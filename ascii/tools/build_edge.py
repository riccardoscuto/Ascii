import bpy

ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
for name, default in (("Edge Strength", 0.8), ("Edge Threshold", 0.05)):
    if name not in ids:
        s = ng.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocketFloat")
        s.default_value = default
        if name == "Edge Strength":
            s.min_value, s.max_value = 0.0, 1.0
        else:
            s.min_value, s.max_value = 0.0, 0.3
    ids = {i.name: i.identifier for i in ng.interface.items_tree
           if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}

gi = ng.nodes["Group Input"]
base = ng.nodes["UV Offset"].outputs[0]
img = ng.nodes["Image Texture.001"].inputs["Image"].default_value
frame_src = ng.nodes["Image Texture.001"].inputs["Frame"].links[0].from_socket
du, dv = 1.0 / 96.0, 1.0 / 54.0
luma = (0.2126, 0.7152, 0.0722)


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


def mr(name, fmin=0.0, fmax=1.0):
    n = ng.nodes.get(name)
    if n is None:
        n = ng.nodes.new("ShaderNodeMapRange")
        n.name = name
        n.data_type = "FLOAT"
        n.clamp = True
    n.inputs[3].default_value = 0.0
    n.inputs[4].default_value = 1.0
    try:
        n.interpolation_type = "SMOOTHSTEP"
    except Exception:
        pass
    return n


hood = {}
for tag, vec in (("L", (-du, 0, 0)), ("R", (du, 0, 0)), ("D", (0, -dv, 0)), ("U", (0, dv, 0))):
    off = ng.nodes.get("Edge Off " + tag)
    if off is None:
        off = ng.nodes.new("ShaderNodeVectorMath")
        off.name = "Edge Off " + tag
        off.operation = "ADD"
        ng.links.new(base, off.inputs[0])
        off.inputs[1].default_value = vec
    tex = ng.nodes.get("Edge Tex " + tag)
    if tex is None:
        tex = ng.nodes.new("GeometryNodeImageTexture")
        tex.name = "Edge Tex " + tag
        tex.inputs[0].default_value = img
        ng.links.new(frame_src, tex.inputs[2])
        ng.links.new(off.outputs[0], tex.inputs[1])
    dot = ng.nodes.get("Edge Dot " + tag)
    if dot is None:
        dot = ng.nodes.new("ShaderNodeVectorMath")
        dot.name = "Edge Dot " + tag
        dot.operation = "DOT_PRODUCT"
        dot.inputs[1].default_value = luma
    ng.links.new(tex.outputs["Color"], dot.inputs[0])
    hood[tag] = dot.outputs[0]

