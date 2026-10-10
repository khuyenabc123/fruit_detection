"""Build the team's Word report (Duy Tan cover, detailed history, results and appendices).

Every number comes from a file in the project (same sources as build_presentation.py):
  .claude/worktrees/gcp-vertex-training/docs/PROJECT_HISTORY.md
  fruit_detection_runs_gcp_review/<job>/ and regression_20261002/
  data/prepared/*/preparation_report.json, data/external/*.json
  ../fruit_detection_presentation/eval/summary.json

The table of contents is written as a real TOC field with cached entries. Page
numbers come from a rendered PDF of a first pass:

  python3 reports/build_project_report.py                 # pass 1 (page numbers "…")
  soffice --headless --convert-to pdf reports/Bao_cao_nhom_Smart_Orchard_AI.docx
  python3 reports/build_project_report.py --pdf Bao_cao_nhom_Smart_Orchard_AI.pdf   # pass 2

Appendix A copies the speaker notes from the PPTX built by build_presentation.py.
Set FRUIT_ROOT to the main checkout when running from a worktree (images live there).
"""

import argparse
import os
import re
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FRUIT_ROOT", HERE.parents[0]))
OUT = HERE / "Bao_cao_nhom_Smart_Orchard_AI.docx"
PPTX = HERE / "Smart_Orchard_AI_Thuyet_trinh_nhom.pptx"
LOGO = HERE / "assets" / "dtu_logo.png"
GCP = ROOT / "fruit_detection_runs_gcp_review"
CASES = ROOT.parent / "fruit_detection_presentation" / "assets" / "cases"
V3_PHOTOS = GCP / "4169118715503181824" / "pipeline_check"

# Cover details. Fill the dotted fields when the team confirms them.
UNIVERSITY = "ĐẠI HỌC DUY TÂN"
UNIT = "BAN SAU ĐẠI HỌC"
REPORT_TYPE = "BÁO CÁO ĐỒ ÁN NHÓM"
COURSE = "MÔN MÁY HỌC"
TOPIC = ("Smart Orchard AI – Nhận diện, đếm và đánh giá độ chín của xoài "
         "và thanh long trên cây bằng học sâu")
MEMBERS = [("Phạm Doãn Đức", "31311570148"),
           ("........................................", "........................"),
           ("........................................", "........................")]
LECTURER = "........................................"
PLACE_DATE = "Đà Nẵng, ngày 10 tháng 10 năm 2026"

FONT = "Times New Roman"
BLACK = RGBColor(0, 0, 0)
TEXT_WIDTH_CM = 21.59 - 2 * 2.54


# ---------------------------------------------------------------- low-level helpers

def set_font(run, size=None, bold=None, italic=None, color=None):
    run.font.name = FONT
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def add_runs(p, text, size=None, bold=False, italic=False):
    """**x** marks bold segments inside text."""
    for i, part in enumerate(text.split("**")):
        if part:
            set_font(p.add_run(part), size, bold or i % 2 == 1, italic)


def shade(cell, hex_fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcpr.append(shd)


def keep_with_next(p):
    p.paragraph_format.keep_with_next = True


class Report:
    def __init__(self, page_map=None):
        self.d = Document()
        self.headings = []          # (level, text)
        self.page_map = page_map or {}
        self.fig = {}
        self.tab = {}
        self.chapter = 0
        self._styles()

    # ------------------------------------------------------------ styles & page
    def _styles(self):
        sec = self.d.sections[0]
        sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)
        for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
            setattr(sec, side, Cm(2.54))
        st = self.d.styles
        normal = st["Normal"]
        normal.font.name = FONT
        normal.font.size = Pt(13)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        pf = normal.paragraph_format
        pf.space_after = Pt(6)
        pf.line_spacing = 1.3
        for name, size in (("Heading 1", 15), ("Heading 2", 14), ("Heading 3", 13)):
            h = st[name]
            h.font.name = FONT
            h.font.size = Pt(size)
            h.font.bold = True
            h.font.italic = False
            h.font.color.rgb = BLACK
            rpr = h.element.get_or_add_rPr()
            fonts = rpr.find(qn("w:rFonts"))
            if fonts is None:
                fonts = OxmlElement("w:rFonts")
                rpr.insert(0, fonts)
            for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                fonts.set(qn(attr), FONT)
            for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                if fonts.get(qn(attr)) is not None:
                    del fonts.attrib[qn(attr)]
            h.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
            h.paragraph_format.space_after = Pt(6)
            h.paragraph_format.keep_with_next = True
        lb = st["List Bullet"]
        lb.font.name = FONT
        lb.font.size = Pt(13)
        lb.paragraph_format.space_after = Pt(3)
        lb.paragraph_format.line_spacing = 1.25

    # ------------------------------------------------------------ blocks
    def h(self, level, text):
        if level == 1 and text.startswith("CHƯƠNG"):
            self.chapter += 1
        p = self.d.add_heading(level=level)
        add_runs(p, text)
        for r in p.runs:
            set_font(r, None, True, False, BLACK)
        self.headings.append((level, text))
        return p

    def chapter_heading(self, text):
        # A trailing empty spacer (e.g. after a table that fills the page) would become a blank page.
        body = self.d.element.body
        last = body[-2] if len(body) > 1 and body[-1].tag == qn("w:sectPr") else body[-1]
        if last.tag == qn("w:p") and not "".join(last.itertext()).strip() \
                and not last.xpath(".//w:br | .//w:drawing"):
            body.remove(last)
        para = self.h(1, text)
        para.paragraph_format.page_break_before = True
        return para

    def p(self, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, italic=False, size=None, indent=True):
        para = self.d.add_paragraph()
        para.alignment = align
        if indent:
            para.paragraph_format.first_line_indent = Cm(0.75)
        add_runs(para, text, size=size, italic=italic)
        return para

    def bullets(self, items):
        for it in items:
            para = self.d.add_paragraph(style="List Bullet")
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_runs(para, it)

    def caption(self, text):
        para = self.d.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_after = Pt(10)
        add_runs(para, text, size=12, italic=True)
        return para

    def table(self, title, header, rows, widths_cm, size=11, highlight=None):
        self.tab[self.chapter] = self.tab.get(self.chapter, 0) + 1
        cap = self.d.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(6)
        cap.paragraph_format.space_after = Pt(4)
        keep_with_next(cap)
        add_runs(cap, f"**Bảng {self.chapter}.{self.tab[self.chapter]}.** {title}", size=12)
        t = self.d.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        scale = TEXT_WIDTH_CM / sum(widths_cm) if sum(widths_cm) > TEXT_WIDTH_CM else 1
        widths = [Cm(w * scale) for w in widths_cm]
        for j, w in enumerate(widths):
            t.columns[j].width = w      # grid widths (LibreOffice/Google Docs read these)
        all_rows = [header] + list(rows)
        for i, row in enumerate(all_rows):
            cells = t.rows[0].cells if i == 0 else t.add_row().cells
            for j, val in enumerate(row):
                c = cells[j]
                c.width = widths[j]
                c.paragraphs[0].text = ""
                lines = str(val).split("\n")
                for k, line in enumerate(lines):
                    para = c.paragraphs[0] if k == 0 else c.add_paragraph()
                    para.paragraph_format.space_after = Pt(0)
                    para.paragraph_format.line_spacing = 1.1
                    add_runs(para, line, size=size, bold=(i == 0))
                if i == 0:
                    shade(c, "D9E7E1")
                elif highlight and i in highlight:
                    shade(c, "EAF5EE")
        for row in t.rows:
            trpr = row._tr.get_or_add_trPr()
            cs = OxmlElement("w:cantSplit")
            trpr.append(cs)
        hdr = t.rows[0]._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        th.set(qn("w:val"), "true")
        hdr.append(th)
        gap = self.d.add_paragraph()
        gap.paragraph_format.space_after = Pt(4)
        return t

    def figure(self, path, width_cm, title):
        self.fig[self.chapter] = self.fig.get(self.chapter, 0) + 1
        para = self.d.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        keep_with_next(para)
        if Path(path).exists():
            para.add_run().add_picture(str(path), width=Cm(width_cm))
        else:
            add_runs(para, f"(thiếu ảnh: {Path(path).name})", italic=True)
        self.caption(f"**Hình {self.chapter}.{self.fig[self.chapter]}.** {title}")

    def figure_row(self, paths, width_cm, title):
        """Several images side by side in one centred paragraph."""
        self.fig[self.chapter] = self.fig.get(self.chapter, 0) + 1
        para = self.d.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        keep_with_next(para)
        for i, path in enumerate(paths):
            if Path(path).exists():
                para.add_run().add_picture(str(path), width=Cm(width_cm))
            if i < len(paths) - 1:
                para.add_run("  ")
        self.caption(f"**Hình {self.chapter}.{self.fig[self.chapter]}.** {title}")

    def code(self, text):
        para = self.d.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.75)
        para.paragraph_format.line_spacing = 1.0
        for k, line in enumerate(text.split("\n")):
            r = para.add_run(line)
            r.font.name = "Courier New"
            r.font.size = Pt(10.5)
            if k < len(text.split("\n")) - 1:
                r.add_break()

    def page_break(self):
        self.d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ------------------------------------------------------------ cover, TOC, footer
    def cover(self):
        d = self.d

        def line(text, size, bold=True, italic=False, before=0, after=6):
            para = d.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_before = Pt(before)
            para.paragraph_format.space_after = Pt(after)
            para.paragraph_format.first_line_indent = Cm(0)
            add_runs(para, text, size=size, bold=bold, italic=italic)
            return para

        line(UNIVERSITY, 25, before=11, after=0)
        line(UNIT, 25, after=10)
        lp = d.add_paragraph()
        lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if LOGO.exists():
            lp.add_run().add_picture(str(LOGO), width=Cm(9.3))
        line("", 13, after=10)
        line(REPORT_TYPE, 25, after=10)
        line(COURSE, 16, after=10)
        tp = d.add_paragraph()
        tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tp.paragraph_format.space_before = Pt(11)
        tp.paragraph_format.space_after = Pt(14)
        set_font(tp.add_run("Tên đề tài: "), 14, True, False)
        set_font(tp.add_run(f"\"{TOPIC}\""), 14, True, True)
        line("", 13, after=14)
        line("Nhóm học viên thực hiện:", 14, after=2)
        for name, sid in MEMBERS:
            line(f"{name} – Mã học viên: {sid}", 14, after=2)
        line(f"Giảng viên hướng dẫn: {LECTURER}", 14, before=8, after=2)
        for _ in range(3):
            line("", 13, after=0)
        line(PLACE_DATE, 16, after=0)
        self.page_break()

    def toc_placeholder(self):
        """Reserve the TOC position; fill_toc() inserts entries once headings are known."""
        para = self.d.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_after = Pt(12)
        add_runs(para, "MỤC LỤC", size=18, bold=True)
        self._toc_anchor = self.d.add_paragraph()
        self.page_break()

    def fill_toc(self):
        entries = [(lvl, txt) for lvl, txt in self.headings if lvl <= 2]
        anchor = self._toc_anchor._p
        paras = []
        for lvl, txt in entries:
            para = OxmlElement("w:p")
            paras.append((para, lvl, txt))
        # Build with python-docx Paragraph wrappers for formatting.
        from docx.text.paragraph import Paragraph
        prev = anchor
        built = []
        for el, lvl, txt in paras:
            prev.addnext(el)
            prev = el
            para = Paragraph(el, self._toc_anchor._parent)
            pf = para.paragraph_format
            pf.left_indent = Cm(0 if lvl == 1 else 0.8)
            pf.space_after = Pt(2)
            pf.line_spacing = 1.15
            pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
            page = self.page_map.get(txt, "…")
            set_font(para.add_run(txt), 12 if lvl == 1 else 12, lvl == 1, False)
            set_font(para.add_run(f"\t{page}"), 12, lvl == 1, False)
            built.append(para)
        # Wrap the entries in a TOC field so Word can refresh them (right click → Update field).
        first, last = built[0], built[-1]
        begin = OxmlElement("w:r")
        fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), "begin"); begin.append(fc)
        instr = OxmlElement("w:r")
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
        it.text = ' TOC \\o "1-2" \\h \\z \\u '
        instr.append(it)
        sep = OxmlElement("w:r")
        fc2 = OxmlElement("w:fldChar"); fc2.set(qn("w:fldCharType"), "separate"); sep.append(fc2)
        ppr = first._p.find(qn("w:pPr"))
        idx = list(first._p).index(ppr) + 1 if ppr is not None else 0
        for k, el in enumerate((begin, instr, sep)):
            first._p.insert(idx + k, el)
        end = OxmlElement("w:r")
        fc3 = OxmlElement("w:fldChar"); fc3.set(qn("w:fldCharType"), "end"); end.append(fc3)
        last._p.append(end)

    def footer(self):
        sec = self.d.sections[0]
        sec.different_first_page_header_footer = True
        fp = sec.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = fp.add_run()
        set_font(r, 11)
        for kind, text in (("begin", None), (None, " PAGE "), ("end", None)):
            if kind:
                fc = OxmlElement("w:fldChar")
                fc.set(qn("w:fldCharType"), kind)
                r._r.append(fc)
            else:
                it = OxmlElement("w:instrText")
                it.set(qn("xml:space"), "preserve")
                it.text = text
                r._r.append(it)

    def save(self, path):
        self.fill_toc()
        self.footer()
        self.d.core_properties.title = "Báo cáo nhóm – Smart Orchard AI"
        # python-docx's template writes <w:zoom> without the schema-required percent attribute.
        for zoom in self.d.settings.element.findall(qn("w:zoom")):
            zoom.set(qn("w:percent"), "100")
        self.d.save(path)


