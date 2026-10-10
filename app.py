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


from engine import MODEL_ID, OUTPUT_DIR, run as engine_run
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def _run(prompt, width, height, seed, source_image, progress):
    try:
        return engine_run(prompt, width, height, seed, source_image, progress)
    except (ValueError, RuntimeError) as exc:
        raise gr.Error(str(exc)) from exc


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

with gr.Blocks(title="Turbo Image Studio", theme=gr.themes.Soft(), analytics_enabled=False) as demo:
    gr.Markdown(
        "# Turbo Image Studio\n"
        "Text-to-image and image editing with the official `Qwen/Qwen-Image-2.1-Turbo` checkpoint. "
        "The first generation downloads the checkpoint into the RunPod workspace cache. "
        "Research/evaluation only under the model license. [README and support](https://github.com/xerox7777777/runpod-turbo-image-studio#readme)."
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
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        share=False,
        auth=auth,
        allowed_paths=[str(OUTPUT_DIR)],
    )
