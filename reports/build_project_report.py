"""Build the team's editable presentation and Word report from checked project facts."""

from datetime import date
from pathlib import Path
import json

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt as DocPt, RGBColor as DocRGB
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PHOTO_DRAGON = ROOT / "fruit_detection_runs_gcp_review/4169118715503181824/pipeline_check/user_photo_1.jpg"
PHOTO_MANGO = ROOT / "fruit_detection_runs_gcp_review/4169118715503181824/pipeline_check/user_photo_3.jpg"
METRIC_FILE = ROOT / "fruit_detection_runs_gcp_review/4169118715503181824/pipeline_check/v3_evaluation.json"
REGRESSION_FILE = ROOT / "fruit_detection_runs_gcp_review/regression_20261002/trial_abc_summary.json"

# Fill these fields when the team supplies the official details. Avoid invented names.
SCHOOL = "ĐẠI HỌC QUỐC GIA – TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN"
FACULTY = "KHOA KHOA HỌC MÁY TÍNH"
TEAM = "NHÓM: ........................................"
MEMBERS = ["........................................ (MSSV: ................)"]
LECTURER = "........................................"
COURSE = "MÁY HỌC"
YEAR = "2025 – 2026"

NAVY = RGBColor(15, 35, 49)
GREEN = RGBColor(24, 127, 91)
MINT = RGBColor(218, 243, 230)
GOLD = RGBColor(238, 169, 67)
WHITE = RGBColor(255, 255, 255)
INK = RGBColor(31, 48, 58)
MUTED = RGBColor(99, 119, 128)
PALE = RGBColor(245, 249, 247)
RED = RGBColor(179, 67, 64)

TALK_TRACKS = [
    ("Mở đầu", "Nhóm trình bày Smart Orchard AI, hệ thống hỗ trợ quan sát xoài và thanh long trên cây. "
     "Báo cáo đi từ bài toán và quá trình phát triển đến dữ liệu, mô hình, ứng dụng và kết quả. "
     "Nêu tên nhóm, các thành viên và phần việc thật sau khi đã được điền chính thức."),
    ("Bài toán", "Trong ảnh vườn, quả có thể khuất lá, nhỏ và chồng lên nhau. Ánh sáng thay đổi còn làm màu "
     "quả kém ổn định. Nhóm đặt ba đầu ra: vị trí quả, độ chín và số lượng. Sản phẩm hỗ trợ quan sát chứ "
     "chưa thay phép đếm, đánh giá trực tiếp tại vườn."),
    ("Phạm vi", "Ảnh tĩnh trả box, nhãn và số lượng. Video dùng ByteTrack để ước lượng số quả theo loài, "
     "hiện không phân loại độ chín từng track. Trang web nhận tệp và hiển thị kết quả; FastAPI cung cấp "
     "API tương ứng cho ảnh, video và trạng thái mô hình."),
    ("Các mốc", "Lịch sử Git bắt đầu từ 12/09. Ngày 18/09 nhóm có notebook Colab và baseline 7 lớp. "
     "Từ 24/09 phát triển pipeline hai giai đoạn. Cuối tháng 9 bổ sung dữ liệu, kiểm toán nhãn và huấn "
     "luyện bản v3. Đầu tháng 10 nhóm dựng benchmark ảnh âm tính, thử API/web và các detector sau rà nhãn."),
    ("Đổi cách tiếp cận", "Baseline 7 lớp trả kết quả trong một lượt nhưng ghép hai nhiệm vụ khó: tìm "
     "quả và đo độ chín. Bản mới tách detector theo loài khỏi classifier theo từng loài để có thể sửa lỗi "
     "và đo riêng. Sau khi thấy ảnh quả khác gây false positive, nhóm còn thêm verifier tùy chọn và trạng "
     "thái chưa chắc chắn cho độ chín."),
    ("Pipeline", "Chỉ vào từng ô: ảnh đi vào YOLOv8s, detector trả box xoài/thanh long, rồi ảnh được cắt "
     "theo box. Crop đi qua classifier theo loài và hiệu chỉnh xác suất. Verifier có thể loại quả khác. "
     "Cuối cùng API trả box, nhãn, confidence và số lượng. Độ chín thấp điểm không bị ép thành nhãn chắc chắn."),
    ("Dữ liệu và chất lượng", "Nhóm nhập dữ liệu Roboflow và các bộ ảnh vườn công khai. Tên lớp của từng "
     "nguồn được ánh xạ theo tên, vì ID có thể khác. Ảnh trùng và biến thể cùng gốc được nhóm trước khi "
     "chia tập. Tắt xoay hue vì đổi màu có thể làm sai nhãn độ chín."),
    ("Quy mô v3", "Đây là quy mô thật của dữ liệu cho checkpoint v3 đang cài. Detector có 9.231 ảnh "
     "train, 1.972 validation và 2.037 test. Classifier xoài có 2.688 ảnh train và 234 test; thanh long "
     "có 958 train và 131 test. Calibration là tập riêng để chọn ngưỡng, không phải test."),
    ("Lỗi dữ liệu", "Báo cáo kiểm toán phát hiện 145 mâu thuẫn nhãn độ chín và 703 box rất nhỏ trong "
     "nguồn thanh long. 675 file Black_Rot chỉ có 270 ảnh khác nhau, nên bỏ 405 bản trùng. Nhóm cũng "
     "không đánh đồng Fresh/Defect với ripe/rotten; dữ liệu không đủ rõ chỉ dùng cho nhiệm vụ phù hợp "
     "hoặc được cách ly."),
    ("Lớp đầu ra", "Xoài v3 dùng young, mature, turning và ripe; thanh long dùng unripe, ripe và rotten. "
     "Đây là tên lớp trong checkpoint và calibration đang cài. Bộ dữ liệu maturity_v2 chuẩn bị sau đó "
     "dùng premature/early cho xoài nhưng chưa thay model v3. Với cả hai loài, dự đoán yếu có nhãn "
     "uncertain."),
    ("Trình tự thực nghiệm", "Quy trình huấn luyện gồm chuẩn bị nhãn, kiểm tra split, train detector, train "
     "hai classifier, rồi đánh giá test riêng. Sau đó nhóm fit temperature và chọn ngưỡng lớp trên "
     "calibration. Việc lưu checkpoint lên cloud/Drive cho phép tiếp tục sau gián đoạn Colab và sao chép "
     "weight vào backend."),
    ("Thông số v3", "Detector v3 bắt đầu từ yolov8s.pt, ảnh 960 pixel, batch 8 và tối đa 100 epoch. "
     "Classifier bắt đầu từ yolov8s-cls.pt, crop 320 pixel, batch 32 và tối đa 50 epoch. Cả ba dùng "
     "AdamW, seed 42. Đây là thông số đọc từ args.yaml của lần train v3, không suy đoán từ code mới nhất."),
    ("Suy luận", "Detector dùng confidence mặc định 0,25. Mỗi box được nới crop 10%; crop quá nhỏ, cạnh "
     "dưới 64 pixel, vẫn có thể được đếm nhưng độ chín ghi chưa chắc chắn. Với crop đủ lớn, classifier "
     "trả xác suất đã hiệu chỉnh. Ngưỡng chấp nhận là mức lớn hơn giữa 0,80 và ngưỡng riêng của lớp. "
     "Verifier tùy chọn loại box có xác suất other từ 0,90."),
    ("Detector v3", "Trên bộ hồi quy gồm 234 ảnh, 584 box chuẩn và ảnh âm tính, detector v3 có precision "
     "55,3%, recall 82,5% và sai số đếm trung bình 1,83 quả mỗi ảnh. Đây là benchmark nguồn công khai, "
     "không phải kiểm tra tại vườn của nhóm. Các chỉ số này chỉ đánh giá tìm box, chưa đánh giá độ chín."),
    ("Thử detector khác", "Bộ hồi quy cho thấy v3 tạo 290 false box trên 112 ảnh âm tính. Sau rà nhãn, "
     "một checkpoint v4_repaired thử nghiệm tăng precision lên 81,0% và giảm sai số đếm còn 0,64 trên "
     "cùng bộ ảnh. Tuy nhiên backend hiện vẫn cài v3; v4 chưa được kiểm tra độc lập tại vườn mục tiêu "
     "hoặc thay vào sản phẩm demo."),
    ("Cải tiến suy luận", "Sau khi phân tích ảnh sai, nhóm thêm bộ kiểm tra loài để loại quả khác. Trên "
     "ảnh mận mẫu, verifier loại bốn box sai; trên ảnh xoài đông quả mẫu, giữ bốn box. Chế độ quét "
     "chi tiết tìm bốn box thay vì hai trên một ảnh xoài chồng lấp, vẫn bỏ sót quả bị che một phần. "
     "Hỗ trợ ảnh tối chỉ được kiểm tra trên bộ tối tổng hợp, chưa có ảnh vườn đêm độc lập."),
    ("Classifier", "Classifier xoài đúng 90,2% trên 234 crop test; trong 179 nhãn được chấp nhận có 174 "
     "nhãn đúng. Thanh long đạt 100% trên 131 crop test của tập đã tuyển chọn. Không suy rộng con số "
     "100% thành kết quả ngoài vườn: bộ ảnh vườn đánh giá detector hiện thiếu ground truth độ chín."),
    ("Ảnh minh họa", "Ảnh bên trái cho thấy ba box thanh long trong một ảnh thử. Ảnh bên phải có "
     "nhiều xoài nhỏ, một số nhãn uncertain. Mời người nghe nhìn vào box và vùng ảnh bị che khuất. "
     "Các ảnh này giúp hiểu giao diện kết quả, nhưng không thay cho thống kê trên bộ test."),
    ("Kiến trúc ứng dụng", "Frontend React và Ant Design nhận tệp và hiển thị kết quả. FastAPI kiểm tra "
     "đầu vào, gọi pipeline PyTorch rồi trả JSON. ByteTrack là nhánh riêng cho video. Có thể chạy "
     "backend và frontend tại máy hoặc đóng gói theo Docker/Modal như tài liệu dự án."),
    ("Một yêu cầu ảnh", "Người dùng chọn ảnh và tùy chỉnh ngưỡng, frontend gửi FormData. API giới hạn 12 MB, "
     "đọc EXIF và chuyển RGB rồi chạy detector, classifier, verifier. JSON trả về số lượng, danh sách "
     "box và ảnh JPEG Base64. Frontend hiện ảnh kết quả và cảnh báo nếu API lỗi."),
    ("Kiểm thử", "Nhóm kiểm tra dữ liệu trùng/chồng split, huấn luyện và đánh giá trên test. Các log web/API "
     "ghi nhận việc khởi tạo model và phản hồi cho ảnh mẫu. Kiểm thử video hiện dùng clip tổng hợp từ "
     "ảnh; cần video vườn thật có số quả chuẩn để đo sai số. Chỉ nói những gì log thực sự chứng minh."),
    ("Video", "Video được giới hạn 50 MB, 30 giây, 1080p và lấy mẫu tối đa 5 fps. ByteTrack nối box theo "
     "ID; mỗi ID có đủ quan sát được đếm một lần theo loài. ID có thể đổi khi che khuất hay camera "
     "di chuyển, nên đầu ra là ước lượng. Không trình bày đây là độ chính xác đã kiểm chứng trên video vườn."),
    ("Kết luận", "Nhóm đã có pipeline ảnh, ứng dụng web/API và tính năng đếm video. Điểm mới về thực "
     "hành là tách hai nhiệm vụ, kiểm soát dữ liệu và trả uncertain cho độ chín. Bước tiếp theo là "
     "thu ảnh/video từ đúng vườn mục tiêu, gắn nhãn độc lập và đo lại trước khi dùng thực tế."),
    ("Nguồn và nhóm", "Điền tên, MSSV, giảng viên và phần việc thật trước khi nộp. Slide này liệt kê "
     "các tệp để giảng viên có thể truy số liệu: README, log classifier test và benchmark detector. "
     "Nếu được hỏi vì sao có nhiều tên lớp xoài, giải thích v3 đang cài khác bộ dữ liệu retrain mới."),
    ("Kết thúc", "Cảm ơn thầy cô và các bạn. Mời đặt câu hỏi, sau đó demo một ảnh xoài, một ảnh thanh long "
     "và một video ngắn nếu có kết nối và thời gian. Khi demo, mở /health trước để xác nhận pipeline_mode."),
]


def add_box(slide, x, y, w, h, fill=WHITE, line=None, radius=True):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid(); shape.fill.fore_color.rgb = fill
    shape.line.fill.background() if line is None else None
    if line is not None:
        shape.line.color.rgb = line
    return shape


def add_text(slide, text, x, y, w, h, size=20, color=INK, bold=False,
             align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.MIDDLE, margin=0.04):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame; tf.clear(); tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = valign
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line; p.alignment = align; p.space_after = Pt(6)
        p.font.name = "Arial"; p.font.size = Pt(size); p.font.bold = bold
        p.font.color.rgb = color
    return box


def add_picture_fit(slide, path, x, y, w, h):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    return slide.shapes.add_picture(str(path), Inches(x+(w-pw)/2),
                                    Inches(y+(h-ph)/2), Inches(pw), Inches(ph))


