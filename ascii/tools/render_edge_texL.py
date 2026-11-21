import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
inst = ng.nodes["Instance on Points"]
idx = ng.nodes.get("Debug Const Index")
if idx is None:
    idx = ng.nodes.new("ShaderNodeMath")
    idx.name = "Debug Const Index"
    idx.operation = "ADD"
    idx.inputs[0].default_value = 8.0
for link in list(inst.inputs["Instance Index"].links):
    ng.links.remove(link)
ng.links.new(idx.outputs[0], inst.inputs["Instance Index"])

store = ng.nodes["Store Named Attribute"]
for link in list(store.inputs["Value"].links):
    ng.links.remove(link)
ng.links.new(ng.nodes["Edge Tex L"].outputs["Color"], store.inputs["Value"])

sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.frame_set(1800)
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = r"G:\VDGP\ascii\experiments\edge\test_edge_texL.png"
bpy.ops.render.render(write_still=True)
print("RENDERED")
