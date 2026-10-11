"""Shared official-checkpoint inference for ComfyUI and optional Gradio."""
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


def run(prompt, width=1024, height=1024, seed=-1, source_image=None, progress=None, step_callback=None):
    global _pipeline
    validate(prompt, width, height, seed)
    if source_image is not None and not isinstance(source_image, Image.Image):
        raise ValueError("Input image must be a decoded image.")
    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA GPU is available. Deploy on an NVIDIA GPU Pod; CPU mode only checks startup.")
    actual_seed = int(seed) if seed >= 0 else secrets.randbelow(2**31)
    with _lock:
        started = time.monotonic()
        try:
            if _pipeline is None:
                if progress:
                    progress(0.02, desc="Downloading/loading official checkpoint; first use can take several minutes")
                candidate = QwenImage21Pipeline.from_pretrained(MODEL_ID, revision=MODEL_REVISION, dtype=torch.bfloat16)
                # CPU offload lowers peak VRAM; no quantized or third-party weights.
                candidate.enable_model_cpu_offload()
                _pipeline = candidate
            loaded = time.monotonic()
            if progress:
                progress(0.15, desc="Running the checkpoint's saved Turbo schedule")
            kwargs = dict(prompt=prompt.strip(), width=int(width), height=int(height),
                          use_kv_cache=True, generator=torch.Generator("cpu").manual_seed(actual_seed))
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
                            schedule="checkpoint saved Turbo schedule", use_kv_cache=True)
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output = OUTPUT_DIR / f"turbo_{metadata['mode']}_{uuid.uuid4().hex}.png"
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
