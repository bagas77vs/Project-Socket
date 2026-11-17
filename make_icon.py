"""
Generate a Space Invader .ico file (multi-size: 256, 128, 64, 48, 32, 16)
"""
from PIL import Image, ImageDraw

# Classic Space Invader pixel pattern (11x8 grid, mirrored)
# 1 = alien body, 0 = transparent
PATTERN = [
    [0,0,1,0,0,0,0,0,1,0,0],
    [0,0,0,1,0,0,0,1,0,0,0],
    [0,0,1,1,1,1,1,1,1,0,0],
    [0,1,1,0,1,1,1,0,1,1,0],
    [1,1,1,1,1,1,1,1,1,1,1],
    [1,0,1,1,1,1,1,1,1,0,1],
    [1,0,1,0,0,0,0,0,1,0,1],
    [0,0,0,1,1,0,1,1,0,0,0],
]

ALIEN_COLOR = (0, 255, 70)      # green
EYE_COLOR   = (0, 0, 0)
BG_COLOR    = (0, 0, 0, 255)    # black background

COLS = len(PATTERN[0])  # 11
ROWS = len(PATTERN)     # 8

def make_frame(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Padding: 10% each side
    pad = int(size * 0.10)
    draw_w = size - 2 * pad
    draw_h = size - 2 * pad

    cell_w = draw_w / COLS
    cell_h = draw_h / ROWS

    for r, row in enumerate(PATTERN):
        for c, val in enumerate(row):
            if val:
                x0 = int(pad + c * cell_w)
                y0 = int(pad + r * cell_h)
                x1 = int(pad + (c + 1) * cell_w) - 1
                y1 = int(pad + (r + 1) * cell_h) - 1
                draw.rectangle([x0, y0, x1, y1], fill=ALIEN_COLOR)

    # Draw eyes (two dark squares inside row 3 cols 4&6)
    eye_positions = [(3, 3), (3, 7)]  # (row, col) in pattern space
    for er, ec in eye_positions:
        x0 = int(pad + ec * cell_w + cell_w*0.1)
        y0 = int(pad + er * cell_h + cell_h*0.1)
        x1 = int(pad + (ec+1) * cell_w - cell_w*0.1) - 1
        y1 = int(pad + (er+1) * cell_h - cell_h*0.1) - 1
        draw.rectangle([x0, y0, x1, y1], fill=EYE_COLOR)

    return img

SIZES = [256, 128, 64, 48, 32, 16]
frames = [make_frame(s) for s in SIZES]

out_path = r"d:\Socket project\client3.ico"
frames[0].save(
    out_path,
    format="ICO",
    sizes=[(s, s) for s in SIZES],
    append_images=frames[1:]
)
print(f"Icon saved → {out_path}")
print(f"Sizes: {SIZES}")

