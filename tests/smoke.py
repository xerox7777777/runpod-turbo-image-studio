"""CPU startup checks of real installed apps, no model downloads or inference."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

def check(command, url, verify, env=None):
    process = subprocess.Popen(command, env=env)
    try:
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError(f'Server exited {process.returncode}: {command}')
            try:
                with urllib.request.urlopen(url,timeout=2) as r:
                    data=r.read()
                verify(data)
                print('PASS HTTP startup:',url,flush=True)
                return
            except (OSError, TimeoutError):
                time.sleep(1)
        raise RuntimeError(f'Server did not become healthy: {url}')
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

def gradio_verify(data):
    config=json.loads(data)
    assert len(config['dependencies'])>=2
    assert config['title']=='Turbo Image Studio'

def comfy_verify(data):
    info=json.loads(data)
    assert 'OfficialTurboGenerate' in info and 'OfficialTurboEdit' in info
    for path in Path('/app/workflows/api').glob('*.json'):
        workflow=json.loads(path.read_text())
        for node in workflow.values():
            assert node['class_type'] in info, (path,node['class_type'])
            required=info[node['class_type']]['input'].get('required',{})
            assert set(required)<=set(node['inputs']), (path,required)
    print('PASS four workflow API node/input schemas',flush=True)

env=dict(os.environ, OUTPUT_DIR='/tmp/turbo-smoke-outputs', PORT='7860')
check([sys.executable,'/app/app.py'],'http://127.0.0.1:7860/config',gradio_verify,env)
check([sys.executable,'/opt/ComfyUI/main.py','--cpu','--listen','127.0.0.1','--port','8188','--disable-auto-launch'],
      'http://127.0.0.1:8188/object_info',comfy_verify,env)
