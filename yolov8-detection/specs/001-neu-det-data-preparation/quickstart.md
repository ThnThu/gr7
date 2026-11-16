# Quickstart: Chuẩn bị dữ liệu NEU-DET

**Feature**: `001-neu-det-data-preparation` | **Date**: 2026-11-14

Hướng dẫn này mô tả cách chạy pipeline sau khi feature được implement. Feature này **chỉ**
chuẩn bị dữ liệu; không huấn luyện, không đánh giá và không chạy YOLOv8s.

## 1. Yêu cầu

- Python 3.11+
- Pillow
- pytest (chỉ cho kiểm thử)
- Dataset NEU-DET gốc ở bất kỳ đường dẫn nào, ví dụ:
  - `/mnt/datasets/NEU-DET`
  - `/home/<user>/datasets/NEU-DET`
  - `data/raw/NEU-DET` (không bắt buộc)

Không cần di chuyển dataset vào `data/raw`, không cần GPU, không cần mạng.

## 2. Cài đặt

Từ thư mục gốc repo:

```bash
pip install -e .
```

Sau khi cài, lệnh `detection` có sẵn trong môi trường.

## 3. Kiểm tra cấu trúc dataset

### 3.1 NEU-DET có hai subset

```text
/mnt/datasets/NEU-DET/
├── train/
│   ├── images/
│   │   ├── crazing_0001.jpg
│   │   └── ...
│   └── annotations/
│       ├── crazing_0001.xml
│       └── ...
└── validation/
    ├── images/
    └── annotations/
```

### 3.2 Single-subset

```text
/mnt/datasets/NEU-DET-flat/
├── images/
└── annotations/
```

Pipeline tự nhận diện một trong hai cấu trúc trên. Ảnh và XML chỉ được ghép khi cùng subset
và cùng stem; không có ghép chéo `train` ↔ `validation`.

## 4. Chạy pipeline

### 4.1 Chạy cơ bản với đường dẫn tùy ý

```bash
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/work/neu-det-processed
```

Mặc định:

- Tỷ lệ split: `0.75,0.15,0.10` (train/validation/test)
- Seed: `42`
- Chính sách bất thường: `fail`

### 4.2 Chỉ định rõ seed và tỷ lệ

```bash
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/work/neu-det-processed \
  --seed 42 \
  --ratios 0.75,0.15,0.10
```

Tỷ lệ phải là ba số dương có tổng bằng `1.0`.

### 4.3 Giữ dữ liệu lỗi thay vì dừng

```bash
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/work/neu-det-processed \
  --on-anomaly quarantine
```

Sample **paired** bị lỗi được copy vào `rejected/` theo đúng layout nguồn; dữ liệu nguồn vẫn
nguyên vẹn. Ảnh/XML unpaired chỉ được ghi trong report và không được copy vào `rejected/`.

- Nếu còn ít nhất một sample hợp lệ: gate `pass_with_quarantine`, exit code `0` (kể cả khi còn
  unpaired error).
- Nếu không còn sample paired hợp lệ nào: gate `fail`, exit code `3`; output là report +
  `rejected/`, không có `images/`, `labels/` hay manifest.

### 4.4 Ghi đè output cũ

```bash
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/work/neu-det-processed \
  --overwrite
```

Không có `--overwrite`, pipeline từ chối ghi đè và trả exit code `4`.

`--overwrite` dùng staging (`<output>.staging`) và backup (`<output>.previous`):

- Validate/gate chạy trước; dataset cũ chưa bị xóa.
- Nếu lần chạy mới lỗi validation/gate, source change, verify hoặc bất biến split, output chỉ còn
  `validation_report.json` (fail mode) hoặc report + `rejected/` (all-quarantined); dataset hợp lệ
  gần nhất nằm ở `<output>.previous`.
- Retry không có `--overwrite` vẫn trả exit code `4` vì output đang không rỗng.
- Retry có `--overwrite` thay report-only cũ một cách an toàn; nếu thành công, dataset mới thay
  thế và backup cũ được dọn.

## 5. Output

```text
/mnt/work/neu-det-processed/
├── images/
│   ├── train/
│   ├── validation/
│   └── test/
├── labels/
│   ├── train/
│   ├── validation/
│   └── test/
├── rejected/                 # chỉ có khi --on-anomaly quarantine
│   ├── images/
│   │   └── <source_subset>/<relative-path>
│   └── annotations/
│       └── <source_subset>/<relative-path>
├── validation_report.json
└── split_manifest.json
```

