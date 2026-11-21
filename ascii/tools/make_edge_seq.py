from pathlib import Path

from PIL import Image, ImageFilter

SRC = Path(r"G:\VDGP\ascii\experiments\edge_seq_src")
OUT = Path(r"G:\VDGP\ascii\experiments\edge_seq")
OUT.mkdir(exist_ok=True)
W, H = 96, 54
T0, T1 = 60.0, 110.0


def smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


for i, p in enumerate(sorted(SRC.glob("f_*.png")), 1):
    im = Image.open(p).convert("L").resize((W, H), Image.Resampling.BOX)
    kx = im.filter(ImageFilter.Kernel((3, 3), [-1, 0, 1, -2, 0, 2, -1, 0, 1], scale=1, offset=128))
    ky = im.filter(ImageFilter.Kernel((3, 3), [-1, -2, -1, 0, 0, 0, 1, 2, 1], scale=1, offset=128))
    px, py = kx.load(), ky.load()
    out = Image.new("RGB", (W, H), (0, 0, 0))
    op = out.load()
    for y in range(H):
        for x in range(W):
            gx = px[x, y] - 128
            gy = py[x, y] - 128
            mag = (gx * gx + gy * gy) ** 0.5
            e = smoothstep(mag, T0, T1)
            agx, agy = abs(gx), abs(gy)
            v = agx / (agx + agy + 1e-6)
            if v > 0.70:
                b = 1
            elif v < 0.30:
                b = 0
            else:
                b = 2 if gx * gy > 0 else 3
            op[x, y] = (int(255 * e), int(255 * b / 3), 0)
    out.save(OUT / f"edge_{i:04d}.png")
print("maps", len(list(OUT.glob('edge_*.png'))))
