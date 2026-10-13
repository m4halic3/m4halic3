import colorsys
import glob
import re

BG = "#0d1117"
WHITE = "#FFFFFF"
PALETTE = [
    "#C1121F",  # vermelho
    "#6B0F1A",  # bordô
    "#E5989B",  # vermelho claro
    "#8B949E",  # cinza
    "#A4161A",  # vermelho escuro
    "#FF758F",  # vermelho rosado
    "#B0B7C3",  # cinza claro
    "#7A1C2B",  # bordô médio
]

HEX = re.compile(r"(?<!url\()#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def normalize(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h.lower()


def lightness(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)[1]


for path in glob.glob("profile-summary-card-output/radical/*.svg"):
    with open(path, encoding="utf-8") as f:
        svg = f.read()

    mapping = {}
    used = 0

    def repl(match):
        global used
        h = normalize(match.group(0))
        if h not in mapping:
            light = lightness(h)
            if light <= 0.12:
                mapping[h] = BG
            elif light >= 0.8:
                mapping[h] = WHITE
            else:
                mapping[h] = PALETTE[used % len(PALETTE)]
                used += 1
        return mapping[h]

    svg = HEX.sub(repl, svg)

    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"{path}: {len(mapping)} cores remapeadas")