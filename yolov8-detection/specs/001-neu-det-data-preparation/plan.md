# Implementation Plan: Chuẩn bị dữ liệu NEU-DET cho Object Detection

**Branch**: `001-neu-det-data-preparation` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-neu-det-data-preparation/spec.md`

**Revision**: 2026-11-14 — rà soát và bổ sung: phát hiện ảnh/XML không khớp trong từng
subset nguồn, cấm ghép chéo train/validation, chia 75/15/10 phân tầng đa nhãn, CLI nhận
đường dẫn nguồn/đầu ra tùy ý, cố định class mapping và mở rộng ma trận kiểm thử.

**Revision (US2 contract refinement)**: 2026-11-15 — đồng bộ accounting `unwritten_samples`,
layout `rejected/` mirror nguồn, duplicate audit theo từng member, gate counters, vòng đời report,
fingerprint status, overwrite staging/commit an toàn, quarantine unpaired/all-quarantined và
`filename_mismatch`.

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

Xây dựng một pipeline dòng lệnh độc lập để biến bộ NEU-DET gốc (annotation Pascal VOC XML)
thành bộ dữ liệu Object Detection sẵn sàng cho YOLOv8s. Pipeline đọc dataset từ bất kỳ đường
dẫn nào do người dùng truyền vào, ghi kết quả vào một thư mục đầu ra riêng, và không bao giờ
sửa, di chuyển hay xóa dữ liệu gốc.

Phạm vi xử lý:

1. Ghép ảnh với XML **chỉ trong cùng một subset nguồn** (`train` với `train`, `validation`
   với `validation`). Ảnh thiếu XML và XML thiếu ảnh được ghi nhận là bất thường, không tự
   ghép với file cùng tên ở subset khác.
2. Chuyển annotation VOC sang nhãn YOLO, kiểm tra class mapping cố định và mọi bounding box.
3. Ghi toàn bộ bất thường, accounting và fingerprint vào `validation_report.json` trước khi quyết
   định dừng hay quarantine; cập nhật report lần cuối sau verify và commit an toàn khi
   `--overwrite`.
4. Chia dữ liệu thành train/validation/test theo tỷ lệ **75/15/10**, phân tầng theo **tập tất cả
   các lớp xuất hiện trong từng ảnh** (multi-label), seed cố định, chống trùng ảnh giữa các split.
5. Ghi `split_manifest.json` mô tả đầy đủ split, lớp, nguồn và cấu hình để tái lập.

Cách tiếp cận kỹ thuật: package Python `detection` (src layout) với CLI `detection prepare`,
dùng thư viện chuẩn cho XML/JSON/hash/stratification, Pillow để xác thực ảnh, và pytest cho
kiểm thử. Mọi quyết định thiết kế được ghi ở [research.md](./research.md), [data-model.md](./data-model.md),
[contracts/cli.md](./contracts/cli.md), [contracts/artifact-formats.md](./contracts/artifact-formats.md)
và [quickstart.md](./quickstart.md).

## Yêu cầu cập nhật và quyết định thiết kế

| # | Yêu cầu bổ sung | Quyết định | Nơi ghi chi tiết |
|---|-----------------|------------|------------------|
| 1 | Phát hiện ảnh thiếu XML, XML thiếu ảnh; không ghép chéo train/validation; không sửa/xóa dữ liệu gốc; ghi nhận vào `validation_report.json` | Ghép cặp theo exact stem trong từng subset nguồn; không dùng `<filename>` hay tên file để ghép chéo; mọi cặp thiếu được ghi anomaly `missing_xml` / `missing_image`; nguồn chỉ đọc và được fingerprint trước/sau chạy | Mục *Data Integrity Rules*, [research.md](./research.md) R-002/R-006/R-011/R-013/R-015, [data-model.md](./data-model.md), [contracts/artifact-formats.md](./contracts/artifact-formats.md) |
| 2 | Chia 75/15/10, stratified theo các lớp xuất hiện trong từng ảnh, không trùng ảnh giữa các tập, seed cố định | Multi-label iterative stratification trên `present_classes`; kích thước split chốt bằng largest-remainder; seed mặc định 42; ảnh trùng nội dung được gom nhóm và gán nguyên tử vào một split | Mục *Split Strategy*, [research.md](./research.md) R-007/R-009/R-013, [data-model.md](./data-model.md) |
| 3 | CLI nhận đường dẫn dataset nguồn và thư mục đầu ra; không bắt buộc đặt dataset trong `data/raw` | `--source PATH` bắt buộc, chấp nhận mọi vị trí; `--output PATH` mặc định `data/processed/neu-det`; output không được nằm trong source | [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md) |
| 4 | Cố định class mapping 0–5 | Một hằng số duy nhất: `0=crazing, 1=inclusion, 2=patches, 3=pitted_surface, 4=rolled-in_scale, 5=scratches`; ghi vào manifest và báo cáo; không remap tự động | [research.md](./research.md) R-005, [data-model.md](./data-model.md), [contracts/artifact-formats.md](./contracts/artifact-formats.md) |
| 5 | Bổ sung kiểm thử cho ảnh thiếu XML, XML thiếu ảnh, bbox không hợp lệ, nhiều đối tượng trong ảnh, ảnh trùng giữa các split | Ma trận kiểm thử bắt buộc, dùng fixture VOC tổng hợp trong `tmp_path`; thêm test chống ghép chéo và test nguồn bất biến | Mục *Testing Strategy*, [research.md](./research.md) R-010 |
| 6 | Accounting phải giải thích mọi ảnh nguồn | Thêm `unwritten_samples`; `accounted_images = written + quarantined + unwritten + unpaired_images`; `accounting_ok` là điều kiện trước khi ghi output | [research.md](./research.md) R-016, [data-model.md](./data-model.md) §5.2, [contracts/artifact-formats.md](./contracts/artifact-formats.md) §3 |
| 7 | Rejected phải giữ nguyên dữ liệu gốc để điều tra | Mirror `rejected/images/<subset>/<relative-path>` và `rejected/annotations/<subset>/<relative-path>`, dùng `shutil.copy2`, chỉ sample paired lỗi, không nhãn YOLO, không đụng nguồn | [research.md](./research.md) R-017, [data-model.md](./data-model.md) §10, [contracts/artifact-formats.md](./contracts/artifact-formats.md) §1 |
| 8 | Duplicate conflict phải xử lý nguyên tử và giải thích được | Một `duplicate_content` cho mỗi member với `group_id`/`sha256`/`member_count`/`labels_consistent`; warning nếu multiset nhãn khớp, error + quarantine toàn nhóm nếu xung đột; `DuplicateGroup` chỉ trong bộ nhớ | [research.md](./research.md) R-013, [data-model.md](./data-model.md) §4.4 |
| 9 | Report phải phản ánh cả run thất bại và fingerprint | First write sau validate/gate trước khi ghi dataset; final update sau verify; fingerprint status `verified_unchanged`/`changed`/`unavailable`; report-write failure exit `5` | [research.md](./research.md) R-006/R-015/R-018, [contracts/artifact-formats.md](./contracts/artifact-formats.md) §3.5/§5 |
| 10 | `--overwrite` không được phá dataset cũ trước khi validate | Staging `<output>.staging`, backup `<output>.previous`, commit sau report/verify; failure output report-only hoặc report + `rejected/` khi all-quarantined; retry theo exit `4`/`--overwrite` | [contracts/cli.md](./contracts/cli.md) §6, [quickstart.md](./quickstart.md) §4.4 |

## Technical Context

**Language/Version**: Python 3.11+ (môi trường phát triển hiện tại: Python 3.14.9)

**Primary Dependencies**: Pillow (xác thực ảnh); thư viện chuẩn `xml.etree.ElementTree`, `json`,
`hashlib`, `argparse`, `random`, `pathlib`, `shutil`. Kiểm thử: pytest (dev dependency).
Không thêm dependency cho stratification hay phát hiện trùng ảnh.

**Storage**: Hệ thống tệp cục bộ — ảnh nguồn chỉ đọc; ảnh đầu ra được **copy** sang thư mục đã
xử lý (không hard link, không symlink để tránh mọi khả năng ghi ngược vào nguồn); nhãn YOLO dạng
text; manifest và báo cáo dạng JSON.

**Testing**: pytest (unit + integration), dùng `tmp_path` và mẫu VOC tổng hợp nhỏ. Không commit
ảnh mẫu và không chạy test trên dataset thật.

**Target Platform**: Linux (máy phát triển của nhóm), CLI không giao diện, không cần GPU.

**Project Type**: Single project — CLI data pipeline trong package `src/detection`.

**Performance Goals**: Xử lý toàn bộ NEU-DET (khoảng 1.800 ảnh) trong dưới 10 phút trên máy
phát triển tiêu chuẩn, bao gồm fingerprint nguồn và copy ảnh.

**Constraints**:

- Dữ liệu gốc bất biến tuyệt đối: chỉ mở để đọc; không ghi, đổi tên, di chuyển hay xóa.
- Không tự động sửa XML, không clip bounding box, không tự gán lớp, không tự ghép cặp khác
  subset nguồn.
- Không tự động loại bỏ mẫu im lặng; mọi mẫu không tham gia split phải có anomaly record.
- Split tất định theo seed; cùng dữ liệu + cấu hình + seed cho cùng phân bổ.
- Không phụ thuộc mạng; không thay đổi kiến trúc YOLOv8s; không triển khai Segmentation.
- Không huấn luyện, không đánh giá và không suy luận trong feature này.

**Scale/Scope**: Khoảng 1.800 ảnh, 6 lớp lỗi, 1–2 đối tượng mỗi ảnh; nguồn thường có hai subset
`train` và `validation`. Đầu ra khoảng 1.800 ảnh + 1.800 tệp nhãn + manifest + báo cáo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Nguyên tắc Constitution | Cổng kiểm tra | Kết quả |
|---|-------------------------|---------------|---------|
| I | Phạm vi Detection-Only | Chỉ xử lý dữ liệu cho Object Detection; không Segmentation/U-Net; không đổi YOLOv8s | PASS |
| II | Toàn vẹn dữ liệu | Nguồn chỉ đọc và có fingerprint; đầu ra ở thư mục riêng; ghép cặp trong từng subset; kiểm tra class/bbox; mọi loại bỏ có ghi nhận trong `validation_report.json` | PASS |
| III | Kiểm soát mô hình & cấu hình | Không huấn luyện; thứ tự 6 lớp cố định; seed, tỷ lệ split, class mapping và thuật toán phân tầng được ghi vào manifest | PASS |
| IV | Đánh giá trung thực | Test split được tạo và cô lập ngay từ khâu dữ liệu; kiểm tra disjoint theo sample, tên tệp và nội dung ảnh; manifest ghi rõ split | PASS |
| V | Tái lập | Seed cố định, thứ tự duyệt ổn định, tie-break tất định, manifest kèm cấu hình và fingerprint nguồn | PASS |
| VI | Chất lượng mã & cộng tác | Cấu trúc module rõ ràng, có test cho từng loại bất thường, không tạo thư mục thừa, không sửa file module khác | PASS |

Không có vi phạm cần biện minh. Chi tiết cách đáp ứng từng cổng nằm trong
[research.md](./research.md) và [data-model.md](./data-model.md).

## Data Integrity Rules

Các quy tắc sau là bất biến của pipeline và phải được kiểm thử:

- **DIR-01 — Nguồn chỉ đọc**: Pipeline không mở bất kỳ tệp nguồn nào ở chế độ ghi. Không tạo,
  sửa, đổi tên, di chuyển hay xóa tệp trong cây thư mục nguồn. Ảnh đầu ra là bản copy.
- **DIR-02 — Phạm vi ghép cặp**: Một ảnh chỉ được ghép với XML có cùng stem trong **cùng một
  subset nguồn**. Không ghép `train/images/a.jpg` với `validation/annotations/a.xml`, kể cả khi
  stem trùng. Không dùng trường `<filename>` trong XML để đổi cặp.
- **DIR-03 — Không tự sửa**: Không clip bbox, không đổi tọa độ, không đổi tên lớp, không tạo
  XML còn thiếu, không tạo ảnh còn thiếu.
- **DIR-04 — Báo cáo đầy đủ**: Mọi bất thường phát hiện trong quá trình discover/pair/validate/
  duplicate audit/verify phải có bản ghi trong `validation_report.json` với mã lỗi, mức độ,
  đường dẫn liên quan (nếu có) và lý do. Báo cáo được ghi cả khi pipeline dừng vì lỗi dữ liệu.
- **DIR-05 — Đầu ra tách biệt**: Thư mục output không được trùng, nằm bên trong, hoặc là thư mục
  cha của thư mục nguồn. Nếu vi phạm, CLI dừng trước khi ghi bất kỳ tệp nào.
- **DIR-06 — Đơn vị nguyên tử**: Sau khi ghép, một cặp ảnh + XML là một sample không thể tách
  rời. Khi chia split và khi ghi output, ảnh và nhãn của cùng sample luôn đi cùng nhau.
- **DIR-07 — Accounting đầy đủ**: `written_samples + quarantined_samples + unwritten_samples +
  unpaired_images == source_images`; mỗi ảnh nguồn được đếm đúng một lần. Nếu sai, dừng trước
  khi ghi output.
- **DIR-08 — Rejected là bản copy trung thực**: Chỉ sample paired lỗi trong chế độ `quarantine`
  được copy vào `rejected/` theo đúng subset và đường dẫn tương đối; dùng `shutil.copy2`; không
  tạo nhãn YOLO; không move/delete nguồn. Unpaired asset chỉ được báo trong report.
- **DIR-09 — Report nguyên tử và đúng vòng đời**: Report được ghi lần đầu sau validate/gate
  trước khi ghi dataset, cập nhật lần cuối sau verify, và cập nhật khi source/verify lỗi nếu còn
  ghi được. Không ghi được report là exit `5`.
- **DIR-10 — Overwrite an toàn**: Không xóa dataset cũ trước khi run mới qua validate/gate. Dùng
  staging/backup và commit sau report/verify; failure output không được giả làm dataset hợp lệ.
- **DIR-11 — Fingerprint trung thực**: Chỉ `status = changed` khi fingerprint thực sự khác;
  lỗi I/O là `unavailable`, không được tạo `source_tree_changed` giả.

## Processing Pipeline

| Bước | Đầu vào | Xử lý | Đầu ra / thất bại |
|------|---------|-------|-------------------|
| 1. Discover | `--source` | Xác định các subset (`train`, `validation`, hoặc single-subset), liệt kê ảnh và XML theo thứ tự sắp xếp; kiểm tra cấu trúc tối thiểu | Danh sách `ImageAsset`, `AnnotationAsset`; lỗi cấu trúc → exit code cấu hình, không ghi output |
| 2. Pair | Danh sách asset | Ghép exact stem **trong từng subset**; phát hiện stem trùng/không rõ, ảnh thiếu XML, XML thiếu ảnh | `MatchedSample` hoặc anomaly `missing_xml` / `missing_image` / `ambiguous_pairing` |
| 3. Validate + convert | `MatchedSample` | Orchestrator tái sử dụng `verify_image()` và `convert_annotation()`; kiểm tra XML/class/bbox/ảnh, so `<size>` và `<filename>`, tính `present_classes`, tạo nhãn YOLO trong bộ nhớ | Sample hợp lệ + label; anomaly `invalid_xml`, `unknown_class`, `invalid_bbox`, `corrupt_image`, `size_mismatch`, `filename_mismatch`… |
| 4. Duplicate audit | Toàn bộ sample eligible | Gom nhóm theo SHA-256; so multiset `(class_id, cx, cy, w, h)`; mỗi member nhận một `duplicate_content` với metadata nhóm | `DuplicateGroup` trong bộ nhớ; warning nếu nhất quán, error nếu xung đột |
| 5. Fingerprint sau validate | Nguồn | Tính lại fingerprint kể cả khi gate sẽ fail; phân biệt unchanged/changed/unavailable | Trạng thái fingerprint cho report; không coi lỗi I/O là changed |
| 6. Gate + first report + staging | Anomaly + cấu hình | Áp dụng `--on-anomaly`; tạo staging; ghi report lần đầu trước khi ghi dataset; `fail` dừng, `quarantine` loại sample paired lỗi và copy sang `rejected/` | `validation_report.json` trong staging; exit `3`/`5` khi dừng, ngược lại tiếp tục |
| 7. Split | Sample eligible | Chia 75/15/10 multi-label, group-aware, seed cố định; kiểm tra disjoint, phủ đầy và accounting | Phân bổ split + thống kê |
| 8. Write | Phân bổ split | Copy ảnh, ghi nhãn YOLO; copy rejected theo layout nguồn trong quarantine mode | `images/`, `labels/`, `rejected/` trong staging |
| 9. Verify + final report | Output + source | Kiểm tra disjoint, đếm file, accounting, recheck fingerprint; cập nhật report lần cuối; chỉ khi mọi bất biến đạt mới ghi manifest | Report cuối + `split_manifest.json`; lỗi → exit 3/5, không commit dataset |
| 10. Commit | Staging + output cũ | Chỉ commit sau report/verify; backup output cũ khi cần; dọn backup sau thành công | Output mới; failure output report-only hoặc report + `rejected/` |

## Split Strategy

- **Pool chia**: Gồm các `MatchedSample` đã ghép đúng trong từng subset nguồn. Khi chia lại
  75/15/10, mỗi sample được xem là đơn vị nguyên tử (ảnh + XML đi cùng nhau); đây không phải
  ghép ảnh–XML xuyên subset.
- **Tỷ lệ mặc định**: 75% train / 15% validation / 10% test. Với **1.800 sample hợp lệ**, mục tiêu
  largest-remainder là **1350 / 270 / 180** ảnh. Trên bộ NEU-DET thực tế, sau khi quarantine
  `patches_101` và `patches_105` còn **1.798 sample hợp lệ**, kết quả largest-remainder 75/15/10
  là **1348 / 270 / 180**. Tỷ lệ có thể truyền qua CLI nhưng phải dương, tổng bằng 1.0 và được ghi
  lại trong manifest. Giá trị dùng để báo cáo là giá trị thực tế sau khi chia.
- **Đơn vị phân tầng**: Mỗi ảnh được biểu diễn bằng `present_classes` — tập **tất cả** class ID
  xuất hiện trong ảnh, không phải chỉ lớp của đối tượng đầu tiên. Ảnh nhiều đối tượng thuộc
  nhiều lớp đóng góp vào thống kê của tất cả các lớp đó.
- **Ảnh không có object**: `present_classes = []`; ảnh vẫn là sample hợp lệ, được phân bổ theo
  phần dung lượng còn lại của từng split với tie-break tất định, và được ghi nhận
  `empty_annotation`. Không loại ảnh này khỏi split.
- **Kích thước split**: Dùng largest-remainder để chốt số ảnh mỗi split sao cho tổng bằng đúng
  số sample hợp lệ; tie-break theo thứ tự `train`, `validation`, `test`.
- **Nhóm trùng nguyên tử**: Nếu một `DuplicateGroup` quá lớn khiến không thể đạt đúng mục tiêu
  mà vẫn giữ toàn nhóm trong một split, ưu tiên tính nguyên tử (không tách nhóm), ghi warning
  `split_distribution_deviation` và ghi tỷ lệ thực tế vào manifest. Với NEU-DET thông thường
  (nhóm trùng nhỏ), tỷ lệ 75/15/10 vẫn đạt chính xác theo largest-remainder.
- **Thuật toán**: Multi-label iterative stratification, ưu tiên lớp hiếm trước, sau đó là
  tie-break bằng `random.Random(seed)` cục bộ và `sample_id` đã sắp xếp. Không dùng trạng thái
  ngẫu nhiên toàn cục.
- **Chống rò rỉ**:
  - Mỗi `sample_id` chỉ thuộc đúng một split.
  - Mỗi output path chỉ thuộc đúng một split.
  - Các ảnh có cùng SHA-256 được gom thành một `DuplicateGroup`; toàn bộ nhóm được gán vào cùng
    một split. Nếu các bản trùng có nhãn xung đột, nhóm bị coi là lỗi chặn.
  - Kiểm tra sau chia: giao của mọi cặp split theo `sample_id`, `output_image`, `sha256` phải rỗng.
- **Tất định**: Cùng dataset, cùng cấu hình và cùng seed phải cho danh sách sample trong từng
  split giống hệt. Timestamp chỉ nằm ở metadata, không tham gia quyết định split.
- **Lớp hiếm**: Nếu một lớp không xuất hiện trong một split, ghi warning `split_class_absent`
  kèm số lượng; không tự ý chuyển sample ra ngoài thuật toán.

## Project Structure

### Documentation (this feature)

```text
specs/001-neu-det-data-preparation/
├── plan.md                       # This file
├── research.md                   # Phase 0 output
├── data-model.md                 # Phase 1 output
├── quickstart.md                 # Phase 1 output
├── contracts/
│   ├── cli.md                    # Giao diện dòng lệnh
│   └── artifact-formats.md       # Định dạng manifest, báo cáo, nhãn YOLO
├── checklists/
│   └── requirements.md           # Spec quality checklist
└── tasks.md                      # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
pyproject.toml                    # Metadata, dependency, entry point `detection`

