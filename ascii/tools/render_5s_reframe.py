import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
zoom = bpy.data.images.load(r"G:\VDGP\ascii\experiments\reframe\zoom_src_58_63.mp4", check_existing=False)
zoom.source = "MOVIE"
for n in ng.nodes:
    if n.bl_idname == "GeometryNodeImageTexture":
        n.inputs[0].default_value = zoom
getattr(ins, ids["Source Frame Scale"]).value = 1.998
getattr(ins, ids["Source Frame Offset"]).value = -3475.52
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
sc.render.filepath = r"G:\VDGP\ascii\render\test5_reframe"
bpy.ops.render.render(animation=True)
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\experiments\reframe_work.blend")
print("DONE REFRAME")
