# Reference Pod inspection

Inspected on 2026-10-10. No reference Pod was rented for this comparison.

| Reference | Inspected evidence | Applied here |
| --- | --- | --- |
| Official ComfyUI CUDA 12.8, cw3nka7d08 | Live template catalog: ports 8188/8080/8888/22, Jupyter enabled, workspace storage. Source runpod-workers/comfyui-base at 33dfcd67fd5dfa666bc339aae4b92cf25d292a8b: README, startup and tests | Editable ComfyUI in workspace, Jupyter root/files, HTTP readiness and crash/restart testing |
| RunPod PyTorch 2.8.0, runpod-torch-v280 | Live catalog and runpod/containers source at af9214bb481a3fa0f64391fdb9f331bd662f988a: Jupyter gate/token and startup | Preserve platform SSH/nginx startup; explicit per-Pod Jupyter authentication, monitored separately |
| Pinned Qwen community template, 16mbtha5fk | Actual Hub page: startup status, workflows/sample inputs, Manager, help and idle termination behavior | Visible startup status and onboarding. Its broader workflows, Manager and automatic termination are not copied or claimed here |

Sources: [official ComfyUI source](https://github.com/runpod-workers/comfyui-base), [RunPod containers](https://github.com/runpod/containers), [pinned community template](https://console.runpod.io/hub/template/16mbtha5fk).

Differences are deliberate: this image uses the official Turbo Diffusers checkpoint and four matching workflows. It supplies Jupyter file access rather than a separate FileBrowser login, keeps authentication enabled, and does not automatically terminate a user's Pod or execute third-party installation scripts. It reports failures while leaving Jupyter available to repair them. Users can add their own models/custom nodes through Jupyter with compatible standard ComfyUI workflows.
