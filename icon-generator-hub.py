import math
src = open("make_icons.py").read().split("TEAL   =")[0]
g = {}; exec(src, g)
squircle_bg, wobble, stroke, circle_pts, P, W, Image, ImageDraw = (g[k] for k in ["squircle_bg","wobble","stroke","circle_pts","P","W","Image","ImageDraw"])
SS = g["SS"]

LILAC = (235, 229, 244, 255)   # app background #ebe5f4
INK   = (36, 29, 68, 255)      # app ink #241d44
TEAL  = (23, 115, 104, 255)    # app accent, used for ticks/"complete"
WHITE = (255, 255, 255, 255)

def kr(d, x, y, s, col, w):
    def Q(px, py): return P(x + px * s, y + py * s)
    stroke(d, wobble([Q(-95, -95), Q(-95, 95)], 1, amp=1.4), w=w, fill=col)
    stroke(d, wobble([Q(-20, -55), Q(-90, 20), Q(-16, 95)], 2, amp=1.4), w=w, fill=col)
    stroke(d, wobble([Q(45, -30), Q(45, 95)], 3, amp=1.4), w=w, fill=col)
    stroke(d, wobble([Q(47, 12), Q(68, -22), Q(112, -30)], 4, amp=1.4), w=w, fill=col)

def tick(d, x, y, s, col, w):
    stroke(d, wobble([P(x - 40*s, y), P(x - 10*s, y + 32*s), P(x + 48*s, y - 40*s)], 9, amp=1.2), w=w, fill=col)

def icon_board(bg, ink, tickcol):
    img = squircle_bg(bg); d = ImageDraw.Draw(img)
    card = [P(232, 232), P(792, 232), P(792, 792), P(232, 792)]
    d.rounded_rectangle([P(232,232), P(792,792)], 40*SS, fill=WHITE)
    stroke(d, wobble(card, 11, amp=1.8, closed=True), w=int(W*0.55), fill=ink)
    for i, cy in enumerate([352, 512, 672]):
        stroke(d, wobble([P(300, cy), P(560, cy)], 20+i, amp=1.5), w=int(W*0.55), fill=ink)
        tick(d, 690, cy, 0.9, tickcol if i < 2 else ink, int(W*0.62))
    return img

def icon_spokes(bg, ink):
    img = squircle_bg(bg); d = ImageDraw.Draw(img)
    w = int(W*0.6)
    stroke(d, circle_pts(*P(512, 512), 150*SS, 31, amp=3), w=w, fill=ink)
    kr(d, 512, 512, 0.62, ink, int(W*0.55))
    for i, (nx, ny) in enumerate([(512, 200), (824, 512), (512, 824), (200, 512)]):
        dx, dy = nx - 512, ny - 512
        L = math.hypot(dx, dy)
        a0 = (512 + dx/L*160, 512 + dy/L*160); a1 = (nx - dx/L*62, ny - dy/L*62)
        stroke(d, wobble([P(*a0), P(*a1)], 40+i, amp=1.5), w=w, fill=ink)
        stroke(d, circle_pts(*P(nx, ny), 52*SS, 50+i, amp=1.5), w=w, fill=ink)
    return img

def icon_house(bg, ink):
    img = squircle_bg(bg); d = ImageDraw.Draw(img)
    w = int(W*0.8)
    stroke(d, wobble([P(212, 470), P(512, 220), P(812, 470)], 61, amp=2), w=w, fill=ink)
    stroke(d, wobble([P(290, 420), P(290, 790), P(734, 790), P(734, 420)], 62, amp=2), w=w, fill=ink)
    kr(d, 512, 600, 0.72, ink, int(W*0.72))
    return img

def icon_tiles(bg, ink, tickcol):
    img = squircle_bg(bg); d = ImageDraw.Draw(img)
    w = int(W*0.5)
    cells = [(232, 232), (532, 232), (232, 532), (532, 532)]
    for i, (x, y) in enumerate(cells):
        d.rounded_rectangle([P(x, y), P(x+260, y+260)], 34*SS, fill=WHITE)
        stroke(d, wobble([P(x,y), P(x+260,y), P(x+260,y+260), P(x,y+260)], 70+i, amp=1.6, closed=True), w=w, fill=ink)
    cx, cy = 362, 362
    stroke(d, circle_pts(*P(cx, cy), 78*SS, 80, amp=2), w=w, fill=ink); kr(d, cx, cy, 0.34, ink, int(W*0.42))
    tick(d, 662, 362, 1.1, tickcol, int(W*0.62))
    stroke(d, wobble([P(290, 730), P(350, 660), P(400, 700), P(470, 600)], 81, amp=1.5), w=w, fill=ink)
    for j, ly in enumerate([612, 662, 712]):
        stroke(d, wobble([P(590, ly), P(740, ly)], 90+j, amp=1.2), w=w, fill=ink)
    return img

out = {
 "A_board":  icon_board(LILAC, INK, TEAL),
 "B_spokes": icon_spokes(LILAC, INK),
 "C_house":  icon_house(LILAC, INK),
 "D_tiles":  icon_tiles(LILAC, INK, TEAL),
}
for n, im in out.items(): im.resize((1024,1024), Image.LANCZOS).save(f"hub_{n}.png")
sheet = Image.new("RGBA", (4*300+60, 380), (238,240,244,255)); dd = ImageDraw.Draw(sheet)
for i, n in enumerate(out):
    sheet.alpha_composite(Image.open(f"hub_{n}.png").resize((256,256), Image.LANCZOS), (30+i*300+22, 40))
    dd.text((30+i*300+130, 320), n.replace("_", "  "), fill=(40,40,60,255))
sheet.save("sheet_hub2.png"); print("ok")
