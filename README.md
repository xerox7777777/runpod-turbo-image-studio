# Turbo Image Studio for RunPod

A community RunPod **Pod** template for text-to-image generation and image editing with the official `Qwen/Qwen-Image-2.1-Turbo` checkpoint. The app uses the Diffusers pipeline shown in the official model card, the checkpoint's saved Turbo sampling schedule, and prefix KV caching.

## Create a Pod

1. Open the [public RunPod template](https://console.runpod.io/hub) and choose **Turbo Image Studio (Qwen Image 2.1 Turbo)**.
2. Choose a GPU Pod with at least 48 GB of VRAM for the tested configuration.
3. Keep the 70 GB container disk or increase it if you plan to keep many outputs.
4. Start the Pod and open the HTTP service on port `7860`.
5. Use **Generate** for text-to-image or **Edit** to upload an image and describe the transformation.

The first generation downloads the official checkpoint from Hugging Face (about 32 GB) into `/workspace/.cache/huggingface`; allow time for the first request. Generated PNG files are also saved under `/workspace/outputs` and are downloadable in the UI. A Pod's container disk is not a long-term backup; attach a RunPod network volume at `/workspace` when creating a Pod if you want model cache and outputs to persist independently of the container disk.

## Optional access password

The Pod's Gradio page is reachable by anyone who has its RunPod proxy URL. To require a login, set **both** `UI_USERNAME` and `UI_PASSWORD` in the Pod environment before startup. Do not publish or reuse a real password in a public template or repository.

## Model license and attribution

The application downloads the model from the official Qwen Hugging Face repository at runtime; this repository and its container image do **not** redistribute the model weights. The model is under the [Qwen Research License Agreement](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE). The agreement limits use to non-commercial research or evaluation unless you obtain a separate commercial license. Review the agreement before use. The application's MIT license does not apply to the model.

Qwen's model card identifies Turbo as an 8-step accelerated checkpoint for text-to-image and image editing. It recommends loading the checkpoint's saved sampling schedule and supports `use_kv_cache=True`.

## Build and publish

The GitHub Actions workflow builds for `linux/amd64` and publishes a versioned image to GHCR when a `v*` tag is pushed. The RunPod template uses a pinned image tag; update it only after publishing and checking a new release.

## Source and official model

- Application source: [GitHub repository](https://github.com/xerox7777777/runpod-turbo-image-studio)
- Official model card: [Qwen/Qwen-Image-2.1-Turbo](https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo)
- Model terms: [Qwen Research License Agreement](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE)

Application code is MIT licensed; model materials are licensed separately as described above.
