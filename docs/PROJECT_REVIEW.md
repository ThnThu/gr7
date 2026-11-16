# PROJECT_REVIEW — AI Industrial Defect (Topic 5)

**Ngày rà soát:** 2026-11-16  
**Phạm vi:** Rà soát toàn bộ nội dung hiện có trong repo `/home/thu/AI_Industrial_Defect` (chỉ đọc; không sửa/xóa/di chuyển file hiện có ngoại trừ tạo báo cáo này).  
**Ghi chú:** Những nội dung không đủ căn cứ được ghi rõ “chưa xác định được” kèm lý do.

## 1. Tóm tắt điều hành (5-7 dòng)
- Repo tập trung vào **Thành viên 2 (Detection Engineer – YOLOv8s, NEU-DET)** theo `phancong.md`; phần lớn hiện vật thực thi nằm trong `yolov8-detection/` (Spec Kit + code data-prep + tests), còn các nhánh U-Net/Otsu/Web/Captioning-VQA của thành viên khác **chưa thấy triển khai trong repo**.
- `Research/` chứa 2 bản phiếu `.md` + 2 `.docx` + `build_docx.py`/`README.md`; `build_docx.py` tham chiếu thêm một nguồn `phieu_dang_ky_de_tai.md` **không tồn tại** trong thư mục, nên không thể khẳng định “bản đầy đủ” đã được build từ script hiện tại.
- Thiết kế (theo sơ đồ `assets/define-design/*.mmd`) mô tả hệ thống 2 nhánh YOLOv8s+U-Net, có tầng Captioning/VQA từ JSON; notebook `define_and_design_v2.ipynb` chỉ có **3 cell markdown** (tiêu đề/anchor) theo kiểm tra nhanh, nội dung chi tiết notebook **chưa xác định được** từ cấu trúc hiện tại.
- Spec Kit: `specs/001-neu-det-data-preparation` đầy đủ spec/plan/tasks/research/contracts/checklists; `specs/002-yolov8s-detection-pipeline` mới có `spec.md` + checklist (thiếu plan/tasks/research/data-model/contracts/quickstart). `tasks.md` của 001 có **toàn bộ 36 task chưa đánh dấu hoàn thành** `[ ]`, dù code và test liên quan đã tồn tại.
- Code `yolov8-detection/src/detection` hiện triển khai pipeline chuẩn bị dữ liệu/CLI (`prepare`) và đã có 138 test pass khi chạy `.venv/bin/python -m pytest tests -q` (138 passed, 1.31s). Huấn luyện/suy luận/đánh giá YOLOv8s (002) **chưa thấy code triển khai**.
- Dữ liệu NEU-DET có trong `NEU-DET/NEU-DET/{train,validation}`: 1440+360 ảnh (6 lớp, 240/60 ảnh/lớp), 1440/360 XML, 3335/854 object; `Results/`, `yolov8-detection/{data,configs,runs,weights}` đều trống (không có checkpoint/log/metrics).

## 2. Kết luận về phiếu đăng ký đã chốt

### 2.1 Liệt kê từng phiếu/tài liệu trong `Research/`

| Tệp | Ngày sửa cuối (mtime) | Kích thước | Mục đích suy ra |
|---|---|---:|---|
| `Research/phieu_dang_ky_de_tai_1_trang.md` | 2026-11-13 18:13 | 4,440 B | Bản 1 trang A4, bảng 10 mục (theo nội dung/README) |
| `Research/phieu_dang_ky_de_tai_1_trang.docx` | 2026-11-13 18:13 | 39,135 B | DOCX tương ứng bản 1 trang |
| `Research/phieu_dang_ky_de_tai_rut_gon.md` | 2026-11-13 18:09 | 11,989 B | Bản rút gọn 11 mục |
| `Research/phieu_dang_ky_de_tai_rut_gon.docx` | 2026-11-13 18:13 | 42,175 B | DOCX tương ứng bản rút gọn |
| `Research/build_docx.py` | 2026-11-13 18:07 | 7,697 B | Script chuyển `.md` → `.docx` (bỏ qua md không tồn tại) |
| `Research/README.md` | 2026-11-13 18:11 | 2,783 B | Mô tả các bản tài liệu, cách build, nguyên tắc nội dung |

