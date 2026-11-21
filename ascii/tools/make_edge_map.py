from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC = Path(r"G:\VDGP\ascii\experiments\source_scan\v_60.png")
OUT = Path(r"G:\VDGP\ascii\experiments\edge\edge60.png")
PREVIEW = Path(r"G:\VDGP\ascii\experiments\edge\edge60_preview.png")
W, H = 480, 270

im = Image.open(SRC).convert("L").resize((W, H), Image.Resampling.LANCZOS)
kx = im.filter(ImageFilter.Kernel((3, 3), [-1, 0, 1, -2, 0, 2, -1, 0, 1], scale=1, offset=128))
ky = im.filter(ImageFilter.Kernel((3, 3), [-1, -2, -1, 0, 0, 0, 1, 2, 1], scale=1, offset=128))
px, py = kx.load(), ky.load()
mags = []
rows = []
for y in range(H):
    for x in range(W):
        gx = px[x, y] - 128
        gy = py[x, y] - 128
        mag = (gx * gx + gy * gy) ** 0.5
        mags.append(mag)
        rows.append((x, y, gx, gy, mag))

mags = sorted(m for m in mags if m > 0)
p99 = mags[min(len(mags) - 1, int(len(mags) * 0.99))] if mags else 1.0
scale = max(0.02, p99 * 0.8)
print("p99", p99, "scale", scale)

out = Image.new("RGB", (W, H), (0, 0, 0))
op = out.load()
prev = Image.new("RGB", (W, H), (0, 0, 0))
pp = prev.load()
for x, y, gx, gy, mag in rows:
    r = int(255 * min(1.0, mag / scale))
    agx, agy = abs(gx), abs(gy)
    v = agx / (agx + agy + 1e-6)
    if v > 0.70:
        b = 1
    elif v < 0.30:
        b = 0
    else:
        b = 2 if gx * gy > 0 else 3
    g = int(255 * b / 3)
    op[x, y] = (r, g, 0)
    pp[x, y] = (r, g, 255 if b == 1 else 0)

out.save(OUT)
prev.save(PREVIEW)
print("saved", OUT)
