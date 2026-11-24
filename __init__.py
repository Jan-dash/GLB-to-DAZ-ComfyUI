import os
import re
import subprocess
import tempfile
from pathlib import Path
import folder_paths

class DAZExportGLB:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'glb': ('FILE_3D_GLB',),
            'blender_path': ('STRING', {'default': 'Path to Blender executable'}),
            'filename_prefix': ('STRING', {'default': 'daz_export'}),
            'enabled': ('BOOLEAN', {'default': True}),
        }, 'optional': {
            'output_directory': ('STRING', {'default': '', 'tooltip': 'Optional output folder. Leave empty to use the ComfyUI output folder. Relative paths are resolved inside the ComfyUI output folder.'}),
            'timeout_seconds': ('INT', {'default': 1800, 'min': 1, 'max': 86400, 'tooltip': 'Maximum Blender runtime in seconds.'}),
        }}
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('obj_path',)
    FUNCTION = 'convert'
    OUTPUT_NODE = True
    CATEGORY = '3D/DAZ'

    def convert(self, glb, blender_path, filename_prefix, enabled, output_directory='', timeout_seconds=1800):
        if not enabled:
            return {'ui': {'text': ['DAZ export disabled']}, 'result': ('',)}
        blender_value = blender_path.strip().strip('"')
        if not blender_value or blender_value == 'Path to Blender executable':
            raise RuntimeError('Set blender_path to the full path of your Blender executable.')
        blender = Path(blender_value).expanduser()
        if blender.name.lower() == 'blender-launcher.exe':
            blender = blender.with_name('blender.exe')
        if not blender.is_file():
            raise RuntimeError(f'Blender not found: {blender}')
        output_value = output_directory.strip().strip('"')
        root = Path(output_value).expanduser() if output_value else Path(folder_paths.get_output_directory())
        if output_value and not root.is_absolute():
            root = Path(folder_paths.get_output_directory()) / root
        root.mkdir(parents=True, exist_ok=True)
        prefix = re.sub(r'[^a-zA-Z0-9_-]', '_', filename_prefix)[:100] or 'daz_export'
        i = 1
        while True:
            out = root / f'{prefix}_{i:05d}'
            try:
                out.mkdir()
                break
            except FileExistsError:
                i += 1
        try:
            with tempfile.TemporaryDirectory(prefix='daz_', dir=folder_paths.get_temp_directory()) as tmp:
                src = Path(tmp) / (out.name + '.glb')
                if callable(getattr(glb, 'save_to', None)):
                    glb.save_to(str(src))
                elif isinstance(glb, (str, os.PathLike)):
                    import shutil
                    name = os.fspath(glb)
                    candidates = [Path(name), Path(folder_paths.get_annotated_filepath(name, folder_paths.get_temp_directory())), Path(folder_paths.get_output_directory()) / name]
                    original = next((p for p in candidates if p.is_file()), None)
                    if original is None:
                        raise RuntimeError(f'GLB not found: {name}')
                    shutil.copyfile(original, src)
                else:
                    raise TypeError(f'Unsupported GLB input: {type(glb).__name__}')
                with src.open('rb') as f:
                    if f.read(4) != b'glTF':
                        raise RuntimeError('Input is not a binary GLB file')
                log = out / 'blender.log'
                cmd = [str(blender), '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(Path(__file__).with_name('convert_glb.py')), '--', str(src), str(out)]
                print(f'[DAZ Export] Exporting to {out}', flush=True)
                with log.open('w', encoding='utf-8') as stream:
                    subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=timeout_seconds)
                obj = out / (src.stem + '.obj')
                if not obj.is_file() or not obj.with_suffix('.mtl').is_file():
                    raise RuntimeError('OBJ or MTL missing')
        except Exception as exc:
            raise RuntimeError(f'DAZ export failed: {exc}. Output/log: {out}') from exc
        print(f'[DAZ Export] Done: {obj}', flush=True)
        return {'ui': {'text': [str(obj)]}, 'result': (str(obj),)}

NODE_CLASS_MAPPINGS = {'DAZExportGLB': DAZExportGLB}
NODE_DISPLAY_NAME_MAPPINGS = {'DAZExportGLB': 'Export GLB to DAZ (Blender)'}
