# Models and files

JupyterLab opens `/workspace`. Open `ComfyUI` for the application files.

| What you add | Folder |
| --- | --- |
| Native ComfyUI checkpoints | `ComfyUI/models/checkpoints` |
| Diffusion models / UNets | `ComfyUI/models/diffusion_models` |
| Text encoders | `ComfyUI/models/text_encoders` |
| VAEs | `ComfyUI/models/vae` |
| LoRAs for compatible workflows | `ComfyUI/models/loras` |
| Upscale models | `ComfyUI/models/upscale_models` |
| Custom nodes | `ComfyUI/custom_nodes` |
| Saved workflows | `ComfyUI/user/default/workflows` |
| Input images | `ComfyUI/input` |
| Outputs including original RGBA and timings | `ComfyUI/output` |
| Official Turbo model cache | `.cache/huggingface` |
| Service logs | `logs` |

Use Jupyter Upload for small files. For large models, use its Terminal to download
directly into the matching folder, rather than uploading a multi-GB file through
the browser. Verify the publisher, license, filename, and format before downloading.
Refresh the ComfyUI page after adding a model; use a workflow compatible with it.

The modular Turbo workflows include **TurboLoraLoader** and PEFT. Select a compatible Qwen Image 2.1 transformer safetensors adapter from `models/loras`; None is the default. LoRAs for older architectures may fail to load. The model checkpoint remains the pinned official Turbo checkpoint. Other models use their own compatible native workflows. ComfyUI-Manager is installed and enabled. See TURBO_WORKFLOWS.md for settings and compatibility.

Only files on a volume mounted at `/workspace` persist when container storage is
cleared. With no volume, these folders are temporary. Download your outputs before
stopping. User-added Python dependencies on container disk must be reinstalled on
a fresh container; adding a custom-node folder alone does not install requirements.
