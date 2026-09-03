import math, random
from PIL import Image, ImageDraw, ImageFilter

SS = 4                      # supersample
N  = 1024 * SS
W  = 52 * SS                # stroke width (~52px at 1024)

def squircle_bg(color, shadow=True):
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    m = 100 * SS            # Apple template margin (824 content in 1024)
    r = 184 * SS
    if shadow:
        sh = Image.new("RGBA", (N, N), (0, 0, 0, 0))
        d = ImageDraw.Draw(sh)
        d.rounded_rectangle([m, m + 10*SS, N - m, N - m + 10*SS], r, fill=(20, 10, 40, 70))
        sh = sh.filter(ImageFilter.GaussianBlur(14 * SS))
        img.alpha_composite(sh)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([m, m, N - m, N - m], r, fill=color)
    return img

def wobble(points, seed, amp=3.2, step=5, closed=False):
    """Densify a polyline and push it around with smooth low-frequency noise."""
    rnd = random.Random(seed)
    ph = [rnd.random() * 6.28 for _ in range(4)]
    fr = [rnd.uniform(0.006, 0.02) for _ in range(4)]
    pts = list(points) + ([points[0]] if closed else [])
    out, t = [], 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(L / (step * SS)))
        nx, ny = (-(y1 - y0) / L, (x1 - x0) / L)
        for i in range(n):
            u = i / n
            x, y = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
            t += L / n
            off = sum(math.sin(t * fr[k] + ph[k]) for k in range(4)) / 4 * amp * SS
            out.append((x + nx * off, y + ny * off))
    out.append(pts[-1])
    return out

def stroke(d, pts, w=W, fill=(255, 255, 255, 255)):
    """Stamp round dabs along the path: smooth, no joint artifacts."""
    r = w / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L / (1.5 * SS)))
        for i in range(n + 1):
            u = i / n
            x, y = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
            d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

def circle_pts(cx, cy, r, seed, n=90, amp=4):
    rnd = random.Random(seed)
    ph = [rnd.random() * 6.28 for _ in range(3)]
    out = []
    for i in range(n + 1):
        a = i / n * 2 * math.pi
        rr = r + sum(math.sin(a * (k + 2) + ph[k]) for k in range(3)) / 3 * amp * SS
        out.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    # blend the seam
    out[-1] = out[0]
    return out

def P(x, y):  # 1024-space -> canvas
    return (x * SS, y * SS)

# ---------- 1. rising line chart with axes (dashboard) ----------
def icon_chart(color):
    img = squircle_bg(color)
    d = ImageDraw.Draw(img)
    stroke(d, wobble([P(250, 250), P(250, 770), P(780, 770)], 11))            # axes
    line = wobble([P(305, 660), P(430, 540), P(520, 600), P(740, 380)], 12)
    stroke(d, line)
    stroke(d, wobble([P(640, 372), P(748, 372), P(748, 480)], 13))            # arrow head
    return img

# ---------- 2. coin with hand-lettered "kr" (Swedish krona) ----------
def icon_kr(color):
    img = squircle_bg(color)
    d = ImageDraw.Draw(img)
    stroke(d, circle_pts(*P(512, 512), 300 * SS, 21, amp=5), w=int(W * 0.95))
    # k
    stroke(d, wobble([P(392, 380), P(392, 640)], 22, amp=2))
    stroke(d, wobble([P(492, 425), P(398, 530), P(500, 640)], 23, amp=2))
    # r
    stroke(d, wobble([P(578, 462), P(578, 640)], 24, amp=2))
    stroke(d, wobble([P(580, 520), P(605, 478), P(660, 468)], 25, amp=2))
    return img

# ---------- 3. stack of coins + rising arrow ----------
def icon_stack(color):
    img = squircle_bg(color)
    d = ImageDraw.Draw(img)
    def coin(cy, seed):
        pts = wobble([P(270, cy), P(300, cy - 34), P(360, cy - 52), P(450, cy - 56),
                      P(540, cy - 52), P(600, cy - 34), P(630, cy), P(600, cy + 34),
                      P(540, cy + 52), P(450, cy + 56), P(360, cy + 52), P(300, cy + 34)],
                     seed, amp=2.2, closed=True)
        stroke(d, pts, w=int(W * 0.85))
    for i, cy in enumerate([700, 600, 500]):
        stroke(d, wobble([P(272, cy), P(272, cy - 100)], 31 + i, amp=1.5), w=int(W*0.85))
        stroke(d, wobble([P(628, cy), P(628, cy - 100)], 41 + i, amp=1.5), w=int(W*0.85))
    for i, cy in enumerate([700, 600, 500, 400]):
        coin(cy, 51 + i)
    # arrow up-right
    stroke(d, wobble([P(660, 470), P(800, 300)], 61, amp=2))
    stroke(d, wobble([P(720, 292), P(806, 292), P(806, 378)], 62, amp=2))
    return img

TEAL   = (23, 115, 104, 255)     # dashboard accent #177368
VIOLET = (98, 72, 168, 255)      # calm deep violet (his finance-lilac, darkened)
NAVY   = (36, 29, 68, 255)       # ink #241d44

variants = {
    "chart_teal":   icon_chart(TEAL),
    "kr_violet":    icon_kr(VIOLET),
    "stack_navy":   icon_stack(NAVY),
    "kr_teal":      icon_kr(TEAL),
    "chart_violet": icon_chart(VIOLET),
}
for name, im in variants.items():
    im.resize((1024, 1024), Image.LANCZOS).save(f"{name}.png")

# preview sheet on a light Dock-ish background
sheet = Image.new("RGBA", (5 * 300 + 60, 380), (238, 240, 244, 255))
dd = ImageDraw.Draw(sheet)
for i, name in enumerate(variants):
    small = Image.open(f"{name}.png").resize((256, 256), Image.LANCZOS)
    sheet.alpha_composite(small, (30 + i * 300 + 22, 40))
    dd.text((30 + i * 300 + 150 - 4 * len(name), 320), f"{i+1}  {name}", fill=(40, 40, 60, 255))
sheet.save("sheet.png")
print("ok")
