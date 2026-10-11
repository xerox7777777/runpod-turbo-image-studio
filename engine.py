"""Official-checkpoint inference for the bundled ComfyUI nodes."""
import gc
import json
import logging
import math
import os
import secrets
import threading
import time
import uuid
from pathlib import Path

import torch
from diffusers import QwenImage21Pipeline
from PIL import Image, PngImagePlugin

MODEL_ID = "Qwen/Qwen-Image-2.1-Turbo"
MODEL_REVISION = "d65dbc9a7e8f6b5479e33dee6030eaab2a906509"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/workspace/outputs"))
_pipeline = None
_lock = threading.Lock()
log = logging.getLogger(__name__)


def validate(prompt, width, height, seed):
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Enter a prompt first.")
    for label, value in (("Width", width), ("Height", height)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and not math.isfinite(value)) or int(value) != value or value < 512 or value > 2752 or value % 16:
            raise ValueError(f"{label} must be 512–2752 and divisible by 16.")
    if isinstance(seed, bool) or not isinstance(seed, (int, float)) or (isinstance(seed, float) and not math.isfinite(seed)) or int(seed) != seed or seed < -1 or seed > 2147483647:
        raise ValueError("Seed must be -1 (random) or 0–2147483647.")


def sampling_options(schedule='official_8_steps', steps=8, custom_sigmas='', cfg=1.0, negative_prompt='', use_kv_cache=True):
    if schedule not in ('official_8_steps', 'experimental_linear', 'experimental_custom'):
        raise ValueError('Unknown Turbo sampling schedule.')
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 50:
        raise ValueError('Steps must be an integer from 1 to 50.')
    if isinstance(cfg, bool) or not isinstance(cfg, (int,float)) or not math.isfinite(cfg) or not 1 <= cfg <= 10:
        raise ValueError('CFG must be finite and from 1 to 10.')
    if not isinstance(negative_prompt, str) or not isinstance(use_kv_cache, bool):
        raise ValueError('Negative prompt must be text and KV caching must be a boolean.')
    if cfg > 1 and not negative_prompt.strip():
        raise ValueError('CFG above 1 needs a negative prompt. Official Turbo uses CFG 1.')
    options = dict(true_cfg_scale=float(cfg), use_kv_cache=use_kv_cache)
    if negative_prompt.strip(): options['negative_prompt'] = negative_prompt.strip()
    if schedule == 'official_8_steps':
        if steps != 8:
            raise ValueError('Official Turbo schedule is 8 steps. Choose an experimental schedule to change steps.')
    elif schedule == 'experimental_linear':
        options['sigmas'] = [1-i/steps for i in range(steps)]
    else:
        try: sigmas = json.loads(custom_sigmas)
        except (TypeError,ValueError) as exc: raise ValueError('Custom sigmas must be a JSON list, excluding terminal zero.') from exc
        if not isinstance(sigmas,list) or len(sigmas)!=steps or any(isinstance(s,bool) or not isinstance(s,(int,float)) or not math.isfinite(s) or not 0<s<=1 for s in sigmas):
            raise ValueError('Provide exactly steps finite sigmas in (0,1]. Do not include terminal zero.')
        if any(a<=b for a,b in zip(sigmas,sigmas[1:])):
            raise ValueError('Custom sigmas must be strictly decreasing.')
        options['sigmas'] = sigmas
    return options


