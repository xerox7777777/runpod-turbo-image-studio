"""ComfyUI nodes wrapping Qwen's official Diffusers checkpoint."""
import sys
import math
import json
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
        return self.convert(engine.run(prompt, width, height, seed, step_callback=self.step_callback()))

    @staticmethod
    def step_callback():
        try:
            from comfy.utils import ProgressBar
            from comfy.model_management import throw_exception_if_processing_interrupted
        except ImportError:
            return None  # Standalone engine unit tests do not install ComfyUI.
        progress = ProgressBar(1)
        def update(pipeline, step, timestep, tensors):
            throw_exception_if_processing_interrupted()
            progress.update_absolute(step + 1, pipeline.num_timesteps)
            return tensors
        return update


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
        return self.convert(engine.run(prompt, width, height, seed, source, step_callback=self.step_callback()))


NODE_CLASS_MAPPINGS = {"OfficialTurboGenerate": TurboGenerate, "OfficialTurboEdit": TurboEdit}
NODE_DISPLAY_NAME_MAPPINGS = {"OfficialTurboGenerate": "Official Qwen 2.1 Turbo Generate", "OfficialTurboEdit": "Official Qwen 2.1 Turbo Edit"}


class TurboModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'checkpoint':([engine.MODEL_ID],), 'precision':(['bfloat16'],), 'offload':(['auto','gpu_resident','model_cpu_offload'],)}}
    RETURN_TYPES=('TURBO_MODEL',)
    FUNCTION='configure'
    CATEGORY='Turbo Image Studio/Workflow'
    def configure(self,checkpoint,precision,offload):
        if checkpoint != engine.MODEL_ID or precision != 'bfloat16' or offload not in ('auto','gpu_resident','model_cpu_offload'):
            raise ValueError('Use the pinned official Turbo checkpoint, BF16 and a supported memory mode.')
        return ({'checkpoint':checkpoint,'precision':precision,'offload':offload},)


class TurboLora:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths
        names=[n for n in folder_paths.get_filename_list('loras') if n.lower().endswith('.safetensors')]
        return {'required':{'model':('TURBO_MODEL',),'lora_name':(['None']+names,),
                            'strength':('FLOAT',{'default':1.0,'min':-2.0,'max':2.0,'step':0.05})}}
    RETURN_TYPES=('TURBO_MODEL',)
    FUNCTION='configure'
    CATEGORY='Turbo Image Studio/Workflow'
    @classmethod
    def IS_CHANGED(cls,model,lora_name,strength):
        if lora_name=='None': return (lora_name,strength)
        import folder_paths
        p=Path(folder_paths.get_full_path_or_raise('loras',lora_name))
        return (lora_name,strength,p.stat().st_mtime_ns,p.stat().st_size)
    def configure(self,model,lora_name,strength):
        result=dict(model)
        result.update(lora_path=None,lora_strength=strength)
        if lora_name!='None':
            import folder_paths
            path=Path(folder_paths.get_full_path_or_raise('loras',lora_name)).resolve()
            roots=folder_paths.get_folder_paths('loras')
            if path.suffix.lower()!='.safetensors' or not any(path.is_relative_to(Path(r).resolve()) for r in roots):
                raise ValueError('LoRA must be a safetensors file inside a configured LoRA folder.')
            result['lora_path']=str(path)
        return (result,)


class TurboPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'prompt':('STRING',{'multiline':True,'default':'A sailboat on a calm lake at sunrise'}),
                            'negative_prompt':('STRING',{'multiline':True,'default':''})}}
    RETURN_TYPES=('TURBO_CONDITIONING',)
    FUNCTION='configure'
    CATEGORY='Turbo Image Studio/Workflow'
    def configure(self,prompt,negative_prompt):
        if not prompt.strip(): raise ValueError('Enter a prompt first.')
        return ({'prompt':prompt,'negative_prompt':negative_prompt},)


