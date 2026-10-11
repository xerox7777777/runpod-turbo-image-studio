# Turbo Image Studio for RunPod

[Deploy the public Pod template](https://console.runpod.io/hub/template/92ov0cv1fr) · [Workflows](workflows) · [Support](SUPPORT.md)

ComfyUI generation and single-image editing with the official **Qwen/Qwen-Image-2.1-Turbo** checkpoint. Official weights download directly from Qwen on the first queued request. No third-party checkpoint or LoRA is included. Gradio was removed in v0.3.1.

## Open your Pod

| RunPod Connect port | What opens |
| --- | --- |
| **8080 HTTP** | Startup status and links to both interfaces |
| **8188 HTTP** | ComfyUI |
| **8888 HTTP** | JupyterLab: file browser, notebooks and terminal |
| 22 TCP | SSH, when enabled and a public key is registered |

Start your Pod and wait for the container pull to finish. **Running does not mean the services are ready.** Open 8080 to check; both services should say ready. Before the container itself starts, even this status page may return 404/502. There is no fixed startup-time guarantee.

Jupyter requires a unique per-Pod token. Use the Jupyter connection/token under RunPod → Connect; the public template enables Start Jupyter and contains no shared password. If deploying the container outside that template, supply your own `JUPYTER_PASSWORD`; without one it generates a token retrievable over SSH with `jupyter server list`. Authentication is never disabled by a blank token or `JUPYTER_DISABLE_AUTH`.

Open `START_HERE.ipynb` in Jupyter for instructions. To use Turbo, close ComfyUI's generic Templates gallery, open Workflows in the sidebar and double-click a bundled workflow:

| Workflow | Purpose |
| --- | --- |
| [text-to-image](workflows/text-to-image.json) | 1024×1024 generation |
| [portrait](workflows/portrait.json) | 768×1024 generation |
| [landscape](workflows/landscape.json) | 1024×768 generation |
| [image-edit](workflows/image-edit.json) | Upload/select an image in LoadImage, then describe changes |

The first queued request downloads roughly 32 GB of official checkpoint files. Opening either interface does not download weights. The bundled OfficialTurbo nodes call Qwen's official Diffusers pipeline with its saved Turbo schedule and KV caching. They support generation and single-image editing; masked inpainting, multi-image editing, upscaling and Turbo LoRA loading are not included. Identical inputs/seed may reuse ComfyUI's cache; change the seed for a fresh result.

## Files and your own models

ComfyUI is copied from the pinned image into **`/workspace/ComfyUI`** on first boot. The application source, custom nodes and model folders are visible in Jupyter. User-edited workflows, model files and user-added custom nodes are preserved on restart when the workspace storage is retained. An unrelated existing ComfyUI installation is left untouched and reported as a setup conflict; use an empty workspace or rename that installation before restarting. The image-owned Turbo runtime files update with the image and prior differing contents are backed up under `/workspace/backups`.

| Files | Path |
| --- | --- |
| Checkpoints | `/workspace/ComfyUI/models/checkpoints` |
| Diffusion models | `/workspace/ComfyUI/models/diffusion_models` |
| Text encoders | `/workspace/ComfyUI/models/text_encoders` |
| VAEs | `/workspace/ComfyUI/models/vae` |
| Compatible LoRAs | `/workspace/ComfyUI/models/loras` |
| Custom nodes | `/workspace/ComfyUI/custom_nodes` |
| Saved workflows | `/workspace/ComfyUI/user/default/workflows` |
| Inputs / outputs | `/workspace/ComfyUI/input` / `output` |
| Official Turbo cache | `/workspace/.cache/huggingface` |
| Logs | `/workspace/logs` |

Input/output/user folders point to the legacy `/workspace/inputs`, `/workspace/outputs` and `/workspace/comfyui-user` folders on a new installation. See [MODEL_FOLDERS.md](MODEL_FOLDERS.md) for details. Use Jupyter Upload for small files or its Terminal to download large models directly into the matching folder. Verify the publisher, model format and license. Refresh ComfyUI and choose a compatible workflow after adding files.

Adding a checkpoint or LoRA here does **not** replace the model used by the OfficialTurbo nodes. Other models use standard ComfyUI loader nodes and their own workflows. ComfyUI-Manager is not bundled. Startup does not automatically run third-party installation scripts. Install extra node dependencies deliberately in Jupyter Terminal; packages installed on container storage must be reinstalled on a fresh container.

The engine saves original RGBA PNGs and prompt/seed/dimension/timing JSON to `/workspace/outputs`; standard SaveImage also saves an RGB preview. Download originals to retain alpha. Prompt metadata is embedded in PNG/JSON files, so remove private content before sharing.

## Resources, storage and access

The tested configuration is an A40 (48 GB class GPU), 50 GB system RAM and 70 GB container disk; 64 GB RAM offers more headroom. The template now allocates 100 GB container disk to leave room for additional files. These are tested allocations, not measured minima or guarantees for other GPUs/resolutions. Turbo uses CPU offload.

**Files persist only on durable storage.** Attach your own network volume or volume disk at `/workspace` for persistent models and files; a network volume must be in the GPU's data center. Without that mount, workspace files are temporary and can be wiped when the Pod stops/restarts. Download outputs before stopping. The template does not create a network volume automatically or share the author's storage. Each user pays for their own GPU and any storage they select. Stop your Pod when finished; stopped volume disks/network volumes can still bill.

Jupyter is token protected. ComfyUI and the status page are unauthenticated for anyone with their proxy URLs. For private ComfyUI access set `COMFY_LISTEN=127.0.0.1` and use an SSH tunnel to 8188. Never store passwords or tokens in this public template/repo. Legacy Gradio variables no longer select an interface or protect ComfyUI.

## Readiness, errors and tests

The supervisor checks real HTTP readiness, records service status, redacts the Jupyter token from logs and keeps Jupyter available after a ComfyUI startup/crash failure. Logs are in `/workspace/logs`. Failures are visible on 8080; services do not automatically restart, create another Pod or rent additional compute. Fix the cause and restart the Pod. Missing CUDA, invalid input, download/cache/output problems and OOM return errors through ComfyUI, with tracebacks in its logs. Inference is serialized; OOM and active interruption clear the pipeline for retry. Cancel is checked at denoising step boundaries and may wait during an in-flight GPU operation or initial loading.

**v0.3.1 validation:** build and fresh GPU/Jupyter/browser verification pending. Previous v0.2.6 passed real A40 generation, input-image editing, progress, active cancellation and recovery. Cancellation stopped inside the Turbo node in 1.922 seconds without a saved canceled PNG; the next request reloaded and succeeded. Historical generation/edit timings were around 30–35 seconds, excluding initial loading, with variation between hosts.

Build publication requires `pip check`, 16 engine regression tests plus workspace/auth tests, and real CPU startup checks. Checks cover both interfaces, authenticated Jupyter file/notebook uploads, native checkpoint discovery, both malformed prompt routes, all four workflows returning missing-GPU errors, a killed ComfyUI with Jupyter still accessible, and restart preservation. Disk full, download failure, permission errors and GPU OOM are simulated; physical disk exhaustion and actual GPU OOM are not induced. This is not an exhaustive guarantee for third-party models/nodes or every host.

RunPod base, ComfyUI, Diffusers and official model revisions are pinned, together with key Python packages. Remaining transitive dependencies use upstream constraints; `/app/installed-dependencies.txt` records the built environment. GitHub Actions publishes versioned linux/amd64 images. A public Pod template needs a public image/configuration; the GitHub repo provides source, builds, documentation and issues.

## Reference templates and support

The workspace/Jupyter/readiness design was compared with [RunPod's official ComfyUI source](https://github.com/runpod-workers/comfyui-base) and the [pinned community Qwen template](https://console.runpod.io/hub/template/16mbtha5fk). See [reference notes](docs/reference-pods.md). These references were inspected, not deployed as additional paid tests.

[SUPPORT.md](SUPPORT.md) covers connection failures and file management. Report wrapper/workflow bugs in [GitHub Issues](https://github.com/xerox7777777/runpod-turbo-image-studio/issues). Community support has no guaranteed response time. RunPod does not officially support this community template. Its direct public link works in prior testing, but Community Hub search did not list it; search discoverability remains unconfirmed. A separate person's account deployment is still recommended.

## Model terms

Review the [Qwen Research License](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE): noncommercial research/evaluation unless separately licensed. Wrapper code is MIT; the model weights have separate terms. The container downloads pinned official weights at runtime and does not redistribute them.

## Tested editing example

v0.2.6, A40, 512×512. Prompt: Change the red coffee mug to a blue coffee mug. Keep the table and composition unchanged. Model edits are not guaranteed to preserve every pixel outside the requested change.

| Generated input | Edited output |
| --- | --- |
| ![Red mug](examples/mug-before.png) | ![Blue mug](examples/mug-after.png) |