> Không tìm thấy file `Research/phieu_dang_ky_de_tai.md` (bản đầy đủ) trong `Research/` (`find . -name 'phieu_dang_ky_de_tai*'`).

### 2.2 So sánh khác biệt chính giữa các phiếu

| Tiêu chí | `phieu_dang_ky_de_tai_1_trang.md` | `phieu_dang_ky_de_tai_rut_gon.md` | Ghi chú |
|---|---|---|---|
| Tên đề tài | Topic 5 — Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh | Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh | Khác cách ghi tiền tố “Topic 5” |
| Phạm vi | 2 nhiệm vụ độc lập: Detection 6 lớp (YOLOv8s) + Segmentation 3 lớp (U-Net); Captioning/VQA tiếng Việt từ JSON (mở rộng giao diện, không fine-tune); ngoài phạm vi: video/realtime, fine-tune VLM/LLM, mạng đa nhiệm, fusion trong luồng chính | Tương tự: Detection + Segmentation độc lập; Captioning/VQA tầng ứng dụng; Decision Fusion là mở rộng nghiên cứu không bắt buộc; không gọi 2 mô hình trong app là Model Fusion | Nhất quán về hướng chính (không fusion trong luồng chính) |
| Mô hình | YOLOv8s pretrained COCO fine-tune (640×640); U-Net từ đầu 4 kênh (256×256, CE+Dice) | YOLOv8s fine-tune 6 lớp; U-Net encoder–decoder 4 kênh (CE+Dice), ưu tiên lightweight nếu thiếu GPU | Nhất quán mô hình chính |
| Baseline | B-D1 YOLOv8n; B-S1 Otsu; tùy chọn B-D2 Faster R-CNN, B-S2 U-Net pretrained | B-D1 YOLOv8n; B-S1 Otsu; tùy chọn B-D2/B-S2; không dùng zero-shot COCO làm baseline định lượng | Nhất quán |
| Dataset/nhãn (đã nêu) | NEU-DET 1.800 ảnh 200×200, 6 lớp, 4.189 box, chia 1.152/288/360; NEU-Seg 4.470 ảnh, mask 0–3 (inclusion/patches/scratches), chia 3.267/363/840 | NEU-DET 1.800 ảnh, 4.189 box, 123 ảnh đa lớp, 1.440 train/360 val (dự kiến dùng 360 val làm test, tách train 80/20); NEU-Seg 4.470 ảnh (3.630/840), mask uint8 0–3, cần xác minh ánh xạ tên lớp mask | **Khác cách diễn đạt/chia tập NEU-DET** (1.152/288/360 vs 80/20 từ 1.440 + 360 test) |
| Chỉ số đánh giá | Detection: P/R/mAP@0.5/mAP@0.5:0.95 trên 360 test NEU-DET; Seg: IoU/Dice/mIoU/Pixel P/R trên 840 test NEU-Seg; Captioning/VQA: nhất quán JSON, hallucination, độ trễ (20–30 ảnh, 5–10 câu hỏi) | Tương tự (bảng mục 9); Captioning/VQA không dùng mAP/IoU, không gộp bảng thị giác | Nhất quán loại chỉ số |
| Ghi chú/rủi ro | Giấy phép cần xác minh; audit 182 ảnh box–mask bất nhất trước tuần 3 | Liệt kê chi tiết mục “Cần xác minh trước khi nộp” (giấy phép, audit 182/11 cặp, 900 ảnh trùng, XML/ảnh lệch, 60 ảnh demo, GPU, không dùng checkpoint U-Net không rõ nguồn, lớp chung fusion, phần cứng đo suy luận, đồng bộ notebook/phiếu/sơ đồ) | Bản rút gọn chi tiết hơn về kiểm chứng |

