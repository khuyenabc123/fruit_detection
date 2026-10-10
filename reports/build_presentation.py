"""Build the team presentation (PPTX) with detailed speaker notes.

Every number on the slides comes from a file in the project. The main sources:
  .claude/worktrees/gcp-vertex-training/docs/PROJECT_HISTORY.md   (rounds, causes, decisions)
  fruit_detection_runs_gcp_review/<job>/                            (Vertex jobs: args, results, reviews)
  fruit_detection_runs_gcp_review/regression_20261002/              (frozen benchmark, trials A/B/C)
  data/prepared/*/preparation_report.json, data/external/*.json     (dataset versions and audits)
  ../fruit_detection_presentation/eval/summary.json                 (Oct 8 re-test of the live pipeline)

Run from anywhere:  python3 reports/build_presentation.py
Set FRUIT_ROOT to the main checkout when running from a worktree (images live there).
"""

import os
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FRUIT_ROOT", HERE.parents[0]))
OUT = HERE / "Smart_Orchard_AI_Thuyet_trinh_nhom.pptx"
GCP = ROOT / "fruit_detection_runs_gcp_review"
CASES = ROOT.parent / "fruit_detection_presentation" / "assets" / "cases"
V3_PHOTOS = GCP / "4169118715503181824" / "pipeline_check"

# Fill in when the team supplies official details. Do not invent names.
TEAM = "NHÓM: ........................................"
MEMBERS = ["........................................ (MSSV: ................)"]
LECTURER = "........................................"
COURSE = "MÁY HỌC"
YEAR = "2025 – 2026"

NAVY = RGBColor(15, 35, 49)
GREEN = RGBColor(24, 127, 91)
MINT = RGBColor(218, 243, 230)
GOLD = RGBColor(196, 128, 22)
GOLD_SOFT = RGBColor(253, 240, 214)
RED = RGBColor(179, 67, 64)
RED_SOFT = RGBColor(250, 228, 226)
WHITE = RGBColor(255, 255, 255)
INK = RGBColor(31, 48, 58)
MUTED = RGBColor(92, 110, 120)
PALE = RGBColor(244, 248, 246)
LINE = RGBColor(214, 224, 220)
CARD = RGBColor(246, 249, 248)
FONT = "Arial"

SW, SH = 13.333, 7.5


# ---------------------------------------------------------------- helpers

def box(s, x, y, w, h, fill=None, line=None, rounded=True, name=None):
    if fill is None:
        fill, line = CARD, (LINE if line is None else line)
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
                             Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        shp.adjustments[0] = min(0.12, 0.12 * 1.2 / max(h, 0.3))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    if name:
        shp.name = name
    return shp


def _runs(p, text, size, color, bold):
    """Add runs to paragraph p; **x** marks bold segments."""
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        r = p.add_run()
        r.text = part
        f = r.font
        f.name = FONT
        f.size = Pt(size)
        f.bold = bold or (i % 2 == 1)
        f.color.rgb = color


def _bullet(p, size):
    pPr = p._p.get_or_add_pPr()
    indent = int(Pt(size) * 1.0)
    pPr.set("marL", str(indent))
    pPr.set("indent", str(-indent))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    bu = pPr.makeelement(qn("a:buChar"), {"char": "•"})
    pPr.append(bu)


def text(s, content, x, y, w, h, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
         valign=MSO_ANCHOR.TOP, space=4, margin=0.0):
    """content: str with \n between paragraphs; lines starting with '- ' become bullets."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0)
    tf.vertical_anchor = valign
    lines = content.split("\n") if isinstance(content, str) else content
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        if line.startswith("- "):
            _bullet(p, size)
            line = line[2:]
        _runs(p, line, size, color, bold)
    return tb


def new_slide(prs, title, kicker):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = WHITE
    text(s, kicker.upper(), .6, .32, 10, .3, 11, GREEN, True)
    text(s, title, .6, .6, 12.1, .6, 27, NAVY, True)
    text(s, f"SMART ORCHARD AI  •  {len(prs.slides):02d}", .6, 7.08, 6, .25, 9, MUTED)
    return s


def pill(s, label, x, y, color, w=None, size=12):
    w = w or (0.2 + 0.085 * len(label) * size / 12)
    b = box(s, x, y, w, .3, color)
    tf = b.text_frame
    tf.margin_left = tf.margin_right = Inches(.06)
    tf.margin_top = tf.margin_bottom = Inches(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _runs(p, label, size, WHITE, True)
    return b


def card(s, x, y, w, h, label, body, color=GREEN, size=14, fill=None, tag=None):
    box(s, x, y, w, h, fill)
    ty = y + .2
    if tag:
        pill(s, tag, x + .22, ty, color)
        ty += .42
    text(s, label, x + .22, ty, w - .44, .4, 17, color, True)
    text(s, body, x + .22, ty + .5, w - .44, h - (ty - y) - .6, size + 2, INK, space=6)


def stat(s, x, y, w, h, value, label, color=GREEN, fill=None, vsize=34, lsize=13):
    box(s, x, y, w, h, fill)
    text(s, value, x + .1, y + .14, w - .2, h * .5, vsize, color, True, PP_ALIGN.CENTER)
    text(s, label, x + .15, y + h * .55, w - .3, h * .42, lsize, INK, False, PP_ALIGN.CENTER)


def table(s, x, y, w, widths, rows, size=13, row_h=.38, header=NAVY, fills=None, bold_col0=True):
    nr, nc = len(rows), len(rows[0])
    shp = s.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr))
    tbl = shp.table
    tot = sum(widths)
    for j, cw in enumerate(widths):
        tbl.columns[j].width = Emu(int(Inches(w) * cw / tot))
    for i in range(nr):
        tbl.rows[i].height = Inches(row_h)
        for j in range(nc):
            c = tbl.cell(i, j)
            c.margin_left = c.margin_right = Inches(.07)
            c.margin_top = c.margin_bottom = Inches(.035)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            if i == 0:
                c.fill.fore_color.rgb = header
            elif fills and i in fills:
                c.fill.fore_color.rgb = fills[i]
            else:
                c.fill.fore_color.rgb = WHITE if i % 2 else RGBColor(248, 251, 250)
            tf = c.text_frame
            tf.word_wrap = True
            val = str(rows[i][j])
            for k, line in enumerate(val.split("\n")):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                _runs(p, line, size, WHITE if i == 0 else INK, i == 0 or (bold_col0 and j == 0))
    return shp


def picture(s, path, x, y, w, h, caption=None, csize=12):
    from PIL import Image
    path = Path(path)
    if not path.exists():
        box(s, x, y, w, h, RGBColor(230, 236, 234))
        text(s, f"(thiếu ảnh: {path.name})", x + .1, y + h / 2 - .2, w - .2, .4, 11, MUTED,
             align=PP_ALIGN.CENTER)
    else:
        with Image.open(path) as im:
            iw, ih = im.size
        ch = h - (.38 if caption else 0)
        sc = min(w / iw, ch / ih)
        pw, ph = iw * sc, ih * sc
        s.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y + (ch - ph) / 2),
                             Inches(pw), Inches(ph))
    if caption:
        text(s, caption, x, y + h - .33, w, .33, csize, MUTED, False, PP_ALIGN.CENTER)


def bar_chart(s, x, y, w, h, cats, series, fmt='0%', horizontal=False, maxv=None, legend=True,
              label_size=11):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals, _ in series:
        cd.add_series(name, vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.font.name = FONT
    ch.font.size = Pt(11)
    ch.font.color.rgb = INK
    ch.has_title = False
    ch.has_legend = legend and len(series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(12)
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.overlap = -10
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = fmt
    dl.number_format_is_linked = False
    dl.font.size = Pt(label_size)
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for (name, vals, color), ser in zip(series, plot.series):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = color
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = LINE
    va.tick_labels.font.size = Pt(10)
    va.tick_labels.font.color.rgb = MUTED
    va.tick_labels.number_format = fmt
    va.tick_labels.number_format_is_linked = False
    va.format.line.fill.background()
    if maxv is not None:
        va.maximum_scale = maxv
    va.minimum_scale = 0
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(11)
    ca.format.line.color.rgb = LINE
    return gf


def flow(s, steps, y, h=1.35, x0=.6, w_total=12.13, color=GREEN, size=13):
    n = len(steps)
    gap = .32
    w = (w_total - gap * (n - 1)) / n
    for i, (head, body) in enumerate(steps):
        x = x0 + i * (w + gap)
        box(s, x, y, w, h)
        text(s, head, x + .12, y + .14, w - .24, .35, 15, color, True, PP_ALIGN.CENTER)
        text(s, body, x + .12, y + .55, w - .24, h - .6, size, INK, False, PP_ALIGN.CENTER)
        if i < n - 1:
            a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w + .05), Inches(y + h / 2 - .11),
                                   Inches(gap - .1), Inches(.22))
            a.fill.solid(); a.fill.fore_color.rgb = color; a.line.fill.background()


def callout(s, body, y, color=GREEN, fill=MINT, h=.62, size=14, x=.6, w=12.13):
    box(s, x, y, w, h, fill)
    text(s, body, x + .25, y + .1, w - .5, h - .2, size, color if color != GREEN else NAVY,
         False, valign=MSO_ANCHOR.MIDDLE)


def section(prs, number, title, subtitle):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = WHITE
    text(s, f"PHẦN {number}", .9, 2.35, 11, .4, 16, GREEN, True)
    text(s, title, .9, 2.85, 11.5, 1.0, 38, NAVY, True)
    text(s, subtitle, .9, 3.95, 11.5, 1.2, 18, MUTED)
    text(s, f"SMART ORCHARD AI  •  {len(prs.slides):02d}", .6, 7.08, 6, .25, 9, MUTED)
    return s


# ---------------------------------------------------------------- slides

def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SW), Inches(SH)
    notes = []

    def N(t):
        notes.append(t.strip())

    # 1 ── Title
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid(); s.background.fill.fore_color.rgb = WHITE
    text(s, "BÁO CÁO DỰ ÁN MÁY HỌC", .9, .95, 11, .4, 16, GREEN, True)
    text(s, "SMART ORCHARD AI", .9, 1.5, 7.8, .9, 44, NAVY, True)
    text(s, "Nhận diện, đếm và đánh giá độ chín\ncủa xoài và thanh long trên cây\nQuá trình phát triển 12/09 – 08/10/2026", .9, 2.5, 7.6, 1.6, 22,
         INK)
    picture(s, V3_PHOTOS / "user_photo_2.jpg", 9.0, .9, 3.75, 5.6,
            "Kết quả v3: 22 quả trên một trụ thanh long")
    text(s, TEAM, .9, 4.45, 7.6, .4, 17, GREEN, True)
    text(s, "\n".join(MEMBERS) + f"\nGVHD: {LECTURER}\nMôn học: {COURSE}  |  Năm học: {YEAR}",
         .9, 4.95, 11, 1.4, 14, INK)
    N("""
Chào thầy cô và các bạn. Nhóm xin trình bày Smart Orchard AI — hệ thống nhận diện xoài và thanh long trên cây,
đếm số quả và đánh giá độ chín của từng quả từ ảnh, cộng với đếm quả trong video ngắn.

Bài trình bày không chỉ đưa kết quả cuối cùng. Nhóm sẽ kể lại đúng quá trình đã làm từ ngày 12/09 đến 08/10/2026:
mỗi lần huấn luyện dùng dữ liệu gì, ra kết quả bao nhiêu, phát hiện vấn đề gì và vì sao phải chạy lại.
Tổng cộng có 8 dòng huấn luyện trong bảng ở slide 6 (vòng 0, 1, 2, v2, v3, v4, nhóm thử nghiệm A/B/C và bộ lọc loài), 9 phiên bản dữ liệu và 4 lần triển khai Cloud Run.
Mọi số liệu trên slide đều lấy từ file trong dự án: lịch sử dự án docs/PROJECT_HISTORY.md, thư mục kết quả các job
Vertex AI trong fruit_detection_runs_gcp_review, và báo cáo chuẩn bị dữ liệu trong data/prepared.

(Giới thiệu tên nhóm, thành viên và phần việc của từng người — điền sau khi nhóm thống nhất.)
""")

    # 2 ── Agenda
    s = new_slide(prs, "Nội dung trình bày", "tổng quan")
    parts = [
        ("1", "Bài toán", "Đầu ra cần có, phạm vi và tổng quan 8 vòng huấn luyện"),
        ("2", "Detector một bước", "Vòng 0–2: 4 lớp → 7 lớp → đổi sang hai giai đoạn"),
        ("3", "Dữ liệu", "17 nguồn dữ liệu, 9 phiên bản, các lỗi nhãn đã sửa"),
        ("4", "Huấn luyện trên cloud", "v2 → v3 → v4 hỏng → thử nghiệm A/B/C"),
        ("5", "Sản phẩm", "Pipeline suy luận, web/API, triển khai, đánh giá 08/10"),
        ("6", "Kết luận & demo", "Bài học, hạn chế, kịch bản demo"),
    ]
    for i, (n, h, b) in enumerate(parts):
        x = .6 + (i % 3) * 4.1
        y = 1.55 + (i // 3) * 2.65
        box(s, x, y, 3.85, 2.35)
        text(s, n, x + .25, y + .2, .8, .8, 40, GREEN if i % 2 == 0 else GOLD, True)
        text(s, h, x + .25, y + 1.0, 3.4, .45, 19, NAVY, True)
        text(s, b, x + .25, y + 1.48, 3.4, .8, 14, INK)
    N("""
Bài trình bày có 6 phần.
Phần 1 nêu bài toán và bảng tổng hợp 8 vòng huấn luyện để người nghe có bức tranh chung.
Phần 2 kể giai đoạn đầu: một detector YOLOv8s vừa tìm quả vừa đoán độ chín, từ 4 lớp lên 7 lớp, và vì sao ngày 24/09
nhóm quyết định đổi sang kiến trúc hai giai đoạn.
Phần 3 nói về dữ liệu: nhóm dùng những bộ dữ liệu nào, lấy ở đâu, giấy phép gì, đã phát hiện và sửa những lỗi nhãn nào,
và 9 phiên bản dữ liệu thay đổi ra sao.
Phần 4 là các lần huấn luyện trên Google Cloud Vertex AI: v2, v3 — bản đang dùng —, v4 bị hỏng khi lưu checkpoint, và ba
thử nghiệm A, B, C ngày 02/10.
Phần 5 là sản phẩm: pipeline suy luận, web và API, lịch sử triển khai, và đợt đánh giá lại ngày 08/10 phát hiện một lỗi mới.
Phần 6 tổng kết bài học, hạn chế, và kịch bản demo trực tiếp.
""")

    # 3 ── Section 1
    section(prs, 1, "Bài toán", "Hệ thống cần trả lời gì, cho ai, và đã phải huấn luyện bao nhiêu lần")
    N("""
Phần 1: bài toán. Nhóm nói ngắn gọn hệ thống cần làm gì, rồi đưa ra dòng thời gian và bảng tổng hợp các lần huấn luyện.
""")

    # 4 ── Problem
    s = new_slide(prs, "Bài toán: tìm, đếm và đánh giá độ chín từng quả", "bài toán")
    card(s, .6, 1.4, 3.85, 3.9, "Khó khăn ở vườn",
         "- Quả trên cây ảnh chụp cả cây chỉ 10–25 pixel\n- Lá che, quả chồng lên nhau\n"
         "- Ánh sáng thay đổi, có ảnh chụp đêm\n- Quả khác (vải, chôm chôm, mận) trông giống", RED, 14)
    card(s, 4.74, 1.4, 3.85, 3.9, "Đầu ra hệ thống",
         "- Box từng quả + loài (xoài / thanh long)\n- Độ chín: xoài 4 mức, thanh long 3 mức\n"
         "- Nhãn **uncertain** khi chưa đủ tin cậy\n- Số quả theo lớp; video: số quả duy nhất", GREEN, 14)
    card(s, 8.88, 1.4, 3.85, 3.9, "Giới hạn đã chọn",
         "- Chỉ 2 loài quả mục tiêu\n- Ảnh JPG/PNG/WEBP ≤ 12 MB\n- Video ≤ 50 MB, ≤ 30 giây, ≤ 1080p\n"
         "- Hỗ trợ quan sát, không thay kiểm tra tại vườn", GOLD, 14)
    callout(s, "Lớp xoài: young · mature · turning · ripe     |     Lớp thanh long: unripe · ripe · rotten     "
               "|     + mango_uncertain / dragonfruit_uncertain", 5.55, h=.7)
    N("""