gx = math("Edge GX", "SUBTRACT", hood["R"], hood["L"])
gy = math("Edge GY", "SUBTRACT", hood["U"], hood["D"])
agx = math("Edge Abs GX", "ABSOLUTE", gx.outputs[0])
agy = math("Edge Abs GY", "ABSOLUTE", gy.outputs[0])
sm = math("Edge Sum", "ADD", agx.outputs[0], agy.outputs[0])
eps = math("Edge Sum Eps", "ADD", sm.outputs[0], None)
eps.inputs[1].default_value = 1e-5
vs = math("Edge V", "DIVIDE", agx.outputs[0], eps.outputs[0])
vert = mr("Edge Vert", 0.62, 0.78)
ng.links.new(vs.outputs[0], vert.inputs[0])
hraw = mr("Edge Hraw", 0.22, 0.38)
ng.links.new(vs.outputs[0], hraw.inputs[0])
horiz = math("Edge Horiz", "SUBTRACT", None, None)
horiz.inputs[0].default_value = 1.0
ng.links.new(hraw.outputs[0], horiz.inputs[1])
diag = math("Edge Diag", "SUBTRACT", None, None, None, True)
diag.inputs[0].default_value = 1.0
ng.links.new(vert.outputs[0], diag.inputs[1])
diag2 = math("Edge Diag2", "SUBTRACT", diag.outputs[0], horiz.outputs[0], None, True)
sign = math("Edge Sign", "MULTIPLY", gx.outputs[0], gy.outputs[0])
pos = math("Edge Pos", "GREATER_THAN", sign.outputs[0], None)
pos.inputs[1].default_value = 0.0
neg = math("Edge Neg", "SUBTRACT", None, None)
neg.inputs[0].default_value = 1.0
ng.links.new(pos.outputs[0], neg.inputs[1])
dpos = math("Edge DPos", "MULTIPLY", diag2.outputs[0], pos.outputs[0])
dneg = math("Edge DNeg", "MULTIPLY", diag2.outputs[0], neg.outputs[0])
b0 = math("Edge Bin0", "MULTIPLY", horiz.outputs[0], None)
b0.inputs[1].default_value = 9.0
b1 = math("Edge Bin1", "MULTIPLY", dpos.outputs[0], None)
b1.inputs[1].default_value = 11.0
b2 = math("Edge Bin2", "MULTIPLY", vert.outputs[0], None)
b2.inputs[1].default_value = 10.0
b3 = math("Edge Bin3", "MULTIPLY", dneg.outputs[0], None)
b3.inputs[1].default_value = 12.0
bs1 = math("Edge BinS1", "ADD", b0.outputs[0], b1.outputs[0])
bs2 = math("Edge BinS2", "ADD", bs1.outputs[0], b2.outputs[0])
bin_ = math("Edge Bin", "ADD", bs2.outputs[0], b3.outputs[0])
mag2a = math("Edge Mag2A", "MULTIPLY", gx.outputs[0], gx.outputs[0])
mag2b = math("Edge Mag2B", "MULTIPLY", gy.outputs[0], gy.outputs[0])
mag2 = math("Edge Mag2", "ADD", mag2a.outputs[0], mag2b.outputs[0])
mag = math("Edge Mag", "SQRT", mag2.outputs[0])
mask = mr("Edge Mask")
ng.links.new(mag.outputs[0], mask.inputs[0])
ng.links.new(gi.outputs["Edge Threshold"], mask.inputs[1])
hi = math("Edge Hi", "ADD", gi.outputs["Edge Threshold"], None)
hi.inputs[1].default_value = 0.07
ng.links.new(hi.outputs[0], mask.inputs[2])
strength = math("Edge Strength Mul", "MULTIPLY", mask.outputs[0], gi.outputs["Edge Strength"], clamp=True)
inv = math("Edge Inv", "SUBTRACT", None, None)
inv.inputs[0].default_value = 1.0
ng.links.new(strength.outputs[0], inv.inputs[1])
lum = ng.nodes["Map Range.001"]
for link in list(lum.inputs[4].links):
    ng.links.remove(link)
lum.inputs[4].default_value = 8.0
la = math("Edge Lum A", "MULTIPLY", lum.outputs[0], inv.outputs[0])
eb = math("Edge Mix B", "MULTIPLY", bin_.outputs[0], strength.outputs[0])
final = math("Edge Final", "ADD", la.outputs[0], eb.outputs[0])
lo = math("Edge Clamp Min", "MAXIMUM", final.outputs[0], None)
lo.inputs[1].default_value = 0.0
hi2 = math("Edge Clamp Max", "MINIMUM", lo.outputs[0], None)
hi2.inputs[1].default_value = 12.0
inst = ng.nodes["Instance on Points"]
for link in list(inst.inputs["Instance Index"].links):
    ng.links.remove(link)
ng.links.new(hi2.outputs[0], inst.inputs["Instance Index"])

ramp = " .,:;+HW@-|/\\"
ng.nodes["String"].string = ramp
getattr(mod.properties.inputs, ids["Character Ramp"]).value = ramp
for i in ng.interface.items_tree:
    if getattr(i, "name", None) == "Character Ramp" and getattr(i, "in_out", None) == "INPUT":
        try:
            i.default_value = ramp
        except Exception:
            pass

grid = ng.nodes["ASCII Grid"]
curves = ng.nodes["String to Curves"]
grid.inputs["Vertices X"].default_value = 96
grid.inputs["Vertices Y"].default_value = 54
curves.inputs["Size"].default_value = 0.0166
du4, dv4 = 1.0 / (96 * 4), 1.0 / (54 * 4)
for name, vec in {"Cell Sample A Offset": (-du4, -dv4, 0.0), "Cell Sample B Offset": (du4, -dv4, 0.0),
                  "Cell Sample C Offset": (-du4, dv4, 0.0), "Cell Sample D Offset": (du4, dv4, 0.0)}.items():
    ng.nodes[name].inputs[1].default_value = vec

getattr(mod.properties.inputs, ids["Edge Strength"]).value = 0.0
getattr(mod.properties.inputs, ids["Edge Threshold"]).value = 0.05
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\experiments\edge_fixed2.blend")
print("BUILT", ramp, len(ramp))
