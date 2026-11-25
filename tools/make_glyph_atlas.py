import bpy
from pathlib import Path

RAMP = " .,:;+HW@"
CELL = 0.012345679
SIZE = 0.9 * CELL
N = len(RAMP)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gcf" / "ascii" / "glyphs"
OUT.mkdir(parents=True, exist_ok=True)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

font = bpy.data.fonts.load("<builtin>")

mesh = bpy.data.meshes.new("points")
verts = [((i - 4) * CELL, 0.0, 0.0) for i in range(N)]
mesh.from_pydata(verts, [], [])
mesh.update()
obj = bpy.data.objects.new("glyphs", mesh)
bpy.context.collection.objects.link(obj)

ng = bpy.data.node_groups.new("BranchNodes", "GeometryNodeTree")
ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
gin = ng.nodes.new("NodeGroupInput")
gout = ng.nodes.new("NodeGroupOutput")

idx = ng.nodes.new("GeometryNodeInputIndex")
store = ng.nodes.new("GeometryNodeStoreNamedAttribute")
store.data_type = "FLOAT"
store.domain = "POINT"
store.inputs["Name"].default_value = "glyph"
ng.links.new(gin.outputs[0], store.inputs["Geometry"])
ng.links.new(idx.outputs[0], store.inputs["Value"])

material = bpy.data.materials.new("GlyphEmission")
material.use_nodes = True
nt = material.node_tree
nt.nodes.clear()
em = nt.nodes.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (1, 1, 1, 1)
em.inputs["Strength"].default_value = 1.0
outn = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(em.outputs[0], outn.inputs[0])

joins = []
for i, char in enumerate(RAMP):
    s2c = ng.nodes.new("GeometryNodeStringToCurves")
    s2c.inputs["String"].default_value = char
    s2c.inputs["Font"].default_value = font
    s2c.inputs["Size"].default_value = SIZE
    s2c.inputs["Align X"].default_value = "Center"
    s2c.inputs["Align Y"].default_value = "Bottom Baseline"
    s2c.inputs["Pivot Point"].default_value = "Top Center"
    fill = ng.nodes.new("GeometryNodeFillCurve")
    cmp = ng.nodes.new("FunctionNodeCompare")
    cmp.data_type = "FLOAT"
    cmp.operation = "EQUAL"
    cmp.inputs[1].default_value = float(i)
    attr = ng.nodes.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = "glyph"
    iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
    ng.links.new(attr.outputs["Attribute"], cmp.inputs[0])
    ng.links.new(store.outputs["Geometry"], iop.inputs["Points"])
    ng.links.new(cmp.outputs[0], iop.inputs["Selection"])
    ng.links.new(s2c.outputs["Curve Instances"], fill.inputs["Curve"])
    ng.links.new(fill.outputs["Mesh"], iop.inputs["Instance"])
    joins.append(iop.outputs["Instances"])

join = ng.nodes.new("GeometryNodeJoinGeometry")
for out in joins:
    ng.links.new(out, join.inputs["Geometry"])
setmat = ng.nodes.new("GeometryNodeSetMaterial")
setmat.inputs["Material"].default_value = material
ng.links.new(join.outputs[0], setmat.inputs["Geometry"])
ng.links.new(setmat.outputs["Geometry"], gout.inputs[0])
obj.modifiers.new("Glyphs", "NODES").node_group = ng

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = N * CELL
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0, 0.5 * CELL, 1)
bpy.context.scene.camera = cam

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 16
scene.render.resolution_x = N * 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.view_settings.view_transform = "Standard"
scene.world = bpy.data.worlds.new("world")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0, 0, 0, 1)
bg.inputs[1].default_value = 0
scene.render.filepath = str(OUT / "branch_atlas.png")
bpy.ops.render.render(write_still=True)
print("BRANCH_ATLAS_DONE", OUT / "branch_atlas.png")
