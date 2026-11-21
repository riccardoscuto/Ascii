import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
for tag, vec in (("L", (-0.1, 0, 0)), ("R", (0.1, 0, 0)), ("D", (0, -0.1, 0)), ("U", (0, 0.1, 0))):
    ng.nodes["Edge Off " + tag].inputs[1].default_value = vec

inst = ng.nodes["Instance on Points"]
mag = ng.nodes["Edge Mag"]
dbg = ng.nodes.get("Debug Mag Index2")
if dbg is None:
    dbg = ng.nodes.new("ShaderNodeMapRange")
    dbg.name = "Debug Mag Index2"
    dbg.data_type = "FLOAT"
    dbg.clamp = True
    dbg.inputs[1].default_value = 0.0
    dbg.inputs[2].default_value = 0.3
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
sc.render.filepath = r"G:\VDGP\ascii\experiments\edge\test_edge_mag10.png"
bpy.ops.render.render(write_still=True)
print("RENDERED")
