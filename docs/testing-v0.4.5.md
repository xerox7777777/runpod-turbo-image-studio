# Configurable workflows and cleanup, v0.4.5

11 October 2026. Only Generation and Image-Edit are bundled, with matching API graphs. Fixed portrait/landscape and legacy/Fast duplicates are removed from the image. The upgrade migrator archives only exact known unmodified legacy graph content under backups/retired-workflows; user-edited graphs are preserved. Local removed source files went to Windows Recycle Bin.

Each workflow includes connected aspect-ratio/input/manual size calculation, a pixel budget, dimension multiplier and a preflight size display. Alignment rounds down to multiples of 16 so default aspect presets do not cross the GPU residency pixel threshold solely from rounding. Unsupported sizes produce an explanatory error. Multiplier affects inference dimensions, not an additional upscaling pass. Model, LoRA, prompt, schedule, seed, output and actual run detail controls remain present.

## Live existing A40 Pod

| Case | Calculated/executed size | Inference |
| --- | --- | --- |
| 3:2 preset generation | 1248x832 | 7.130 s |
| Non-square input image edit, match_input | 1248x832 | 8.877 s |
| Manual 768 square, multiplier 1.25 | 960x960 | 5.999 s |
| Browser image edit, square input | 1024x1024 | 8.795 s |

All used the official BF16 Turbo checkpoint, official eight steps, CFG 1, KV cache on, GPU resident. Each displayed one saved original output. Actual image dimensions matched the calculated size. Oversized 4 MP / 2x requests and match_input without an image returned descriptive errors. Original PNG/JSON, browser screenshots and API history were saved locally. First model loading is excluded from inference timing.

The actual running service was patched with backups. Its workflow directory and the refreshed browser catalog both contained only Generation and Image-Edit. The initial already-open browser retained an old node catalog; a fresh browser tab loaded the new node and completed the edit. No fresh paid Pod or storage was created. Only the agent-created Jupyter kernel was closed afterward; the user's Pod remains running.

## Build and publication

Container CI run 38170876441 passed 35 regression tests, CPU service checks, both API workflow validation checks, and restart preservation checks. Resolution regression cases cover all nine ratios, automatic input ratio, manual multiplier, larger sizes, NaN/infinite values, missing/multiple inputs and size limits. Migration regression verifies unchanged legacy archival and retention of user changes.

Public template 92ov0cv1fr reads back as v0.4.5, public=true, serverless=false. Its container manifest was fetched anonymously. The new image itself was not deployed on a second paid GPU; the same node/source revision was exercised on the existing A40.

## Reference and limits

The exact g8ow1s1s0a template's author documents Resolution Master and Scale Image to Total Pixels Advanced in https://comfyui.rozenlaan.site/ComfyUI_image2_custom_nodes/. The author's workflow screenshot was inspected. Direct graph downloads remained inaccessible with 403, and the screenshot does not establish exact node settings. The bundled resolution node implements the requested controls without downloading third-party models. No claim is made that this reproduces every feature of that reference Pod.

Preservation of aspect ratio is approximate after 16-pixel alignment. Extreme ratios/pixel budgets can violate minimum/maximum side limits and are rejected. A 2x dimension multiplier uses roughly four times the pixels and can require CPU offload or more VRAM. No speed guarantee applies to larger canvases. Post-generation model upscaling, masked inpainting and multi-input editing remain outside these graphs. Real third-party LoRA visual compatibility and physical disk-full/GPU OOM were not tested in this change.
