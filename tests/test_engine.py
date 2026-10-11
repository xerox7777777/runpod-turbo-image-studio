import importlib.util
import json
import tempfile
import unittest
import concurrent.futures
import time
import sys
from unittest.mock import Mock
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image
import torch
import engine


class FakePipeline:
    calls = []
    def load_lora_weights(self,*args,**kwargs): self.adapter_loaded=True
    def set_adapters(self,*args,**kwargs): self.adapter_strength=kwargs['adapter_weights']
    def unload_lora_weights(self): self.adapter_loaded=False
    def enable_model_cpu_offload(self):
        self.offload_enabled = True
    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(images=[Image.new("RGBA", (kwargs["width"], kwargs["height"]), (0, 100, 200, 128))])


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.output_patch = patch.object(engine, "OUTPUT_DIR", Path(self.tmp))
        self.output_patch.start()
        self.gpu = patch.object(engine.torch.cuda, "is_available", return_value=True)
        self.gpu.start()
        self.memory = patch.object(engine.torch.cuda, 'mem_get_info', return_value=(1024**3,24*1024**3))
        self.memory.start()
        engine._pipeline = FakePipeline()
        FakePipeline.calls.clear()

    def tearDown(self):
        engine._pipeline = None
        self.output_patch.stop()
        self.gpu.stop()
        self.memory.stop()
        # Temporary outputs are left in the ephemeral CI build filesystem.

    def test_gpu_resident_loads_directly_to_cuda(self):
        engine._pipeline = None
        pipe = FakePipeline()
        with patch.object(engine.QwenImage21Pipeline, 'from_pretrained', return_value=pipe) as loader:
            _, _, details = engine.run('boat',512,512,42,memory_mode='gpu_resident')
        self.assertEqual(loader.call_args.kwargs['device_map'],'cuda')
        self.assertEqual(json.loads(details)['offload'],'gpu_resident')
        self.assertFalse(hasattr(pipe,'offload_enabled'))

    def test_auto_selects_resident_only_in_verified_envelope(self):
        with patch.object(engine.torch.cuda,'mem_get_info',return_value=(48*1024**3,48*1024**3)):
            for width,height,cfg,expected in [(1024,1024,1,'gpu_resident'),(2048,2048,1,'model_cpu_offload'),(512,512,2,'model_cpu_offload')]:
                engine._pipeline=None
                with patch.object(engine.QwenImage21Pipeline,'from_pretrained',return_value=FakePipeline()):
                    _, _, details=engine.run('boat',width,height,42,cfg=cfg,negative_prompt='blurry' if cfg>1 else '')
                self.assertEqual(json.loads(details)['offload'],expected)

    def test_bad_memory_mode_rejected(self):
        with self.assertRaises(ValueError):engine.run('boat',512,512,42,memory_mode='invalid')

    def test_generate_and_metadata(self):
        image, filename, details = engine.run("boat", 512, 512, 42)
        self.assertTrue(Path(filename).exists())
        self.assertTrue(Path(filename).with_suffix('.json').exists())
        self.assertEqual(json.loads(details)['seed'], 42)
        self.assertEqual(Image.open(filename).mode, 'RGBA')
        self.assertIn('turbo_run', Image.open(filename).info)
        self.assertTrue(FakePipeline.calls[0]['use_kv_cache'])
        self.assertNotIn('num_inference_steps', FakePipeline.calls[0])
        self.assertNotIn('sigmas', FakePipeline.calls[0])

    def test_experimental_steps_and_metadata(self):
        _,_,details=engine.run('boat',512,512,42,schedule='experimental_linear',steps=4,use_kv_cache=False)
        self.assertEqual(FakePipeline.calls[-1]['sigmas'],[1.0,0.75,0.5,0.25])
        self.assertFalse(FakePipeline.calls[-1]['use_kv_cache'])
        self.assertEqual(json.loads(details)['requested_steps'],4)

    def test_sampling_rejects_ignored_or_bad_controls(self):
        for kwargs in [{'steps':4},{'schedule':'bad'},{'steps':True},{'cfg':float('nan')},{'cfg':2},
                       {'schedule':'experimental_custom','custom_sigmas':'bad'},
                       {'schedule':'experimental_custom','steps':2,'custom_sigmas':'[1,0]'},
                       {'schedule':'experimental_custom','steps':2,'custom_sigmas':'[0.5,1]'}]:
            with self.assertRaises(ValueError): engine.run('boat',512,512,42,**kwargs)

    def test_custom_sigmas_and_cfg_reach_pipeline(self):
        engine.run('boat',512,512,42,schedule='experimental_custom',steps=3,custom_sigmas='[1,0.6,0.2]',cfg=2,negative_prompt='blurry')
        self.assertEqual(FakePipeline.calls[-1]['sigmas'],[1,0.6,0.2])
        self.assertEqual(FakePipeline.calls[-1]['true_cfg_scale'],2)
        self.assertEqual(FakePipeline.calls[-1]['negative_prompt'],'blurry')

    def test_lora_does_not_leak_to_next_request(self):
        path=Path(self.tmp)/'adapter.safetensors';path.write_bytes(b'fixture')
        pipeline=engine._pipeline
        engine.run('boat',512,512,42,lora_path=path,lora_strength=0.5)
        self.assertTrue(pipeline.adapter_loaded)
        self.assertEqual(pipeline.adapter_strength,0.5)
        engine.run('boat',512,512,43)
        self.assertFalse(pipeline.adapter_loaded)

    def test_bad_lora_and_zero_strength(self):
        with self.assertRaises(ValueError): engine.run('boat',512,512,42,lora_path='/missing.safetensors')
        path=Path(self.tmp)/'adapter.safetensors';path.write_bytes(b'fixture')
        engine.run('boat',512,512,42,lora_path=path,lora_strength=0)
        self.assertFalse(getattr(engine._pipeline,'adapter_loaded',False))

    def test_edit_passes_rgba(self):
        engine.run("sunset", 512, 512, 12, Image.new('RGB', (32, 32)))
        self.assertEqual(FakePipeline.calls[0]['image'].mode, 'RGBA')

    def test_random_seed(self):
        _, _, details = engine.run("boat", 512, 512, -1)
        self.assertGreaterEqual(json.loads(details)['seed'], 0)

    def test_invalid_inputs(self):
        for args in [("",512,512,0), ('x',513,512,0), ('x',512,512,-2), ('x',512,512,2**32)]:
            with self.assertRaises(ValueError):
                engine.run(*args)

    def test_no_gpu(self):
        with patch.object(engine.torch.cuda, 'is_available', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'No CUDA'):
                engine.run('x',512,512,0)

    def test_unusual_invalid_inputs_before_loading(self):
        engine._pipeline = None
        with patch.object(engine.QwenImage21Pipeline, 'from_pretrained') as load:
            for value in [None, True, '512', float('nan'), float('inf'), 512.5, 10**1000]:
                with self.assertRaises(ValueError):
                    engine.run('x', value, 512, 0)
                with self.assertRaises(ValueError):
                    engine.run('x', 512, 512, value)
            with self.assertRaisesRegex(ValueError, 'decoded image'):
                engine.run('x',512,512,0,source_image='file.png')
            load.assert_not_called()

    def test_concurrent_requests_are_serialized(self):
        class Busy(FakePipeline):
            active = 0
            peak = 0
            def __call__(self, **kwargs):
                self.active += 1
                self.peak = max(self.peak, self.active)
                time.sleep(0.03)
                result = super().__call__(**kwargs)
                self.active -= 1
                return result
        pipeline = Busy()
        engine._pipeline = pipeline
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(engine.run,'x',512,512,n) for n in (1,2)]
            results = [future.result() for future in futures]
        self.assertEqual(pipeline.peak,1)
        self.assertNotEqual(results[0][1],results[1][1])

    def test_output_failure_and_retry(self):
        for error in [OSError(28,'No space left on device'), PermissionError('read only')]:
            with patch.object(Image.Image,'save',side_effect=error):
                with self.assertRaisesRegex(RuntimeError,'Download/cache/output failed'):
                    engine.run('x',512,512,0)
            self.assertTrue(Path(engine.run('x',512,512,0)[1]).exists())

    def test_failed_download_retry(self):
        engine._pipeline = None
        with patch.object(engine.QwenImage21Pipeline,'from_pretrained',side_effect=[OSError('offline'),FakePipeline()]):
            with self.assertRaises(RuntimeError):
                engine.run('x',512,512,0)
            self.assertIsNone(engine._pipeline)
            self.assertTrue(Path(engine.run('x',512,512,0)[1]).exists())

    def test_oom_retry(self):
        class OOM:
            def __call__(self, **kwargs):
                raise torch.cuda.OutOfMemoryError('test')
        engine._pipeline = OOM()
        with self.assertRaises(RuntimeError):
            engine.run('x',512,512,0)
        with patch.object(engine.QwenImage21Pipeline,'from_pretrained',return_value=FakePipeline()):
            self.assertTrue(Path(engine.run('x',512,512,0)[1]).exists())

    def test_step_callback_cancellation_resets_and_retry_succeeds(self):
        class Cancelled(BaseException):
            pass
        class CallbackPipeline(FakePipeline):
            def __call__(self, **kwargs):
                kwargs['callback_on_step_end'](self,0,0,{'latents':None})
                return super().__call__(**kwargs)
        def cancel(*args):
            raise Cancelled('cancelled by user')
        engine._pipeline = CallbackPipeline()
        with self.assertRaises(Cancelled):
            engine.run('x',512,512,0,step_callback=cancel)
        self.assertIsNone(engine._pipeline)
        self.assertEqual(list(Path(self.tmp).glob('*.png')),[])
        with patch.object(engine.QwenImage21Pipeline,'from_pretrained',return_value=FakePipeline()):
            self.assertTrue(Path(engine.run('x',512,512,0)[1]).exists())

    def test_oom_resets_pipeline(self):
        class OOM:
            def __call__(self, **kwargs):
                raise torch.cuda.OutOfMemoryError('test')
        engine._pipeline = OOM()
        with self.assertRaisesRegex(RuntimeError,'GPU memory exhausted'):
            engine.run('x',512,512,0)
        self.assertIsNone(engine._pipeline)

    def test_download_error(self):
        engine._pipeline = None
        with patch.object(engine.QwenImage21Pipeline, 'from_pretrained', side_effect=OSError('test')):
            with self.assertRaisesRegex(RuntimeError,'Download/cache/output failed'):
                engine.run('x',512,512,0)

    def test_load_official_pinned_checkpoint(self):
        engine._pipeline = None
        candidate = FakePipeline()
        with patch.object(engine.QwenImage21Pipeline, 'from_pretrained', return_value=candidate) as load:
            engine.run('x',512,512,0)
        load.assert_called_once_with(engine.MODEL_ID, revision=engine.MODEL_REVISION, dtype=torch.bfloat16)
        self.assertTrue(candidate.offload_enabled)

    def test_comfy_nodes(self):
        spec=importlib.util.spec_from_file_location('turbo_node', Path(__file__).resolve().parents[1]/'custom_nodes/turbo_official/__init__.py')
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        img, mask, details=mod.TurboGenerate().generate('x',512,512,42)
        self.assertEqual(tuple(img.shape),(1,512,512,3))
        self.assertEqual(tuple(mask.shape),(1,512,512))
        mod.TurboEdit().generate('sunset',512,512,42,torch.zeros(1,32,32,3))
        with self.assertRaisesRegex(ValueError,'one input image'):
            mod.TurboEdit().generate('x',512,512,42,torch.zeros(2,32,32,3))

    def test_resolution_modes_and_invalid_requests(self):
        spec=importlib.util.spec_from_file_location('resolution_node',Path(__file__).resolve().parents[1]/'custom_nodes/turbo_official/__init__.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        node=mod.TurboResolution()
        self.assertEqual(node.calculate('aspect_ratio','1:1',1.048576,1,1024,1024)[:2],(1024,1024))
        for ratio in node.RATIOS:
            w,h,_=node.calculate('aspect_ratio',ratio,1.048576,1,1024,1024)
            self.assertEqual((w%16,h%16),(0,0))
            self.assertLessEqual(w*h,1024*1024)
            self.assertLess(abs(w/h-node.RATIOS[ratio]),0.04)
        w,h,_=node.calculate('match_input','1:1',1.048576,1,1024,1024,torch.zeros(1,64,96,3))
        self.assertLess(abs(w/h-1.5),0.04)
        self.assertEqual(node.calculate('manual','1:1',1.048576,1.5,1024,1024)[:2],(1536,1536))
        self.assertEqual(node.calculate('aspect_ratio','1:1',1.048576,2,1024,1024)[:2],(2048,2048))
        for mode,mp,mult,img in [('match_input',1,1,None),('match_input',1,1,torch.zeros(2,32,32,3)),('unknown',1,1,None),('aspect_ratio',float('nan'),1,None),('aspect_ratio',1,float('inf'),None),('aspect_ratio',4,2,None),('aspect_ratio',0.25,0.25,None)]:
            with self.assertRaises(ValueError):node.calculate(mode,'1:1',mp,mult,1024,1024,img)

    def test_retired_workflow_archive_preserves_user_edits(self):
        import workspace,hashlib
        root=Path(self.tmp)/'migration';app=root/'app';baked=root/'baked';target=root/'workspace'
        app.mkdir(parents=True);baked.mkdir();(app/'custom_nodes/turbo_official/web').mkdir(parents=True)
        for name in ('engine.py','request_guard.py','custom_nodes/turbo_official/__init__.py'):(app/name).write_text('# fixture')
        original={'nodes':[],'version':0.4};canonical=json.dumps(original,sort_keys=True,separators=(',',':'))
        (app/'retired-workflows.json').write_text(json.dumps({'legacy.json':[hashlib.sha256(canonical.encode()).hexdigest()],'edited.json':[hashlib.sha256(canonical.encode()).hexdigest()]}))
        comfy=workspace.prepare(target,baked,app);folder=comfy/'user/default/workflows'
        (folder/'legacy.json').write_text(json.dumps(original,indent=2));(folder/'edited.json').write_text(json.dumps({'nodes':[],'version':0.4,'user_changes':True}))
        workspace.prepare(target,baked,app)
        self.assertFalse((folder/'legacy.json').exists())
        self.assertTrue((target/'backups/retired-workflows/legacy.json').exists())
        self.assertTrue((folder/'edited.json').exists())

    def test_saved_result_displays_original_without_creating_copy(self):
        spec=importlib.util.spec_from_file_location('turbo_saved_node',Path(__file__).resolve().parents[1]/'custom_nodes/turbo_official/__init__.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        _,filename,details=engine.run('boat',512,512,42)
        with patch.dict(sys.modules,{'folder_paths':SimpleNamespace(get_output_directory=lambda:self.tmp)}):
            result=mod.TurboSavedResult().show(details)
            self.assertEqual(result['ui']['images'][0]['filename'],Path(filename).name)
            self.assertEqual(len(list(Path(self.tmp).glob('*.png'))),1)
            with self.assertRaises(ValueError):mod.TurboSavedResult().show(json.dumps({'output_filename':'../outside.png'}))

    def test_comfy_progress_and_interrupt_callback(self):
        spec=importlib.util.spec_from_file_location('turbo_callback_node', Path(__file__).resolve().parents[1]/'custom_nodes/turbo_official/__init__.py')
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        progress=Mock()
        interrupt=Mock()
        modules={'comfy':SimpleNamespace(), 'comfy.utils':SimpleNamespace(ProgressBar=Mock(return_value=progress)),
                 'comfy.model_management':SimpleNamespace(throw_exception_if_processing_interrupted=interrupt)}
        with patch.dict(sys.modules,modules):
            callback=mod.TurboGenerate.step_callback()
            tensors={'latents':'unchanged'}
            self.assertIs(callback(SimpleNamespace(num_timesteps=8),2,0,tensors),tensors)
        interrupt.assert_called_once_with()
        progress.update_absolute.assert_called_once_with(3,8)

if __name__ == '__main__':
    unittest.main()
