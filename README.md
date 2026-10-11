# Turbo Image Studio for RunPod

[Deploy the public Pod template](https://console.runpod.io/hub/template/92ov0cv1fr) · [Workflows](workflows) · [Support](SUPPORT.md)

ComfyUI generation and single-image editing with the official **Qwen/Qwen-Image-2.1-Turbo** checkpoint. Official weights download directly from Qwen on the first queued request. No third-party checkpoint or LoRA is included. Gradio is not included.

## v0.4.2 performance fix

Zoom the canvas above 60% if node labels are hidden by ComfyUI’s rendering optimization. Open **Generation** or **Image-Edit**. The connected graph exposes model/precision/memory mode, LoRA selection/strength, prompts, schedule/steps/CFG/KV caching, resolution/seed, preview/save and actual run details. Manager and all nodes are preinstalled; a sample edit image is included. See [every control explained](TURBO_WORKFLOWS.md). Official default is eight steps, CFG 1 and KV caching. Auto memory mode keeps the full official BF16 pipeline on a GPU with at least 44 GiB total/free VRAM for outputs up to 1 MP at CFG 1. Other workloads use CPU offloading; gpu_resident can be selected explicitly but needs enough memory. Verified on A40: generation 6.7–7.2 seconds and single-image editing 8.7–8.9 seconds at 1024×1024, excluding first model loading/download. The bundled graphs show/save one original RGBA result, without duplicate SaveImage/Preview outputs. Experimental schedules require explicit sigmas; changing the step count alone never silently does nothing.

v0.4.1 passed 29 regression tests, CPU service checks, 19 Jupyter checks, and A40 tests for official generation, input-image editing, custom schedules, CFG, invalid settings, and real adapter loading/reset. Browser generation displayed actual settings. The LoRA integration test used a locally created zero-effect adapter; visual quality and compatibility with your chosen adapter are not yet verified. See [previous validation report](docs/testing-v0.4.1.md) and [performance verification](docs/testing-v0.4.2.md).

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
| [Generation](workflows/Generation.json) | 1024×1024 generation |
| [Image-Edit](workflows/Image-Edit.json) | Upload/select an image in LoadImage, then describe changes |

The first queued request downloads roughly 32 GB of official checkpoint files. Opening either interface does not download weights. The bundled OfficialTurbo nodes call Qwen's official Diffusers pipeline with its saved Turbo schedule and KV caching. They support generation and single-image editing; masked inpainting and multi-image editing are not included. The modular workflows include an optional compatible transformer LoRA loader. Identical inputs/seed may reuse ComfyUI's cache; change the seed for a fresh result.

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

Adding a checkpoint does **not** replace the official Turbo pipeline. Compatible adapters are selected using TurboLoraLoader in the modular graphs; copying a file alone does not enable it. Other models use standard ComfyUI loader nodes and their own workflows. ComfyUI-Manager 4.2.2 is bundled and enabled. Startup does not automatically run third-party installation scripts. Install extra node dependencies deliberately in Jupyter Terminal; packages installed on container storage must be reinstalled on a fresh container.

The engine saves original RGBA PNGs and prompt/seed/dimension/timing JSON to `/workspace/outputs`; the workflow displays that saved original directly. Download originals to retain alpha. Prompt metadata is embedded in PNG/JSON files, so remove private content before sharing.

## Resources, storage and access

The tested configuration is an A40 (48 GB class GPU), 50 GB system RAM and 100 GB container disk; 64 GB RAM offers more headroom. The template now allocates 100 GB container disk to leave room for additional files. These are tested allocations, not measured minima or guarantees for other GPUs/resolutions. Turbo selects GPU residency for the verified A40 1 MP/CFG 1 envelope, with CPU offload for other auto-mode workloads.

**Files persist only on durable storage.** Attach your own network volume or volume disk at `/workspace` for persistent models and files; a network volume must be in the GPU's data center. Without that mount, workspace files are temporary and can be wiped when the Pod stops/restarts. Download outputs before stopping. The template does not create a network volume automatically or share the author's storage. Each user pays for their own GPU and any storage they select. Stop your Pod when finished; stopped volume disks/network volumes can still bill.

Jupyter is token protected. ComfyUI and the status page are unauthenticated for anyone with their proxy URLs. For private ComfyUI access set `COMFY_LISTEN=127.0.0.1` and use an SSH tunnel to 8188. Never store passwords or tokens in this public template/repo. Legacy Gradio variables no longer select an interface or protect ComfyUI.

## Readiness, errors and tests

The supervisor checks real HTTP readiness, records service status, redacts the Jupyter token from logs and keeps Jupyter available after a ComfyUI startup/crash failure. Logs are in `/workspace/logs`. Failures are visible on 8080; services do not automatically restart, create another Pod or rent additional compute. Fix the cause and restart the Pod. Missing CUDA, invalid input, download/cache/output problems and OOM return errors through ComfyUI, with tracebacks in its logs. Inference is serialized; OOM and active interruption clear the pipeline for retry. Cancel is checked at denoising step boundaries and may wait during an in-flight GPU operation or initial loading.

**Previous v0.3.3 validation:** v0.3.3 passed 24 regression tests, real CPU startup checks, 19 Jupyter API checks and 13 A40 GPU checks. Browser login, notebook execution/save, model-folder browsing, upload, terminal and image-edit graph loading passed. Generation, input-image editing, active cancellation and recovery ran on GPU. Physical disk exhaustion and GPU OOM were not induced. A deliberately terminated ComfyUI process was reported as failed while Jupyter remained usable. All test Pods were stopped. See [test details](docs/testing-v0.3.3.md).

Build publication requires `pip check`, 29 regression tests, and real CPU startup checks. Checks cover both interfaces, authenticated Jupyter file/notebook uploads, native checkpoint discovery, both malformed prompt routes, all legacy and modular workflows returning missing-GPU errors, a killed ComfyUI with Jupyter still accessible, and restart preservation. Disk full, download failure, permission errors and GPU OOM are simulated; physical disk exhaustion and actual GPU OOM are not induced. This is not an exhaustive guarantee for third-party models/nodes or every host.

RunPod base, ComfyUI, Diffusers and official model revisions are pinned, together with key Python packages. Remaining transitive dependencies use upstream constraints; `/app/installed-dependencies.txt` records the built environment. GitHub Actions publishes versioned linux/amd64 images. A public Pod template needs a public image/configuration; the GitHub repo provides source, builds, documentation and issues.

## Reference templates and support

The workspace/Jupyter/readiness design was compared with [RunPod's official ComfyUI source](https://github.com/runpod-workers/comfyui-base) and the [pinned community Qwen template](https://console.runpod.io/hub/template/16mbtha5fk). See [reference notes](docs/reference-pods.md). These references were inspected, not deployed as additional paid tests.

[SUPPORT.md](SUPPORT.md) covers connection failures and file management. Report wrapper/workflow bugs in [GitHub Issues](https://github.com/xerox7777777/runpod-turbo-image-studio/issues). Community support has no guaranteed response time. RunPod does not officially support this community template. Its direct public link works in prior testing, but Community Hub search did not list it; search discoverability remains unconfirmed. A separate person's account deployment is still recommended.

## Model terms

Review the [Qwen Research License](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE): noncommercial research/evaluation unless separately licensed. Wrapper code is MIT; the model weights have separate terms. The container downloads pinned official weights at runtime and does not redistribute them.

## Tested editing example

v0.3.3, A40, 512×512. Prompt: Change the red coffee mug to a blue coffee mug. Keep the table and composition unchanged. Model edits are not guaranteed to preserve every pixel outside the requested change.

| Generated input | Edited output |
| --- | --- |
| ![Red mug](examples/mug-before.png) | ![Blue mug](examples/mug-after.png) |

## Canvas size controls

Generation and Image-Edit each include the installed **Aspect Ratio / Auto Resolution / Multiplier** node, connected to the sampler width/height. There are no separate fast, portrait or landscape graphs.

* **aspect_ratio** chooses square, portrait, landscape, widescreen or ultrawide presets.
* **match_input** calculates canvas dimensions from the connected input image aspect ratio; Image-Edit uses this by default. It does not crop the uploaded input.
* **manual** uses the explicit width and height instead of megapixel sizing.
* **target_megapixels** sets the approximate pixel budget; the default 1.048576 MP gives a 1024 square.
* **multiplier** scales both dimensions; 2x produces approximately four times the pixels. It changes generation resolution, not a separate post-generation upscaler.
* Dimensions round to multiples of 16. The calculated size display runs before inference; Actual Run Settings records the executed dimensions afterward. Values outside 512–2752 per side produce a clear error rather than silently distorting the ratio.

Larger canvases can move auto memory mode to CPU offload and increase time and VRAM demand. The previous A40 timings apply to 1024x1024, not arbitrary multipliers. No extra model downloads are required for these controls. The official Turbo checkpoint and eight-step defaults are unchanged. Native IMAGE/INT outputs remain compatible with ordinary image processing and size nodes.

On upgrade, known unmodified legacy bundled graphs are moved to `/workspace/backups/retired-workflows`. User-edited graphs are retained; any such graph may still need its memory setting changed manually.