Bài toán của nhóm có ba đầu ra: vị trí từng quả, độ chín của từng quả, và số lượng.

Khó khăn chính nằm ở cột bên trái. Khi chụp cả cây, một quả chỉ chiếm 10 đến 25 pixel — đây là con số nhóm đo được ngày 24/09
khi mô hình đầu tiên thất bại. Quả bị lá che, chồng lên nhau, ánh sáng thay đổi, và có những loại quả khác như vải, chôm chôm, mận
trông rất giống.

Cột giữa là đầu ra. Xoài có 4 mức: young (non), mature (già xanh), turning (đang chuyển màu) và ripe (chín). Thanh long có 3 mức:
unripe, ripe, rotten. Điểm quan trọng là nhãn uncertain: khi mô hình chưa đủ tin cậy thì hệ thống nói "chưa chắc" thay vì đoán bừa.
Tên lớp xoài hiện nay là kết quả của lần sửa ngày 29/09 — phần 4 sẽ giải thích vì sao bỏ bộ nhãn cũ.

Cột phải là phạm vi nhóm chọn: chỉ hai loài quả, giới hạn kích thước ảnh 12 MB, video 50 MB và 30 giây. Hệ thống để hỗ trợ quan sát,
chưa thay được việc kiểm tra tại vườn, vì nhóm chưa có ảnh có nhãn từ chính vườn mục tiêu.
""")

    # 5 ── Timeline
    s = new_slide(prs, "Dòng thời gian dự án: 12/09 → 08/10/2026", "quá trình")
    events = [
        ("12/09", "Vòng 0", "YOLOv8s 4 lớp trên Colab", GREEN),
        ("18–20/09", "Vòng 1", "7 lớp; checkpoint bị ghi đè, khôi phục từ Drive", GREEN),
        ("24/09", "Đổi hướng", "Ảnh thật cho kết quả rất tệ → thiết kế hai giai đoạn; Cloud Run đầu tiên", RED),
        ("25–27/09", "Vòng 2", "Huấn luyện hai giai đoạn trên Colab: thất bại", RED),
        ("28/09", "Dữ liệu + v2", "Sửa nhãn, thêm ảnh vườn; chuyển sang Vertex AI", GOLD),
        ("29/09", "v3", "Lớp xoài theo hình thức + ảnh cả cây → bản đang dùng", GREEN),
        ("30/09", "v4", "Checkpoint FP16 hỏng; xoài chín bị mất", RED),
        ("02/10", "A / B / C", "Rà nhãn, 3 thử nghiệm có kiểm soát; giữ v3", GOLD),
        ("03/10", "Triển khai", "Cloud Run chạy v3 + giao diện điện thoại", GREEN),
        ("05–06/10", "Tính năng", "Video, ảnh tối, quét kỹ, bộ lọc quả khác", GREEN),
        ("08/10", "Đánh giá lại", "Bộ lọc xóa nhầm xoài chín → cần huấn luyện lại", RED),
    ]
    col_w = 12.13 / 2 - .15
    for i, (d, h, b, c) in enumerate(events):
        col = 0 if i < 6 else 1
        row = i if i < 6 else i - 6
        x = .6 + col * (col_w + .3)
        y = 1.38 + row * .93
        box(s, x, y, col_w, .8)
        pill(s, d, x + .15, y + .25, c, w=1.15)
        text(s, h, x + 1.45, y + .1, 1.55, .6, 15, NAVY, True, valign=MSO_ANCHOR.MIDDLE)
        text(s, b, x + 3.0, y + .08, col_w - 3.1, .66, 13, INK, valign=MSO_ANCHOR.MIDDLE)
    N("""
Đây là dòng thời gian thực tế, dựng lại từ lịch sử Git, file docs/PROJECT_HISTORY.md và các thư mục kết quả.
Màu xanh là bước thành công, màu vàng là bước sửa/thử nghiệm, màu đỏ là lúc phát hiện thất bại.

Ngày 12/09 nhóm có bản đầu tiên: YOLOv8s 4 lớp. Ngày 18–20/09 nâng lên 7 lớp trên Colab và gặp sự cố checkpoint bị ghi đè.
Ngày 24/09 nhóm thử trên ảnh thật chụp cả cây và kết quả rất tệ — đây là điểm quyết định đổi sang kiến trúc hai giai đoạn.
Ngày 25–27/09 huấn luyện hai giai đoạn trên Colab nhưng thất bại. Ngày 28/09 nhóm dừng huấn luyện để sửa dữ liệu trước,
rồi chuyển huấn luyện lên Google Cloud Vertex AI, ra bản v2.
Ngày 29/09 ra v3 — đây là bản đang chạy trong ứng dụng. Ngày 30/09 bản v4 hỏng vì lỗi lưu checkpoint.
Ngày 02/10 nhóm rà nhãn và chạy ba thử nghiệm A, B, C nhưng không bản nào thay được v3.
Ngày 03/10 triển khai v3 lên Cloud Run. Ngày 05–06/10 thêm video, hỗ trợ ảnh tối, quét kỹ và bộ lọc quả khác.
Ngày 08/10 đánh giá lại toàn bộ và phát hiện bộ lọc quả khác xóa nhầm xoài chín.
""")

    # 6 ── Summary table of training rounds
    s = new_slide(prs, "8 vòng huấn luyện: kết quả và lý do phải chạy lại", "tổng hợp")
    rows = [
        ("Vòng", "Ngày • nơi chạy", "Kết quả chính", "Vấn đề → lý do chạy lại"),
        ("0 · 4 lớp", "12/09 • Colab T4", "Test mAP50 91,3%", "Rò rỉ split: 456 ảnh gốc nằm ở nhiều tập → số ảo"),
        ("1 · 7 lớp", "18–20/09 • Colab", "Val mAP50 85,4%", "Ảnh cả cây: 0–7 quả; detector vừa tìm vừa phân độ chín"),
        ("2 · 2 giai đoạn", "25–27/09 • Colab", "Không còn số liệu", "Polygon đọc thành box; Colab ngắt; nhãn nhiễu"),
        ("v2", "28/09 • Vertex V100", "Det mAP50 98,5%; xoài 63,9%", "Lớp xoài theo tuổi quả; ảnh rộng chỉ thấy 3/~40 quả"),
        ("v3 ✔ đang dùng", "29/09 • Vertex V100", "Det mAP50 94,9%; xoài 90,2%", "Nhận nhầm vải/táo; cụm thanh long dày ~53%"),
        ("v4", "30/09 • Vertex V100", "Val 93,3% → tải lại 31,4%", "Checkpoint FP16 hỏng; xoài chín 11 → 0 quả"),
        ("A / B / C", "02/10 • Vertex V100", "Precision 55% → 66–68%", "Vẫn mất xoài nhỏ/đỏ (11 → 4) → giữ v3"),
        ("Bộ lọc loài", "06/10 • CPU laptop", "Box sai ảnh âm tính 1.103 → 264", "Xóa 24/49 xoài chín → cần huấn luyện lại"),
    ]
    table(s, .6, 1.38, 12.13, [1.7, 2.0, 3.0, 5.4], rows, size=13, row_h=.58,
          fills={5: MINT})
    N("""
Bảng này là xương sống của bài trình bày; các phần sau sẽ đi vào từng dòng.

Vòng 0, ngày 12/09: mAP50 trên test 91,3% nhưng con số này ảo vì 456 ảnh gốc có bản tăng cường nằm ở nhiều tập cùng lúc.
Vòng 1, 18–20/09: 7 lớp, mAP50 validation 85,4%, nhưng trên ảnh cả cây chỉ tìm được 0 đến 7 quả.
Vòng 2: lần đầu thử hai giai đoạn trên Colab, thất bại; sau đó mới phát hiện nhãn polygon của thanh long bị đọc thành box.
v2, ngày 28/09: detector rất cao, 98,5%, nhưng phân loại độ chín xoài chỉ 63,9% vì nhãn xoài được định nghĩa theo số ngày sau
đậu quả — không nhìn thấy được trên ảnh.
v3, ngày 29/09 — dòng tô xanh — là bản đang dùng: detector mAP50 94,9% trên 2.037 ảnh test, xoài 90,2%.
v4 ngày 30/09: lúc huấn luyện đạt 93,3% nhưng tải lại file đã lưu chỉ còn 31,4% vì lỗi FP16.
Ba thử nghiệm A, B, C ngày 02/10 tăng precision từ 55% lên 66–68% nhưng làm mất xoài nhỏ và xoài đỏ, nên nhóm giữ v3.
Cuối cùng, bộ lọc loài thêm ngày 06/10 giảm mạnh box sai trên ảnh không có quả, nhưng xóa nhầm 24 trên 49 xoài chín.

Điểm chung: lần nào chạy lại cũng có một nguyên nhân đo được, không phải chạy lại cho "may mắn".
""")

    # 7 ── Section 2
    section(prs, 2, "Giai đoạn 1: một detector làm mọi việc",
            "Vòng 0 và vòng 1 trên Colab, lần triển khai đầu tiên, và vì sao phải đổi kiến trúc")
    N("""
Phần 2: giai đoạn đầu, khi nhóm dùng một mô hình YOLOv8s duy nhất vừa tìm quả vừa phân loại độ chín.
""")

    # 8 ── Round 0
    s = new_slide(prs, "Vòng 0 (12/09): YOLOv8s 4 lớp — điểm cao nhưng không đáng tin", "vòng 0")
    card(s, .6, 1.4, 5.0, 4.55, "Thiết lập",
         "- 2 bộ Roboflow: xoài (Premature / early / mature / ripe) và thanh long (Unripe / Ripe / Rotten)\n"
         "- Gộp thành 4 lớp: mango_unripe/ripe, dragonfruit_unripe/ripe; bỏ Rotten\n"
         "- YOLOv8s, 30 epoch, Colab T4, AdamW\n"
         "- hsv_h = 0: không xoay màu, vì xoay hue biến xoài xanh thành vàng", GREEN, 14)
    stat(s, 5.85, 1.4, 2.4, 1.6, "91,3%", "mAP50 test\n(714 ảnh)", GREEN)
    stat(s, 8.4, 1.4, 2.0, 1.6, "95,6%", "Precision", GREEN, vsize=28)
    stat(s, 10.55, 1.4, 2.18, 1.6, "85,1%", "Recall", GREEN, vsize=28)
    card(s, 5.85, 3.2, 6.88, 2.75, "Vấn đề phát hiện sau đó",
         "- Bộ xoài có 2.004 ảnh nhưng chỉ từ **926 ảnh gốc**; **456 ảnh gốc** có bản tăng cường nằm ở nhiều split\n"
         "- Xoài vàng sau thu hoạch bị gọi là \"unripe\" (lệch miền dữ liệu)\n"
         "- Ảnh kết quả bị xanh lơ do lẫn BGR/RGB", RED, 14)
    callout(s, "→ Chạy lại: gom nhóm theo ảnh gốc (phần tên trước \".rf.\") rồi mới chia 70/20/10; tách độ chín xoài thành 4 mức",
            6.15, h=.65)
    N("""
Vòng 0 là commit đầu tiên ngày 12/09 (a1e93c4). Nhóm dùng hai bộ dữ liệu xuất từ Roboflow: một bộ xoài có 4 giai đoạn và một bộ thanh long
có Unripe, Ripe, Rotten. Ở vòng này nhóm gộp ba giai đoạn xanh của xoài thành "unripe" và bỏ lớp Rotten, nên chỉ còn 4 lớp.
Có một quyết định giữ từ đầu đến cuối: tắt xoay màu hue khi tăng cường dữ liệu, vì xoay hue biến xoài xanh thành xoài vàng, tức là đổi nhãn độ chín.

Kết quả nhìn rất đẹp: mAP50 91,3%, precision 95,6%, recall 85,1% trên 714 ảnh test.
Nhưng sau đó nhóm phát hiện: bộ xoài có 2.004 ảnh mà chỉ sinh ra từ 926 ảnh gốc — Roboflow tạo nhiều bản xoay, lật của cùng một ảnh.
456 ảnh gốc có bản sao nằm ở cả train và test, nên mô hình được kiểm tra trên ảnh nó đã gần như thấy. Con số 91,3% vì vậy không dùng được.
Ngoài ra xoài vàng sau thu hoạch bị gọi là chưa chín, và ảnh kết quả bị đổi màu xanh lơ do lẫn thứ tự kênh BGR/RGB của OpenCV.

Lý do chạy lại: phải chia dữ liệu theo ảnh gốc — tất cả bản sao có cùng phần tên trước ".rf." phải nằm chung một tập — và nhóm muốn
phân độ chín xoài chi tiết hơn.
""")

    # 9 ── Round 1
    s = new_slide(prs, "Vòng 1 (18–20/09): 7 lớp trên Colab và sự cố mất checkpoint", "vòng 1")
    card(s, .6, 1.4, 3.9, 4.6, "Thiết lập",
         "- 7 lớp: mango_premature / early / mature / ripe; dragonfruit_unripe / ripe / rotten\n"
         "- Ánh xạ nhãn theo **tên**, không theo ID\n- YOLOv8s, 80 epoch, 640 px, batch 16, AdamW, seed 42\n"
         "- ~76 giây/epoch, tổng 1 giờ 39 phút", GREEN, 14)
    card(s, 4.72, 1.4, 4.0, 4.6, "Hai sự cố",
         "- Colab ngắt kết nối, mất checkpoint → ghi thẳng lên Google Drive + ô resume (commit 98348dc)\n"
         "- Một lần chạy nhầm trên **CPU** cùng tên run, exist_ok=True: ghi đè best.pt bằng mô hình 1 epoch "
         "(mAP50 0,027; 8.745 giây/epoch)\n- Khôi phục best.pt 80 epoch từ lịch sử phiên bản của Drive", RED, 14)
    stat(s, 8.95, 1.4, 1.83, 1.45, "85,4%", "mAP50 val", GREEN, vsize=26)
    stat(s, 10.9, 1.4, 1.83, 1.45, "75,2%", "mAP50-95 val", GREEN, vsize=26)
    card(s, 8.95, 3.05, 3.78, 2.95, "Hạn chế",
         "- Chỉ có số validation, không chạy test\n- premature hay bị nhầm với mature\n"
         "- Bài học: kiểm tra có GPU, tên run mới mỗi lần, exist_ok=False", GOLD, 14)
    callout(s, "File còn dùng làm baseline: backend/weights/fruit_yolov8s_7class.pt (PIPELINE_MODE=legacy)", 6.2, h=.6)
    N("""
Vòng 1 từ ngày 18 đến 20/09. Nhóm viết notebook Colab mới với 7 lớp: 4 giai đoạn xoài và 3 trạng thái thanh long, có thêm rotten.
Nhãn từ các bộ dữ liệu được ánh xạ theo tên lớp chứ không theo ID số, vì mỗi bộ đánh ID khác nhau.
Mô hình YOLOv8s, 80 epoch, ảnh 640 pixel, batch 16, mỗi epoch khoảng 76 giây trên GPU.

Có hai sự cố đáng kể. Thứ nhất, Colab miễn phí hay ngắt kết nối và xóa checkpoint, nên nhóm sửa notebook để ghi checkpoint thẳng
lên Google Drive và thêm ô resume — commit 98348dc. Thứ hai, có một lần chạy nhầm trên CPU với cùng tên run và tùy chọn exist_ok=True:
nó chỉ chạy được 1 epoch, mất 8.745 giây, và ghi đè lên best.pt tốt của 80 epoch. Nếu chạy hết trên CPU sẽ mất khoảng 8 ngày.
Nhóm khôi phục được file 80 epoch từ lịch sử phiên bản của Google Drive.

