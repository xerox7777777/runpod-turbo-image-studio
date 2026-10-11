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

The bundled OfficialTurbo nodes use the pinned official Diffusers checkpoint in the
Hugging Face cache. Putting a different checkpoint or LoRA in a model folder does
not change those nodes. Additional models use ComfyUI's standard loader nodes and
their own compatible workflows. This release does not install ComfyUI-Manager or
automatically execute third-party installation scripts.

Only files on a volume mounted at `/workspace` persist when container storage is
cleared. With no volume, these folders are temporary. Download your outputs before
stopping. User-added Python dependencies on container disk must be reinstalled on
a fresh container; adding a custom-node folder alone does not install requirements.
