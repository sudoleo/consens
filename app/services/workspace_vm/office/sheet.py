"""The overview of a converted file's first pages (convert.sh): one picture,
the pages in a grid on a grey ground, each with its number above it; two
columns of slides, three of portrait pages. At most LONGEST pixels on its
long side: the providers scale a picture down to about that anyway, and a
poster or a sheet of many pages stays far below their limits."""
import glob
import sys

from PIL import Image, ImageDraw, ImageFont

LONGEST = 1568

folder = sys.argv[1]
paths = sorted(glob.glob(folder + "/page-*.png"), key=lambda path: int(path.rsplit("-", 1)[1].split(".")[0]))
pages = [Image.open(path).convert("RGB") for path in paths]
width = max(page.width for page in pages)
height = max(page.height for page in pages)
columns = min(len(pages), 2 if width >= height else 3)
rows = -(-len(pages) // columns)
gap, label = 12, 16
sheet = Image.new("RGB", (columns * width + (columns + 1) * gap, rows * (height + label + gap) + gap), "#d9d9d9")
draw = ImageDraw.Draw(sheet)
try:
    # Pillow 10.1 and later scale the built-in font; the bitmap one is 11 px.
    font = ImageFont.load_default(size=14)
except TypeError:
    font = ImageFont.load_default()
for index, page in enumerate(pages):
    x = gap + (index % columns) * (width + gap)
    y = gap + (index // columns) * (height + label + gap)
    draw.text((x, y), str(index + 1), fill="#333333", font=font)
    sheet.paste(page, (x, y + label))
if max(sheet.size) > LONGEST:
    scale = LONGEST / max(sheet.size)
    sheet = sheet.resize((max(1, round(sheet.width * scale)), max(1, round(sheet.height * scale))), Image.LANCZOS)
sheet.save(folder + "/pages.png", optimize=True)