Kết quả: mAP50 validation 85,4%, mAP50-95 75,2%. Lưu ý đây chỉ là số validation, chưa có test. Lớp premature hay bị nhầm với mature.
Bài học rút ra: luôn kiểm tra có GPU trước khi chạy, mỗi lần chạy một tên mới, và không cho phép ghi đè.
File này vẫn được giữ làm baseline, chọn bằng PIPELINE_MODE=legacy.
""")

    # 10 ── First deployment
    s = new_slide(prs, "Triển khai đầu tiên (20–24/09): từ Modal sang Cloud Run", "triển khai")
    flow(s, [
        ("Modal", "Lỗi \"Token missing\", rồi \"spend limit\": gói miễn phí giới hạn $0 khi chưa gắn thẻ"),
        ("Tạm thời", "Backend chạy trên laptop qua Cloudflare quick tunnel — chỉ sống khi laptop bật"),
        ("Cloud Run 24/09", "asia-southeast1, CPU, scale-to-zero; mô hình 7 lớp"),
        ("Kết quả", "/health và /detect chạy; ~7,6 giây/ảnh; revision fruit-detection-00001-z2h"),
    ], 1.5, h=2.1)
    card(s, .6, 3.95, 6.0, 2.3, "Hai lỗi khi deploy Cloud Run",
         "- Service account của Cloud Build không đọc được source → cấp role Cloud Run Builder\n"
         "- Chính sách tổ chức chặn truy cập công khai → --no-invoker-iam-check", RED, 14)
    card(s, 6.83, 3.95, 5.9, 2.3, "Vì sao quan trọng",
         "Có bản chạy thật trên web giúp nhóm thử ảnh thật ngay. Chính lần thử này ngày 24/09 cho thấy "
         "mô hình 7 lớp không dùng được trên ảnh cả cây.", GREEN, 14)
    N("""
Song song với huấn luyện, nhóm cần một bản chạy được trên web để thử ảnh.
Lựa chọn đầu tiên là Modal: lần đầu lỗi "Token missing", lần sau lỗi vượt giới hạn chi tiêu — gói miễn phí của Modal có giới hạn 0 đô
cho đến khi gắn thẻ. Tạm thời nhóm chạy backend trên laptop và mở ra ngoài bằng Cloudflare quick tunnel, nhưng cách này chỉ chạy khi laptop bật.

Ngày 24/09 nhóm triển khai lên Google Cloud Run ở vùng asia-southeast1, chạy CPU và tự tắt khi không có người dùng.
Gặp hai lỗi: service account của Cloud Build không đọc được mã nguồn, phải cấp role Cloud Run Builder; và chính sách tổ chức chặn truy cập công khai,
phải dùng cờ --no-invoker-iam-check. Sau đó /health và /detect chạy, khoảng 7,6 giây mỗi ảnh. Revision này là fruit-detection-00001-z2h,
vẫn giữ để có thể quay lại.

Ý nghĩa: có bản web thật giúp nhóm thử ảnh thật ngay, và chính lần thử ngày 24/09 cho thấy mô hình chưa dùng được — slide tiếp theo.
""")

    # 11 ── 24/09 failure
    s = new_slide(prs, "24/09: thử ảnh thật — \"kết quả rất tệ\"", "phân tích lỗi")
    table(s, .6, 1.4, 6.3, [3.0, 1.1, 1.1, 1.1], [
        ("Ảnh thử (mô hình 7 lớp)", "conf 0,25", "conf 0,80", "conf 0,90"),
        ("Thanh long cận cảnh", "3", "2", "1"),
        ("Cả cây thanh long", "0", "0", "0"),
        ("Cây xoài (hàng chục quả)", "7", "0", "0"),
        ("Xoài chín", "2 (gọi là mature)", "0", "0"),
    ], size=14, row_h=.62)
    text(s, "Số box tìm được ở từng ngưỡng confidence", .6, 4.6, 6.3, .3, 12, MUTED)
    card(s, 7.15, 1.4, 5.58, 4.4, "Ba nguyên nhân tìm được",
         "- **Lệch miền:** dữ liệu là ảnh cận cảnh 640 px; trên ảnh cả cây mỗi quả chỉ 10–25 px\n"
         "- **Confidence chưa hiệu chỉnh:** F1 tốt nhất ở ngưỡng ~0,42, nên đòi 80–90% là mất gần hết box\n"
         "- **Một mô hình làm hai việc:** vừa tìm quả vừa phân 7 mức chín; độ chính xác theo mức chỉ ~56% (premature), "
         "~67% (mature), ~84% (ripe)", RED, 14)
    callout(s, "Quyết định: tách việc tìm quả và việc đánh giá độ chín thành hai mô hình riêng", 6.05, h=.6)
    N("""
Ngày 24/09 nhóm thử mô hình 7 lớp trên 4 ảnh thật. Bảng bên trái là số box tìm được ở ba ngưỡng confidence.
Ảnh thanh long cận cảnh còn tạm được: 3 box. Nhưng ảnh cả cây thanh long: không tìm được quả nào. Cây xoài có hàng chục quả: chỉ 7 box ở
ngưỡng 0,25, và về 0 khi tăng ngưỡng lên 0,8. Ảnh xoài chín thì bị gọi là mature.

Nhóm tìm ra ba nguyên nhân.
Một: lệch miền dữ liệu. Ảnh huấn luyện là ảnh cận cảnh 640 pixel, còn trên ảnh cả cây mỗi quả chỉ 10–25 pixel.
Hai: confidence của YOLO không phải xác suất đã hiệu chỉnh. Ngưỡng cho F1 tốt nhất là khoảng 0,42, nên khi người dùng đòi 80–90% thì gần như mọi box đều bị bỏ.
Ba: một mô hình phải vừa tìm quả vừa phân biệt 7 mức chín. Độ chính xác theo từng mức chỉ khoảng 56% với premature, 67% với mature, 84% với ripe.

Từ đây nhóm quyết định tách bài toán thành hai bước, mỗi bước đo và sửa riêng.
""")

    # 12 ── Two-stage design
    s = new_slide(prs, "Thiết kế mới: pipeline hai giai đoạn (commit f2c43ab, 24/09)", "kiến trúc")
    flow(s, [
        ("Ảnh vào", "Ảnh vườn, xoay đúng EXIF, RGB"),
        ("Detector", "YOLOv8s 2 lớp: mango / dragonfruit; conf thấp 0,25 để không mất quả nhỏ"),
        ("Cắt quả", "Nới box 10%; crop < 64 px → uncertain"),
        ("Classifier", "YOLOv8s-cls riêng cho xoài (4 mức) và thanh long (3 mức)"),
        ("Hiệu chỉnh", "Temperature scaling + ngưỡng riêng từng lớp → nhãn hoặc *_uncertain"),
    ], 1.45, h=2.25, size=13)
    card(s, .6, 4.0, 3.9, 2.35, "Lợi ích", "Mỗi bước có chỉ số riêng: detector đo precision/recall/mAP; classifier đo accuracy trên crop.", GREEN, 14)
    card(s, 4.72, 4.0, 3.9, 2.35, "Dữ liệu dùng được nhiều hơn", "Bộ chỉ có box (MangoYOLO) vẫn dùng cho detector; bộ chỉ có nhãn ảnh (Black_Rot) dùng cho classifier.", GOLD, 14)
    card(s, 8.84, 4.0, 3.89, 2.35, "Trả lời trung thực", "Detector giữ quả ở ngưỡng thấp để đếm; độ chín chỉ hiện khi xác suất hiệu chỉnh đủ cao.", GREEN, 14)
    N("""
Thiết kế mới, commit f2c43ab ngày 24/09, gồm năm bước như trên slide.
Ảnh vào được xoay đúng theo EXIF và chuyển về RGB. Detector YOLOv8s chỉ có hai lớp: xoài và thanh long. Ngưỡng confidence để thấp, 0,25,
vì nhiệm vụ của nó là không bỏ sót quả nhỏ.
Mỗi box được nới rộng 10% rồi cắt ra. Crop nhỏ hơn 64 pixel vẫn được đếm nhưng không đoán độ chín — quy tắc này thêm ngày 02/10.
Crop đi vào classifier riêng theo loài: xoài 4 mức, thanh long 3 mức.
Cuối cùng xác suất được hiệu chỉnh bằng temperature scaling trên một tập calibration riêng, và mỗi lớp có ngưỡng riêng. Nếu không đạt ngưỡng,
nhãn là mango_uncertain hoặc dragonfruit_uncertain.

Ba lợi ích ở hàng dưới. Mỗi bước có chỉ số riêng nên biết lỗi nằm ở đâu. Dùng được nhiều dữ liệu hơn: bộ chỉ có box như MangoYOLO vẫn dùng cho detector,
bộ chỉ có nhãn cả ảnh như Black_Rot vẫn dùng cho classifier. Và hệ thống trả lời trung thực: vẫn đếm quả, nhưng chỉ nói độ chín khi đủ chắc.
""")

    # 13 ── Round 2
    s = new_slide(prs, "Vòng 2 (24–27/09): hai giai đoạn trên Colab — thất bại", "vòng 2")
    card(s, .6, 1.4, 3.9, 4.45, "Đã chạy",
         "- Detector (bước 6A) và classifier xoài (6B) chạy xong\n- Classifier thanh long (6C) lỗi\n"
         "- Dữ liệu mới: MangoYOLO, CQU on-tree, Mendeley thanh long; loại 630/2.127 ảnh thanh long trùng byte", GREEN, 14)
    card(s, 4.72, 1.4, 3.9, 4.45, "Sự cố",
         "- Resume lỗi: Ultralytics đánh dấu run xong bằng epoch = −1 → sửa ở commit 237fd8f\n"
         "- Runtime ngắt; runtime mới không thấy file zip Roboflow trên Drive\n"
         "- 27/09 thử ảnh trên cây: \"terrible\"; log Colab bị mất", RED, 14)
    card(s, 8.84, 1.4, 3.89, 4.45, "Nguyên nhân gốc (28/09)",
         "Bộ thanh long Roboflow \".yolov8\" thực ra chứa **polygon phân đoạn**. Hàm read_yolo_boxes lấy 4 số đầu "
         "của polygon làm x, y, w, h → box và crop đều sai. Mọi checkpoint detector/thanh long trước đó phải bỏ.", GOLD, 14)
    callout(s, "Quyết định 28/09: \"đã huấn luyện nhiều mà vẫn không nhận ra\" → dừng huấn luyện, sửa dữ liệu trước", 6.05, h=.6,
            color=RED, fill=RED_SOFT)
    N("""
Vòng 2 là lần đầu huấn luyện pipeline hai giai đoạn, trên Colab từ 24 đến 27/09.
Nhóm thêm dữ liệu công khai cho detector: MangoYOLO và bộ xoài trên cây của CQUniversity, cùng bộ thanh long của Mendeley; loại 630 trong 2.127 ảnh
thanh long gốc vì trùng từng byte.

Detector và classifier xoài chạy xong, classifier thanh long lỗi. Khi chạy tiếp thì resume hỏng vì Ultralytics đánh dấu run đã xong bằng epoch bằng −1;
nhóm sửa ở commit 237fd8f để nhận ra run đã xong và dùng lại best.pt. Runtime Colab lại ngắt, và runtime mới không tìm thấy file zip trên Drive.
Ngày 27/09 thử trên ảnh trên cây, kết quả vẫn rất tệ. Log của các phiên Colab này bị mất nên không còn số liệu.

Nguyên nhân gốc được tìm ra ngày 28/09: bộ thanh long xuất từ Roboflow ở định dạng ".yolov8" nhưng thực chất chứa polygon phân đoạn.
Code cũ lấy 4 số đầu tiên của polygon làm tọa độ box, nên mọi box và crop thanh long đều sai. Tất cả checkpoint trước đó phải bỏ.

Từ đây nhóm quyết định: dừng huấn luyện, sửa dữ liệu trước. Đó là nội dung phần 3.
""")

    # 14 ── Section 3
    section(prs, 3, "Dữ liệu", "Nguồn dữ liệu, các lỗi nhãn đã phát hiện, và 9 phiên bản dữ liệu")
    N("""
Phần 3: dữ liệu. Đây là phần nhóm tốn công nhất, vì ba vòng huấn luyện thất bại đều do dữ liệu chứ không do mô hình.
""")

    # 15 ── Sources 1
    s = new_slide(prs, "Nguồn dữ liệu (1/2): bộ gốc và bộ thêm ngày 24–28/09", "nguồn dữ liệu")
    table(s, .6, 1.35, 12.13, [3.1, 3.6, 1.35, 4.1], [
        ("Bộ dữ liệu", "Nội dung", "Giấy phép", "Cách dùng"),
        ("Roboflow xoài (export gốc)", "2.004 ảnh từ 926 ảnh gốc; 4 giai đoạn", "CC BY 4.0", "Detector + classifier xoài (mọi phiên bản)"),
        ("Roboflow thanh long (export gốc)", "3.007 ảnh; Unripe/Ripe/Rotten; nhãn polygon", "CC BY 4.0", "Từ v2 chỉ giữ crop quả nổi bật đã rà"),
        ("MangoYOLO — CQUniversity", "1.730 ảnh, 15.281 box, chụp đêm có đèn", "CC BY 4.0", "Chỉ detector (không có độ chín)"),
        ("CQU on-tree mango segmentation", "542 tile tán cây, 5.314 mask", "CC BY 4.0", "Detector: mask → box (536 tile)"),
        ("Mendeley 2jpzbx8tm6 — maturity", "2.127 ảnh gốc Immature/Mature", "CC BY 4.0", "Classifier thanh long; bỏ từ v2"),
        ("Mendeley 2jpzbx8tm6 — quality", "1.652 ảnh Fresh/Defect", "CC BY 4.0", "Không dùng: Fresh/Defect ≠ chín/hỏng"),
        ("DF pose v2 — Mendeley t8kbmg6cgz", "2.448 frame vườn, 4.637 box, từ 7 video", "CC BY 4.0", "Detector thanh long ngoài vườn"),
        ("MangoFruitBD v2 — bhrz29mkmr", "1.070 ảnh xoài ban ngày, 1.841 box", "CC BY-NC", "Detector; chỉ dùng phi thương mại"),
    ], size=13, row_h=.56)
    N("""
Slide này và slide sau liệt kê toàn bộ nguồn dữ liệu nhóm đã dùng, theo đúng file data/external/datasets.json và các báo cáo kiểm toán.

Hai bộ đầu là hai export từ Roboflow dùng từ ngày đầu. Bộ xoài 2.004 ảnh nhưng chỉ từ 926 ảnh gốc. Bộ thanh long 3.007 ảnh, nhãn thực chất là polygon.
MangoYOLO của CQUniversity có 1.730 ảnh và 15.281 box, chụp ban đêm có đèn chiếu — rất tốt cho detector nhưng không có nhãn độ chín.
Bộ phân đoạn xoài trên cây của CQU có 542 tile; nhóm đổi mask thành box.
Hai bộ thanh long của Mendeley: bộ maturity có 2.127 ảnh gốc, dùng cho classifier ở vòng 2 rồi bỏ ở v2 vì crop từ Roboflow tốt hơn;
bộ quality có nhãn Fresh/Defect thì không dùng, vì "tươi/khuyết tật" không phải "chín/hỏng" — đây là quy tắc nhóm giữ suốt dự án.
Ngày 28/09 thêm hai bộ ảnh vườn thật: DF pose v2 với 2.448 frame thanh long lấy từ 7 video, và MangoFruitBD với 1.070 ảnh xoài ban ngày.
Lưu ý MangoFruitBD có giấy phép phi thương mại CC BY-NC, nên mô hình từ v2 trở đi chỉ dùng cho học tập.
""")

    # 16 ── Sources 2
    s = new_slide(prs, "Nguồn dữ liệu (2/2): ảnh cả cây, quả hỏng và ảnh âm tính", "nguồn dữ liệu")
    table(s, .6, 1.35, 12.13, [3.25, 3.55, 1.35, 4.0], [
        ("Bộ dữ liệu", "Nội dung", "Giấy phép", "Cách dùng • từ phiên bản"),
        ("DF-MOD Black_Rot — kpsywfwkrf", "675 file nhưng chỉ 270 ảnh khác nhau", "CC BY 4.0", "thanh long rotten • v2"),
        ("Mendeley gcgrjvwmm2 far-field", "1.023 ảnh xoài chụp xa/gần", "CC BY 4.0", "Detector, nhóm 10 ảnh liên tiếp • v3"),
        ("Mendeley mm8g66d7rc ripening", "951 ảnh xoài chín dần trên bàn", "chưa ghi", "Classifier: stage 2 → turning • v3"),
        ("Roboflow mango-tree (jerng-mi)", "690 ảnh cả cây, ~13 quả/ảnh", "CC BY 4.0", "Detector • v3"),
        ("Roboflow pitaya \"goodgoodgood\"", "992 ảnh hàng thanh long", "CC BY 4.0", "Detector • v3"),
        ("Roboflow ripe-dragon-fruits", "97 ảnh cả trụ thanh long", "CC BY 4.0", "Detector • v3"),
        ("Roboflow thanh-long-detection", "5.534 ảnh; 19 tên lớp lộn xộn", "CC BY 4.0", "Detector • v4 (C: giới hạn 600)"),
        ("10 nguồn ảnh âm tính", "1.428 ảnh vải, chôm chôm, lựu, táo, cà chua, hoa thanh long", "CC BY / MIT", "Ảnh không có quả • v4"),
        ("Wikimedia Commons", "11 ảnh xoài đỏ/trên cây, tự gán box", "CC0 / BY / BY-SA", "Detector • recovery C"),
    ], size=13, row_h=.52)
    N("""
