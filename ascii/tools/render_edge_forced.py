import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
getattr(ins, ids["Edge Strength"]).value = 1.0
mask = ng.nodes["Edge Mask"]
for link in list(mask.inputs[1].links):
    ng.links.remove(link)
for link in list(mask.inputs[2].links):
    ng.links.remove(link)
mask.inputs[1].default_value = -1.0
mask.inputs[2].default_value = -0.9
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.frame_set(1800)
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = r"G:\VDGP\ascii\experiments\edge\test_edge_forced.png"
bpy.ops.render.render(write_still=True)
print("RENDERED")
