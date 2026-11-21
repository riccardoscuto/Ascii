import bpy

ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}


def math(name, op, a=None, b=None, c=None, clamp=False):
    n = ng.nodes.get(name)
    if n is None:
        n = ng.nodes.new("ShaderNodeMath")
        n.name = name
    n.operation = op
    n.use_clamp = clamp
    for idx, src in ((0, a), (1, b), (2, c)):
        if src is not None:
            ng.links.new(src, n.inputs[idx])
    return n


# epsilon on the gradient denominator
eps = math("Edge Sum Eps", "ADD", ng.nodes["Edge Sum"].outputs[0], None)
eps.inputs[1].default_value = 1e-5
v = ng.nodes["Edge V"]
for link in list(v.inputs[1].links):
    ng.links.remove(link)
ng.links.new(eps.outputs[0], v.inputs[1])

# clamp the final index to 0..12
lo = math("Edge Clamp Min", "MAXIMUM", ng.nodes["Edge Final"].outputs[0], None)
lo.inputs[1].default_value = 0.0
hi = math("Edge Clamp Max", "MINIMUM", lo.outputs[0], None)
hi.inputs[1].default_value = 12.0
inst = ng.nodes["Instance on Points"]
for link in list(inst.inputs["Instance Index"].links):
    ng.links.remove(link)
ng.links.new(hi.outputs[0], inst.inputs["Instance Index"])

# real ramp
ramp = " .,:;+HW@-|/\\"
getattr(ins, ids["Character Ramp"]).value = ramp
for i in ng.interface.items_tree:
    if getattr(i, "name", None) == "Character Ramp" and getattr(i, "in_out", None) == "INPUT":
        try:
            i.default_value = ramp
        except Exception:
            pass

getattr(ins, ids["Edge Strength"]).value = 0.0
getattr(ins, ids["Edge Threshold"]).value = 0.05
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\experiments\edge_fixed.blend")
print("FIXED", getattr(ins, ids["Character Ramp"]).value)
