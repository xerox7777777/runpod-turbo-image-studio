# Turbo Image Studio for RunPod

Community **Pod** template for the official `Qwen/Qwen-Image-2.1-Turbo` checkpoint. ComfyUI is the default interface. It uses our two custom nodes to call Qwen's official Diffusers pipeline and saved Turbo schedule, with KV caching. Model weights download directly from Qwen; no third-party checkpoint or LoRA is included.

**Validation status:** v0.2.1 completed two real generations and one input-image edit on an A40 (48 GB GPU class, 50 GB allocated system RAM), 2026-10-10. The edit changed a red boat to yellow while retaining the scene. Measured inference: 33.097 seconds square generation, 30.679 seconds landscape generation, 36.142 seconds editing; first model download/load added 21.272 seconds on this host. These are examples, not performance guarantees. v0.2.3 keeps that inference path and adds stricter input/HTTP validation, with real HTTP startup and simulated failure/recovery checks; its final image has not had a separate GPU launch.

## Start and use

1. Open [the public Pod template](https://console.runpod.io/hub/template/92ov0cv1fr).
2. Choose an NVIDIA GPU; the tested allocation was A40 (48 GB class), 50 GB system RAM and 70 GB disk. Use at least that RAM/storage for this configuration; 64 GB RAM leaves more headroom. This is not a measured minimum and larger images may need more resources. The engine uses model CPU offload.
3. For a durable model cache, attach your own network volume at `/workspace`. Container disk is ephemeral and can be wiped on restart. This template does not give other users access to the author's volume or outputs.
4. Start the Pod and open ComfyUI on **8188**. Queuing the first request downloads and loads roughly 32 GB of official checkpoint files. No download happens just by opening the UI.
5. Open a bundled workflow under ComfyUI's saved workflows, or drag in a JSON from [workflows](workflows). Upload/select an image in LoadImage for editing.
6. Download results and stop your Pod when finished. Every user rents their own GPU/storage.

## Bundled workflows

| File | Purpose |
| --- | --- |
| [text-to-image.json](workflows/text-to-image.json) | Square 1024×1024 generation |
| [image-edit.json](workflows/image-edit.json) | Upload an image and give edit instructions |
| [portrait.json](workflows/portrait.json) | 768×1024 portrait generation |
| [landscape.json](workflows/landscape.json) | 1024×768 landscape generation |

API-format variants are in [workflows/api](workflows/api). These are workflows for this image's `OfficialTurboGenerate` and `OfficialTurboEdit` nodes, not native third-party checkpoint workflows. Connect outputs to standard ComfyUI image nodes as needed. The shared engine saves the original RGBA PNG and a JSON record with prompt, seed, dimensions, load time and inference time to `/workspace/outputs`. SaveImage creates an additional RGB preview/output; use the original `turbo_*.png` to preserve alpha. The alpha mask is a separate node output. Prompts are saved in PNG/JSON metadata; remove them before public sharing if private.

This release supports generation and single-image editing. It does not claim masked inpainting, multi-image editing, upscaling or LoRA support. Sampling uses the checkpoint's saved schedule rather than overriding it with a guessed step count.

## Gradio: optional simple interface

Gradio is a Python web UI with two tabs: Generate and Edit. It was initially selected to expose the official Diffusers examples with fewer controls. It is not required by Qwen or RunPod. Set `UI_MODE=gradio` and open **7860** to use it instead of ComfyUI. Set both `UI_USERNAME` and `UI_PASSWORD` to require a login. Never store a real password in this public template/repo.

ComfyUI is reachable by anyone with the proxy URL in the default configuration. It does not use Gradio's password settings. For private access set `COMFY_LISTEN=127.0.0.1` and connect via SSH tunnel, e.g. `ssh -L 8188:127.0.0.1:8188 <your RunPod SSH destination>`, then open http://localhost:8188. Obtain the exact SSH destination from your Pod's Connect tab.

## Dependencies, errors and builds

RunPod PyTorch/CUDA base, ComfyUI source, Diffusers source and the official model revision are version pinned in Dockerfile/requirements. Transformers, Accelerate, Gradio and Pillow are pinned. ComfyUI's remaining transitive dependencies use its upstream constraints; the built image records the resolved set at `/app/installed-dependencies.txt`. This is not a complete transitive lockfile. Custom nodes are included in the image; no node-manager install step is needed.

The build runs `pip check`, fourteen mocked unit tests and real HTTP startup checks for Gradio and CPU-mode ComfyUI, including queuing all four API workflows and checking their missing-GPU errors. Seven malformed request envelopes must return HTTP 400 on both /prompt and /api/prompt. Simulated tests cover concurrent calls, unique outputs, nonfinite/nonnumeric inputs, disk full, permissions, download failure/retry and GPU OOM/retry. These checks do not download weights or test GPU inference. A failing check stops publication. Actual GPU tests also checked invalid dimensions/seeds, missing edit files, blank prompts and service health afterward. The shared engine validates inputs before loading, serializes inference, reports missing GPU/download/disk errors, clears its pipeline after OOM, and retains tracebacks in Pod logs. A failed request is returned through ComfyUI/Gradio; there is no silent substitution or automatic paid restart.

GitHub Actions builds/pushes `linux/amd64` images on a `v*` tag. The template uses a version tag. A public Pod template only requires a public image and public template configuration; this public GitHub repo supplies source, builds and documentation.

## Support

See [SUPPORT.md](SUPPORT.md) for fixes and reporting instructions. Report wrapper/workflow bugs in [GitHub Issues](https://github.com/xerox7777777/runpod-turbo-image-studio/issues). Community support has no guaranteed response time. RunPod does not officially support this community template.

## Model terms

The model's [Qwen Research License Agreement](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE) limits use to noncommercial research/evaluation unless you obtain separate commercial permission. Review its terms before use. The code's MIT license does not apply to model weights. The container downloads weights at runtime and does not redistribute them.

[Official model and pipeline examples](https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo) · [Source](https://github.com/xerox7777777/runpod-turbo-image-studio) · [Support](https://github.com/xerox7777777/runpod-turbo-image-studio/issues)
