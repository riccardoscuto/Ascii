import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
inst = ng.nodes["Instance on Points"]
mag = ng.nodes["Edge Mag"]
dbg = ng.nodes.get("Debug Mag Index")
if dbg is None:
    dbg = ng.nodes.new("ShaderNodeMapRange")
    dbg.name = "Debug Mag Index"
    dbg.data_type = "FLOAT"
    dbg.clamp = True
    dbg.inputs[1].default_value = 0.0
    dbg.inputs[2].default_value = 0.15
    dbg.inputs[3].default_value = 0.0
    dbg.inputs[4].default_value = 8.0
    try:
        dbg.interpolation_type = "LINEAR"
    except Exception:
        pass
ng.links.new(mag.outputs[0], dbg.inputs[0])
for link in list(inst.inputs["Instance Index"].links):
    ng.links.remove(link)
ng.links.new(dbg.outputs[0], inst.inputs["Instance Index"])

sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.frame_set(1800)
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = r"G:\VDGP\ascii\experiments\edge\test_edge_mag.png"
bpy.ops.render.render(write_still=True)
print("RENDERED")
