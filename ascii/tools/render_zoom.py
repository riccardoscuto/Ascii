import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
grid = ng.nodes["ASCII Grid"]
curves = ng.nodes["String to Curves"]
grid.inputs["Vertices X"].default_value = 96
grid.inputs["Vertices Y"].default_value = 54
curves.inputs["Size"].default_value = 0.0166
du, dv = 1.0 / (96 * 4), 1.0 / (54 * 4)
for name, vec in {"Cell Sample A Offset": (-du, -dv, 0.0), "Cell Sample B Offset": (du, -dv, 0.0),
                  "Cell Sample C Offset": (-du, dv, 0.0), "Cell Sample D Offset": (du, dv, 0.0)}.items():
    ng.nodes[name].inputs[1].default_value = vec

zoom = bpy.data.images.load(r"G:\VDGP\ascii\experiments\edge\zoom60.png", check_existing=False)
for n in ng.nodes:
    if n.bl_idname == "GeometryNodeImageTexture":
        n.inputs[0].default_value = zoom

sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.frame_set(1800)
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = r"G:\VDGP\ascii\experiments\edge\zoom_1800.png"
bpy.ops.render.render(write_still=True)
print("RENDERED")
