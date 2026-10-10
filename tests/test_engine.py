import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image
import torch
import engine


class FakePipeline:
    calls = []
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

if __name__ == '__main__':
    unittest.main()
