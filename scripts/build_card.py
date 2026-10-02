"""Render the pixel profile card: data/stats.json + config/profile.json -> assets/card-{light,dark}.gif.

Draws on a small 400px canvas with an unantialiased pixel font, then upscales
with nearest-neighbour so every logical pixel stays a crisp square. The cat
(scripts/cat.py) is composited per frame to animate the GIF.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import cat

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets" / "fonts" / "PressStart2P-Regular.ttf"
W, SCALE, M, CAT_PX = 400, 3, 12, 3  # logical width, upscale factor, margin, cat pixel size

# name -> (BG, PANEL, FG, DIM, GREEN, PINK, CYAN, YELLOW, ORANGE, cat fur, cat outline)
THEMES = {
    "light": ((226, 234, 255), (196, 208, 240), (30, 28, 60), (96, 102, 148),
              (30, 150, 70), (225, 50, 130), (0, 125, 190), (214, 140, 0), (230, 110, 30),
              (255, 255, 255), (112, 118, 165)),
    "dark": ((20, 16, 31), (30, 25, 48), (232, 230, 240), (125, 122, 153),
             (124, 255, 107), (255, 95, 162), (94, 231, 255), (255, 216, 74), (255, 150, 60),
             (250, 250, 255), (176, 178, 208)),
}


def set_theme(name):
    """Swap the module-level palette (render() and helpers read these globals at call time)."""
    global BG, PANEL, FG, DIM, GREEN, PINK, CYAN, YELLOW, ORANGE, LANG_COLORS
    BG, PANEL, FG, DIM, GREEN, PINK, CYAN, YELLOW, ORANGE, cat.W, cat.G = THEMES[name]
    LANG_COLORS = [CYAN, GREEN, YELLOW, PINK, ORANGE]


set_theme("light")


STEP = 50  # ms per GIF frame; every cat pose duration is a multiple of it
BANNER_W, BANNER_H, HORIZON = W - 2 * M, 48, 30
# fixed night-scene palette, same in both themes so the banner reads as a screen
SKY = [(12, 9, 30), (22, 12, 48), (38, 14, 66), (58, 16, 80)]
SUN = [(255, 216, 74), (255, 170, 60), (255, 120, 90), (255, 80, 150)]  # top -> bottom
GRID_H, GRID_V, GROUND = (255, 60, 160), (150, 70, 255), (18, 8, 36)
STARS = [((i * 53 + 11) % BANNER_W, (i * 29 + 5) % (HORIZON - 6), i) for i in range(30)]


def banner(t):
    """Synthwave strip: striped sun, twinkling stars, grid rushing at the viewer, a comet per loop.
    Own canvas, so nothing it draws can spill onto the card."""
    img = Image.new("RGB", (BANNER_W, BANNER_H))
    d = ImageDraw.Draw(img)
    cx = BANNER_W // 2

    def px(x, y, c):
        d.point((x, y), fill=c)

    def hline(x1, x2, y, c):
        d.line([(x1, y), (x2, y)], fill=c)

    for y in range(HORIZON):  # sky bands, darker at the top
        hline(0, BANNER_W, y, SKY[min(len(SKY) - 1, y * len(SKY) // HORIZON)])
    for sx, sy, i in STARS:  # period 4 divides 12 steps/loop -> seamless twinkle
        phase = (i + int(t * 12)) % 4
        if phase:
            px(sx, sy, (255, 255, 255) if phase == 1 else (140, 150, 220))
    r, cut = 20, int(t * 4)  # sun; the dark stripes crawl down 4 steps per loop
    for dy in range(r):
        if dy < 12 and (dy + cut) % 4 == 3:
            continue
        half = int(math.sqrt(r * r - dy * dy))
        hline(cx - half, cx + half, HORIZON - 1 - dy, SUN[min(3, (r - 1 - dy) * 4 // r)])
    for y in range(HORIZON, BANNER_H):
        hline(0, BANNER_W, y, GROUND)
    for i in range(-8, 9):  # vertical lines fan out; spread start keeps the horizon from clumping
        d.line([(cx + i * 7, HORIZON + 1), (cx + i * 44, BANNER_H - 1)], fill=GRID_V)
    hline(0, BANNER_W, HORIZON, GRID_H)
    for k in range(6):  # horizontal lines accelerate toward the viewer (z^2 spacing)
        z = (k + t) / 6
        y = HORIZON + 1 + round((BANNER_H - HORIZON - 2) * z * z)
        if y > HORIZON + 1 and y < BANNER_H - 1:
            hline(0, BANNER_W, y, GRID_H)
    hx = round(-12 + (BANNER_W + 24) * t)  # comet: enters left, leaves right, once per loop
    hy = 4 + hx // 18
    for n in range(12):
        c = 255 - n * 20
        px(hx - n * 2, hy - n // 3, (c, c, 255))
    return img


def bar_fill(value, cap):
    """Log-scaled 0..1 so early progress is visible; saturates at cap."""
    return min(1.0, math.log1p(max(value, 0)) / math.log1p(cap))


ICON_DIR = ROOT / "assets" / "icons"


def slug(label):
    """Icon file name for a tool label: 'VS Code' -> 'vscode'."""
    return "".join(c for c in label.lower() if c.isalnum())


def ascii_up(s):
    """Press Start 2P only covers ASCII; anything else becomes '?'."""
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in s).upper()


class Pen:
    def __init__(self, h):
        self.img = Image.new("RGB", (W, h), BG)
        self.d = ImageDraw.Draw(self.img)
        self.d.fontmode = "1"  # no antialiasing -> hard pixel edges
        self._fonts = {}

    def font(self, size):
        if size not in self._fonts:
            self._fonts[size] = ImageFont.truetype(str(FONT), size)
        return self._fonts[size]

    def text(self, x, y, s, size=8, fill=FG, anchor="l"):
        s = ascii_up(s)
        if anchor == "r":
            x -= len(s) * size
        self.d.text((x, y), s, font=self.font(size), fill=fill)
        return len(s) * size

    def rect(self, x, y, w, h, fill):
        self.d.rectangle([x, y, x + w - 1, y + h - 1], fill=fill)

    def frame(self, x, y, w, h, color, t=1):
        for i in range(t):
            self.d.rectangle([x + i, y + i, x + w - 1 - i, y + h - 1 - i], outline=color)

    def slot(self, x, y, n, color):
        """Bookmark ribbon with a V-notched tail; ends flush with the right margin."""
        x, y = x + 2, y - 4
        self.rect(x, y, 22, 18, color)
        for k in range(1, 5):
            self.rect(x + 11 - k, y + 13 + k, 2 * k, 1, BG)
        self.text(x + 3, y + 3, f"{n:02d}", 8, BG)

    def tile(self, cx, y, label, color):
        """Framed 16x16 pixel icon with its label centred underneath. No icon file
        for this label -> its first letter is drawn instead."""
        self.rect(cx - 12, y, 24, 24, PANEL)
        self.frame(cx - 12, y, 24, 24, DIM)
        path = ICON_DIR / f"{slug(label)}.png"
        if path.exists():
            self.img.paste(color, (cx - 8, y + 4), Image.open(path))
        else:
            self.text(cx - 8, y + 8, label[:1], 8, color)
        s = ascii_up(truncate(label, 7))
        self.text(cx - len(s) * 4, y + 28, s, 8, FG)

    def rule(self, y):
        for x in range(M, W - M, 4):
            self.rect(x, y, 2, 1, DIM)

    def blocks(self, x, y, frac, n, color, bw=6, gap=2, h=8):
        on = round(frac * n)
        for i in range(n):
            self.rect(x + i * (bw + gap), y, bw, h, color if i < on else PANEL)


def truncate(s, n):
    return s if len(s) <= n else s[: n - 1] + "~"


def lang_shares(languages, top=3):
    """[(name, fraction)] for the biggest languages (>=1%), remainder lumped as Other."""
    total = sum(sz for _, sz in languages) or 1
    shown = [(n, sz / total) for n, sz in languages[:top] if sz / total >= 0.01]
    rest = 1 - sum(f for _, f in shown)
    return shown + ([("Other", rest)] if shown and rest >= 0.01 else [])


def lang_color(name):
    """Stable colour per language so Python looks the same in every row."""
    known = {"Python": CYAN, "C#": GREEN, "JavaScript": YELLOW, "C++": PINK, "MATLAB": ORANGE, "Other": DIM}
    return known.get(name, LANG_COLORS[sum(map(ord, name)) % len(LANG_COLORS)])


def render(stats, cfg):
    p = Pen(1200)  # scratch height; the image is cropped to the drawn content below
    y = 10
    p.text(M, y, "FIG_000 / PLAYER PROFILE", 8, DIM)
    p.text(W - M, y, "@" + cfg["login"], 8, DIM, anchor="r")
    y += 14
    p.rule(y)

    # header: name + role + cat
    y += 10
    p.text(M, y, cfg["name"], 32, GREEN)
    y += 42
    p.text(M, y, cfg["role"], 8, FG)
    y += 14
    p.text(M, y, cfg["school"], 8, DIM)
    y += 20
    p.rule(y)

    # animated banner (drawn per frame below) + stat bars
    y += 10
    p.text(M, y, "FIG_001 / STATS", 8, CYAN)
    y += 16
    banner_y = y
    p.frame(M - 1, y - 1, BANNER_W + 2, BANNER_H + 2, DIM)
    y += BANNER_H + 12
    caps = cfg["caps"]
    rows = [
        ("STARS", stats["stars"], caps["stars"], YELLOW),
        ("COMMITS", stats["commits"], caps["commits"], GREEN),
        ("PRS", stats["prs"], caps["prs"], CYAN),
        ("FOLLOWERS", stats["followers"], caps["followers"], PINK),
    ]
    for label, val, cap, color in rows:
        p.text(M, y, label, 8, FG)
        p.blocks(M + 96, y, bar_fill(val, cap), 20, color)
        p.text(W - M, y, str(val), 8, color, anchor="r")
        y += 16
    p.text(M, y, "COMMITS + PRS = LAST 365 DAYS", 8, DIM)
    y += 20
    p.rule(y)

    # top repos
    y += 10
    p.text(M, y, "FIG_002 / TOP REPOS", 8, CYAN)
    y += 16
    for i, r in enumerate(stats["top_repos"][:6]):
        shares = lang_shares(r["languages"])
        p.slot(W - M - 24, y - 3, i + 1, lang_color(shares[0][0]) if shares else DIM)
        p.text(M, y, "> " + truncate(r["name"], 34), 8, FG)
        y += 14
        if shares:
            x, bar_w = M, W - 2 * M - 28  # leave room for the slot badge
            for j, (name, frac) in enumerate(shares):
                w = max(2, round(bar_w * frac)) if j < len(shares) - 1 else M + bar_w - x
                p.rect(x, y, w, 8, lang_color(name))
                x += w
            y += 14
            x = M
            for name, frac in shares:
                label = f"{truncate(name, 10)} {frac * 100:.0f}%"
                w = 14 + len(label) * 8 + 10
                if x + w > W - M:
                    break
                p.rect(x, y, 8, 8, lang_color(name))
                p.text(x + 14, y, label, 8, FG)
                x += w
        else:
            p.text(M + 16, y, "NO CODE", 8, DIM)
        y += 20
    p.rule(y)

    # tools (left) + tech stack (right); stack takes the full width when there are no tools
    def tags(x0, x1, y, items):
        """Draw wrapped tag boxes in [x0, x1]; returns the y of the last row."""
        x = x0
        for t in items:
            w = len(t) * 8 + 12
            if x + w > x1 and x > x0:
                x, y = x0, y + 20
            p.frame(x, y, w, 16, PINK)
            p.text(x + 6, y + 4, t, 8, FG)
            x += w + 6
        return y

    y += 10
    tools = cfg.get("tools", [])
    mid = W // 2
    sx0 = mid + 4 if tools else M
    p.text(sx0, y, "FIG_004 / TECH STACK", 8, CYAN)
    ye = tags(sx0, W - M, y + 16, cfg["stack"])
    if tools:
        p.text(M, y, "FIG_003 / TOOLS", 8, CYAN)
        per_row = (mid - 4 - M) // 61  # 61px pitch fits a 7-char label
        for i, t in enumerate(tools):
            row, col = divmod(i, per_row)
            ty = y + 16 + row * 46
            p.tile(M + 30 + col * 61, ty, t, LANG_COLORS[i % len(LANG_COLORS)])
            ye = max(ye, ty + 20)  # tile + label end at ty + 36; +28 below leaves the usual gap
    y = ye + 28
    p.rule(y)

    y += 10
    p.text(M, y, "PUBLIC GITHUB DATA", 8, DIM)
    p.text(W - M, y, "REFRESHED " + stats["fetched_at"], 8, DIM, anchor="r")
    y += 18

    img = p.img.crop((0, 0, W, y))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, y - 1], outline=PINK, width=2)
    d.rectangle([3, 3, W - 4, y - 4], outline=DIM, width=1)

    # One GIF frame per STEP ms over the cat's whole cycle; the banner is a pure
    # function of t in [0, 1), so loop end meets loop start.
    timeline = [sprite for sprite, ms in cat.frames() for _ in range(ms // STEP)]
    out = []
    for i, sprite in enumerate(timeline):
        frame = img.copy()
        frame.paste(banner(i / len(timeline)), (M, banner_y))
        big = sprite.resize((cat.GW * CAT_PX, cat.GH * CAT_PX), Image.NEAREST)
        frame.paste(big, (W - M - big.width, 38), big)
        out.append((frame.resize((W * SCALE, y * SCALE), Image.NEAREST), STEP))
    return out


if __name__ == "__main__":
    stats = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
    cfg = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
    for theme in THEMES:
        set_theme(theme)
        out = ROOT / "assets" / f"card-{theme}.gif"
        frames = render(stats, cfg)
        pal = [f.quantize(colors=128, dither=Image.Dither.NONE) for f, _ in frames]
        pal[0].save(out, save_all=True, append_images=pal[1:], duration=[ms for _, ms in frames],
                    loop=0, disposal=1)
        print("wrote", out, f"{out.stat().st_size // 1024} KB")
