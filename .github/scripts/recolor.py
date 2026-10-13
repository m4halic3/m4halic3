import colorsys
import glob
import re
import sys

BG = "#0d1117"
WHITE = "#ffffff"
GRAY = "#8b949e"
PALETTE = [
    "#c1121f",  # vermelho
    "#6b0f1a",  # bordô
    "#e5989b",  # vermelho claro
    "#a4161a",  # vermelho escuro
    "#ff758f",  # vermelho rosado
    "#7a1c2b",  # bordô médio
    "#b0b7c3",  # cinza claro
]

NAMED = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0),
    "yellow": (255, 255, 0), "purple": (128, 0, 128), "pink": (255, 192, 203),
    "orange": (255, 165, 0), "blue": (0, 0, 255), "green": (0, 128, 0),
    "gray": (128, 128, 128), "grey": (128, 128, 128),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255),
}

PATTERN = re.compile(
    r"(?P<hex>(?<!url\()(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-zA-Z]))"
    r"|(?P<rgb>rgba?\(\s*\d+\s*[, ]\s*\d+\s*[, ]\s*\d+(?:\s*[,/]\s*[\d.]+%?)?\s*\))"
    r"|(?P<hsl>hsla?\(\s*[\d.]+(?:deg)?\s*[, ]\s*[\d.]+%\s*[, ]\s*[\d.]+%(?:\s*[,/]\s*[\d.]+%?)?\s*\))"
    r"|(?P<pre>(?:fill|stroke|stop-color|color|background|background-color)\s*[:=]\s*[\"']?)"
    r"(?P<name>white|black|red|yellow|purple|pink|orange|blue|green|gray|grey|cyan|magenta)\b",
    re.I,
)


def to_alpha(value):
    if value is None:
        return None
    value = value.strip()
    return float(value[:-1]) / 100 if value.endswith("%") else float(value)


def parse(match):
    if match.group("hex"):
        s = match.group("hex")[1:]
        if len(s) in (3, 4):
            s = "".join(c * 2 for c in s)
        rgb = tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        alpha = int(s[6:8], 16) / 255 if len(s) == 8 else None
        return rgb, alpha
    if match.group("rgb"):
        nums = re.findall(r"[\d.]+%?", match.group("rgb"))
        rgb = tuple(int(float(n)) for n in nums[:3])
        return rgb, to_alpha(nums[3]) if len(nums) > 3 else None
    if match.group("hsl"):
        nums = re.findall(r"[\d.]+%?", match.group("hsl"))
        h = float(nums[0]) / 360
        s = float(nums[1].rstrip("%")) / 100
        l = float(nums[2].rstrip("%")) / 100
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        rgb = (round(r * 255), round(g * 255), round(b * 255))
        return rgb, to_alpha(nums[3]) if len(nums) > 3 else None
    return NAMED[match.group("name").lower()], None


def process(svg):
    mapping = {}
    counter = {"used": 0}

    def classify(rgb):
        if rgb in mapping:
            return mapping[rgb]
        _, light, sat = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
        if light <= 0.16:
            new = BG
        elif light >= 0.78:
            new = WHITE
        elif sat < 0.15:
            new = GRAY
        else:
            new = PALETTE[counter["used"] % len(PALETTE)]
            counter["used"] += 1
        mapping[rgb] = new
        return new

    def repl(match):
        rgb, alpha = parse(match)
        new = classify(rgb)
        prefix = match.group("pre") or ""
        if alpha is not None and alpha < 1:
            r, g, b = (int(new[i:i + 2], 16) for i in (1, 3, 5))
            return f"{prefix}rgba({r},{g},{b},{alpha:.2f})"
        return prefix + new

    return PATTERN.sub(repl, svg), len(mapping)


files = glob.glob("profile-summary-card-output/radical/*.svg")
if not files:
    print("ERRO: nenhum SVG encontrado em profile-summary-card-output/radical/")
    sys.exit(1)

total = 0
for path in files:
    with open(path, encoding="utf-8") as f:
        svg = f.read()
    new_svg, n = process(svg)
    total += n
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_svg)
    print(f"{path}: {n} cores remapeadas")

if total == 0:
    print("ERRO: nenhuma cor encontrada para remapear")
    sys.exit(1)