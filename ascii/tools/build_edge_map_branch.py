import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}

edge_img = bpy.data.images.load(r"G:\VDGP\ascii\experiments\edge\edge60_96.png", check_existing=False)
try:
    edge_img.colorspace_settings.name = "Non-Color"
except Exception:
    pass

tex = ng.nodes.get("Edge Map")
if tex is None:
    tex = ng.nodes.new("GeometryNodeImageTexture")
    tex.name = "Edge Map"
    tex.inputs[0].default_value = edge_img
    ng.links.new(ng.nodes["UV Offset"].outputs[0], tex.inputs["Vector"])
else:
    tex.inputs[0].default_value = edge_img

sep = ng.nodes.get("Edge Map Sep")
if sep is None:
    sep = ng.nodes.new("FunctionNodeSeparateColor")
    sep.name = "Edge Map Sep"
    sep.mode = "RGB"
    ng.links.new(tex.outputs["Color"], sep.inputs[0])

strength = ng.nodes["Edge Strength Mul"]
for link in list(strength.inputs[0].links):
    ng.links.remove(link)
ng.links.new(sep.outputs["Red"], strength.inputs[0])

mul = ng.nodes.get("Edge Map Bin Mul")
if mul is None:
    mul = ng.nodes.new("ShaderNodeMath")
    mul.name = "Edge Map Bin Mul"
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 3.0
ng.links.new(sep.outputs["Green"], mul.inputs[0])
rnd = ng.nodes.get("Edge Map Bin Round")
if rnd is None:
    rnd = ng.nodes.new("ShaderNodeMath")
    rnd.name = "Edge Map Bin Round"
    rnd.operation = "ROUND"
ng.links.new(mul.outputs[0], rnd.inputs[0])
add = ng.nodes.get("Edge Map Bin Add")
if add is None:
    add = ng.nodes.new("ShaderNodeMath")
    add.name = "Edge Map Bin Add"
    add.operation = "ADD"
    add.inputs[1].default_value = 9.0
ng.links.new(rnd.outputs[0], add.inputs[0])

mixb = ng.nodes["Edge Mix B"]
for link in list(mixb.inputs[0].links):
    ng.links.remove(link)
ng.links.new(add.outputs[0], mixb.inputs[0])

getattr(ins, ids["Edge Strength"]).value = 1.0
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.frame_set(1800)
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
for tag, s in (("emap_s050", 0.5), ("emap_s080", 0.8), ("emap_s100", 1.0)):
    getattr(ins, ids["Edge Strength"]).value = s
    sc.render.filepath = rf"G:\VDGP\ascii\experiments\edge\{tag}.png"
    bpy.ops.render.render(write_still=True)
    print("WROTE", tag)

getattr(ins, ids["Edge Strength"]).value = 0.8
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\experiments\edge_map_work.blend")
print("SAVED")

