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
sc.render.filepath = r"G:\VDGP\ascii\render\test5_C"
bpy.ops.render.render(animation=True)
print("DONE C")
