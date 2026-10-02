"""Pixel white cat licking its paw. frames() -> list of (RGBA image, ms) on a GW x GH grid."""
from PIL import Image

GW, GH = 23, 20  # tail reaches x=21; the extra column holds its right outline
W, G, P, E = (250, 250, 255), (176, 178, 208), (255, 130, 170), (40, 36, 64)


def _ellipse(cx, cy, rx, ry):
    return {(x, y) for x in range(GW) for y in range(GH)
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1}


def _line(a, b, thick=2):
    (x0, y0), (x1, y1) = a, b
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    pts = {(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)) for i in range(n + 1)}
    return {(x + dx, y) for x, y in pts for dx in range(1 - thick, 1)}


# (paw tip, tongue pixels, eyes closed) per animation frame, ms
POSES = [
    ((8, 18), [], False, 700),
    ((6, 13), [], False, 150),
    ((4, 10), [], True, 200),
    ((4, 9), [(2, 9), (2, 10)], True, 200),
    ((4, 10), [], True, 200),
    ((4, 9), [(2, 9), (2, 10)], True, 200),
    ((6, 13), [], False, 150),
]


def _paint(img, pixels, fill):
    """Fill + 1px outline (painter's algorithm: later shapes cover earlier ones)."""
    edge = {(x + dx, y + dy) for x, y in pixels for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - pixels
    for x, y in edge:
        if 0 <= x < GW and 0 <= y < GH:
            img.putpixel((x, y), G + (255,))
    for x, y in pixels:
        if 0 <= x < GW and 0 <= y < GH:
            img.putpixel((x, y), fill + (255,))


def frames():
    out = []
    tail = _line((18, 18), (20, 16)) | _line((20, 16), (21, 11), 2) | _line((21, 11), (19, 9), 1)
    body = {p for p in _ellipse(12, 13, 6.4, 6.2) if p[1] <= 18}
    head = _ellipse(6, 6, 5.2, 4.2)
    ears = {(2, 1), (3, 1), (2, 2), (3, 2), (4, 2), (9, 1), (10, 1), (8, 2), (9, 2), (10, 2)}
    for tip, tongue, closed, ms in POSES:
        img = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
        _paint(img, tail, W)
        _paint(img, body, W)
        _paint(img, head, W)
        _paint(img, ears, W)
        for x, y in ((3, 2), (9, 2)):
            img.putpixel((x, y), P + (255,))
        for x in (3, 8):  # eyes: dot when open, flat line when closed
            img.putpixel((x, 5), (G if closed else E) + (255,))
            if closed:
                img.putpixel((x + 1, 5), G + (255,))
        img.putpixel((5, 7), P + (255,))  # nose
        leg = _line((9, 11), tip)
        if tip[1] < 14:  # raised: rounded paw pad at the tip
            leg |= {(tip[0] + dx, tip[1] + dy) for dx in (-2, -1, 0) for dy in (0, 1)}
        _paint(img, leg, W)  # licking foreleg
        for x, y in tongue:
            img.putpixel((x, y), P + (255,))
        out.append((img, ms))
    return out
