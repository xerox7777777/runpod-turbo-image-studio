# v0.4.2 performance verification

11 October 2026. Existing user-authorized A40 Pod gc9gtw07pzf9di, 48 GiB class VRAM, 50 GB RAM. No additional Pod or paid storage was created. Official Qwen Turbo revision d65dbc9a7e8f6b5479e33dee6030eaab2a906509, BF16, eight saved-schedule steps, CFG 1, KV cache enabled, output 1024x1024.

## Measurements

| Isolated resident run | Inference seconds |
| --- | --- |
| Generation first | 7.203 |
| Generation warm | 6.714 |
| Generation with conditioning cache fill | 6.723 |
| Generation with conditioning cache hit | 6.705 |
| Image edit first | 8.794 |
| Image edit warm | 8.705 |
| Updated engine auto-mode generation | 7.183 |
| Updated engine auto-mode editing | 8.855 |

Direct GPU loading took about 16–18 seconds extra with already cached weights. Downloads are excluded. Generation profiling: warm conditioning encoding ~0.037s, transformer ~6.16s, VAE decode ~0.45s. Conditioning cache offers little extra speed when components stay resident and was not added to the release.

v0.4.1 CPU-offloaded browser generation/editing on A40 measured 29.324/32.342s. The currently running Pod's old edit history measured 33.329/36.362s. These are representative workloads, not a benchmark against the original full model on identical inputs; no original-model speed claim is made. Isolated probe output images and updated engine images were saved locally.

## Corrections

Auto selects direct device_map=cuda loading at >=44 GiB total/free initial VRAM, <=1 MP, CFG 1; otherwise model CPU offload. An already resident pipeline stays resident for subsequent eligible requests. Explicit modes are available. Mode changes reload; OOM resets for retry. Larger/CFG>1 workloads were not benchmarked resident. No promise is made for other hardware or a strict ten-second ceiling.

Turbo-Fast graphs include one Saved Turbo Image output node that shows the original RGBA file from the engine. It does not re-run inference, encode another preview, or save a second RGB result. Existing saved user graphs are retained. Old graphs can choose the new memory mode manually.

## Exact reference

The user's reference is g8ow1s1s0a, image ls250824/run-comfyui-image2:09102026, not the other nomadoor template reviewed previously. Its live public configuration selects BF16 above 40 GiB VRAM and includes both standard and Turbo workflows. It also downloads modified third-party text encoders and prompt enhancers, which were not copied/downloaded. Direct workflow JSON links under provisioning.rozenlaan.site returned HTTP 403 and were blocked in browser navigation, so their current node-level implementation was not verified. The public template and author's documentation were inspected. The other template's workflow JSONs were inspected earlier but are a different reference.

## Tests and limits

33 regression tests and real CPU service checks passed in container CI run 38169133823. Live Fast API generation measured 7.318s inference plus 11.738s initial loading; input-image editing measured 8.953s inference. Browser Run produced one blue mug from the bundled red mug input in 8.864s, with no loading. These tests used the patched actual ComfyUI service. The documentation follow-up image is v0.4.2.1; its engine and nodes are unchanged from the measured v0.4.2 build. The image/node output path uses only files within the configured ComfyUI output root. Jupyter and the user's original ComfyUI service remained available during isolated tests. Actual GPU OOM/disk-full were not induced. GPU residency consumes more VRAM; the user must avoid competing workloads. Per-mode timing is inference time, with loading separately recorded.
