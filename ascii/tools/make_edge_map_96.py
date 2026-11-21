from pathlib import Path

from PIL import Image, ImageFilter

SRC = Path(r"G:\VDGP\ascii\experiments\source_scan\v_60.png")
OUT = Path(r"G:\VDGP\ascii\experiments\edge\edge60_96.png")
PREVIEW = Path(r"G:\VDGP\ascii\experiments\edge\edge60_96_preview.png")
W, H = 96, 54

im = Image.open(SRC).convert("L").resize((W, H), Image.Resampling.BOX)
kx = im.filter(ImageFilter.Kernel((3, 3), [-1, 0, 1, -2, 0, 2, -1, 0, 1], scale=1, offset=128))
ky = im.filter(ImageFilter.Kernel((3, 3), [-1, -2, -1, 0, 0, 0, 1, 2, 1], scale=1, offset=128))
px, py = kx.load(), ky.load()
rows = []
mags = []
for y in range(H):
    for x in range(W):
        gx = px[x, y] - 128
        gy = py[x, y] - 128
        mag = (gx * gx + gy * gy) ** 0.5
        mags.append(mag)
        rows.append((x, y, gx, gy, mag))

vals = sorted(m for m in mags if m > 0)
p50 = vals[int(0.50 * len(vals))]
p75 = vals[int(0.75 * len(vals))]
p90 = vals[int(0.90 * len(vals))]
p95 = vals[int(0.95 * len(vals))]
p99 = vals[min(len(vals) - 1, int(0.99 * len(vals)))]
print("percentiles", p50, p75, p90, p95, p99)
t0 = max(6.0, p90)
t1 = max(t0 + 6.0, p99 * 0.85)


def smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


out = Image.new("RGB", (W, H), (0, 0, 0))
op = out.load()
prev = Image.new("RGB", (W, H), (0, 0, 0))
pp = prev.load()
for x, y, gx, gy, mag in rows:
    e = smoothstep(mag, t0, t1)
    agx, agy = abs(gx), abs(gy)
    v = agx / (agx + agy + 1e-6)
    if v > 0.70:
        b = 1
    elif v < 0.30:
        b = 0
    else:
        b = 2 if gx * gy > 0 else 3
    r = int(255 * e)
    g = int(255 * b / 3)
    op[x, y] = (r, g, 0)
    pp[x, y] = (r, g, 255 if b == 1 else 0)

out.save(OUT)
prev.save(PREVIEW)
print("saved", OUT)
