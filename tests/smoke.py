"""CPU startup checks of real installed apps, no model downloads or inference."""
import json
import base64
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error
import signal
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

SMOKE_WORKSPACE=Path('/tmp/turbo-smoke-workspace')
SMOKE_TOKEN='build-only-random-looking-token-0728394'

def jupyter_request(path, payload=None, token=SMOKE_TOKEN):
    body=json.dumps(payload).encode() if payload is not None else None
    headers={'Authorization':'token '+token,'Content-Type':'application/json'} if token else {'Content-Type':'application/json'}
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8888'+path,data=body,headers=headers,
            method='PUT' if payload is not None else 'GET'),timeout=10) as response:
        return json.load(response)

def studio_verify(data):
    state=json.loads(data)
    assert state['ready'],state
    root=jupyter_request('/api/contents')
    assert 'ComfyUI' in [item['name'] for item in root['content']]
    for token in ('', 'incorrect-token'):
        try:
            jupyter_request('/api/status',token=token)
        except urllib.error.HTTPError as error:
            assert error.code in (401,403),error.code
        else:
            raise AssertionError('Jupyter allowed an unauthenticated API request')
    print('PASS Jupyter per-Pod token, unauthorized access rejected, workspace root visible',flush=True)
    # A synthetic file tests upload/loader discovery without third-party weights.
    jupyter_request('/api/contents/ComfyUI/models/checkpoints/upload-test.safetensors',{
        'type':'file','format':'base64','content':base64.b64encode(b'not a real model; folder discovery test').decode()})
    with urllib.request.urlopen('http://127.0.0.1:8188/object_info') as response:
        info=json.load(response)
    assert 'upload-test.safetensors' in info['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'cell_type':'code','id':'test','source':'2 + 2','metadata':{},'execution_count':None,'outputs':[]}]}
    jupyter_request('/api/contents/upload-test.ipynb',{'type':'notebook','format':'json','content':notebook})
    assert jupyter_request('/api/contents/upload-test.ipynb')['content']['cells'][0]['source']=='2 + 2'
    print('PASS Jupyter file/notebook upload and native ComfyUI checkpoint discovery',flush=True)
    with urllib.request.urlopen('http://127.0.0.1:8188/object_info') as response:
        comfy_verify(response.read())
    try:
        urllib.request.urlopen('http://127.0.0.1:7860',timeout=1)
    except OSError:
        pass
    else:
        raise AssertionError('Unused Gradio port unexpectedly serves')
    saved=SMOKE_WORKSPACE/'ComfyUI/user/default/workflows/text-to-image.json'
    workflow=json.loads(saved.read_text())
    workflow.setdefault('extra',{})['restart_test']='preserved'
    saved.write_text(json.dumps(workflow))
    # Prove a dead ComfyUI leaves Jupyter and the startup page usable.
    child_ids=Path(f'/proc/{STUDIO_PID}/task/{STUDIO_PID}/children').read_text().split()
    child=next(int(pid) for pid in child_ids if b'ComfyUI/main.py' in Path('/proc/'+pid+'/cmdline').read_bytes())
    os.kill(child,signal.SIGTERM)
    for _ in range(15):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/health') as response:
                state=json.load(response)
        except urllib.error.HTTPError as error:
            state=json.load(error)
        if state['comfyui']=='failed':
            break
        time.sleep(1)
    assert state['comfyui']=='failed' and state['jupyter']=='ready',state
    assert jupyter_request('/api/status')
    print('PASS ComfyUI crash is visible; Jupyter remains available for repairs',flush=True)

def comfy_verify(data):
    info=json.loads(data)
    assert 'OfficialTurboGenerate' in info and 'OfficialTurboEdit' in info
    for body in [b'{broken', b'null', b'[]', b'{}', b'{"prompt":{}}', b'{"prompt":{"1":null}}', b'{"prompt":{"1":{"class_type":"X","inputs":[]}}}']:
        for route in ('/prompt','/api/prompt'):
            request=urllib.request.Request('http://127.0.0.1:8188'+route,data=body,headers={'Content-Type':'application/json'})
            try:
                urllib.request.urlopen(request,timeout=5)
            except urllib.error.HTTPError as exc:
                assert exc.code == 400, (route,body,exc.code)
                assert 'error' in json.loads(exc.read())
            else:
                raise AssertionError('Invalid request accepted: '+repr(body))
    print('PASS seven malformed request envelopes on both prompt routes rejected with HTTP 400',flush=True)
    for path in Path('/app/workflows/api').glob('*.json'):
        workflow=json.loads(path.read_text())
        for node in workflow.values():
            assert node['class_type'] in info, (path,node['class_type'])
            required=info[node['class_type']]['input'].get('required',{})
            assert set(required)<=set(node['inputs']), (path,required)
        if '3' in workflow:
            Image.new('RGB',(64,64),(40,100,200)).save(SMOKE_WORKSPACE/'ComfyUI/input/smoke-input.png')
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

env=dict(os.environ, OUTPUT_DIR=str(SMOKE_WORKSPACE/'outputs'), WORKSPACE_DIR=str(SMOKE_WORKSPACE),
         JUPYTER_PASSWORD=SMOKE_TOKEN, CUDA_VISIBLE_DEVICES='')
STUDIO_PID=None
# Capture the supervisor PID for the controlled service-crash test.
original_popen=subprocess.Popen
def capture_popen(*args,**kwargs):
    global STUDIO_PID
    process=original_popen(*args,**kwargs)
    STUDIO_PID=process.pid
    return process
subprocess.Popen=capture_popen
check([sys.executable,'/app/startup.py','--cpu','--skip-platform'],
      'http://127.0.0.1:8080/health',studio_verify,env)

def verify_restart(data):
    assert json.loads(data)['ready']
    saved=SMOKE_WORKSPACE/'ComfyUI/user/default/workflows/text-to-image.json'
    assert json.loads(saved.read_text())['extra']['restart_test']=='preserved'
    assert jupyter_request('/api/contents/ComfyUI/models/checkpoints/upload-test.safetensors')
    print('PASS restart preserves uploaded model, notebook and user-edited workflow',flush=True)

check([sys.executable,'/app/startup.py','--cpu','--skip-platform'],
      'http://127.0.0.1:8080/health',verify_restart,env)
