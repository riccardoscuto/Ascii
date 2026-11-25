import bpy
from mathutils import Vector
from pathlib import Path

RAMP = " .,:;+HW@"
CELL = 0.012345679
OUT = Path(r"G:\VDGP\gcf\ascii\glyphs\branch_atlas.png")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
font = bpy.data.fonts.get("Bfont Regular") or bpy.data.fonts.load("<builtin>")

material = bpy.data.materials.new("AtlasWhite")
material.use_nodes = True
nt = material.node_tree
nt.nodes.clear()
em = nt.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (1, 1, 1, 1)
em.inputs["Strength"].default_value = 1.0
outn = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(em.outputs[0], outn.inputs[0])

for i, char in enumerate(RAMP):
    curve = bpy.data.curves.new(f"atlas_curve_{i}", type="FONT")
    curve.body = char
    curve.font = font
    curve.size = 1.0
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    obj = bpy.data.objects.new(f"atlas_{i}", curve)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.view_layer.objects.active
    obj.select_set(False)
    if obj.type != "MESH":
        obj.data = bpy.data.meshes.new(f"atlas_mesh_{i}")
    mesh = obj.data
    if len(mesh.vertices):
        xs = [v.co.x for v in mesh.vertices]
        ys = [v.co.y for v in mesh.vertices]
        zs = [v.co.z for v in mesh.vertices]
        center = Vector(((min(xs) + max(xs)) * 0.5,
                         (min(ys) + max(ys)) * 0.5,
                         (min(zs) + max(zs)) * 0.5))
        for v in mesh.vertices:
            v.co = (v.co - center) * CELL * 0.9
        mesh.update()
        print("ATLAS", i, repr(char), round(max(xs) - min(xs), 3),
              round(max(ys) - min(ys), 3))
    obj.location = ((i - 4) * CELL, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj.data.materials.append(material)

cam_data = bpy.data.cameras.new("atlas-cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = len(RAMP) * CELL
cam = bpy.data.objects.new("atlas-cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0, 0, 1)
bpy.context.scene.camera = cam

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 16
scene.render.resolution_x = len(RAMP) * 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.view_settings.view_transform = "Standard"
scene.world = bpy.data.worlds.new("atlas-world")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0, 0, 0, 1)
bg.inputs[1].default_value = 0
scene.render.filepath = str(OUT)
bpy.ops.render.render(write_still=True)
print("TEXT_ATLAS_DONE", OUT)
