# Phiếu đăng ký đề tài

Thư mục này chứa phiếu đăng ký đề tài **“Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh”** theo định hướng hai mô hình độc lập: YOLOv8s cho Object Detection và U-Net cho Semantic Segmentation. Tầng ứng dụng có thêm Captioning/VQA tiếng Việt từ JSON bằng LLM/prompt có sẵn; Model Fusion chỉ nằm ở phần mở rộng không bắt buộc.

## Các bản tài liệu

| Tệp | Mục đích |
|---|---|
| `phieu_dang_ky_de_tai_1_trang.md` | Bản một trang A4, bảng 10 mục chuẩn, mỗi mục 1–3 câu; dùng để nộp theo mẫu đăng ký một trang |
| `phieu_dang_ky_de_tai_rut_gon.md` | Bản cô đọng 11 mục, giữ đủ dữ liệu, baseline, đánh giá, kế hoạch và danh sách cần xác minh |
| `*.docx` | Bản Word tương ứng, tạo từ các tệp Markdown bằng `build_docx.py` |
| `build_docx.py` | Chuyển Markdown sang DOCX, không cần pandoc; tự bỏ qua tệp Markdown không tồn tại |

Bản một trang dùng Times New Roman 12 pt, lề 1,4 cm và bảng 2 cột (`Mục` | `Nội dung`) để vừa đúng một trang A4.

## Tạo lại DOCX

```bash
python3 -m venv /tmp/opencode/docxenv
/tmp/opencode/docxenv/bin/pip install python-docx
/tmp/opencode/docxenv/bin/python Research/build_docx.py
```

## Nguyên tắc nội dung

- **[Đã khảo sát]** / **[Đã kiểm tra]** chỉ dùng cho thông tin đã kiểm tra trực tiếp trên dữ liệu.
- **[Dự kiến]** là nội dung nhóm sẽ thực hiện, chưa có kết quả.
- **[Cần xác minh]** là nội dung chưa đủ căn cứ, không được khẳng định khi nộp.
- Baseline thống nhất với notebook: **B-D1 YOLOv8n** và **B-S1 phân ngưỡng Otsu**. Zero-shot COCO không phải baseline định lượng.
- Captioning/VQA chỉ diễn giải JSON, không tạo box/mask mới, không fine-tune LLM/VLM và không phải fusion.
- Không có kết quả mAP/IoU/Dice nào trong tài liệu; mọi chỉ số là kế hoạch đánh giá.

## Trước khi nộp

1. Xác minh giấy phép NEU-DET và NEU-Seg.
2. Audit **182 ảnh** single-class trùng NEU-DET có mask khác lớp box và **11 cặp ảnh gần trùng** NEU-Seg.
3. Chốt cách xử lý lỗi dữ liệu: `crazing_240.xml` nằm sai tập; 900 ảnh trùng giữa hai bộ; 60 ảnh both-test dùng làm demo held-out.
4. Xác nhận GPU/RAM, thời gian huấn luyện và phần cứng đo thời gian suy luận.
5. Không dùng checkpoint U-Net chưa rõ nguồn gốc và dữ liệu huấn luyện.
6. Đồng bộ `define_and_design_v2.ipynb`, phiếu một trang và các sơ đồ trong `assets/define-design/`.