class TurboSampling:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'schedule':(['official_8_steps','experimental_linear','experimental_custom'],),
            'steps':('INT',{'default':8,'min':1,'max':50}),
            'cfg':('FLOAT',{'default':1.0,'min':1.0,'max':10.0,'step':0.1}),
            'use_kv_cache':('BOOLEAN',{'default':True}),
            'custom_sigmas':('STRING',{'multiline':True,'default':'[1.0, 0.875, 0.75, 0.625, 0.5, 0.375, 0.25, 0.125]'})}}
    RETURN_TYPES=('TURBO_SAMPLING',)
    FUNCTION='configure'
    CATEGORY='Turbo Image Studio/Workflow'
    def configure(self,schedule,steps,cfg,use_kv_cache,custom_sigmas):
        # CFG/negative-prompt compatibility is checked when inputs meet in Sampler.
        engine.sampling_options(schedule,steps,custom_sigmas,cfg,'validation' if cfg>1 else '',use_kv_cache)
        return ({'schedule':schedule,'steps':steps,'cfg':cfg,'use_kv_cache':use_kv_cache,'custom_sigmas':custom_sigmas},)


class TurboSampler(TurboGenerate):
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'model':('TURBO_MODEL',),'conditioning':('TURBO_CONDITIONING',),'sampling':('TURBO_SAMPLING',),
                            'width':('INT',{'default':1024,'min':512,'max':2752,'step':16}),
                            'height':('INT',{'default':1024,'min':512,'max':2752,'step':16}),
                            'seed':('INT',{'default':42,'min':0,'max':2147483647})},
                'optional':{'image':('IMAGE',)}}
    CATEGORY='Turbo Image Studio/Workflow'
    def generate(self,model,conditioning,sampling,width,height,seed,image=None):
        source=None
        if image is not None:
            if image.ndim!=4 or image.shape[0]!=1: raise ValueError('Use one input image per edit request.')
            source=Image.fromarray((image[0].detach().cpu().clamp(0,1).numpy()*255).round().astype(np.uint8))
        if model.get('checkpoint')!=engine.MODEL_ID: raise ValueError('This sampler requires the official Turbo model configuration.')
        return self.convert(engine.run(conditioning['prompt'],width,height,seed,source,
            step_callback=self.step_callback(),negative_prompt=conditioning['negative_prompt'],**sampling,
            lora_path=model.get('lora_path'),lora_strength=model.get('lora_strength',1.0),memory_mode=model.get('offload','auto')))


