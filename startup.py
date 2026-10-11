"""Run independent ComfyUI, authenticated JupyterLab and a startup status page."""
import argparse
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from workspace import prepare, inside

APP = Path(__file__).resolve().parent
STATE = {'version': 'v0.4.5', 'comfyui': 'starting', 'jupyter': 'starting',
         'message': 'Preparing workspace. Model downloads begin only on the first queued request.'}
STOP = threading.Event()


def safe_log(text, token):
    return text.replace(token, '[redacted]') if token else text


def proxy_origin(pod_id):
    if re.fullmatch(r'[a-z0-9-]{1,64}', pod_id):
        return 'https://'+pod_id+'-8888.proxy.runpod.net'
    return ''


def probe(url, token=None):
    headers = {'Authorization': 'token '+token} if token else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=1) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


class StatusHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path in ('/health', '/healthz'):
            data = dict(STATE)
            data['ready'] = data['comfyui'] == data['jupyter'] == 'ready'
            body = json.dumps(data).encode()
            self.send_response(200 if data['ready'] else 503)
            content_type = 'application/json'
        elif self.path == '/':
            body = (APP/'status.html').read_bytes()
            self.send_response(200)
            content_type = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def launch(name, command, logs, token, env=None):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1, env=env, start_new_session=True)
    def drain():
        with (logs/(name+'.log')).open('a') as output:
            for line in process.stdout:
                redacted = safe_log(line, token)
                output.write(redacted)
                output.flush()
                print('['+name+'] '+redacted.rstrip(), flush=True)
    threading.Thread(target=drain, daemon=True).start()
    return process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cpu', action='store_true', help='CPU startup checks; no Turbo inference')
    parser.add_argument('--skip-platform', action='store_true', help='Container build smoke tests only')
    args = parser.parse_args()
    workspace = Path(os.environ.get('WORKSPACE_DIR', '/workspace')).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if workspace == Path('/'):
        raise ValueError('WORKSPACE_DIR must not be the filesystem root')
    logs = inside(workspace, workspace/'logs')
    logs.mkdir(exist_ok=True)
    token = os.environ.get('JUPYTER_PASSWORD') or secrets.token_urlsafe(32)
    # The token is per Pod, never a value saved in the public template or dashboard.
    config = {'IdentityProvider': {'token': token}, 'ServerApp': {
        'ip': '0.0.0.0', 'port': 8888, 'port_retries': 0, 'root_dir': str(workspace),
        'allow_root': True, 'open_browser': False, 'allow_remote_access': True,
        'trust_xheaders': True, 'allow_origin': proxy_origin(os.environ.get('RUNPOD_POD_ID', '')),
        'jpserver_extensions': {'jupyter_workspace_routes': True}},
        'FileContentsManager': {'delete_to_trash': True}}
    config_path = Path(tempfile.gettempdir())/('turbo-jupyter-'+str(os.getpid())+'.json')
    fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(config, file)
    services = {}
    server = ThreadingHTTPServer(('0.0.0.0', 8080), StatusHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    def stop(*_):
        STOP.set()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        if not args.skip_platform:
            # Base /start.sh keeps SSH/nginx alive. This supervisor owns Jupyter.
            platform_env = dict(os.environ, JUPYTER_PASSWORD='', JUPYTER_DISABLE_AUTH='false')
            services['platform'] = launch('platform', ['/start.sh'], logs, token, platform_env)
        services['jupyter'] = launch('jupyter', [sys.executable, '-m', 'jupyterlab', '--config='+str(config_path)], logs, token)
        print('Jupyter uses the per-Pod token from Connect. Without that setting, retrieve it with jupyter server list over SSH.', flush=True)
        try:
            comfy = prepare(workspace, Path('/opt/ComfyUI'), APP)
            command = [sys.executable, '-u', str(comfy/'main.py'), '--listen', os.environ.get('COMFY_LISTEN', '0.0.0.0'),
                       '--port', '8188', '--user-directory', str(comfy/'user'), '--input-directory', str(comfy/'input'),
                       '--output-directory', str(comfy/'output'), '--disable-auto-launch', '--enable-manager']
            if args.cpu:
                command.append('--cpu')
            services['comfyui'] = launch('comfyui', command, logs, token)
            STATE['message'] = 'Services are starting. Check the status below; Running in RunPod does not mean ready.'
        except Exception as exc:
            STATE['comfyui'] = 'failed'
            STATE['message'] = safe_log(str(exc), token)
            print('Workspace preparation failed: '+STATE['message'], flush=True)
        previous = {}
        while not STOP.wait(1):
            for name, url in [('comfyui', 'http://127.0.0.1:8188/system_stats'), ('jupyter', 'http://127.0.0.1:8888/api/status')]:
                process = services.get(name)
                if process is None or process.poll() is not None:
                    STATE[name] = 'failed'
                    if process is not None:
                        STATE['message'] = name+' exited with code '+str(process.returncode)+'. Open logs/'+name+'.log in Jupyter, fix the cause and restart the Pod.'
                else:
                    STATE[name] = 'ready' if probe(url, token if name == 'jupyter' else None) else 'starting'
            if STATE['comfyui'] == STATE['jupyter'] == 'ready':
                STATE['message'] = 'Ready. Open ComfyUI for generation or JupyterLab to manage files. No model has been downloaded just by starting the services.'
            if previous != STATE:
                print('Service status: '+json.dumps(STATE), flush=True)
                previous = dict(STATE)
            (logs/'service-status.json').write_text(json.dumps(STATE, indent=2))
    finally:
        for process in services.values():
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for process in services.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        server.shutdown()


if __name__ == '__main__':
    main()
