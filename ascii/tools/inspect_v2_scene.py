import bpy

sc = bpy.context.scene
cam = sc.camera
print("SCENE", sc.render.resolution_x, sc.render.resolution_y, sc.render.fps, sc.frame_start, sc.frame_end)
print("CAMERA", cam.name if cam else None, cam.data.type if cam else None,
      getattr(cam.data, "ortho_scale", None) if cam else None,
      tuple(round(v, 4) for v in cam.location) if cam else None,
      tuple(round(v, 4) for v in cam.rotation_euler) if cam else None)
ng = bpy.data.node_groups["Geometry Nodes.001"]
grid = ng.nodes["ASCII Grid"]
print("GRID", grid.inputs["Size X"].default_value, grid.inputs["Size Y"].default_value,
      grid.inputs["Vertices X"].default_value, grid.inputs["Vertices Y"].default_value)
for o in bpy.data.objects:
    print("OBJ", o.name, o.type, tuple(round(v, 3) for v in o.scale))
print("ENGINE", sc.render.engine, sc.eevee.taa_render_samples)