Nhóm dữ liệu thứ hai được thêm dần theo từng vấn đề.
DF-MOD Black_Rot thêm ngày 28/09 để có quả thanh long hỏng thật: 675 file nhưng kiểm tra hash chỉ có 270 ảnh khác nhau — 405 bản là bản sao y hệt.
Ngày 29/09, để sửa lỗi không tìm được quả trên ảnh cả cây, nhóm thêm bốn nguồn: bộ xoài chụp xa gcgrjvwmm2 của Mendeley 1.023 ảnh;
Roboflow mango-tree 690 ảnh cả cây, trung bình khoảng 13 quả mỗi ảnh; Roboflow pitaya 992 ảnh hàng thanh long; và 97 ảnh trụ thanh long chín.
Cũng ngày 29/09 thêm bộ Mendeley mm8g66d7rc gồm 951 ảnh xoài chín dần đặt trên bàn, dùng cho classifier để có lớp turning;
giấy phép bộ này chưa được ghi trong file của dự án, nhóm cần bổ sung.
Ngày 30/09, cho v4, thêm bộ thanh-long-detection 5.534 ảnh — bộ này có tới 19 tên lớp lộn xộn như "thanhlongchin", "Class_A", "0", "16",
tất cả được gộp thành dragonfruit — và 1.428 ảnh âm tính: vải, chôm chôm, lựu, táo, cà chua, hoa thanh long, để dạy mô hình đâu không phải quả.
Cuối cùng, cho thử nghiệm C ngày 02/10, thêm 11 ảnh xoài từ Wikimedia Commons do nhóm tự vẽ box.
""")

    # 17 ── 28/09 data fixes
    s = new_slide(prs, "28/09: những lỗi dữ liệu đã tìm và sửa", "làm sạch dữ liệu")
    fixes = [
        ("Polygon đọc thành box", "Đổi mỗi polygon thành box bao ngoài; kiểm tra tọa độ trong [0,1]; bỏ box diện tích 0.", RED),
        ("Nhãn thanh long nhiễu", "145 nhãn mâu thuẫn với nguồn, 703 box < 1% ảnh; cuống xanh gán Unripe, mảnh vụn gán Rotten → chỉ giữ quả nổi bật, crop ≥ 64 px.", RED),
        ("Thiếu ảnh ngoài vườn", "Thêm DF pose v2 (2.448 frame) và MangoFruitBD (1.070 ảnh); frame cùng một video luôn nằm chung một tập.", GOLD),
        ("Thiếu quả hỏng thật", "Black_Rot: 675 file → 270 ảnh duy nhất (bỏ 405 bản sao), gom 3 cặp chụp cùng quả.", GOLD),
    ]
    for i, (h, b, c) in enumerate(fixes):
        x = .6 + (i % 2) * 6.17
        y = 1.4 + (i // 2) * 2.12
        card(s, x, y, 5.96, 1.95, h, b, c, 14)
    callout(s, "Cổng sẵn sàng: mỗi lớp cần ≥ 80 nhóm ảnh gốc ở train và ≥ 20 ở val/calib/test, nếu không script từ chối huấn luyện. "
               "Kết quả maturity_v2: detector 10.438 ảnh, classifier xoài 2.534 crop, thanh long 1.416 crop; 22 test pass.",
            5.75, h=.95)
    N("""
Ngày 28/09 nhóm dừng huấn luyện và rà lại dữ liệu. Bốn lỗi chính:

Một, polygon bị đọc thành box: sửa bằng cách đổi mỗi polygon thành hình chữ nhật bao ngoài, kiểm tra tọa độ nằm trong 0 đến 1, bỏ box diện tích 0.
Hai, nhãn thanh long nhiễu: kiểm toán tìm ra 145 box có nhãn độ chín mâu thuẫn với nhãn của chính ảnh gốc, và 703 box nhỏ hơn 1% diện tích ảnh.
Xem trực tiếp thì thấy cuống xanh bị gán Unripe, mảnh vụn bị gán Rotten. Cách sửa: chỉ giữ quả nổi bật — box lớn nhất chiếm ít nhất 10% ảnh,
cạnh ngắn ít nhất 64 pixel — còn ảnh mâu thuẫn thì cách ly.
Ba, thiếu ảnh ngoài vườn: thêm DF pose và MangoFruitBD; mọi frame của cùng một video phải nằm chung một tập để không rò rỉ.
Bốn, thiếu quả hỏng thật: thêm Black_Rot, loại 405 bản sao, và gom 3 cặp ảnh chụp cùng một quả từ hai góc.

Nhóm cũng thêm một "cổng sẵn sàng": mỗi lớp phải có ít nhất 80 nhóm ảnh gốc trong train và 20 trong mỗi tập val, calib, test, nếu không script không cho huấn luyện.
Kết quả là bộ maturity_v2 với 10.438 ảnh detector, 2.534 crop xoài, 1.416 crop thanh long; 22 test tự động đều pass.
""")

    # 18 ── Data versions
    s = new_slide(prs, "9 phiên bản dữ liệu: số ảnh và thay đổi", "phiên bản dữ liệu")
    table(s, .6, 1.35, 12.13, [2.7, .85, 2.25, 6.33], [
        ("Phiên bản", "Ngày", "Detector train/val/test", "Thay đổi chính và lý do"),
        ("two_stage_public", "24/09", "1.570 / 354 / 342", "Chỉ có box xoài; lỗi polygon chưa phát hiện"),
        ("orchard_v1", "28/09", "7.522 / 1.610 / 1.663", "Thêm DF pose, MangoFruitBD; chia frame theo video"),
        ("maturity_v2", "28/09", "7.272 / 1.556 / 1.610", "Rà thanh long; cách ly 1.406 nhãn Fresh/Defect; Black_Rot"),
        ("maturity_v3 ✔", "29/09", "9.231 / 1.972 / 2.037", "+2.802 ảnh cả cây; lớp xoài theo hình thức — bản đang dùng"),
        ("detector_v4", "30/09", "14.094 / 3.016 / 3.077", "+5.534 thanh-long, +1.428 ảnh âm tính; 3 ảnh test rò rỉ"),
        ("v5_audit (A)", "02/10", "13.551 / 2.735 / 2.819", "Cách ly 1.082 ảnh có split/nhãn mâu thuẫn"),
        ("v5 không âm tính giống (B)", "02/10", "13.278 / 2.735 / 2.819", "A bỏ 273 ảnh táo/lựu/cà chua"),
        ("v5_label_review", "02/10", "12.255 / 2.735 / 2.819", "Bỏ 1.604 box trùng; chưa đủ điều kiện huấn luyện"),
        ("v5_recovery_c (C)", "02/10", "9.183 / 2.735 / 2.819", "50 nhãn sửa ×4, 11 ảnh xoài ×16, thanh-long ≤ 600"),
    ], size=13, row_h=.5, fills={4: MINT})
    N("""
Bảng này liệt kê 9 phiên bản dữ liệu, số liệu lấy từ preparation_report.json của từng thư mục trong data/prepared.

two_stage_public ngày 24/09 chỉ có box xoài — detector lúc đó thực tế không có box thanh long nào. orchard_v1 ngày 28/09 thêm ảnh vườn.
maturity_v2 cùng ngày là bản đã rà nhãn thanh long; 1.406 ảnh mang nhãn quality bị cách ly.
maturity_v3 ngày 29/09 — dòng tô xanh — là dữ liệu của mô hình đang dùng: 9.231 ảnh train, 1.972 val, 2.037 test cho detector;
classifier xoài 2.688 train, 351 val, 235 calibration, 234 test; classifier thanh long giữ như v2: 958, 196, 131, 131.
detector_v4 ngày 30/09 tăng lên hơn 20 nghìn ảnh, và cũng là lúc phát hiện 3 ảnh test có bản sao trong train.
Ngày 02/10 có bốn phiên bản cho các thử nghiệm: A cách ly 1.082 ảnh có lịch sử chia tập hoặc nhãn mâu thuẫn; B giống A nhưng bỏ 273 ảnh táo, lựu, cà chua;
bản label_review loại 1.604 box trùng nhưng bị đánh dấu chưa sẵn sàng vì phải bỏ quá nhiều ảnh thanh long ngoài vườn;
và C với 50 ảnh sửa nhãn được lặp 4 lần mỗi epoch, 11 ảnh xoài mới lặp 16 lần, giới hạn bộ thanh-long còn 600 ảnh.
Quan trọng: từ A trở đi, tập val và test được giữ y hệt từng byte để so sánh công bằng.
""")

    # 19 ── Quality rules in code
    s = new_slide(prs, "Quy tắc chất lượng được viết thành code", "kiểm soát dữ liệu")
    rules = [
        ("Chống rò rỉ", "rf_group_id gom mọi bản \".rf.\" của một ảnh gốc; assert_no_group_leakage dừng nếu một nhóm nằm ở hai tập"),
        ("Bản sao gần giống", "dHash 64-bit (cả ảnh lật) lệch ≤ 4 bit + so màu thu nhỏ; cụm có nhãn khác nhau bị cách ly"),
        ("Quả nổi bật", "dominant_fruit: box lớn nhất ≥ 10% ảnh, cạnh ≥ 64 px, tỉ lệ 0,25–4, các box khác nằm trong nó"),
        ("Nhãn đúng nghĩa", "curate_dragon: nhãn box phải khớp nhãn nguồn; Fresh/Defect không bao giờ thành ripe/rotten"),
        ("Đủ dữ liệu mới train", "MIN_GROUPS = 80 / 20 / 20 / 20 nhóm mỗi lớp; thiếu thì \"BLOCKED\""),
        ("Giữ màu", "hsv_h = 0 và tắt auto_augment của classifier, vì màu chính là tín hiệu độ chín"),
    ]
    for i, (h, b) in enumerate(rules):
        y = 1.38 + i * .9
        box(s, .6, y, 12.13, .78)
        pill(s, f"{i + 1}", .8, y + .24, GREEN if i % 2 == 0 else NAVY, w=.4)
        text(s, h, 1.4, y + .1, 2.7, .6, 15, NAVY, True, valign=MSO_ANCHOR.MIDDLE)
        text(s, b, 4.15, y + .08, 8.4, .64, 14, INK, valign=MSO_ANCHOR.MIDDLE)
    N("""
Các bài học về dữ liệu không chỉ nằm trong báo cáo mà được viết thành code trong training/prepare_two_stage_data.py và training/maturity_data.py.

Một, chống rò rỉ: hàm rf_group_id gom mọi bản sao Roboflow của cùng một ảnh gốc; assert_no_group_leakage dừng chương trình nếu một nhóm nằm ở hai tập.
Hai, bản sao gần giống: nhóm tính dấu vân tay dHash 64 bit, kể cả ảnh lật; hai ảnh lệch không quá 4 bit và màu thu nhỏ gần giống thì coi là một nhóm.
Nếu trong một cụm có nhãn khác nhau thì cả cụm bị cách ly.
Ba, chỉ lấy quả nổi bật cho classifier: box lớn nhất phải chiếm ít nhất 10% ảnh, cạnh ít nhất 64 pixel, tỉ lệ cạnh từ 0,25 đến 4.
Bốn, nhãn phải đúng nghĩa: nhãn box phải khớp nhãn nguồn, và nhãn Fresh/Defect không bao giờ được đổi thành chín/hỏng.
Năm, đủ dữ liệu mới được train: thiếu nhóm thì script báo BLOCKED.
Sáu, giữ màu: tắt xoay hue và tắt auto_augment của classifier, vì auto_augment tự thêm biến đổi màu làm vô hiệu cấu hình hsv_h bằng 0.
""")

    # 20 ── Section 4
    section(prs, 4, "Huấn luyện trên Google Cloud",
            "v2 → v3 (bản đang dùng) → v4 hỏng → ba thử nghiệm có kiểm soát A / B / C")
    N("""
Phần 4: các lần huấn luyện trên Google Cloud Vertex AI. Với mỗi lần, nhóm trình bày cấu hình, kết quả và lý do chạy lại.
""")

    # 21 ── Why Vertex
    s = new_slide(prs, "Vì sao chuyển sang Vertex AI (28/09)", "hạ tầng")
    stat(s, .6, 1.4, 2.85, 1.75, "7–14 giờ", "một lần huấn luyện đầy đủ trên Colab T4", RED, vsize=30)
    stat(s, 3.7, 1.4, 2.85, 1.75, "0 GPU", "quota Compute Engine của tài khoản Free Trial", RED, vsize=30)
    stat(s, 6.8, 1.4, 2.85, 1.75, "$5–10", "mỗi lần chạy 4–5 giờ trên Spot V100", GREEN, vsize=30)
    stat(s, 9.9, 1.4, 2.83, 1.75, "₫5,78 triệu", "tín dụng Free Trial — ngân sách duy nhất", GOLD, vsize=26)
    card(s, .6, 3.4, 6.0, 3.25, "Cách làm (scripts/gcp/)",
         "- Tải bộ dữ liệu đã chuẩn bị lên Cloud Storage một lần (file .tar)\n"
         "- Gửi Vertex AI custom job: 1 × V100 Spot, n1-standard-8, giới hạn 24 giờ\n"
         "- Checkpoint mỗi epoch lên bucket → job bị thu hồi vẫn chạy tiếp\n"
         "- Script trạng thái hiện epoch và log", GREEN, 14)
    card(s, 6.83, 3.4, 5.9, 3.25, "Chi phí",
         "- Spot V100 ~$0,75–1,00/giờ so với $2,48/giờ thường\n"
         "- Giới hạn 24 giờ: tối đa ~$30/lần nếu lỗi\n"
         "- Thử nghiệm A/B/C chỉ 10 epoch, giới hạn 2 giờ\n"
         "- Lỗi nhỏ đã sửa: Vertex từ chối biến môi trường rỗng (027ef31)", GOLD, 14)
    N("""
Sau ba vòng trên Colab, nhóm thấy Colab không phù hợp: một lần huấn luyện đầy đủ cần 7 đến 14 giờ trên T4 và không thể chạy mà không có người trông.
Tài khoản Google Cloud Free Trial có quota GPU của Compute Engine bằng 0, nên không tạo được máy ảo GPU. Nhưng Vertex AI có quota Spot riêng cho T4, V100, A100.
Ngân sách duy nhất là tín dụng Free Trial khoảng 5,78 triệu đồng, hết hạn ngày 10/12.

Nhóm viết bộ script trong scripts/gcp: tải bộ dữ liệu đã chuẩn bị lên Cloud Storage một lần, gửi job Vertex AI chạy trên một GPU V100 dạng Spot, giới hạn 24 giờ.
Checkpoint được ghi lên bucket sau mỗi epoch, nên nếu Google thu hồi máy Spot thì job chạy tiếp từ epoch cuối.
Spot V100 giá khoảng 0,75 đến 1 đô mỗi giờ, so với 2,48 đô bình thường; một lần chạy 4–5 giờ tốn khoảng 5 đến 10 đô.
Các thử nghiệm A, B, C sau này chỉ chạy 10 epoch với giới hạn 2 giờ để tiết kiệm.
""")

    # 22 ── v2
    s = new_slide(prs, "v2 (28/09): detector tốt, độ chín xoài chưa dùng được", "vòng 3 · v2")
    text(s, "Job 4689768257580695552 • maturity_v2 • YOLOv8s 100 epoch, 960 px, batch 8 • YOLOv8s-cls 50 epoch, 320 px, batch 32 • 3 giờ 9 phút",
         .6, 1.3, 12.1, .3, 13, MUTED)
    stat(s, .6, 1.75, 2.9, 1.55, "98,5%", "Detector mAP50 test\n(mAP50-95 80,9%)", GREEN, vsize=30)
    stat(s, 3.7, 1.75, 2.9, 1.55, "100%", "Thanh long 131/131", GREEN, vsize=30)
    stat(s, 6.8, 1.75, 2.9, 1.55, "63,9%", "Xoài 92/144 crop test", RED, vsize=30)
    stat(s, 9.9, 1.75, 2.83, 1.55, "18/144", "xoài có nhãn chắc chắn", RED, vsize=30)
    card(s, .6, 3.5, 4.0, 2.85, "Lỗi ngưỡng (29/09)",
         "Ngưỡng làm tròn 6 chữ số: 0,9999997868 → 1,0 nên loại crop thanh long đúng. Sửa bằng float64 + xử lý hòa → 128/131 lên 131/131.", GOLD, 14)
    card(s, 4.8, 3.5, 3.9, 2.85, "Ảnh chụp rộng",
         "Cả trụ thanh long: 3/~40 quả. Cây xoài: 8 quả. Quét kích thước ảnh 640–1600 px không giúp → lỗi dữ liệu, không phải tham số.", RED, 14)
    card(s, 8.9, 3.5, 3.83, 2.85, "Vì sao xoài thất bại",
         "Bộ \"Mango Growth Stages\" chia premature/early/mature theo **số ngày sau đậu quả**, không nhìn thấy trên ảnh. Gộp chín/chưa chín: 97,9%.", RED, 14)
    N("""
