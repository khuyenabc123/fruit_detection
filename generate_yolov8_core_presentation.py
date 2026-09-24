from pathlib import Path
from math import exp

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


OUT = Path(__file__).with_name("YOLOv8_Tu_Pixel_Den_Bounding_Box.pptx")

W, H = 13.333, 7.5
BG = RGBColor(8, 16, 30)
BG_2 = RGBColor(14, 27, 46)
CARD = RGBColor(20, 36, 58)
CARD_2 = RGBColor(27, 47, 72)
INK = RGBColor(244, 248, 255)
MUTED = RGBColor(157, 177, 202)
GRID = RGBColor(52, 75, 102)
CYAN = RGBColor(38, 208, 206)
GREEN = RGBColor(89, 221, 146)
YELLOW = RGBColor(255, 190, 72)
ORANGE = RGBColor(255, 132, 74)
RED = RGBColor(255, 91, 111)
PURPLE = RGBColor(155, 126, 255)
BLUE = RGBColor(75, 150, 255)

FONT = "Noto Sans"
MONO = "DejaVu Sans Mono"


def shape(slide, kind, x, y, w, h, fill=CARD, line=GRID, radius=False, transparency=0):
    if radius:
        kind = MSO_SHAPE.ROUNDED_RECTANGLE
    s = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.fill.transparency = transparency
    s.line.color.rgb = line
    s.line.width = Pt(1)
    return s


def rect(slide, x, y, w, h, fill=CARD, line=GRID, radius=True, transparency=0):
    return shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, fill, line, radius, transparency)


def outline(slide, x, y, w, h, color=CYAN, width=2.0, radius=False):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.background()
    s.line.color.rgb = color
    s.line.width = Pt(width)
    return s


