"""Prepare editable ComfyUI files while preserving user models and workflows."""
import json
import hashlib
import shutil
import uuid
from pathlib import Path

CORE_REVISION = '7f7fd918ed0815c5d5ef2ccfe44bfc8e72cfd217'
MODEL_FOLDERS = ('checkpoints', 'diffusion_models', 'text_encoders', 'vae', 'loras',
                 'controlnet', 'upscale_models', 'embeddings', 'clip', 'clip_vision')


def inside(root, path):
    root, resolved = Path(root).resolve(), Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Workspace path points outside the workspace: '+str(path))
    return Path(path)


def prepare(workspace, baked, app):
    workspace, baked, app = Path(workspace), Path(baked), Path(app)
    workspace.mkdir(parents=True, exist_ok=True)
    comfy = inside(workspace, workspace/'ComfyUI')
    marker = comfy/'.turbo-core-revision'
    # Never overwrite an unrelated installation or silently change its core.
    if comfy.exists():
        if not marker.exists() or marker.read_text().strip() != CORE_REVISION:
            raise ValueError('Existing ComfyUI installation is not this pinned bundle. '
                             'Use an empty workspace or rename it in Jupyter before restarting.')
    else:
        def ignore_bundle(path, names):
            ignored = {name for name in names if name in ('.git', '__pycache__')}
            if Path(path) == baked:
                ignored.update(set(names) & {'input', 'output', 'user'})
            if Path(path) == baked/'custom_nodes':
                ignored.update(set(names) & {'turbo_official'})
            return ignored
        shutil.copytree(baked, comfy, symlinks=True, ignore=ignore_bundle)
        marker.write_text(CORE_REVISION)
    for name in MODEL_FOLDERS:
        inside(workspace, comfy/'models'/name).mkdir(parents=True, exist_ok=True)
    for name, legacy in [('input', 'inputs'), ('output', 'outputs'), ('user', 'comfyui-user')]:
        target = inside(workspace, workspace/legacy)
        target.mkdir(parents=True, exist_ok=True)
        alias = comfy/name
        if not alias.exists() and not alias.is_symlink():
            alias.symlink_to(target, target_is_directory=True)
        inside(workspace, alias).mkdir(parents=True, exist_ok=True)
    workflow_dir = inside(workspace, comfy/'user'/'default'/'workflows')
    workflow_dir.mkdir(parents=True, exist_ok=True)
    retired_manifest = app/'retired-workflows.json'
    if retired_manifest.exists():
        for name, fingerprints in json.loads(retired_manifest.read_text()).items():
            previous = inside(workspace, workflow_dir/name)
            if not previous.is_file() or previous.is_symlink():
                continue
            try:
                canonical = json.dumps(json.loads(previous.read_text()), sort_keys=True, separators=(',', ':'))
            except (ValueError, UnicodeError):
                continue
            if hashlib.sha256(canonical.encode()).hexdigest() not in fingerprints:
                continue  # Preserve any user-edited workflow.
            archive = inside(workspace, workspace/'backups'/'retired-workflows'/name)
            archive.parent.mkdir(parents=True, exist_ok=True)
            if archive.exists():
                archive = inside(workspace, archive.with_name(archive.stem+'-'+uuid.uuid4().hex+archive.suffix))
            shutil.move(str(previous), str(archive))  # Recoverable archive, no deletion.
    example = app/'examples'/'mug-before.png'
    if example.exists() and not (comfy/'input'/'example-red-mug.png').exists():
        shutil.copy2(example,inside(workspace,comfy/'input'/'example-red-mug.png'))
    for source in (app/'workflows').glob('*.json'):
        dest = inside(workspace, workflow_dir/source.name)
        if not dest.exists():
            shutil.copy2(source, dest)
    node = inside(workspace, comfy/'custom_nodes'/'turbo_official')
    node.mkdir(parents=True, exist_ok=True)
    # These three image-owned files update with the image; preserve prior contents.
    managed = [(app/'engine.py', comfy/'engine.py'),
               (app/'request_guard.py', comfy/'request_guard.py'),
               (app/'custom_nodes'/'turbo_official'/'__init__.py', node/'__init__.py')]
    managed.extend((source,node/source.relative_to(app/'custom_nodes'/'turbo_official'))
                   for source in (app/'custom_nodes'/'turbo_official'/'web').glob('*.js'))
    for source, dest in managed:
        inside(workspace, dest)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes() != source.read_bytes():
            backup = inside(workspace, workspace/'backups'/dest.relative_to(comfy))
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(dest, backup)
        shutil.copy2(source, dest)
    for name in ('START_HERE.ipynb', 'MODEL_FOLDERS.md', 'TURBO_WORKFLOWS.md', 'Turbo-Workflow-Guide-v0.4.ipynb'):
        if not (app/name).exists(): continue
        destination = inside(workspace, workspace/name)
        if not destination.exists():
            shutil.copy2(app/name, destination)
    return comfy
