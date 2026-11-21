import bpy

ng = bpy.data.node_groups["Geometry Nodes.001"]
for tag in ("L", "R", "D", "U"):
    off = ng.nodes.get("Edge Off " + tag)
    tex = ng.nodes.get("Edge Tex " + tag)
    dot = ng.nodes.get("Edge Dot " + tag)
    print("OFF", tag, list(off.inputs[0].links[0].from_node.name) if off.inputs[0].is_linked else None,
          list(off.inputs[1].default_value))
    print("TEX", tag,
          tex.inputs["Vector"].links[0].from_node.name if tex.inputs["Vector"].is_linked else None,
          tex.inputs["Frame"].links[0].from_node.name if tex.inputs["Frame"].is_linked else None,
          tex.inputs["Image"].default_value.name if tex.inputs["Image"].default_value else None)
    print("DOT", tag, dot.inputs[0].links[0].from_node.name if dot.inputs[0].is_linked else None,
          tuple(dot.inputs[1].default_value))
for name in ("Edge GX", "Edge GY", "Edge Mag", "Edge Sum", "Edge V", "Debug Mag Index"):
    n = ng.nodes.get(name)
    vals = []
    for i in n.inputs[:5]:
        if i.is_linked:
            vals.append(f"{i.name}<-{i.links[0].from_node.name}")
        elif hasattr(i, "default_value"):
            v = i.default_value
            vals.append(f"{i.name}={round(v, 5) if isinstance(v, float) else v}")
    print("NODE", name, vals)
