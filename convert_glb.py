import bpy
import sys
import re
from pathlib import Path

source, output = map(Path, sys.argv[sys.argv.index('--') + 1:])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
if not any(o.type == 'MESH' for o in bpy.context.scene.objects):
    raise RuntimeError('No mesh imported')
# Extract embedded images without recompressing or changing their color space.
for i, img in enumerate(bpy.data.images, 1):
    if img.source != 'FILE' and not img.packed_file:
        continue
    packed = img.packed_file
    data = bytes(packed.data) if packed else Path(bpy.path.abspath(img.filepath)).read_bytes()
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        ext = '.png'
    elif data.startswith(b'\xff\xd8'):
        ext = '.jpg'
    else:
        ext = Path(img.filepath).suffix or '.bin'
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', Path(img.name).stem)[:80] or 'texture'
    path = output / f'{i:02d}_{name}{ext}'
    path.write_bytes(data)
    if packed:
        img.unpack(method='REMOVE')
    img.filepath = str(path)
    img.reload()
    print('Texture:', path.name)

# glTF and DAZ use Y-up; keep the original model size and UV coordinates.
obj = output / (source.stem + '.obj')
bpy.ops.wm.obj_export(filepath=str(obj), check_existing=False,
    forward_axis='NEGATIVE_Z', up_axis='Y', global_scale=1.0,
    export_uv=True, export_normals=True, export_materials=True,
    export_pbr_extensions=False, path_mode='RELATIVE',
    export_triangulated_mesh=False, export_material_groups=True)
mtl = obj.with_suffix('.mtl')
if not obj.is_file() or not mtl.is_file():
    raise RuntimeError('OBJ or MTL missing')
if not any(line.strip().startswith('map_Kd ') for line in mtl.read_text(encoding='utf-8', errors='replace').splitlines()):
    print('WARNING: No map_Kd in MTL. Assign base color manually in DAZ if needed.')
print('Export finished:', obj)