### 2.3 Nguồn build `.docx` và lệch so với `.md`

| DOCX | MD nguồn tương ứng (theo `build_docx.py`) | Bằng chứng | Lệch `.docx` so với `.md`? |
|---|---|---|---|
| `Research/phieu_dang_ky_de_tai_1_trang.docx` | `Research/phieu_dang_ky_de_tai_1_trang.md` | `Research/build_docx.py` jobs (dòng ~213-219) map cặp này; mtime md 18:13, docx 18:13 | **Chưa xác định được** (không so sánh nội dung nhị phân .docx; timestamp trùng nhưng chưa đủ chứng cứ nội dung) |
| `Research/phieu_dang_ky_de_tai_rut_gon.docx` | `Research/phieu_dang_ky_de_tai_rut_gon.md` | `build_docx.py` jobs (dòng ~206-212); mtime md 18:09, docx 18:13 | **Chưa xác định được** (md cũ hơn docx 4 phút nhưng không thể kết luận lệch nếu docx build sau từ phiên bản tương đương/khác; cần mở file để xác minh) |
| (không có docx) | `Research/phieu_dang_ky_de_tai.md` (bản đầy đủ) | `build_docx.py` tham chiếu đầu tiên `phieu_dang_ky_de_tai.md` → `phieu_dang_ky_de_tai.docx` nhưng có nhánh “Bỏ qua (không có tệp)” nếu thiếu | `phieu_dang_ky_de_tai.md` và `.docx` **không tồn tại** trong `Research/` |

### 2.4 Đối chiếu với `phancong.md`, `define_and_design_v2.ipynb`, `assets/define-design`

| Nguồn đối chiếu | Nội dung quan sát | Mức khớp với phiếu nào |
|---|---|---|
| `phancong.md` | Đề tài Topic 5, 6 thành viên; TV2: YOLOv8s trên NEU-DET; TV3: YOLOv8n baseline; TV4: U-Net/NEU-Seg; TV5: Otsu + Web Streamlit/Gradio tích hợp 2 nhánh; TV6: Captioning/VQA (nếu được duyệt), báo cáo/README | Khớp **cả 2 phiếu** về kiến trúc 2 nhánh + baseline + ứng dụng web/Captioning (ở mức định hướng); không đủ chi tiết để phân biệt 1 trang/rút gọn là “chốt” |
| `assets/define-design/*.mmd` (`01_system_architecture.mmd`, `03_parallel_inference_workflow.mmd`, `04_model_evaluation_workflow.mmd`, `02_data_preparation_pipeline.mmd`, `define_system_overview.mmd`, `README.md`) | 2 nhánh độc lập YOLOv8s (NEU-DET) & U-Net (NEU-Seg), Text Generation Layer Captioning/VQA từ JSON (không fine-tune, fallback), baseline B-D1/B-S1 (tùy chọn B-D2/B-S2), không fusion trong luồng chính, không so mAP với IoU | Khớp **bản rút gọn** và **bản 1 trang** (cả hai đều nhất quán với sơ đồ); khớp nhất về nhấn mạnh “không fusion/không so sánh chéo chỉ số” như `README.md` sơ đồ |
| `define_and_design_v2.ipynb` | File 45,092 B; kiểm tra nhanh cho thấy **3 cell markdown**: tiêu đề đề tài và 2 anchor `<a id="define">`, `<a id="design">` (không thấy cell nội dung/sơ đồ trong trích xuất nhanh) | **Chưa xác định được mức khớp nội dung** với phiếu nào (notebook có thể chứa nội dung không hiển thị trong trích xuất tối thiểu hoặc bị rút gọn; cần mở đầy đủ để kết luận) |
| Triển khai thực tế trong repo (`yolov8-detection/specs`, `src/detection`) | Chỉ tập trung Feature 001 data-prep NEU-DET/YOLO; Feature 002 mới ở mức spec cho train/eval/infer YOLOv8s; không có code U-Net/Seg/Otsu/Web/Captioning | **Khớp phạm vi Thành viên 2** trong `phancong.md`; **chưa phản ánh đầy đủ** phạm vi hệ thống mô tả trong cả hai phiếu/sơ đồ |

