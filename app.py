#!/usr/bin/env python3
"""A small Gradio UI for the official Qwen Image 2.1 Turbo checkpoint."""

from __future__ import annotations

import os
import secrets
import threading
import uuid
from pathlib import Path

import gradio as gr
import torch
from diffusers import QwenImage21Pipeline
from PIL import Image


MODEL_ID = os.environ.get("MODEL_ID", "Qwen/Qwen-Image-2.1-Turbo")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/workspace/outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_pipeline: QwenImage21Pipeline | None = None
_load_lock = threading.Lock()
_inference_lock = threading.Lock()


def _get_pipeline(progress: gr.Progress) -> QwenImage21Pipeline:
    global _pipeline

    if not torch.cuda.is_available():
        raise gr.Error("No CUDA GPU is available. Create this template on a GPU Pod.")

    if _pipeline is None:
        with _load_lock:
            if _pipeline is None:
                progress(0.02, desc="Downloading/loading the official checkpoint (first use can take a while)")
                candidate = QwenImage21Pipeline.from_pretrained(
                    MODEL_ID,
                    dtype=torch.bfloat16,
                )
                candidate.to("cuda")
                _pipeline = candidate

    return _pipeline


def _validate(prompt: str, width: int, height: int) -> None:
    if not prompt or not prompt.strip():
        raise gr.Error("Enter a prompt first.")
    for label, value in (("Width", width), ("Height", height)):
        if value < 512 or value > 2752 or value % 16:
            raise gr.Error(f"{label} must be between 512 and 2752 and divisible by 16.")


def _run(
    prompt: str,
    width: int,
    height: int,
    seed: int,
    source_image: Image.Image | None,
    progress: gr.Progress = gr.Progress(),
) -> tuple[Image.Image, str, str]:
    _validate(prompt, int(width), int(height))
    actual_seed = int(seed) if int(seed) >= 0 else secrets.randbelow(2**31)
    pipe = _get_pipeline(progress)

    kwargs: dict[str, object] = {
        "prompt": prompt.strip(),
        "width": int(width),
        "height": int(height),
        "use_kv_cache": True,
        "generator": torch.Generator("cpu").manual_seed(actual_seed),
    }
    if source_image is not None:
        kwargs["image"] = source_image.convert("RGBA")

    progress(0.15, desc="Generating with the saved Turbo sampling schedule")
    with _inference_lock:
        image = pipe(**kwargs).images[0]

    filename = f"turbo_{'edit' if source_image is not None else 'generate'}_{uuid.uuid4().hex[:12]}.png"
    output_path = OUTPUT_DIR / filename
    image.save(output_path)
    return image, str(output_path), f"Seed: {actual_seed} · Saved: {output_path}"


def generate(prompt: str, width: int, height: int, seed: int, progress: gr.Progress = gr.Progress()):
    return _run(prompt, width, height, seed, None, progress)


def edit(
    source_image: Image.Image | None,
    prompt: str,
    width: int,
    height: int,
    seed: int,
    progress: gr.Progress = gr.Progress(),
):
    if source_image is None:
        raise gr.Error("Upload an input image to edit.")
    return _run(prompt, width, height, seed, source_image, progress)


username = os.environ.get("UI_USERNAME", "").strip()
password = os.environ.get("UI_PASSWORD", "")
if bool(username) != bool(password):
    raise RuntimeError("Set both UI_USERNAME and UI_PASSWORD, or leave both unset.")
auth = (username, password) if username and password else None

with gr.Blocks(title="Turbo Image Studio", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# Turbo Image Studio\n"
        "Text-to-image and image editing with the official `Qwen/Qwen-Image-2.1-Turbo` checkpoint. "
        "The first generation downloads the checkpoint into the RunPod workspace cache. "
        "See the project README for the model license and access guidance."
    )
    with gr.Tab("Generate"):
        prompt_in = gr.Textbox(label="Prompt", lines=5, placeholder="Describe the image to create")
        with gr.Row():
            width_in = gr.Slider(512, 2752, value=1024, step=16, label="Width")
            height_in = gr.Slider(512, 2752, value=1024, step=16, label="Height")
            seed_in = gr.Slider(-1, 2147483647, value=-1, step=1, label="Seed (-1 = random)")
        generate_button = gr.Button("Generate", variant="primary")
        generated = gr.Image(label="Generated image", type="pil", interactive=False)
        generated_file = gr.File(label="Download PNG")
        generated_info = gr.Textbox(label="Run details", interactive=False)
        generate_button.click(
            generate,
            inputs=[prompt_in, width_in, height_in, seed_in],
            outputs=[generated, generated_file, generated_info],
            concurrency_limit=1,
        )

    with gr.Tab("Edit"):
        source_in = gr.Image(label="Input image", type="pil")
        edit_prompt = gr.Textbox(label="Edit instructions", lines=5, placeholder="Describe how to transform the input image")
        with gr.Row():
            edit_width = gr.Slider(512, 2752, value=1024, step=16, label="Output width")
            edit_height = gr.Slider(512, 2752, value=1024, step=16, label="Output height")
            edit_seed = gr.Slider(-1, 2147483647, value=-1, step=1, label="Seed (-1 = random)")
        edit_button = gr.Button("Edit image", variant="primary")
        edited = gr.Image(label="Edited image", type="pil", interactive=False)
        edited_file = gr.File(label="Download PNG")
        edited_info = gr.Textbox(label="Run details", interactive=False)
        edit_button.click(
            edit,
            inputs=[source_in, edit_prompt, edit_width, edit_height, edit_seed],
            outputs=[edited, edited_file, edited_info],
            concurrency_limit=1,
        )

    gr.Markdown(
        "**Access:** this Pod's Gradio page is reachable by anyone who has its RunPod proxy URL "
        "unless `UI_USERNAME` and `UI_PASSWORD` are configured in the Pod environment."
    )

demo.queue(default_concurrency_limit=1, max_size=4)
demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", "7860")),
    share=False,
    auth=auth,
    allowed_paths=[str(OUTPUT_DIR)],
    analytics_enabled=False,
)
