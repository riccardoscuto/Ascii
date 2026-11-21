import bpy

ng = bpy.data.node_groups["Geometry Nodes.001"]
for name in ("UV Scale", "UV Offset", "Position"):
    n = ng.nodes.get(name)
    print("NODE", name, n.bl_idname if n else None, getattr(n, "operation", None))
    if n:
        for i in n.inputs:
            if i.is_linked:
                print("  ", i.name, "<-", i.links[0].from_node.name)
            elif hasattr(i, "default_value"):
                print("  ", i.name, "=", i.default_value)
