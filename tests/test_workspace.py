import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import workspace
import startup


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='turbo-workspace-test-'))
        self.baked, self.app, self.volume = (self.root/n for n in ('baked', 'app', 'volume'))
        self.baked.mkdir()
        (self.baked/'main.py').write_text('# pinned source')
        self.app.mkdir()
        for name in ('engine.py', 'request_guard.py', 'START_HERE.ipynb', 'MODEL_FOLDERS.md'):
            (self.app/name).write_text('bundled')
        (self.app/'custom_nodes'/'turbo_official').mkdir(parents=True)
        (self.app/'custom_nodes'/'turbo_official'/'__init__.py').write_text('node')
        (self.app/'workflows').mkdir()
        (self.app/'workflows'/'image-edit.json').write_text('bundled workflow')

    def test_folders_and_legacy_aliases(self):
        comfy = workspace.prepare(self.volume, self.baked, self.app)
        for name in workspace.MODEL_FOLDERS:
            self.assertTrue((comfy/'models'/name).is_dir())
        self.assertEqual((comfy/'output').resolve(), self.volume/'outputs')
        self.assertTrue((self.volume/'START_HERE.ipynb').exists())

    def test_internal_input_package_is_preserved(self):
        package = self.baked/'comfy_api'/'input'
        package.mkdir(parents=True)
        (package/'__init__.py').write_text('internal API')
        (self.baked/'input').mkdir()
        comfy = workspace.prepare(self.volume, self.baked, self.app)
        self.assertEqual((comfy/'comfy_api'/'input'/'__init__.py').read_text(), 'internal API')
        self.assertEqual((comfy/'input').resolve(), self.volume/'inputs')

    def test_restart_preserves_models_workflows_and_custom_nodes(self):
        comfy = workspace.prepare(self.volume, self.baked, self.app)
        saved = comfy/'user'/'default'/'workflows'/'image-edit.json'
        saved.write_text('my edited workflow')
        model = comfy/'models'/'checkpoints'/'my-model.safetensors'
        model.write_bytes(b'user model')
        node = comfy/'custom_nodes'/'my-node.py'
        node.write_text('user node')
        workspace.prepare(self.volume, self.baked, self.app)
        self.assertEqual(saved.read_text(), 'my edited workflow')
        self.assertEqual(model.read_bytes(), b'user model')
        self.assertEqual(node.read_text(), 'user node')

    def test_owned_runtime_update_has_backup(self):
        comfy = workspace.prepare(self.volume, self.baked, self.app)
        (comfy/'engine.py').write_text('previous engine')
        workspace.prepare(self.volume, self.baked, self.app)
        self.assertEqual((self.volume/'backups'/'engine.py').read_text(), 'previous engine')
        self.assertEqual((comfy/'engine.py').read_text(), 'bundled')

    def test_foreign_install_not_overwritten(self):
        (self.volume/'ComfyUI').mkdir(parents=True)
        (self.volume/'ComfyUI'/'main.py').write_text('foreign')
        with self.assertRaisesRegex(ValueError, 'Existing ComfyUI'):
            workspace.prepare(self.volume, self.baked, self.app)
        self.assertEqual((self.volume/'ComfyUI'/'main.py').read_text(), 'foreign')

    def test_external_symlink_rejected(self):
        self.volume.mkdir()
        (self.volume/'ComfyUI').symlink_to(self.baked, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'outside the workspace'):
            workspace.prepare(self.volume, self.baked, self.app)

    def test_logs_redact_token(self):
        self.assertEqual(startup.safe_log('url?token=secret-token', 'secret-token'), 'url?token=[redacted]')


if __name__ == '__main__':
    unittest.main()