def run(prompt, width=1024, height=1024, seed=-1, source_image=None, progress=None, step_callback=None,
        schedule='official_8_steps', steps=8, custom_sigmas='', cfg=1.0, negative_prompt='', use_kv_cache=True,
        lora_path=None, lora_strength=1.0, memory_mode='auto'):
    global _pipeline
    validate(prompt, width, height, seed)
    sampling = sampling_options(schedule,steps,custom_sigmas,cfg,negative_prompt,use_kv_cache)
    if isinstance(lora_strength,bool) or not isinstance(lora_strength,(int,float)) or not math.isfinite(lora_strength) or not -2 <= lora_strength <= 2:
        raise ValueError('LoRA strength must be finite and from -2 to 2.')
    if lora_path is not None:
        lora_path = Path(lora_path)
        if not lora_path.is_file() or lora_path.suffix.lower() != '.safetensors':
            raise ValueError('Select an existing compatible Qwen Image 2.1 transformer LoRA safetensors file.')
    if source_image is not None and not isinstance(source_image, Image.Image):
        raise ValueError("Input image must be a decoded image.")
    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA GPU is available. Deploy on an NVIDIA GPU Pod; CPU mode only checks startup.")
    if memory_mode not in ('auto', 'gpu_resident', 'model_cpu_offload'):
        raise ValueError('Choose auto, gpu_resident or model_cpu_offload memory mode.')
    actual_seed = int(seed) if seed >= 0 else secrets.randbelow(2**31)
    with _lock:
        started = time.monotonic()
        try:
            current_mode = getattr(_pipeline, '_turbo_memory_mode', 'model_cpu_offload') if _pipeline is not None else None
            selected_mode = memory_mode
            if selected_mode == 'auto':
                free, total = torch.cuda.mem_get_info()
                # Verified A40 envelope: BF16, <=1 MP, CFG 1, one input image.
                # Larger workloads retain the established offload path.
                enough = total >= 44 * 1024**3 and (current_mode == 'gpu_resident' or free >= 44 * 1024**3)
                selected_mode = 'gpu_resident' if enough and width*height <= 1024*1024 and cfg == 1 else 'model_cpu_offload'
            if _pipeline is not None and current_mode != selected_mode:
                _pipeline = None
                gc.collect()
                torch.cuda.empty_cache()
            if _pipeline is None:
                if progress:
                    progress(0.02, desc="Downloading/loading official checkpoint; first use can take several minutes")
                load_options = {'device_map': 'cuda'} if selected_mode == 'gpu_resident' else {}
                candidate = QwenImage21Pipeline.from_pretrained(MODEL_ID, revision=MODEL_REVISION, dtype=torch.bfloat16, **load_options)
                if selected_mode == 'model_cpu_offload':
                    candidate.enable_model_cpu_offload()
                candidate._turbo_memory_mode = selected_mode
                _pipeline = candidate
            # Reset adapters on every request, including when the next workflow
            # selects None. No adapter state may leak between users/workflows.
            if getattr(_pipeline,'_turbo_has_lora',False):
                _pipeline.unload_lora_weights()
                _pipeline._turbo_has_lora = False
            if lora_path is not None and lora_strength != 0:
                try:
                    _pipeline.load_lora_weights(str(lora_path.parent),weight_name=lora_path.name,adapter_name='turbo_user',use_safetensors=True)
                    if hasattr(_pipeline,'get_active_adapters') and 'turbo_user' not in _pipeline.get_active_adapters():
                        raise ValueError('No compatible transformer adapter was activated.')
                    _pipeline.set_adapters('turbo_user',adapter_weights=float(lora_strength))
                    _pipeline._turbo_has_lora = True
                except Exception as exc:
                    _pipeline = None
                    gc.collect()
                    torch.cuda.empty_cache()
                    raise ValueError('LoRA could not load. Use a transformer adapter compatible with Qwen Image 2.1; older Qwen Image/Edit adapters may have incompatible keys or dimensions.') from exc
            loaded = time.monotonic()
            if progress:
                progress(0.15, desc="Running the checkpoint's saved Turbo schedule")
            kwargs = dict(prompt=prompt.strip(), width=int(width), height=int(height),
                          generator=torch.Generator("cpu").manual_seed(actual_seed), **sampling)
            if step_callback is not None:
                kwargs["callback_on_step_end"] = step_callback
            if source_image is not None:
                if not isinstance(source_image, Image.Image):
                    raise ValueError("Input image must be a decoded image.")
                kwargs["image"] = source_image.convert("RGBA")
            with torch.inference_mode():
                result = _pipeline(**kwargs).images[0]
            metadata = dict(model=MODEL_ID, model_revision=MODEL_REVISION, prompt=prompt.strip(), seed=actual_seed,
                            width=int(width), height=int(height), mode="edit" if source_image else "generate",
                            load_seconds=round(loaded-started, 3), inference_seconds=round(time.monotonic()-loaded, 3),
                            schedule=schedule, requested_steps=steps, actual_steps=int(getattr(_pipeline,'num_timesteps',steps)),
                            scheduler=type(_pipeline.scheduler).__name__ if hasattr(_pipeline,'scheduler') else 'FlowMatchEulerDiscreteScheduler',
                            requested_sigmas=sampling.get('sigmas'), saved_sigmas=list(getattr(getattr(_pipeline,'config',None),'sample_sigmas',[]) or []),
                            true_cfg_scale=float(cfg), negative_prompt=negative_prompt.strip(), use_kv_cache=use_kv_cache,
                            dtype='bfloat16', offload=selected_mode, requested_memory_mode=memory_mode, lora=lora_path.name if lora_path else None,
                            lora_strength=float(lora_strength) if lora_path else 0.0)
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output = OUTPUT_DIR / f"turbo_{metadata['mode']}_{uuid.uuid4().hex}.png"
            metadata['output_filename'] = output.name
            png_info = PngImagePlugin.PngInfo()
            png_info.add_text("turbo_run", json.dumps(metadata))
            result.save(output, pnginfo=png_info)
            output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            return result, str(output), json.dumps(metadata, indent=2)
        except torch.cuda.OutOfMemoryError as exc:
            _pipeline = None
            gc.collect()
            torch.cuda.empty_cache()
            log.exception("GPU memory exhausted")
            raise RuntimeError("GPU memory exhausted. Try 1024×1024, close other workloads, or choose more VRAM; retry reloads the model.") from exc
        except OSError as exc:
            log.exception("Model or output I/O failed")
            raise RuntimeError("Download/cache/output failed. Check free disk space, Hugging Face connectivity and permissions; cached downloads resume on retry. See Pod logs and README.") from exc
        except BaseException:
            # ComfyUI's InterruptProcessingException derives from BaseException.
            # Always re-raise it after cleanup so ComfyUI records cancellation.
            # An interrupted callback can leave offload/KV state unfinished.
            # Reload on retry instead of reusing that partially completed state.
            if step_callback is not None:
                _pipeline = None
                gc.collect()
                torch.cuda.empty_cache()
            log.exception("Turbo request failed")
            raise
