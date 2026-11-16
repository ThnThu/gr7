# Sơ đồ Define & Design

Thư mục này chứa 01 sơ đồ tổng quan cho giai đoạn **Define** và 04 sơ đồ chi tiết cho giai đoạn **Design** của đề tài *“Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh”*.

Toàn bộ sơ đồ dùng Mermaid `flowchart LR`, nền trắng, cùng một bảng màu:

| Màu | Vai trò |
|---|---|
| Navy `#0f2a44` | Thành phần hệ thống chính |
| Blue `#dbeafe` / `#2563eb` | YOLOv8s · Detection |
| Teal `#ccfbf1` / `#0f766e` | U-Net · Segmentation |
| Purple `#f3e8ff` / `#7e22ce` | Text Generation Layer · Captioning/VQA |
| Gray `#f1f5f9` / `#94a3b8` | Dữ liệu và xử lý chung |
| Green `#dcfce7` / `#16a34a` | Đầu ra và kết quả |

## Danh mục

| Tệp | Giai đoạn | Nội dung |
|---|---|---|
| `define_system_overview` | Define | Người dùng → tải ảnh → hai nhánh AI (YOLOv8s, U-Net) → sinh mô tả/hỏi đáp → hiển thị hình ảnh + ngôn ngữ |
| `01_system_architecture` | Design | Kiến trúc thành phần; `Result Collection` → `Text Generation Layer` → `Result Visualization`; hợp đồng JSON giữa các tầng |
| `02_data_preparation_pipeline` | Design | Hai pipeline chuẩn bị dữ liệu riêng cho NEU-DET và NEU-Seg |
| `03_parallel_inference_workflow` | Design | Suy luận song song, độc lập, thêm bước sinh ngôn ngữ; không fusion |
| `04_model_evaluation_workflow` | Design | Đánh giá riêng từng mô hình với baseline B-D1/B-S1, thêm đánh giá tầng ứng dụng; không so sánh mAP với IoU |

Mỗi sơ đồ có ba định dạng: `.mmd` (nguồn, chỉnh sửa được), `.svg` (vector), `.png` (dán vào Word/Google Docs). Tệp `render.py` dựng lại toàn bộ và tự sửa lỗi mất chữ/dính chữ.

## Quy ước nội dung

- Hai mô hình **độc lập**: không chia sẻ trọng số, không chia sẻ đặc trưng, không hợp nhất đầu ra trong luồng chính.
- **Tầng ứng dụng Captioning/VQA** chỉ nhận JSON đã chuẩn hóa để sinh mô tả tiếng Việt và trả lời câu hỏi mẫu; không tạo/sửa box, mask hay lớp.
- Dùng **LLM/prompt có sẵn, không fine-tune**; có template fallback khi LLM lỗi, timeout hoặc không có mạng.
- **Không** có Model Fusion/Decision Fusion trong 05 sơ đồ. Fusion chỉ là hướng mở rộng không bắt buộc ở mục **2.12** của `define_and_design_v2.ipynb`.
- Baseline bắt buộc: **B-D1 YOLOv8n** (Detection) và **B-S1 phân ngưỡng Otsu** (Segmentation). B-D2/B-S2 chỉ là tùy chọn nếu đủ tài nguyên.
- Detection và Segmentation dùng hai bộ dữ liệu riêng, không gộp thành dataset chung.
- mAP (Detection) và IoU/Dice (Segmentation) đo hai nhiệm vụ khác nhau, không so sánh trực tiếp.

## Đồng bộ với notebook

Các tệp `.mmd` được trích trực tiếp từ các khối Mermaid trong `define_and_design_v2.ipynb`. Khi sửa sơ đồ, sửa khối Mermaid trong notebook trước rồi trích lại để tránh lệch nội dung:

```bash
python3 - <<'PY'
import json, re
from pathlib import Path
nb = json.load(open('define_and_design_v2.ipynb'))
blocks = []
for cell in nb['cells']:
    s = ''.join(cell['source'])
    blocks += [m.group(1).strip() for m in re.finditer(r'```mermaid\n(.*?)```', s, re.S)]
names = ['define_system_overview', '01_system_architecture',
         '02_data_preparation_pipeline', '03_parallel_inference_workflow',
         '04_model_evaluation_workflow']
for name, body in zip(names, blocks):
    Path(f'assets/define-design/{name}.mmd').write_text(body + '\n', encoding='utf-8')
PY
```