def textbox(slide, value, x, y, w, h, size=18, color=INK, bold=False,
            align=PP_ALIGN.LEFT, font=FONT, valign=MSO_ANCHOR.TOP,
            margin=0.04, italic=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = value
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    return box


def rich(slide, parts, x, y, w, h, size=18, align=PP_ALIGN.LEFT,
         valign=MSO_ANCHOR.TOP, font=FONT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    for value, color, bold in parts:
        r = p.add_run()
        r.text = value
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
    return box


def line(slide, x1, y1, x2, y2, color=GRID, width=1.2):
    if abs(y2 - y1) < 0.01:
        s = rect(slide, x1, y1, max(0.01, x2 - x1), width / 72, color, color, False)
    else:
        s = rect(slide, x1, y1, width / 72, max(0.01, y2 - y1), color, color, False)
    return s


def arrow(slide, x, y, w=0.46, h=0.46, color=CYAN, direction="right"):
    kinds = {
        "right": MSO_SHAPE.CHEVRON,
        "down": MSO_SHAPE.DOWN_ARROW,
        "left": MSO_SHAPE.LEFT_ARROW,
    }
    s = shape(slide, kinds[direction], x, y, w, h, color, color, False, 5)
    return s


def circle(slide, x, y, d, fill=CYAN, line_color=None):
    return shape(slide, MSO_SHAPE.OVAL, x, y, d, d, fill, line_color or fill)


def pill(slide, label, x, y, w, color=CYAN, text_color=INK, size=9.5):
    rect(slide, x, y, w, 0.36, color, color, True, 72)
    textbox(slide, label, x + 0.05, y + 0.055, w - 0.1, 0.22, size, text_color, True, PP_ALIGN.CENTER)


def card(slide, x, y, w, h, heading, body="", accent=CYAN, number=None,
         body_size=11.5, heading_size=14):
    rect(slide, x, y, w, h, CARD, GRID, True)
    rect(slide, x, y, 0.055, h, accent, accent, True)
    hx = x + 0.25
    if number:
        textbox(slide, number, x + 0.22, y + 0.17, 0.45, 0.3, 10, accent, True)
        hx = x + 0.66
    textbox(slide, heading, hx, y + 0.16, w - (hx - x) - 0.18, 0.34,
            heading_size, INK, True)
    if body:
        textbox(slide, body, x + 0.25, y + 0.61, w - 0.48, h - 0.75,
                body_size, MUTED)


def formula(slide, value, x, y, w, h=0.58, color=INK, size=16, accent=CYAN):
    rect(slide, x, y, w, h, BG_2, GRID, True)
    rect(slide, x, y, 0.05, h, accent, accent, True)
    textbox(slide, value, x + 0.16, y + 0.10, w - 0.28, h - 0.18,
            size, color, True, PP_ALIGN.CENTER, MONO, MSO_ANCHOR.MIDDLE)


def bullets(slide, items, x, y, w, h, size=12.5, color=INK, accent=CYAN, spacing=7):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(spacing)
        p.line_spacing = 1.06
        r1 = p.add_run()
        r1.text = "●  "
        r1.font.name = FONT
        r1.font.size = Pt(max(8, size - 4))
        r1.font.color.rgb = accent
        r2 = p.add_run()
        r2.text = item
        r2.font.name = FONT
        r2.font.size = Pt(size)
        r2.font.color.rgb = color
    return box


def matrix(slide, values, x, y, cell=0.36, colors=None, text_size=9, line_color=GRID):
    rows = len(values)
    cols = len(values[0])
    for r in range(rows):
        for c in range(cols):
            fill = colors[r][c] if colors else CARD_2
            rect(slide, x + c * cell, y + r * cell, cell - 0.02, cell - 0.02,
                 fill, line_color, False)
            textbox(slide, str(values[r][c]), x + c * cell, y + r * cell + 0.06,
                    cell - 0.02, cell - 0.08, text_size,
                    INK if fill != RGBColor(245, 245, 245) else BG, True, PP_ALIGN.CENTER,
                    MONO)
    return cols * cell, rows * cell


def add_bg(slide):
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = BG
    rect(slide, 11.9, -0.32, 1.75, 0.98, CYAN, CYAN, True, 86)
    rect(slide, -0.42, 6.94, 2.1, 0.88, PURPLE, PURPLE, True, 90)


def title(slide, kicker, heading, number):
    textbox(slide, kicker.upper(), 0.70, 0.30, 8.2, 0.28, 9.5, CYAN, True)
    textbox(slide, heading, 0.70, 0.67, 11.7, 0.62, 25, INK, True)
    textbox(slide, f"{number:02d}", 12.06, 0.39, 0.55, 0.28, 10, MUTED, True, PP_ALIGN.RIGHT)
    line(slide, 0.70, 1.40, 12.62, 1.40, GRID, 1.2)


def footer(slide, number, source=""):
    if source:
        textbox(slide, source, 0.70, 7.12, 10.9, 0.18, 7.2, MUTED)
    textbox(slide, f"PIXEL → YOLOv8  ·  {number:02d}", 11.35, 7.10, 1.26, 0.20,
            7.5, MUTED, True, PP_ALIGN.RIGHT)


def new_slide(prs, kicker, heading, number, source=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    title(slide, kicker, heading, number)
    footer(slide, number, source)
    return slide


def add_cover(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    # Pixel field becoming a bounding box.
    px = [
        [RED, ORANGE, YELLOW, GREEN, CYAN, BLUE],
        [ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE],
        [YELLOW, GREEN, CYAN, BLUE, PURPLE, RED],
        [GREEN, CYAN, BLUE, PURPLE, RED, ORANGE],
        [CYAN, BLUE, PURPLE, RED, ORANGE, YELLOW],
    ]
    for r in range(5):
        for c in range(6):
            rect(slide, 8.38 + c * 0.55, 1.35 + r * 0.55, 0.43, 0.43,
                 px[r][c], px[r][c], False, 12)
    outline(slide, 9.10, 2.05, 2.65, 2.00, GREEN, 3)
    pill(slide, "MANGO  0.93", 9.10, 1.64, 1.55, GREEN)
    for i, label in enumerate(["RGB", "FEATURE", "BOX"]):
        pill(slide, label, 8.54 + i * 1.30, 4.56, 1.05,
             [RED, CYAN, GREEN][i], size=8.5)
        if i < 2:
            arrow(slide, 9.65 + i * 1.30, 4.54, 0.30, 0.36, MUTED)
    textbox(slide, "MACHINE LEARNING · COMPUTER VISION", 0.82, 0.72, 6.9, 0.3, 10, CYAN, True)
    textbox(slide, "TỪ PIXEL ĐẾN\nBOUNDING BOX", 0.82, 1.42, 7.15, 1.65, 35, INK, True)
    textbox(slide, "Cốt lõi cách YOLOv8 nhìn, học và dự đoán", 0.86, 3.40, 6.9, 0.46, 17, MUTED)
    line(slide, 0.86, 4.13, 6.82, 4.13, GRID)
    textbox(slide, "Không bắt đầu từ API. Bắt đầu từ một con số màu sắc.",
            0.86, 4.44, 6.75, 0.62, 15, GREEN, True)
    textbox(slide, "YOLOv8s · Object Detection · Fruit Detection", 0.86, 6.56, 5.8, 0.26, 9.5, MUTED, True)


def add_roadmap(prs):
    slide = new_slide(prs, "00 · Bản đồ", "Một dự đoán được tạo ra qua 8 phép biến đổi", 2)
    stages = [
        ("01", "Pixel", "R,G,B", RED),
        ("02", "Tensor", "1×3×640×640", ORANGE),
        ("03", "Backbone", "trích đặc trưng", YELLOW),
        ("04", "Neck", "hợp nhất tỉ lệ", GREEN),
        ("05", "Head", "box + class", CYAN),
        ("06", "Decode", "tọa độ ảnh", BLUE),
        ("07", "NMS", "bỏ box trùng", PURPLE),
        ("08", "Output", "quả + 0.93", RED),
    ]
    x0, y0 = 0.55, 2.08
    for i, (num, head, body, color) in enumerate(stages):
        x = x0 + i * 1.57
        rect(slide, x, y0, 1.28, 2.46, CARD, GRID, True)
        circle(slide, x + 0.43, y0 + 0.24, 0.42, color)
        textbox(slide, num, x + 0.43, y0 + 0.32, 0.42, 0.18, 8.5, BG, True, PP_ALIGN.CENTER)
        textbox(slide, head, x + 0.10, y0 + 0.88, 1.08, 0.32, 13, INK, True, PP_ALIGN.CENTER)
        textbox(slide, body, x + 0.09, y0 + 1.42, 1.10, 0.52, 9.2, MUTED, False, PP_ALIGN.CENTER)
        if i < len(stages) - 1:
            arrow(slide, x + 1.31, y0 + 1.00, 0.23, 0.40, GRID)
    rich(slide, [("Điểm xuyên suốt: ", MUTED, False),
                 ("mọi thứ đều là tensor và phép toán khả vi", CYAN, True),
                 (" — cho đến bước NMS.", MUTED, False)],
         1.15, 5.28, 11.0, 0.48, 15, PP_ALIGN.CENTER)
    formula(slide, "pixel → feature → logits → probability / box → detection",
            2.10, 5.92, 9.10, 0.64, INK, 15, GREEN)


def add_pixel(prs):
    slide = new_slide(prs, "01 · Đầu vào", "Một pixel không phải “màu” — nó là ba con số", 3)
    # Large RGB pixel.
    rect(slide, 0.78, 1.86, 4.25, 4.72, CARD, GRID, True)
    textbox(slide, "PIXEL (x = 421, y = 206)", 1.08, 2.12, 3.64, 0.26, 10, CYAN, True, PP_ALIGN.CENTER)
    channels = [("R", "214", RED), ("G", "98", GREEN), ("B", "37", BLUE)]
    for i, (name, value, color) in enumerate(channels):
        y = 2.68 + i * 0.95
        rect(slide, 1.20, y, 0.64, 0.64, color, color, True)
        textbox(slide, name, 1.20, y + 0.13, 0.64, 0.28, 14, INK, True, PP_ALIGN.CENTER)
        textbox(slide, value, 2.14, y + 0.08, 1.08, 0.38, 22, INK, True, PP_ALIGN.RIGHT, MONO)
        textbox(slide, "/ 255", 3.30, y + 0.17, 0.78, 0.24, 10, MUTED, False, PP_ALIGN.LEFT, MONO)
    rect(slide, 1.22, 5.74, 3.34, 0.54, RGBColor(214, 98, 37), RGBColor(214, 98, 37), True)
    textbox(slide, "màu hiển thị", 1.22, 5.90, 3.34, 0.20, 9.5, INK, True, PP_ALIGN.CENTER)

    textbox(slide, "ẢNH = LƯỚI PIXEL", 5.56, 1.90, 2.35, 0.26, 10, CYAN, True)
    vals = [["…"] * 6 for _ in range(5)]
    cols = [[CARD_2] * 6 for _ in range(5)]
    vals[2][4] = "●"; cols[2][4] = ORANGE
    matrix(slide, vals, 5.58, 2.36, 0.55, cols, 11)
    textbox(slide, "tọa độ (x, y)", 6.00, 5.32, 2.40, 0.28, 11, MUTED, True, PP_ALIGN.CENTER)
    arrow(slide, 8.94, 3.32, 0.52, 0.55, CYAN)
    rect(slide, 9.72, 2.18, 2.85, 2.70, BG_2, GRID, True)
    textbox(slide, "Vector tại pixel", 10.02, 2.47, 2.25, 0.28, 12, MUTED, True, PP_ALIGN.CENTER)
    formula(slide, "[214, 98, 37]", 10.05, 3.04, 2.20, 0.62, INK, 16, ORANGE)
    formula(slide, "[0.839, 0.384, 0.145]", 9.91, 3.92, 2.48, 0.62, GREEN, 11.5, GREEN)
    rich(slide, [("640 × 640 pixel × 3 kênh = ", MUTED, False),
                 ("1.228.800 giá trị đầu vào", YELLOW, True)],
         5.58, 5.90, 6.92, 0.42, 14, PP_ALIGN.CENTER)


def add_preprocess(prs):
    slide = new_slide(prs, "02 · Tiền xử lý", "Từ tệp ảnh đến tensor mà mạng có thể tính", 4)
    steps = [
        ("Ảnh gốc", "1920 × 1080 × 3\nuint8 · [0,255]", RED),
        ("Resize", "giữ tỉ lệ\nscale = 640/1920", ORANGE),
        ("Letterbox", "640 × 640\npadding trên / dưới", YELLOW),
        ("Normalize", "float32\nx / 255 ∈ [0,1]", GREEN),
        ("Reorder", "HWC → CHW\n640×640×3 → 3×640×640", CYAN),
        ("Batch", "B×3×640×640\nví dụ B = 1", PURPLE),
    ]
    x = 0.55
    for i, (head, body, color) in enumerate(steps):
        rect(slide, x, 2.05, 1.78, 2.68, CARD, GRID, True)
        circle(slide, x + 0.63, 2.30, 0.52, color)
        textbox(slide, str(i + 1), x + 0.63, 2.41, 0.52, 0.20, 9.5, BG, True, PP_ALIGN.CENTER)
        textbox(slide, head, x + 0.13, 3.06, 1.52, 0.31, 13.5, INK, True, PP_ALIGN.CENTER)
        textbox(slide, body, x + 0.13, 3.66, 1.52, 0.72, 9.5, MUTED, False, PP_ALIGN.CENTER, MONO)
        if i < len(steps) - 1:
            arrow(slide, x + 1.81, 3.05, 0.28, 0.50, GRID)
        x += 2.08
    formula(slide, "X ∈ ℝ^(B×C×H×W) = ℝ^(1×3×640×640)",
            2.13, 5.27, 9.06, 0.70, INK, 16, CYAN)
    textbox(slide, "Quan trọng: padding không tạo thêm thông tin; nó chỉ giúp kích thước phù hợp với stride 32.",
            1.42, 6.20, 10.50, 0.34, 12, MUTED, True, PP_ALIGN.CENTER)


def add_convolution(prs):
    slide = new_slide(prs, "03 · Phép toán nền tảng", "Convolution: một ô đầu ra được tính như thế nào?", 5)
    textbox(slide, "PATCH 3×3", 0.88, 1.78, 2.20, 0.25, 10, CYAN, True, PP_ALIGN.CENTER)
    patch = [[0, 0, 0], [0, 1, 1], [0, 1, 1]]
    matrix(slide, patch, 1.18, 2.27, 0.70, [[CARD_2] * 3 for _ in range(3)], 14)
    textbox(slide, "×", 3.53, 2.92, 0.45, 0.38, 24, MUTED, True, PP_ALIGN.CENTER)
    textbox(slide, "KERNEL 3×3", 4.10, 1.78, 2.20, 0.25, 10, GREEN, True, PP_ALIGN.CENTER)
    kernel = [[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]]
    matrix(slide, kernel, 4.38, 2.27, 0.70, [[BG_2] * 3 for _ in range(3)], 14)
    textbox(slide, "→", 6.79, 2.92, 0.52, 0.38, 24, MUTED, True, PP_ALIGN.CENTER)
    rect(slide, 7.55, 2.55, 1.16, 1.16, CYAN, CYAN, True, 18)
    textbox(slide, "2", 7.55, 2.82, 1.16, 0.42, 27, INK, True, PP_ALIGN.CENTER, MONO)
    textbox(slide, "1 ô feature", 7.34, 3.96, 1.57, 0.24, 9.5, MUTED, True, PP_ALIGN.CENTER)
    rect(slide, 9.30, 1.92, 3.22, 3.05, CARD, GRID, True)
    textbox(slide, "TÍNH TỪNG PHẦN TỬ", 9.61, 2.18, 2.60, 0.27, 10, YELLOW, True, PP_ALIGN.CENTER)
    textbox(slide, "0·(-1) + 0·0 + 0·1\n+ 0·(-1) + 1·0 + 1·1\n+ 0·(-1) + 1·0 + 1·1",
            9.70, 2.74, 2.44, 1.12, 11.5, INK, False, PP_ALIGN.LEFT, MONO)
    formula(slide, "Σ(patch ⊙ kernel) + b = 2", 9.58, 4.16, 2.66, 0.52, GREEN, 10.5, GREEN)
    formula(slide, "y[o,i,j] = b[o] + Σc Σu Σv W[o,c,u,v] · x[c,i+u,j+v]",
            1.12, 5.25, 11.06, 0.70, INK, 12.2, PURPLE)
    textbox(slide, "Với ảnh RGB, kernel có độ sâu 3: nó cộng đồng thời thông tin R, G và B.",
            1.08, 6.20, 11.10, 0.34, 12.5, MUTED, True, PP_ALIGN.CENTER)


def add_feature_maps(prs):
    slide = new_slide(prs, "04 · Biểu diễn", "Một kernel tạo một feature map; nhiều kernel tạo nhiều kênh", 6)
    # Stacked input channels.
    channel_data = [("R", RED), ("G", GREEN), ("B", BLUE)]
    for i, (label, color) in enumerate(channel_data):
        ox = 0.80 + i * 0.18
        oy = 2.10 - i * 0.18
        rect(slide, ox, oy, 2.42, 2.42, color, color, False, 48)
        textbox(slide, label, ox + 0.86, oy + 0.91, 0.70, 0.32, 18, INK, True, PP_ALIGN.CENTER)
    textbox(slide, "3 input channels", 0.88, 4.78, 2.72, 0.26, 11, MUTED, True, PP_ALIGN.CENTER)
    arrow(slide, 3.76, 3.00, 0.55, 0.58, CYAN)
    rect(slide, 4.54, 2.05, 2.16, 2.60, CARD, GRID, True)
    textbox(slide, "32 KERNEL", 4.82, 2.35, 1.60, 0.30, 12, CYAN, True, PP_ALIGN.CENTER)
    textbox(slide, "mỗi kernel:\n3 × 3 × 3\n+ 1 bias", 4.87, 3.02, 1.50, 1.10, 13, INK, False, PP_ALIGN.CENTER, MONO)
    arrow(slide, 6.94, 3.00, 0.55, 0.58, CYAN)
    # Output stacked maps.
    for i in range(6):
        ox = 7.80 + i * 0.18
        oy = 2.30 - i * 0.12
        rect(slide, ox, oy, 2.26, 2.26,
             [PURPLE, BLUE, CYAN, GREEN, YELLOW, ORANGE][i], GRID, False, 42)
    textbox(slide, "32 feature maps", 7.96, 4.80, 3.12, 0.26, 11, MUTED, True, PP_ALIGN.CENTER)
    rect(slide, 11.13, 2.05, 1.40, 2.60, BG_2, GRID, True)
    textbox(slide, "Học dần", 11.33, 2.38, 1.00, 0.28, 11, YELLOW, True, PP_ALIGN.CENTER)
    textbox(slide, "cạnh\ntexture\nmàu\nhình dạng\nbộ phận", 11.30, 3.00, 1.06, 1.34, 10.5, INK, False, PP_ALIGN.CENTER)
    formula(slide, "W: (C_out, C_in, k, k) = (32, 3, 3, 3)",
            2.26, 5.47, 8.80, 0.65, INK, 14.5, GREEN)
    textbox(slide, "Tên “cạnh” hay “texture” là cách con người diễn giải; mạng chỉ tối ưu các trọng số W.",
            1.20, 6.32, 10.92, 0.35, 12, MUTED, True, PP_ALIGN.CENTER)


def add_conv_block(prs):
    slide = new_slide(prs, "05 · Conv block", "Conv → BatchNorm → SiLU: ba bước trong một lớp", 7,
                      "Nguồn: Ultralytics nn/modules/conv.py")
    stages = [
        ("Conv", "z = W*x", "trộn lân cận + kênh", CYAN),
        ("BatchNorm", "ẑ = γ(z−μ)/√(σ²+ε)+β", "ổn định phân phối", GREEN),
        ("SiLU", "a = ẑ · sigmoid(ẑ)", "thêm phi tuyến", PURPLE),
    ]
    x = 1.02
    for i, (head, eq, body, color) in enumerate(stages):
        rect(slide, x, 2.10, 3.22, 2.80, CARD, GRID, True)
        pill(slide, f"STEP {i+1}", x + 0.24, 2.33, 0.88, color, size=8)
        textbox(slide, head, x + 0.24, 2.92, 2.72, 0.36, 18, INK, True)
        formula(slide, eq, x + 0.24, 3.48, 2.72, 0.58, INK, 10.5 if i == 1 else 13, color)
        textbox(slide, body, x + 0.25, 4.34, 2.70, 0.25, 10.5, MUTED, True, PP_ALIGN.CENTER)
        if i < 2:
            arrow(slide, x + 3.35, 3.16, 0.45, 0.55, GRID)
        x += 4.08
    rich(slide, [("Không có phi tuyến: ", MUTED, False),
                 ("nhiều lớp linear vẫn chỉ tương đương một phép linear", RED, True),
                 (". SiLU giúp mạng mô hình hóa quan hệ phức tạp.", MUTED, False)],
         1.10, 5.42, 11.15, 0.52, 13.5, PP_ALIGN.CENTER)
    formula(slide, "SiLU(x) = x / (1 + e^(−x))",
            4.10, 6.18, 5.12, 0.58, INK, 15, PURPLE)


def add_stride(prs):
    slide = new_slide(prs, "06 · Không gian", "Stride giảm độ phân giải nhưng mở rộng vùng nhìn", 8)
    # The square side is a visual encoding, not a literal spatial scale.
    sizes = [("640²", "pixel", 2.00, RED), ("320²", "s=2", 1.65, ORANGE),
             ("160²", "s=4", 1.38, YELLOW), ("80²", "s=8", 1.14, GREEN),
             ("40²", "s=16", 0.95, CYAN), ("20²", "s=32", 0.78, PURPLE)]
    x = 0.66
    for i, (label, sub, side, color) in enumerate(sizes):
        y = 2.26 + (2.00 - side) / 2
        rect(slide, x, y, side, side, color, color, False, 72)
        textbox(slide, label, x, y + side / 2 - 0.25, side, 0.30,
                13 if side > 1 else 10, INK, True, PP_ALIGN.CENTER)
        textbox(slide, sub, x, y + side / 2 + 0.14, side, 0.22,
                8.5, MUTED, True, PP_ALIGN.CENTER)
        if i < len(sizes) - 1:
            x += side + 0.27
            arrow(slide, x - 0.23, 3.03, 0.21, 0.38, GRID)
    rect(slide, 10.17, 1.92, 2.34, 3.72, CARD, GRID, True)
    textbox(slide, "ĐÁNH ĐỔI", 10.40, 2.20, 1.88, 0.28, 10, YELLOW, True, PP_ALIGN.CENTER)
    bullets(slide, [
        "H,W nhỏ → ít phép tính hơn",
        "mỗi ô đại diện vùng ảnh lớn hơn",
        "ngữ nghĩa tăng, chi tiết vị trí giảm",
        "vật thể nhỏ cần feature map 80×80",
    ], 10.37, 2.82, 1.94, 2.35, 9.6, INK, CYAN, 7)
    textbox(slide, "Receptive field", 10.40, 5.18, 1.88, 0.24, 9.5, GREEN, True, PP_ALIGN.CENTER)
    formula(slide, "H_out = ⌊(H + 2p − k)/s⌋ + 1",
            2.38, 5.70, 6.72, 0.58, INK, 14, BLUE)
    textbox(slide, "Receptive field = vùng ảnh gốc có thể ảnh hưởng đến một ô đặc trưng.",
            1.18, 6.48, 8.95, 0.30, 11.2, MUTED, True, PP_ALIGN.CENTER)


def add_backbone(prs):
    slide = new_slide(prs, "07 · Backbone", "Hành trình tensor trong YOLOv8s (input 640×640)", 9,
                      "Nguồn: ultralytics/cfg/models/v8/yolov8.yaml")
    rows = [
        ("Input", "3×640×640", "RGB đã chuẩn hóa", RED),
        ("Conv s=2", "32×320×320", "cạnh / màu cục bộ", ORANGE),
        ("Conv + C2f×1", "64×160×160", "texture", YELLOW),
        ("P3 · Conv + C2f×2", "128×80×80", "chi tiết — vật thể nhỏ", GREEN),
        ("P4 · Conv + C2f×2", "256×40×40", "ngữ nghĩa — vật thể vừa", CYAN),
        ("P5 · Conv + C2f×1", "512×20×20", "ngữ nghĩa sâu — vật thể lớn", PURPLE),
        ("SPPF", "512×20×20", "ngữ cảnh đa vùng", BLUE),
    ]
    y = 1.74
    for i, (stage, tensor, meaning, color) in enumerate(rows):
        rect(slide, 0.80, y, 11.72, 0.62, CARD if i % 2 == 0 else BG_2, GRID, True)
        circle(slide, 1.02, y + 0.14, 0.32, color)
        textbox(slide, f"{i:02d}", 1.02, y + 0.20, 0.32, 0.14, 7, BG, True, PP_ALIGN.CENTER)
        textbox(slide, stage, 1.55, y + 0.14, 2.20, 0.26, 12.2, INK, True)
        textbox(slide, tensor, 4.07, y + 0.14, 2.26, 0.26, 11.5, color, True, font=MONO)
        textbox(slide, meaning, 6.68, y + 0.14, 5.40, 0.26, 11.2, MUTED)
        y += 0.71
    rich(slide, [("Quy luật: ", MUTED, False), ("H,W giảm", ORANGE, True),
                 (" — ", MUTED, False), ("số kênh tăng", CYAN, True),
                 (" — đặc trưng từ cục bộ đến ngữ nghĩa.", MUTED, False)],
         1.25, 6.76, 10.80, 0.30, 12.5, PP_ALIGN.CENTER)


def add_c2f(prs):
    slide = new_slide(prs, "08 · C2f", "C2f giữ nhiều đường truyền đặc trưng và gradient", 10,
                      "Nguồn: Ultralytics nn/modules/block.py")
    # Block diagram.
    rect(slide, 0.82, 2.30, 1.46, 1.02, CARD, GRID, True)
    textbox(slide, "Input X", 0.82, 2.64, 1.46, 0.28, 14, INK, True, PP_ALIGN.CENTER)
    arrow(slide, 2.47, 2.57, 0.45, 0.50, CYAN)
    rect(slide, 3.08, 2.16, 1.60, 1.32, CARD_2, GRID, True)
    textbox(slide, "Conv 1×1", 3.08, 2.44, 1.60, 0.28, 13, CYAN, True, PP_ALIGN.CENTER)
    textbox(slide, "2c channels", 3.08, 2.92, 1.60, 0.22, 9.5, MUTED, False, PP_ALIGN.CENTER, MONO)
    arrow(slide, 4.86, 2.57, 0.45, 0.50, CYAN)
    rect(slide, 5.46, 1.88, 1.58, 0.82, BG_2, GRID, True)
    rect(slide, 5.46, 3.06, 1.58, 0.82, BG_2, GRID, True)
    textbox(slide, "chunk A", 5.46, 2.14, 1.58, 0.26, 12, GREEN, True, PP_ALIGN.CENTER)
    textbox(slide, "chunk B", 5.46, 3.32, 1.58, 0.26, 12, YELLOW, True, PP_ALIGN.CENTER)
    arrow(slide, 7.22, 3.15, 0.45, 0.50, YELLOW)
    rect(slide, 7.84, 3.01, 1.72, 0.94, CARD_2, GRID, True)
    textbox(slide, "Bottleneck 1", 7.84, 3.31, 1.72, 0.28, 11.5, INK, True, PP_ALIGN.CENTER)
    arrow(slide, 9.74, 3.15, 0.45, 0.50, YELLOW)
    rect(slide, 10.35, 3.01, 1.72, 0.94, CARD_2, GRID, True)
    textbox(slide, "Bottleneck n", 10.35, 3.31, 1.72, 0.28, 11.5, INK, True, PP_ALIGN.CENTER)
    # Concat bus.
    line(slide, 6.24, 4.33, 11.16, 4.33, PURPLE, 2)
    for xx in [6.24, 8.70, 11.16]:
        line(slide, xx, 3.95 if xx > 6.3 else 3.88, xx, 4.33, PURPLE, 2)
    textbox(slide, "CONCAT [A, B, Bottleneck₁, …, Bottleneckₙ]", 6.05, 4.49, 5.50, 0.28, 11, PURPLE, True, PP_ALIGN.CENTER, MONO)
    arrow(slide, 11.72, 4.40, 0.42, 0.50, PURPLE)
    rect(slide, 12.20, 4.23, 0.72, 0.84, CYAN, CYAN, True, 60)
    textbox(slide, "Conv", 12.20, 4.49, 0.72, 0.24, 9, INK, True, PP_ALIGN.CENTER)

    cards = [
        ("Đường ngắn", "A đi thẳng tới concat → giữ đặc trưng gốc.", GREEN),
        ("Đường sâu", "B qua chuỗi bottleneck → đặc trưng biến đổi dần.", YELLOW),
        ("Gradient", "Nhiều đường hồi truyền giúp tối ưu ổn định hơn.", PURPLE),
    ]
    x = 0.86
    for head, body, color in cards:
        card(slide, x, 5.42, 3.80, 1.12, head, body, color, body_size=9.8, heading_size=12.5)
        x += 4.02
    textbox(slide, "C2f không tự “nhìn thấy quả”; nó tạo không gian đặc trưng thuận lợi để head phân loại và định vị.",
            1.00, 6.77, 11.25, 0.28, 11.5, MUTED, True, PP_ALIGN.CENTER)


def add_sppf(prs):
    slide = new_slide(prs, "09 · SPPF", "SPPF gom ngữ cảnh ở nhiều kích thước mà không đổi H×W", 11,
                      "Nguồn: Ultralytics nn/modules/block.py")
    blocks = [
        ("X", "20×20×512", CYAN),
        ("Conv 1×1", "20×20×256", GREEN),
        ("MaxPool 5", "≈ receptive 5", YELLOW),
        ("MaxPool 5", "≈ receptive 9", ORANGE),
        ("MaxPool 5", "≈ receptive 13", RED),
    ]
    x = 0.58
    for i, (head, sub, color) in enumerate(blocks):
        rect(slide, x, 2.18, 1.90, 1.36, CARD, GRID, True)
        textbox(slide, head, x + 0.12, 2.48, 1.66, 0.30, 12.5, color, True, PP_ALIGN.CENTER)
        textbox(slide, sub, x + 0.12, 2.98, 1.66, 0.24, 9.2, MUTED, False, PP_ALIGN.CENTER, MONO)
        if i < len(blocks) - 1:
            arrow(slide, x + 1.94, 2.63, 0.34, 0.45, GRID)
        x += 2.43
    line(slide, 3.49, 4.05, 10.78, 4.05, PURPLE, 2)
    for xx in [3.49, 5.92, 8.35, 10.78]:
        line(slide, xx, 3.54, xx, 4.05, PURPLE, 2)
    textbox(slide, "Concat 4 nhánh theo chiều channel", 5.15, 4.20, 4.18, 0.28, 12, PURPLE, True, PP_ALIGN.CENTER)
    arrow(slide, 9.48, 4.14, 0.45, 0.50, PURPLE)
    rect(slide, 10.15, 4.05, 2.18, 0.78, CARD_2, GRID, True)
    textbox(slide, "Conv 1×1 → 512ch", 10.15, 4.29, 2.18, 0.27, 11.5, INK, True, PP_ALIGN.CENTER)
    rich(slide, [("MaxPool giữ phản hồi mạnh nhất trong vùng. ", MUTED, False),
                 ("Ba lần pool 5×5 liên tiếp", YELLOW, True),
                 (" xấp xỉ các vùng 5, 9 và 13 với chi phí thấp.", MUTED, False)],
         1.15, 5.40, 11.05, 0.58, 13.3, PP_ALIGN.CENTER)
    formula(slide, "SPPF(X) = Conv(Concat[X₀, Pool(X₀), Pool²(X₀), Pool³(X₀)])",
            1.64, 6.22, 10.05, 0.60, INK, 12.2, YELLOW)


def add_neck(prs):
    slide = new_slide(prs, "10 · Neck", "FPN + PAN: đưa ngữ nghĩa sâu về lại vị trí chi tiết", 12,
                      "Nguồn: YOLOv8 model YAML; FPN/PAN feature fusion")
    # Three levels left and right.
    levels = [
        ("P3", "80×80×128", 2.02, GREEN, "small"),
        ("P4", "40×40×256", 3.38, CYAN, "medium"),
        ("P5", "20×20×512", 4.74, PURPLE, "large"),
    ]
    for name, dims, y, color, role in levels:
        rect(slide, 0.82, y, 2.20, 0.88, CARD, GRID, True)
        textbox(slide, name, 1.04, y + 0.16, 0.56, 0.28, 13, color, True)
        textbox(slide, dims, 1.67, y + 0.16, 1.12, 0.28, 10.5, INK, True, PP_ALIGN.RIGHT, MONO)
        textbox(slide, role, 1.04, y + 0.53, 1.72, 0.18, 8.5, MUTED, True, PP_ALIGN.CENTER)
    # Top-down path.
    textbox(slide, "TOP-DOWN · FPN", 3.52, 1.75, 3.38, 0.25, 10, CYAN, True, PP_ALIGN.CENTER)
    rect(slide, 3.57, 2.15, 3.28, 3.50, BG_2, GRID, True)
    textbox(slide, "P5", 3.88, 4.79, 0.54, 0.25, 11, PURPLE, True)
    arrow(slide, 4.58, 4.45, 0.46, 0.52, PURPLE, "down")
    textbox(slide, "Upsample ×2", 5.17, 4.47, 1.23, 0.24, 9.5, MUTED, True)
    textbox(slide, "Concat với P4", 4.38, 3.58, 1.78, 0.27, 11, CYAN, True, PP_ALIGN.CENTER)
    arrow(slide, 4.58, 3.06, 0.46, 0.52, CYAN, "down")
    textbox(slide, "Concat với P3", 4.38, 2.39, 1.78, 0.27, 11, GREEN, True, PP_ALIGN.CENTER)
    # Bottom up.
    textbox(slide, "BOTTOM-UP · PAN", 7.22, 1.75, 3.38, 0.25, 10, GREEN, True, PP_ALIGN.CENTER)
    rect(slide, 7.27, 2.15, 3.28, 3.50, BG_2, GRID, True)
    textbox(slide, "P3 fused", 8.03, 2.40, 1.75, 0.27, 11, GREEN, True, PP_ALIGN.CENTER)
    arrow(slide, 8.49, 2.88, 0.46, 0.52, GREEN, "down")
    textbox(slide, "Conv s=2 + concat", 7.75, 3.55, 2.18, 0.27, 10.5, CYAN, True, PP_ALIGN.CENTER)
    arrow(slide, 8.49, 4.02, 0.46, 0.52, CYAN, "down")
    textbox(slide, "P5 fused", 8.03, 4.83, 1.75, 0.27, 11, PURPLE, True, PP_ALIGN.CENTER)
    rect(slide, 10.96, 2.08, 1.55, 3.64, CARD, GRID, True)
    textbox(slide, "KẾT QUẢ", 11.20, 2.38, 1.06, 0.24, 9.5, YELLOW, True, PP_ALIGN.CENTER)
    textbox(slide, "mỗi mức có cả\n\nCHI TIẾT\nkhông gian\n\n+\n\nNGỮ NGHĨA\nsâu", 11.16, 2.96, 1.15, 2.33, 9.5, INK, True, PP_ALIGN.CENTER)
    rich(slide, [("P3 không chỉ “nhìn vật nhỏ”. Nó còn nhận ngữ nghĩa từ P5; ", MUTED, False),
                 ("đó là lý do fusion đa tỉ lệ quan trọng.", CYAN, True)],
         1.28, 6.18, 10.82, 0.52, 13.2, PP_ALIGN.CENTER)


def add_head(prs):
    slide = new_slide(prs, "11 · Detection head", "Tại mỗi điểm lưới: một nhánh box, một nhánh class", 13,
                      "Nguồn: Ultralytics Detect head; reg_max=16")
    # Pyramid counts.
    levels = [("P3", "80×80", "6.400", GREEN), ("P4", "40×40", "1.600", CYAN), ("P5", "20×20", "400", PURPLE)]
    y = 1.92
    for name, dims, count, color in levels:
        rect(slide, 0.76, y, 2.18, 0.92, CARD, GRID, True)
        textbox(slide, name, 0.98, y + 0.17, 0.48, 0.26, 12, color, True)
        textbox(slide, dims, 1.54, y + 0.17, 0.96, 0.26, 10.5, INK, True, PP_ALIGN.RIGHT, MONO)
        textbox(slide, count + " điểm", 0.98, y + 0.53, 1.52, 0.20, 8.8, MUTED, False, PP_ALIGN.RIGHT, MONO)
        y += 1.12
    formula(slide, "6.400 + 1.600 + 400 = 8.400 điểm", 0.76, 5.44, 2.85, 0.63, YELLOW, 10.5, YELLOW)

    arrow(slide, 3.85, 3.26, 0.55, 0.60, CYAN)
    rect(slide, 4.62, 2.06, 1.66, 3.68, CARD, GRID, True)
    textbox(slide, "Một điểm", 4.84, 2.37, 1.22, 0.28, 13, CYAN, True, PP_ALIGN.CENTER)
    circle(slide, 5.15, 3.00, 0.60, CYAN)
    textbox(slide, "(i,j)", 5.02, 3.76, 0.86, 0.28, 12, INK, True, PP_ALIGN.CENTER, MONO)
    textbox(slide, "anchor point\n≠ anchor box", 4.84, 4.48, 1.22, 0.54, 9.5, MUTED, True, PP_ALIGN.CENTER)
    arrow(slide, 6.52, 3.26, 0.55, 0.60, CYAN)

    rect(slide, 7.30, 1.92, 2.20, 4.10, CARD, GRID, True)
    pill(slide, "BOX BRANCH", 7.62, 2.25, 1.56, ORANGE)
    textbox(slide, "Conv 3×3\n↓\nConv 3×3\n↓\nConv 1×1",
            7.63, 2.92, 1.55, 1.76, 12, INK, True, PP_ALIGN.CENTER, MONO)
    formula(slide, "4 × 16 = 64", 7.57, 5.04, 1.66, 0.56, ORANGE, 11.5, ORANGE)

    rect(slide, 9.82, 1.92, 2.20, 4.10, CARD, GRID, True)
    pill(slide, "CLASS BRANCH", 10.13, 2.25, 1.58, GREEN)
    textbox(slide, "Conv 3×3\n↓\nConv 3×3\n↓\nConv 1×1",
            10.15, 2.92, 1.55, 1.76, 12, INK, True, PP_ALIGN.CENTER, MONO)
    formula(slide, "nc = 7", 10.09, 5.04, 1.66, 0.56, GREEN, 12, GREEN)

    textbox(slide, "YOLOv8 detect head là anchor-free, decoupled và objectness-free.",
            3.70, 6.33, 8.95, 0.34, 13, INK, True, PP_ALIGN.CENTER)
    pill(slide, "TỔNG / ĐIỂM = 64 + 7 = 71 LOGITS", 4.80, 6.73, 4.30, YELLOW, size=9)


def add_dfl(prs):
    slide = new_slide(prs, "12 · DFL", "Mỗi cạnh box là một phân phối, không phải một số duy nhất", 14,
                      "Nguồn: Generalized Focal Loss; Ultralytics DFL module")
    textbox(slide, "Ví dụ khoảng cách cạnh trái l ∈ {0,…,15}", 0.88, 1.83, 5.42, 0.28, 11, CYAN, True)
    probs = [0.00, 0.00, 0.01, 0.03, 0.09, 0.19, 0.31, 0.22, 0.10, 0.04, 0.01, 0, 0, 0, 0, 0]
    x0, base_y, bw = 0.88, 4.70, 0.37
    for i, p in enumerate(probs):
        h = max(0.04, p * 7.0)
        color = ORANGE if i in (5, 6, 7) else CARD_2
        rect(slide, x0 + i * bw, base_y - h, bw - 0.035, h, color, color, False)
        textbox(slide, str(i), x0 + i * bw, base_y + 0.10, bw - 0.035, 0.18, 7.3, MUTED, False, PP_ALIGN.CENTER, MONO)
    line(slide, x0, base_y, x0 + 16 * bw, base_y, GRID, 1)
    textbox(slide, "softmax(logits)", 2.72, 5.28, 2.14, 0.24, 10, MUTED, True, PP_ALIGN.CENTER, MONO)
    formula(slide, "E[l] = Σᵢ i·pᵢ ≈ 6.24 ô", 1.62, 5.76, 4.40, 0.62, INK, 14, ORANGE)

    rect(slide, 7.26, 1.88, 5.18, 4.38, CARD, GRID, True)
    textbox(slide, "4 CẠNH × 16 BINS", 7.62, 2.18, 4.46, 0.28, 11, YELLOW, True, PP_ALIGN.CENTER)
    sides = [("l", ORANGE), ("t", YELLOW), ("r", GREEN), ("b", CYAN)]
    y = 2.82
    for label, color in sides:
        pill(slide, label, 7.70, y, 0.48, color, size=11)
        for i in range(16):
            v = 38 + int(170 * exp(-((i - (4 + len(label))) ** 2) / 12))
            c = RGBColor(min(255, color[0] * v // 160), min(255, color[1] * v // 160), min(255, color[2] * v // 160))
            rect(slide, 8.38 + i * 0.22, y + 0.04, 0.18, 0.28, c, c, False)
        y += 0.74
    textbox(slide, "Softmax → kỳ vọng → 4 khoảng cách liên tục", 7.68, 5.82, 4.30, 0.24, 10.5, GREEN, True, PP_ALIGN.CENTER)
    rich(slide, [("Lợi ích trực giác: ", MUTED, False),
                 ("biểu diễn được sự không chắc chắn giữa hai giá trị lân cận", CYAN, True),
                 (" và cho tín hiệu học mịn hơn.", MUTED, False)],
         1.05, 6.48, 11.20, 0.44, 12.5, PP_ALIGN.CENTER)


def add_decode(prs):
    slide = new_slide(prs, "13 · Giải mã box", "Từ điểm trên feature map về tọa độ pixel ảnh", 15,
                      "Nguồn: make_anchors(), dist2bbox(), Detect._inference()")
    # Grid visual.
    gx, gy, cell = 0.84, 1.90, 0.57
    for r in range(7):
        for c in range(8):
            rect(slide, gx + c * cell, gy + r * cell, cell - 0.02, cell - 0.02,
                 BG_2 if (r + c) % 2 == 0 else CARD, GRID, False)
    ci, cj = 5, 3
    circle(slide, gx + ci * cell + cell * 0.37, gy + cj * cell + cell * 0.37, 0.18, CYAN)
    outline(slide, gx + 3 * cell, gy + 2 * cell, 3.5 * cell, 3.8 * cell, GREEN, 2)
    textbox(slide, "cell (i=5, j=3)", 1.38, 6.10, 3.30, 0.26, 10.5, MUTED, True, PP_ALIGN.CENTER, MONO)

    rect(slide, 5.92, 1.88, 6.53, 4.82, CARD, GRID, True)
    textbox(slide, "BƯỚC 1 · TỌA ĐỘ ĐIỂM", 6.25, 2.17, 5.85, 0.26, 10, CYAN, True)
    formula(slide, "aₓ=(i+0.5)·s=(5+0.5)·8=44 px", 6.26, 2.58, 5.80, 0.55, INK, 11.3, CYAN)
    formula(slide, "aᵧ=(j+0.5)·s=(3+0.5)·8=28 px", 6.26, 3.25, 5.80, 0.55, INK, 11.3, CYAN)
    textbox(slide, "BƯỚC 2 · DFL DỰ ĐOÁN KHOẢNG CÁCH (đơn vị ô)", 6.25, 4.06, 5.85, 0.26, 10, ORANGE, True)
    formula(slide, "[l,t,r,b] = [2.5, 1.0, 3.0, 4.0]", 6.26, 4.47, 5.80, 0.55, INK, 12.5, ORANGE)
    textbox(slide, "BƯỚC 3 · NHÂN STRIDE VÀ TRỪ / CỘNG", 6.25, 5.28, 5.85, 0.26, 10, GREEN, True)
    formula(slide, "[x₁,y₁,x₂,y₂] = [24,20,68,60] px", 6.26, 5.69, 5.80, 0.62, GREEN, 13, GREEN)
    textbox(slide, "x₁=aₓ−l·s; y₁=aᵧ−t·s; x₂=aₓ+r·s; y₂=aᵧ+b·s",
            1.12, 6.63, 11.18, 0.28, 11, MUTED, True, PP_ALIGN.CENTER, MONO)


def add_class_scores(prs):
    slide = new_slide(prs, "14 · Phân loại", "Logit trở thành xác suất qua sigmoid", 16,
                      "Nguồn: Ultralytics Detect head inference path")
    classes = [
        ("mango_ripe", 2.60, GREEN),
        ("mango_unripe", -0.85, YELLOW),
        ("dragon_ripe", -2.10, RED),
        ("dragon_unripe", -1.72, PURPLE),
        ("apple", -2.65, CYAN),
        ("orange", -3.10, ORANGE),
        ("banana", -2.35, BLUE),
    ]
    y = 1.77
    for label, z, color in classes:
        p = 1 / (1 + exp(-z))
        textbox(slide, label, 0.84, y + 0.10, 2.24, 0.24, 10.5, INK, True)
        textbox(slide, f"z={z:+.2f}", 3.13, y + 0.10, 0.93, 0.24, 9.5, MUTED, False, PP_ALIGN.RIGHT, MONO)
        rect(slide, 4.31, y + 0.08, 5.95, 0.28, BG_2, BG_2, True)
        rect(slide, 4.31, y + 0.08, max(0.04, 5.95 * p), 0.28, color, color, True, 12)
        textbox(slide, f"{p:.3f}", 10.47, y + 0.08, 0.72, 0.24, 10, color, True, PP_ALIGN.RIGHT, MONO)
        y += 0.67
    formula(slide, "p(c|point) = sigmoid(z_c) = 1 / (1 + e^(−z_c))",
            2.05, 6.31, 8.63, 0.62, INK, 14, GREEN)
    rect(slide, 11.52, 1.98, 0.78, 4.35, CARD, GRID, True)
    textbox(slide, "Không có\nsoftmax\n\n→ các lớp\nkhông bị ép\ntổng = 1\n\nKhông có\nobjectness\nriêng", 11.62, 2.35, 0.58, 3.58, 8.7, YELLOW, True, PP_ALIGN.CENTER)


def add_assignment(prs):
    slide = new_slide(prs, "15 · Gán mục tiêu", "Task-Aligned Assigner: điểm nào chịu trách nhiệm học quả này?", 17,
                      "Nguồn: Ultralytics utils/tal.py; TOOD (ICCV 2021)")
    # Candidate grid and GT box.
    gx, gy, cell = 0.74, 1.86, 0.48
    for r in range(9):
        for c in range(10):
            rect(slide, gx + c * cell, gy + r * cell, cell - 0.025, cell - 0.025,
                 BG_2, GRID, False)
            circle(slide, gx + c * cell + 0.18, gy + r * cell + 0.18, 0.08, MUTED)
    outline(slide, gx + 2.2 * cell, gy + 1.6 * cell, 5.7 * cell, 5.2 * cell, GREEN, 2.5)
    positives = [(4, 4), (5, 4), (6, 4), (4, 5), (5, 5), (6, 5), (5, 3), (5, 6)]
    for c, r in positives:
        circle(slide, gx + c * cell + 0.13, gy + r * cell + 0.13, 0.18, YELLOW)
    pill(slide, "GROUND TRUTH", 1.83, 2.22, 1.58, GREEN, size=8)
    textbox(slide, "điểm vàng = positive candidates", 1.10, 6.36, 3.92, 0.25, 10, YELLOW, True, PP_ALIGN.CENTER)

    rect(slide, 5.90, 1.84, 6.58, 4.90, CARD, GRID, True)
    steps = [
        ("1", "Inside GT", "chỉ xét điểm có tâm nằm trong ground-truth box", CYAN),
        ("2", "Alignment metric", "t = s^α · IoU^β, với α=0.5 và β=6", PURPLE),
        ("3", "Top-k", "chọn các điểm có t cao nhất cho mỗi ground truth", YELLOW),
        ("4", "Resolve conflict", "một điểm khớp nhiều GT → giữ GT có overlap phù hợp", ORANGE),
        ("5", "Targets", "tạo target class score, box và foreground mask", GREEN),
    ]
    y = 2.12
    for num, head, body, color in steps:
        circle(slide, 6.20, y + 0.06, 0.39, color)
        textbox(slide, num, 6.20, y + 0.14, 0.39, 0.16, 8, BG, True, PP_ALIGN.CENTER)
        textbox(slide, head, 6.78, y, 1.62, 0.27, 11.5, color, True)
        textbox(slide, body, 8.40, y, 3.66, 0.43, 10, MUTED)
        y += 0.88
    formula(slide, "t = classification_score^0.5 × CIoU^6",
            6.62, 6.27, 5.17, 0.55, INK, 11.2, PURPLE)
    textbox(slide, "Ý nghĩa: điểm positive phải vừa đoán đúng lớp, vừa định vị tốt — hai nhiệm vụ được căn chỉnh.",
            1.05, 6.82, 11.18, 0.27, 11.2, MUTED, True, PP_ALIGN.CENTER)


def add_loss(prs):
    slide = new_slide(prs, "16 · Hàm mất mát", "YOLOv8 học bằng ba tín hiệu sai số", 18,
                      "Nguồn: Ultralytics v8DetectionLoss; BboxLoss")
    losses = [
        ("L_cls", "BCEWithLogits", "Sai lớp bao nhiêu?", "mọi điểm / lớp", GREEN),
        ("L_box", "1 − CIoU", "Box lệch vị trí, tỉ lệ, tâm?", "positive points", CYAN),
        ("L_dfl", "Distribution Focal Loss", "Phân phối 16 bins lệch bao nhiêu?", "positive points", ORANGE),
    ]
    x = 0.74
    for symbol, name, question, scope, color in losses:
        rect(slide, x, 1.97, 3.82, 3.48, CARD, GRID, True)
        textbox(slide, symbol, x + 0.25, 2.20, 1.10, 0.39, 19, color, True, font=MONO)
        textbox(slide, name, x + 0.25, 2.82, 3.30, 0.32, 13.5, INK, True)
        textbox(slide, question, x + 0.25, 3.48, 3.27, 0.50, 11.5, MUTED)
        pill(slide, scope, x + 0.25, 4.58, 1.74, color, size=8)
        x += 4.02
    formula(slide, "L_total = λ_box·L_box + λ_cls·L_cls + λ_dfl·L_dfl",
            1.70, 5.86, 9.92, 0.72, INK, 16, YELLOW)
    textbox(slide, "Loss chỉ dùng khi train. Khi inference, model chỉ forward → decode → threshold → NMS.",
            1.12, 6.80, 11.05, 0.27, 11.5, MUTED, True, PP_ALIGN.CENTER)


def add_backprop(prs):
    slide = new_slide(prs, "17 · Học", "Backpropagation biến lỗi cuối thành thay đổi ở từng kernel", 19)
    stages = [
        ("Forward", "X → ŷ", CYAN),
        ("Loss", "L(ŷ,y)", RED),
        ("Gradient", "∂L/∂W", PURPLE),
        ("Optimizer", "W ← W − η·g", YELLOW),
        ("Lặp lại", "nhiều batch", GREEN),
    ]
    x = 0.66
    for i, (head, eq, color) in enumerate(stages):
        rect(slide, x, 2.04, 2.07, 1.50, CARD, GRID, True)
        textbox(slide, head, x + 0.16, 2.31, 1.75, 0.30, 13, color, True, PP_ALIGN.CENTER)
        textbox(slide, eq, x + 0.16, 2.88, 1.75, 0.28, 11.2, INK, True, PP_ALIGN.CENTER, MONO)
        if i < len(stages) - 1:
            arrow(slide, x + 2.12, 2.53, 0.34, 0.48, GRID)
        x += 2.54
    # Reverse gradient path.
    line(slide, 1.68, 4.33, 11.84, 4.33, PURPLE, 2.2)
    arrow(slide, 0.98, 4.08, 0.62, 0.55, PURPLE, "left")
    textbox(slide, "gradient đi ngược qua chain rule", 4.37, 4.53, 4.58, 0.28, 12, PURPLE, True, PP_ALIGN.CENTER)
    formula(slide, "∂L/∂W₁ = ∂L/∂ŷ · ∂ŷ/∂hₙ · … · ∂h₁/∂W₁",
            2.14, 5.16, 9.04, 0.70, INK, 14, PURPLE)
    rich(slide, [("Một kernel không được lập trình để tìm “cạnh quả”. ", MUTED, False),
                 ("Nó trở thành hữu ích vì các cập nhật gradient lặp đi lặp lại làm loss giảm.", GREEN, True)],
         1.10, 6.24, 11.18, 0.56, 13.2, PP_ALIGN.CENTER)


def add_nms(prs):
    slide = new_slide(prs, "18 · Suy luận", "Từ 8.400 điểm đến vài detection cuối cùng", 20,
                      "Nguồn: Ultralytics prediction post-processing; IoU/NMS")
    steps = [
        ("8.400 điểm", "box + 7 scores", CYAN),
        ("Sigmoid", "xác suất lớp", GREEN),
        ("Threshold", "bỏ score thấp", YELLOW),
        ("Sort", "cao → thấp", ORANGE),
        ("NMS", "bỏ box trùng", PURPLE),
        ("Output", "xyxy + class", RED),
    ]
    x = 0.49
    for i, (head, body, color) in enumerate(steps):
        rect(slide, x, 1.90, 1.77, 1.30, CARD, GRID, True)
        textbox(slide, head, x + 0.10, 2.17, 1.57, 0.30, 11.5, color, True, PP_ALIGN.CENTER)
        textbox(slide, body, x + 0.10, 2.70, 1.57, 0.24, 9.2, MUTED, False, PP_ALIGN.CENTER)
        if i < len(steps) - 1:
            arrow(slide, x + 1.81, 2.34, 0.28, 0.43, GRID)
        x += 2.11
    # NMS visual.
    rect(slide, 0.80, 3.75, 5.12, 2.68, BG_2, GRID, True)
    circle(slide, 2.49, 4.38, 1.10, ORANGE)
    outline(slide, 1.77, 4.05, 2.48, 1.82, GREEN, 3)
    outline(slide, 1.94, 4.18, 2.48, 1.82, CYAN, 2)
    outline(slide, 2.17, 4.02, 2.48, 1.82, PURPLE, 2)
    pill(slide, "0.93", 1.77, 3.76, 0.72, GREEN, size=8)
    pill(slide, "0.88", 2.64, 3.76, 0.72, CYAN, size=8)
    pill(slide, "0.74", 3.51, 3.76, 0.72, PURPLE, size=8)
    textbox(slide, "3 box cùng mô tả một quả", 1.40, 6.05, 3.90, 0.24, 10, MUTED, True, PP_ALIGN.CENTER)
    arrow(slide, 6.23, 4.66, 0.68, 0.65, PURPLE)
    rect(slide, 7.30, 3.75, 5.12, 2.68, BG_2, GRID, True)
    circle(slide, 9.25, 4.38, 1.10, ORANGE)
    outline(slide, 8.53, 4.05, 2.48, 1.82, GREEN, 3)
    pill(slide, "MANGO 0.93", 8.53, 3.76, 1.48, GREEN, size=8)
    textbox(slide, "giữ box score cao nhất; loại box cùng lớp có IoU lớn", 7.83, 6.02, 4.08, 0.30, 9.8, MUTED, True, PP_ALIGN.CENTER)
    formula(slide, "IoU(A,B) = area(A∩B) / area(A∪B)",
            3.70, 6.65, 5.93, 0.52, INK, 12, PURPLE)


def add_end_to_end(prs):
    slide = new_slide(prs, "19 · Tổng hợp", "Theo dấu một quả xoài từ pixel đến kết quả", 21)
    stages = [
        ("01", "Pixel", "[214,98,37]", RED),
        ("02", "Normalize", "[.839,.384,.145]", ORANGE),
        ("03", "Conv/C2f", "feature patterns", YELLOW),
        ("04", "P3/P4/P5", "multi-scale", GREEN),
        ("05", "Head", "64 box + 7 cls", CYAN),
        ("06", "Decode", "[x₁,y₁,x₂,y₂]", BLUE),
        ("07", "Score", "mango=0.93", PURPLE),
        ("08", "NMS", "1 detection", RED),
    ]
    for i, (num, head, body, color) in enumerate(stages):
        # Snake flow: 01→02→03→04, then down to 05←06←07←08.
        if i < 4:
            col, y = i, 1.91
        else:
            col, y = 7 - i, 4.26
        x = 0.72 + col * 3.08
        rect(slide, x, y, 2.55, 1.42, CARD, GRID, True)
        circle(slide, x + 0.18, y + 0.18, 0.42, color)
        textbox(slide, num, x + 0.18, y + 0.27, 0.42, 0.16, 8, BG, True, PP_ALIGN.CENTER)
        textbox(slide, head, x + 0.76, y + 0.19, 1.54, 0.30, 13, INK, True)
        textbox(slide, body, x + 0.20, y + 0.84, 2.15, 0.28, 9.6, color, True, PP_ALIGN.CENTER, MONO)
        if i < 3:
            arrow(slide, x + 2.62, y + 0.43, 0.35, 0.48, GRID)
        elif i == 3:
            arrow(slide, x + 1.02, y + 1.55, 0.50, 0.48, GRID, "down")
        elif i < 7:
            arrow(slide, x - 0.46, y + 0.43, 0.35, 0.48, GRID, "left")
    formula(slide, "YOLO = learned feature extractor + dense predictor + geometric decoding + filtering",
            1.03, 6.35, 11.25, 0.62, INK, 12.5, GREEN)
    textbox(slide, "Không có bước nào “nhận diện bằng mắt”. Mỗi bước là phép biến đổi số học đã được học từ dữ liệu.",
            1.02, 6.98, 11.24, 0.26, 10.8, MUTED, True, PP_ALIGN.CENTER)


def add_summary(prs):
    slide = new_slide(prs, "20 · Kết luận", "Năm ý phải giải thích được khi bị hỏi sâu", 22)
    items = [
        ("01", "Pixel → tensor", "RGB là số; preprocessing tạo B×3×H×W.", RED),
        ("02", "Tensor → feature", "Convolution học kernel; C2f duy trì nhiều đường đặc trưng.", ORANGE),
        ("03", "Feature → đa tỉ lệ", "Backbone giảm H,W; neck hợp nhất chi tiết và ngữ nghĩa.", GREEN),
        ("04", "Điểm → box + class", "Head anchor-free tách regression và classification; DFL dự đoán 4 phân phối.", CYAN),
        ("05", "Học và suy luận", "TAL + 3 loss + backprop khi train; threshold + NMS khi predict.", PURPLE),
    ]
    y = 1.74
    for num, head, body, color in items:
        rect(slide, 0.82, y, 11.70, 0.86, CARD, GRID, True)
        circle(slide, 1.08, y + 0.20, 0.46, color)
        textbox(slide, num, 1.08, y + 0.30, 0.46, 0.17, 8, BG, True, PP_ALIGN.CENTER)
        textbox(slide, head, 1.79, y + 0.16, 2.32, 0.28, 13, color, True)
        textbox(slide, body, 4.20, y + 0.16, 7.90, 0.45, 10.8, MUTED)
        y += 0.98
    pill(slide, "CÂU TRẢ LỜI CỐT LÕI", 4.81, 6.78, 1.93, YELLOW, size=8)
    textbox(slide, "YOLO biến pixel thành đặc trưng, đặc trưng thành phân phối và phân phối thành hình học.",
            2.10, 6.29, 9.14, 0.34, 13.5, INK, True, PP_ALIGN.CENTER)


def add_sources(prs):
    slide = new_slide(prs, "Phụ lục · Nguồn", "Nguồn kỹ thuật dùng để kiểm chứng nội dung", 23)
    sources = [
        ("Kiến trúc YOLOv8", "github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/models/v8/yolov8.yaml", CYAN),
        ("Conv / C2f / SPPF", "github.com/ultralytics/ultralytics/tree/main/ultralytics/nn/modules", GREEN),
        ("Detect head / DFL", "github.com/ultralytics/ultralytics/blob/main/ultralytics/nn/modules/head.py", ORANGE),
        ("TAL / box decoding", "github.com/ultralytics/ultralytics/blob/main/ultralytics/utils/tal.py", PURPLE),
        ("Loss", "github.com/ultralytics/ultralytics/blob/main/ultralytics/utils/loss.py", RED),
        ("YOLO gốc", "Redmon et al., CVPR 2016 — You Only Look Once", YELLOW),
        ("DFL", "Li et al., NeurIPS 2020 — Generalized Focal Loss", BLUE),
        ("Task alignment", "Feng et al., ICCV 2021 — TOOD", CYAN),
    ]
    y = 1.69
    for i, (topic, ref, color) in enumerate(sources):
        x = 0.78 if i < 4 else 6.78
        yy = y + (i % 4) * 1.27
        rect(slide, x, yy, 5.75, 1.02, CARD, GRID, True)
        textbox(slide, topic, x + 0.24, yy + 0.16, 1.64, 0.27, 11.5, color, True)
        textbox(slide, ref, x + 1.94, yy + 0.14, 3.54, 0.56, 8.5, MUTED, False, font=MONO)
    textbox(slide, "Ghi chú phiên bản", 0.84, 6.84, 1.58, 0.22, 9.5, YELLOW, True)
    textbox(slide, "Slide mô tả YOLOv8 detect head cổ điển: anchor-free, decoupled, reg_max=16 và NMS.",
            2.48, 6.80, 9.67, 0.30, 10.5, MUTED, True)


def set_properties(prs):
    props = prs.core_properties
    props.title = "Từ Pixel đến Bounding Box — Cốt lõi YOLOv8"
    props.subject = "Giải thích cơ chế YOLOv8 từ RGB, convolution, feature maps đến loss và NMS"
    props.author = "Machine Learning Group Project"
    props.keywords = "YOLOv8, pixel, convolution, C2f, SPPF, FPN, PAN, DFL, TAL, NMS"
    props.comments = "Editable PowerPoint generated with python-pptx."


def build():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    set_properties(prs)
    for fn in [
        add_cover,
        add_roadmap,
        add_pixel,
        add_preprocess,
        add_convolution,
        add_feature_maps,
        add_conv_block,
        add_stride,
        add_backbone,
        add_c2f,
        add_sppf,
        add_neck,
        add_head,
        add_dfl,
        add_decode,
        add_class_scores,
        add_assignment,
        add_loss,
        add_backprop,
        add_nms,
        add_end_to_end,
        add_summary,
        add_sources,
    ]:
        fn(prs)
    prs.save(OUT)
    print(f"Created {OUT} with {len(prs.slides)} slides")


if __name__ == "__main__":
    build()
