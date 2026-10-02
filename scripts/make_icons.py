"""One-off: fetch simple-icons SVGs -> 16x16 binary masks in assets/icons/.

Dev tool, not run by CI (the PNGs are committed). Needs network + PyMuPDF.
simple-icons is CC0; the logos are trademarks of their owners, shown here only
to say "I use this". Icon file name = card label lowercased, non-alphanumerics
stripped (see build_card.slug). Tools missing here (MATLAB, WSL has no logo)
fall back to a letter tile in build_card.
"""
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "assets" / "icons"
# card label slug -> simple-icons slug
ICONS = {
    "vscode": "visualstudiocode", "git": "git", "docker": "docker", "postman": "postman",
    "ollama": "ollama", "autocad": "autocad", "fusion": "autodesk", "wsl": "linux",
}
GRID, HI = 16, 128


def mask(svg):
    svg = svg.replace("<svg ", '<svg fill="black" ', 1)
    pix = fitz.open(stream=svg.encode(), filetype="svg")[0].get_pixmap(
        matrix=fitz.Matrix(HI / 24, HI / 24), alpha=True)
    img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    a = img.getchannel("A").resize((GRID, GRID), Image.BOX)  # coverage per cell
    return a.point(lambda v: 255 if v >= 115 else 0)  # threshold -> crisp pixels


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, slug in ICONS.items():
        url = f"https://cdn.jsdelivr.net/npm/simple-icons/icons/{slug}.svg"
        mask(urllib.request.urlopen(url).read().decode()).save(OUT / f"{name}.png")
        print("wrote", name)