src/
└── detection/
    ├── __init__.py
    ├── cli.py                    # Parse lệnh `prepare`, ánh xạ exit code
    └── data/
        ├── __init__.py
        ├── classes.py            # Danh sách 6 lớp cố định + chuẩn hóa tên lớp
        ├── discovery.py          # Phát hiện subset, ảnh, XML; giới hạn phạm vi ghép cặp
        ├── converter.py          # VOC XML -> nhãn YOLO (class_id cx cy w h)
        ├── validator.py          # Kiểm tra ảnh, cặp ảnh–nhãn, class, bbox, anomaly
        ├── splitter.py           # Multi-label stratified split, group-aware, tất định
        ├── manifest.py           # Ghi validation_report.json + split_manifest.json
        └── pipeline.py           # Điều phối discover -> pair -> validate -> split -> write

tests/
├── unit/
│   ├── test_classes.py           # Class mapping cố định, chuẩn hóa tên
│   ├── test_converter.py         # Nhiều object, nhãn rỗng, định dạng số
│   ├── test_validator.py         # Thiếu XML/ảnh, bbox lỗi, XML hỏng, ảnh hỏng
│   ├── test_splitter.py          # 75/15/10, multi-label, trùng ảnh, tái lập
│   └── test_manifest.py          # Schema report/manifest, gate, exit code
└── integration/
    └── test_prepare_dataset.py   # CLI end-to-end, source/output tùy ý, nguồn bất biến
