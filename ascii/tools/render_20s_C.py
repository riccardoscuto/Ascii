import bpy

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.render.fps = 30
sc.frame_start = 1440
sc.frame_end = 2039
sc.render.image_settings.media_type = "VIDEO"
sc.render.image_settings.file_format = "FFMPEG"
sc.render.ffmpeg.format = "MPEG4"
sc.render.ffmpeg.codec = "H264"
sc.render.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"
sc.render.ffmpeg.ffmpeg_preset = "GOOD"
sc.render.ffmpeg.audio_codec = "NONE"
sc.render.filepath = r"G:\VDGP\ascii\render\ASCII_C_96_20s_master"
bpy.ops.render.render(animation=True)
print("DONE 20s C")
