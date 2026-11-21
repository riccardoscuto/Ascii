import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}

ramp = " .,:;+HW@-|/\\"
getattr(ins, ids["Character Ramp"]).value = ramp
for i in ng.interface.items_tree:
    if getattr(i, "name", None) == "Character Ramp" and getattr(i, "in_out", None) == "INPUT":
        try:
            i.default_value = ramp
        except Exception:
            pass

sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
ims = sc.render.image_settings
ims.media_type = "IMAGE"
ims.file_format = "PNG"
sc.frame_set(1800)

outdir = r"G:\VDGP\ascii\experiments\edge"
for tag, strength, threshold in (("s050_t050b", 0.5, 0.05), ("s080_t050b", 0.8, 0.05),
                                 ("s100_t050b", 1.0, 0.05), ("s100_t020b", 1.0, 0.02)):
    getattr(ins, ids["Edge Strength"]).value = strength
    getattr(ins, ids["Edge Threshold"]).value = threshold
    sc.render.filepath = rf"{outdir}\{tag}.png"
    bpy.ops.render.render(write_still=True)
    print("WROTE", tag)

getattr(ins, ids["Edge Strength"]).value = 0.8
getattr(ins, ids["Edge Threshold"]).value = 0.05
sc.render.filepath = r"G:\VDGP\ascii\render\ascii_"
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\experiments\edge_work.blend")
print("SAVED")
