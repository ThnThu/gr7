# Tài liệu đăng ký đề tài (Research)

Thư mục này chứa **một (01) phiếu đăng ký đề tài chính thức** cho đề tài:

**“Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp bằng AI”** (Nhóm 7)

## Nguồn chính thức (authoritative)

| Tệp | Vai trò |
|---|---|
| `PHIEU_DANG_KY_DE_TAI.md` | **Nguồn soạn thảo chính thức duy nhất (single source of truth).** Mọi chỉnh sửa nội dung phải thực hiện tại đây. |
| `PHIEU_DANG_KY_DE_TAI.docx` | **Bản phục vụ nộp/trình bày**, được sinh từ Markdown ở trên. Không chỉnh sửa trực tiếp DOCX như nguồn sự thật. |

> Không được tạo thêm bản “chính thức” khác (bản 1 trang/bản rút gọn song song) trong thư mục `Research/`. Nếu cần trích xuất theo mẫu khác, phải tạo bản dẫn xuất tạm và ghi rõ nguồn gốc từ `PHIEU_DANG_KY_DE_TAI.md`.

## Phiên bản cũ (lưu trữ)

Các phiên bản đăng ký trước đây được chuyển vào `archive/` để bảo toàn lịch sử và **không được chỉnh sửa, không được nộp**:

- `archive/phieu_dang_ky_de_tai_1_trang.md` / `.docx`
- `archive/phieu_dang_ky_de_tai_rut_gon.md` / `.docx`

Các tệp trong `archive/` chỉ dùng để tham chiếu/đối chiếu nội dung lịch sử.

## Tạo lại DOCX từ Markdown

Yêu cầu: Python 3 và gói `python-docx`.

```bash
# (tùy chọn) tạo môi trường tạm
python3 -m venv /tmp/opencode/docxenv
/tmp/opencode/docxenv/bin/pip install python-docx

# sinh DOCX chính thức
cd Research
/tmp/opencode/docxenv/bin/python build_docx.py
# hoặc, nếu đã cài python-docx trong môi trường hiện tại:
# python3 build_docx.py
```

Script `build_docx.py` chỉ đọc `PHIEU_DANG_KY_DE_TAI.md` và ghi đè `PHIEU_DANG_KY_DE_TAI.docx` (A4, phân cấp tiêu đề, bảng, đánh số trang ở chân trang khi được hỗ trợ). Script bỏ qua các tệp Markdown không tồn tại và **không** xử lý nội dung trong `archive/`.

## Quy ước nội dung

- Mục đánh dấu **[CẦN XÁC NHẬN]** là thông tin chưa được xác minh/chưa chốt và phải được bổ sung trước khi nộp chính thức.
- Tài liệu mô tả đề xuất/kế hoạch và các quyết định kỹ thuật đã chốt; **không** khẳng định kết quả thực nghiệm chưa thực hiện và **không** thay thế biên bản phê duyệt của giảng viên/hội đồng.
- Chính sách chia tập NEU-DET (Feature 001): **Train 75% = 1.350**, **Validation 15% = 270**, **Test 10% = 180** (tổng 1.800), **seed = 42**, phân tầng đa nhãn xác định (deterministic multi-label stratification) và chống rò rỉ nhóm trùng (duplicate-group leakage prevention).
- Hai nhánh thị giác **độc lập**: YOLOv8s (Object Detection, NEU-DET) và U-Net (Semantic Segmentation, NEU-Seg); không gộp dataset, không so sánh trực tiếp mAP với IoU/Dice, và YOLOv8s không thực hiện segmentation.
