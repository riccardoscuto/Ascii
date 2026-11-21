import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
getattr(ins, ids["Edge Strength"]).value = 0.8

edge_img = bpy.data.images.load(r"G:\VDGP\ascii\experiments\edge_seq\edge_seq.mp4", check_existing=False)
edge_img.source = "MOVIE"
try:
    edge_img.colorspace_settings.name = "Non-Color"
except Exception:
    pass

tex = ng.nodes["Edge Map"]
tex.inputs[0].default_value = edge_img
for link in list(tex.inputs["Frame"].links):
    ng.links.remove(link)
sc_time = ng.nodes["Scene Time"]
sub = ng.nodes.get("Edge Seq Frame")
if sub is None:
    sub = ng.nodes.new("ShaderNodeMath")
    sub.name = "Edge Seq Frame"
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = 1739.0
ng.links.new(sc_time.outputs["Frame"], sub.inputs[0])
ng.links.new(sub.outputs[0], tex.inputs["Frame"])

grid = ng.nodes["ASCII Grid"]
curves = ng.nodes["String to Curves"]
grid.inputs["Vertices X"].default_value = 96
grid.inputs["Vertices Y"].default_value = 54
curves.inputs["Size"].default_value = 0.0166
du, dv = 1.0 / (96 * 4), 1.0 / (54 * 4)
for name, vec in {"Cell Sample A Offset": (-du, -dv, 0.0), "Cell Sample B Offset": (du, -dv, 0.0),
                  "Cell Sample C Offset": (-du, dv, 0.0), "Cell Sample D Offset": (du, dv, 0.0)}.items():
    ng.nodes[name].inputs[1].default_value = vec

sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.render.fps = 30
sc.frame_start = 1740
sc.frame_end = 1889
sc.render.image_settings.media_type = "VIDEO"
sc.render.image_settings.file_format = "FFMPEG"
sc.render.ffmpeg.format = "MPEG4"
sc.render.ffmpeg.codec = "H264"
sc.render.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"
sc.render.ffmpeg.ffmpeg_preset = "GOOD"
sc.render.ffmpeg.audio_codec = "NONE"
sc.render.filepath = r"G:\VDGP\ascii\render\test5_D"
bpy.ops.render.render(animation=True)
print("DONE D")
