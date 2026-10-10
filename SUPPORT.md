# Community support

Report reproducible template, node, startup or workflow bugs at:
https://github.com/xerox7777777/runpod-turbo-image-studio/issues

Include image version, GPU/VRAM, resolution, whether Generate or Edit failed,
workflow JSON, and the relevant traceback from Pod logs. Remove API keys,
proxy URLs, passwords, private prompts and private images. Share images only
when you are comfortable making them public.

This is a community project. No response time or ongoing support service is
promised. RunPod handles platform/billing issues; Qwen handles upstream model
issues. GitHub Issues is for this wrapper and its packaging.

## Troubleshooting

- **502 or service missing:** inspect Pod logs; open ComfyUI on port 8188 in
  default mode, or Gradio on 7860 with UI_MODE=gradio. The other port has no server.
- **No CUDA:** choose an NVIDIA GPU; CPU startup checks cannot generate images.
- **Out of memory:** start at 1024×1024, run one request at a time, close other
  GPU workloads or use a larger card. The shared engine uses model CPU offload.
  On OOM it clears its pipeline so the next request reloads it.
- **First request slow:** the checkpoint downloads and loads lazily; inspect
  logs. Later requests reuse the loaded model. Network/cache failures report
  an actionable error; retry resumes Hugging Face's cached download.
- **Disk full:** increase storage or use a network volume mounted at /workspace.
  Download output files before stopping; container-disk data can be lost.
- **Missing input:** upload and select an image in LoadImage before queueing Edit.
- **Missing nodes:** use this image and its bundled workflows; arbitrary third
  party workflows/custom nodes are not installed or supported.
- **Blank prompt/bad size:** dimensions must be 512–2752, divisible by 16;
  enter a nonempty prompt. Batch image editing accepts one image per request.
- **ComfyUI authentication:** COMFY_LISTEN=127.0.0.1 and an SSH tunnel protect
  access. UI_USERNAME/PASSWORD apply only to Gradio; startup rejects them in
  ComfyUI mode to prevent a false expectation of password protection.
