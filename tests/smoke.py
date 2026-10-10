"""CPU startup checks of real installed apps, no model downloads or inference."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from PIL import Image

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
        if '3' in workflow:
            Image.new('RGB',(64,64),(40,100,200)).save('/opt/ComfyUI/input/smoke-input.png')
            workflow['3']['inputs']['image']='smoke-input.png'
        request=urllib.request.Request('http://127.0.0.1:8188/prompt',
                                       data=json.dumps({'prompt':workflow}).encode(),
                                       headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=5) as response:
            queued=json.load(response)
        for _ in range(30):
            with urllib.request.urlopen('http://127.0.0.1:8188/history/'+queued['prompt_id'],timeout=5) as response:
                history=json.load(response)
            if queued['prompt_id'] in history:
                messages=history[queued['prompt_id']]['status']['messages']
                errors=[m[1] for m in messages if m[0]=='execution_error']
                assert errors and 'No CUDA GPU' in errors[0]['exception_message'], (path,messages)
                print('PASS workflow queued and missing-GPU error returned:',path.name,flush=True)
                break
            time.sleep(0.5)
        else:
            raise AssertionError('Workflow did not finish '+path.name)
    print('PASS four workflow API node/input schemas',flush=True)

env=dict(os.environ, OUTPUT_DIR='/tmp/turbo-smoke-outputs', PORT='7860')
check([sys.executable,'/app/app.py'],'http://127.0.0.1:7860/config',gradio_verify,env)
check([sys.executable,'/opt/ComfyUI/main.py','--cpu','--listen','127.0.0.1','--port','8188','--disable-auto-launch'],
      'http://127.0.0.1:8188/object_info',comfy_verify,env)