```

### Runtime data layout

```text
<source>/                         # Bất kỳ vị trí nào; chỉ đọc; KHÔNG bắt buộc nằm trong data/raw
├── train/
│   ├── images/
│   └── annotations/
└── validation/
    ├── images/
    └── annotations/

<output>/                         # Bất kỳ vị trí nào, không nằm trong <source>
├── images/{train,validation,test}/
├── labels/{train,validation,test}/
├── rejected/                     # Chỉ có khi --on-anomaly quarantine
│   ├── images/<source_subset>/<relative-path>
│   └── annotations/<source_subset>/<relative-path>
├── validation_report.json
└── split_manifest.json

<output>.staging/                 # Artifact tạm trong lúc chạy/commit; không thuộc contract
<output>.previous/                # Dataset cũ được giữ tới khi commit thành công
```

Khi run thất bại sau khi đã có staging (fail mode, source change, verify failure, split invariant
hoặc all-quarantined), output chỉ chứa `validation_report.json`; riêng all-quarantined có thêm
`rejected/`. Không có `images/`, `labels/` hay manifest; dataset cũ nếu có nằm ở
`<output>.previous`.

Không tạo `configs/` cho feature này: cấu hình xử lý nằm trong tham số CLI và được ghi lại
trong manifest. `dataset.yaml` cho YOLOv8s thuộc feature `002-yolov8s-detection-pipeline`.

**Structure Decision**: Chọn single project với package `src/detection`, vì module chỉ có một
CLI nội bộ và không cần backend/frontend. `data/` chỉ là vị trí mặc định gợi ý cho output,
không phải nơi bắt buộc chứa dataset gốc. Các bước xử lý được tách thành module nhỏ
(`discovery`, `converter`, `validator`, `splitter`, `manifest`) để tránh trùng lặp và dễ kiểm thử.

## CLI Contract Summary

Chi tiết đầy đủ ở [contracts/cli.md](./contracts/cli.md). Tóm tắt:

| Tham số | Mặc định | Ý nghĩa |
|---------|----------|---------|
| `--source PATH` | Bắt buộc | Thư mục dataset nguồn; có thể ở bất kỳ đâu |
| `--output PATH` | `data/processed/neu-det` | Thư mục đầu ra; phải tách biệt khỏi nguồn |
| `--seed INT` | `42` | Seed cố định cho phân bổ split |
| `--ratios T,V,TE` | `0.75,0.15,0.10` | Tỷ lệ train/validation/test |
| `--on-anomaly {fail,quarantine}` | `fail` | Dừng khi có lỗi hoặc loại mẫu lỗi khỏi split |
| `--overwrite` | Tắt | Thay thế an toàn output đã tồn tại qua staging/backup; không phá dataset cũ trước validate |

Exit code: `0` thành công (`pass`/`pass_with_quarantine`), `2` lỗi cấu trúc/cấu hình, `3` lỗi dữ
liệu chặn/all-quarantined/source changed, `4` output đã tồn tại mà không có `--overwrite`, `5`
lỗi I/O bao gồm không ghi được report và fingerprint `unavailable`.

## Testing Strategy

Tất cả test dùng fixture VOC tổng hợp trong `tmp_path`, không phụ thuộc dataset thật.

| ID | Kịch bản | Kỳ vọng |
|----|----------|---------|
| T-01 | Ảnh có trong `train/images` nhưng không có XML cùng subset | `validation_report.json` có `missing_xml`; ảnh không vào split; nguồn không đổi |
| T-02 | XML có trong `validation/annotations` nhưng không có ảnh cùng subset | Report có `missing_image`; XML không vào split; nguồn không đổi |
| T-03 | `train/images/a.jpg` và `validation/annotations/a.xml` cùng stem | **Không** tạo sample; report có `missing_xml` cho ảnh và `missing_image` cho XML; nguồn không đổi |
| T-04 | Bbox có `xmin >= xmax`, `ymin >= ymax`, tọa độ âm, vượt biên, không phải số hoặc quá nhỏ để làm tròn thành 0 | Mỗi trường hợp là `invalid_bbox`; không clip, không sửa, không sinh nhãn |
| T-05 | Một ảnh có nhiều object thuộc nhiều lớp | Nhãn có đủ số dòng; `present_classes` chứa tất cả lớp; `image_counts_by_class` đếm ảnh một lần, `object_counts_by_class` đếm đủ object |
| T-06 | Hai ảnh cùng nội dung ở hai subset nguồn, nhãn nhất quán | Cùng một `DuplicateGroup`; cả hai vào **cùng** một split; không có SHA-256 xuất hiện ở hai split |
| T-07 | Hai ảnh cùng nội dung nhưng nhãn xung đột | `duplicate_content` mức error; gate fail hoặc quarantine toàn nhóm |
| T-08 | Chạy split với 75/15/10 và seed cố định hai lần trên dataset không có nhóm trùng chặn tỷ lệ | Danh sách sample từng split giống hệt; tổng đúng; với 1.800 sample hợp lệ đạt 1350/270/180 (NEU-DET thực tế: 1.798 sample sau quarantine `patches_101`/`patches_105` → 1348/270/180) |
| T-09 | Kiểm tra giao các split | Giao theo `sample_id`, `output_image`, `sha256` đều rỗng |
| T-10 | Chạy CLI với source/output ngoài `data/raw` | Thành công; manifest ghi đúng đường dẫn tuyệt đối/relative đã dùng |
| T-11 | Hash toàn bộ cây nguồn trước và sau khi chạy | Hash giống hệt; không có tệp mới/đổi tên/xóa trong nguồn |
| T-12 | Output đã tồn tại, không có `--overwrite` | Exit code 4; không ghi đè |
| T-13 | Output nằm trong source | Exit code 2; không ghi gì vào nguồn |
| T-14 | Class name sai hoa/thường hoặc có khoảng trắng thừa | Chuẩn hóa `strip().lower()` rồi map đúng; tên lạ vẫn là `unknown_class` |
| T-15 | Dataset có ảnh thiếu XML, XML thiếu ảnh và một sample lỗi bbox, chạy với `--on-anomaly quarantine` | `written + quarantined + unwritten + unpaired_images == source_images`; `accounting_ok = true`; rejected mirror đúng subset/path; unpaired không bị copy |
| T-16 | Duplicate content nhãn nhất quán | Mỗi member có `duplicate_content` warning với `group_id`, `sha256`, `member_count`, `labels_consistent = true`; nhóm được giữ |
| T-17 | Duplicate content nhãn xung đột | Mỗi member có error; fail mode exit `3`; quarantine mode copy toàn nhóm sang `rejected/`; accounting đủ |
| T-18 | `<filename>` khác basename ảnh nhưng stem vẫn ghép đúng | Warning `filename_mismatch`; cặp ảnh–XML không đổi; `paths` có cả ảnh và XML |
| T-19 | XML `<size>` khác kích thước thật | Warning `size_mismatch` do validator orchestration tạo; `paths` có cả ảnh và XML; kích thước thật dùng để chuẩn hóa |
| T-20 | Quarantine chỉ còn unpaired error, vẫn còn sample paired eligible | Gate `pass_with_quarantine`, exit `0`, `blocking_errors > 0`; unpaired không nằm trong `rejected/` |
| T-21 | Quarantine loại toàn bộ sample paired | Gate `fail`, exit `3`; output có report + `rejected/`, không có `images/`/`labels/`/manifest; `accounting_ok = true` |
| T-22 | `--overwrite` với run mới fail validation/gate | Dataset cũ không bị xóa; output report-only; retry không `--overwrite` exit `4`; retry có `--overwrite` thay report an toàn |
| T-23 | Report first write/final update và report-write failure | Report tồn tại sau validate trước khi có ảnh/nhãn; final update phản ánh written/quarantined/fingerprint; lỗi ghi report exit `5`, không ghi manifest |
| T-24 | Fingerprint nguồn changed vs unavailable | `changed` tạo `source_tree_changed` error, exit `3`; `unavailable` không tạo anomaly giả, gate fail, exit `5`; `verified_after_run` chỉ true khi unchanged |
| T-25 | Thứ tự anomaly có nhiều record cùng code/paths | Ổn định theo `code`, `paths`, `sample_id` (null cuối), object index, `reason` |

## Implementation Phases

| Phase | Nội dung | Trạng thái |
|-------|----------|------------|
| 0 | Research: chốt parser, pairing scope, anomaly taxonomy, split algorithm, artifact formats | Hoàn tất trong [research.md](./research.md) |
| 1 | Design: data model, CLI contract, artifact contract, quickstart | Hoàn tất trong tài liệu này và các tệp liên quan |
| 2 | Tasks: chia nhỏ công việc theo module/test | Chờ `/speckit.tasks` |
| 3 | Implement: code pipeline + test | **Không thực hiện trong lần cập nhật này** |
| 4 | Verify: chạy test, kiểm tra nguồn bất biến, đối chiếu manifest | **Không thực hiện trong lần cập nhật này** |

## Risks and Mitigations

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|--------|-----------|------------|
| Dataset nguồn có cấu trúc khác giả định | Không discover được hoặc bỏ sót file | Contract discovery rõ ràng; lỗi cấu trúc dừng sớm; report ghi đường dẫn |
| Ảnh/XML thiếu cặp do lỗi copy dữ liệu | Mất mẫu hoặc rò rỉ nếu ghép bừa | Chỉ ghép trong subset; anomaly bắt buộc; không tự sửa |
| Nhãn đa lớp hiếm khiến split lệch | Đánh giá thiếu công bằng | Iterative stratification ưu tiên lớp hiếm; warning `split_class_absent`; manifest ghi phân bố thật |
| Ảnh trùng nội dung nhưng khác nhãn | Rò rỉ hoặc nhãn sai | SHA-256 grouping; xung đột nhãn là error chặn |
| Trùng tên file giữa các subset | Ghi đè output | Tên output deterministic, có prefix subset/hash khi cần; manifest ánh xạ rõ |
| Nguồn bị thay đổi bởi tiến trình khác | Kết quả không tái lập | Fingerprint trước/sau; `changed` là error, `unavailable` là I/O failure, không đánh đồng |
| Copy ảnh làm chậm hoặc tốn dung lượng | Vượt mục tiêu 10 phút | Copy tuần tự, không xử lý pixel; 1.800 ảnh nằm trong ngưỡng |
| Output đã tồn tại từ lần chạy trước | Ghi đè nhầm hoặc mất dataset cũ | Mặc định từ chối; `--overwrite` dùng staging/backup, chỉ commit sau validate/report/verify |
| Report-only failure bị nhầm là dataset | Feature 002 dùng dữ liệu thiếu | Chỉ output có manifest + gate pass/pass_with_quarantine mới hợp lệ; contract ghi rõ |
| Duplicate group xung đột bị xử lý nửa vời | Rò rỉ hoặc mất mẫu | Một anomaly/member, quarantine toàn nhóm, accounting từng member |
| Report ghi lỗi giữa chừng | Kết quả không giải thích được | Atomic write; report-write failure exit `5`, không commit/manifest |

## Documentation Sync

Cập nhật 2026-11-14 đã đồng bộ toàn bộ tài liệu Feature 001 theo quyết định kỹ thuật cuối cùng:
tỷ lệ split mặc định là **75/15/10** (train/validation/test), seed mặc định là **42**, với
**1.800 sample hợp lệ** mục tiêu largest-remainder tương ứng **1350/270/180**. Trên bộ NEU-DET
thực tế, sau khi quarantine `patches_101` và `patches_105` còn **1.798 sample hợp lệ** nên kết
quả largest-remainder 75/15/10 là **1348/270/180**. Cách phân tầng là multi-label theo tất cả
lớp xuất hiện trong từng ảnh; ảnh trùng nội dung được gom nhóm nguyên tử và không tách giữa các
split. `spec.md`, `checklists/requirements.md`, `plan.md`, `research.md`, `data-model.md`,
`quickstart.md` và các contract trong `contracts/` đã được rà soát và thống nhất theo cùng một
cấu hình split, không còn tài liệu nào ghi tỷ lệ cũ.

Cập nhật 2026-11-15 đồng bộ US2: accounting có `unwritten_samples`; rejected mirror nguồn và chỉ
sample paired; duplicate audit một anomaly/member với metadata nhóm; gate counters theo severity;
report first write/final update; fingerprint status ba trạng thái; overwrite staging/backup và
retry; quarantine unpaired/all-quarantined; `filename_mismatch`; deterministic anomaly ordering.
`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli.md`,
`contracts/artifact-formats.md`, `quickstart.md` và `tasks.md` được cập nhật cùng lúc.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Không có vi phạm. Không cần biện minh thêm.
