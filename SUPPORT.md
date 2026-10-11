# Community support

Report reproducible wrapper/workflow/startup bugs in [GitHub Issues](https://github.com/xerox7777777/runpod-turbo-image-studio/issues). Include image version, GPU/VRAM, system RAM, storage mount, workflow and relevant logs. Remove tokens, credentials, proxy URLs and private content. Community support has no guaranteed response time; RunPod handles platform/billing issues and Qwen handles upstream model issues.

## An interface will not open

1. Check the image version and Connect HTTP ports: **8080 status**, **8188 ComfyUI**, **8888 JupyterLab**. Port 7860 was removed. A Pod created before this template update keeps its old configuration; deploy the new template, or update its image, ports and Start Jupyter setting then restart. Save existing container outputs before any reset.
2. Running can mean the host is still pulling/extracting the image. The proxy may return 404 then 502 before a service binds. Open 8080 after the container starts and wait for both services to say ready.
3. Jupyter asks for your per-Pod token from RunPod → Connect. Do not use a shared password. Without a platform-supplied token, use SSH and `jupyter server list` to retrieve the generated token. Wrong/missing tokens cannot access its files or terminals.
4. Open `/workspace/logs/comfyui.log`, `jupyter.log` and `service-status.json` in Jupyter or over SSH. ComfyUI failure leaves Jupyter available. Correct the error, then restart from RunPod. There is no automatic service restart or additional paid deployment.
5. Existing unrelated `/workspace/ComfyUI` is not overwritten. Back up/rename it through Jupyter and use this template's pinned bundle, or deploy with an empty workspace. A partly copied first-boot installation without its revision marker is also reported as a conflict.
6. If both services are unavailable, inspect container startup logs in RunPod. If the host cannot restart because its GPU was rented by someone else, use RunPod migration or choose another available host; application changes cannot create host capacity.

## Proxy 403 and Jupyter login

A proxy HTTP 403 is different from an application still starting. During v0.3.3 testing, RunPod/Cloudflare returned `error code: 1010` for the default Python client signature and accepted a browser signature for the same endpoint. A normal browser opened both applications. This does not establish the exact cause of every Chrome 403; record the response, Pod ID, time and service readiness for RunPod platform support. See [Cloudflare error 1010](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/).

Jupyter login behind the proxy previously rejected the external Origin because RunPod forwards an internal Host. v0.3.3 allows only that Pod’s exact Jupyter proxy origin, with token authentication and CSRF checks retained. Do not work around access errors by disabling authentication or allowing every origin. SSH tunneling remains an alternative when platform proxy access fails.

## Models and storage

Open [MODEL_FOLDERS.md](MODEL_FOLDERS.md) or `/workspace/START_HERE.ipynb`. Upload small files in Jupyter; download large models directly through its Terminal. Standard ComfyUI models must use compatible workflows. The official Turbo nodes do not automatically load checkpoints/LoRAs added to other folders. Custom-node requirements are not automatically installed.

A volume mounted at `/workspace` preserves files. Without one, they are temporary. Download original outputs before stopping; volume storage can still bill after GPU compute stops. An empty cache does not prevent the interfaces from opening; the first queued Turbo request downloads official weights.

## Inference errors

* Missing input: upload/select an image in LoadImage before queuing image-edit.
* Bad prompt/size: use a nonempty prompt and dimensions 512–2752 divisible by 16. Single-image editing accepts one image per request.
* No CUDA: choose an NVIDIA GPU; CPU startup checks cannot generate images.
* OOM: use smaller dimensions, close other workloads or choose more VRAM/RAM. OOM clears the pipeline before retry. A40 with 50 GB system RAM was tested, not established as a universal minimum.
* Download/cache/output failure: check disk space, network access and permissions. Cached Hugging Face downloads resume on retry. Larger user models need more storage.
* Cancel/loading: cancellation is checked between denoising steps and may wait for an in-flight operation or initial load. After cancellation the next request reloads the model.
* Repeated result: identical inputs and seed can reuse ComfyUI's cache. Change the seed for a fresh execution.

## Access

Jupyter requires its per-Pod token. ComfyUI is unauthenticated by default; for private access set `COMFY_LISTEN=127.0.0.1` and use SSH tunneling. Gradio was removed and old UI_USERNAME/UI_PASSWORD settings do not protect ComfyUI.
