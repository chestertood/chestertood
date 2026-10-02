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
RIBBON = ((235, 60, 70), (170, 28, 45), (255, 130, 130))  # base / shade / highlight
# metals: (light, base, dark, edge) for gold / silver / bronze
MEDALS = [((255, 238, 150), (255, 208, 64), (214, 150, 30), (120, 76, 14)),
          ((245, 247, 255), (205, 210, 225), (150, 156, 180), (78, 82, 108)),
          ((240, 170, 100), (205, 127, 50), (150, 85, 30), (84, 44, 16))]


def level(xp):
    """(level, progress 0..1). Level L starts at 4*(L-1)^2 xp."""
    lv = 1 + math.isqrt(xp // 4)
    lo, hi = 4 * (lv - 1) ** 2, 4 * lv**2
    return lv, (xp - lo) / (hi - lo)


def bar_fill(value, cap):
    """Log-scaled 0..1 so early progress is visible; saturates at cap."""
    return min(1.0, math.log1p(max(value, 0)) / math.log1p(cap))


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

    def medal(self, x, y, rank, d=16):
        """Bevelled pixel medal on a red V ribbon; rank 0/1/2 = gold/silver/bronze."""
        light, base, dark, edge = MEDALS[rank]
        top = y - 2  # coin top; ribbon tucks under it
        for k in range(9):
            s = min(k, 4)
            self.rect(x + d - 5 - s, top - 8 + k, 3, 1, RIBBON[1])
            self.rect(x + 2 + s, top - 8 + k, 3, 1, RIBBON[0])
            self.rect(x + 2 + s, top - 8 + k, 1, 1, RIBBON[2])
        c = (d - 1) / 2
        for j in range(d):
            for i in range(d):
                r = math.hypot(i - c, j - c)
                if r > d / 2:
                    continue
                if r > d / 2 - 1:
                    col = edge
                elif r > d / 2 - 2.6:
                    col = light if i + j < d - 1 else dark  # bevel: lit top-left, shaded bottom-right
                else:
                    col = base
                self.rect(x + i, top + j, 1, 1, col)
        self.rect(x + 3, top + 3, 2, 1, (255, 255, 255))  # glint
        self.text(x + 4, top + 4, str(rank + 1), 8, edge)

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
    p = Pen(700)
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

    # level + stat bars
    xp = (stats["commits"] + 5 * stats["prs"] + 10 * stats["stars"]
          + 5 * stats["followers"] + 3 * stats["repos"])
    lv, prog = level(xp)
    y += 10
    p.text(M, y, "FIG_001 / STATS", 8, CYAN)
    y += 16
    p.text(M, y, f"LV {lv:02d}", 24, YELLOW)
    p.text(W - M, y + 2, f"{xp} XP", 8, DIM, anchor="r")
    p.blocks(M + 140, y + 14, prog, 20, YELLOW, bw=6, gap=2, h=8)
    y += 36
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
        if i < len(MEDALS):  # only the first three get a medal
            p.medal(W - M - 16, y, i)
        p.text(M, y, "> " + truncate(r["name"], 34), 8, FG)
        y += 14
        shares = lang_shares(r["languages"])
        if shares:
            x, bar_w = M, W - 2 * M - 28  # leave room for the medal
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

    # tech stack
    y += 10
    p.text(M, y, "FIG_003 / TECH STACK", 8, CYAN)
    y += 16
    x = M
    for t in cfg["stack"]:
        w = len(t) * 8 + 12
        if x + w > W - M:
            x, y = M, y + 20
        p.frame(x, y, w, 16, PINK)
        p.text(x + 6, y + 4, t, 8, FG)
        x += w + 6
    y += 28
    p.rule(y)

    y += 10
    p.text(M, y, "PUBLIC GITHUB DATA", 8, DIM)
    p.text(W - M, y, "REFRESHED " + stats["fetched_at"], 8, DIM, anchor="r")
    y += 18

    img = p.img.crop((0, 0, W, y))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, y - 1], outline=PINK, width=2)
    d.rectangle([3, 3, W - 4, y - 4], outline=DIM, width=1)

    out = []
    for sprite, ms in cat.frames():
        frame = img.copy()
        big = sprite.resize((cat.GW * CAT_PX, cat.GH * CAT_PX), Image.NEAREST)
        frame.paste(big, (W - M - big.width, 38), big)
        out.append((frame.resize((W * SCALE, y * SCALE), Image.NEAREST), ms))
    return out


if __name__ == "__main__":
    stats = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
    cfg = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
    for theme in THEMES:
        set_theme(theme)
        out = ROOT / "assets" / f"card-{theme}.gif"
        frames = render(stats, cfg)
        pal = [f.quantize(colors=64, dither=Image.Dither.NONE) for f, _ in frames]
        pal[0].save(out, save_all=True, append_images=pal[1:], duration=[ms for _, ms in frames],
                    loop=0, disposal=1)
        print("wrote", out, f"{out.stat().st_size // 1024} KB")
