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
        engine._pipeline = FakePipeline()
        FakePipeline.calls.clear()

    def tearDown(self):
        engine._pipeline = None
        self.output_patch.stop()
        self.gpu.stop()
        # Temporary outputs are left in the ephemeral CI build filesystem.

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
        class Cancelled(Exception):
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
            self.assertIs(callback(SimpleNamespace(timesteps=range(8)),2,0,tensors),tensors)
        interrupt.assert_called_once_with()
        progress.update_absolute.assert_called_once_with(3,8)

if __name__ == '__main__':
    unittest.main()