# ---------------------------------------------------------------- content

def write(R: Report):
    P, B, H = R.p, R.bullets, R.h

    R.cover()
    R.toc_placeholder()

    # ---------------- Lời mở đầu & tóm tắt
    H(1, "LỜI MỞ ĐẦU")
    P("Đếm quả và đánh giá độ chín trên cây là công việc tốn thời gian của người làm vườn. Với xoài và thanh long, "
      "quả thường nhỏ trong ảnh chụp cả cây, bị lá che, chồng lên nhau và thay đổi màu theo ánh sáng. Nhóm chọn đề tài "
      "Smart Orchard AI để xây dựng một hệ thống thị giác máy tính có thể nhận một ảnh hoặc một video ngắn, tìm từng quả, "
      "đếm số quả và cho biết độ chín của từng quả — đồng thời biết nói \"chưa chắc chắn\" khi bằng chứng chưa đủ.")
    P("Báo cáo này không chỉ trình bày kết quả cuối cùng. Nhóm ghi lại đúng quá trình đã diễn ra từ ngày 12/09 đến 08/10/2026: "
      "mỗi lần huấn luyện dùng dữ liệu nào, cấu hình nào, đạt kết quả bao nhiêu, phát hiện vấn đề gì và vì sao phải chạy lại. "
      "Tổng cộng có 8 vòng huấn luyện, 9 phiên bản dữ liệu, 17 nguồn dữ liệu công khai và 4 lần triển khai lên Google Cloud Run. "
      "Mọi số liệu đều trích từ tệp trong dự án; danh sách tệp minh chứng nằm ở cuối báo cáo. Nhóm cảm ơn giảng viên hướng dẫn "
      "và các tác giả dữ liệu mở (CQUniversity, Mendeley Data, Roboflow Universe, Wikimedia Commons).")

    H(1, "TÓM TẮT")
    P("Smart Orchard AI là pipeline hai giai đoạn: (1) detector YOLOv8s tìm quả xoài và thanh long trên ảnh 960 pixel; "
      "(2) với mỗi quả, classifier YOLOv8s-cls riêng theo loài dự đoán độ chín (xoài: young, mature, turning, ripe; "
      "thanh long: unripe, ripe, rotten). Xác suất được hiệu chỉnh bằng temperature scaling và ngưỡng riêng từng lớp; "
      "dự đoán không đủ tin cậy hoặc quả quá nhỏ được gắn nhãn uncertain. Hệ thống có API FastAPI, giao diện React, "
      "đếm quả trong video bằng ByteTrack và được triển khai trên Google Cloud Run; huấn luyện chạy trên Vertex AI.")
    P("Mô hình đang dùng (v3, job Vertex AI 4169118715503181824) đạt mAP50 94,9% và recall 88,3% trên 2.037 ảnh test; "
      "classifier xoài đúng 90,2% trên 234 crop, trong đó 179 crop được trả nhãn và 97,2% số nhãn đó đúng. Tuy nhiên, "
      "trên benchmark có ảnh không chứa quả, precision chỉ 55,3%; recall trên ảnh cả cây dày quả khoảng 53–56%; "
      "và bộ lọc loài thêm ngày 06/10 xóa nhầm 24/49 xoài chín. Báo cáo phân tích nguyên nhân của từng con số và các bước tiếp theo.")
    P("**Từ khóa:** YOLOv8, phát hiện đối tượng, phân loại độ chín, hiệu chỉnh xác suất, temperature scaling, ByteTrack, "
      "Vertex AI, Cloud Run.", indent=False)

    # ---------------- Chương 1
    R.chapter_heading("CHƯƠNG 1. GIỚI THIỆU")
    H(2, "1.1. Bối cảnh và bài toán")
    P("Ảnh vườn đặt ra bốn khó khăn chính. Thứ nhất, khi chụp cả cây, mỗi quả chỉ chiếm khoảng 10–25 pixel — đây là con số "
      "nhóm đo được ngày 24/09 khi mô hình đầu tiên thất bại. Thứ hai, quả bị lá che và chồng lên nhau. Thứ ba, ánh sáng thay "
      "đổi, có cả ảnh chụp đêm, làm màu quả — tín hiệu chính của độ chín — kém ổn định. Thứ tư, các loại quả khác như vải, "
      "chôm chôm, mận có hình dạng và màu gần giống.")
    H(2, "1.2. Mục tiêu và đầu ra")
    B(["Tìm vị trí (bounding box) và loài của từng quả: xoài hoặc thanh long.",
       "Phân loại độ chín: xoài 4 mức (young – non, mature – già xanh, turning – đang chuyển màu, ripe – chín); thanh long "
       "3 mức (unripe, ripe, rotten).",
       "Trả nhãn **mango_uncertain / dragonfruit_uncertain** khi quả quá nhỏ hoặc độ tin cậy chưa đủ, thay vì đoán bừa.",
       "Đếm số quả theo lớp trong ảnh; ước lượng số quả duy nhất trong video ngắn.",
       "Cung cấp giao diện web và API để người dùng thử ảnh, video."])
    H(2, "1.3. Phạm vi và giới hạn")
    B(["Chỉ hai loài quả mục tiêu; quả khác nằm ngoài phạm vi (nhưng hệ thống cố gắng không báo nhầm).",
       "Ảnh JPG/PNG/WEBP tối đa 12 MB; video MP4/MOV/WebM/AVI tối đa 50 MB, 30 giây, 1080p.",
       "Hệ thống hỗ trợ quan sát, chưa thay thế việc kiểm tra tại vườn vì nhóm chưa có ảnh có nhãn từ chính vườn mục tiêu.",
       "Dữ liệu từ v2 trở đi có bộ MangoFruitBD giấy phép phi thương mại, nên mô hình chỉ dùng cho học tập, nghiên cứu."])
    H(2, "1.4. Thuật ngữ")
    R.table("Thuật ngữ dùng trong báo cáo", ["Thuật ngữ", "Ý nghĩa"], [
        ("Detector", "Mô hình YOLOv8s tìm box và loài quả (2 lớp)."),
        ("Classifier", "Mô hình YOLOv8s-cls phân loại độ chín từ ảnh cắt (crop) của một quả, riêng cho từng loài."),
        ("Precision / Recall", "Tỉ lệ box dự đoán là đúng / tỉ lệ quả thật được tìm thấy (khớp khi IoU ≥ 0,5)."),
        ("mAP50, mAP50-95", "Độ chính xác trung bình ở ngưỡng IoU 0,5 và trung bình trên IoU 0,5–0,95 (chặt hơn)."),
        ("Calibration (hiệu chỉnh)", "Điều chỉnh xác suất của mô hình để \"80% tin cậy\" nghĩa là đúng khoảng 80%."),
        ("Temperature T", "Hệ số chia log-xác suất trước softmax; T > 1 làm mô hình bớt tự tin."),
        ("ECE", "Expected Calibration Error: sai lệch trung bình giữa độ tin cậy và tỉ lệ đúng thực tế."),
        ("Uncertain", "Quả vẫn được đếm nhưng không trả nhãn độ chín vì quá nhỏ hoặc chưa đủ tin cậy."),
        ("Ảnh âm tính", "Ảnh không có xoài hay thanh long (vải, táo, hoa…), dùng để đo box sai."),
        ("Rò rỉ dữ liệu (leakage)", "Ảnh giống nhau nằm ở cả train và test, làm kết quả test cao giả."),
    ], [4.0, 12.5])

    # ---------------- Chương 2
    R.chapter_heading("CHƯƠNG 2. QUÁ TRÌNH PHÁT TRIỂN DỰ ÁN")
    P("Chương này dựng lại quá trình từ lịch sử Git, tệp docs/PROJECT_HISTORY.md, các thư mục kết quả của từng job Vertex AI "
      "và báo cáo chuẩn bị dữ liệu. Thời gian theo giờ Việt Nam.")
    H(2, "2.1. Dòng thời gian")
    R.table("Các mốc chính của dự án", ["Ngày", "Sự kiện", "Kết quả / quyết định"], [
        ("12/09", "Vòng 0: YOLOv8s 4 lớp trên Colab (commit a1e93c4)", "mAP50 91,3% nhưng bị rò rỉ split"),
        ("18–20/09", "Vòng 1: 7 lớp; checkpoint bị ghi đè, khôi phục từ Drive", "mAP50 val 85,4%"),
        ("20–24/09", "Thử Modal thất bại; triển khai Cloud Run đầu tiên", "~7,6 giây/ảnh"),
        ("24/09", "Thử ảnh thật cả cây: kết quả rất tệ", "Đổi sang pipeline hai giai đoạn (f2c43ab)"),
        ("25–27/09", "Vòng 2: hai giai đoạn trên Colab", "Thất bại; log bị mất"),
        ("28/09", "Sửa dữ liệu (polygon, nhãn nhiễu); chuyển sang Vertex AI; v2", "Xoài chỉ 63,9%"),
        ("29/09", "v3: lớp xoài theo hình thức + ảnh cả cây", "Mô hình đang dùng"),
        ("30/09", "v4: detector 1280 px, thêm ảnh âm tính", "Checkpoint FP16 hỏng, loại"),
        ("02/10", "Benchmark cố định, rà nhãn, thử nghiệm A/B/C", "Không bản nào thay v3"),
        ("03/10", "Cloud Run chạy v3 + giao diện điện thoại", "1,4–1,8 giây/ảnh"),
        ("05–06/10", "Video, ảnh tối, quét kỹ, bộ lọc loài", "Bản fix4"),
        ("08/10", "Đánh giá lại toàn bộ pipeline", "Bộ lọc xóa nhầm xoài chín"),
    ], [2.2, 8.5, 5.8], highlight={7})
    H(2, "2.2. Tổng hợp các vòng huấn luyện")
    R.table("Kết quả và lý do phải chạy lại của từng vòng", ["Vòng", "Ngày • nơi chạy", "Kết quả chính", "Vấn đề → lý do chạy lại"], [
        ("0 · 4 lớp", "12/09 • Colab T4", "Test mAP50 91,3%", "456 ảnh gốc có bản sao ở nhiều tập → số ảo"),
        ("1 · 7 lớp", "18–20/09 • Colab", "Val mAP50 85,4%", "Ảnh cả cây tìm 0–7 quả; một mô hình làm hai việc"),
        ("2 · hai giai đoạn", "25–27/09 • Colab", "Không còn số liệu", "Polygon đọc thành box; Colab ngắt; nhãn nhiễu"),
        ("v2", "28/09 • Vertex V100", "Det mAP50 98,5%; xoài 63,9%", "Nhãn xoài theo tuổi quả; ảnh rộng chỉ thấy 3/~40 quả"),
        ("v3 (đang dùng)", "29/09 • Vertex V100", "Det mAP50 94,9%; xoài 90,2%", "Nhận nhầm vải/táo; trụ thanh long dày ~53%"),
        ("v4", "30/09 • Vertex V100", "Val 93,3% → tải lại 31,4%", "Checkpoint FP16 hỏng; xoài chín 11 → 0 quả"),
        ("A / B / C", "02/10 • Vertex V100", "Precision 55% → 66–68%", "Vẫn mất xoài nhỏ/đỏ (11 → 4) → giữ v3"),
        ("Bộ lọc loài", "06/10 • CPU laptop", "Box sai 1.103 → 264", "Xóa 24/49 xoài chín → cần huấn luyện lại"),
    ], [2.6, 3.2, 4.2, 6.5], highlight={5})

    H(2, "2.3. Vòng 0 (12/09): YOLOv8s 4 lớp")
    P("Bản đầu tiên dùng hai bộ dữ liệu xuất từ Roboflow: bộ xoài có bốn giai đoạn (Premature, early-fruit, mature, ripe) và "
      "bộ thanh long có Unripe, Ripe, Rotten. Nhóm gộp ba giai đoạn xanh của xoài thành mango_unripe, bỏ lớp Rotten, còn 4 lớp: "
      "mango_unripe, mango_ripe, dragonfruit_unripe, dragonfruit_ripe. Mô hình YOLOv8s huấn luyện 30 epoch trên Colab T4 với AdamW. "
      "Một quyết định được giữ suốt dự án: **hsv_h = 0**, tức không xoay sắc độ (hue) khi tăng cường dữ liệu, vì xoay hue biến xoài xanh "
      "thành vàng — tức đổi luôn nhãn độ chín.")
    P("Kết quả trên 714 ảnh test: precision 95,6%, recall 85,1%, mAP50 91,3%, mAP50-95 77,7%. Sau đó nhóm phát hiện bộ xoài có "
      "2.004 ảnh nhưng chỉ sinh ra từ 926 ảnh gốc (Roboflow tạo các bản xoay, lật), và **456 ảnh gốc có bản sao nằm ở nhiều tập**. "
      "Mô hình được kiểm tra trên ảnh gần như đã thấy, nên con số 91,3% không dùng được. Ngoài ra xoài vàng sau thu hoạch bị gọi là "
      "\"unripe\" và ảnh kết quả bị đổi màu xanh lơ do lẫn thứ tự kênh BGR/RGB.")
    P("**Lý do chạy lại:** chia dữ liệu theo ảnh gốc — mọi bản sao có cùng phần tên trước \".rf.\" phải nằm chung một tập — và "
      "tách độ chín xoài chi tiết hơn.")

    H(2, "2.4. Vòng 1 (18–20/09): 7 lớp trên Colab")
    P("Notebook Colab mới dùng 7 lớp: mango_premature, mango_early, mango_mature, mango_ripe, dragonfruit_unripe, dragonfruit_ripe, "
      "dragonfruit_rotten. Nhãn các bộ được ánh xạ theo tên lớp, không theo ID số. Cấu hình: YOLOv8s, 80 epoch, ảnh 640 px, batch 16, "
      "AdamW, seed 42; khoảng 76 giây mỗi epoch, tổng 1 giờ 39 phút trên GPU.")
    B(["**Sự cố 1:** Colab miễn phí hay ngắt và xóa checkpoint → ghi checkpoint thẳng lên Google Drive, thêm ô resume (commit 98348dc).",
       "**Sự cố 2:** một lần chạy nhầm trên CPU với cùng tên run và exist_ok=True ghi đè best.pt 80 epoch bằng mô hình 1 epoch "
       "(mAP50 0,027; 8.745 giây/epoch). Nhóm khôi phục được file từ lịch sử phiên bản của Google Drive.",
       "**Kết quả:** validation precision 82,6%, recall 81,3%, mAP50 85,4%, mAP50-95 75,2%. Chưa chạy test. Lớp premature hay bị nhầm với mature.",
       "**Bài học:** kiểm tra có GPU trước khi chạy, mỗi lần một tên run mới, exist_ok=False, lưu định kỳ."])
    P("Mô hình này vẫn được giữ làm baseline (backend/weights/fruit_yolov8s_7class.pt, chọn bằng PIPELINE_MODE=legacy).")

    H(2, "2.5. Triển khai đầu tiên (20–24/09)")
    P("Nhóm thử Modal trước: lần đầu lỗi \"Token missing\", lần sau lỗi vượt giới hạn chi tiêu vì gói miễn phí giới hạn $0 khi chưa "
      "gắn thẻ. Tạm thời backend chạy trên laptop qua Cloudflare quick tunnel. Ngày 24/09 nhóm triển khai lên Google Cloud Run "
      "(asia-southeast1, CPU, tự tắt khi không có người dùng). Hai lỗi phải sửa: service account của Cloud Build không đọc được "
      "mã nguồn (cấp role Cloud Run Builder) và chính sách tổ chức chặn truy cập công khai (cờ --no-invoker-iam-check). Revision "
      "fruit-detection-00001-z2h chạy khoảng 7,6 giây/ảnh và vẫn được giữ để rollback.")

    H(2, "2.6. Phân tích thất bại ngày 24/09")
    P("Có bản web thật, nhóm thử ngay bốn ảnh chụp thực tế. Kết quả ở bảng dưới đây cho thấy mô hình 7 lớp không dùng được trên ảnh cả cây.")
    R.table("Số box mô hình 7 lớp tìm được trên ảnh thật", ["Ảnh thử", "conf 0,25", "conf 0,80", "conf 0,90"], [
        ("Thanh long cận cảnh", "3", "2", "1"),
        ("Cả trụ thanh long", "0", "0", "0"),
        ("Cây xoài (hàng chục quả)", "7", "0", "0"),
        ("Xoài chín", "2 (gọi là mature)", "0", "0"),
    ], [7.0, 3.2, 3.2, 3.2])
    P("Nhóm tìm ra ba nguyên nhân:")
    B(["**Lệch miền dữ liệu:** ảnh huấn luyện là ảnh cận cảnh 640 px; trên ảnh cả cây mỗi quả chỉ 10–25 px.",
       "**Confidence chưa hiệu chỉnh:** F1 tốt nhất ở ngưỡng khoảng 0,42, nên đòi 80–90% là mất gần hết box.",
       "**Một mô hình làm hai việc:** vừa tìm quả vừa phân biệt 7 mức chín; độ chính xác theo mức chỉ khoảng 56% (premature), "
       "67% (mature), 84% (ripe)."])
    P("Từ đây nhóm quyết định tách việc tìm quả và việc đánh giá độ chín thành hai mô hình riêng (Chương 4).")

    H(2, "2.7. Vòng 2 (24–27/09): hai giai đoạn trên Colab")
    P("Pipeline hai giai đoạn (commit f2c43ab) được huấn luyện lần đầu trên Colab, có thêm dữ liệu MangoYOLO, CQU on-tree và bộ "
      "thanh long Mendeley; 630/2.127 ảnh thanh long gốc bị loại vì trùng từng byte. Detector và classifier xoài chạy xong, "
      "classifier thanh long lỗi. Resume hỏng vì Ultralytics đánh dấu run đã xong bằng epoch = −1 (sửa ở commit 237fd8f); "
      "runtime ngắt; runtime mới không thấy file zip trên Drive. Ngày 27/09 thử trên ảnh trên cây, kết quả vẫn rất tệ; log các "
      "phiên Colab này bị mất nên không còn số liệu.")
    P("Nguyên nhân gốc tìm ra ngày 28/09: bộ thanh long Roboflow xuất dưới tên \".yolov8\" nhưng chứa **polygon phân đoạn**, và "
      "code cũ đọc nhầm polygon thành box (Mục 3.3). Mọi checkpoint detector và thanh long trước đó phải bỏ. Nhóm quyết định "
      "**dừng huấn luyện để sửa dữ liệu trước**.")

    # ---------------- Chương 3
    R.chapter_heading("CHƯƠNG 3. DỮ LIỆU VÀ CHUẨN BỊ")
    P("Ba vòng thất bại đầu tiên đều do dữ liệu chứ không do mô hình. Chương này trình bày các nguồn dữ liệu, lỗi đã phát hiện, "
      "cách sửa được viết thành code, và 9 phiên bản dữ liệu.")
    H(2, "3.1. Nguồn dữ liệu")
    P("Danh sách lấy từ data/external/datasets.json, data/external/README.md và các báo cáo kiểm toán. Cột \"Từ\" cho biết phiên "
      "bản dữ liệu đầu tiên dùng nguồn đó.")
    R.table("Các nguồn dữ liệu dùng trong dự án", ["Bộ dữ liệu (mã / địa chỉ)", "Nội dung", "Giấy phép", "Cách dùng • từ"], [
        ("Roboflow xoài (export gốc)", "2.004 ảnh từ 926 ảnh gốc; 4 giai đoạn", "CC BY 4.0", "Detector + classifier xoài • vòng 0"),
        ("Roboflow thanh long (export gốc)", "3.007 ảnh; Unripe/Ripe/Rotten; nhãn polygon", "CC BY 4.0", "Từ v2 chỉ giữ crop quả nổi bật • vòng 0"),
        ("MangoYOLO – CQUniversity (acquire.cqu.edu.au, 13450661)", "1.730 ảnh, 15.281 box, chụp đêm có đèn", "CC BY 4.0", "Chỉ detector • 24/09"),
        ("CQU on-tree mango segmentation (21655628)", "542 tile tán cây, 5.314 mask", "CC BY 4.0", "Detector, mask → box • 24/09"),
        ("Mendeley 2jpzbx8tm6 – Dragon Fruit Maturity", "2.127 ảnh gốc Immature/Mature", "CC BY 4.0", "Classifier thanh long; bỏ từ v2"),
        ("Mendeley 2jpzbx8tm6 – Dragon Fruit Quality", "1.652 ảnh Fresh/Defect", "CC BY 4.0", "Không dùng: Fresh/Defect ≠ chín/hỏng"),
        ("DF pose v2 – Mendeley t8kbmg6cgz", "2.448 frame vườn, 4.637 box, 7 video", "CC BY 4.0", "Detector thanh long • orchard_v1"),
        ("MangoFruitBD v2 – Mendeley bhrz29mkmr", "1.070 ảnh xoài ban ngày, 1.841 box", "CC BY-NC", "Detector • orchard_v1"),
        ("DF-MOD Black_Rot – Mendeley kpsywfwkrf", "675 file, chỉ 270 ảnh khác nhau", "CC BY 4.0", "Thanh long rotten • v2"),
        ("Mendeley gcgrjvwmm2 – far-field mango", "1.023 ảnh xoài chụp xa/gần", "CC BY 4.0", "Detector • v3"),
        ("Mendeley mm8g66d7rc – mango ripening", "951 ảnh xoài chín dần trên bàn", "chưa ghi", "Classifier (turning) • v3"),
        ("Roboflow mango-tree (jerng-mi)", "690 ảnh cả cây, ~13 quả/ảnh", "CC BY 4.0", "Detector • v3"),
        ("Roboflow pitaya \"goodgoodgood\"", "992 ảnh hàng thanh long", "CC BY 4.0", "Detector • v3"),
        ("Roboflow ripe-dragon-fruits", "97 ảnh trụ thanh long chín", "CC BY 4.0", "Detector • v3"),
        ("Roboflow thanh-long-detection", "5.534 ảnh; 19 tên lớp lộn xộn", "CC BY 4.0", "Detector • v4"),
        ("10 nguồn ảnh âm tính (Roboflow)", "1.428 ảnh vải, chôm chôm, lựu, táo, cà chua, hoa thanh long", "CC BY 4.0 / MIT", "Ảnh không có quả • v4"),
        ("Wikimedia Commons", "11 ảnh xoài đỏ/trên cây, tự gán box", "CC0 / BY / BY-SA", "Detector • recovery C"),
    ], [5.2, 4.8, 2.2, 4.3], size=10.5)
    P("Hai điểm cần lưu ý về giấy phép: MangoFruitBD là CC BY-NC (phi thương mại; trang tải ghi 3.0, tệp README trong bộ ghi 4.0), "
      "và giấy phép của bộ Mendeley mm8g66d7rc chưa được ghi trong tệp nào của dự án — nhóm cần bổ sung trước khi công bố.")

    H(3, "3.1.1. Bộ DF pose là gì")
    P("DF pose (\"Dragon Fruit pose dataset v2\", tác giả Xing Yang) được gán nhãn cho bài toán ước lượng tư thế quả: mỗi dòng nhãn "
      "có 17 số theo định dạng YOLO-pose — lớp, 4 số của box và 4 keypoint × (x, y, độ hiển thị). Dự án chỉ cần vị trí quả nên "
      "script download_orchard_datasets.py chỉ giữ 5 số đầu, hai lớp tư thế được gộp thành dragonfruit, và hàm nạp "
      "load_orchard_detection kiểm tra mỗi dòng đúng 5 số. Quả trong bộ này rất nhỏ (box trung vị chiếm 0,62% diện tích ảnh) — "
      "đúng kiểu ảnh mô hình 7 lớp đã thất bại. Vì 2.448 frame chỉ đến từ 7 video, mọi frame của một video phải nằm chung một tập.")

    H(2, "3.2. Các lỗi dữ liệu đã tìm và sửa ngày 28/09")
    B(["**Polygon đọc thành box:** đổi mỗi polygon thành box bao ngoài; kiểm tra tọa độ trong [0, 1]; bỏ box diện tích 0.",
       "**Nhãn thanh long nhiễu:** kiểm toán tìm 145 nhãn độ chín mâu thuẫn với nhãn nguồn và 703 box nhỏ hơn 1% diện tích ảnh; "
       "cuống xanh bị gán Unripe, mảnh vụn bị gán Rotten. Chỉ giữ quả nổi bật, crop ≥ 64 px; ảnh mâu thuẫn bị cách ly.",
       "**Thiếu ảnh ngoài vườn:** thêm DF pose v2 và MangoFruitBD; frame cùng video chung một tập.",
       "**Thiếu quả hỏng thật:** thêm Black_Rot; 675 file chỉ có 270 ảnh duy nhất (bỏ 405 bản sao), gom 3 cặp chụp cùng quả.",
       "**Cổng sẵn sàng:** mỗi lớp cần ≥ 80 nhóm ảnh gốc ở train và ≥ 20 ở val/calib/test, nếu không script từ chối huấn luyện."])
    P("Kết quả là bộ maturity_v2: detector 10.438 ảnh, classifier xoài 2.534 crop, thanh long 1.416 crop; 22 test tự động pass.")

    H(2, "3.3. Lỗi polygon đọc thành box")
    P("Nhãn YOLO có hai dạng. Dạng box có đúng 5 số: lớp, x_tâm, y_tâm, rộng, cao. Dạng polygon có lớp rồi danh sách các điểm "
      "(x, y) chạy quanh viền quả. Bộ thanh long được xuất dưới tên \".yolov8\" nên trông như box nhưng thực ra là polygon. "
      "Hàm read_yolo_boxes ở commit f2c43ab chỉ lấy 4 số sau mã lớp (parts[1:5]) và coi là box, tức tọa độ điểm 1 bị hiểu thành "
      "tâm, tọa độ điểm 2 bị hiểu thành rộng và cao. Ví dụ dòng polygon:")
    R.code("1  0.41 0.27  0.55 0.25  0.61 0.38  0.58 0.52  0.44 0.55  0.39 0.41")
    P("bị đọc thành box tâm (0,41; 0,27), rộng 0,55, cao 0,25 — sai hoàn toàn. Box đúng (bao ngoài các điểm) là x từ 0,39 đến "
      "0,61, y từ 0,25 đến 0,55, tức tâm (0,50; 0,40), rộng 0,22, cao 0,30. Bản sửa trong training/prepare_two_stage_data.py nhận "
      "diện dòng có ≥ 7 số và tổng số giá trị lẻ là polygon, lấy min/max của các điểm để tạo box; test "
      "training/test_prepare_two_stage_data.py giữ cho lỗi không quay lại.")

    H(2, "3.4. Chín phiên bản dữ liệu")
    R.table("Số ảnh detector và thay đổi qua từng phiên bản (preparation_report.json)",
            ["Phiên bản", "Ngày", "Detector train / val / test", "Thay đổi chính và lý do"], [
        ("two_stage_public", "24/09", "1.570 / 354 / 342", "Chỉ có box xoài; lỗi polygon chưa phát hiện"),
        ("orchard_v1", "28/09", "7.522 / 1.610 / 1.663", "Thêm DF pose, MangoFruitBD; chia frame theo video"),
        ("maturity_v2", "28/09", "7.272 / 1.556 / 1.610", "Rà thanh long; cách ly 1.406 nhãn Fresh/Defect; Black_Rot"),
        ("maturity_v3 (đang dùng)", "29/09", "9.231 / 1.972 / 2.037", "+2.802 ảnh cả cây; lớp xoài theo hình thức"),
        ("detector_v4", "30/09", "14.094 / 3.016 / 3.077", "+5.534 thanh-long, +1.428 ảnh âm tính; 3 ảnh test rò rỉ"),
        ("v5_audit (A)", "02/10", "13.551 / 2.735 / 2.819", "Cách ly 1.082 ảnh có split/nhãn mâu thuẫn"),
        ("v5 bỏ âm tính giống (B)", "02/10", "13.278 / 2.735 / 2.819", "A bỏ 273 ảnh táo/lựu/cà chua"),
        ("v5_label_review", "02/10", "12.255 / 2.735 / 2.819", "Bỏ 1.604 box trùng; chưa đủ điều kiện huấn luyện"),
        ("v5_recovery_c (C)", "02/10", "9.183 / 2.735 / 2.819", "50 nhãn sửa ×4, 11 ảnh xoài ×16, thanh-long ≤ 600"),
    ], [3.8, 1.5, 4.0, 7.2], size=10.5, highlight={4})
    P("Với v3, classifier xoài có 2.688 / 351 / 235 / 234 crop (train / val / calib / test; train gồm young 1.119, mature 900, "
      "turning 155, ripe 514) và classifier thanh long 958 / 196 / 131 / 131 (giữ như v2). Từ thử nghiệm A trở đi, tập val và "
      "test được giữ giống hệt từng byte để mọi mô hình được so trên cùng một bộ.")

    H(2, "3.5. Quy tắc chất lượng viết thành code")
    R.table("Các quy tắc dữ liệu và nơi cài đặt", ["Quy tắc", "Cài đặt"], [
        ("Chống rò rỉ", "rf_group_id gom mọi bản \".rf.\" của một ảnh gốc; assert_no_group_leakage dừng nếu một nhóm nằm ở hai tập"),
        ("Bản sao gần giống", "fingerprint + cluster_records (dHash 64 bit, cả ảnh lật; lệch ≤ 4 bit và màu lệch ≤ 12) → gom nhóm; cụm lẫn nhãn bị cách ly"),
        ("Quả nổi bật", "dominant_fruit: box lớn nhất ≥ 10% ảnh, cạnh ≥ 64 px, tỉ lệ 0,25–4, các box khác nằm ≥ 90% trong nó"),
        ("Nhãn đúng nghĩa", "curate_dragon: nhãn box phải khớp nhãn nguồn; Fresh/Defect không bao giờ thành ripe/rotten"),
        ("Đủ dữ liệu mới train", "MIN_GROUPS = 80 / 20 / 20 / 20 nhóm mỗi lớp; thiếu thì \"BLOCKED\""),
        ("Giữ màu", "hsv_h = 0 và tắt auto_augment của classifier (auto_augment tự thêm biến đổi màu)"),
        ("Chia tập", "Detector 70/15/15; classifier 65/15/10/10 (train/val/calib/test), phân tầng theo nguồn và lớp"),
    ], [3.8, 12.7], size=11)

    H(3, "3.5.1. dHash – tìm ảnh gần giống")
    P("dHash (difference hash) là một thuật toán tạo \"dấu vân tay\" cho ảnh, nhóm tự cài trong khoảng 10 dòng ở hàm fingerprint() "
      "của training/maturity_data.py, chỉ dùng Pillow để thu nhỏ ảnh. Ảnh được chuyển xám, thu về 9×8 pixel; trên mỗi hàng so từng "
      "pixel với pixel bên phải (sáng hơn ghi 1, không thì 0) được số 64 bit. Làm thêm với ảnh lật ngang và giữ giá trị nhỏ hơn để "
      "ảnh lật vẫn ra cùng dấu vân tay; kèm một ảnh màu 8×8 để so màu. Hai ảnh bị coi là bản sao nếu số 64 bit khác không quá "
      "4 bit và màu lệch trung bình không quá 12 (thang 0–255). SHA256 chỉ bắt được ảnh trùng từng byte; dHash bắt được cả bản "
      "resize, nén lại, lật — nhờ vậy ngày 30/09 tìm ra 76/830 ảnh test của v4 có ảnh gần giống trong train. Giới hạn: hai ảnh "
      "chụp cùng quả từ hai góc có dHash khác xa nhau, nên 3 cặp Black_Rot phải được xác định bằng mắt (BLACK_ROT_VIEW_PAIRS).")

    H(2, "3.6. Rà soát nhãn detector (02/10)")
    P("Sau thất bại của v4, nhóm rà lại nhãn bằng hai script trong worktree gcp-vertex-training. "
      "**training/audit_detector_labels.py** chỉ đọc ảnh train và (1) kiểm tra tự động: thiếu tệp, dòng không phải số, lớp khác 0/1, "
      "box tràn ra ngoài ảnh, box trùng hệt nhau, số box lệch manifest, box có cạnh < 12 px khi ảnh về 960 px; (2) thống kê theo "
      "nguồn và so với bộ cũ; (3) chọn ngẫu nhiên 24 ảnh mỗi nguồn với seed cố định và vẽ box lên ảnh thành các trang 3×4 "
      "(xanh lá: xoài, xanh lơ: thanh long). Đợt 02/10 tạo 54 trang với 603 ảnh.")
    P("Người xem ghi quyết định vào review_decisions.json kèm hash ảnh, hash nhãn và lý do. **training/apply_detector_label_review.py** "
      "từ chối chạy nếu hash không khớp, chỉ cho cách ly ảnh train, cách ly cả nhóm (một frame lỗi kéo theo cả video), xóa box "
      "trùng, copy nguyên val/test và ghi ra một bộ dữ liệu mới. Kết quả rà:")
    B(["5 ảnh ghi \"không có quả\" thật ra có xoài; 12 ảnh thiếu hoặc lệch box (7 frame thanh long bỏ sót quả xanh hoặc đỏ).",
       "28 ảnh của nguồn \"hoa thanh long ban đêm\" là tranh vẽ, không phải ảnh vườn thật.",
       "1.604 box trùng hệt nhau trong 290 ảnh xoài trên cây (đã có từ v3).",
       "Tỉ lệ ảnh có xoài trong train giảm từ 53,1% xuống 36,0% sau khi thêm bộ thanh-long."])
    P("Lưu ý trung thực: theo PROJECT_HISTORY.md, việc xem bằng mắt lần này do trợ lý AI (Codex) thực hiện, không có người gán nhãn "
      "thứ hai kiểm tra lại; script cũng ghi rõ xem ảnh thu nhỏ không chứng nhận được mọi box đều đúng.")

    # ---------------- Chương 4
    R.chapter_heading("CHƯƠNG 4. PHƯƠNG PHÁP VÀ KIẾN TRÚC")
    H(2, "4.1. Pipeline hai giai đoạn")
    P("Thiết kế từ ngày 24/09 (commit f2c43ab) tách bài toán thành hai bước, mỗi bước có chỉ số riêng:")
    B(["**Detector** YOLOv8s 2 lớp (mango, dragonfruit) ở 960 px, ngưỡng confidence thấp 0,25 để không bỏ sót quả nhỏ; ảnh rất nhỏ "
       "chỉ được phóng to tối đa khoảng 2 lần.",
       "**Bộ lọc loài** (thêm 06/10, tùy chọn): YOLOv8n-cls 224 px với ba lớp mango / dragonfruit / other; loại box có P(other) ≥ 0,90.",
       "**Cắt quả:** nới box 10%; crop có cạnh < 64 px vẫn được đếm nhưng gắn uncertain (crop_too_small).",
       "**Classifier theo loài** YOLOv8s-cls 320 px; xác suất chia cho nhiệt độ T rồi so với ngưỡng (Mục 4.3).",
       "**Kết quả:** box, nhãn, độ tin cậy, lý do uncertain, số lượng theo lớp và ảnh đã vẽ box."])
    P("Lợi ích: biết lỗi nằm ở bước nào; dùng được bộ chỉ có box (MangoYOLO) cho detector và bộ chỉ có nhãn ảnh (Black_Rot) cho "
      "classifier; hệ thống vẫn đếm quả nhưng chỉ nói độ chín khi đủ chắc.")

    H(2, "4.2. Hiệu chỉnh xác suất")
    P("Nhãn uncertain **không được huấn luyện như một lớp**. Classifier chỉ học các lớp thật; uncertain là quyết định lúc suy luận dựa "
      "trên hai đại lượng tính trên một tập calibration riêng (không dùng để train, không dùng để test), cài trong hàm "
      "calibrate_classifier của training/train_two_stage.py:")
    B(["**Temperature T:** chia log-xác suất cho T rồi softmax lại; T được chọn bằng minimize_scalar trong khoảng 0,05–10 để "
       "negative log-likelihood trên tập calibration nhỏ nhất. Xoài v3: T = 2,154 (mô hình gốc quá tự tin), ECE giảm 0,071 → 0,034. "
       "Thanh long: T = 0,050 (chạm biên dưới vì tập calibration tách biệt hoàn toàn).",
       "**Ngưỡng riêng từng lớp** (choose_class_thresholds): với các crop được đoán là một lớp, xếp theo độ tin cậy giảm dần, tìm "
       "điểm thấp nhất mà nhóm phía trên vẫn đúng ≥ 80% (--target-precision 0.80) và có ít nhất max(5, 10%) mẫu; nếu không đạt thì "
       "ngưỡng = 1,0. Ngưỡng được lưu đủ độ chính xác float64 vì lỗi làm tròn 0,9999997868 → 1,0 từng loại nhầm crop đúng."])

    H(2, "4.3. Quy tắc gắn nhãn uncertain")
    P("Code trong backend/two_stage.py: quả bị gắn uncertain nếu (1) crop có cạnh ngắn hơn 64 px — lý do crop_too_small, classifier "
      "không chạy; hoặc (2) độ tin cậy sau hiệu chỉnh của lớp được đoán thấp hơn mức yêu cầu — lý do low_confidence, với")
    R.code("mức yêu cầu = max(ngưỡng người dùng, ngưỡng riêng của lớp)\nuncertain   = độ tin cậy < mức yêu cầu")
    R.table("Ngưỡng có hiệu lực của v3", ["Lớp", "Ngưỡng lớp", "Thanh trượt 0,55", "Thanh trượt 0,80"], [
        ("mango_young", "0,46", "0,55", "0,80"), ("mango_mature", "0,44", "0,55", "0,80"),
        ("mango_ripe", "0,54", "0,55", "0,80"), ("mango_turning", "0,82", "0,82", "0,82"),
        ("dragonfruit (3 lớp)", "≈ 1,0", "≈ 1,0", "≈ 1,0"),
    ], [5.0, 3.5, 4.0, 4.0])
    P("Ngưỡng người dùng là tham số ripeness_threshold của /detect (API mặc định 0,80, chỉ cho chọn 0,50–0,99). Vì vậy ngưỡng 0,44 và "
      "0,46 không bao giờ có hiệu lực một mình, và để thanh trượt 0,80 sẽ đè lên gần hết ngưỡng calibration. Ngày 03/10 nhóm hạ "
      "mặc định của giao diện trên Cloud Run xuống 0,55 và đổi thẻ kết quả thành \"Model nghiêng về: Xoài non · tin cậy 72,4% "
      "(cần ≥ 80%)\", vì người dùng đọc \"Độ chín 72,4%\" thành \"quả chín 72%\". Quả uncertain vẫn được đếm; JSON vẫn ghi lớp mô hình "
      "nghiêng về (candidate_class) và mức yêu cầu (required_ripeness_confidence).")

    H(2, "4.4. Tùy chọn ảnh tối, quét kỹ và đếm video")
    B(["**low_light_assist:** CLAHE trên kênh L của không gian LAB (clip 2,0, ô 8×8), chỉ đưa ảnh đã tăng sáng cho detector; "
       "classifier vẫn nhìn màu gốc để không làm sai độ chín.",
       "**detailed_scan:** chạy detector ở ít nhất 1280 px, NMS IoU 0,5 và test-time augmentation, cho ảnh nhiều quả chồng nhau. "
       "Chia ảnh thành ô 512 px đã thử ngày 02/10 nhưng tắt vì precision giảm 55,3% → 39,2%.",
       "**Video (backend/video.py):** lấy khoảng 5 khung/giây, ByteTrack (conf = min(ngưỡng, 0,1), IoU 0,7), mỗi yêu cầu một tracker "
       "riêng; một ID được đếm nếu xuất hiện ≥ 2 khung và có ≥ 1 box vượt ngưỡng; bộ lọc loài kiểm tra crop tốt nhất của mỗi ID; "
       "video không phân loại độ chín."])

    # ---------------- Chương 5
    R.chapter_heading("CHƯƠNG 5. HUẤN LUYỆN VÀ CÁC LẦN CHẠY LẠI")
    H(2, "5.1. Chuyển huấn luyện sang Vertex AI")
    P("Một lần huấn luyện đầy đủ cần 7–14 giờ trên Colab T4 và không thể chạy không người trông. Tài khoản Google Cloud Free Trial "
      "có quota GPU Compute Engine bằng 0, nhưng Vertex AI có quota Spot riêng. Ngân sách duy nhất là tín dụng Free Trial khoảng "
      "5,78 triệu đồng (hết hạn 10/12). Bộ script scripts/gcp/ tải bộ dữ liệu đã chuẩn bị lên Cloud Storage một lần, gửi Vertex AI "
      "custom job trên 1 × V100 Spot (n1-standard-8, giới hạn 24 giờ), ghi checkpoint mỗi epoch lên bucket để job bị thu hồi vẫn "
      "chạy tiếp, và có script xem tiến độ. Spot V100 khoảng $0,75–1,00/giờ so với $2,48/giờ thường; một lần chạy 4–5 giờ tốn "
      "khoảng $5–10. Lỗi nhỏ đã sửa: Vertex từ chối biến môi trường rỗng (commit 027ef31).")

    H(2, "5.2. Thông số huấn luyện của mô hình v3")
    R.table("Thông số từ args.yaml của job 4169118715503181824", ["", "Detector", "Classifier xoài", "Classifier thanh long"], [
        ("Mô hình gốc", "yolov8s.pt (COCO)", "yolov8s-cls.pt (ImageNet)", "yolov8s-cls.pt"),
        ("Lớp", "mango, dragonfruit", "young, mature, turning, ripe", "unripe, ripe, rotten"),
        ("Dữ liệu train/val/calib/test", "9.231 / 1.972 / – / 2.037 ảnh", "2.688 / 351 / 235 / 234", "958 / 196 / 131 / 131"),
        ("Ảnh • batch", "960 px • 8", "320 px • 32", "320 px • 32"),
        ("Epoch tối đa • patience", "100 • 25", "50 • 15", "50 • 15"),
        ("Optimizer", "AdamW, lr0 0,01, lrf 0,01, wd 0,0005, warmup 3", "như detector", "như detector"),
        ("Seed • AMP", "42 (deterministic) • có", "42 • có", "42 • có"),
        ("Tăng cường màu", "hsv_h 0, hsv_s 0,5, hsv_v 0,35", "hsv_h 0, hsv_s 0,35, hsv_v 0,25", "như xoài"),
        ("Tăng cường hình học", "xoay 7°, dịch 0,1, scale 0,4, lật ngang 0,5, mosaic 0,5 (tắt 10 epoch cuối), erasing 0,4",
         "xoay 10°, dịch 0,08, scale 0,25, lật ngang 0,5, erasing 0,1, auto_augment tắt", "như xoài"),
        ("Loss", "box 7,5 · cls 0,5 · dfl 1,5", "cross-entropy", "cross-entropy"),
        ("Thực tế", "100/100 epoch, tốt nhất epoch 86", "50/50 epoch (0,158 giờ), val top-1 86,0%", "dừng sớm epoch 22, tốt nhất epoch 7, val 100%"),
    ], [3.4, 4.8, 4.3, 4.0], size=10.5)
    P("Môi trường: 1 × V100 Spot, Ultralytics 8.4.155, torch 2.4.0; tổng thời gian job 3 giờ 54 phút.")

    H(2, "5.3. v2 (28/09, job 4689768257580695552)")
    P("Lần đầu trên Vertex AI, chạy 3 giờ 9 phút với bộ maturity_v2 và cùng cấu hình như Bảng 5.1. Detector đạt mAP50 98,5% "
      "(mAP50-95 80,9%) trên test; thanh long 131/131. Nhưng xoài chỉ đúng **63,9%** (92/144 crop; premature 42,6%, early 69,7%, "
      "mature 66,7%, ripe 92%). Kiểm tra ngày 29/09 tìm ra:")
    B(["**Lỗi làm tròn ngưỡng:** 0,9999997868 thành 1,0 nên loại crop thanh long đúng; sửa bằng float64 và xử lý trường hợp bằng nhau "
       "(test training/test_calibration_thresholds.py) → 128/131 lên 131/131 được nhận.",
       "**Xoài gần như luôn uncertain:** premature và mature không đạt precision 80% ở ngưỡng nào nên ngưỡng = 1,0; chỉ 18/144 quả có nhãn.",
       "**Ảnh chụp rộng:** cả trụ thanh long 3/~40 quả, cây xoài 8 quả; quét kích thước 640–1600 px không cải thiện → thiếu dữ liệu, không phải tham số.",
       "**Nguyên nhân xoài:** bộ Mendeley \"Mango Growth Stages\" chia premature/early/mature theo **số ngày sau đậu quả**, không nhìn "
       "thấy trên ảnh. Khi gộp về chín/chưa chín, mô hình đã đúng 97,9%."])

    H(2, "5.4. v3 (29/09, job 4169118715503181824) – mô hình đang dùng")
    P("v3 giữ nguyên cấu hình v2 và chỉ đổi dữ liệu, nên so sánh v2–v3 cho thấy đúng tác dụng của dữ liệu. Hai thay đổi: (1) lớp xoài "
      "định nghĩa theo cái nhìn thấy — young (premature + early cũ), mature (mature cũ + ripening stage 0 và 1), turning (mới, "
      "stage 2), ripe (ripe cũ + stage 3), dùng thêm 951 ảnh Mendeley mm8g66d7rc; (2) thêm 2.802 ảnh cả cây (far-field 1.023, "
      "mango-tree 690, pitaya 992, ripe dragon plants 97). Bộ detector tăng lên 13.240 ảnh (+27%) và 36.861 box (+60%).")
    R.table("Recall detector v2 → v3 trên cùng ảnh test (40 ảnh/nguồn) và các chỉ số khác",
            ["Phép đo", "v2", "v3"], [
        ("Cả cây xoài (rf_mango_tree)", "6,3%", "86,0%"),
        ("Hàng thanh long (rf_pitaya_orchard)", "25,2%", "91,6%"),
        ("Trụ thanh long (rf_ripe_dragon_plants)", "11,7%", "53,2%"),
        ("Xoài chụp xa (mango_farfield)", "63%", "76,5%"),
        ("Classifier xoài – accuracy", "63,9%", "90,2%"),
        ("Xoài được trả nhãn chắc chắn", "18/144", "179/234 (174 đúng)"),
        ("Ảnh thật: trụ thanh long / cây xoài", "3 / 8 quả", "22 / 46 quả"),
    ], [8.0, 3.5, 5.0])
    R.figure_row([V3_PHOTOS / "user_photo_2.jpg", V3_PHOTOS / "user_photo_3.jpg"], 6.5,
                 "Kết quả v3 trên ảnh thật: trụ thanh long 22 quả (trái) và cây xoài 46 quả, nhiều quả nhỏ là uncertain (phải)")

    H(2, "5.5. Kiểm tra v3 trên ảnh Internet (30/09)")
    P("Nhóm thử 37 ảnh Wikimedia Commons (từ khóa \"thanh long\", \"xoài\", \"dragon fruit plant\", \"mango tree\") và xem bằng mắt. "
      "Làm tốt: tìm thấy xoài ở 10/11 ảnh có xoài (31 quả trên một cây đông), xoài vàng chín đúng nhãn, thanh long trên trụ đúng, "
      "gần như không báo nhầm lá, hoa, nhà. Lỗi mới: vải bị gọi là thanh long, hoa thanh long bị gọi là quả xanh, xoài đỏ và xoài "
      "xanh cận cảnh hay uncertain. Trên ảnh âm tính, v3 tạo 214 box sai trên ảnh vải Việt Nam, 174 trên litchi, 73 trên táo, "
      "27 trên chôm chôm, 22 trên lựu. Đây là lý do làm v4.")

    H(2, "5.6. v4 (30/09, job 5533271247212773376): job thành công nhưng mô hình hỏng")
    P("v4 chỉ huấn luyện lại detector và đổi nhiều thứ cùng lúc: 20.187 ảnh (thêm 5.534 ảnh thanh-long và 1.428 ảnh âm tính), "
      "1280 px, fine-tune từ v3 trong 50 epoch với lr0 khởi đầu lại 0,01 (4,07 giờ). Lúc huấn luyện mAP50 validation đạt 93,3%, "
      "nhưng tải lại best.pt chỉ còn **31,4%**, thanh long trên test 1,1%. Nguyên nhân: checkpoint lưu ở FP16 làm **27 phương sai "
      "BatchNorm** ở đầu ra bão hòa tại 65.504 (giá trị lớn nhất của FP16); mọi giá trị vẫn hữu hạn nên kiểm tra NaN không phát hiện.")
    P("Bản ước lượng lại BatchNorm vẫn mất xoài: ảnh cụm xoài nhỏ 11 → 0 quả, ảnh xoài đỏ 10 → 5. Kiểm tra dHash tìm thấy 76/830 "
      "ảnh test có ảnh gần giống trong train, và bộ rf_ripe_dragon_plants bị chia lại tập sau khi khử trùng. Vì đổi quá nhiều thứ "
      "cùng lúc, nhóm không biết thay đổi nào gây lỗi xoài. Sửa: lưu checkpoint FP32 (định dạng fruit-fp32-v1), kiểm tra dự đoán "
      "trước/sau khi lưu giống hệt (commit d4b85a1); giữ v3. **Bài học: job chạy xong không có nghĩa mô hình dùng được.**")

    H(2, "5.7. Chuẩn bị đánh giá công bằng (02/10)")
    B(["**Checkpoint an toàn:** best.pt FP32, last.pt giữ optimizer và EMA; kiểm tra tensor hữu hạn, BatchNorm hợp lệ, dự đoán giống "
       "hệt sau khi tải lại. Smoke test trên CPU: cố ý ngắt sau epoch 0, resume, chạy xong epoch 2.",
       "**Benchmark cố định:** 234 ảnh validation, 584 quả, 112 ảnh không có quả; 960 px, conf 0,25, IoU 0,5; hash ảnh và nhãn được "
       "kiểm tra mỗi lần. Cộng thêm các ảnh thật của nhóm làm ảnh hồi quy.",
       "**Tiêu chí đặt trước:** mô hình mới chỉ thay v3 nếu lấy lại được các ảnh xoài bị mất.",
       "44 test pass; frontend build và lint pass."])

    H(2, "5.8. Thử nghiệm A / B / C (02/10)")
    P("Cả ba fine-tune detector v3 trong 10 epoch, 960 px, batch 8, lr0 = 0,0001, seed 42, V100 Spot giới hạn 2 giờ; tập val/test giống "
      "nhau từng byte. Chỉ dữ liệu train khác nhau.")
    R.table("Thiết lập ba thử nghiệm", ["Thử", "Job • thời gian", "Dữ liệu khác nhau"], [
        ("A", "5756784368953589760 • 33 phút", "Dữ liệu đã kiểm toán, có ảnh âm tính (13.551 ảnh train)"),
        ("B", "2208933025004126208 • 32 phút", "Như A nhưng bỏ 273 ảnh táo/lựu/cà chua"),
        ("C", "3521406860940804096 • ~26 phút", "50 nhãn sửa ×4, 11 ảnh xoài Wikimedia ×16, thanh-long ≤ 600 → tỉ lệ ảnh có xoài về 53,3%"),
    ], [1.2, 5.3, 10.0])
    P("Trước khi chạy C có một sự cố: khi kiểm tra cục bộ, Ultralytics gặp một JPEG bị cắt và tự \"sửa\" bằng cách ghi đè tệp; tệp "
      "này được hard-link vào 5 bộ dữ liệu nên cả 5 thay đổi. Bước kiểm tra hash phát hiện, nhóm khôi phục bản gốc rồi mới gửi job.")
    R.table("Kết quả trên benchmark cố định và ảnh hồi quy", ["Chỉ số / ảnh", "v3", "A", "B", "C"], [
        ("Precision", "55,3%", "66,4%", "64,7%", "67,8%"),
        ("Recall", "82,5%", "82,7%", "82,5%", "82,4%"),
        ("Sai số đếm trung bình (quả/ảnh)", "1,83", "1,21", "1,30", "1,17"),
        ("Box sai trên 112 ảnh âm tính", "290", "161", "177", "142"),
        ("Cụm xoài chín nhỏ (số box)", "11", "4", "4", "4"),
        ("Xoài đỏ trên cây", "10", "5", "5 + 2 sai loài", "7"),
        ("Cả trụ thanh long", "22", "15", "13", "14"),
        ("Cây xoài", "46", "38", "38", "41"),
    ], [6.5, 2.5, 2.5, 2.5, 2.5])
    P("Theo tiêu chí đặt trước, **không bản nào thay v3**. Quét ngưỡng confidence từ 0,05 đến 0,4 cho thấy recall nguồn xoài trên "
      "cây không vượt khoảng 53% ở bất kỳ ngưỡng nào — mô hình không thấy các quả này, không phải do ngưỡng. Giả thuyết còn lại: "
      "khoảng 560 ảnh âm tính vải, litchi, chôm chôm trông giống cụm xoài đỏ nhỏ; đây là giả thuyết cần kiểm chứng.")

    # ---------------- Chương 6
    R.chapter_heading("CHƯƠNG 6. CÀI ĐẶT HỆ THỐNG")
    H(2, "6.1. Kiến trúc ứng dụng")
    P("Frontend React + Ant Design (Vite) cho phép tải ảnh hoặc video, chỉnh thanh trượt ngưỡng phát hiện (0,25) và ngưỡng độ chín, "
      "bật hai công tắc \"Hỗ trợ ảnh thiếu sáng\" và \"Quét kỹ ảnh nhiều quả\". Backend FastAPI kiểm tra định dạng, kích thước, xoay "
      "ảnh theo EXIF, rồi gọi pipeline chạy bằng Ultralytics 8.4.155 trên PyTorch CPU; video dùng ByteTrack (thư viện lap). Khi build "
      "frontend, FastAPI phục vụ luôn giao diện tại \"/\".")
    R.table("Các endpoint của API", ["Endpoint", "Tham số chính → kết quả"], [
        ("GET /health", "pipeline_mode (two-stage / legacy), model_loaded, detector_imgsz, other_fruit_filter, model_classes"),
        ("POST /detect", "ảnh ≤ 12 MB; conf_threshold 0,25; ripeness_threshold 0,80; low_light_assist; detailed_scan → total_count, "
                         "counts, detections[] (bbox, species, class_name, ripeness_confidence, uncertain, uncertainty_reason, "
                         "candidate_class, required_ripeness_confidence, other_fruit_probability), ảnh JPEG base64"),
        ("POST /detect-video", "mp4/m4v/mov/webm/avi ≤ 50 MB, ≤ 30 giây, ≤ 1080p → total_unique_count, counts, khung hình minh họa"),
        ("GET /docs", "Swagger UI tự sinh từ FastAPI"),
    ], [3.5, 13.0], size=11)

    H(2, "6.2. Các dịch vụ cloud")
    R.table("Dịch vụ Google Cloud và các nền tảng khác", ["Dịch vụ", "Dùng để", "Chi tiết"], [
        ("Cloud Run", "Host ứng dụng", "Service fruit-detection, asia-southeast1; 1 CPU, 2 GiB, timeout 120 s, concurrency 1, tối đa 1 instance, tự tắt; "
                                       "fruit-detection-542444439835.asia-southeast1.run.app"),
        ("Cloud Build", "Build Docker image khi deploy", "gcloud run deploy --source; cấp role Cloud Run Builder cho service account"),
        ("Artifact Registry", "Lưu image", "Nơi deploy --source mặc định đẩy image (suy ra từ cách deploy)"),
        ("Vertex AI custom job", "Huấn luyện", "us-central1, 1 × V100 Spot, n1-standard-8; job v2, v3, v4, A, B, C"),
        ("Cloud Storage", "Dữ liệu và checkpoint", "Bucket project-1c166153-8e72-4d82-9e0-fruit-training"),
        ("Colab + Google Drive", "Huấn luyện vòng 0–2", "Không còn dùng"),
        ("Modal", "Thử host", "Thất bại vì giới hạn chi tiêu $0; modal_app.py vẫn còn trong repo"),
        ("Cloudflare quick tunnel", "Host tạm từ laptop", "Chỉ chạy khi laptop bật"),
    ], [3.6, 3.9, 9.0], size=11)

    H(2, "6.3. Lịch sử triển khai Cloud Run")
    R.table("Các revision đã triển khai", ["Ngày", "Revision / tag", "Nội dung và lý do"], [
        ("24/09", "00001-z2h", "Mô hình 7 lớp; ~7,6 giây/ảnh; giữ để rollback"),
        ("03/10", "00003-hat • v3-mobile", "v3 + giao diện điện thoại. Sửa Dockerfile thiếu module, thêm .gcloudignore để không mất weight; "
                                            "deploy_cloud_run.sh tạo revision chưa nhận traffic → smoke test → PROMOTE=1"),
        ("03/10", "00005-yap • v3-ui-fix", "Thẻ độ chín mới; ngưỡng mặc định giao diện 0,55"),
        ("06–08/10", "fix4", "v3 + bộ lọc loài + video + ảnh tối + quét kỹ"),
    ], [2.2, 4.3, 10.0], size=11)
    P("Kiểm tra image trong giới hạn của Cloud Run (1 CPU, 2 GiB): sẵn sàng sau khoảng 3 giây, RAM tối đa 572 MiB, 1,4–2,1 giây mỗi ảnh "
      "(trụ thanh long 22 quả trong 1,8 giây, cây xoài 46 quả trong 1,4 giây); yêu cầu đầu tiên sau khi dịch vụ tự tắt sẽ chậm hơn. "
      "Lưu ý vận hành: .dockerignore của bản chính chưa cho phép tệp species_verifier.pt, nên build mới sẽ mất bộ lọc nếu không thêm dòng này.")

    H(2, "6.4. Tính năng thêm 05–06/10")
    P("Mỗi tính năng xuất phát từ một ảnh lỗi cụ thể. Ảnh mận trên tay bị v3 gọi là \"thanh long chín 100%\"; nhóm huấn luyện nhanh bộ "
      "lọc loài YOLOv8n-cls 3 lớp trên CPU laptop (5 epoch, 224 px, lớp \"other\" lấy ảnh mận Wikimedia), bật lên thì hai box sai biến "
      "mất. Với ảnh tối tổng hợp (gamma 2,2, phơi sáng 35%), ảnh thường tìm 13 quả, làm tối còn 2, bật hỗ trợ lên 6. Quét kỹ trên ảnh "
      "5 xoài chồng nhau tăng từ 2 lên 4 quả. Dữ liệu huấn luyện bộ lọc nằm trong thư mục tạm và đã mất — đây là nguồn gốc của lỗi ở Mục 7.4.")
    R.figure_row([CASES / "filter_plum_off.jpg", CASES / "filter_plum_on.jpg"], 5.0,
                 "Ảnh mận: tắt bộ lọc có 2 box sai (trái), bật bộ lọc còn 0 box (phải)")
    R.figure_row([CASES / "low_0_normal.jpg", CASES / "low_0_dark.jpg", CASES / "low_0_assist.jpg"], 4.5,
                 "Ảnh thường 13 quả, làm tối 2 quả, làm tối + hỗ trợ ảnh tối 6 quả")

    H(2, "6.5. Kiểm thử")
    B(["Dữ liệu: 22 test (28/09) → 44 test (02/10 sáng) → 56 test (02/10 tối, gồm bảo vệ import/review) → 63 test khi tạo recovery C.",
       "Checkpoint: test FP16 guard, safe checkpoints, smoke test CPU có ngắt và resume.",
       "Ứng dụng: /health và tải bốn ảnh thật trả HTTP 200 với số lượng nhất quán; giao diện điện thoại kiểm tra bằng Chromium headless "
       "ở 320–1280 px (chưa thử trên điện thoại thật); video thử ở Mục 7.5."])

    # ---------------- Chương 7
    R.chapter_heading("CHƯƠNG 7. KẾT QUẢ VÀ PHÂN TÍCH LỖI")
    H(2, "7.1. Detector v3")
    R.table("Detector v3 trên tập test (2.037 ảnh, 7.468 box)", ["Tập", "Precision", "Recall", "mAP50", "mAP50-95"], [
        ("Val, epoch 86", "92,8%", "89,8%", "95,2%", "69,0%"),
        ("Test – tất cả", "92,2%", "88,3%", "94,9%", "68,3%"),
        ("Test – xoài", "92,6%", "86,6%", "94,2%", "66,4%"),
        ("Test – thanh long", "91,8%", "90,0%", "95,6%", "70,1%"),
    ], [5.0, 2.9, 2.9, 2.9, 2.9], highlight={2})
    P("mAP thấp hơn v2 vì tập test v3 có thêm ảnh cả cây khó hơn, không phải mô hình kém đi.")

    H(2, "7.2. Classifier và độ tin cậy")
    R.table("Classifier v3 trên tập test", ["", "Xoài (234 crop)", "Thanh long (131 crop)"], [
        ("Accuracy", "90,2% (211/234)", "100% (131/131)"),
        ("Recall theo lớp", "turning 24/24 · ripe 47/49 · mature 76/87 · young 64/74", "ripe 46/46 · rotten 27/27 · unripe 58/58"),
        ("Nhầm lẫn chính", "mature → young 11; young → mature 8; ripe ↔ young 2 + 2", "không có"),
        ("Được trả nhãn", "179/234 (76%), trong đó 174 đúng (97,2%)", "131/131"),
        ("Theo nguồn", "Mendeley ripening 96/96 · Roboflow 115/138", "Roboflow 104/104 · Black_Rot 27/27"),
        ("Hiệu chỉnh (calib)", "T = 2,154; ECE 0,071 → 0,034; accuracy 87,7%", "T = 0,050; ECE 0,004 → 0; accuracy 100%"),
    ], [3.4, 7.0, 6.1], size=11)
    P("Với xoài, hiệu chỉnh có tác dụng thật. Mô hình đoán sai 23/234 crop; ngưỡng uncertain giữ lại 18 trong 23 lỗi đó (78%), chỉ 5 "
      "lỗi lọt ra thành nhãn sai; đổi lại 37 crop đúng cũng bị gắn uncertain. Lỗi dồn vào hai lớp xanh young và mature — đúng chỗ khó "
      "nhìn bằng mắt. Với thanh long, độ tin cậy luôn ≈ 1,0 nên không phân biệt được ca dễ hay khó (Mục 7.6). Nhóm chưa kiểm tra con số "
      "179/234 được đo với ngưỡng lớp hay với max(0,80; ngưỡng lớp); nên chạy lại ở cả hai mức nếu cần báo cáo chính xác.")

    H(2, "7.3. Đánh giá lại pipeline đang chạy (08/10)")
    P("Nhóm chạy lại toàn bộ pipeline đã triển khai trên 2.037 ảnh test, 400 ảnh không có quả và 200 ảnh làm tối, so sánh bật/tắt bộ lọc loài "
      "(tệp eval/summary.json của thư mục trình bày).")
    R.table("Kết quả đánh giá ngày 08/10", ["Phép đo", "Lọc tắt", "Lọc bật"], [
        ("Recall tổng (7.768 quả)", "88,8%", "88,5%"),
        ("Precision tổng", "84,1%", "84,1%"),
        ("Box sai trên 400 ảnh không có quả", "1.103", "264"),
        ("Ảnh âm tính còn box sai", "276/400", "114/400"),
        ("Ảnh vải còn box sai", "—", "28/40"),
        ("Recall ảnh thường / tối / tối + hỗ trợ", "86,4% / 54,0% / 62,9%", ""),
        ("Recall theo nguồn yếu nhất", "xoài trên cây 56,4%; trụ thanh long 53,2%", ""),
        ("Nhãn độ chín", "2.493 chắc chắn / 5.673 uncertain (~3/4 do crop < 64 px)", ""),
    ], [7.0, 5.5, 4.0], size=11)
    R.table("Recall theo nguồn (lọc tắt)", ["Nguồn", "Recall", "Nguồn", "Recall"], [
        ("dragon_fruit_orchard", "99,7%", "rf_pitaya_orchard", "90,7%"),
        ("rf_dragonfruit_curated", "100%", "mango_orchard_daylight", "90,1%"),
        ("mango_yolo", "97,9%", "rf_mango_tree", "86,9%"),
        ("rf_mango", "96,5%", "mango_farfield", "78,3%"),
        ("mango_on_tree", "56,4%", "rf_ripe_dragon_plants", "53,2%"),
    ], [4.8, 3.4, 4.8, 3.4], size=11)

    H(2, "7.4. Lỗi bộ lọc loài xóa nhầm xoài chín")
    P("Khi đếm theo mức chín, bộ lọc loài xóa **24/49 xoài chín** và **8/24 xoài turning** trong tập test, dù detector vẫn chấm các quả "
      "này 0,70–0,87. Bộ lọc được huấn luyện nhanh với ảnh mận và học rằng vỏ vàng cam có đốm là \"quả khác\". Số tổng không phát hiện "
      "lỗi vì tập test detector chủ yếu là xoài xanh, nên recall tổng chỉ giảm 0,3 điểm. Cách sửa: huấn luyện lại bộ lọc với crop xoài "
      "chín và xoài có đốm trong lớp mango, rồi kiểm tra tỉ lệ bị loại theo từng mức chín trước khi deploy; trong lúc chờ, tắt bộ lọc "
      "khi cần đánh giá độ chín (SPECIES_VERIFIER_PATH trỏ tới tệp không tồn tại).")
    R.figure_row([CASES / "filter_spotted_off.jpg", CASES / "filter_spotted_on.jpg"], 7.0,
                 "Xoài chín có đốm: tắt bộ lọc nhận \"mango ripe 89%\" (trái), bật bộ lọc mất hết (phải)")

    H(2, "7.5. Đếm quả trong video")
    P("Video vườn thanh long 20 giây (100 khung) đếm được 3 quả. Video giả lập lia máy qua cây xoài 12 giây (60 khung) đếm 12 trong khi "
      "thực tế 8 — một chiếc lá bị nhận là xoài, và quả bị che rồi xuất hiện lại được gán ID mới. Số đếm video là ước lượng; chưa có "
      "video vườn thật có số quả chuẩn để đo sai số.")

    H(2, "7.6. Vì sao các con số cao và con số nào nên tin")
    P("Một phần con số cao là thật: detector chỉ còn 2 lớp khác nhau rõ, và độ chín có tín hiệu màu mạnh (turning 24/24, ripe 47/49); "
      "chỉ đổi định nghĩa lớp xoài đã nâng accuracy từ 63,9% lên 90,2%. Phần còn lại đến từ cách đo:")
    B(["Test cùng nguồn, cùng camera, cùng kiểu nền với train — kiểm tra trong phân phối quen thuộc.",
       "Crop classifier đã chọn lọc (quả nổi bật, ≥ 64 px); ca mơ hồ bị cách ly.",
       "Có nguồn rất dễ: Mendeley ripening là xoài trên bàn trắng (96/96), trong khi Roboflow chỉ 115/138 (83%).",
       "mAP50 dễ tính (IoU ≥ 0,5); ở mức chặt mAP50-95 chỉ 68,3%.",
       "Có thể còn rò rỉ: 76/830 ảnh test v4 có ảnh gần giống trong train."])
    P("**Classifier thanh long có overfitting không?** Không theo nghĩa thông thường: trong results.csv, train loss và val loss cùng giảm "
      "(val loss 0,007 ở epoch 7, 0,0004 ở epoch 22), không có lúc val loss tăng, và test riêng cũng 131/131. Vấn đề là tập đánh giá "
      "quá dễ và mô hình có thể học tắt: toàn bộ lớp rotten đến từ một bộ (Black_Rot), ripe/unripe từ bộ khác, nên mô hình có thể "
      "phân biệt theo \"kiểu ảnh\" thay vì vết thối; đạt 100% từ epoch 7 và T chạm biên 0,05. Ở thử nghiệm B, hai quả xoài đỏ bị chuyển "
      "nhầm sang nhánh thanh long và vẫn được gọi là \"chín\" với độ tin cậy rất cao. Cách kiểm chứng: gán nhãn vài chục crop thanh "
      "long cắt từ ảnh vườn, hoặc thêm ảnh quả thối từ nguồn khác, rồi đo lại.")
    R.table("So sánh phép đo dễ và khó", ["Phép đo", "Kết quả"], [
        ("Detector, tập test chính", "mAP50 94,9%, recall 88,3%"),
        ("Benchmark 234 ảnh có ảnh âm tính", "precision 55,3%, 290 box sai trên 112 ảnh"),
        ("Xoài dày trên cây / trụ thanh long", "recall 56% / 53%"),
        ("Ảnh tối", "recall 54% (63% khi bật hỗ trợ)"),
        ("Cả pipeline trên ảnh nguyên", "~30% quả có nhãn độ chín chắc chắn"),
    ], [8.0, 8.5])

    # ---------------- Chương 8
    R.chapter_heading("CHƯƠNG 8. KẾT LUẬN, BÀI HỌC VÀ HƯỚNG PHÁT TRIỂN")
    H(2, "8.1. Kết quả đạt được")
    B(["Pipeline hai giai đoạn có hiệu chỉnh xác suất và nhãn uncertain; mô hình v3 đạt mAP50 94,9% và accuracy độ chín xoài 90,2% trên tập test cùng nguồn.",
       "Quy trình dữ liệu chống rò rỉ, khử trùng, rà nhãn được viết thành code và có test.",
       "Hạ tầng huấn luyện trên Vertex AI có checkpoint an toàn và benchmark cố định.",
       "Ứng dụng web/API chạy trên Cloud Run, có đếm video, hỗ trợ ảnh tối, quét kỹ và lọc quả khác."])
    H(2, "8.2. Năm bài học")
    B(["**Sửa dữ liệu trước khi train lại:** ba vòng thất bại vì dữ liệu (polygon, nhãn theo tuổi quả, thiếu ảnh cả cây); thêm epoch không sửa được.",
       "**Kiểm tra trên đúng loại ảnh sẽ dùng:** 91% và 98,5% che giấu thất bại trên ảnh cả cây vì test giống train.",
       "**Confidence thô không phải xác suất:** hiệu chỉnh và nhãn uncertain cho câu trả lời trung thực.",
       "**Nhãn phải nhìn thấy được:** chỉ đổi định nghĩa lớp xoài, accuracy từ 63,9% lên 90,2%.",
       "**Bảo vệ và kiểm tra checkpoint, xem kết quả theo nhóm:** v4 cho thấy job xong chưa chắc mô hình dùng được; A/B/C và bộ lọc "
       "loài đều đẹp trên số tổng nhưng làm mất xoài chín."])
    H(2, "8.3. Hạn chế")
    B(["Bộ lọc loài xóa 24/49 xoài chín; xoài dày trên cây và trụ thanh long dày quả chỉ ~53–56% recall; vải/litchi vẫn bị nhận nhầm.",
       "Ảnh tối 54% (63% khi hỗ trợ); video mới là ước lượng.",
       "Classifier thanh long 100% chưa kiểm chứng ngoài tập tuyển chọn.",
       "MangoFruitBD phi thương mại; giấy phép mm8g66d7rc chưa ghi.",
       "Chưa có ảnh/video có nhãn từ vườn mục tiêu."])
    H(2, "8.4. Hướng phát triển (theo chi phí)")
    B(["Huấn luyện lại bộ lọc loài với xoài chín/đốm và kiểm tra tỉ lệ loại theo từng mức chín.",
       "Thử giới hạn phóng to cho ảnh nhỏ trên benchmark (chỉ cần đánh giá, không cần train).",
       "Nếu train tiếp, mỗi lần chỉ đổi một yếu tố (ví dụ C bỏ ảnh vải/chôm chôm).",
       "Sửa nhãn 1.246 frame thanh long đang bị cách ly.",
       "Thu ảnh và video có nhãn từ đúng vườn, đúng camera; giữ một tập test chưa đụng tới cho mô hình được chọn."])

    # ---------------- References
    R.chapter_heading("TÀI LIỆU THAM KHẢO")
    refs = [
        "G. Jocher, A. Chaurasia, J. Qiu. Ultralytics YOLOv8, 2023. https://github.com/ultralytics/ultralytics",
        "C. Guo, G. Pleiss, Y. Sun, K. Q. Weinberger. On Calibration of Modern Neural Networks. ICML, 2017.",
        "Y. Zhang et al. ByteTrack: Multi-Object Tracking by Associating Every Detection Box. ECCV, 2022.",
        "A. Koirala, K. B. Walsh, Z. Wang, C. McCarthy. Deep learning for real-time fruit detection and orchard fruit load estimation: "
        "benchmarking of 'MangoYOLO'. Precision Agriculture 20, 2019.",
        "K. Zuiderveld. Contrast Limited Adaptive Histogram Equalization. Graphics Gems IV, 1994.",
        "N. Krawetz. Kind of Like That (dHash). The Hacker Factor Blog, 2013.",
        "MangoYOLO data set, CQUniversity: https://acquire.cqu.edu.au/articles/dataset/MangoYOLO_data_set/13450661",
        "Mendeley Data: 2jpzbx8tm6 (Dragon fruit maturity/quality), t8kbmg6cgz (DF pose v2), bhrz29mkmr (MangoFruitBD v2), "
        "kpsywfwkrf (DF-MOD), gcgrjvwmm2 (on-tree mango), mm8g66d7rc (mango ripening). https://data.mendeley.com/datasets/<mã>",
        "Roboflow Universe: jerng-mi/mango-tree-rya7c, pitaya-2jhyv/goodgoodgood, training-dwctq/ripe-dragon-fruits, "
        "thanh-long-v1/thanh-long-detection-znzlc. https://universe.roboflow.com",
    ]
    for i, ref in enumerate(refs, 1):
        para = R.d.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.8)
        para.paragraph_format.first_line_indent = Cm(-0.8)
        add_runs(para, f"[{i}]  {ref}", size=12)
    H(2, "Tệp minh chứng trong dự án")
    R.table("Nơi kiểm tra số liệu", ["Minh chứng", "Đường dẫn"], [
        ("Lịch sử dự án", ".claude/worktrees/gcp-vertex-training/docs/PROJECT_HISTORY.md"),
        ("Job Vertex (args, results, review)", "fruit_detection_runs_gcp_review/<mã job>/"),
        ("Benchmark + A/B/C", "fruit_detection_runs_gcp_review/regression_20261002/trial_abc_summary.json"),
        ("Rà nhãn 02/10", "fruit_detection_runs_gcp_review/label_audit_20261002/"),
        ("Dữ liệu (phiên bản, nguồn)", "data/prepared/*/preparation_report.json; data/external/datasets.json"),
        ("Đánh giá 08/10", "fruit_detection_presentation/eval/summary.json"),
    ], [5.0, 11.5], size=11)

    # ---------------- Appendices
    R.chapter = "A"
    R.chapter_heading("PHỤ LỤC A. LỜI THUYẾT TRÌNH THEO TỪNG SLIDE")
    P("Nội dung dưới đây chép từ Speaker Notes của tệp Smart_Orchard_AI_Thuyet_trinh_nhom.pptx (do reports/build_presentation.py tạo), "
      "để người trình bày có thể in ra và luyện tập.")
    for i, (title, note) in enumerate(slide_notes(), 1):
        H(3, f"Slide {i:02d}. {title}")
        for chunk in [c.strip() for c in note.split("\n\n") if c.strip()]:
            P(" ".join(chunk.split()), indent=False, size=12)

    R.chapter = "B"
    R.chapter_heading("PHỤ LỤC B. CÁCH CHẠY VÀ KỊCH BẢN DEMO")
    H(2, "B.1. Chạy tại máy")
    R.code("python3 -m venv .venv && source .venv/bin/activate\npip install -r backend/requirements.txt\n"
           "uvicorn backend.app:app --host 127.0.0.1 --port 8000\n# terminal thứ hai\ncd frontend && npm ci && npm run dev   # http://localhost:5173")
    P("Biến môi trường: PIPELINE_MODE (auto / two-stage / legacy), DETECTOR_IMGSZ (960), OTHER_FRUIT_THRESHOLD (0,90), "
      "SPECIES_VERIFIER_PATH (trỏ tới tệp không tồn tại để tắt bộ lọc). Weight v3 và tệp calibration phải có trong backend/weights. "
      "Gọi API trực tiếp:", indent=False)
    R.code('curl -F "file=@anh.jpg" "http://localhost:8000/detect?conf_threshold=0.25&detailed_scan=true"')
    H(2, "B.2. Kịch bản demo (~6 phút)")
    R.table("Các bước demo", ["#", "Thao tác", "Tệp / cài đặt", "Điều cần chỉ ra"], [
        ("1", "Mở /health", "…/health", "pipeline_mode = two-stage, other_fruit_filter"),
        ("2", "Thanh long cận cảnh", "dragon-fruit-pucka-fertilizer-1.jpg", "3 box, nhãn chín + độ tin cậy"),
        ("3", "Cả trụ thanh long", "tru-cay-thanh-long.jpg", "~22 quả; quả nhỏ → uncertain"),
        ("4", "Cây xoài nhiều quả", "oxi-house-cay-xoai-tu-quy-2_…jpg", "~46 box; thẻ \"Model nghiêng về …\""),
        ("5", "Quả khác", "images (9).jpeg (mận)", "Lọc tắt có box sai → bật còn 0"),
        ("6", "Xoài chồng nhau", "images (7).jpeg + \"Quét kỹ\"", "2 → 4 trên 5 quả"),
        ("7", "Video", "orchard_dragon_input.mp4 (20 s)", "Số quả duy nhất, khung minh họa"),
        ("8", "Lỗi đã biết", "Xoài chín có đốm, lọc bật/tắt", "Bộ lọc xóa xoài chín → bài học"),
    ], [0.8, 3.6, 6.0, 6.1], size=11)
    P("Chuẩn bị: mở trang Cloud Run trước 1–2 phút (dịch vụ tự tắt khi không dùng). Nếu mạng hoặc máy lỗi, dùng ảnh kết quả có sẵn "
      "trong báo cáo và video đã gán nhãn *_annotated.mp4. Rollback Cloud Run: gcloud run services update-traffic fruit-detection "
      "--region=asia-southeast1 --to-revisions=<revision>=100.", indent=False)

    R.chapter = "C"
    R.chapter_heading("PHỤ LỤC C. CÁC TỆP MÃ NGUỒN XỬ LÝ DỮ LIỆU")
    P("Bản dùng để tạo dữ liệu v3 trở đi nằm trong worktree gcp-vertex-training (đã merge lên origin/main); bản checkout chính dừng ở maturity_v2.")
    R.table("Tệp Python xử lý dữ liệu", ["Tệp", "Chức năng"], [
        ("scripts/download_orchard_datasets.py", "Tải DF pose v2 và MangoFruitBD; kiểm tra CRC/SHA256, chuẩn hóa box"),
        ("scripts/download_dragon_black_rot.py", "Tải Black_Rot của DF-MOD; kiểm tra đủ 675 tệp theo hash"),
        ("scripts/download_roboflow_detection.py", "Tải các bộ Roboflow ảnh cả cây"),
        ("scripts/download_negatives.py", "Tải ảnh âm tính (quả khác, hoa thanh long)"),
        ("scripts/audit_public_datasets.py", "Kiểm kê các bộ đã tải"),
        ("training/prepare_two_stage_data.py", "Gộp nguồn, polygon → box, ánh xạ nhãn, chia tập theo nhóm, cắt crop, chống rò rỉ"),
        ("training/maturity_data.py", "Rà nhãn thanh long, dHash, cổng sẵn sàng 80/20"),
        ("training/detector_splits.py", "Chia tập detector ổn định, gom bản sao"),
        ("training/prepare_detector_trial.py", "Tạo dữ liệu thử nghiệm A/B"),
        ("training/audit_detector_labels.py", "Kiểm tra nhãn tự động và vẽ trang rà"),
        ("training/apply_detector_label_review.py", "Áp quyết định rà vào bộ dữ liệu mới"),
        ("training/prepare_detector_recovery.py", "Tạo bộ recovery C"),
        ("training/evaluate_detector_regression.py", "Benchmark cố định 234 ảnh"),
        ("training/evaluate_orchard_pipeline.py", "Đánh giá cả pipeline với ngưỡng của app"),
    ], [6.8, 9.7], size=11)

    R.chapter = "D"
    R.chapter_heading("PHỤ LỤC D. PHÂN CÔNG NHÓM")
    P("Điền tên, mã học viên và phần việc thực tế của từng thành viên trước khi nộp.", indent=False)
    R.table("Phân công", ["Thành viên / mã học viên", "Phần việc", "Minh chứng"],
            [(f"{n} – {s}", "................................", "................................") for n, s in MEMBERS],
            [6.0, 5.5, 5.0])


