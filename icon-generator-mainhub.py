import math
src = open("make_icons.py").read().split("TEAL   =")[0]
g = {}; exec(src, g)
squircle_bg, wobble, stroke, circle_pts, P, W, Image, ImageDraw = (g[k] for k in ["squircle_bg","wobble","stroke","circle_pts","P","W","Image","ImageDraw"])
SS = g["SS"]
exec(open("make_hub2.py").read().split("def icon_board")[0].split("WHITE = ")[1].split("\n",1)[1], g)  # kr(), tick()
kr, tick = g["kr"], g["tick"]

CREAM  = (250, 241, 226, 255)   # --bg #faf1e2
INK    = (42, 36, 32, 255)      # --ink #2a2420
INDIGO = (88, 104, 201, 255)    # FINANCE shelf
TEAL   = (31, 158, 147, 255)    # EVERYDAY APPS
LILAC  = (122, 95, 192, 255)    # MAC TOOLS
CORAL  = (217, 106, 69, 255)    # YOUR LINKS / accent
WHITE  = (255, 255, 255, 255)
SHELF  = [INDIGO, TEAL, LILAC, CORAL]

def tile_outline(d, x, y, s, seed, col, w):
    stroke(d, wobble([P(x,y), P(x+s,y), P(x+s,y+s), P(x,y+s)], seed, amp=1.6, closed=True), w=w, fill=col)

def glyph_phone(d, cx, cy, col, w):
    stroke(d, wobble([P(cx-42,cy-70), P(cx+42,cy-70), P(cx+42,cy+70), P(cx-42,cy+70)], 101, amp=1.2, closed=True), w=w, fill=col)
    stroke(d, wobble([P(cx-14,cy+48), P(cx+14,cy+48)], 102, amp=0.8), w=int(w*0.8), fill=col)

def glyph_laptop(d, cx, cy, col, w):
    stroke(d, wobble([P(cx-58,cy-48), P(cx+58,cy-48), P(cx+58,cy+30), P(cx-58,cy+30)], 111, amp=1.2, closed=True), w=w, fill=col)
    stroke(d, wobble([P(cx-80,cy+54), P(cx+80,cy+54)], 112, amp=1.0), w=w, fill=col)

def glyph_link(d, cx, cy, col, w):
    stroke(d, wobble([P(cx-50,cy+50), P(cx+50,cy-50)], 121, amp=1.2), w=w, fill=col)
    stroke(d, wobble([P(cx-10,cy-52), P(cx+52,cy-52), P(cx+52,cy+10)], 122, amp=1.0), w=w, fill=col)

def glyph_kr(d, cx, cy, col, w):
    stroke(d, circle_pts(*P(cx, cy), 88*SS, 131, amp=2), w=int(w*0.8), fill=col); kr(d, cx, cy, 0.34, col, int(w*0.7))

GLYPHS = [glyph_kr, glyph_phone, glyph_laptop, glyph_link]
CELLS = [(232, 232), (532, 232), (232, 532), (532, 532)]

# A. four shelves (planks) in the four colours, small tiles resting on each
def icon_shelves():
    img = squircle_bg(CREAM); d = ImageDraw.Draw(img)
    w = int(W*0.55)
    for i, y in enumerate([300, 445, 590, 735]):
        col = SHELF[i]
        stroke(d, wobble([P(232, y), P(792, y)], 140+i, amp=1.4), w=int(W*0.7), fill=col)
        n = [2, 3, 2, 3][i]
        xs = [330, 512, 694] if n == 3 else [400, 624]
        for j, x in enumerate(xs):
            tile_outline(d, x-44, y-112, 88, 150+i*3+j, INK, w)
    return img

# B. four ink-outlined white tiles, glyph in each shelf colour (sister of the Finance Hub icon)
def icon_tiles_ink():
    img = squircle_bg(CREAM); d = ImageDraw.Draw(img)
    w = int(W*0.5)
    for i, (x, y) in enumerate(CELLS):
        d.rounded_rectangle([P(x, y), P(x+260, y+260)], 34*SS, fill=WHITE)
        tile_outline(d, x, y, 260, 160+i, INK, w)
        GLYPHS[i](d, x+130, y+130, SHELF[i], int(W*0.55))
    return img

# C. four flat colour tiles with white glyphs ("really colourful")
def icon_tiles_colour():
    img = squircle_bg(CREAM); d = ImageDraw.Draw(img)
    for i, (x, y) in enumerate(CELLS):
        d.rounded_rectangle([P(x, y), P(x+260, y+260)], 40*SS, fill=SHELF[i])
        tile_outline(d, x, y, 260, 170+i, SHELF[i], int(W*0.5))   # softens the corners hand-drawn
        GLYPHS[i](d, x+130, y+130, WHITE, int(W*0.6))
    return img

# D. today's coral grid, but the four squares in the four shelf colours on cream
def icon_grid_colour():
    img = squircle_bg(CREAM); d = ImageDraw.Draw(img)
    for i, (x, y) in enumerate([(300, 300), (540, 300), (300, 540), (540, 540)]):
        tile_outline(d, x, y, 184, 180+i, SHELF[i], int(W*0.95))
    return img

out = {"A_shelves": icon_shelves(), "B_tiles_ink": icon_tiles_ink(), "C_tiles_colour": icon_tiles_colour(), "D_grid_colour": icon_grid_colour()}
for n, im in out.items(): im.resize((1024,1024), Image.LANCZOS).save(f"mainhub_{n}.png")
sheet = Image.new("RGBA", (5*300+60, 380), (238,240,244,255)); dd = ImageDraw.Draw(sheet)
names = ["current"] + list(out)
files = ["current_mainhub.png"] + [f"mainhub_{n}.png" for n in out]
for i, (n, f) in enumerate(zip(names, files)):
    sheet.alpha_composite(Image.open(f).convert("RGBA").resize((256,256), Image.LANCZOS), (30+i*300+22, 40))
    dd.text((30+i*300+120, 320), n.replace("_", " "), fill=(40,40,60,255))
sheet.save("sheet_mainhub.png"); print("ok")
