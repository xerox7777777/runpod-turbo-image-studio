# Turbo workflow controls

Open Workflows and choose **Generation** or **Image-Edit**. All nodes and ComfyUI-Manager 4.2.2 are included. Only Generation and Image-Edit are bundled; use the aspect-ratio control for portrait or landscape.

## Follow the connected graph

1. **Official Turbo Model / Precision** selects the pinned Qwen Image 2.1 Turbo checkpoint, BF16 and memory mode. This node configures a pipeline handle; weights load on the first sampler execution.
2. **Qwen 2.1 Transformer LoRA** defaults to None. Upload a compatible transformer LoRA safetensors file to `/workspace/ComfyUI/models/loras`, refresh ComfyUI, select it and set strength. The loader and PEFT dependency are included. Old Qwen Image/Edit adapters are not automatically compatible with the different 2.1 architecture. Loading errors are reported; no weights are downloaded for you. Each request resets the previous adapter, so selecting None removes it.
3. **Prompt** contains positive and negative text. With the recommended CFG=1, negative text does not guide sampling. CFG above 1 requires a negative prompt and is experimental for Turbo.
4. **Sampling Settings** exposes the schedule, steps, CFG and KV cache. `official_8_steps`, steps=8, CFG=1 and KV=true preserve Qwen's recommendation. Setting another step count while retaining official schedule produces an explanatory error, never a silently ignored value. `experimental_linear` uses the chosen 1–50 steps with explicit call-time sigmas. `experimental_custom` requires a strictly descending JSON sigma list with exactly steps values in (0,1], excluding terminal zero. The scheduler remains FlowMatchEulerDiscreteScheduler and applies its configured shift. Other schedules/CFG values have not been evaluated by Qwen.
5. **Sampler** sets width, height and seed. An optional IMAGE connection enables single-image editing. The edit graph includes a LoadImage node and a bundled example image. Replace it by uploading/selecting your image. IMAGE output connects to ordinary image processing, preview and save nodes.
6. **Saved Turbo Image** displays the one original RGBA file from `/workspace/outputs`, where matching JSON metadata is saved. Bundled workflows do not create an additional preview file or run inference twice.
7. **Actual Turbo Run Settings** displays model revision, actual steps, scheduler, saved/requested sigma inputs, CFG, prompts, KV state, precision, offload, adapter/strength, seed and timing after execution. This is the result of the run, not just a template description.

## Pipeline handles and native nodes

The graph exposes real configuration connections for the official Diffusers pipeline. `TURBO_MODEL`, `TURBO_CONDITIONING` and `TURBO_SAMPLING` are specific types, not native ComfyUI MODEL/CLIP/LATENT objects. Use the included Turbo LoRA loader and sampler with those handles. Native KSampler/LoRA Loader cannot replace them. Standard native model loaders remain installed for separate compatible workflows. This avoids claiming unsupported native checkpoint compatibility.

The v0.4.1 loader integration was verified with a locally created zero-effect adapter, including strength and reset. Compatibility and visual quality of any real adapter still require testing. If canvas text is hidden at low zoom, zoom above 60%.

## Manager and dependencies

Manager is enabled through ComfyUI's supported `--enable-manager` integration. Open its extension/Manager control to browse installed nodes or the registry; standard security defaults are retained. All bundled workflows run without installing another node. Additional third-party node packages can change dependencies; the tested image remains the recovery baseline. Save user files and avoid updating the core blindly. Durable files require a volume mounted at `/workspace`.

## References

[Official Turbo sampling](https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo#sampling), [official Diffusers pipeline](https://github.com/huggingface/diffusers/blob/85c9fa4caee33d1c5b473395784471d2d7957c1b/src/diffusers/pipelines/qwenimage21/pipeline_qwenimage21.py), [ComfyUI Manager setup](https://github.com/Comfy-Org/ComfyUI#comfyui-manager).

## v0.4.2 memory modes and outputs

Auto selects gpu_resident for a GPU with at least 44 GiB total VRAM and initially free VRAM, outputs up to 1 MP, CFG 1. It retains a loaded resident pipeline on subsequent runs. Other auto workloads use model_cpu_offload. Select gpu_resident explicitly only with enough VRAM; OOM clears the pipeline for retry. Switching modes reloads the pipeline. BF16 and official Qwen weights are preserved, without quantization or third-party adapters. A40 tests measured 6.7–7.2 second generation and 8.7–8.9 second single-image edits at 1024×1024. First loading/download is extra. Bundled workflows use Saved Turbo Image to display the one original RGBA file directly. Unmodified legacy bundled workflows are archived under backups; user-edited workflows are preserved; load a current graph or explicitly change its memory mode.

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