def slide_notes():
    from pptx import Presentation
    if not PPTX.exists():
        return []
    out = []
    prs = Presentation(PPTX)
    n = len(prs.slides)
    for i, s in enumerate(prs.slides):
        texts = [sh.text_frame.text.strip() for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
        if i == n - 1:
            title = texts[0]
        elif texts and texts[0].startswith("PHẦN "):
            title = f"{texts[0].title()} – {texts[1]}"
        elif i == 0:
            title = "Trang tiêu đề"
        else:
            title = texts[1] if len(texts) > 1 else texts[0]
        out.append((" ".join(title.split()), s.notes_slide.notes_text_frame.text))
    return out


def page_map_from_pdf(pdf, headings):
    """Find the physical page of each heading in a rendered first pass."""
    pages = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True,
                           check=True).stdout.split("\f")
    norm = lambda s: re.sub(r"\s+", "", s).lower()
    npages = [norm(p) for p in pages]
    # Skip the cover and the TOC pages (their entries repeat every heading, with dot leaders).
    start = 0
    for i, p in enumerate(pages):
        if "MỤC LỤC" in p or p.count("....") >= 5:
            start = i + 1
        elif start:
            break
    mapping, cur = {}, start
    for lvl, txt in headings:
        if lvl > 2:
            continue
        key = norm(txt)[:30]
        for j in range(cur, len(npages)):
            if key in npages[j]:
                mapping[txt] = j + 1
                cur = j
                break
    return mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, help="PDF of a first pass, used for TOC page numbers")
    args = ap.parse_args()
    page_map = {}
    if args.pdf:
        probe = Report()
        write(probe)
        page_map = page_map_from_pdf(args.pdf, probe.headings)
    R = Report(page_map)
    write(R)
    R.save(OUT)
    missing = [t for lvl, t in R.headings if lvl <= 2 and t not in page_map]
    print("Created", OUT, "| TOC pages:", "from PDF" if args.pdf else "placeholder",
          f"| unmatched headings: {len(missing)}" if args.pdf else "")


if __name__ == "__main__":
    main()