### 2.5 Kết luận: phiếu nào nhiều khả năng là bản chốt

| Kết luận | Độ tin cậy | Bằng chứng | Phiếu có thể là nháp/cũ (cần xác nhận) |
|---|---|---|---|
| **`Research/phieu_dang_ky_de_tai_rut_gon.md` (và `.docx` tương ứng)** có nhiều khả năng là bản đang được dùng làm tham chiếu chi tiết gần nhất với thiết kế/sơ đồ và ghi chú kiểm chứng. **`Research/phieu_dang_ky_de_tai_1_trang.md`** nhiều khả năng là biến thể nộp gọn (1 trang) cùng hướng nội dung. | **Trung bình** | Cả hai md tồn tại, nội dung nhất quán với `assets/define-design/README.md` và `phancong.md` về 2 nhánh + baseline + Captioning/VQA; bản rút gọn có mục “Cần xác minh trước khi nộp” chi tiết và `README.md` Research nêu 3 bản nhưng bản đầy đủ `.md` vắng mặt. Không có dấu hiệu “approved/chốt” rõ ràng (commit/tag/chữ ký) trong repo. | (1) `Research/phieu_dang_ky_de_tai.md` / `.docx` (bản đầy đủ) — **không tồn tại**, có thể đã xóa/chưa tạo hoặc nằm ngoài repo (cần xác nhận). (2) Một trong hai bản 1 trang/rút gọn có thể là nháp tùy mục đích nộp — **chưa xác định được**. (3) `build_docx.py` còn job build bản đầy đủ — dấu vết quy trình cũ/chưa đồng bộ. |

## 3. Tiến độ theo từng hạng mục

### 3.1 Thiết kế (`define_and_design_v2.ipynb`, sơ đồ)

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Notebook `define_and_design_v2.ipynb` | **Một phần / chưa xác định nội dung đầy đủ** | Tồn tại (45,092 B). Trích xuất nhanh: 3 cell markdown, nội dung gồm tiêu đề đề tài và anchor `define`/`design` (`define_and_design_v2.ipynb`). Không xác nhận được pipeline/mô tả chi tiết từ lần đọc nhanh. |
| Sơ đồ `assets/define-design/*.mmd` | **Có** | 5 file `.mmd`: `define_system_overview`, `01_system_architecture`, `02_data_preparation_pipeline`, `03_parallel_inference_workflow`, `04_model_evaluation_workflow`. Mô tả 2 nhánh độc lập, Result Collection → Text Generation Layer (Captioning/VQA) → Visualization, baseline B-D1/B-S1, không fusion. |
| Sơ đồ `.svg/.png`, `render.py`, `README.md` | **Có** | Có bản render SVG/PNG cho 5 sơ đồ, `assets/define-design/render.py`, `assets/define-design/README.md` (hướng dẫn dựng lại, lưu ý `htmlLabels:false`, đồng bộ với notebook). |