v2 là lần đầu trên Vertex AI, job 4689768257580695552, ngày 28/09 từ 20 giờ đến 23 giờ 09, tổng 3 giờ 9 phút.
Detector YOLOv8s 100 epoch, ảnh 960 pixel; hai classifier YOLOv8s-cls 50 epoch, ảnh 320 pixel. Classifier xoài dừng sớm ở epoch 43.

Kết quả: detector mAP50 98,5% trên test, thanh long đúng 131 trên 131. Nhưng xoài chỉ đúng 63,9%, tức 92 trên 144 crop.

Ngày 29/09 nhóm kiểm tra kỹ và tìm ra ba vấn đề.
Một, lỗi ngưỡng: ngưỡng được làm tròn 6 chữ số, nên 0,9999997868 thành 1,0 và loại cả những crop thanh long đúng. Sửa bằng cách giữ đủ độ chính xác float64
và xử lý trường hợp bằng nhau; có test riêng trong training/test_calibration_thresholds.py. Thanh long được nhận từ 128 lên 131 trên 131.
Hai, ngưỡng của premature và mature bị đặt bằng 1,0 vì không mức nào đạt precision 80%, nên chỉ 18 trên 144 quả xoài có nhãn — còn lại là uncertain.
Ba, ảnh chụp rộng: cả trụ thanh long chỉ thấy 3 trong khoảng 40 quả. Nhóm thử nhiều kích thước ảnh từ 640 đến 1600 pixel nhưng không cải thiện —
nghĩa là thiếu dữ liệu, không phải chỉnh tham số.

Nguyên nhân xoài: bộ Mendeley chia giai đoạn theo số ngày sau khi đậu quả. Các quả xanh này nhìn y hệt nhau. Khi gộp về chín/chưa chín, mô hình đã đúng 97,9% —
nó học tốt cái nhìn thấy được; nhãn mới là vấn đề.
""")

    # 23 ── v3 changes
    s = new_slide(prs, "Chuẩn bị v3 (29/09): nhãn theo cái nhìn thấy + ảnh cả cây", "vòng 4 · v3")
    table(s, .6, 1.4, 6.2, [2.2, 4.0], [
        ("Lớp xoài v3", "Lấy từ"),
        ("mango_young", "premature + early cũ (đều xanh nhỏ)"),
        ("mango_mature", "mature cũ + ripening stage 0 và 1"),
        ("mango_turning (mới)", "ripening stage 2 — bắt đầu vàng"),
        ("mango_ripe", "ripe cũ + ripening stage 3"),
    ], size=14, row_h=.6)
    text(s, "Stage 1 \"Early Ripe\" nhìn giống stage 0 nên gộp vào mature.", .6, 4.55, 6.2, .5, 13, MUTED)
    card(s, 7.05, 1.4, 5.68, 3.6, "Dữ liệu ảnh cả cây cho detector",
         "- Mendeley far-field xoài: 1.023 ảnh\n- Roboflow mango-tree: 690 cây, ~13 quả/ảnh\n"
         "- Roboflow pitaya orchard: 992 ảnh\n- Ripe dragon plants: 97 ảnh\n"
         "- Mỗi ảnh Roboflow chỉ giữ 1 bản gốc", GREEN, 14)
    stat(s, .6, 5.2, 3.0, 1.2, "13.240", "ảnh detector (+27%)", NAVY, vsize=26)
    stat(s, 3.8, 5.2, 3.0, 1.2, "36.861", "box huấn luyện (+60%)", NAVY, vsize=26)
    callout(s, "Backend và frontend cập nhật theo tên lớp mới (commit f4ccdd2 … 67cf444)", 5.2, h=1.2, x=7.05, w=5.68)
    N("""
Từ hai nguyên nhân của v2, nhóm sửa đúng hai chỗ cho v3.

Một, đổi định nghĩa lớp xoài theo cái nhìn thấy trên ảnh. Bảng bên trái: young là premature và early cũ, vì đều xanh nhỏ; mature giữ nguyên;
thêm lớp mới turning cho quả bắt đầu ngả vàng; ripe là quả chín. Để có quả turning, nhóm thêm bộ Mendeley 951 ảnh xoài chín dần:
stage 0 và 1 vào mature — stage 1 "Early Ripe" khi xem trực tiếp không khác stage 0 —, stage 2 vào turning, stage 3 vào ripe.

Hai, thêm dữ liệu ảnh cả cây cho detector: 1.023 ảnh xoài chụp xa, 690 ảnh cây xoài, 992 ảnh hàng thanh long và 97 ảnh trụ thanh long.
Mỗi ảnh Roboflow chỉ giữ một bản gốc thay vì cả bản tăng cường.

Kết quả: bộ detector tăng từ 10.438 lên 13.240 ảnh, tăng 27%, và số box tăng 60% lên 36.861. Backend và frontend được cập nhật tên lớp mới.
""")

    # 24 ── v3 vs v2 results
    s = new_slide(prs, "v3 (29/09, job 4169118715503181824): cải thiện rõ trên ảnh cả cây", "vòng 4 · v3")
    bar_chart(s, .5, 1.3, 7.3, 4.6,
              ["Cả cây xoài", "Hàng thanh long", "Trụ thanh long", "Xoài chụp xa"],
              [("v2", [.063, .252, .117, .63], RGBColor(170, 184, 190)),
               ("v3", [.86, .916, .532, .765], GREEN)], maxv=1.0)
    text(s, "Recall detector trên cùng ảnh test (40 ảnh/nguồn)", .6, 5.95, 7.2, .3, 12, MUTED)
    stat(s, 8.05, 1.4, 2.25, 1.4, "90,2%", "xoài đúng\n(v2: 63,9%)", GREEN, vsize=26)
    stat(s, 10.48, 1.4, 2.25, 1.4, "179/234", "xoài có nhãn chắc\n(174 đúng)", GREEN, vsize=24)
    picture(s, V3_PHOTOS / "user_photo_2.jpg", 8.05, 3.0, 2.25, 3.3, "Trụ thanh long: 3 → 22")
    picture(s, V3_PHOTOS / "user_photo_3.jpg", 10.48, 3.0, 2.25, 3.3, "Cây xoài: 8 → 46")
    N("""
v3 chạy ngày 29/09 từ 16 giờ 48 đến 20 giờ 42, job 4169118715503181824, cùng cấu hình với v2 — chỉ đổi dữ liệu. Vì vậy so sánh v2 và v3 cho thấy đúng tác dụng của dữ liệu.

Biểu đồ là recall của detector trên cùng các ảnh test, 40 ảnh mỗi nguồn. Ảnh cả cây xoài từ 6% lên 86%. Hàng thanh long từ 25% lên 92%.
Trụ thanh long từ 12% lên 53% — tiến bộ lớn nhưng vẫn là điểm yếu. Xoài chụp xa từ 63% lên 77%.

Bên phải: classifier xoài từ 63,9% lên 90,2%; số quả có nhãn chắc chắn từ 18 trên 144 lên 179 trên 234, trong đó 174 đúng.
Hai ảnh thật của nhóm: trụ thanh long từ 3 lên 22 quả, cây xoài từ 8 lên 46 quả. Trên ảnh cây xoài nhiều quả có nhãn uncertain vì quá nhỏ hoặc chưa đủ tin cậy —
đó là hành vi mong muốn.
""")

    # 25 ── v3 details
    s = new_slide(prs, "Chi tiết v3 — mô hình đang chạy trong ứng dụng", "vòng 4 · v3")
    table(s, .6, 1.4, 6.0, [2.2, 1.2, 1.2, 1.4], [
        ("Detector test (2.037 ảnh, 7.468 box)", "P", "R", "mAP50 / 50-95"),
        ("Tất cả", "92,2%", "88,3%", "94,9 / 68,3"),
        ("Xoài", "92,6%", "86,6%", "94,2 / 66,4"),
        ("Thanh long", "91,8%", "90,0%", "95,6 / 70,1"),
    ], size=13, row_h=.55)
    text(s, "Epoch tốt nhất 86/100 • thời gian 3 giờ 54 phút • V100 Spot", .6, 3.65, 6.0, .3, 12, MUTED)
    table(s, .6, 4.1, 6.0, [2.2, 1.9, 1.9], [
        ("Classifier xoài (234 test)", "Đúng / tổng", "Ngưỡng lớp"),
        ("young", "64 / 74", "0,46"),
        ("mature", "76 / 87", "0,44"),
        ("turning", "24 / 24", "0,82"),
        ("ripe", "47 / 49", "0,54"),
    ], size=13, row_h=.44)
    card(s, 6.85, 1.4, 5.88, 2.55, "Hiệu chỉnh xác suất",
         "- Xoài: T = 2,154 trên 235 crop calibration; ECE 0,071 → 0,034\n"
         "- Thanh long: T = 0,050; ECE 0,004 → 0; ngưỡng ≈ 1,0 vì tập calibration tách biệt hoàn toàn", GREEN, 14)
    card(s, 6.85, 4.1, 5.88, 2.2, "Cần nói rõ",
         "Thanh long 100% (131/131) trên tập đã tuyển chọn, T rất nhỏ → mô hình có thể dựa cả vào nền ảnh. Chưa có ảnh độc lập từ vườn mục tiêu.", RED, 14)
    N("""
Đây là chi tiết của v3, mô hình đang chạy. Các file trong backend/weights khớp với job này: hash của detector.pt trùng với best.pt của job,
và hai file calibration khớp từng trường.

Detector trên 2.037 ảnh test với 7.468 box: precision 92,2%, recall 88,3%, mAP50 94,9%, mAP50-95 68,3%. Thanh long tốt hơn xoài một chút.
Epoch tốt nhất là 86 trên 100. mAP thấp hơn v2 vì tập test v3 có thêm ảnh cả cây khó hơn — không phải mô hình kém đi.

Classifier xoài: turning đúng 24 trên 24, ripe 47 trên 49, mature 76 trên 87, young 64 trên 74. Lỗi chủ yếu là nhầm young và mature — hai lớp đều xanh.
Ngưỡng từng lớp được chọn trên tập calibration để đạt precision khoảng 80%: turning cần 0,82, các lớp khác từ 0,44 đến 0,54.

Hiệu chỉnh: xoài có nhiệt độ T bằng 2,154, nghĩa là mô hình gốc quá tự tin và được làm "mềm" lại; sai số hiệu chỉnh ECE giảm từ 0,071 xuống 0,034.
Thanh long có T bằng 0,05 và ngưỡng gần 1,0 vì tập calibration tách biệt hoàn toàn.
Nhóm phải nói rõ: con số 100% của thanh long là trên tập đã tuyển chọn; nhiều khả năng mô hình dựa cả vào nền ảnh, và chưa có ảnh độc lập từ vườn thật.
""")

    # 26 ── Internet check / v3 weaknesses
    s = new_slide(prs, "30/09: thử v3 trên ảnh Internet và ảnh không có quả", "kiểm tra v3")
    card(s, .6, 1.4, 3.9, 4.0, "Làm tốt (37 ảnh Wikimedia)",
         "- Tìm thấy xoài ở 10/11 ảnh có xoài (31 quả trên một cây đông)\n- Xoài vàng chín: đúng nhãn\n"
         "- Thanh long trên trụ: đúng\n- Gần như không báo nhầm lá, hoa, nhà", GREEN, 14)
    card(s, 4.72, 1.4, 3.9, 4.0, "Lỗi mới",
         "- Vải bị gọi là thanh long\n- Hoa thanh long → quả xanh\n"
         "- Xoài đỏ: uncertain\n- Xoài xanh cận cảnh hay uncertain", RED, 14)
    bar_chart(s, 8.75, 1.3, 4.0, 4.2, ["Vải VN", "Litchi", "Táo", "Chôm chôm", "Lựu"],
              [("Box sai", [214, 174, 73, 27, 22], RED)], fmt='0', horizontal=True, legend=False)
    text(s, "Box sai của v3 trên ảnh âm tính", 8.85, 5.5, 3.9, .3, 12, MUTED)
    callout(s, "→ Lý do làm v4: thêm ảnh âm tính (quả giống), thêm ảnh trụ thanh long dày quả, tăng độ phân giải 1280 px",
            5.95, h=.6)
    N("""
Ngày 30/09 nhóm thử v3 trên 37 ảnh lấy từ Wikimedia Commons với từ khóa "thanh long", "xoài", "dragon fruit plant", "mango tree", và xem bằng mắt.
Phần làm tốt: tìm thấy xoài ở 10 trên 11 ảnh có xoài, có ảnh tới 31 quả; xoài vàng chín được gọi đúng; thanh long trên trụ đúng; gần như không báo nhầm lá, hoa hay nhà cửa.

Phần lỗi: vải bị gọi là thanh long — vì mô hình chỉ biết hai loại quả nên cái gì đỏ tròn cũng phải là một trong hai. Hoa thanh long bị gọi là quả xanh.
Xoài đỏ và xoài xanh cận cảnh hay bị uncertain.

Biểu đồ bên phải là số box sai của v3 trên các bộ ảnh không có xoài hay thanh long: 214 box trên ảnh vải Việt Nam, 174 trên litchi, 73 trên táo.
Đây là lý do làm v4: thêm ảnh âm tính, thêm ảnh trụ thanh long dày quả, và tăng độ phân giải lên 1280 pixel.
""")

    # 27 ── v4
    s = new_slide(prs, "v4 (30/09): job \"thành công\" nhưng mô hình hỏng", "vòng 5 · v4")
    card(s, .6, 1.4, 3.9, 4.15, "Thay đổi (cùng lúc)",
         "- 20.187 ảnh (+5.534 thanh-long, +1.428 ảnh âm tính)\n- 1280 px thay vì 960\n"
         "- Fine-tune từ v3, 50 epoch, lr0 = 0,01\n- 4,07 giờ, ~293 giây/epoch", GOLD, 14)
    stat(s, 4.72, 1.4, 1.9, 1.6, "93,3%", "mAP50 val lúc train", GREEN, vsize=26)
    stat(s, 6.72, 1.4, 1.9, 1.6, "31,4%", "mAP50 khi tải lại best.pt", RED, vsize=26)
    card(s, 4.72, 3.2, 3.9, 2.35, "Nguyên nhân",
         "Lưu checkpoint ở FP16: **27 phương sai BatchNorm** bão hòa ở 65.504 (giá trị lớn nhất của FP16). Thanh long test mAP50 còn 0,011.", RED, 14)
    card(s, 8.84, 1.4, 3.89, 4.15, "Kể cả bản sửa",
         "- Ước lượng lại BatchNorm → vẫn mất xoài: ảnh 11 quả → 0, xoài đỏ 10 → 5\n"
         "- 76/830 ảnh test có ảnh gần giống trong train\n- Đổi nhiều thứ cùng lúc → không biết cái nào gây lỗi", RED, 14)
    callout(s, "Sửa: checkpoint FP32 (định dạng fruit-fp32-v1), kiểm tra dự đoán giống hệt sau khi lưu/tải lại, guard d4b85a1. Giữ v3.",
            5.8, h=.65)
    N("""
v4 chạy ngày 30/09, job 5533271247212773376, chỉ huấn luyện lại detector. Nhóm đổi nhiều thứ cùng lúc: dữ liệu tăng lên 20.187 ảnh với bộ thanh-long và 1.428 ảnh âm tính,
độ phân giải 1280 pixel, fine-tune từ v3 trong 50 epoch với learning rate khởi đầu lại 0,01. Chạy 4,07 giờ.

