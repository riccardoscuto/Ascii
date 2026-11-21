import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
getattr(ins, ids["Edge Strength"]).value = 0.8
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
tex = ng.nodes["Edge Map"]
for f in (1560, 1755, 1800, 1965, 2025):
    img = bpy.data.images.load(rf"G:\VDGP\ascii\experiments\edge\edge_{f}_96.png", check_existing=False)
    try:
        img.colorspace_settings.name = "Non-Color"
    except Exception:
        pass
    tex.inputs[0].default_value = img
    sc.frame_set(f)
    sc.render.filepath = rf"G:\VDGP\ascii\experiments\edge\D_{f}.png"
    bpy.ops.render.render(write_still=True)
    print("WROTE", f)
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\experiments\edge_frames_work.blend")
print("SAVED")