### 3.2 Spec Kit (`yolov8-detection/specs/001-*`, `002-*`)

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| `specs/001-neu-det-data-preparation` — file | **Đầy đủ (theo cấu trúc Spec Kit)** | Có: `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `quickstart.md`, `checklists/requirements.md`, `contracts/cli.md`, `contracts/artifact-formats.md`. `.specify/memory/constitution.md` (v1.0.0) tồn tại. |
| 001 — mục tiêu (tóm tắt) | **Rõ** | Chuẩn bị NEU-DET cho Object Detection: chuyển VOC XML→YOLO, kiểm tra class/bbox/cặp ảnh-nhãn/trùng, split 75/15/10 tái lập (seed 42), báo cáo/manifest, không sửa nguồn, CLI `detection prepare` (`specs/001-.../spec.md`, `plan.md`, `quickstart.md`). |
| 001 — tasks | **Chưa đánh dấu hoàn thành** | `tasks.md`: 36 task dạng checkbox, **0 `[X]`, 36 `[ ]`** (T001–T036). Trạng thái checkbox **không phản ánh** việc code/test đã có (xem mục 3.3). |
| 001 — task còn dở theo phase (theo `[ ]`) | **Tất cả phases** | Phase 1 (T001–T003), Phase 2 (T004–T010), Phase 3/US1 (T011–T016), Phase 4/US2 (T017–T024), Phase 5/US3 (T025–T032), Phase 6 Polish (T033–T036). |
| `specs/002-yolov8s-detection-pipeline` — file | **Thiếu nhiều** | Có: `spec.md`, `checklists/requirements.md`. **Thiếu:** `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/` (và các file Spec Kit khác nếu cần). |
| 002 — mục tiêu (tóm tắt) | **Rõ (ở mức spec)** | Huấn luyện YOLOv8s từ pretrained trên dữ liệu đã chuẩn bị (001), lưu config/log/checkpoint, đánh giá P/R/mAP50/mAP50-95, suy luận+trực quan hóa trên ảnh đơn; phụ thuộc 001 (`specs/002-.../spec.md`). |
| 002 — tasks | **Chưa có** | Không có `tasks.md` → **chưa xác định được** số task done/todo. |

### 3.3 Code, cấu hình, test (`yolov8-detection/`)

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| `yolov8-detection/src/detection` | **Có (data-prep/CLI)** | `cli.py`: argparse `detection prepare`, validate source/output/ratios/overwrite, map exit code 0/2/3/4/5. `data/classes.py`: mapping 6 lớp cố định. `data/discovery.py`: discover subset, fingerprint, pairing trong subset. `data/converter.py`: VOC→YOLO (normalize, không clip, empty label). `data/validator.py`: verify ảnh/hash/size (Pillow). `data/manifest.py`: build config, write JSON atomic. `data/pipeline.py`: orchestrate discover→pair→verify→convert→write (US1/interim `train` theo code), overwrite xử lý artifact sở hữu. `data/models.py`, `data/splitter.py`: **chưa đọc chi tiết toàn bộ** trong lần rà soát này (chỉ kiểm tra tồn tại/khung). |
| `yolov8-detection/configs`, `data`, `runs`, `weights` | **Trống** | Thư mục tồn tại nhưng không có file nội dung. |
| `yolov8-detection/pyproject.toml` | **Có** | Package `detection` (src layout), Python >=3.11, deps `Pillow`, dev `pytest`, script `detection= detection.cli:main`. |
| Tests | **Có, pass** | `tests/unit/` (test_classes, cli, converter, discovery, manifest, models) + `tests/integration/test_prepare_dataset.py` + `tests/conftest.py`. Kết quả chạy: **138 passed in 1.31s** (`cd yolov8-detection && .venv/bin/python -m pytest tests -q`). Lưu ý: `python3 -m pytest` hệ thống báo “No module named pytest”; dùng `.venv`. |
| Test thiếu (so với kỳ vọng tài liệu 001) | **Một phần** | Tài liệu/plan/tasks 001 nhắc `test_validator.py`, `test_splitter.py`, full US2/US3 behaviors; trong `tests/unit/` hiện **không có** `test_validator.py`, `test_splitter.py` (chỉ thấy test khác). Chưa xác định được mức bao phủ đầy đủ so với T017–T032. |

### 3.4 Dữ liệu và kết quả

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Dataset NEU-DET gốc | **Có** | `NEU-DET/NEU-DET/{train,validation}` với `images/` (thư mục con theo lớp) và `annotations/`. Train: 1440 ảnh (240/lớp × 6 lớp), 1440 XML, 3335 object (crazing 527, inclusion 852, patches 688, pitted_surface 345, rolled-in_scale 496, scratches 427). Validation: 360 ảnh (60/lớp), 360/361 file XML? `find` đếm 360 ảnh & 361 xml trong validation (`ls`/`find` cho thấy 360 jpg, 361 xml) — **chênh 1 file XML cần kiểm tra**; tổng object 854. `NEU-DET/NEU-DET/check_neudet.py` là script kiểm tra (chạy từ root split theo thiết kế script). |
| Cách chia train/val/test | **Chưa có output xử lý** | Nguồn có `train` và `validation`; không thấy bộ đã xử lý/split train/val/test trong `yolov8-detection/data` hay nơi khác (trống). Spec 001 dự kiến 75/15/10, seed 42. |
| `data/`, `weights/`, `runs/` (yolov8-detection) | **Trống** | Không có dataset processed, checkpoint, log huấn luyện. |
| `Results/` (repo root) | **Trống** | Không có chỉ số/báo cáo kết quả. |
| Checkpoint/log huấn luyện/chỉ số | **Không có** | Chưa xác định được metrics vì chưa có artifact huấn luyện/đánh giá. |

## 4. Danh sách mâu thuẫn / rủi ro

| # | Loại | Mô tả | Dẫn chứng |
|---|---|---|---|
| 1 | Mâu thuẫn/thiếu nhất quán | **Thiếu “bản đầy đủ” phiếu đăng ký**: `build_docx.py` và `Research/README.md` tham chiếu `phieu_dang_ky_de_tai.md/.docx` nhưng file không tồn tại. | `Research/build_docx.py`, `Research/README.md`, `find` trong `Research/` |
| 2 | Mâu thuẫn | **Cách chia NEU-DET khác nhau giữa phiếu 1 trang và rút gọn** (1.152/288/360 vs dùng 360 val làm test + tách 1.440 train 80/20). Spec 001 lại định hướng split 75/15/10 từ pool đã ghép. | `Research/phieu_dang_ky_de_tai_1_trang.md`, `Research/phieu_dang_ky_de_tai_rut_gon.md`, `yolov8-detection/specs/001-.../spec.md` |
| 3 | Mâu thuẫn phạm vi | **Thiết kế/sơ đồ/phiếu** mô tả hệ thống 2 nhánh + Captioning/VQA + (tùy chọn) so sánh baseline; **repo thực tế** chủ yếu mới có data-prep detection (001) và spec 002, chưa có Segmentation/Web/Captioning/Otsu. | `assets/define-design/*.mmd`, `Research/*.md`, `phancong.md`, cây `yolov8-detection/src` |
| 4 | Mâu thuẫn quy trình | **`tasks.md` (001) toàn bộ `[ ]`** trong khi code và 138 test pass — trạng thái task không đồng bộ với hiện trạng thực thi (rủi ro hiểu sai tiến độ). | `yolov8-detection/specs/001-.../tasks.md`, kết quả pytest |
| 5 | Rủi ro dữ liệu | **Validation annotations đếm 361 XML vs 360 ảnh** (theo lệnh `find`/kiểm tra nhanh) — có thể có XML thừa/không ghép; cần xác minh bằng pipeline/check. | Đếm file trong `NEU-DET/NEU-DET/validation/` |
| 6 | Rủi ro tái lập/môi trường | `pytest` không có ở Python hệ thống; chạy được trong `yolov8-detection/.venv` (Python 3.14 theo pycache). `.venv`, `.pytest_cache`, `__pycache__`, `.egg-info` nằm trong repo — có thể gây nhiễu/khác biệt môi trường. | `yolov8-detection/.venv`, `yolov8-detection/pyproject.toml`, kết quả chạy test |
| 7 | Thiếu so với “Sản phẩm bàn giao” TV2 (`phancong.md`) | Thiếu: **checkpoint YOLOv8s**, **code train/predict** (002), **log huấn luyện**, **bảng chỉ số đánh giá (P/R/mAP)**, **báo cáo phân tích lỗi Detection**. Đã có một phần: code liên quan chuẩn bị dữ liệu/CLI, tests, specs. | `phancong.md` (mục TV2), `yolov8-detection/{runs,weights,configs,src}`, `Results/` |
| 8 | Thiếu Spec Kit 002 | 002 chỉ có `spec.md` + checklist; thiếu `plan/tasks/research/...` → khó triển khai/đánh giá tiến độ có kiểm soát. | `yolov8-detection/specs/002-yolov8s-detection-pipeline/` |
| 9 | Rủi ro thiết kế tài liệu | `define_and_design_v2.ipynb` trích xuất nhanh chỉ thấy 3 cell/ít nội dung hiển thị — có thể không phản ánh đầy đủ sơ đồ/thiết kế như kỳ vọng đối chiếu. | `define_and_design_v2.ipynb` |
| 10 | Đường dẫn/giả định | `NEU-DET/NEU-DET/check_neudet.py` dùng `ROOT = Path(".")` và tìm `train/images`, `train/annotations` tương đối — chạy sai thư mục sẽ cho kết quả sai (script tiện ích, không phải lỗi pipeline chính nhưng dễ nhầm). | `NEU-DET/NEU-DET/check_neudet.py` |

## 5. Việc cần làm tiếp theo (ưu tiên, tối đa 10)

| Ưu tiên | Việc cần làm | Lý do | Gợi ý đầu ra/kiểm chứng |
|---:|---|---|---|
| 1 | **Xác nhận chính thức phiếu đăng ký đã chốt** (1 trang hay rút gọn hay bản đầy đủ ngoài repo) và đồng bộ phiên bản `.md/.docx` | Tránh mâu thuẫn phạm vi/split/đánh giá khi nộp và khi triển khai | Cập nhật `Research/` (bổ sung bản đầy đủ nếu cần), ghi rõ bản “final” trong README/tên file; đối chiếu `build_docx.py` |
| 2 | **Chốt quy ước chia dữ liệu NEU-DET** cho Detection (split nào dùng train/val/test, seed, tỷ lệ) và thống nhất với spec 001/002 & phiếu | Hiện có ≥3 cách diễn đạt khác nhau; ảnh hưởng công bằng baseline và đánh giá | Tài liệu quyết định + cập nhật spec/contracts/phiếu; manifest split khi chạy pipeline |
| 3 | **Chạy/kiểm tra NEU-DET thực tế** (bao gồm lệch 361 xml vs 360 ảnh ở validation) và tạo dataset processed + `validation_report.json`/`split_manifest.json` | Có dữ liệu gốc nhưng chưa có artifact xử lý; cần phát hiện lỗi ghép nhãn | Output trong `yolov8-detection/data/...` (hoặc theo chọn), report gate/accounting |
| 4 | **Hoàn thiện Spec Kit 002** (`plan.md`, `tasks.md`, contracts/research/data-model/quickstart) trước khi code train/eval/infer | 002 mới dừng ở spec; cần kiểm soát cấu hình, log, chọn checkpoint, anti-leakage test set | Bộ file trong `specs/002-yolov8s-detection-pipeline/` |
| 5 | **Triển khai pipeline 002**: train YOLOv8s (pretrained), lưu config/log/checkpoint, eval trên val/test, infer+visualize | Bàn giao cốt lõi của TV2 còn thiếu | `src/detection` mở rộng hoặc module phù hợp, `configs/`, `runs/`, `weights/`, script/CLI rõ ràng |
| 6 | **Sinh báo cáo đánh giá và phân tích lỗi Detection** (P, R, mAP50, mAP50-95 tổng & theo lớp) | Đáp ứng sản phẩm bàn giao TV2 và yêu cầu spec/phiếu | Bảng metrics + phân tích FP/FN/nhầm lớp trong `Results/` hoặc docs kèm dẫn chứng |
| 7 | **Đồng bộ trạng thái Spec 001**: cập nhật `tasks.md` theo thực tế, bổ sung test còn thiếu (validator/splitter/US2-US3) nếu chưa đạt contract | Tránh “done ngoài giấy tờ” và rủi ro thiếu hành vi (quarantine/report lifecycle/split) | Tasks đánh dấu đúng, pytest coverage nhóm test theo plan |
| 8 | **Làm rõ/khôi phục nội dung `define_and_design_v2.ipynb` và liên kết sơ đồ** | Notebook hiện khó dùng làm bằng chứng thiết kế chi tiết | Notebook có nội dung/diagram rõ, trích `*.mmd` nhất quán với `assets/define-design/` |
| 9 | **Chuẩn hóa môi trường chạy** (ghi rõ dùng `.venv`, Python version, cách cài `pytest`/deps, dọn artifact không cần commit nếu phù hợp quy ước nhóm) | Đảm bảo tái lập khi người khác/CI chạy | README/quickstart cập nhật; `pytest` chạy theo hướng dẫn |
| 10 | **Theo dõi/chuẩn bị tích hợp liên nhóm** (format output, đường dẫn model, demo set 60 ảnh) khi 002 có checkpoint | TV5/TV6 cần checkpoint + code predict + hướng dẫn; hiện chưa có | Contract bàn giao (file weights, schema dự đoán, ví dụ chạy) |

## 6. Câu hỏi cần tôi xác nhận lại

1. **Phiếu nào là bản “chốt” để nộp/đối chiếu?** `phieu_dang_ky_de_tai_1_trang.*`, `phieu_dang_ky_de_tai_rut_gon.*`, hay một bản đầy đủ (`phieu_dang_ky_de_tai.md/.docx`) đang lưu ở nơi khác?
2. **Bản đầy đủ `Research/phieu_dang_ky_de_tai.md/.docx`** từng tồn tại trong repo không? Nếu có, có cần khôi phục không hay `build_docx.py` nên bỏ job tương ứng?
3. **Quy ước split NEU-DET chính thức** cho module Detection là gì (giữ `train/validation` gốc, hay tái chia 75/15/10/seed 42 như spec 001, hay phương án trong phiếu 1 trang/rút gọn)? Tập nào dùng làm test cuối cùng và có “đụng” vào test khi chọn checkpoint không?
4. **`define_and_design_v2.ipynb`**: bản hiện tại (3 cell) có phải là bản thiết kế đầy đủ không, hay file đầy đủ nằm nơi khác/cần khôi phục?
5. File **XML thừa trong `NEU-DET/NEU-DET/validation/annotations`** (so với số ảnh) có phải vấn đề đã biết cần cách ly/báo cáo không?
6. Mức ưu tiên hiện tại: hoàn thiện **Feature 001 (data-prep + artifact + đồng bộ tasks/tests)** trước, hay chuyển sang **Feature 002 (train/eval/infer YOLOv8s)** song song?
7. Có yêu cầu commit/dọn `.venv`, `__pycache__`, `.pytest_cache`, `*.egg-info` khỏi repo hay giữ nguyên trạng phục vụ rà soát không? (Câu hỏi để xác nhận quy ước; báo cáo này không thực hiện thay đổi.)

---
*Báo cáo được lập dựa trên đọc file/thư mục và kết quả lệnh kiểm tra không phá hủy (`find/ls/cat/wc/python3` trích xuất thông tin, chạy `pytest` trong `yolov8-detection/.venv`).*