Job báo thành công, và lúc huấn luyện mAP50 validation đạt 93,3%. Nhưng khi tải lại file best.pt đã lưu, mAP50 chỉ còn 31,4%, thanh long trên test còn 1,1%.
Nguyên nhân: checkpoint được lưu ở độ chính xác FP16. 27 giá trị phương sai trong các lớp BatchNorm của đầu ra vượt quá giá trị lớn nhất FP16 là 65.504 nên bị cắt.
Mọi giá trị vẫn hữu hạn nên kiểm tra "không có NaN" không phát hiện ra.

Nhóm thử ước lượng lại các giá trị BatchNorm. Bản sửa tốt hơn trên số tổng, nhưng vẫn mất xoài: một ảnh v3 tìm được 11 quả, v4 tìm 0; ảnh xoài đỏ từ 10 còn 5.
Ngoài ra kiểm tra dấu vân tay ảnh tìm thấy 76 trên 830 ảnh test có ảnh gần giống trong train.
Và vì đổi quá nhiều thứ cùng lúc, nhóm không biết thay đổi nào gây lỗi xoài.

Bài học: job chạy xong không có nghĩa là mô hình dùng được. Nhóm chuyển sang lưu FP32, kiểm tra dự đoán trước và sau khi lưu phải giống hệt — commit d4b85a1 — và giữ v3.
""")

    # 28 ── Recovery Oct 2
    s = new_slide(prs, "02/10: chuẩn bị đánh giá công bằng trước khi thử tiếp", "phục hồi")
    card(s, .6, 1.4, 3.9, 4.6, "Checkpoint an toàn",
         "- best.pt FP32 + last.pt giữ optimizer và EMA\n- Kiểm tra tensor hữu hạn, BatchNorm hợp lệ, dự đoán giống hệt sau khi tải lại\n"
         "- Smoke test CPU: ngắt sau epoch 0, resume, xong epoch 2", GREEN, 14)
    card(s, 4.72, 1.4, 3.9, 4.6, "Benchmark cố định",
         "- 234 ảnh val, 584 quả, 112 ảnh không có quả\n- 960 px, conf 0,25, IoU 0,5\n"
         "- Hash ảnh + nhãn được kiểm tra mỗi lần chạy\n- Thêm bộ ảnh thật của nhóm làm ảnh hồi quy", GOLD, 14)
    card(s, 8.84, 1.4, 3.89, 4.6, "Thử chia ô 512 px → tắt",
         "- Precision 55,3% → 39,2%\n- Box sai trên ảnh âm tính 290 → 538\n- Chỉ thêm 6 quả đúng\n"
         "- 44 test pass; frontend build/lint pass", RED, 14)
    callout(s, "Tiêu chí đặt trước khi thử: chỉ thay v3 nếu mô hình mới lấy lại được các ảnh xoài bị mất", 6.2, h=.6)
    N("""
Ngày 02/10, trước khi huấn luyện tiếp, nhóm làm ba việc để không lặp lại lỗi v4.

Một, checkpoint an toàn: lưu best.pt ở FP32 và last.pt giữ trạng thái optimizer để resume; khi lưu phải kiểm tra tensor hữu hạn, BatchNorm hợp lệ,
và dự đoán trước, sau khi lưu giống hệt. Nhóm chạy thử trên CPU: cố ý ngắt sau epoch 0, resume, và chạy xong epoch 2.

Hai, một benchmark cố định: 234 ảnh validation với 584 quả và 112 ảnh không có quả, chạy ở 960 pixel, ngưỡng 0,25, IoU 0,5.
Hash của ảnh và nhãn được kiểm tra mỗi lần, để mọi mô hình được so trên đúng một bộ. Cộng thêm các ảnh thật của nhóm làm ảnh hồi quy.

Ba, nhóm thử chia ảnh thành ô 512 pixel để tìm quả nhỏ. Kết quả xấu: precision giảm từ 55,3% xuống 39,2%, box sai tăng từ 290 lên 538, chỉ thêm 6 quả đúng. Nên tắt.

Và nhóm đặt tiêu chí trước khi thử: mô hình mới chỉ thay v3 nếu lấy lại được các ảnh xoài bị mất.
""")

    # 29 ── Trials A/B/C setup + audit
    s = new_slide(prs, "Thử nghiệm A / B / C (02/10): mỗi lần đổi một yếu tố dữ liệu", "vòng 6")
    table(s, .6, 1.38, 7.0, [1.0, 2.1, 3.9], [
        ("Thử", "Job • thời gian", "Dữ liệu khác nhau"),
        ("A", "5756784368953589760\n33 phút", "Dữ liệu đã kiểm toán, có ảnh âm tính (13.551 ảnh train)"),
        ("B", "2208933025004126208\n32 phút", "Như A nhưng bỏ 273 ảnh táo/lựu/cà chua"),
        ("C", "3521406860940804096\n~26 phút", "50 nhãn sửa ×4, 11 ảnh xoài mới ×16, thanh-long ≤ 600"),
    ], size=13, row_h=.85)
    text(s, "Chung: fine-tune từ v3, 10 epoch, 960 px, batch 8, lr0 = 0,0001, seed 42, V100 Spot, giới hạn 2 giờ; val/test giống hệt từng byte",
         .6, 4.88, 7.0, .7, 12, MUTED)
    card(s, 7.85, 1.38, 4.88, 4.0, "Rà nhãn 603 ảnh train (tối 02/10)",
         "- 5 ảnh \"không có quả\" thật ra có xoài\n- 12 ảnh thiếu/sai box\n"
         "- 28 ảnh \"hoa thanh long đêm\" là tranh vẽ\n- 1.604 box trùng trong 290 ảnh\n"
         "- Tỉ lệ ảnh có xoài giảm 53% → 36%", GOLD, 14)
    callout(s, "Sự cố trước khi chạy C: Ultralytics tự \"sửa\" một JPEG lỗi bằng cách ghi đè file — file đó được hard-link vào 5 bộ dữ liệu. "
               "Kiểm tra hash phát hiện, khôi phục bản gốc rồi mới chạy.", 5.6, h=.85, color=RED, fill=RED_SOFT, size=13)
    N("""
Ngày 02/10 nhóm chạy ba thử nghiệm có kiểm soát. Cả ba đều fine-tune detector v3 trong 10 epoch, 960 pixel, learning rate rất nhỏ 0,0001, cùng seed,
và tập val/test giống nhau từng byte. Chỉ dữ liệu train khác nhau.

A dùng dữ liệu đã kiểm toán có ảnh âm tính. B giống A nhưng bỏ 273 ảnh táo, lựu, cà chua — để kiểm tra giả thuyết ảnh quả đỏ âm tính làm mất xoài đỏ.
Giữa A và B, nhóm rà bằng mắt 603 ảnh train và tìm ra: 5 ảnh ghi là không có quả nhưng thật ra có xoài; 12 ảnh thiếu hoặc sai box;
28 ảnh của nguồn "hoa thanh long ban đêm" thực ra là tranh vẽ; 1.604 box bị trùng; và tỉ lệ ảnh có xoài trong train đã giảm từ 53% xuống 36% khi thêm bộ thanh-long.
Từ đó tạo C: sửa 50 ảnh và lặp chúng 4 lần mỗi epoch, thêm 11 ảnh xoài đỏ và trên cây từ Wikimedia lặp 16 lần, giới hạn bộ thanh-long còn 600 ảnh,
để tỉ lệ ảnh có xoài về lại 53%.

Trước khi chạy C có một sự cố: khi kiểm tra cục bộ, Ultralytics gặp một file JPEG bị cắt và tự "sửa" bằng cách ghi đè lên file. File đó được hard-link vào 5 bộ dữ liệu,
nên cả 5 thay đổi cùng lúc. Bước kiểm tra hash phát hiện, nhóm khôi phục bản gốc rồi mới gửi job.
""")

    # 30 ── A/B/C results
    s = new_slide(prs, "Kết quả A / B / C: precision tăng nhưng mất xoài → giữ v3", "vòng 6")
    bar_chart(s, .5, 1.3, 6.0, 3.0, ["v3", "A", "B", "C"],
              [("Precision", [.553, .6635, .647, .6775], GREEN),
               ("Recall", [.8253, .8271, .8253, .8236], NAVY)], maxv=1.0)
    text(s, "Benchmark cố định 234 ảnh • box sai trên 112 ảnh âm tính: v3 290 • A 161 • B 177 • C 142",
         .6, 4.35, 6.0, .55, 12, MUTED)
    table(s, 6.75, 1.38, 5.98, [2.5, .8, .8, 1.1, .8], [
        ("Ảnh hồi quy (số box)", "v3", "A", "B", "C"),
        ("Cụm xoài chín nhỏ", "11", "4", "4", "4"),
        ("Xoài đỏ trên cây", "10", "5", "5 + 2 sai", "7"),
        ("Cả trụ thanh long", "22", "15", "13", "14"),
        ("Thanh long cận cảnh", "3", "3", "3", "2"),
        ("Cây xoài", "46", "38", "38", "41"),
    ], size=13, row_h=.5)
    callout(s, "Quyết định: không bản nào thay v3 — tiêu chí \"lấy lại ảnh xoài\" không đạt. Hạ ngưỡng xuống 0,05 vẫn không vượt "
               "~53% recall xoài trên cây → vấn đề dữ liệu, không phải ngưỡng.", 5.1, h=.95, size=14)
    N("""
Kết quả trên benchmark cố định: precision tăng rõ, từ 55,3% của v3 lên 66 đến 68% với A, B, C, recall giữ khoảng 82,5%.
Box sai trên 112 ảnh không có quả giảm từ 290 xuống 161, 177 và 142. Nếu chỉ nhìn số tổng thì C là tốt nhất.

Nhưng bảng bên phải là các ảnh hồi quy. Cụm xoài chín nhỏ: v3 tìm 11, cả ba bản mới chỉ 4. Xoài đỏ trên cây: v3 10, A và B còn 5, B còn gọi nhầm 2 quả xoài đỏ là thanh long.
Trụ thanh long và cây xoài cũng giảm.

Theo tiêu chí đã đặt trước, không bản nào thay v3. Nhóm còn quét ngưỡng confidence từ 0,05 đến 0,4: với nguồn xoài trên cây, recall không bao giờ vượt khoảng 53%
dù hạ ngưỡng — nghĩa là mô hình không thấy những quả này, chứ không phải ngưỡng quá cao.
Giả thuyết còn lại: khoảng 560 ảnh âm tính vải, litchi, chôm chôm trông giống cụm xoài đỏ nhỏ. Đây là giả thuyết cần kiểm chứng, chưa phải kết luận.
""")

    # 31 ── Section 5
    section(prs, 5, "Sản phẩm", "Pipeline suy luận, web/API, lịch sử triển khai và đánh giá lại ngày 08/10")
    N("""
Phần 5: sản phẩm mà người dùng thực sự dùng — pipeline suy luận, giao diện, API và các lần triển khai.
""")

    # 32 ── Inference pipeline details
    s = new_slide(prs, "Pipeline suy luận hiện tại: từ ảnh đến nhãn", "suy luận")
    steps = [
        ("Detector", "YOLOv8s v3 ở 960 px, conf ≥ 0,25; ảnh nhỏ chỉ phóng to tối đa ~2 lần"),
        ("Bộ lọc loài", "YOLOv8n-cls 224 px (mango / dragonfruit / other); loại box có P(other) ≥ 0,90"),
        ("Cắt quả", "Nới 10%; cạnh < 64 px → *_uncertain, lý do crop_too_small (vẫn được đếm)"),
        ("Độ chín", "Classifier theo loài 320 px → chia logit cho T → ngưỡng = max(ngưỡng người dùng, ngưỡng lớp)"),
        ("Ảnh tối", "low_light_assist: CLAHE kênh L (clip 2,0, ô 8×8) chỉ cho detector; độ chín dùng màu gốc"),
        ("Quét kỹ", "detailed_scan: ảnh ≥ 1280 px, NMS IoU 0,5, test-time augmentation"),
    ]
    for i, (h, b) in enumerate(steps):
        y = 1.38 + i * .9
        box(s, .6, y, 12.13, .78)
        pill(s, f"{i + 1}" if i < 4 else "tùy chọn", .8, y + .24, GREEN if i < 4 else GOLD, w=1.0)
        text(s, h, 2.0, y + .1, 2.0, .6, 15, NAVY, True, valign=MSO_ANCHOR.MIDDLE)
        text(s, b, 4.05, y + .08, 8.5, .64, 14, INK, valign=MSO_ANCHOR.MIDDLE)
    N("""
Đây là pipeline đang chạy, đọc từ backend/two_stage.py.

Bước 1: detector v3 ở 960 pixel, ngưỡng 0,25. Ảnh rất nhỏ chỉ được phóng to tối đa khoảng 2 lần để tránh làm méo.
Bước 2: bộ lọc loài — một YOLOv8n-cls nhỏ ảnh 224 pixel với ba lớp xoài, thanh long và "quả khác". Box nào có xác suất "quả khác" từ 0,9 trở lên bị loại.
Bộ lọc này thêm ngày 06/10 và đang có lỗi — slide 37 sẽ nói.
Bước 3: cắt quả, nới 10%. Crop nhỏ hơn 64 pixel vẫn được đếm nhưng nhãn độ chín là uncertain với lý do crop_too_small.
Bước 4: classifier theo loài ảnh 320 pixel; logit chia cho nhiệt độ T rồi softmax; nhãn chỉ được nhận nếu xác suất vượt cả ngưỡng người dùng chọn và ngưỡng riêng của lớp.

Hai tùy chọn: hỗ trợ ảnh tối dùng CLAHE trên kênh độ sáng L, chỉ đưa ảnh đã tăng sáng cho detector, còn classifier vẫn nhìn màu gốc để không làm sai độ chín.
Quét kỹ chạy detector ở ít nhất 1280 pixel với test-time augmentation, dùng cho ảnh nhiều quả chồng nhau.
""")

    # 33 ── Architecture & API
    s = new_slide(prs, "Kiến trúc ứng dụng và API", "hệ thống")
    flow(s, [
        ("React + Ant Design", "Vite; tải ảnh/video, 2 thanh trượt ngưỡng, 2 công tắc"),
        ("FastAPI", "Kiểm tra định dạng, kích thước, EXIF; điều phối"),
        ("Ultralytics 8.4.155", "PyTorch CPU; detector, verifier, 2 classifier"),
        ("ByteTrack", "Theo dõi ID quả trong video (thư viện lap)"),
    ], 1.4, h=1.55)
    table(s, .6, 3.3, 12.13, [2.1, 10.0], [
        ("Endpoint", "Tham số chính → kết quả"),
        ("GET /health", "pipeline_mode (two-stage / legacy), model_loaded, detector_imgsz, other_fruit_filter, model_classes"),
        ("POST /detect", "ảnh ≤ 12 MB; conf_threshold 0,25; ripeness_threshold 0,80; low_light_assist; detailed_scan → "
                         "total_count, counts, detections[], ảnh JPEG base64"),
        ("POST /detect-video", "mp4/mov/webm/avi ≤ 50 MB, ≤ 30 giây, ≤ 1080p → total_unique_count, counts, khung hình minh họa"),
        ("GET /docs", "Swagger UI tự sinh từ FastAPI"),
    ], size=13, row_h=.56)
    N("""
Kiến trúc gồm bốn khối. Frontend React với Ant Design, build bằng Vite: người dùng tải ảnh hoặc video, chỉnh hai thanh ngưỡng và bật hai công tắc.
Backend FastAPI kiểm tra định dạng, kích thước, xoay ảnh theo EXIF, rồi gọi pipeline. Mô hình chạy bằng Ultralytics 8.4.155 trên PyTorch CPU.
Video dùng ByteTrack để nối box giữa các khung hình thành từng ID.

