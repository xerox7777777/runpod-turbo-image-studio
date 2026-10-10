"""ComfyUI nodes wrapping Qwen's official Diffusers checkpoint."""
import sys
from pathlib import Path
import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import engine

# Unit tests import these nodes without a running ComfyUI server.
try:
    import server
except ImportError:
    pass
else:
    from request_guard import install
    install()


class TurboGenerate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt": ("STRING", {"multiline": True, "default": "A sailboat on a calm lake at sunrise"}),
            "width": ("INT", {"default": 1024, "min": 512, "max": 2752, "step": 16}),
            "height": ("INT", {"default": 1024, "min": 512, "max": 2752, "step": 16}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
        }}
    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "alpha_mask", "run_details")
    FUNCTION = "generate"
    CATEGORY = "Turbo Image Studio/Official Qwen"

    @staticmethod
    def convert(result):
        image, _, details = result
        pixels = np.asarray(image.convert("RGBA")).astype(np.float32) / 255.0
        return torch.from_numpy(pixels[None, :, :, :3].copy()), torch.from_numpy((1-pixels[None, :, :, 3]).copy()), details

    def generate(self, prompt, width, height, seed):
        return self.convert(engine.run(prompt, width, height, seed))


class TurboEdit(TurboGenerate):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        inputs["required"]["image"] = ("IMAGE",)
        return inputs

    def generate(self, prompt, width, height, seed, image):
        if image.ndim != 4 or image.shape[0] != 1:
            raise ValueError("Use one input image per edit request.")
        source = Image.fromarray((image[0].detach().cpu().clamp(0, 1).numpy()*255).round().astype(np.uint8))
        return self.convert(engine.run(prompt, width, height, seed, source))


NODE_CLASS_MAPPINGS = {"OfficialTurboGenerate": TurboGenerate, "OfficialTurboEdit": TurboEdit}
NODE_DISPLAY_NAME_MAPPINGS = {"OfficialTurboGenerate": "Official Qwen 2.1 Turbo Generate", "OfficialTurboEdit": "Official Qwen 2.1 Turbo Edit"}