class TurboResolution:
    RATIOS = {'1:1': 1, '3:4': 3/4, '4:3': 4/3, '2:3': 2/3,
              '3:2': 3/2, '9:16': 9/16, '16:9': 16/9, '9:21': 9/21, '21:9': 21/9}
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'mode': (['aspect_ratio', 'match_input', 'manual'],),
            'aspect_ratio': (list(cls.RATIOS),),
            'target_megapixels': ('FLOAT', {'default': 1.048576, 'min': 0.25, 'max': 4.0, 'step': 0.05}),
            'multiplier': ('FLOAT', {'default': 1.0, 'min': 0.25, 'max': 2.0, 'step': 0.05}),
            'manual_width': ('INT', {'default': 1024, 'min': 512, 'max': 2752, 'step': 16}),
            'manual_height': ('INT', {'default': 1024, 'min': 512, 'max': 2752, 'step': 16})},
            'optional': {'image': ('IMAGE',)}}
    RETURN_TYPES = ('INT', 'INT', 'STRING')
    RETURN_NAMES = ('width', 'height', 'resolution_details')
    FUNCTION = 'calculate'
    CATEGORY = 'Turbo Image Studio/Workflow'
    def calculate(self, mode, aspect_ratio, target_megapixels, multiplier, manual_width, manual_height, image=None):
        if not math.isfinite(target_megapixels) or not 0.25 <= target_megapixels <= 4:
            raise ValueError('Target megapixels must be 0.25–4.')
        if not math.isfinite(multiplier) or not 0.25 <= multiplier <= 2:
            raise ValueError('Resolution multiplier must be 0.25–2; it multiplies both dimensions.')
        if mode == 'manual':
            engine.validate('resolution', manual_width, manual_height, 0)
            w, h = manual_width, manual_height
        elif mode in ('aspect_ratio', 'match_input'):
            if mode == 'match_input':
                if image is None or image.ndim != 4 or image.shape[0] != 1 or min(image.shape[1:3]) <= 0:
                    raise ValueError('Match input needs one connected input image.')
                ratio = image.shape[2]/image.shape[1]
            else:
                if aspect_ratio not in self.RATIOS: raise ValueError('Choose a supported aspect ratio.')
                ratio = self.RATIOS[aspect_ratio]
            area = target_megapixels*1_000_000
            w, h = math.sqrt(area*ratio), math.sqrt(area/ratio)
        else:
            raise ValueError('Choose aspect_ratio, match_input or manual sizing.')
        # Round down so alignment cannot push a nominal 1 MP preset into CPU offload.
        w, h = (int(math.floor(x*multiplier/16))*16 for x in (w,h))
        if not (512 <= w <= 2752 and 512 <= h <= 2752):
            raise ValueError(f'Calculated {w}×{h} is outside 512–2752 per dimension. Adjust target megapixels/multiplier or use manual mode.')
        details = json.dumps({'mode': mode, 'aspect_ratio': aspect_ratio if mode == 'aspect_ratio' else None,
            'target_megapixels': target_megapixels if mode != 'manual' else None,
            'dimension_multiplier': multiplier, 'width': w, 'height': h,
            'actual_megapixels': round(w*h/1_000_000, 6), 'alignment': 16}, indent=2)
        return w, h, details


class TurboRunDetails:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'details':('STRING',{'forceInput':True})}}
    RETURN_TYPES=()
    OUTPUT_NODE=True
    FUNCTION='show'
    CATEGORY='Turbo Image Studio/Workflow'
    def show(self,details): return {'ui':{'text':[details]}}


class TurboSavedResult:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'details': ('STRING', {'forceInput': True})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'show'
    CATEGORY = 'Turbo Image Studio/Workflow'
    def show(self, details):
        import json
        import folder_paths
        filename = json.loads(details)['output_filename']
        path = (engine.OUTPUT_DIR / filename).resolve()
        output_root = Path(folder_paths.get_output_directory()).resolve()
        if path.parent != engine.OUTPUT_DIR.resolve() or not path.is_file() or not path.is_relative_to(output_root):
            raise ValueError('The saved Turbo image must be inside the ComfyUI output directory.')
        relative = path.relative_to(output_root)
        return {'ui': {'images': [{'filename': relative.name, 'subfolder': str(relative.parent) if relative.parent != Path('.') else '', 'type': 'output'}]}}


NODE_CLASS_MAPPINGS.update({'TurboResolution':TurboResolution,'TurboSavedResult':TurboSavedResult,'TurboModelConfig':TurboModel,'TurboLoraLoader':TurboLora,'TurboPrompt':TurboPrompt,
                          'TurboSamplingSettings':TurboSampling,'TurboSampler':TurboSampler,'TurboRunDetails':TurboRunDetails})
NODE_DISPLAY_NAME_MAPPINGS.update({'TurboResolution':'Aspect Ratio / Auto Resolution / Multiplier','TurboSavedResult':'Saved Turbo Image (original RGBA)','TurboModelConfig':'Official Turbo Model / Precision',
    'TurboLoraLoader':'Qwen 2.1 Transformer LoRA (optional)', 'TurboPrompt':'Turbo Positive / Negative Prompt',
    'TurboSamplingSettings':'Turbo Schedule / Steps / CFG / KV Cache', 'TurboSampler':'Turbo Generate or Edit Sampler',
    'TurboRunDetails':'Actual Turbo Run Settings'})
WEB_DIRECTORY='./web'