Bảng là các endpoint. /health cho biết đang chạy chế độ two-stage hay legacy và bộ lọc quả khác có bật không — khi demo luôn mở endpoint này trước.
/detect nhận ảnh tối đa 12 MB với các tham số ngưỡng và hai tùy chọn, trả về tổng số, số theo lớp, danh sách box với nhãn, độ tin cậy, lý do uncertain, và ảnh đã vẽ box.
/detect-video nhận video tối đa 50 MB, 30 giây, 1080p, trả về số quả duy nhất. /docs là Swagger để thử API trực tiếp.
""")

    # 34 ── Deployment history
    s = new_slide(prs, "Lịch sử triển khai Cloud Run (asia-southeast1)", "triển khai")
    table(s, .6, 1.38, 12.13, [1.25, 2.5, 8.38], [
        ("Ngày", "Revision / tag", "Nội dung và lý do"),
        ("24/09", "00001-z2h", "Mô hình 7 lớp; ~7,6 giây/ảnh; giữ lại để rollback"),
        ("03/10", "00003-hat • v3-mobile", "v3 + giao diện điện thoại. Sửa Dockerfile thiếu module, thêm .gcloudignore để không bỏ sót weight; "
                                          "deploy_cloud_run.sh: revision không nhận traffic → smoke test → PROMOTE=1"),
        ("03/10", "00005-yap • v3-ui-fix", "Người dùng đọc \"Độ chín 72,4%\" là \"chín 72%\" → thẻ ghi \"Model nghiêng về: Xoài non · tin cậy 72,4% (cần ≥ 80%)\"; "
                                          "ngưỡng mặc định giao diện 0,55"),
        ("06–08/10", "fix4", "v3 + bộ lọc loài + video ByteTrack + ảnh tối + quét kỹ"),
    ], size=13, row_h=.85)
    stat(s, .6, 5.55, 2.9, 1.25, "1,4–1,8 s", "mỗi ảnh (cây xoài 46 quả, trụ thanh long 22)", GREEN, vsize=22, lsize=12)
    stat(s, 3.7, 5.55, 2.9, 1.25, "572 MiB", "RAM tối đa; giới hạn 1 CPU, 2 GiB", NAVY, vsize=22, lsize=12)
    callout(s, "Lưu ý: .dockerignore hiện chưa cho phép species_verifier.pt — build mới sẽ mất bộ lọc nếu không thêm dòng này",
            5.55, h=1.25, x=6.8, w=5.93, color=RED, fill=RED_SOFT, size=13)
    N("""
Lịch sử triển khai lên Cloud Run, vùng asia-southeast1.

Ngày 24/09 là bản 7 lớp, revision 00001-z2h, giữ lại để có thể rollback bằng một lệnh.
Ngày 03/10 triển khai v3 cùng giao diện điện thoại. Có hai lỗi suýt làm hỏng lần deploy: Dockerfile chỉ copy app.py và two_stage.py nhưng code v3 còn import thêm module,
và khi không có file .gcloudignore thì gcloud dùng .gitignore — file này loại thư mục weight, nên image sẽ không có mô hình.
Nhóm viết script deploy_cloud_run.sh: tạo revision mới chưa nhận traffic, smoke test, chỉ chuyển traffic khi đặt PROMOTE=1.
Cùng ngày sửa thẻ độ chín: người dùng đọc "Độ chín 72,4%" thành "quả chín 72%", trong khi đó là độ tin cậy của dự đoán. Thẻ mới ghi rõ mô hình nghiêng về lớp nào,
độ tin cậy bao nhiêu và cần bao nhiêu. Ngưỡng mặc định trên giao diện hạ xuống 0,55 để ngưỡng riêng từng lớp phát huy tác dụng.
Từ 06 đến 08/10 là bản fix4 có thêm bộ lọc loài, video, ảnh tối và quét kỹ.

Chạy trên 1 CPU, 2 GiB, mỗi ảnh 1,4 đến 1,8 giây, RAM tối đa 572 MiB. Lưu ý vận hành: .dockerignore hiện chưa cho phép file species_verifier.pt.
""")

    # 35 ── Features Oct 5–6
    s = new_slide(prs, "Tính năng thêm 05–06/10 và tác dụng trên ảnh mẫu", "tính năng")
    picture(s, CASES / "filter_plum_off.jpg", .6, 1.35, 2.0, 2.75, "Mận — lọc tắt")
    picture(s, CASES / "filter_plum_on.jpg", 2.7, 1.35, 2.0, 2.75, "Mận — lọc bật")
    text(s, "Ảnh mận: 1 \"thanh long chín 100%\" + 1 xoài sai → 0 box", .6, 4.15, 4.1, .55, 13, INK)
    picture(s, CASES / "low_0_normal.jpg", 4.95, 1.35, 2.5, 2.4, "Ảnh thường: 13 quả")
    picture(s, CASES / "low_0_dark.jpg", 7.55, 1.35, 2.5, 2.4, "Làm tối: 2")
    picture(s, CASES / "low_0_assist.jpg", 10.15, 1.35, 2.5, 2.4, "Tối + hỗ trợ: 6")
    text(s, "Ảnh tối tổng hợp (gamma 2,2, phơi sáng 35%)", 4.95, 3.85, 7.7, .4, 13, INK)
    card(s, .6, 4.75, 4.0, 1.95, "Bộ lọc loài",
         "YOLOv8n-cls 3 lớp, 5 epoch, 224 px, train trên CPU laptop với ảnh mận Wikimedia", GREEN, 13)
    card(s, 4.8, 4.75, 3.9, 1.95, "Quét kỹ",
         "Ảnh 5 xoài chồng nhau: 2 → 4 quả; vẫn sót 1 quả bị che", GOLD, 13)
    card(s, 8.9, 4.75, 3.83, 1.95, "Video",
         "Lấy ~5 khung/giây, ByteTrack, mỗi ID xuất hiện ≥ 2 khung được đếm 1 lần", NAVY, 13)
    N("""
Ngày 05 và 06/10 nhóm thêm bốn tính năng, mỗi tính năng xuất phát từ một ảnh lỗi cụ thể.

Bộ lọc loài: ảnh mận trên tay bị v3 gọi là "thanh long chín 100%" và một quả xoài uncertain. Nhóm huấn luyện nhanh một YOLOv8n-cls 3 lớp trên CPU laptop,
5 epoch, ảnh 224 pixel, lớp "quả khác" lấy ảnh mận từ Wikimedia. Bật bộ lọc thì hai box sai biến mất — hai ảnh bên trái.

Hỗ trợ ảnh tối: ba ảnh giữa là cùng một ảnh test. Ảnh thường tìm được 13 quả; làm tối nhân tạo còn 2; bật hỗ trợ lên 6. Có cải thiện nhưng chưa bằng ảnh sáng,
và chỉ thử trên ảnh làm tối nhân tạo, chưa có ảnh vườn đêm thật.

Quét kỹ: ảnh 5 quả xoài chồng nhau từ 2 lên 4 quả, vẫn sót một quả bị che.
Video: lấy khoảng 5 khung hình mỗi giây, ByteTrack gán ID, ID nào xuất hiện ít nhất 2 khung và có ít nhất một box vượt ngưỡng thì được đếm một lần. Video không đánh giá độ chín.

Lưu ý: bộ lọc loài được train nhanh và dữ liệu train nằm trong thư mục tạm đã mất — đây chính là nguồn gốc lỗi ở slide sau.
""")

    # 36 ── Oct 8 evaluation
    s = new_slide(prs, "08/10: đánh giá lại toàn bộ pipeline đang chạy", "đánh giá")
    stat(s, .6, 1.4, 2.3, 1.45, "88,8% → 88,5%", "recall 2.037 ảnh test\n(lọc tắt → bật)", GREEN, vsize=20)
    stat(s, 3.05, 1.4, 2.3, 1.45, "1.103 → 264", "box sai trên 400 ảnh\nkhông có quả", GREEN, vsize=22)
    stat(s, 5.5, 1.4, 2.3, 1.45, "54% → 63%", "recall ảnh tối →\ncó hỗ trợ (thường 86%)", GOLD, vsize=22)
    bar_chart(s, 8.0, 1.25, 4.8, 3.3,
              ["mango_yolo", "rf_mango", "dragon orchard", "pitaya", "rf_mango_tree", "mango_on_tree", "ripe dragon plants"],
              [("Recall", [.9787, .9651, .9966, .9067, .8693, .5639, .5319], GREEN)],
              horizontal=True, legend=False, maxv=1.0, label_size=10)
    text(s, "Recall theo nguồn (lọc tắt)", 8.1, 4.55, 4.6, .3, 12, MUTED)
    card(s, .6, 3.1, 7.2, 2.0, "Ảnh không có quả: bộ lọc giúp nhiều",
         "Số ảnh âm tính còn box sai: 276/400 → 114/400. Vải vẫn khó: 28/40 ảnh còn box sai khi bật lọc.", GREEN, 14)
    card(s, .6, 5.3, 7.2, 1.45, "Độ chín",
         "2.493 nhãn chắc chắn so với 5.673 uncertain — khoảng 3/4 uncertain do crop < 64 px.", GOLD, 14)
    card(s, 8.0, 5.0, 4.73, 1.75, "Điểm yếu còn lại",
         "Xoài dày trên cây 56%, trụ thanh long 53% recall.", RED, 14)
    N("""
Ngày 08/10 nhóm chạy lại toàn bộ pipeline đang triển khai trên 2.037 ảnh test, 400 ảnh không có quả và 200 ảnh làm tối, so sánh bật và tắt bộ lọc loài.

Recall tổng giảm rất ít: 88,8% khi tắt lọc, 88,5% khi bật; precision khoảng 84%. Trên 400 ảnh không có xoài hay thanh long, số box sai giảm từ 1.103 xuống 264,
số ảnh có box sai giảm từ 276 xuống 114. Riêng vải vẫn khó: 28 trên 40 ảnh vẫn còn box sai.
Ảnh tối: ảnh thường tìm 86%, làm tối còn 54%, bật hỗ trợ lên 63%.

Biểu đồ bên phải: recall theo nguồn. Các nguồn cận cảnh và hàng thanh long đều trên 86%. Hai điểm yếu là xoài dày trên cây 56% và trụ thanh long 53% — trùng với kết quả benchmark trước đó.

Độ chín: 2.493 quả có nhãn chắc chắn, 5.673 uncertain; khoảng ba phần tư số uncertain là do quả quá nhỏ trong ảnh, dưới 64 pixel.

Nhìn số tổng thì bộ lọc có vẻ rất tốt. Slide tiếp theo cho thấy vì sao không được chỉ nhìn số tổng.
""")

    # 37 ── Verifier bug
    s = new_slide(prs, "Lỗi phát hiện ngày 08/10: bộ lọc loài xóa nhầm xoài chín", "phân tích lỗi")
    picture(s, CASES / "filter_spotted_off.jpg", .6, 1.35, 4.0, 2.75, "Lọc tắt: xoài chín 89%")
    picture(s, CASES / "filter_spotted_on.jpg", 4.75, 1.35, 4.0, 2.75, "Lọc bật: mất hết")
    stat(s, 9.0, 1.35, 1.8, 1.4, "24/49", "xoài chín bị xóa", RED, vsize=26)
    stat(s, 10.93, 1.35, 1.8, 1.4, "8/24", "xoài turning bị xóa", RED, vsize=26)
    card(s, 9.0, 2.95, 3.73, 1.85, "Vì sao số tổng che lỗi",
         "Tập test detector chủ yếu là xoài xanh → recall chỉ giảm 0,3 điểm.", GOLD, 13)
    card(s, .6, 4.4, 4.0, 2.3, "Nguyên nhân",
         "Bộ lọc học: vỏ vàng cam có đốm = \"quả khác\" (giống mận chín). Detector vẫn chấm các quả này 0,70–0,87.", RED, 14)
    card(s, 4.75, 4.4, 4.0, 2.3, "Cách sửa",
         "Train lại bộ lọc với crop xoài chín, xoài đốm trong lớp mango; kiểm tra tỉ lệ bị loại theo từng mức chín.", GREEN, 14)
    card(s, 9.0, 5.0, 3.73, 1.7, "Trong lúc chờ",
         "Tắt bộ lọc khi demo độ chín (SPECIES_VERIFIER_PATH).", NAVY, 13)
    N("""
Đây là phát hiện quan trọng nhất của đợt đánh giá 08/10. Hai ảnh bên trái là cùng một ảnh xoài chín có đốm.
Tắt bộ lọc: quả xoài được nhận là chín với 89%. Bật bộ lọc: tất cả biến mất.

Khi đếm theo mức chín, bộ lọc xóa 24 trên 49 quả xoài chín và 8 trên 24 quả xoài turning trong tập test. Detector vẫn chấm các quả này từ 0,70 đến 0,87 — tức detector đúng, bộ lọc sai.
Nguyên nhân: bộ lọc được huấn luyện nhanh với ảnh mận, và học được rằng vỏ vàng cam có đốm là "quả khác".

Vì sao số tổng không phát hiện? Vì tập test của detector chủ yếu là xoài xanh, nên recall tổng chỉ giảm 0,3 điểm. Lỗi chỉ lộ ra khi chia theo mức chín.
Đây là cùng bài học với thử nghiệm A/B/C: phải xem theo từng nhóm, không chỉ số tổng.

Cách sửa: huấn luyện lại bộ lọc, đưa crop xoài chín và xoài có đốm vào lớp mango, rồi kiểm tra tỉ lệ bị loại cho từng mức chín trước khi deploy.
Trong lúc chờ, khi demo độ chín xoài, nhóm tắt bộ lọc bằng cách trỏ SPECIES_VERIFIER_PATH tới file không tồn tại; /health sẽ báo other_fruit_filter bằng false.
""")

    # 38 ── Video
    s = new_slide(prs, "Đếm quả trong video: cách làm và kết quả thử", "video")
    card(s, .6, 1.4, 5.95, 4.0, "Cách làm (backend/video.py)",
         "- Giới hạn: 50 MB, 30 giây, 1920×1080; tối đa 150 khung được theo dõi\n"
         "- Lấy mẫu ~5 khung/giây; ByteTrack conf = min(ngưỡng, 0,1), IoU 0,7\n"
         "- Mỗi yêu cầu một tracker riêng → ID không lẫn giữa người dùng\n"
         "- Đếm ID xuất hiện ≥ 2 khung và có ≥ 1 box vượt ngưỡng\n"
         "- Bộ lọc loài kiểm tra crop tốt nhất của mỗi ID; không phân độ chín", GREEN, 14)
    table(s, 6.8, 1.4, 5.93, [2.6, 1.2, 1.1, 1.0], [
        ("Video thử (08/10)", "Thời lượng", "Đếm", "Thật"),
        ("Vườn thanh long", "20 s / 100 khung", "3", "—"),
        ("Lia máy cây xoài (giả lập)", "12 s / 60 khung", "12", "8"),
    ], size=13, row_h=.7)
    card(s, 6.8, 3.75, 5.93, 1.65, "Vì sao đếm thừa",
         "Một chiếc lá bị nhận là xoài; quả bị che rồi xuất hiện lại được gán ID mới.", RED, 14)
    callout(s, "Kết quả video là ước lượng: chưa có video vườn thật có số quả chuẩn để đo sai số", 5.65, h=.6,
            color=RED, fill=RED_SOFT)
    N("""
Đếm quả trong video nằm trong backend/video.py. Giới hạn 50 MB, 30 giây, độ phân giải 1080p.
Hệ thống lấy khoảng 5 khung hình mỗi giây, chạy detector với ngưỡng thấp và ByteTrack để nối box thành ID. Mỗi yêu cầu có tracker riêng nên ID không lẫn giữa các người dùng.
Một ID được đếm nếu xuất hiện ít nhất 2 khung và có ít nhất một box vượt ngưỡng. Bộ lọc loài chỉ kiểm tra crop tốt nhất của mỗi ID. Video không phân loại độ chín.

Kết quả thử ngày 08/10: video vườn thanh long 20 giây đếm được 3 quả. Video giả lập lia máy qua cây xoài 12 giây đếm 12 trong khi thực tế 8 — đếm thừa vì một chiếc lá bị nhận là xoài,
và quả bị che rồi xuất hiện lại được gán ID mới.

Nhóm nói rõ: số đếm video là ước lượng. Chưa có video vườn thật có số quả chuẩn để đo sai số.
""")

    # 39 ── Section 6
    section(prs, 6, "Kết luận & demo", "Bài học, hạn chế, bước tiếp theo và kịch bản demo trực tiếp")
    N("""
