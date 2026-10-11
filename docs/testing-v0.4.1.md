# v0.4.1 verification, 11 October 2026

Image: ghcr.io/xerox7777777/runpod-turbo-image-studio:v0.4.1
Source image commit: 92c0980. Build 38113662414 passed.

## Completed checks

* 29 regression tests and real CPU service/startup checks passed in CI. These include legacy and modular workflows, missing GPU errors, malformed prompts, first start/restart preservation, and ComfyUI crash reporting while Jupyter remains available.
* 19 live Jupyter/API checks passed: authentication, file upload, notebook operations, terminal, model folders, and synthetic model discovery. These are file/discovery checks, not inference on arbitrary checkpoints.
* 22 modular GPU assertions passed across five successful runs and two intentional invalid settings: official eight-step generation, four-step explicit sigmas with KV off, input-image editing, three custom sigmas, CFG 2 with negative prompt, incorrect official step count, and missing negative prompt at CFG 2.
* 9 adapter assertions passed: local zero-effect rank-one transformer adapter discovered, loaded through Diffusers/PEFT, set to strength 0.5, generated successfully, then unloaded on the next None run. No third-party LoRA weights were downloaded. Real adapter compatibility and visual quality remain unverified.
* Browser tests: Manager/Extensions registry catalog opened; all four new workflows appeared; generation and input-image editing ran from the Run button and displayed actual JSON settings in the graph. No additional node downloads were needed.

A40, 50 GB system RAM, 100 GB ephemeral container disk, no persistent/network volume. Browser generation at 1024x1024 took 29.324 seconds of inference; editing the bundled 512x512 input into a 1024x1024 output took 32.342 seconds. Both were warm runs, eight actual steps, official saved sigma schedule, CFG 1, KV cache on, BF16 and CPU offload. These timings exclude startup/download time and are not a comparison against regular Qwen.

## Limits and bugs found

The v0.4.0 Docker ignore pattern accidentally excluded the bundled edit input. v0.4.1 explicitly includes that image; CPU checks verify both it and the Run Details JavaScript ship in the image. The fresh GPU Pod confirmed LoadImage could read it and editing succeeded.

ComfyUI hides canvas labels at low zoom as a rendering optimization; zoom above 60% to read controls. The graph uses typed Diffusers pipeline handles, not native KSampler MODEL/CLIP/LATENT. It exposes schedules, sigmas, steps, guidance and KV cache, but does not expose a choice of native ComfyUI samplers. IMAGE outputs can use standard image nodes.

Physical GPU OOM and full disk were not induced. Failure cases in regression tests are simulated. No persistent-volume redeployment or separate person's account deployment was performed. Public image manifests/layers were accessible anonymously and the public Pod template/direct configure link was verified, but Community Hub search discoverability remains unconfirmed.

Some browser/agent signatures get Cloudflare HTTP 403 before reaching ComfyUI. Browser navigation here succeeded. The user's exact Chrome condition has not been reproduced or resolved; fresh direct URL/browser access worked for them. Jupyter tokens do not govern ComfyUI proxy access.

## Cleanup and publication

Test Pod ftnfe7woghpk5j was stopped and a fresh read returned EXITED. Original PNGs, metadata, reports and dependency versions were saved locally first. The temporary registered SSH key was removed while preserving other keys; temporary Pod token/key environment variables were removed. Existing user-created Pods were not stopped or modified.

Public template 92ov0cv1fr now uses v0.4.1 with 100 GB disk, ports 8080/8188/8888 HTTP and 22 TCP, Start Jupyter/SSH, CUDA constraints and no shared credentials. Existing Pods do not receive a template update automatically. Use the new image for these modular workflows.

Raw reports and images are included in the local verification bundle. Community support is via the public GitHub issue tracker; no guaranteed response time.