def new_slide(prs, title, kicker=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_box(s, 0, 0, 13.333, 7.5, PALE, radius=False)
    add_box(s, 0, 0, 13.333, 0.13, GREEN, radius=False)
    if kicker:
        add_text(s, kicker.split(" • ", 1)[-1].upper(), .65, .31, 10.5, .32, 11, GREEN, True)
    add_text(s, title, .65, .72, 12.0, .65, 29, NAVY, True)
    add_text(s, f"SMART ORCHARD AI  •  {len(prs.slides):02d}", .65, 7.12, 12, .18, 9, MUTED)
    return s


def card(s, x, y, w, h, label, body, accent=GREEN, body_size=17):
    add_box(s, x, y, w, h, WHITE)
    add_box(s, x, y, .09, h, accent, radius=False)
    add_text(s, label, x+.23, y+.18, w-.48, .42, 20, accent, True)
    add_text(s, body, x+.23, y+.74, w-.48, h-.88, body_size, INK,
             valign=MSO_ANCHOR.TOP)


def detail_rows(s, rows, y0=1.55, row_h=.91, gap=.10):
    """Compact, readable sequence of numbered facts for a technical slide."""
    for i, (tag, title, body) in enumerate(rows):
        y = y0+i*(row_h+gap)
        add_box(s,.7,y,11.95,row_h,WHITE)
        add_box(s,.7,y,1.18,row_h,GREEN if i%2==0 else NAVY)
        add_text(s,tag,.82,y+.08,.93,row_h-.16,16,WHITE,True,PP_ALIGN.CENTER)
        add_text(s,title,2.04,y+.11,3.0,row_h-.2,18,NAVY,True)
        add_text(s,body,5.12,y+.10,7.23,row_h-.18,15,INK)


def build_pptx():
    data = json.loads(METRIC_FILE.read_text())
    benchmark = json.loads(REGRESSION_FILE.read_text())["models"]["v3"]["total"]
    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)

    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_box(s, 0, 0, 13.333, 7.5, NAVY, radius=False)
    add_box(s, .65, .72, .14, 5.85, GOLD, radius=False)
    add_text(s, "BÁO CÁO DỰ ÁN MÁY HỌC", 1.0, .83, 10.7, .36, 16, MINT, True)
    add_text(s, "SMART ORCHARD AI", 1.0, 1.46, 11.2, .83, 38, WHITE, True)
    add_text(s, "Nhận diện, đếm và đánh giá độ chín\ncủa xoài và thanh long trên cây",
             1.0, 2.43, 10.7, 1.25, 25, WHITE)
    add_text(s, TEAM, 1.0, 4.55, 11, .42, 17, MINT, True)
    add_text(s, f"Môn học: {COURSE}  |  Năm học: {YEAR}", 1.0, 5.11, 11, .42, 15, WHITE)
    add_text(s, "Bộ slide báo cáo nhóm • 10/2026", 1.0, 6.56, 11, .25, 11, MINT)

    s = new_slide(prs, "Bài toán và mục tiêu", "01 • tổng quan")
    card(s, .65, 1.61, 3.83, 4.6, "Quan sát tại vườn",
         "Quả nhỏ, bị lá che và ánh sáng thay đổi khiến việc đếm thủ công khó ổn định.")
    card(s, 4.75, 1.61, 3.83, 4.6, "Bài toán AI",
         "Định vị quả trên ảnh; nhận diện xoài hoặc thanh long; phân loại giai đoạn chín từ vùng quả.", GOLD)
    card(s, 8.85, 1.61, 3.83, 4.6, "Đầu ra sử dụng",
         "Ảnh có khung và nhãn, số lượng theo lớp; video cho ước lượng số quả duy nhất.")

    s = new_slide(prs, "Phạm vi sản phẩm", "02 • chức năng")
    items = [
        ("01", "Ảnh tĩnh", "Phát hiện, đếm, hiển thị độ chín và vùng chưa chắc chắn."),
        ("02", "Video ngắn", "ByteTrack ghép các khung hình để ước lượng số quả duy nhất."),
        ("03", "Ứng dụng web", "React + Ant Design tải tệp, điều chỉnh ngưỡng và xem kết quả."),
        ("04", "API", "FastAPI cung cấp /detect, /detect-video, /health và /docs."),
    ]
    for i,(n,t,b) in enumerate(items):
        y = 1.55 + i*1.2
        add_box(s, .7, y, 11.95, 1.04, WHITE)
        add_text(s, n, .96, y+.12, .65, .72, 25, GREEN, True)
        add_text(s, t, 1.8, y+.13, 2.45, .65, 20, NAVY, True)
        add_text(s, b, 4.26, y+.13, 8.1, .69, 17, INK)

    s = new_slide(prs, "Các mốc phát triển của dự án", "03 • quá trình")
    detail_rows(s,[
        ("09/12","Khởi tạo","Định nghĩa bài toán, tổ chức backend, frontend và dữ liệu."),
        ("09/18","Baseline","Notebook Colab và checkpoint YOLOv8s 7 lớp; thử ảnh mẫu."),
        ("09/24","Tách hai bước","Detector theo loài + hai classifier độ chín và hiệu chỉnh."),
        ("09/28","Dữ liệu v3","Bổ sung ảnh vườn, kiểm toán nhãn và huấn luyện trên cloud."),
        ("10/02","Phân tích lỗi","Benchmark ảnh âm tính, sửa nhãn và thử detector mới."),
    ],row_h=.89,gap=.08)

    s = new_slide(prs, "Vì sao nhóm đổi cách tiếp cận?", "04 • quyết định kỹ thuật")
    card(s,.68,1.55,3.82,4.87,"Bản ban đầu",
         "YOLOv8s dự đoán trực tiếp 7 lớp loài + độ chín.\n\nMột box phải giải quyết đồng thời vị trí và màu/giai đoạn chín.",GREEN,16)
    card(s,4.76,1.55,3.82,4.87,"Bản hai giai đoạn",
         "Detector chỉ tìm xoài/thanh long.\n\nCrop từng quả cho classifier riêng; xác suất được hiệu chỉnh.",GOLD,16)
    card(s,8.84,1.55,3.82,4.87,"Bài học từ thử nghiệm",
         "Ảnh quả khác gây false positive; quả nhỏ và xoài nhiều giai đoạn vẫn khó.\n\nNhóm thêm verifier và nhãn chưa chắc chắn.",RED,16)

    s = new_slide(prs, "Luồng xử lý hai giai đoạn", "03 • kiến trúc")
    stages = [
        ("Ảnh đầu vào", "Ảnh vườn"),
        ("YOLOv8s", "Tìm xoài / thanh long"),
        ("Cắt vùng quả", "Kiểm tra quả khác"),
        ("Classifier", "Độ chín theo từng loài"),
        ("Kết quả", "Box • nhãn • số lượng"),
    ]
    for i,(a,b) in enumerate(stages):
        x=.65+i*2.53
        add_box(s,x,2.05,2.13,2.8,WHITE)
        add_box(s,x,2.05,2.13,.14,GREEN,radius=False)
        add_text(s,a,x+.12,2.48,1.9,.52,19,NAVY,True,PP_ALIGN.CENTER)
        add_text(s,b,x+.13,3.15,1.87,1.05,15,INK,align=PP_ALIGN.CENTER)
        if i<4: add_text(s,"→",x+2.15,3.06,.35,.55,26,GREEN,True,PP_ALIGN.CENTER)
    add_box(s,.65,5.36,12.0,.79,MINT)
    add_text(s,"Điểm thiết kế: ngưỡng độ chín đã hiệu chỉnh; dự đoán yếu được gắn nhãn “chưa chắc chắn”.",
             .9,5.54,11.5,.43,17,NAVY)

    s = new_slide(prs, "Dữ liệu và kiểm soát chất lượng", "04 • phương pháp")
    card(s,.68,1.55,5.8,4.85,"Nguồn dữ liệu",
         "Ảnh xoài và thanh long từ Roboflow và các bộ dữ liệu vườn công khai.\n\nNhãn được ánh xạ theo tên; dữ liệu phát hiện và dữ liệu độ chín được tách đúng vai trò.",GREEN,17)
    card(s,6.76,1.55,5.8,4.85,"Quy tắc xử lý",
         "Loại ảnh trùng; gom biến thể cùng ảnh gốc vào một tập; kiểm tra box/crop và nhãn mâu thuẫn.\n\nTắt xoay hue khi tăng cường dữ liệu vì màu là tín hiệu quan trọng của độ chín.",GOLD,17)

    s = new_slide(prs, "Quy mô dữ liệu của lần huấn luyện v3", "07 • dữ liệu")
    add_text(s,"Số ảnh theo split; detector và hai classifier có tập dữ liệu riêng",.72,1.44,11.7,.38,16,MUTED)
    columns=[("Thành phần","Train","Val","Calib","Test"),
             ("Detector","9.231","1.972","—","2.037"),
             ("Classifier xoài","2.688","351","235","234"),
             ("Classifier thanh long","958","196","131","131")]
    for i,row in enumerate(columns):
        y=2.02+i*.84
        add_box(s,.73,y,11.86,.72,NAVY if i==0 else WHITE)
        xs=[.9,5.85,7.47,9.08,10.65]; ws=[4.67,1.36,1.35,1.35,1.55]
        for j,v in enumerate(row):add_text(s,v,xs[j],y+.08,ws[j],.55,17,WHITE if i==0 else INK,i==0)
    add_box(s,.73,5.72,11.86,.77,MINT)
    add_text(s,"Nguồn: data/prepared/two_stage_maturity_v3/preparation_report.json",.94,5.88,11.4,.43,15,NAVY)

    s = new_slide(prs, "Nhóm đã xử lý những lỗi dữ liệu nào?", "08 • làm sạch")
    card(s,.68,1.56,3.82,4.83,"Nhãn chưa đáng tin",
         "Phát hiện 145 trường hợp nhãn độ chín mâu thuẫn với nguồn và 703 box nhỏ hơn 1% diện tích ảnh.\n\nQuả mơ hồ được loại khỏi classifier.",GREEN,15)
    card(s,4.76,1.56,3.82,4.83,"Ảnh trùng / rò rỉ",
         "675 file Black_Rot chỉ có 270 ảnh khác nhau: loại 405 bản trùng.\n\nCác biến thể từ cùng ảnh gốc được giữ cùng split.",GOLD,15)
    card(s,8.84,1.56,3.82,4.83,"Sai ý nghĩa nhãn",
         "Không suy diễn Fresh/Defect thành ripe/rotten.\n\nNhãn chỉ dùng cho đúng nhiệm vụ: phát hiện loài hoặc phân loại độ chín.",RED,15)

    s = new_slide(prs, "Các lớp đầu ra hiện tại", "05 • mô hình")
    card(s,.67,1.55,5.82,4.9,"Xoài · 4 mức",
         "mango_young — non\nmango_mature — trưởng thành\nmango_turning — chuyển chín\nmango_ripe — chín\n\n+ mango_uncertain khi chưa đủ tin cậy",GREEN,17)
    card(s,6.76,1.55,5.82,4.9,"Thanh long · 3 mức",
         "dragonfruit_unripe — chưa chín\ndragonfruit_ripe — chín\ndragonfruit_rotten — hỏng\n\n+ dragonfruit_uncertain khi chưa đủ tin cậy",GOLD,17)

    s = new_slide(prs, "Huấn luyện và đánh giá", "06 • thực nghiệm")
    for i,(h,b) in enumerate([
        ("Chuẩn bị", "Dữ liệu được kiểm tra nhãn, ảnh trùng và rò rỉ giữa các tập."),
        ("Huấn luyện", "Detector YOLOv8s, classifier xoài và classifier thanh long riêng."),
        ("Hiệu chỉnh", "Temperature scaling và ngưỡng theo lớp cho độ chín."),
        ("Đo lường", "Precision/recall cho box; accuracy cho crop; kiểm thử nguồn công khai."),
    ]):
        x=.68+(i%2)*6.08; y=1.55+(i//2)*2.38
        card(s,x,y,5.78,2.08,h,b,GREEN if i%2==0 else GOLD,15)

    s = new_slide(prs, "Thiết lập huấn luyện của checkpoint v3", "11 • huấn luyện")
    card(s,.68,1.55,3.82,4.86,"Detector",
         "YOLOv8s pretrained\n2 lớp: mango, dragonfruit\n100 epoch tối đa\nẢnh 960 px; batch 8\nAdamW; seed 42",GREEN,17)
    card(s,4.76,1.55,3.82,4.86,"Classifier",
         "YOLOv8s-cls pretrained\nXoài 4 lớp, thanh long 3 lớp\n50 epoch tối đa\nCrop 320 px; batch 32\nAdamW; seed 42",GOLD,17)
    card(s,8.84,1.55,3.82,4.86,"Sau huấn luyện",
         "Lưu best.pt từng mô hình.\n\nĐo test riêng; fit temperature và ngưỡng trên tập calibration.\n\nSao chép weight + JSON vào backend.",GREEN,16)

    s = new_slide(prs, "Từ điểm số đến nhãn hiển thị", "12 • suy luận")
    detail_rows(s,[
        ("1","Phát hiện","Detector tìm box, mặc định conf ≥ 0,25."),
        ("2","Cắt ảnh","Nới vùng quả 10%; cạnh crop < 64 px → chưa chắc chắn."),
        ("3","Phân loại","Chọn classifier xoài hoặc thanh long; crop 320 px."),
        ("4","Hiệu chỉnh","Temperature scaling; ngưỡng hiệu lực = max(0,80; ngưỡng lớp)."),
        ("5","Lọc / trả về","Verifier tùy chọn loại quả khác; trả box, nhãn và số lượng."),
    ],row_h=.88,gap=.08)

    s = new_slide(prs, "Kết quả nhận diện trên bộ hồi quy", "07 • kết quả")
    add_text(s,"234 ảnh nguồn công khai • 584 box chuẩn • IoU 0,5 • confidence 0,25",.72,1.46,12,.4,16,MUTED)
    metrics=[("Precision",f"{benchmark['precision']*100:.1f}%"),("Recall",f"{benchmark['recall']*100:.1f}%"),
             ("Sai số đếm / ảnh",f"{benchmark['count_mae']:.2f}")]
    for i,(l,v) in enumerate(metrics):
        x=.7+i*4.16
        add_box(s,x,2.2,3.85,2.08,WHITE)
        add_text(s,v,x+.16,2.46,3.5,.77,38,GREEN,True,PP_ALIGN.CENTER)
        add_text(s,l,x+.15,3.36,3.55,.48,18,INK,align=PP_ALIGN.CENTER)
    add_box(s,.7,4.8,12,.96,MINT)
    add_text(s,"Số liệu box của detector v3 trước verifier; chưa phải kết quả tại vườn triển khai độc lập.",
             .92,4.96,11.5,.64,16,NAVY)

    s = new_slide(prs, "Phân tích lỗi và thử nghiệm detector", "14 • cải tiến")
    add_text(s,"Cùng 234 ảnh / 584 box, gồm 112 ảnh âm tính",.73,1.47,11.7,.4,16,MUTED)
    columns=[("Phiên bản","Precision","Recall","MAE đếm","FP ảnh âm tính"),
             ("detector v3 đang cài","55,3%","82,5%","1,83","290"),
             ("v4 sửa nhãn – thử nghiệm","81,0%","83,7%","0,64","19")]
    for i,row in enumerate(columns):
        y=2.08+i*.87
        add_box(s,.73,y,11.86,.73,NAVY if i==0 else WHITE)
        xs=[.9,4.75,6.68,8.51,10.33];ws=[3.65,1.78,1.63,1.61,2.00]
        for j,v in enumerate(row):add_text(s,v,xs[j],y+.09,ws[j],.52,16,WHITE if i==0 else INK,i==0)
    add_box(s,.73,5.27,11.86,1.16,MINT)
    add_text(s,"v4 là kết quả thí nghiệm trên bộ công khai, chưa thay checkpoint đang chạy. Bộ này chỉ đo phát hiện; chưa có nhãn độ chín.",
             .94,5.43,11.4,.8,16,NAVY)

    s = new_slide(prs, "Các cải tiến sau khi xem ảnh lỗi", "phân tích lỗi")
    card(s,.68,1.56,3.82,4.83,"Lọc quả khác",
         "Verifier tùy chọn lọc lớp other ở ngưỡng 0,90.\n\nẢnh mận mẫu: loại 4/4 box sai; ảnh xoài đông mẫu: giữ 4/4 box.",GREEN,15)
    card(s,4.76,1.56,3.82,4.83,"Quét ảnh đông quả",
         "detailed_scan tăng kích thước ảnh và dùng test-time augmentation.\n\nẢnh mẫu: 4 box thay vì 2, vẫn bỏ sót một quả bị che.",GOLD,15)
    card(s,8.84,1.56,3.82,4.83,"Hỗ trợ ảnh tối",
         "low_light_assist tăng tương phản cho detector; classifier vẫn dùng màu gốc.\n\nMới thử trên ảnh tối tổng hợp, chưa có ảnh đêm vườn thực.",RED,15)

    s = new_slide(prs, "Kết quả phân loại độ chín", "08 • kết quả")
    mango=data["classifiers_test"]["mango_classifier"]
    dragon=data["classifiers_test"]["dragon_classifier"]
    card(s,.68,1.55,5.8,4.75,"Xoài",
         f"Accuracy test: {mango['accuracy']*100:.1f}% trên {mango['test_images']} crop.\n\nChấp nhận nhãn: {mango['accepted']}; đúng {mango['accepted_correct']}.",GREEN,19)
    card(s,6.76,1.55,5.8,4.75,"Thanh long",
         f"Accuracy test: {dragon['accuracy']*100:.1f}% trên {dragon['test_images']} crop.\n\nChấp nhận nhãn: {dragon['accepted']}; đúng {dragon['accepted_correct']}.",GOLD,19)
    add_text(s,"Tập test là dữ liệu đã tuyển chọn; chưa chứng minh độ chính xác trên mọi vườn và điều kiện chụp.",
             .74,6.47,11.9,.43,14,RED)

    s = new_slide(prs, "Ví dụ đầu ra trên ảnh", "09 • demo")
    add_box(s,.7,1.55,5.9,4.72,WHITE)
    add_picture_fit(s,PHOTO_DRAGON,.82,1.7,5.66,3.56)
    add_text(s,"Thanh long: box, nhãn và xác suất",.9,5.43,5.5,.53,15,INK,True,PP_ALIGN.CENTER)
    add_box(s,6.76,1.55,5.9,4.72,WHITE)
    add_picture_fit(s,PHOTO_MANGO,6.88,1.7,5.66,3.56)
    add_text(s,"Xoài: nhiều quả nhỏ, có nhãn chưa chắc chắn",6.88,5.43,5.66,.53,15,INK,True,PP_ALIGN.CENTER)
    add_text(s,"Ảnh đầu ra lưu trong pipeline_check của dự án; dùng để minh họa, không thay cho chỉ số đánh giá.",
             .75,6.46,11.7,.35,13,MUTED)

    s = new_slide(prs, "Kiến trúc ứng dụng", "10 • triển khai")
    for i,(a,b) in enumerate([
        ("React + Ant Design", "Tải ảnh/video và hiển thị kết quả"),
        ("FastAPI", "Kiểm tra tệp và điều phối suy luận"),
        ("Ultralytics + PyTorch", "Detector, classifier, verifier"),
        ("ByteTrack", "Ước lượng số quả duy nhất trong video"),
    ]):
        y=1.48+i*1.24
        add_box(s,.75,y,11.84,1.04,WHITE)
        add_box(s,.75,y,2.9,1.04,GREEN if i<3 else GOLD)
        add_text(s,a,.97,y+.11,2.46,.78,17,WHITE,True)
        add_text(s,b,3.9,y+.13,8.37,.74,17,INK)

    s = new_slide(prs, "Đường đi của một yêu cầu ảnh", "18 • tích hợp")
    detail_rows(s,[
        ("1","Giao diện","Người dùng chọn JPG/PNG/WEBP; tùy chỉnh ngưỡng và chế độ quét."),
        ("2","API kiểm tra","Giới hạn 12 MB, giải mã ảnh, xoay đúng EXIF và chuyển RGB."),
        ("3","Suy luận","Chạy detector → crop → classifier → verifier tùy chọn."),
        ("4","Phản hồi","JSON gồm box, nhãn, confidence, số lượng và ảnh JPEG Base64."),
        ("5","Hiển thị","React vẽ ảnh kết quả, bảng số lượng và cảnh báo khi lỗi."),
    ],row_h=.88,gap=.08)

    s = new_slide(prs, "Nhóm đã kiểm thử ứng dụng ra sao?", "19 • kiểm chứng")
    card(s,.68,1.56,3.82,4.83,"Dữ liệu / mô hình",
         "Kiểm tra split không chồng nhóm, ảnh trùng, lớp thiếu, crop lỗi.\n\nĐo test classifier và bộ hồi quy detector có ảnh âm tính.",GREEN,15)
    card(s,4.76,1.56,3.82,4.83,"API / giao diện",
         "Kiểm tra /health, tải ảnh hợp lệ, giới hạn tệp, ảnh lỗi và phản hồi JSON.\n\nCó log thử ảnh web và HTTP trong repo.",GOLD,15)
    card(s,8.84,1.56,3.82,4.83,"Video / triển khai",
         "Thử ByteTrack bằng clip tổng hợp từ ảnh.\n\nDocker/Modal có hướng dẫn đóng gói; chưa có benchmark video vườn thực.",RED,15)

    s = new_slide(prs, "Đếm video và giới hạn", "11 • đánh giá")
    card(s,.68,1.56,5.8,4.8,"Video + ByteTrack",
         "Lấy mẫu tối đa 5 khung hình/giây, theo dõi ID và chỉ đếm mỗi track một lần.\n\nAPI trả tổng số quả, số theo loài và một khung hình minh họa.",GREEN,17)
    card(s,6.76,1.56,5.8,4.8,"Cần nói rõ khi báo cáo",
         "Track ID có thể đổi khi quả bị che hoặc camera di chuyển.\n\nVideo mới được thử với clip tổng hợp từ ảnh; chưa đo sai số đếm trên video vườn thực.",RED,17)

    s = new_slide(prs, "Kết luận và hướng phát triển", "12 • tổng kết")
    card(s,.68,1.55,5.8,4.85,"Đã hoàn thành",
         "Pipeline hai giai đoạn; giao diện web; API ảnh/video; phân loại có cơ chế chưa chắc chắn; tài liệu tái lập huấn luyện.",GREEN,18)
    card(s,6.76,1.55,5.8,4.85,"Bước tiếp theo",
         "Thu thập ảnh và video tại vườn mục tiêu; gắn nhãn đầy đủ; đo đếm và độ chín ngoài thực địa; cải thiện quả nhỏ, chồng lấp và quả nhìn giống.",GOLD,18)

    s = new_slide(prs, "Nhóm thực hiện và nguồn minh chứng", "13 • phụ lục")
    card(s,.68,1.55,5.8,4.85,"Thông tin nhóm",
         TEAM+"\n\n"+"\n".join(MEMBERS)+"\n\nGVHD: "+LECTURER,
         GREEN,17)
    card(s,6.76,1.55,5.8,4.85,"Nguồn trong dự án",
         "README.md, training/README.md, backend/README.md\n\n"
         "v3_evaluation.json — classifier test\n\n"
         "trial_abc_summary.json — detector benchmark",
         GOLD,16)

    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_box(s,0,0,13.333,7.5,NAVY,radius=False)
    add_text(s,"CẢM ƠN THẦY/CÔ\nVÀ CÁC BẠN",.8,1.56,11.7,1.6,36,WHITE,True,PP_ALIGN.CENTER)
    add_text(s,"NHÓM THỰC HIỆN • SMART ORCHARD AI",.8,3.78,11.7,.52,20,MINT,True,PP_ALIGN.CENTER)
    add_text(s,"Thảo luận & demo",.8,4.67,11.7,.48,19,WHITE,align=PP_ALIGN.CENTER)
    if len(prs.slides) != len(TALK_TRACKS):
        raise ValueError(f"Slide/note mismatch: {len(prs.slides)} vs {len(TALK_TRACKS)}")
    for slide, (_, note) in zip(prs.slides, TALK_TRACKS):
        slide.notes_slide.notes_text_frame.text = note
    prs.save(OUT / "Smart_Orchard_AI_Thuyet_trinh_nhom.pptx")


def style_doc(doc):
    sec=doc.sections[0]
    sec.page_width=Cm(21); sec.page_height=Cm(29.7)
    sec.top_margin=Cm(2.3); sec.bottom_margin=Cm(2.1)
    sec.left_margin=Cm(2.8); sec.right_margin=Cm(2.2)
    styles=doc.styles
    normal=styles["Normal"]
    normal.font.name="Arial"; normal.font.size=DocPt(11)
    normal.font.color.rgb=DocRGB(31,48,58)
    normal.paragraph_format.space_after=DocPt(6)
    normal.paragraph_format.line_spacing=1.25
    for name,size in [("Heading 1",16),("Heading 2",13),("Heading 3",11)]:
        st=styles[name]; st.font.name="Arial"; st.font.size=DocPt(size); st.font.bold=True
        st.font.color.rgb=DocRGB(15,35,49)
        st.paragraph_format.space_before=DocPt(13); st.paragraph_format.space_after=DocPt(6)


def para(doc,text="",bold=False,align=None,size=None,space_after=None):
    p=doc.add_paragraph()
    if align is not None:p.alignment=align
    r=p.add_run(text);r.bold=bold
    if size:r.font.size=DocPt(size)
    if space_after is not None:p.paragraph_format.space_after=DocPt(space_after)
    return p


def bullet(doc,text):
    return doc.add_paragraph(text,style="List Bullet")


def add_table(doc,heads,rows):
    t=doc.add_table(rows=1,cols=len(heads));t.style="Light Shading Accent 1"
    for i,h in enumerate(heads):t.rows[0].cells[i].text=h
    for row in rows:
        cells=t.add_row().cells
        for i,v in enumerate(row):cells[i].text=str(v)
    for row_index,row in enumerate(t.rows):
        trPr=row._tr.get_or_add_trPr()
        no_split=OxmlElement("w:cantSplit");trPr.append(no_split)
        if row_index == 0:
            repeat=OxmlElement("w:tblHeader");repeat.set(qn("w:val"),"true");trPr.append(repeat)
        for cell in row.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.name="Arial";run.font.size=DocPt(9.5)
                    if row_index == 0:run.bold=True
    doc.add_paragraph()
    return t


def page_break(doc):doc.add_page_break()


def build_docx():
    test=json.loads(METRIC_FILE.read_text())
    detector=json.loads(REGRESSION_FILE.read_text())["models"]["v3"]["total"]
    d=Document();style_doc(d)
    # Cover follows the reference's centered institution, report type, course,
    # large topic and left-aligned author/adviser block.
    para(d,SCHOOL+"\n"+FACULTY,True,WD_ALIGN_PARAGRAPH.CENTER,14,44)
    para(d,"BÁO CÁO BÀI TẬP LỚN",True,WD_ALIGN_PARAGRAPH.CENTER,21,13)
    para(d,"Môn học: "+COURSE,False,WD_ALIGN_PARAGRAPH.CENTER,14,38)
    para(d,"ĐỀ TÀI:\nNHẬN DIỆN, ĐẾM VÀ ĐÁNH GIÁ ĐỘ CHÍN\nCỦA XOÀI VÀ THANH LONG TRÊN CÂY\n(SMART ORCHARD AI)",True,WD_ALIGN_PARAGRAPH.CENTER,17,55)
    para(d,"Báo cáo dự án nhóm",False,WD_ALIGN_PARAGRAPH.CENTER,14,33)
    para(d,TEAM,True,size=12,space_after=5)
    para(d,"Sinh viên thực hiện:",True,size=12,space_after=3)
    for m in MEMBERS:para(d,"    • "+m,size=11,space_after=2)
    para(d,"Giảng viên hướng dẫn: "+LECTURER,size=11,space_after=2)
    para(d,"Năm học: "+YEAR,size=11,space_after=0)
    page_break(d)

    d.add_heading("MỤC LỤC",0)
    for line in ["Tóm tắt", "Chương 1. Giới thiệu", "Chương 2. Quá trình phát triển dự án",
                 "Chương 3. Dữ liệu và chuẩn bị", "Chương 4. Phương pháp và kiến trúc",
                 "Chương 5. Huấn luyện và hiệu chỉnh", "Chương 6. Cài đặt hệ thống",
                 "Chương 7. Thực nghiệm, phân tích lỗi và cải tiến",
                 "Chương 8. Hạn chế và hướng phát triển",
                 "Tài liệu và minh chứng trong dự án", "Phụ lục A. Gợi ý lời thuyết trình theo slide",
                 "Phụ lục B. Cách chạy và kiểm tra bản demo", "Phụ lục C. Phân công nhóm"]:
        para(d,line)
    page_break(d)

    d.add_heading("TÓM TẮT",0)
    para(d,"Smart Orchard AI là hệ thống thị giác máy tính nhằm phát hiện xoài và thanh long trên cây, "
         "đếm quả trong ảnh, ước lượng số quả duy nhất trong video và đánh giá độ chín của từng quả. "
         "Phiên bản đang dùng tách việc định vị quả khỏi phân loại độ chín: YOLOv8s tìm vùng quả, "
         "sau đó bộ phân loại theo từng loài xử lý crop. Dự đoán thiếu tin cậy được gắn nhãn chưa chắc chắn. "
         "Hệ thống có FastAPI và giao diện React để thử ảnh/video. Báo cáo trình bày quy trình dữ liệu, "
         "kiến trúc, kết quả đo được và giới hạn thực nghiệm.")
    para(d,"Từ khóa: YOLOv8, phát hiện đối tượng, phân loại độ chín, ByteTrack, FastAPI, React.",True)

    d.add_heading("CHƯƠNG 1. GIỚI THIỆU",1)
    d.add_heading("1.1. Bối cảnh",2)
    para(d,"Trong ảnh chụp vườn, quả có thể nhỏ, bị lá hoặc cành che, chồng lên nhau và chịu ánh sáng thay đổi. "
         "Đếm thủ công tốn thời gian, còn đánh giá độ chín bằng màu dễ bị ảnh hưởng bởi điều kiện chụp. "
         "Dự án tập trung vào hai loại quả: xoài và thanh long. Đây là bài toán thực nghiệm phục vụ hỗ trợ quan sát, "
         "không thay thế việc kiểm tra trực tiếp tại vườn.")
    d.add_heading("1.2. Mục tiêu và phạm vi",2)
    for x in ["Phát hiện vị trí và loài của từng quả trong ảnh.",
              "Phân loại độ chín theo thang riêng của xoài và thanh long; trả trạng thái chưa chắc chắn khi cần.",
              "Đếm box trong ảnh và ước lượng số quả duy nhất trong video bằng theo dõi ID.",
              "Cung cấp giao diện web và API để người dùng thử tệp và xem kết quả."]:
        bullet(d,x)
    para(d,"Đầu vào ảnh hỗ trợ JPG/PNG/WEBP; đầu vào video hỗ trợ MP4/MOV/WebM/AVI theo giới hạn hiện tại "
         "của API. Đối tượng khác xoài và thanh long nằm ngoài phạm vi nhận diện mục tiêu.")
    d.add_heading("1.3. Yêu cầu chức năng và tiêu chí quan sát",2)
    add_table(d,["Tình huống","Đầu vào","Kết quả cần quan sát"],[
        ["Kiểm tra ảnh vườn","Một ảnh có xoài/thanh long","Box từng quả, loài, nhãn độ chín hoặc uncertain, tổng số và số theo lớp"],
        ["Ảnh khó","Ảnh tối hoặc nhiều quả sát nhau","Có thể bật hỗ trợ sáng/quét chi tiết; kết quả vẫn cần kiểm bằng mắt"],
        ["Kiểm tra video","Clip ngắn","Số track quả duy nhất ước lượng theo loài và khung hình xem trước"],
        ["Theo dõi dịch vụ","Không cần tệp","/health cho biết weight đã nạp và chế độ pipeline đang chạy"],
    ])
    para(d,"Những tiêu chí trên mô tả hành vi sản phẩm đã triển khai. Mục tiêu học máy cần đánh giá riêng "
         "bằng dữ liệu có ground truth: box đúng/sai, loài đúng/sai, nhãn độ chín đúng/sai và sai số số lượng. "
         "Không thể kết luận hiệu quả chỉ từ việc giao diện vẽ được box trên vài ảnh mẫu.")
    d.add_heading("1.4. Thuật ngữ dùng nhất quán",2)
    para(d,"Trong báo cáo, 'phát hiện' là xác định box và loài; 'phân loại độ chín' là dự đoán nhãn từ "
         "crop quả; 'đếm ảnh' là số box còn lại sau lọc; 'đếm video' là số track ID được chấp nhận. "
         "Từ 'uncertain' không có nghĩa hệ thống không thấy quả: box vẫn có thể được giữ cho phần đếm, "
         "chỉ nhãn độ chín chưa đủ bằng chứng. Precision, recall và mAP thuộc bài toán phát hiện; "
         "accuracy của classifier đo trên crop, không phải ảnh nguyên vườn.")

    d.add_heading("CHƯƠNG 2. QUÁ TRÌNH PHÁT TRIỂN DỰ ÁN",1)
    d.add_heading("2.1. Các mốc được ghi nhận",2)
    para(d,"Quá trình dưới đây được dựng từ lịch sử Git, notebook, báo cáo chuẩn bị dữ liệu và các thư mục "
         "kết quả trong repo. Đây là mốc của sản phẩm chung, không phải phân công hay đánh giá đóng góp cá nhân.")
    add_table(d,["Thời điểm","Việc nhóm đã thực hiện","Minh chứng"],[
        ["12/09/2026","Khởi tạo repository và định hình bài toán nhận diện quả.","Git history"],
        ["18/09/2026","Viết notebook Colab; huấn luyện baseline YOLOv8s 7 lớp; lưu checkpoint lên Drive.","training/train_yolo.ipynb; Git history"],
        ["24/09/2026","Chuyển sang detector 2 lớp + classifier riêng cho từng loài; thêm API suy luận có hiệu chỉnh.","training/train_two_stage.py; backend/two_stage.py"],
        ["28/09/2026","Kiểm toán nhãn, nhập thêm dữ liệu vườn và Black_Rot; chuẩn bị dữ liệu v3, huấn luyện trên cloud.","data/prepared/two_stage_maturity_v3; runs_maturity_v3"],
        ["30/09–02/10/2026","Thử web/API, dựng bộ hồi quy có ảnh âm tính, rà lỗi nhãn và so sánh các detector thử nghiệm.","web_test_20260930; regression_20261002"],
    ])
    d.add_heading("2.2. Baseline đơn giai đoạn và bài học",2)
    para(d,"Bản đầu dùng một mô hình YOLOv8s dự đoán trực tiếp lớp kết hợp giữa loài và độ chín. "
         "Điểm thuận tiện là một lần chạy trả box và nhãn. Tuy nhiên, nhận diện vị trí quả trong tán lá và "
         "phân biệt các mức chín bằng màu là hai nhiệm vụ khác nhau. Nhóm giữ checkpoint 7 lớp làm baseline, "
         "sau đó thiết kế pipeline hai giai đoạn để tối ưu và đánh giá riêng từng việc.")
    para(d,"README còn ghi chỉ số 4 lớp rất cao từ giai đoạn cũ, nhưng chính README cảnh báo dữ liệu có biến thể "
         "cùng ảnh gốc nằm ở nhiều split. Vì vậy tài liệu này không dùng các con số đó làm kết quả dự án hiện tại.")
    d.add_heading("2.3. Phiên bản đang chạy và các thử nghiệm tiếp theo",2)
    para(d,"Các weight trong backend/weights khớp với lần huấn luyện v3: detector, classifier xoài và "
         "classifier thanh long. File calibration xoài của bản này dùng nhãn young/mature/turning/ripe. "
         "Nhóm tiếp tục chuẩn bị bộ dữ liệu maturity_v2 với nhãn premature/early/mature/ripe và thử detector "
         "sau rà nhãn; đây là hướng tái huấn luyện/thí nghiệm, chưa phải checkpoint được cài trong backend. "
         "Việc phân biệt này tránh gán số liệu thử nghiệm của mô hình khác cho sản phẩm đang demo.")
    add_table(d,["Hiện vật","Trạng thái trong repo"],[
        ["YOLOv8s 7 lớp","Baseline cũ, chọn bằng PIPELINE_MODE=legacy"],
        ["Pipeline hai giai đoạn v3","Weight đang cài trong backend; mặc định khi đủ tệp"],
        ["Bộ maturity_v2","Đã chuẩn bị và kiểm toán dữ liệu; chưa thay weight v3"],
        ["Detector v4 đã sửa nhãn","Đã đánh giá trên bộ hồi quy; chưa thay weight đang chạy"],
    ])
    d.add_heading("2.4. Cách nhóm chuyển phản hồi thành thay đổi",2)
    para(d,"Quy trình phát triển có vòng lặp rõ: chạy mô hình trên ảnh có nhãn hoặc ảnh mẫu, lưu ảnh đầu ra "
         "và log, phân loại lỗi, rồi sửa đúng phần gây lỗi. Ví dụ, false positive trên ảnh quả khác dẫn "
         "đến bộ ảnh âm tính và verifier; bỏ sót quả đông/chồng lấp dẫn đến detailed_scan; crop quá nhỏ "
         "và nhãn độ chín thiếu tin cậy dẫn đến trạng thái uncertain; nhãn nguồn không nhất quán dẫn đến "
         "quy tắc cách ly và kiểm toán lại dữ liệu. Các thay đổi này được giữ riêng để đo hiệu ứng, thay vì "
         "diễn giải ảnh demo như một phép kiểm thử tổng quát.")
    add_table(d,["Vấn đề quan sát","Thay đổi đã làm","Cách kiểm tra / trạng thái"],[
        ["Biến thể cùng ảnh gốc rơi vào nhiều split","Nhóm theo danh tính ảnh gốc và hash","Kiểm tra group overlap trong manifest"],
        ["Nhãn độ chín không đồng nhất","Cách ly crop mâu thuẫn; tách nhãn detector/classifier","Báo cáo maturity audit, readiness"],
        ["Quả khác bị nhận nhầm","Verifier và ảnh âm tính","Ảnh mẫu + benchmark detector; chưa đủ dữ liệu vườn độc lập"],
        ["Quả chồng lấp / ánh sáng yếu","detailed_scan / low_light_assist","Kiểm tra mẫu; chưa có thử nghiệm hiện trường đủ lớn"],
        ["Đếm lặp khung hình video","ByteTrack theo ID","Clip tổng hợp; chưa có video vườn gắn nhãn"],
    ])

    d.add_heading("CHƯƠNG 3. DỮ LIỆU VÀ CHUẨN BỊ",1)
    d.add_heading("3.1. Nguồn và nhãn",2)
    para(d,"Dự án kết hợp dữ liệu Roboflow với các bộ dữ liệu công khai có ảnh vườn. Các nguồn được kiểm tra "
         "trước khi đưa vào huấn luyện. Tệp gốc và báo cáo kiểm toán dữ liệu được mô tả trong "
         "training/README.md và data/external/README.md. Bộ detector dùng nhãn loài xoài/thanh long; "
         "các classifier dùng nhãn độ chín của từng loài.")
    add_table(d,["Loài","Các nhãn độ chín của mô hình hiện tại"],[
        ["Xoài","mango_young; mango_mature; mango_turning; mango_ripe"],
        ["Thanh long","dragonfruit_unripe; dragonfruit_ripe; dragonfruit_rotten"],
    ])
    para(d,"Mô hình đơn giai đoạn 7 lớp là baseline cũ. Tên nhãn trong checkpoint hai giai đoạn hiện tại "
         "khác một phần so với baseline, vì vậy báo cáo này dùng tên từ tệp hiệu chỉnh đang cài tại backend/weights.")
    d.add_heading("3.2. Làm sạch và chia tập",2)
    for x in [
        "Ánh xạ nhãn theo tên, không ghép theo mã lớp của từng nguồn.",
        "Loại ảnh trùng và gom các biến thể tăng cường từ cùng ảnh gốc vào một tập để giảm rò rỉ.",
        "Kiểm tra box, crop quá nhỏ, nhãn mâu thuẫn và các ảnh không đủ bằng chứng về độ chín.",
        "Tách train, validation, calibration và test cho classifier; hiệu chỉnh ngưỡng trên tập calibration.",
        "Không xoay hue khi tăng cường dữ liệu vì màu là tín hiệu quan trọng cho độ chín.",
    ]:bullet(d,x)
    para(d,"Các bước kiểm toán giúp phát hiện lỗi dữ liệu nhưng chưa bảo đảm ảnh công khai đại diện cho mọi vườn "
         "triển khai. Kiểm tra độc lập tại vườn mục tiêu vẫn là công việc cần thực hiện.")

    d.add_heading("3.3. Dữ liệu thực sự dùng cho checkpoint v3",2)
    prep=json.loads((ROOT/"data/prepared/two_stage_maturity_v3/preparation_report.json").read_text())
    add_table(d,["Tập dữ liệu","Train","Validation","Calibration","Test"],[
        ["Detector",prep["detector"]["images_train"],prep["detector"]["images_val"],"—",prep["detector"]["images_test"]],
        ["Classifier xoài",prep["mango_classifier"]["images_train"],prep["mango_classifier"]["images_val"],prep["mango_classifier"]["images_calib"],prep["mango_classifier"]["images_test"]],
        ["Classifier thanh long",prep["dragon_classifier"]["images_train"],prep["dragon_classifier"]["images_val"],prep["dragon_classifier"]["images_calib"],prep["dragon_classifier"]["images_test"]],
    ])
    para(d,"Detector v3 lấy ảnh từ nhiều nguồn xoài/thanh long, gồm ảnh cây và ảnh ngoài vườn. "
         "Dữ liệu chỉ có box loài dùng để huấn luyện detector; các crop có nhãn độ chín đủ rõ mới được đưa "
         "vào classifier. Với xoài v3, nhãn Roboflow premature/early được gom thành young, trong khi "
         "dữ liệu chín theo giai đoạn khác được ánh xạ thành mature, turning và ripe. Đây là lựa chọn "
         "của v3, không phải một định nghĩa nông học đã được kiểm chứng tại mọi vườn.")
    d.add_heading("3.4. Những lỗi cụ thể được phát hiện",2)
    for x in [
        "Bộ thanh long có 145 trường hợp nhãn độ chín không khớp với tên nguồn và 703 box chiếm dưới 1% diện tích ảnh; crop mơ hồ được cách ly khi dựng classifier.",
        "Trong 675 tệp Black_Rot gốc tải về, chỉ có 270 ảnh khác nhau; loại 405 bản sao chính xác và nhóm thêm ba cặp góc chụp lặp đã xem trực quan.",
        "Nhãn Fresh/Defect mô tả chất lượng và không tự động tương đương với ripe/rotten. Bộ Black_Rot chỉ đại diện một dạng hỏng có thể nhìn thấy.",
        "Dữ liệu Roboflow có biến thể tên chứa .rf.; tách theo danh tính ảnh gốc, không theo tên file đã tăng cường. Kiểm tra hash để tìm ảnh trùng giữa các split.",
        "Một số bộ nhãn là polygon hoặc keypoint; script chuyển phần hình học hợp lệ thành box YOLO. Nhãn crop quá nhỏ hoặc nhãn mâu thuẫn không được dùng cho độ chín.",
    ]:bullet(d,x)
    para(d,"Các con số trên phản ánh kiểm toán dữ liệu, không phải số lỗi được xác nhận thủ công cho mọi ảnh. "
         "Báo cáo chi tiết nằm tại data/external/maturity_audit_report.json và các preparation_report.json.")
    d.add_heading("3.5. Vai trò của từng nhóm nguồn ảnh",2)
    source_rows=[]
    source_labels={
        "dragon_fruit_orchard":"Ảnh vườn thanh long, box loài",
        "mango_farfield":"Xoài chụp xa, tăng đa dạng kích thước",
        "mango_on_tree":"Xoài trên cây, nhiều quả trong tán",
        "mango_orchard_daylight":"Xoài vườn ban ngày",
        "mango_yolo":"Xoài có box định vị",
        "rf_dragonfruit_curated":"Thanh long Roboflow đã lọc nhãn",
        "rf_mango":"Xoài Roboflow; ảnh có thể cấp crop độ chín",
        "rf_mango_tree":"Xoài trong cảnh cây",
        "rf_pitaya_orchard":"Thanh long trong vườn",
        "rf_ripe_dragon_plants":"Thanh long trên cây với quả nhỏ/xa",
    }
    for source,count in prep["detector_source_images"].items():
        source_rows.append([source,count,source_labels[source]])
    add_table(d,["Nguồn detector v3","Ảnh nguồn","Vai trò trong dữ liệu"],source_rows)
    para(d,"'Ảnh nguồn' là số từ báo cáo chuẩn bị trước khi phân bổ split, không cộng trực tiếp thành số ảnh "
         "train cuối cùng vì còn bước loại trùng và lọc. Những nguồn có box nhưng không có ground truth độ "
         "chín chỉ giúp detector. Với classifier xoài, báo cáo v3 ghi 951 ảnh nguồn Mendeley mango ripening "
         "và 3.135 ảnh Roboflow trước các bước lọc/crop/chia tập. Classifier thanh long lấy crop được "
         "tuyển chọn và nhóm ảnh Black_Rot đã loại trùng.")
    add_table(d,["Bộ dữ liệu công khai","Thông tin trong manifest của dự án","Phạm vi được sử dụng"],[
        ["MangoYOLO","CC BY 4.0; box Pascal VOC","Định vị xoài; không có nhãn độ chín"],
        ["On-tree mango segmentation","CC BY 4.0; mask/box xoài trên cây","Định vị xoài"],
        ["DF pose v2","CC BY 4.0; box + keypoint","Lấy box thanh long cho detector"],
        ["MangoFruitBD v2","Trang nguồn ghi CC BY-NC 3.0; README archive ghi CC BY-NC 4.0","Ảnh xoài ban ngày cho detector; dùng nghiên cứu phi thương mại"],
        ["DF-MOD Black_Rot gốc","CC BY 4.0; 675 file trước loại trùng","Ứng viên nhãn thanh long hỏng sau kiểm tra"],
    ])
    para(d,"Tệp data/external/datasets.json ghi trang nguồn, điều khoản và checksum của từng bộ. "
         "Một số bộ được khảo sát nhưng không đưa vào huấn luyện v3; vì vậy không liệt kê mọi dữ liệu "
         "đã tải như thể đều góp vào kết quả. Khi chia sẻ hoặc sử dụng ngoài phạm vi học tập, nhóm cần "
         "giữ phần ghi công và xem lại điều kiện của từng nguồn.")
    d.add_heading("3.6. Tạo nhãn chung từ định dạng khác nhau",2)
    para(d,"Script chuẩn bị đọc nhãn YOLO theo tên lớp trong data.yaml, đọc box Pascal VOC của MangoYOLO, "
         "và đọc box COCO của tập xoài trên cây. Với nhãn segmentation YOLO, danh sách điểm polygon "
         "được bao bằng box nhỏ nhất. Với bộ pose, chỉ box được giữ và keypoint không trở thành tọa độ "
         "của một quả. Mọi box được đưa về định dạng tâm x, tâm y, rộng, cao theo tỷ lệ kích thước ảnh "
         "để YOLO huấn luyện. Box có tọa độ không hợp lệ hoặc kích thước quá nhỏ bị bỏ/đánh dấu theo "
         "quy tắc của script, rồi lưu nguồn gốc trong manifest để truy vết.")
    add_table(d,["Nhãn nguồn","Nhãn hoặc nhiệm vụ của v3","Giải thích"],[
        ["Xoài Roboflow: premature, early-fruit","mango_young","v3 gộp hai mức đầu"],
        ["Xoài Roboflow: mature, ripe","mango_mature, mango_ripe","giữ mức tương ứng"],
        ["Mango ripening: stage0/1/2/3","mature/mature/turning/ripe","theo ánh xạ trong preparation_report v3"],
        ["Thanh long: Immature/Mature","unripe/ripe khi crop hợp lệ","đòi nhãn crop phù hợp nguồn"],
        ["Thanh long Black_Rot gốc","dragonfruit_rotten","chỉ biểu hiện hỏng/đốm đen đã chọn"],
        ["Fresh/Defect","không tự đổi thành độ chín","có thể dùng box loài nếu hợp lệ"],
    ])
    d.add_heading("3.7. Chia tập và điều kiện cho phép huấn luyện",2)
    para(d,"Đơn vị chia tập là nhóm ảnh nguồn, không phải từng crop. Một ảnh có nhiều crop phải ở cùng "
         "một split; biến thể Roboflow có cùng tiền tố trước '.rf.' cũng được gom. Với khung hình lấy từ "
         "cùng clip thanh long, script giữ cả clip trong một tập và cân bằng theo số khung hình. "
         "Ảnh trùng byte được phát hiện bằng hash; ảnh tương tự và ảnh đảo gương được nhóm bằng dấu vân "
         "tay thị giác với giới hạn đã ghi trong README. Tập classifier có thêm calibration độc lập để "
         "chọn ngưỡng, sau đó test chỉ dùng để báo cáo.")
    para(d,"Trước train, readiness gate kiểm tra từng lớp và tập có đủ số nhóm nguồn tối thiểu: 80 nhóm "
         "ở train, 20 nhóm ở validation, calibration và test. Gate còn kiểm tra lớp bị thiếu, crop dưới "
         "64 px, nhãn xung đột, hash trùng giữa các tập và manifest không đổi sau audit. Đây là ngưỡng "
         "tối thiểu cho một lần thử huấn luyện, không phải bảo đảm sai số thống kê hay hiệu quả ngoài vườn.")

    d.add_heading("CHƯƠNG 4. PHƯƠNG PHÁP VÀ KIẾN TRÚC",1)
    d.add_heading("4.1. Pipeline ảnh hai giai đoạn",2)
    para(d,"Ảnh đầu vào → detector YOLOv8s tìm xoài/thanh long → cắt từng vùng quả → tùy chọn bộ kiểm tra "
         "quả khác → classifier riêng cho từng loài → hiệu chỉnh xác suất và áp ngưỡng → box, nhãn và số lượng. "
         "Nhờ tách bước phát hiện và phân loại, detector tập trung vào định vị còn classifier xử lý chi tiết màu và "
         "bề mặt của quả. Trường hợp crop quá nhỏ hoặc điểm độ chín không đạt ngưỡng được gắn *_uncertain.")
    para(d,"Khi suy luận, API mở ảnh, xử lý hướng EXIF và chuyển RGB. Detector chạy với ngưỡng box mặc định 0,25. "
         "Mỗi box được nới thêm 10% ở các cạnh để tạo crop. Nếu cạnh ngắn dưới 64 px, hệ thống vẫn giữ box "
         "cho phần đếm nhưng không ép ra nhãn độ chín. Các crop còn lại được đưa vào classifier tương ứng, "
         "xử lý theo batch ở kích thước 320 px.")
    para(d,"Với tùy chọn low_light_assist, ảnh được nâng tương phản cục bộ bằng CLAHE chỉ cho detector; "
         "classifier vẫn nhìn màu ảnh gốc để hạn chế làm sai tín hiệu độ chín. Với detailed_scan, detector "
         "dùng kích thước đầu vào lớn hơn (tối đa ít nhất 1280) và test-time augmentation. Đây là tùy chọn "
         "phục vụ thử nghiệm; cần đo thêm trên ảnh vườn thực.")
    d.add_heading("4.2. Hiệu chỉnh và nhãn chưa chắc chắn",2)
    para(d,"Sau khi classifier tạo xác suất, backend dùng temperature của từng loài để hiệu chỉnh. "
         "Ngưỡng áp dụng cho một nhãn là giá trị lớn hơn giữa ngưỡng lớp đã học trên tập calibration và "
         "ngưỡng API (mặc định 0,80). Điểm thấp hơn ngưỡng này tạo mango_uncertain hoặc "
         "dragonfruit_uncertain. Tùy chọn species_verifier.pt kiểm tra crop có phải quả khác hay không; "
         "xác suất lớp other từ 0,90 trở lên làm box bị loại trước khi đếm.")
    d.add_heading("4.3. Đếm trong video",2)
    para(d,"API video lấy mẫu tối đa 5 khung hình/giây rồi dùng ByteTrack nối các box theo ID. "
         "Mỗi ID bền vững được đếm một lần; đầu ra gồm số quả theo loài và một khung hình minh họa. "
         "Video hiện chưa trả nhãn độ chín. Khi vật bị che hoặc camera di chuyển mạnh, ID có thể tách hoặc đổi, "
         "dẫn đến sai số đếm.")
    para(d,"Cụ thể, mỗi request tạo tracker riêng để ID của video trước không lẫn sang video sau. "
         "Video bị giới hạn 50 MB, 30 giây và 1080p; phân tích tối đa 150 khung hình được chọn. "
         "Một track cần xuất hiện ít nhất hai lần khi có đủ khung hình; loài cuối cùng lấy theo đa số quan sát. "
         "Nếu có verifier, hệ thống chọn crop rõ nhất theo confidence của mỗi track để kiểm tra quả khác.")
    d.add_heading("4.4. Mô hình baseline",2)
    para(d,"Checkpoint YOLOv8s 7 lớp đơn giai đoạn vẫn có thể chọn bằng PIPELINE_MODE=legacy để so sánh. "
         "Mặc định backend chọn pipeline hai giai đoạn khi đủ ba checkpoint mới. Các số liệu từ mô hình 4 lớp "
         "trong README được đánh dấu cũ và có nguy cơ lạc quan do rò rỉ biến thể; không dùng làm kết quả hiện tại.")
    d.add_heading("4.5. Dữ liệu đi qua hệ thống theo từng bước",2)
    add_table(d,["Bước","Đầu vào","Xử lý","Đầu ra"],[
        ["1. Đọc ảnh","Bytes từ upload","Giải mã, xoay EXIF, RGB","PIL Image chuẩn"],
        ["2. Tìm quả","Ảnh nguyên / ảnh tăng tương phản tùy chọn","YOLOv8s + NMS","Box, loài, detection confidence"],
        ["3. Tạo crop","Box + ảnh màu gốc","Nới 10%, chặn mép ảnh, xét cạnh 64 px","Crop hoặc uncertain do kích thước"],
        ["4. Phân loại","Crop theo loài","YOLOv8s-cls 320 px, temperature scaling","Xác suất độ chín đã hiệu chỉnh"],
        ["5. Quyết định","Xác suất + ngưỡng","Áp max(ngưỡng API, ngưỡng lớp); lọc other tùy chọn","Nhãn cuối hoặc uncertain"],
        ["6. Trả kết quả","Danh sách box hợp lệ","Tổng hợp số lượng; vẽ box lên ảnh","JSON + JPEG Base64"],
    ])
    para(d,"Cần tách hai loại confidence: detection_confidence đo mức mô hình phát hiện box, còn "
         "ripeness_confidence là xác suất lớp sau hiệu chỉnh của classifier. Một box có thể được phát hiện "
         "rõ nhưng độ chín vẫn uncertain; giao diện và người đọc không nên xem hai điểm số này như một. "
         "Đếm ảnh bằng số box cuối cùng, không phải số quả thật nếu mô hình bỏ sót hoặc tạo box sai.")
    d.add_heading("4.6. Lý do dùng nhãn uncertain",2)
    para(d,"Mức độ chín có thể không xác định từ ảnh vì quả quá nhỏ, bị che hoặc màu bị ảnh hưởng bởi ánh "
         "sáng. Ép mọi crop vào một lớp sẽ khiến kết quả có vẻ chắc chắn hơn bằng chứng. Bởi vậy pipeline "
         "vẫn báo đã tìm thấy quả, nhưng trả *_uncertain nếu crop nhỏ hoặc điểm lớp thấp hơn ngưỡng. "
         "Cách này đánh đổi độ phủ của nhãn độ chín lấy độ tin cậy cao hơn trên những nhãn được chấp nhận. "
         "Đánh đổi ấy phải được báo cùng coverage: ví dụ ở test xoài v3, 179/234 crop được chấp nhận, "
         "không chỉ báo accuracy trên tập được chấp nhận.")
    d.add_heading("4.7. Tùy chọn cho ảnh khó và chi phí tính toán",2)
    para(d,"low_light_assist biến đổi độ tương phản trong không gian LAB bằng CLAHE, chỉ cho nhánh phát "
         "hiện. Giữ crop phân loại từ ảnh gốc là quyết định quan trọng vì classifier phụ thuộc màu. "
         "detailed_scan cho ảnh đông quả tăng giới hạn kích thước đầu vào lên ít nhất 1280 px, giảm "
         "ngưỡng NMS IoU từ 0,7 xuống 0,5 và bật test-time augmentation. Các tùy chọn tăng công việc "
         "suy luận; ảnh nhỏ được giới hạn phóng đại xấp xỉ hai lần để tránh mất lợi ích khi phóng quá mức. "
         "Tài liệu không công bố số mili giây hay FPS vì repo chưa có benchmark tốc độ ổn định cho "
         "toàn pipeline trên thiết bị triển khai.")

    d.add_heading("CHƯƠNG 5. HUẤN LUYỆN VÀ HIỆU CHỈNH",1)
    d.add_heading("5.1. Trình tự chạy",2)
    for x in [
        "Nhập nguồn ảnh, nhãn và metadata; kiểm tra file đọc được, box hợp lệ, nguồn có đủ lớp.",
        "Dựng detector và hai classifier thành ba tập riêng; tách theo nhóm ảnh gốc, xuất manifest và báo cáo readiness.",
        "Huấn luyện detector trước, sau đó huấn luyện classifier xoài và thanh long; mỗi stage có thể tiếp tục từ checkpoint khi bị ngắt.",
        "Đánh giá trên test của từng stage; fit temperature và chọn ngưỡng lớp trên calibration, không dùng test để chọn ngưỡng.",
        "Sao chép best.pt và calibration.json vào backend/weights; kiểm tra /health rồi thử ảnh/video mẫu.",
    ]:bullet(d,x)
    d.add_heading("5.2. Cấu hình lần huấn luyện v3",2)
    add_table(d,["Cấu hình","Detector","Classifier xoài / thanh long"],[
        ["Mô hình gốc","yolov8s.pt","yolov8s-cls.pt"],
        ["Ảnh đầu vào","960 px","320 px"],
        ["Batch","8","32"],
        ["Epoch tối đa","100","50"],
        ["Optimizer / seed","AdamW / 42","AdamW / 42"],
        ["Early stopping patience","25","15"],
    ])
    para(d,"Các cấu hình trên đọc từ args.yaml của lần runs_maturity_v3, không suy ra từ mã đào tạo đã thay đổi "
         "sau lần chạy. Quá trình dùng checkpoint pretrained, ảnh nhỏ không bị đổi hue (hsv_h=0) và "
         "không áp dụng auto_augment cho classifier. Kết quả best.pt được chọn trong quá trình huấn luyện, "
         "sau đó đánh giá trên test tách riêng.")
    d.add_heading("5.3. Lưu mô hình và khả năng tái lập",2)
    para(d,"Notebook Colab và script hỗ trợ chứa các bước nhập nguồn, chuẩn bị, kiểm toán, huấn luyện, "
         "kiểm thử và sao chép artifact. Checkpoint được lưu trên Drive/cloud để tránh mất sau khi runtime "
         "ngắt; backend chỉ cần ba tệp trọng số, hai JSON calibration và verifier tùy chọn. "
         "Repo giữ cả weight v3 đang chạy và checkpoint 7 lớp cũ để có thể so sánh.")
    d.add_heading("5.4. Điều gì được lưu sau mỗi stage",2)
    add_table(d,["Stage","Tệp chính","Mục đích"],[
        ["Chuẩn bị","manifest.csv, preparation_report.json, data_readiness.json","Truy vết nguồn, split và điều kiện huấn luyện"],
        ["Detector","detector/weights/best.pt, results.csv, hình validation/test","Chọn checkpoint và xem lỗi định vị"],
        ["Classifier xoài","mango_classifier/weights/best.pt, calibration.json","Suy luận bốn mức xoài và ngưỡng"],
        ["Classifier thanh long","dragon_classifier/weights/best.pt, calibration.json","Suy luận ba mức thanh long và ngưỡng"],
        ["Tích hợp","backend/weights/*.pt và *calibration.json","Nạp cùng lúc khi API khởi động"],
    ])
    para(d,"Script train kiểm tra manifest bằng SHA256 trước khi huấn luyện classifier để tránh đánh giá "
         "một tập khác với tập đã audit. Tùy chọn resume dùng last.pt khi lần chạy chưa kết thúc và dùng "
         "best.pt khi stage đã xong; nếu thiếu checkpoint cần thiết, script báo lỗi thay vì âm thầm "
         "huấn luyện một stage khác. Notebook Colab tách detector, xoài và thanh long thành các bước "
         "độc lập để có thể chạy lại sau khi mất kết nối.")
    d.add_heading("5.5. Hiệu chỉnh xác suất và chọn ngưỡng",2)
    para(d,"Sau khi classifier huấn luyện, calibration không đổi lớp dự đoán mà điều chỉnh độ sắc của "
         "phân bố xác suất bằng temperature T. Có thể viết ở mức khái niệm: p_i' = softmax(log(p_i)/T). "
         "Với T lớn hơn 1, phân bố thường bớt tự tin; với T nhỏ hơn 1, phân bố sắc hơn. T được fit "
         "trên tập calibration; script đo expected calibration error (ECE) trước và sau khi fit, rồi tìm "
         "ngưỡng theo lớp để đạt mục tiêu precision đặt trước trên tập này. Mục tiêu mặc định trong script "
         "là 0,80, nhưng là tiêu chí trên calibration, không bảo đảm precision tương tự ngoài vườn.")
    calib_mango=json.loads((ROOT/"backend/weights/mango_calibration.json").read_text())
    calib_dragon=json.loads((ROOT/"backend/weights/dragon_calibration.json").read_text())
    add_table(d,["Classifier","Temperature","Số mẫu calibration","ECE trước → sau"],[
        ["Xoài",f"{calib_mango['temperature']:.3f}",calib_mango["calibration_samples"],f"{calib_mango['ece_before']:.3f} → {calib_mango['ece_after']:.3f}"],
        ["Thanh long",f"{calib_dragon['temperature']:.3f}",calib_dragon["calibration_samples"],f"{calib_dragon['ece_before']:.3f} → {calib_dragon['ece_after']:.3f}"],
    ])
    para(d,"Ví dụ, với nhãn mango_turning, ngưỡng lớp trong JSON v3 khoảng 0,819. Khi API để mức "
         "0,80, ngưỡng hiệu lực vẫn là 0,819; với mango_ripe có ngưỡng lớp khoảng 0,544, ngưỡng "
         "hiệu lực trở thành 0,80. Nếu xác suất đã hiệu chỉnh nhỏ hơn ngưỡng hiệu lực, kết quả được "
         "gắn mango_uncertain. Cần cẩn thận khi chuyển checkpoint: JSON calibration phải khớp đúng "
         "tên và thứ tự lớp của classifier, nếu không backend từ chối nạp.")
    d.add_heading("5.6. Các lớp huấn luyện và các phiên bản cần phân biệt",2)
    para(d,"Mã chuẩn bị dữ liệu đang trong quá trình phát triển tiếp và profile maturity_v2 dùng bốn "
         "mức xoài premature/early/mature/ripe. Checkpoint v3 hiện cài ở backend lại dùng "
         "young/mature/turning/ripe. Không thể lấy accuracy của classifier v3 để tuyên bố hiệu quả "
         "cho bộ nhãn maturity_v2; muốn so sánh cần train weight mới trên đúng split và đánh giá lại. "
         "Đây là một giới hạn quan trọng khi nhóm thuyết trình tiến độ dự án đang phát triển.")

    d.add_heading("CHƯƠNG 6. CÀI ĐẶT HỆ THỐNG",1)
    add_table(d,["Thành phần","Công nghệ","Vai trò"],[
        ["AI","Ultralytics YOLOv8, PyTorch","Phát hiện và phân loại"],
        ["Theo dõi","ByteTrack, OpenCV","Đếm đối tượng theo ID trong video"],
        ["Backend","FastAPI, Python","API, suy luận và trả JSON/ảnh"],
        ["Frontend","React, TypeScript, Vite, Ant Design","Tải tệp, điều chỉnh ngưỡng, xem kết quả"],
        ["Triển khai","Docker, Modal (tùy chọn)","Đóng gói và chạy ứng dụng"],
    ])
    d.add_heading("6.1. Luồng sử dụng",2)
    para(d,"Người dùng mở giao diện, chọn ảnh hoặc video và gọi API. Với ảnh, giao diện có thể chỉnh "
         "ngưỡng phát hiện, ngưỡng độ chín, hỗ trợ ảnh tối và quét chi tiết ảnh nhiều quả. Backend trả ảnh đã "
         "vẽ box, danh sách phát hiện và số lượng theo lớp. Với video, backend trả ước lượng số quả duy nhất.")
    d.add_heading("6.2. Điểm cuối API",2)
    add_table(d,["Đường dẫn","Chức năng"],[
        ["GET /health","Trạng thái mô hình và pipeline"],
        ["POST /detect","Phân tích ảnh, mặc định conf=0,25 và ngưỡng độ chín=0,80"],
        ["POST /detect-video","Theo dõi và đếm quả trong video ngắn"],
        ["GET /docs","Tài liệu API tương tác"],
    ])

    d.add_heading("6.3. Từ thao tác trên web đến kết quả",2)
    para(d,"Frontend React dùng thành phần FruitDetector.tsx cho hai luồng tệp. Trước khi gửi, giao diện kiểm "
         "tra định dạng và dung lượng ảnh 12 MB/video 50 MB. Ảnh được gửi qua FormData tới /detect kèm "
         "các tham số conf_threshold, ripeness_threshold, low_light_assist và detailed_scan. Backend xác "
         "thực dữ liệu, chạy pipeline và trả JSON gồm danh sách box, confidence, số lượng từng nhãn và "
         "annotated_image_base64. Giao diện hiển thị ảnh có box cùng bảng thống kê; lỗi API được thông báo "
         "ngay trên trang.")
    para(d,"Khi khởi động, FastAPI tự chọn pipeline hai giai đoạn nếu các weight cần thiết tồn tại; "
         "nếu không sẽ rơi về baseline cũ. GET /health cho biết trạng thái model và pipeline_mode, "
         "giúp kiểm tra bản demo đang dùng đúng phiên bản. Có thể ép PIPELINE_MODE=legacy để so sánh. "
         "Frontend đã build có thể được FastAPI phục vụ tại cùng URL; Docker và modal_app.py cung cấp "
         "đường đóng gói triển khai, còn DEPLOY_MODAL.md là hướng dẫn vận hành.")
    d.add_heading("6.4. Phần nào đã được kiểm thử",2)
    para(d,"Repo có test cho chuẩn bị dữ liệu, ngưỡng calibration và helper notebook. Thư mục "
         "web_test_20260930 và regression_20261002 chứa kết quả chạy web/API. HTTP smoke trên bốn ảnh "
         "ghi nhận mã 200 và số box trả về; bộ API smoke riêng kiểm tra khởi tạo model và gọi handler trực "
         "tiếp, không phải thử transport HTTP. Video mới được thử bằng clip tổng hợp từ các ảnh được cung cấp; "
         "chưa có phép đo trên video vườn gắn nhãn.")
    d.add_heading("6.5. Cấu trúc mã nguồn và trách nhiệm",2)
    add_table(d,["Đường dẫn","Trách nhiệm chính"],[
        ["training/prepare_two_stage_data.py","Nhập nguồn, chuẩn hóa box/crop, chia split, xuất manifest và readiness"],
        ["training/train_two_stage.py","Huấn luyện ba stage, đo test, hiệu chỉnh confidence"],
        ["training/train_two_stage_colab.ipynb","Chạy tuần tự từng stage trên Colab, hỗ trợ resume"],
        ["backend/two_stage.py","Luồng ảnh: detector, crop, classifier, verifier, vẽ kết quả"],
        ["backend/video.py","Đọc video, ByteTrack, đếm ID, tạo ảnh preview"],
        ["backend/app.py","Khởi tạo weight, validate request, expose endpoint"],
        ["frontend/src/components/FruitDetector.tsx","Tải ảnh/video, lựa chọn ngưỡng, gọi API, hiển thị"],
        ["modal_app.py; Dockerfile; DEPLOY_MODAL.md","Đóng gói và hướng dẫn triển khai"],
    ])
    d.add_heading("6.6. Hợp đồng dữ liệu của API ảnh",2)
    para(d,"POST /detect nhận một tệp multipart/form-data tên file. Query conf_threshold mặc định 0,25 "
         "và bị giới hạn trong [0,01;1,00]; ripeness_threshold mặc định 0,80 và bị giới hạn trong "
         "[0,50;0,99]. low_light_assist và detailed_scan là hai cờ boolean. API từ chối tệp không phải "
         "ảnh, ảnh trên 12 MB hoặc ảnh không giải mã được. Với pipeline legacy, hai cờ hỗ trợ ảnh khó "
         "bị từ chối vì chúng chỉ được cài cho hai giai đoạn.")
    add_table(d,["Trường trong response","Ý nghĩa"],[
        ["success, filename, pipeline_mode","Trạng thái xử lý, tên tệp, mode đang dùng"],
        ["total_count","Số box cuối sau lọc trong ảnh"],
        ["counts","Bảng số box theo từng nhãn đầu ra"],
        ["detections[].bbox","[x_min, y_min, x_max, y_max] theo pixel của ảnh"],
        ["detections[].detection_confidence","Độ tin cậy phát hiện box"],
        ["detections[].ripeness_confidence","Điểm lớp độ chín sau calibration"],
        ["detections[].uncertain","Có/không bị từ chối nhãn độ chín"],
        ["annotated_image_base64","JPEG đã vẽ box để hiển thị trực tiếp"],
    ])
    para(d,"Về mặt diễn giải, counts không phải sản lượng thật của cây: nếu detector tạo hai box cho một "
         "quả hoặc bỏ sót quả bị che, bảng này cũng sai tương ứng. Với ảnh, hệ thống không gộp ID theo "
         "thời gian. Người dùng nên giữ ảnh gốc để đối chiếu kết quả.")
    d.add_heading("6.7. Quy trình demo và vận hành",2)
    for x in [
        "Khởi động backend, mở GET /health và xác nhận model_loaded=true, pipeline_mode=two-stage; kiểm tra other_fruit_filter khi muốn demo verifier.",
        "Mở web React, tải một ảnh thanh long dễ quan sát; ghi lại tổng box, nhãn và ảnh đã vẽ. Sau đó thử một ảnh xoài đông quả để giải thích uncertain và detailed_scan.",
        "Nếu trình bày ảnh tối, bật low_light_assist và so sánh trên cùng ảnh; chỉ mô tả thay đổi quan sát được, không công bố cải thiện tổng quát từ một ví dụ.",
        "Tải một video ngắn trong giới hạn; đọc tổng track và lời nhắc rằng đây là ước lượng. Không dùng một video demo để công bố accuracy đếm video.",
        "Khi cần so sánh baseline, dùng PIPELINE_MODE=legacy rồi khởi động lại dịch vụ; ghi rõ đã đổi mô hình và schema nhãn.",
    ]:bullet(d,x)
    para(d,"Ở môi trường cloud, tài liệu DEPLOY_MODAL.md mô tả cách build frontend và đóng gói cùng backend "
         "trên một URL. Sự tồn tại của cấu hình triển khai không tự chứng minh uptime, tốc độ hay chi phí; "
         "các chỉ số vận hành cần đo riêng nếu nhóm muốn trình bày như kết quả.")

    d.add_heading("CHƯƠNG 7. THỰC NGHIỆM, PHÂN TÍCH LỖI VÀ CẢI TIẾN",1)
    d.add_heading("7.1. Phát hiện đối tượng",2)
    para(d,"Bộ hồi quy công khai ngày 02/10/2026 gồm 234 ảnh và 584 box chuẩn, có cả ảnh âm tính. "
         "Đánh giá detector v3 với confidence 0,25, IoU ghép cặp 0,5 và kích thước ảnh 960. "
         "Kết quả dưới đây là phát hiện đối tượng trước verifier tùy chọn, không đo độ chín.")
    add_table(d,["Chỉ số","Giá trị"],[
        ["Precision",f"{detector['precision']*100:.1f}%"],
        ["Recall",f"{detector['recall']*100:.1f}%"],
        ["Sai số đếm tuyệt đối trung bình / ảnh",f"{detector['count_mae']:.2f}"],
        ["TP / FP / FN",f"{detector['tp']} / {detector['fp']} / {detector['fn']}"],
    ])
    para(d,"Cách đọc chỉ số: TP là box dự đoán ghép được với box chuẩn đúng loài ở IoU tối thiểu "
         "0,5; FP là box dư hoặc sai loài; FN là box chuẩn bị bỏ sót. Precision = TP/(TP+FP), còn "
         "recall = TP/(TP+FN). Với số liệu này, 482/(482+389) ≈ 55,3% và 482/(482+102) ≈ 82,5%. "
         "Sai số đếm tuyệt đối trung bình (MAE) là tổng |số dự đoán − số chuẩn| chia số ảnh; báo cáo "
         "ghi tổng sai số 429 trên 234 ảnh, tức khoảng 1,83. Chỉ số gộp không cho biết ảnh nào lỗi "
         "nặng, nên nhóm còn xem theo nguồn và ảnh âm tính.")
    para(d,"Bộ ảnh này không phải tập vườn triển khai độc lập. Nhiều false positive trên ảnh quả khác là "
         "vấn đề còn tồn tại; bộ kiểm tra loài tùy chọn có kết quả thử riêng nhưng chưa được chứng minh trên "
         "cùng toàn bộ benchmark.")
    d.add_heading("7.1.1. Kết quả thay đổi theo nguồn ảnh",3)
    source_eval=test["detector_per_source_conf025_iou05"]
    add_table(d,["Nguồn của bộ kiểm tra riêng","Ảnh","Số quả chuẩn","Precision v3","Recall v3"],[
        [label,source_eval[key]["images"],source_eval[key]["fruits"],
         f"{source_eval[key]['v3_precision']*100:.1f}%",f"{source_eval[key]['v3_recall']*100:.1f}%"]
        for key,label in [
            ("dragon_fruit_orchard","Thanh long vườn"),
            ("mango_farfield","Xoài chụp xa"),
            ("mango_on_tree","Xoài trên cây"),
            ("rf_mango_tree","Xoài Roboflow trên cây"),
            ("rf_pitaya_orchard","Thanh long Roboflow vườn"),
            ("rf_ripe_dragon_plants","Thanh long trên cây, nhiều quả nhỏ"),
        ]
    ])
    para(d,"Bảng nguồn này là phép kiểm tra khác với bộ hồi quy 234 ảnh: đa số nguồn lấy 40 ảnh, "
         "nguồn cuối lấy 15 ảnh. Số đo cho thấy mô hình không ổn định đồng đều: recall 53,2% ở nhóm "
         "rf_ripe_dragon_plants thấp hơn nhiều so với các nguồn dễ hơn. Sự khác biệt có thể đến từ kích "
         "thước quả, che khuất, góc chụp và chất lượng nhãn; bảng tự nó không chứng minh nguyên nhân. "
         "Khi báo cáo, cần nêu rõ từng tập và tránh gộp các kết quả với phép hồi quy 234 ảnh.")
    d.add_heading("7.2. Phân loại độ chín trên crop test",2)
    mango=test["classifiers_test"]["mango_classifier"]
    dragon=test["classifiers_test"]["dragon_classifier"]
    add_table(d,["Bộ phân loại","Số crop test","Accuracy","Nhãn được chấp nhận"],[
        ["Xoài",mango["test_images"],f"{mango['accuracy']*100:.1f}%",f"{mango['accepted_correct']}/{mango['accepted']} đúng"],
        ["Thanh long",dragon["test_images"],f"{dragon['accuracy']*100:.1f}%",f"{dragon['accepted_correct']}/{dragon['accepted']} đúng"],
    ])
    para(d,"Accuracy thô xoài 90,17% có nghĩa khoảng 211/234 crop được phân loại đúng trước bước "
         "từ chối độ tin cậy. Trong 179 crop được chấp nhận, 174 đúng, tức độ đúng có điều kiện "
         "174/179 ≈ 97,2%, nhưng coverage chỉ 179/234 ≈ 76,5%. Năm crop được chấp nhận vẫn sai. "
         "Tập test thanh long 131/131 đúng và cùng số được chấp nhận; kết quả này rất tốt trong phạm vi "
         "tập đã tuyển chọn nhưng quá nhỏ và quá đồng nhất để tuyên bố bao quát mọi biểu hiện hỏng.")
    add_table(d,["Lớp xoài trong test v3","Đúng / tổng lớp","Nhận xét"],[
        ["mango_young","64/74","dễ nhầm với mature ở một số crop"],
        ["mango_mature","76/87","11 trường hợp bị nhầm sang young"],
        ["mango_turning","24/24","tập test lớp này chỉ 24 crop"],
        ["mango_ripe","47/49","2 trường hợp bị nhầm sang young"],
    ])
    matrix=ROOT/"fruit_detection_runs_gcp_review/4169118715503181824/mango_classifier_test/confusion_matrix.png"
    if matrix.exists():
        para(d,"Hình 7.1. Ma trận nhầm lẫn của classifier xoài v3 trên 234 crop test; trục ngang là nhãn thật.",True)
        d.add_picture(str(matrix),width=Cm(12.6))
        para(d,"Đường chéo biểu thị dự đoán đúng. Lỗi nổi bật là 11 crop mature được dự đoán young và "
             "8 crop young được dự đoán mature; điều này phù hợp với việc hai mức đầu có dấu hiệu hình "
             "ảnh gần nhau. Ma trận chỉ thuộc classifier trên crop test, không phản ánh lỗi box của detector.")
    para(d,"Đây là test trên dữ liệu đã tuyển chọn cho classifier. Chỉ số thanh long 100% trên 131 crop "
         "không đồng nghĩa hiệu quả 100% trên ảnh vườn mới. Nhãn độ chín trong bộ ảnh vườn dùng đánh giá "
         "detector hiện không có ground truth, nên chưa đo accuracy độ chín đầu-cuối tại vườn.")
    para(d,"Cũng cần tách accuracy của classifier khi nó nhận crop chuẩn khỏi hiệu quả thực tế khi crop "
         "được tạo từ detector: box lệch, quá nhỏ hoặc chứa nhiều quả có thể làm nhãn độ chín sai dù "
         "classifier đạt điểm cao trên crop test. Vì vậy đánh giá đầu-cuối cần một bộ ảnh vườn mới có cả "
         "box và nhãn độ chín của từng quả, rồi đo phát hiện, nhãn và số lượng trên cùng ảnh.")
    d.add_heading("7.3. Phân tích lỗi và thử nghiệm cải tiến",2)
    para(d,"Bộ hồi quy có 112 ảnh âm tính giúp lộ ra vấn đề: v3 tạo 290 false box trên ảnh không chứa "
         "xoài/thanh long. Các cảnh xoài nhiều quả nhỏ và quả nhìn giống cũng gây bỏ sót hoặc nhận nhầm. "
         "Nhóm rà nhãn và thử detector mới trên đúng benchmark để so sánh cùng ngưỡng. Bản v4_repaired "
         "có kết quả tốt hơn về false positive và sai số đếm, nhưng đây là checkpoint thử nghiệm, chưa cài "
         "vào backend và chưa kiểm tra độc lập ở vườn mục tiêu.")
    comparison=json.loads((ROOT/"fruit_detection_runs_gcp_review/regression_20261002/comparison.json").read_text())
    v4=comparison["models"]["v4_repaired"]["total"]
    add_table(d,["Detector","Precision","Recall","MAE đếm/ảnh","False box ảnh âm tính"],[
        ["detector v3 đang cài",f"{detector['precision']*100:.1f}%",f"{detector['recall']*100:.1f}%",f"{detector['count_mae']:.2f}",detector["negative_false_boxes"]],
        ["v4_repaired thử nghiệm",f"{v4['precision']*100:.1f}%",f"{v4['recall']*100:.1f}%",f"{v4['count_mae']:.2f}",v4["negative_false_boxes"]],
    ])
    para(d,"comparison.json ghi split=val: đây là so sánh detector trên bộ nguồn công khai, không đánh "
         "giá độ chín. Việc chọn triển khai "
         "checkpoint mới cần thêm kiểm tra độc lập, đặc biệt với quả nhỏ, ảnh tối và vườn Việt Nam.")
    para(d,"Ở tầng suy luận, nhóm bổ sung verifier tùy chọn để loại crop giống loại quả khác. "
         "Theo backend/README.md, ngưỡng other=0,90 loại cả bốn box sai trong ảnh mận mẫu và giữ "
         "bốn box xoài trong ảnh xoài đông mẫu. Trên 846 box phát hiện khớp từ 250 ảnh quả hold-out, "
         "verifier loại 2/650 box xoài và 1/196 box thanh long. Đây là kiểm thử giới hạn, không chứng "
         "minh khả năng từ chối mọi loại quả chưa thấy.")
    para(d,"Để hỗ trợ cảnh khó, detailed_scan tăng kích thước suy luận và bật test-time augmentation: "
         "trên ảnh chồng lấp mẫu, số box xoài tăng từ hai lên bốn nhưng vẫn bỏ sót quả một phần. "
         "low_light_assist tăng tương phản chỉ cho detector; kiểm thử ảnh tối tổng hợp cho thấy cải thiện "
         "recall, nhưng chưa được đánh giá bằng ảnh đêm vườn thật.")
    d.add_heading("7.4. Minh họa kết quả",2)
    add_table(d,["Ảnh mẫu trong pipeline_check","Box đầu ra","Tóm tắt nhãn"],[
        ["dragon-fruit-pucka-fertilizer-1.jpg",3,"3 dragonfruit_ripe"],
        ["tru-cay-thanh-long.jpg",22,"21 dragonfruit_ripe; 1 dragonfruit_unripe"],
        ["oxi-house-cay-xoai-tu-quy-...jpg",46,"25 mango_young; 21 mango_uncertain"],
        ["images.jpeg",11,"10 mango_ripe; 1 mango_uncertain"],
    ])
    para(d,"Bảng chỉ mô tả đầu ra mô hình trong các ảnh thử được lưu kèm v3_evaluation.json. Không có "
         "box/độ chín chuẩn cho những ảnh này trong báo cáo, nên 46 box không thể tự suy ra rằng ảnh thật "
         "có đúng 46 quả. Các ảnh đông quả giúp nhóm nhận ra crop nhỏ và trạng thái uncertain xuất hiện "
         "thường xuyên, từ đó quyết định giữ nhãn chưa chắc chắn trong giao diện.")
    if PHOTO_DRAGON.exists():
        para(d,"Hình 7.2. Ảnh đầu ra thanh long từ pipeline hiện tại.",True)
        d.add_picture(str(PHOTO_DRAGON),width=Cm(12.8))
    if PHOTO_MANGO.exists():
        para(d,"Hình 7.3. Ảnh xoài nhiều quả, gồm nhãn chưa chắc chắn.",True)
        d.add_picture(str(PHOTO_MANGO),width=Cm(12.8))
    para(d,"Các ảnh minh họa là kết quả chạy mẫu lưu trong thư mục pipeline_check; không thay cho "
         "đánh giá định lượng. API video hiện được kiểm tra bằng clip tổng hợp từ ảnh, chưa có bộ video vườn thực "
         "được gắn nhãn để báo cáo sai số đếm.")

    d.add_heading("CHƯƠNG 8. HẠN CHẾ VÀ HƯỚNG PHÁT TRIỂN",1)
    for x in [
        "Quả nhỏ, bị che khuất hoặc chồng lấp vẫn có thể bị bỏ sót; ảnh quả khác có thể gây false positive.",
        "Độ chín xoài là bài toán khó: màu và các giai đoạn gần nhau; cơ chế chưa chắc chắn làm giảm số nhãn được chấp nhận.",
        "Thiếu ảnh và video tại đúng vườn, camera và điều kiện sáng mục tiêu để đánh giá độc lập đầu-cuối.",
        "ByteTrack ước lượng số quả duy nhất, nhưng chưa có phép đo định lượng trên video vườn thực.",
    ]:bullet(d,x)
    para(d,"Hướng tiếp theo là thu thập dữ liệu thực địa có box và nhãn độ chín đáng tin cậy, giữ tách biệt "
         "với train; đo precision, recall, sai số đếm và độ chín trên cùng bộ ảnh/video; bổ sung quả nhìn "
         "giống và các cảnh đông quả; sau đó tinh chỉnh mô hình và ngưỡng dựa trên lỗi quan sát được.")
    d.add_heading("8.1. Những kết luận hiện chưa thể đưa ra",2)
    for x in [
        "Chưa thể nói mô hình đếm chính xác ở một vườn cụ thể, vì chưa có bộ ảnh/video độc lập của vườn đó với mọi quả được gắn box.",
        "Chưa thể nói thanh long đạt độ chính xác độ chín 100% ngoài thực tế; con số 100% chỉ thuộc 131 crop test đã tuyển chọn.",
        "Chưa thể nói verifier loại được mọi quả không phải xoài/thanh long; ảnh mận mẫu và tập matched boxes không bao trùm mọi loài quả.",
        "Chưa thể nói detailed_scan hoặc low_light_assist luôn tốt hơn; mới có thử nghiệm ảnh mẫu và kiểm tra tối tổng hợp.",
        "Chưa thể chuyển kết quả detector v4_repaired thành kết quả của sản phẩm demo, vì backend hiện còn cài weight v3.",
    ]:bullet(d,x)
    d.add_heading("8.2. Kế hoạch đánh giá thực địa đề xuất",2)
    add_table(d,["Bước","Cách thực hiện","Đầu ra cần lưu"],[
        ["1. Lấy mẫu","Chụp nhiều cây, buổi sáng/trưa/chiều, ảnh tối, nhiều góc; quay video ổn định và rung nhẹ","Danh sách vườn/camera/ngày và tệp gốc"],
        ["2. Gắn nhãn","Đánh box mọi quả nhìn thấy; ghi loài, độ chín nếu chắc, độ che khuất; hai người kiểm tra mẫu khó","Bộ ground truth có hướng dẫn nhãn"],
        ["3. Khóa test","Giữ riêng ảnh/video của cây, ngày hoặc vườn không dùng để train/chọn ngưỡng","Manifest split và hash chống rò rỉ"],
        ["4. Đo ảnh","Precision, recall, mAP, sai số đếm và confusion độ chín đầu-cuối","Bảng theo loài, kích thước, ánh sáng, mật độ"],
        ["5. Đo video","Đếm quả thật duy nhất theo đoạn video, đối chiếu ID đứt/nhân đôi","MAE theo clip, FP/FN track; ví dụ lỗi"],
        ["6. Quyết định","So v3 với bản sửa nhãn dưới cùng điều kiện; chỉ thay checkpoint khi vượt mục tiêu đã thống nhất","Biên bản chọn model và giới hạn sử dụng"],
    ])
    para(d,"Với nhãn độ chín, nhóm cần thống nhất định nghĩa có thể nhận bằng ảnh cho từng mức, nhất là "
         "xoài young/mature/turning và thanh long rotten. Những quả không đủ bằng chứng nên được đánh "
         "dấu 'không xác định' trong ground truth, thay vì buộc người gắn nhãn đoán. Cách thiết kế test "
         "này giúp đo cả tỷ lệ từ chối nhãn của hệ thống, không chỉ accuracy trên các trường hợp dễ.")
    d.add_heading("8.3. Thứ tự cải tiến sau khi có dữ liệu mới",2)
    para(d,"Ưu tiên đầu là lỗi có tác động lớn nhất đến sản phẩm: false positive từ quả khác và bỏ sót "
         "quả nhỏ/chồng lấp. Tiếp theo là cải thiện độ chín xoài bằng nhãn chất lượng cao và kiểm tra "
         "calibration trên dữ liệu mới. Cuối cùng là cải thiện track ID trong video bằng cảnh di chuyển "
         "thực, xử lý trùng ID và đo tốc độ suy luận trên thiết bị dự kiến. Mỗi thay đổi nên đi cùng "
         "bộ benchmark khóa phiên bản và báo cáo trước/sau trên cùng ảnh, để nhóm biết thay đổi nào "
         "thực sự có ích.")

    d.add_heading("TÀI LIỆU VÀ MINH CHỨNG TRONG DỰ ÁN",1)
    for x in [
        "README.md — tổng quan, cài đặt, API và lưu ý về chỉ số cũ.",
        "training/README.md; training/train_two_stage_colab.ipynb — dữ liệu, huấn luyện và hiệu chỉnh.",
        "backend/README.md; backend/app.py; backend/two_stage.py; backend/video.py — pipeline và API.",
        "frontend/src/components/FruitDetector.tsx — giao diện người dùng.",
        "fruit_detection_runs_gcp_review/4169118715503181824/pipeline_check/v3_evaluation.json — classifier test.",
        "fruit_detection_runs_gcp_review/regression_20261002/trial_abc_summary.json — benchmark detector.",
        "fruit_detection_runs_gcp_review/regression_20261002/comparison.json — so sánh v3 và v4_repaired trên cùng bộ ảnh.",
        "data/prepared/two_stage_maturity_v3/preparation_report.json — quy mô dữ liệu của checkpoint đang cài.",
        "data/external/maturity_audit_report.json — kiểm toán nhãn và ảnh trùng.",
    ]:bullet(d,x)
    page_break(d)
    d.add_heading("PHỤ LỤC A. GỢI Ý LỜI THUYẾT TRÌNH THEO SLIDE",1)
    para(d,"Nội dung dưới đây cũng được nhúng vào Speaker Notes của tệp PowerPoint. Người trình bày có "
         "thể điều chỉnh cách nói và thời lượng nhưng cần giữ nguyên phạm vi của các chỉ số.")
    for i,(topic,script) in enumerate(TALK_TRACKS,1):
        d.add_heading(f"Slide {i:02d}. {topic}",2)
        para(d,script)

    d.add_heading("PHỤ LỤC B. CÁCH CHẠY VÀ KIỂM TRA BẢN DEMO",1)
    para(d,"Các bước dưới đây dành cho máy đã cài Python 3.10+ và Node.js 18+. Chạy lệnh từ thư mục "
         "gốc fruit_detection; trọng số v3 và JSON calibration phải nằm trong backend/weights. "
         "Các lệnh là hướng dẫn tái hiện bản demo tại máy, không phải yêu cầu để đọc báo cáo.")
    add_table(d,["Bước","Lệnh hoặc thao tác","Kết quả mong đợi"],[
        ["Cài backend","python3 -m venv .venv; source .venv/bin/activate; pip install -r backend/requirements.txt","Phụ thuộc FastAPI/Ultralytics được cài"],
        ["Chạy backend","uvicorn backend.app:app --host 127.0.0.1 --port 8000","/health trả model_loaded=true"],
        ["Cài và chạy frontend","cd frontend; npm ci; npm run dev","Mở http://localhost:5173"],
        ["Kiểm tra ảnh","curl -F 'file=@fruit.jpg' 'http://127.0.0.1:8000/detect?conf_threshold=0.25'","JSON có total_count, detections, annotated_image_base64"],
        ["Kiểm tra tài liệu API","Mở http://127.0.0.1:8000/docs","Có /detect, /detect-video, /health"],
    ])
    para(d,"Frontend ở chế độ phát triển dùng Vite proxy sang backend. Nếu đóng gói frontend để FastAPI "
         "phục vụ cùng URL, cần chạy npm run build trước. Trong báo cáo trực tiếp, hãy mở /health và "
         "kiểm tra pipeline_mode trước khi chụp hoặc trình bày kết quả, vì mode legacy và two-stage có "
         "schema nhãn khác nhau. Nếu không có GPU, thời gian suy luận trên CPU có thể cao hơn; tài liệu "
         "không nêu thời gian cố định khi chưa đo trên đúng máy.")
    d.add_heading("PHỤ LỤC C. PHÂN CÔNG NHÓM",1)
    para(d,"Điền tên, MSSV và phần việc thực tế của từng thành viên trước khi nộp. Không gán đóng góp khi "
         "chưa có thông tin từ nhóm.")
    add_table(d,["Thành viên / MSSV","Phần việc","Minh chứng"],
              [["................................", "................................", "................................"] for _ in range(4)])

    footer=d.sections[0].footer.paragraphs[0]
    footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("SMART ORCHARD AI  •  BÁO CÁO NHÓM  |  Trang ")
    fld=OxmlElement("w:fldSimple"); fld.set(qn("w:instr"),"PAGE")
    footer._p.append(fld)
    d.save(OUT / "Bao_cao_nhom_Smart_Orchard_AI.docx")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    # The slide deck now comes from build_presentation.py; this script only builds the Word report.
    build_docx()
    print("Created DOCX in",OUT,"(PPTX: run build_presentation.py)")