Phần cuối: bài học, hạn chế, bước tiếp theo, và kịch bản demo.
""")

    # 40 ── Lessons
    s = new_slide(prs, "Năm bài học từ 8 vòng huấn luyện", "bài học")
    lessons = [
        ("Sửa dữ liệu trước khi train lại", "3 vòng thất bại vì dữ liệu: polygon đọc thành box, nhãn theo tuổi quả, thiếu ảnh cả cây. Thêm epoch không sửa được."),
        ("Test trên ảnh sẽ dùng thật", "91% và 98,5% che giấu thất bại trên ảnh cả cây vì test giống train."),
        ("Confidence thô không phải xác suất", "Hiệu chỉnh + nhãn uncertain cho câu trả lời trung thực; cắt 80–90% trên điểm YOLO thô mất gần hết box."),
        ("Nhãn phải nhìn thấy được", "Giai đoạn theo số ngày sau đậu quả không học được từ ảnh (63,9% → 90,2% khi đổi nhãn)."),
        ("Bảo vệ và kiểm tra checkpoint", "Tên run mới, lưu ngoài máy, resume, FP32, so dự đoán sau khi tải lại; xem kết quả theo từng nhóm, không chỉ số tổng."),
    ]
    for i, (h, b) in enumerate(lessons):
        y = 1.38 + i * 1.08
        box(s, .6, y, 12.13, .95)
        text(s, str(i + 1), .8, y + .12, .6, .7, 30, GREEN if i % 2 == 0 else GOLD, True, valign=MSO_ANCHOR.MIDDLE)
        text(s, h, 1.5, y + .1, 3.6, .75, 16, NAVY, True, valign=MSO_ANCHOR.MIDDLE)
        text(s, b, 5.2, y + .08, 7.35, .8, 14, INK, valign=MSO_ANCHOR.MIDDLE)
    N("""
Năm bài học nhóm rút ra, mỗi bài gắn với một lần thất bại cụ thể.

Một: sửa dữ liệu trước khi huấn luyện lại. Ba vòng thất bại đều do dữ liệu — polygon đọc thành box, nhãn theo tuổi quả, thiếu ảnh cả cây. Thêm epoch không sửa được.
Hai: kiểm tra trên đúng loại ảnh sẽ dùng. Con số 91% của vòng 0 và 98,5% của v2 che giấu thất bại trên ảnh cả cây, vì tập test giống tập train.
Ba: confidence thô của mô hình không phải xác suất. Hiệu chỉnh nhiệt độ cộng nhãn uncertain cho câu trả lời trung thực.
Bốn: nhãn phải nhìn thấy được trên ảnh. Chỉ đổi định nghĩa lớp xoài, cùng mô hình và cấu hình, độ chính xác từ 63,9% lên 90,2%.
Năm: bảo vệ và kiểm tra checkpoint — v4 cho thấy job thành công chưa chắc mô hình dùng được. Và đánh giá theo từng nhóm: cả thử nghiệm A/B/C lẫn bộ lọc loài
đều trông tốt trên số tổng nhưng làm mất xoài chín.
""")

    # 41 ── Limits & next steps
    s = new_slide(prs, "Hạn chế hiện tại và bước tiếp theo", "hướng phát triển")
    card(s, .6, 1.4, 5.95, 4.95, "Hạn chế đo được",
         "- Bộ lọc loài xóa 24/49 xoài chín\n- Xoài dày trên cây: recall ~50–56%\n"
         "- Trụ thanh long dày quả: ~53%\n- Vải/litchi vẫn bị nhận nhầm\n"
         "- Ảnh tối: 54% (63% có hỗ trợ)\n- Thanh long 100% chưa kiểm chứng ngoài tập tuyển chọn\n"
         "- MangoFruitBD giấy phép phi thương mại\n- Chưa có ảnh/video có nhãn từ vườn mục tiêu", RED, 14)
    card(s, 6.78, 1.4, 5.95, 4.95, "Bước tiếp theo (theo chi phí)",
         "- Train lại bộ lọc loài với xoài chín/đốm, kiểm tra theo mức chín\n"
         "- Thử giới hạn phóng to cho ảnh nhỏ trên benchmark\n"
         "- Nếu train tiếp: mỗi lần đổi một yếu tố (vd. C bỏ ảnh vải/chôm chôm)\n"
         "- Sửa nhãn 1.246 frame thanh long đang cách ly\n"
         "- Thu ảnh và video có nhãn từ đúng vườn, đúng camera\n"
         "- Giữ một tập test chưa đụng tới cho mô hình được chọn", GREEN, 14)
    N("""
Bên trái là các hạn chế nhóm đã đo được, không phải phỏng đoán.
Bộ lọc loài đang xóa một nửa số xoài chín. Recall trên xoài dày trên cây chỉ khoảng 50 đến 56%, trụ thanh long dày quả khoảng 53%. Vải và litchi vẫn bị nhận nhầm.
Ảnh tối chỉ còn 54%, có hỗ trợ là 63%. Độ chính xác 100% của thanh long chưa được kiểm chứng ngoài tập đã tuyển chọn.
Bộ MangoFruitBD có giấy phép phi thương mại. Và quan trọng nhất: chưa có ảnh hay video có nhãn từ chính vườn mục tiêu.

Bên phải là bước tiếp theo, xếp theo chi phí từ thấp đến cao.
Rẻ nhất là train lại bộ lọc loài với xoài chín và xoài đốm, rồi kiểm tra tỉ lệ bị loại theo từng mức chín.
Tiếp theo là thử giới hạn phóng to cho ảnh nhỏ trên benchmark — chỉ cần chạy đánh giá, không cần train.
Nếu train tiếp thì mỗi lần chỉ đổi một yếu tố, ví dụ C nhưng bỏ ảnh vải, chôm chôm.
Sửa nhãn 1.246 frame thanh long ngoài vườn đang bị cách ly.
Và thu ảnh, video có nhãn từ đúng vườn và đúng camera — điều mà không bộ dữ liệu công khai nào thay được. Mô hình được chọn cuối cùng phải được kiểm tra trên một tập test chưa đụng tới.
""")

    # 42 ── Demo script
    s = new_slide(prs, "Kịch bản demo (~6 phút)", "demo")
    table(s, .6, 1.35, 12.13, [.55, 2.9, 4.55, 4.13], [
        ("#", "Thao tác", "File / cài đặt", "Điều cần chỉ ra"),
        ("1", "Mở /health", "Trình duyệt → …/health", "pipeline_mode = two-stage, other_fruit_filter"),
        ("2", "Thanh long cận cảnh", "dragon-fruit-pucka-fertilizer-1.jpg", "3 box, nhãn chín + độ tin cậy"),
        ("3", "Cả trụ thanh long", "tru-cay-thanh-long.jpg", "~22 quả; nhiều quả nhỏ → uncertain (crop < 64 px)"),
        ("4", "Cây xoài nhiều quả", "oxi-house-cay-xoai-tu-quy-2_…jpg", "~46 box; thẻ \"Model nghiêng về … (cần ≥ x%)\""),
        ("5", "Quả khác", "images (9).jpeg (mận)", "Lọc tắt: box sai → bật: 0 box"),
        ("6", "Xoài chồng nhau", "images (7).jpeg + bật \"Quét kỹ\"", "2 → 4 trên 5 quả"),
        ("7", "Video", "orchard_dragon_input.mp4 (20 s)", "Số quả duy nhất theo loài, khung minh họa"),
        ("8", "Lỗi đã biết", "Ảnh xoài chín có đốm, lọc bật/tắt", "Bộ lọc xóa xoài chín → bài học"),
    ], size=13, row_h=.55)
    callout(s, "Ảnh ở ~/Downloads; video ở fruit_detection_presentation/assets/video; Swagger /docs để gọi API trực tiếp", 6.4, h=.5, size=13)
    N("""
KỊCH BẢN DEMO — khoảng 6 phút. Người demo mở sẵn trình duyệt ở trang ứng dụng (Cloud Run hoặc http://localhost:5173), thư mục ảnh ~/Downloads và thư mục video.

Bước 1 (20 giây): mở /health. Nói: "Hệ thống đang chạy chế độ two-stage, detector 960 pixel, bộ lọc quả khác đang bật." Nếu thấy legacy thì dừng và kiểm tra weight.
Bước 2 (40 giây): tải ảnh thanh long cận cảnh dragon-fruit-pucka-fertilizer-1.jpg. Chỉ vào 3 box và nhãn dragonfruit_ripe, đọc độ tin cậy.
Bước 3 (45 giây): tải ảnh cả trụ thanh long tru-cay-thanh-long.jpg. Kết quả khoảng 22 quả. Chỉ ra nhiều quả nhỏ có nhãn uncertain vì crop nhỏ hơn 64 pixel —
"hệ thống vẫn đếm nhưng không đoán độ chín khi quả quá nhỏ". Nhắc: bản 7 lớp ngày 24/09 tìm được 0 quả trên ảnh này.
Bước 4 (45 giây): ảnh cây xoài oxi-house… Khoảng 46 box. Mở một thẻ uncertain, đọc dòng "Model nghiêng về: Xoài non · tin cậy … (cần ≥ …)" và giải thích đây là độ tin cậy, không phải phần trăm chín.
Bước 5 (40 giây): ảnh mận images (9).jpeg. Nếu đang chạy local, tắt bộ lọc trước để thấy box sai, rồi bật lại để thấy 0 box. Trên Cloud Run bộ lọc luôn bật, nên chỉ cho thấy 0 box và dùng slide 35 để so sánh.
Bước 6 (40 giây): ảnh 5 quả xoài chồng nhau images (7).jpeg: chạy thường được 2 quả, bật "Quét kỹ ảnh nhiều quả" được 4.
Bước 7 (60 giây): tải video orchard_dragon_input.mp4 vào thẻ "Đếm quả trong video". Chờ xử lý, đọc số quả duy nhất và khung hình minh họa. Nói rõ đây là ước lượng.
Bước 8 (40 giây): trình bày lỗi đã biết bằng ảnh xoài chín có đốm: bật bộ lọc thì quả biến mất. Đây là lý do bước tiếp theo là huấn luyện lại bộ lọc.

Nếu thầy cô muốn xem API: mở /docs, chọn POST /detect, "Try it out", tải một ảnh và xem JSON có total_count, counts và detections.
""")

    # 43 ── Demo setup & backup
    s = new_slide(prs, "Chuẩn bị demo và phương án dự phòng", "demo")
    card(s, .6, 1.4, 5.95, 2.75, "Chạy tại máy",
         "- uvicorn backend.app:app --host 127.0.0.1 --port 8000\n- cd frontend && npm ci && npm run dev → localhost:5173\n"
         "- Tắt bộ lọc: SPECIES_VERIFIER_PATH=/khong-co-file\n- Weight v3 phải có trong backend/weights", GREEN, 13)
    card(s, 6.78, 1.4, 5.95, 2.75, "Chạy trên Cloud Run",
         "- fruit-detection-542444439835.asia-southeast1.run.app\n- Yêu cầu đầu tiên chậm hơn (scale-to-zero) → mở trước 1–2 phút\n"
         "- Bản hiện tại có bộ lọc loài → xoài chín có thể mất", GOLD, 13)
    card(s, .6, 4.4, 5.95, 2.3, "Nếu mạng/máy lỗi",
         "Dùng ảnh kết quả có sẵn trên slide 24, 35, 37 và thư mục pipeline_check; video đã gán nhãn *_annotated.mp4.", RED, 13)
    card(s, 6.78, 4.4, 5.95, 2.3, "Rollback Cloud Run",
         "gcloud run services update-traffic fruit-detection --region=asia-southeast1 --to-revisions=<revision>=100", NAVY, 13)
    N("""
Chuẩn bị trước buổi demo.

Nếu chạy tại máy: chạy uvicorn backend.app:app ở cổng 8000, rồi trong thư mục frontend chạy npm ci và npm run dev, mở localhost:5173 — Vite tự chuyển các yêu cầu /detect và /health sang backend.
Muốn demo độ chín xoài mà không bị bộ lọc xóa nhầm, đặt biến môi trường SPECIES_VERIFIER_PATH tới một file không tồn tại; /health sẽ báo other_fruit_filter bằng false.
Weight v3 và file calibration phải có trong backend/weights.

Nếu dùng Cloud Run: địa chỉ ghi trên slide. Dịch vụ tự tắt khi không có người dùng nên yêu cầu đầu tiên chậm hơn — mở trang trước 1 đến 2 phút.
Bản đang chạy có bộ lọc loài nên xoài chín có thể biến mất; nếu xảy ra, dùng chính điều đó để minh họa lỗi ở slide 37.

Nếu mạng hoặc máy lỗi: dùng các ảnh kết quả đã có trên slide 24, 35, 37, thư mục pipeline_check của job v3, và các video đã gán nhãn *_annotated.mp4.
Nếu bản deploy mới có vấn đề, lệnh rollback Cloud Run chuyển toàn bộ traffic về một revision cũ.
""")

    # 44 ── Evidence & team
    s = new_slide(prs, "Nguồn minh chứng và thông tin nhóm", "phụ lục")
    card(s, .6, 1.4, 5.0, 4.95, "Nhóm thực hiện",
         TEAM + "\n" + "\n".join(MEMBERS) + f"\nGVHD: {LECTURER}\n\n(Điền phần việc của từng thành viên)", GREEN, 14)
    table(s, 5.85, 1.4, 6.88, [3.6, 3.28], [
        ("Minh chứng", "Đường dẫn"),
        ("Lịch sử dự án", "docs/PROJECT_HISTORY.md"),
        ("Job Vertex (args, results, review)", "fruit_detection_runs_gcp_review/<job>/"),
        ("Benchmark + A/B/C", "…/regression_20261002/trial_abc_summary.json"),
        ("Rà nhãn 02/10", "…/label_audit_20261002/"),
        ("Phiên bản dữ liệu", "data/prepared/*/preparation_report.json"),
        ("Nguồn dữ liệu", "data/external/datasets.json"),
        ("Đánh giá 08/10", "fruit_detection_presentation/eval/summary.json"),
    ], size=12, row_h=.6)
    N("""
Slide cuối liệt kê nơi kiểm tra mọi số liệu trong bài.
Lịch sử dự án nằm ở docs/PROJECT_HISTORY.md. Mỗi job Vertex AI có thư mục riêng trong fruit_detection_runs_gcp_review theo mã job, gồm cấu hình args.yaml,
results.csv theo từng epoch và file review. Benchmark và ba thử nghiệm A/B/C ở regression_20261002. Kết quả rà nhãn ở label_audit_20261002.
Số ảnh từng phiên bản dữ liệu ở preparation_report.json của từng thư mục trong data/prepared. Danh sách nguồn dữ liệu, URL và giấy phép ở data/external/datasets.json.
Đánh giá ngày 08/10 ở eval/summary.json của thư mục trình bày.

(Đọc tên thành viên và phần việc của từng người.)
""")

    # 45 ── Thanks
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid(); s.background.fill.fore_color.rgb = WHITE
    text(s, "CẢM ƠN THẦY CÔ VÀ CÁC BẠN", .8, 2.3, 11.7, .9, 38, NAVY, True, PP_ALIGN.CENTER)
    text(s, "Hỏi đáp & demo", .8, 3.35, 11.7, .5, 22, GREEN, True, PP_ALIGN.CENTER)
    text(s, "v3 • job 4169118715503181824 • Cloud Run asia-southeast1", .8, 4.1, 11.7, .4, 14,
         MUTED, align=PP_ALIGN.CENTER)
    N("""
Cảm ơn thầy cô và các bạn đã lắng nghe. Nhóm xin nhận câu hỏi, sau đó demo theo kịch bản ở slide 42.

Một số câu hỏi có thể gặp và cách trả lời ngắn:
— "Vì sao không dùng mô hình A/B/C có precision cao hơn?" Vì tiêu chí đặt trước là lấy lại các ảnh xoài bị mất; cả ba đều mất xoài nhỏ và xoài đỏ (11 xuống 4).
— "Vì sao thanh long 100%?" Tập test là tập đã tuyển chọn; nhiệt độ T rất nhỏ cho thấy các lớp tách hẳn, có thể do nền ảnh. Chưa có ảnh độc lập.
— "Vì sao nhiều quả uncertain?" Khoảng ba phần tư là do quả nhỏ hơn 64 pixel trong ảnh; hệ thống vẫn đếm nhưng không đoán độ chín.
— "Tốn bao nhiêu tiền?" Chỉ dùng tín dụng Free Trial; mỗi lần train đầy đủ trên Spot V100 khoảng 5–10 đô.
""")

    if len(prs.slides) != len(notes):
        raise ValueError(f"slide/note mismatch: {len(prs.slides)} vs {len(notes)}")
    for slide, note in zip(prs.slides, notes):
        slide.notes_slide.notes_text_frame.text = note
    prs.core_properties.title = "Smart Orchard AI — báo cáo nhóm"
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print("Created", build())