- Mỗi ảnh trong `images/<split>/` có đúng một nhãn cùng stem trong `labels/<split>/`.
- Ảnh không có object có nhãn rỗng.
- `validation_report.json` ghi mọi bất thường, accounting, fingerprint và trạng thái gate.
- `split_manifest.json` ghi danh sách sample, thống kê lớp, seed, tỷ lệ và fingerprint nguồn.
- `rejected/` chỉ chứa ảnh gốc + XML gốc của sample paired lỗi, giữ nguyên subset/đường dẫn
  tương đối; không có nhãn YOLO.
- Khi run lỗi sau khi đã có staging (fail mode, source change, verify failure, split invariant hoặc
  all-quarantined), output chỉ chứa report; riêng all-quarantined có thêm `rejected/`. Không có
  manifest và không được dùng để huấn luyện; dataset cũ nếu có nằm ở `<output>.previous`.

## 6. Kiểm tra kết quả

### 6.1 Xem trạng thái gate và số lượng bất thường

```bash
jq '.gate, .summary.anomaly_counts' \
  /mnt/work/neu-det-processed/validation_report.json
```

Kiểm tra cân đối ảnh nguồn (SC-001):

```bash
jq '.summary | {
  source_images,
  source_annotations,
  written_samples,
  quarantined_samples,
  unwritten_samples,
  unpaired_images,
  unpaired_annotations,
  accounted_images,
  accounting_ok
}' /mnt/work/neu-det-processed/validation_report.json
```

Công thức:

```text
accounted_images =
    written_samples + quarantined_samples + unwritten_samples + unpaired_images
```

`accounting_ok` phải là `true` ở mọi lần report được ghi; nếu `false`, pipeline đã dừng và report
ghi rõ lý do. `unwritten_samples` là sample paired chưa ghi và không quarantine tại thời điểm report
(fail mode, source change/verify failure, hoặc đang chờ ghi ở report đầu tiên).
`unpaired_annotations` chỉ để báo cáo phía XML, không cộng vào `accounted_images`.

Gate counters chỉ đếm anomaly record:

```bash
jq '.gate | {
  status,
  blocking_errors,
  warnings
}' /mnt/work/neu-det-processed/validation_report.json
```

`pass_with_quarantine` có thể có `blocking_errors > 0` (các lỗi đã được quarantine xử lý);
`info` không được cộng vào `blocking_errors` hay `warnings`.

### 6.2 Xem số ảnh từng split

```bash
jq '.splits | to_entries | map({split: .key, images: .value.images})' \
  /mnt/work/neu-det-processed/split_manifest.json
```

Với 1.800 ảnh, mục tiêu là:

```text
train: 1350
validation: 270
test: 180
```

Nếu một nhóm ảnh trùng nội dung quá lớn khiến không thể đạt chính xác tỷ lệ này, pipeline ưu
tiên giữ toàn nhóm trong cùng một split để chống data leakage và ghi sai lệch thực tế
(`split_distribution_deviation`) trong report/manifest.

### 6.3 Kiểm tra không trùng ảnh giữa các split

```bash
jq '.invariants | {
  pairwise_disjoint_sample_id,
  pairwise_disjoint_output_path,
  pairwise_disjoint_sha256
}' /mnt/work/neu-det-processed/split_manifest.json
```

Cả ba giá trị phải là `true`. Phép kiểm tra độc lập (tính lại giao của các tập SHA-256 theo từng
split) nằm trong `tests/unit/test_splitter.py`.

### 6.4 Kiểm tra class mapping

```bash
jq '.classes' /mnt/work/neu-det-processed/split_manifest.json
```

Kỳ vọng đúng thứ tự:

```text
0 crazing
1 inclusion
2 patches
3 pitted_surface
4 rolled-in_scale
5 scratches
```

### 6.5 Kiểm tra dữ liệu nguồn không đổi

Tính hash cây nguồn trước và sau khi chạy:

```bash
find /mnt/datasets/NEU-DET -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  | sha256sum
```

Hai lần chạy lệnh trên (trước và sau pipeline) phải cho cùng một hash. Report cũng ghi
`source.fingerprint.status = "verified_unchanged"` và `verified_after_run = true`.

Nếu status là `changed`, nguồn đã bị thay đổi trong lúc chạy; nếu là `unavailable`, phép kiểm
tra không hoàn tất được vì lỗi I/O — trường hợp này **không** phải bằng chứng nguồn đã đổi. Cả
hai đều dẫn tới gate `fail`; `changed` dùng exit code `3`, `unavailable` dùng exit code `5`.

## 7. Chạy kiểm thử

```bash
pytest -q
```

Các nhóm test bắt buộc:

| Nhóm | Nội dung |
|------|----------|
| `tests/unit/test_validator.py` | Orchestration sample, kế thừa kiểm tra pairing từ discovery, bbox lỗi, XML hỏng, ảnh hỏng, `size_mismatch`, `filename_mismatch`, duplicate audit |
| `tests/unit/test_converter.py` | Nhiều object, nhiều lớp, nhãn rỗng, định dạng 6 chữ số |
| `tests/unit/test_splitter.py` | 75/15/10, multi-label, ảnh trùng, tái lập, disjoint |
| `tests/unit/test_classes.py` | Class mapping cố định, chuẩn hóa tên |
| `tests/unit/test_manifest.py` | Schema report/manifest, accounting, gate counters, vòng đời report, fingerprint status |
| `tests/integration/test_prepare_dataset.py` | CLI end-to-end, report-only failure, quarantine/rejected, overwrite/retry, nguồn bất biến |

Test dùng fixture VOC tổng hợp trong `tmp_path`; không cần dataset thật.

## 8. Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|------------|------------------------|------------|
| Exit code `2` | Source sai đường dẫn/cấu trúc, ratios sai, output nằm trong source | Kiểm tra lại `--source`, `--output`, `--ratios` |
| Exit code `3` | Có `missing_xml`, `missing_image`, `invalid_bbox`, `unknown_class`, duplicate conflict, all-quarantined… | Mở `validation_report.json`, xem `anomalies`; sửa dữ liệu nguồn hoặc dùng `--on-anomaly quarantine` |
| Exit code `4` | Output đã tồn tại (kể cả report-only từ lần lỗi trước) | Dùng `--overwrite` hoặc chọn output mới; dataset cũ có thể ở `<output>.previous` |
| Exit code `5` | Lỗi I/O, không ghi được report, fingerprint `unavailable`, hết dung lượng, quyền ghi | Kiểm tra ổ đĩa/quyền; chạy lại với `--overwrite` sau khi khắc phục |
| Report có `missing_xml` | Ảnh không có XML cùng stem trong cùng subset | Bổ sung XML đúng subset; **không** copy XML từ subset khác |
| Report có `missing_image` | XML không có ảnh cùng stem trong cùng subset | Bổ sung ảnh đúng subset; không tự tạo ảnh |
| Report có `ambiguous_pairing` | Một stem có nhiều ảnh hoặc nhiều XML trong cùng subset | Giữ đúng một ảnh và một XML; sửa/đổi tên dữ liệu nguồn; không tự chọn |
| Report có `invalid_bbox` | Tọa độ âm, zero-size, vượt biên hoặc không phải số | Sửa annotation nguồn; pipeline không clip hộ |
| Report có `unknown_class` | Tên lớp sai hoặc không thuộc 6 lớp | Sửa tên lớp; không tự gán lớp khác |
| Report có `duplicate_content` | Ảnh trùng nội dung; warning nếu nhãn nhất quán, error nếu xung đột | Kiểm tra `details.group_id`/`member_count`/`labels_consistent`; sửa nhãn hoặc quarantine toàn nhóm |
| Report có `filename_mismatch` | `<filename>` trong XML khác tên ảnh nhưng cặp ghép vẫn đúng | Sửa metadata XML nếu cần; pipeline không đổi cặp |
| Report có `size_mismatch` | `<size>` trong XML khác kích thước thật | Pipeline dùng kích thước thật; sửa XML nếu muốn hết warning |
| Report/manifest có `split_distribution_deviation` | Nhóm ảnh trùng nguyên tử quá lớn khiến tỷ lệ lệch mục tiêu | Giữ nguyên nhóm trong một split để chống leakage; đọc tỷ lệ thực tế trong manifest |
| `source_tree_changed` | Nguồn bị thay đổi thực sự trong lúc chạy | Chạy lại khi không có tiến trình khác ghi vào nguồn |
| `fingerprint.status = unavailable` | Không đọc được nguồn để kiểm tra fingerprint | Kiểm tra quyền/ổ đĩa; đây không phải bằng chứng nguồn đã đổi |

## 9. Lưu ý phạm vi

- Không huấn luyện YOLOv8s trong feature này.
- Không tạo `dataset.yaml`; feature 002 đọc manifest để tạo.
- Không sửa, di chuyển hoặc xóa dữ liệu gốc.
- Không ghép ảnh và XML khác subset nguồn.
- Output lỗi chỉ là report (hoặc report + `rejected/` khi all-quarantined), không phải dataset
  huấn luyện; chỉ output có `split_manifest.json` và gate `pass`/`pass_with_quarantine` mới dùng
  được.
- Tỷ lệ mặc định của feature là **75/15/10** (train/validation/test) với seed **42**; toàn bộ
  tài liệu Feature 001 đã được đồng bộ theo quyết định này.