## Dựng lại sơ đồ

Cần Node.js và Chromium (Playwright/Puppeteer) cho `mmdc`:

```bash
npx -y @mermaid-js/mermaid-cli \
  -i assets/define-design/01_system_architecture.mmd \
  -o assets/define-design/01_system_architecture.svg \
  -b white
```

> **Quan trọng — giữ chữ khi render:** mỗi khối Mermaid mở đầu bằng
> `%%{init: {"htmlLabels": false}}%%`. Nếu thiếu dòng này, Mermaid xuất nhãn dưới dạng
> `<foreignObject>` (HTML) và `rsvg-convert` sẽ **bỏ toàn bộ chữ**, chỉ còn khung.
> Dòng init buộc nhãn thành thẻ `<text>` nên SVG/PNG giữ được chữ. Khi sửa sơ đồ, giữ
> nguyên dòng này ở đầu mỗi khối.

Nếu máy không có Chromium, dùng script có sẵn (gọi Kroki rồi sửa SVG và gọi `rsvg-convert`):

```bash
python3 assets/define-design/render.py          # tất cả .mmd
python3 assets/define-design/render.py 04_model_evaluation_workflow.mmd
```

Script xử lý **hai lỗi render** đã gặp:

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| Mất toàn bộ chữ, chỉ còn khung | Mermaid vẽ nhãn bằng `<foreignObject>`, `rsvg-convert` bỏ qua | Dòng `%%{init: {"htmlLabels": false}}%%` ở đầu mỗi khối |
| Chữ dính nhau: `Ngườidùng` | `rsvg-convert` bỏ dấu cách đầu mỗi `<tspan>` | Script thêm `xml:space="preserve"` vào mọi `<text>` |

Nếu làm thủ công, phải thêm `xml:space="preserve"` sau khi tải SVG:

```bash
curl -X POST -H "Content-Type: text/plain" \
  --data-binary @assets/define-design/01_system_architecture.mmd \
  https://kroki.io/mermaid/svg -o 01_system_architecture.svg
sed -i 's/<text /<text xml:space="preserve" /g' 01_system_architecture.svg
rsvg-convert -w 2200 01_system_architecture.svg -o 01_system_architecture.png
```

Kiểm tra nhanh sau khi render (phải ra `foreignObject=0`, `text>0`, và chữ có dấu cách):

```bash
grep -c '<foreignObject' 01_system_architecture.svg   # phải là 0
grep -o '<text' 01_system_architecture.svg | wc -l    # phải > 0
rsvg-convert -f pdf 01_system_architecture.svg -o /tmp/chk.pdf
pdftotext /tmp/chk.pdf - | head -3                    # phải đọc được "Người dùng", "Tải ảnh sản phẩm"
```

Lưu ý: Kroki dùng phiên bản Mermaid khác nên khoảng cách và kích thước có thể lệch so với `mmdc`; nên dựng lại toàn bộ bằng một công cụ duy nhất để giữ phong cách đồng nhất.

## Khổ giấy

Ưu tiên chèn ảnh ở chế độ **A4 ngang, rộng hết lề** (khoảng 25–26 cm). Các sơ đồ `01_system_architecture`, `03_parallel_inference_workflow` và `04_model_evaluation_workflow` có tỉ lệ ngang lớn do thể hiện đủ hai nhánh và chuỗi kết quả; khi in khổ dọc nên tách thành hình riêng hoặc dùng khổ A3.

## Cần xác nhận

- Audit **182 ảnh** single-class trùng NEU-DET có mask khác lớp box và **11 cặp ảnh gần trùng** NEU-Seg trước khi huấn luyện.
- Giấy phép của NEU-DET và NEU-Seg chưa được xác minh.
- Số liệu trong sơ đồ là mô tả quy trình, không phải kết quả thực nghiệm.
