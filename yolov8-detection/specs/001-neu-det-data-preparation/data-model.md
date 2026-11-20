# Data Model: Chuẩn bị dữ liệu NEU-DET

**Feature**: `001-neu-det-data-preparation` | **Date**: 2026-11-14

**Nguồn yêu cầu**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md)

Tài liệu này mô tả các thực thể dữ liệu, quan hệ, trạng thái xử lý và bất biến của pipeline.
Đây là mô hình thiết kế; không phải mã nguồn và không bao gồm dữ liệu thật.

## 1. Class Catalogue (bất biến)

Class mapping là hằng số duy nhất của toàn bộ module, không phụ thuộc thứ tự file, thứ tự
`<object>` hay tên thư mục nguồn.

| `class_id` | `class_name` | Ghi chú |
|------------|--------------|---------|
| 0 | `crazing` | Tên chuẩn dùng trong nhãn YOLO, manifest, report và feature 002 |
| 1 | `inclusion` | |
| 2 | `patches` | |
| 3 | `pitted_surface` | |
| 4 | `rolled-in_scale` | Giữ nguyên dấu gạch nối |
| 5 | `scratches` | |

Quy tắc:

- Tên nguồn được chuẩn hóa bằng `strip()` + `lower()` trước khi tra cứu.
- Không chấp nhận fuzzy matching, alias, số lớp khác hoặc thứ tự khác.
- Tên không khớp sau chuẩn hóa tạo `AnomalyRecord(code="unknown_class", severity="error")`.
- `class_id` phải nằm trong `0..5`; manifest và report luôn ghi đủ 6 lớp theo đúng thứ tự trên.

## 2. Quan hệ thực thể

```text
SourceDataset
├── SourceSubset (train, validation, ...)
│   ├── ImageAsset
│   └── AnnotationAsset
│
ImageAsset ──(cùng subset + cùng stem)── AnnotationAsset
        └──────────────┬──────────────┘
                 MatchedSample
                 ├── SourceObject 0..*
                 ├── present_classes: set[class_id]
                 ├── AnomalyRecord *
                 ├── DuplicateGroup 0..1
                 └── SplitAssignment 0..1
                             └── Split (train | validation | test)

ValidationReport  ── tổng hợp anomaly + gate + fingerprint nguồn
SplitManifest     ── tổng hợp SplitAssignment + thống kê + cấu hình
```

Một `MatchedSample` chỉ được tạo khi ảnh và XML thỏa đồng thời: cùng `SourceSubset`, cùng stem,
và mỗi bên là duy nhất trong subset đó.

## 3. Thực thể nguồn

### 3.1 `SourceDataset`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `root` | path | Đường dẫn `--source`; có thể ở bất kỳ đâu, không bắt buộc `data/raw` |
| `subsets` | list[`SourceSubset`] | Các subset phát hiện được, sắp xếp theo tên |
| `image_files` | list[path] | Toàn bộ ảnh hợp lệ về phần mở rộng, sắp xếp theo đường dẫn tương đối |
| `annotation_files` | list[path] | Toàn bộ XML, sắp xếp theo đường dẫn tương đối |
| `fingerprint` | `SourceFingerprint` | Fingerprint cây nguồn (xem §3.5) |
| `read_only` | bool | Luôn `true`; pipeline không mở tệp nguồn ở chế độ ghi |

### 3.2 `SourceSubset`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `name` | string | `train`, `validation`, hoặc `root` nếu source là single-subset |
| `relative_prefix` | string | Tiền tố tương đối dùng trong `sample_id` |
| `images_dir` | path | Thư mục `images/` của subset |
| `annotations_dir` | path | Thư mục `annotations/` của subset |

Phạm vi ghép cặp bị giới hạn trong một `SourceSubset`. Không có thực thể nào đại diện cho
"cặp ảnh–XML xuyên subset".

### 3.3 `ImageAsset`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `asset_id` | string | `<subset>/<relative_path>` |
| `subset` | string | Tên subset nguồn |
| `relative_path` | path | Đường dẫn tương đối trong source |
| `stem` | string | Tên tệp không gồm phần mở rộng |
| `extension` | string | Phần mở rộng đã chuẩn hóa (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`) |
| `width`, `height` | int | Kích thước thật đọc bằng Pillow; `null` nếu ảnh hỏng |
| `sha256` | string | SHA-256 nội dung ảnh; `null` nếu không đọc được |
| `status` | enum | `discovered`, `valid`, `corrupt`, `unpaired` |

### 3.4 `AnnotationAsset`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `asset_id` | string | `<subset>/<relative_path>` |
| `subset` | string | Tên subset nguồn |
| `relative_path` | path | Đường dẫn tương đối trong source |
| `stem` | string | Tên tệp không gồm `.xml` |
| `objects` | list[`SourceObject`] | Có thể rỗng (annotation hợp lệ không có object) |
| `declared_size` | {width, height}? | Lấy từ `<size>` nếu có |
| `declared_filename` | string? | Lấy từ `<filename>`; chỉ dùng để đối chiếu warning |
| `status` | enum | `discovered`, `valid`, `invalid_xml`, `unpaired` |

### 3.5 `SourceFingerprint`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `algorithm` | string | `sha256` |
| `entries` | list[{relative_path, size, sha256}] | Sắp xếp theo `relative_path`, chỉ gồm tệp trong cây nguồn |
| `tree_sha256` | string | SHA-256 của chuỗi entries đã chuẩn hóa, đo trước khi xử lý |
| `status` | enum | `verified_unchanged`, `changed`, `unavailable` (xem quy tắc bên dưới) |
| `after_tree_sha256` | string? | Fingerprint sau chạy nếu đọc được; `null` khi `status = unavailable` |
| `verified_after_run` | bool | Chỉ `true` khi `status = verified_unchanged` |
| `changed` | list[path] | Tệp thêm/sửa/xóa; chỉ có phần tử khi `status = changed` |
| `error` | string? | Mô tả lỗi I/O khi `status = unavailable`; `null` trong các trường hợp khác |

Quy tắc:

- Fingerprint được tính lại sau bước validate, kể cả khi gate sẽ `fail`, và được tính lại lần
  cuối sau khi ghi/verify output trên đường thành công.
- `verified_unchanged`: fingerprint sau khớp trước; đây là bằng chứng nguồn không đổi.
- `changed`: fingerprint sau khác trước; `changed` liệt kê khác biệt và report có anomaly
  `source_tree_changed` mức `error`.
- `unavailable`: không thể hoàn tất phép kiểm tra vì lỗi I/O. Trạng thái này **không** phải bằng
  chứng nguồn đã thay đổi: không được đặt `verified_after_run = true`, không được tạo anomaly
  `source_tree_changed`, và `changed` phải rỗng. Lỗi được báo qua `error`, stderr và exit code
  `5`; gate là `fail`.
- Một phép kiểm tra chưa chạy không bao giờ được ghi thành `changed` hoặc `verified_unchanged`.

## 4. Thực thể dẫn xuất

### 4.1 `SourceObject`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `index` | int | Thứ tự `<object>` trong XML, bắt đầu từ 0 |
| `class_name_raw` | string | Tên lớp như trong XML |
| `class_name` | string | Tên sau `strip().lower()` |
| `class_id` | int? | `0..5`; `null` nếu không map được |
| `bbox` | `BoundingBox` | Tọa độ gốc và trạng thái hợp lệ |
| `yolo_line` | string? | `class_id cx cy w h`, 6 chữ số thập phân; `null` nếu lỗi |

### 4.2 `BoundingBox`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `xmin`, `ymin`, `xmax`, `ymax` | float | Tọa độ gốc trong XML |
| `image_width`, `image_height` | int | Kích thước ảnh thật dùng để kiểm tra |
| `valid` | bool | Kết quả kiểm tra |
| `reason` | string? | Mã lý do nếu không hợp lệ |
| `normalized` | {cx, cy, w, h}? | Chỉ có khi `valid`; tính từ tọa độ gốc |

Quy tắc hợp lệ:

- Bốn tọa độ phải parse được thành số hữu hạn (không NaN/Inf).
- `xmin < xmax` và `ymin < ymax`; chiều rộng và chiều cao lớn hơn 0.
- `0 <= xmin`, `0 <= ymin`, `xmax <= image_width`, `ymax <= image_height`.
- Không clip, không làm tròn tọa độ gốc, không tự sửa bbox.
- Bbox hợp lệ chạm biên (`xmax == width`) vẫn được chấp nhận.
- Sau khi làm tròn 6 chữ số thập phân, `w` và `h` phải lớn hơn 0; nếu không, bbox là
  `invalid_bbox` (zero-size sau chuẩn hóa).
- Nếu bất kỳ object nào trong XML không hợp lệ, **toàn bộ sample** bị đánh dấu lỗi; không ghi
  nhãn một phần và không bỏ riêng object lỗi.

Công thức chuẩn hóa (chỉ dùng cho object hợp lệ):

```text
cx = (xmin + xmax) / 2 / image_width
cy = (ymin + ymax) / 2 / image_height
w  = (xmax - xmin) / image_width
h  = (ymax - ymin) / image_height
```

Giá trị ghi ra có 6 chữ số thập phân; `w` và `h` phải nằm trong `(0, 1]`, `cx` và `cy` trong
`[0, 1]`.

### 4.3 `MatchedSample`

Đơn vị nguyên tử của pipeline. Ảnh và XML của sample luôn đi cùng nhau qua validate, split và
write.

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `sample_id` | string | `<subset>/<stem>`; duy nhất trên toàn dataset |
| `source_subset` | string | Subset nguồn |
| `image` | `ImageAsset` | Ảnh đã ghép |
| `annotation` | `AnnotationAsset` | XML đã ghép |
| `objects` | list[`SourceObject`] | Toàn bộ object hợp lệ của sample |
| `object_count` | int | `len(objects)`; có thể bằng 0 |
| `present_classes` | list[int] | Tập **unique** class ID xuất hiện, sắp xếp tăng dần; `[]` nếu ảnh không có object |
| `label_lines` | list[string] | Các dòng nhãn YOLO theo thứ tự object |
| `state` | enum | Xem §7 |
| `duplicate_group` | string? | `sha256:<hex>` nếu ảnh thuộc nhóm trùng |
| `anomalies` | list[`AnomalyRecord`] | Các bất thường gắn với sample |

`present_classes` là cơ sở phân tầng. Ví dụ ảnh có 2 object `crazing` và 1 object `patches`
cho `present_classes = [0, 2]`, không phải chỉ `[0]`. Ảnh không có object có
`present_classes = []`; vẫn là sample hợp lệ, tham gia split theo dung lượng còn lại và được
ghi `empty_annotation` mức `info`.

### 4.4 `DuplicateGroup`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `group_id` | string | `sha256:<hex>` của nội dung ảnh |
| `sha256` | string | Hash nội dung |
| `members` | list[string] | Các `sample_id` có cùng nội dung |
| `labels_consistent` | bool | Multiset `(class_id, cx, cy, w, h)` của các object, sau chuẩn hóa và làm tròn 6 chữ số, giống nhau giữa mọi member; thứ tự `<object>` trong XML không được tính |
| `assigned_split` | string? | `train`/`validation`/`test`; tất cả member dùng chung giá trị này |
| `state` | enum | `grouped`, `conflict`, `quarantined` |

Quy tắc:

- Nhóm chỉ gồm các sample **eligible** đã vượt qua validate; nhóm có ít nhất 2 member.
- Mỗi member nhận đúng một anomaly `duplicate_content`; `details` gồm `group_id`, `sha256`,
  `member_count`, `labels_consistent`.
- `labels_consistent = true` → warning; nhóm được giữ nguyên và gán nguyên tử vào một split.
- `labels_consistent = false` → error cho toàn bộ member; ở `fail` mode gate fail; ở
  `quarantine` mode toàn bộ nhóm bị quarantine và copy sang `rejected/`.
- Mọi member của nhóm đều được đếm trong `written_samples` hoặc `quarantined_samples` (hoặc
  `unwritten_samples` khi gate fail), không bị bỏ sót.
- `DuplicateGroup` chỉ được giữ trong bộ nhớ để US3 dùng; report không có trường top-level
  `duplicate_groups`. Manifest của US3 mới ghi `duplicate_groups`.
- Sau chia, không có `sha256` nào xuất hiện ở hai split.

### 4.5 `SplitAssignment`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `sample_id` | string | Khóa của sample |
| `split` | enum | `train`, `validation`, `test` |
| `source_subset` | string | Giữ nguyên nguồn để truy vết |
| `source_image` | path | Đường dẫn tương đối trong source |
| `source_xml` | path | Đường dẫn tương đối trong source |
| `output_image` | path | Đường dẫn tương đối trong output, ví dụ `images/train/a.jpg` |
| `output_label` | path | Đường dẫn tương đối trong output, ví dụ `labels/train/a.txt` |
| `sha256` | string | Hash ảnh, dùng kiểm tra rò rỉ |
| `present_classes` | list[int] | Tập unique class ID của ảnh |
| `object_count` | int | Số object của sample |

### 4.6 `Split`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `name` | enum | `train`, `validation`, `test` |
| `target_ratio` | float | Tỷ lệ cấu hình, mặc định `0.75`, `0.15`, `0.10` |
| `actual_ratio` | float | `images / total_eligible_images` |
| `images` | int | Số sample |
| `objects` | int | Tổng số object |
| `image_counts_by_class` | map[class_id, int] | Số ảnh có ít nhất một object của lớp |
| `object_counts_by_class` | map[class_id, int] | Tổng số object theo lớp |
| `source_subset_counts` | map[subset, int] | Số sample theo subset nguồn |
| `assignments` | list[`SplitAssignment`] | Danh sách sample của split |

## 5. Thực thể báo cáo

### 5.1 `AnomalyRecord`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `code` | string | Mã bất thường (xem §6) |
| `severity` | enum | `error`, `warning`, `info` |
| `scope` | enum | `dataset`, `subset`, `image`, `annotation`, `sample`, `split` |
| `sample_id` | string? | Nếu bất thường gắn với sample |
| `source_subset` | string? | Subset nguồn |
| `paths` | list[path] | Một hoặc nhiều đường dẫn nguồn liên quan; có thể rỗng với anomaly cấp dataset/split |
| `reason` | string | Giải thích ngắn, không che giấu dữ liệu |
| `details` | object | Chi tiết bổ sung (tọa độ, object index, class name, hash, …) |

`AnomalyRecord` không bao giờ thay thế dữ liệu nguồn; nó chỉ mô tả vấn đề.

### 5.2 `ValidationReport`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `schema_version` | string | `1.0` |
| `feature` | string | `001-neu-det-data-preparation` |
| `generated_at` | ISO-8601 | Thời điểm tạo report |
| `source` | object | `root`, `subsets`, `fingerprint` (gồm `tree_sha256`, `status`, `after_tree_sha256`, `verified_after_run`, `changed`, `error`) |
| `config` | object | `seed`, `ratios`, `on_anomaly` lấy từ CLI; class mapping và phiên bản thuật toán cố định |
| `summary` | object | Số ảnh/XML/cặp/sample, số object, accounting và thống kê anomaly |
| `gate` | object | `status`, `blocking_errors`, `warnings` |
| `anomalies` | list[`AnomalyRecord`] | Toàn bộ bất thường, sắp xếp ổn định theo `code`, `paths`, `sample_id`, object index, `reason` |

`summary` tối thiểu:

| Trường | Ý nghĩa |
|--------|---------|
| `source_images` | Số ảnh phát hiện |
| `source_annotations` | Số XML phát hiện |
| `matched_samples` | Số cặp ghép được trong cùng subset |
| `unpaired_images` | Số ảnh không thuộc sample nào (thiếu XML hoặc ambiguous) |
| `unpaired_annotations` | Số XML không thuộc sample nào (thiếu ảnh hoặc ambiguous) |
| `eligible_samples` | Số sample vượt qua validate và không bị loại bởi gate/quarantine |
| `quarantined_samples` | Số sample paired bị loại khỏi interim dataset và được copy sang `rejected/` (chế độ quarantine) |
| `unwritten_samples` | Số sample paired chưa được ghi và không bị quarantine tại thời điểm report: sample lỗi trong chế độ `fail`, sample hợp lệ bị chặn bởi gate/`fail`, source thay đổi, verify/write thất bại, hoặc sample đang chờ ghi ở report đầu tiên |
| `written_samples` | Số sample paired đã ghi thành công vào interim dataset |
| `accounted_images` | `written_samples + quarantined_samples + unwritten_samples + unpaired_images` |
| `accounting_ok` | `accounted_images == source_images`; nếu `false`, pipeline dừng |
| `objects_total` | Tổng object của sample `eligible_samples` (đã validate, không quarantine); giữ nguyên giữa first write và final update; manifest mới là nguồn số liệu của dataset đã ghi |
| `objects_by_class` | Số object của sample eligible theo 6 class ID |
| `anomaly_counts` | Số lượng theo từng `code` |

Quy tắc accounting:

- Mỗi ảnh nguồn thuộc đúng một nhóm: `written`, `quarantined`, `unwritten` hoặc `unpaired`.
- `unwritten_samples` đếm **mọi** sample paired chưa ghi và không quarantine tại thời điểm report,
  kể cả sample lỗi trong chế độ `fail` và sample đang chờ ghi ở first write; không chỉ sample hợp lệ.
- `unpaired_images` là ảnh nguồn không tạo được sample (thiếu XML hoặc ambiguous pairing).
- `unpaired_annotations` chỉ dùng để báo cáo phía XML; XML không được cộng vào
  `accounted_images` vì đại lượng này đếm ảnh nguồn.
- Mẫu paired bị loại trong chế độ `fail` là `unwritten_samples`, không phải
  `quarantined_samples`.
- Toàn bộ sample paired bị quarantine được đếm là `quarantined_samples` kể cả khi không còn
  sample eligible nào; report khi đó có gate `fail`.
- `eligible_samples` không được dùng thay cho `written_samples` trong công thức accounting.

### 5.3 `SplitManifest`

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `schema_version` | string | `1.0` |
| `generated_at` | ISO-8601 | Thời điểm tạo manifest |
| `dataset` | object | Tên dataset, source root, source fingerprint, subsets |
| `config` | object | `seed`, `ratios`, `on_anomaly` thực tế của lần chạy lấy từ CLI; stratification, duplicate policy, class mapping |
| `classes` | list[{id, name}] | 6 lớp theo đúng thứ tự |
| `totals` | object | Tổng images/objects và thống kê lớp |
| `splits` | map[split, `Split`] | `train`, `validation`, `test` |
| `duplicate_groups` | list[`DuplicateGroup`] | Nhóm ảnh trùng và split được gán |
| `invariants` | object | Kết quả kiểm tra disjoint, phủ đầy, nguồn bất biến |

### 5.4 Vòng đời `validation_report.json`

Report được ghi nguyên tử và có thể được cập nhật nhiều lần trong một lần chạy:

1. **First write**: sau discover → pair → validate → duplicate audit → gate, sau khi fingerprint
   được tính lại và trước khi ghi bất kỳ ảnh/nhãn interim nào. Report phải phản ánh anomaly,
   accounting tại thời điểm đó, gate và fingerprint. Vì chưa ghi dataset, sample paired chưa ghi
   (kể cả eligible đang chờ ghi) được đếm vào `unwritten_samples` để `accounting_ok` vẫn đúng.
2. **Final update**: sau khi ghi và verify output, report được cập nhật để phản ánh
   `written_samples`, `quarantined_samples`, `unwritten_samples`, fingerprint cuối và gate cuối;
   sample đã ghi chuyển từ `unwritten_samples` sang `written_samples`.
3. **Failure update**: khi source thay đổi hoặc verify thất bại, report được cập nhật với lỗi và
   gate `fail` nếu vẫn có thể ghi report.
4. Nếu không thể ghi report (kể cả first write hoặc final update), pipeline dừng với exit code
   `5`; không được coi là thành công và không ghi manifest.
5. Report luôn nằm trong output/staging và chỉ trở thành output chính thức khi commit an toàn
   (xem [contracts/cli.md](./contracts/cli.md) §6). Report không bao giờ được ghi vào source.

## 6. Mã bất thường

| `code` | Severity | Phạm vi | Điều kiện | Tác động |
|--------|----------|---------|-----------|----------|
| `missing_xml` | error | image | Ảnh không có XML cùng stem trong cùng subset | Sample không được tạo |
| `missing_image` | error | annotation | XML không có ảnh cùng stem trong cùng subset | Sample không được tạo |
| `ambiguous_pairing` | error | subset | Một stem có >1 ảnh hoặc >1 XML trong cùng subset | Không ghép; ghi nhận |
| `invalid_xml` | error | annotation | XML hỏng, thiếu `<annotation>`, hoặc `<object>` thiếu `<name>`/`<bndbox>` bắt buộc | Sample lỗi |
| `unknown_class` | error | sample | Tên lớp không khớp 6 lớp sau chuẩn hóa | Sample lỗi |
| `invalid_bbox` | error | sample | Bbox không phải số, âm, zero-size, ngược trục, vượt biên | Sample lỗi |
| `corrupt_image` | error | image | Pillow không mở/verify được | Sample lỗi |
| `empty_annotation` | info | sample | XML hợp lệ, 0 object | Giữ sample, nhãn rỗng |
| `size_mismatch` | warning | sample | `<size>` khác kích thước thật | Dùng kích thước thật; anomaly do validator orchestration tạo, `paths` gồm cả ảnh và XML |
| `filename_mismatch` | warning | annotation | Basename của `<filename>` khác tên ảnh đã ghép | Chỉ cảnh báo; không đổi cặp, không đổi tên |
| `duplicate_content` | warning / error | sample | Cùng SHA-256; warning nếu nhãn nhất quán, error nếu xung đột | Gom nhóm hoặc quarantine toàn nhóm; một anomaly cho mỗi member |
| `split_distribution_deviation` | warning | split | Nhóm trùng nguyên tử khiến tỷ lệ split lệch mục tiêu | Ghi nhận, giữ atomicity |
| `split_class_absent` | warning | split | Một class ID không có mặt trong split | Ghi nhận, không tự chuyển |
| `source_tree_changed` | error | dataset | Fingerprint sau chạy **khác** trước chạy | Fail, báo động |
| `unsupported_file` | info | dataset | Tệp không phải ảnh/XML | Bỏ qua, ghi nhận |

Quy tắc chi tiết cho anomaly:

- `size_mismatch`: do bước orchestration validation (T020) tạo sau khi so
  `AnnotationAsset.declared_size` với kích thước thật từ `verify_image()`. `paths` chứa cả ảnh
  và XML; `details` chứa `declared` và `actual`; kích thước thật được dùng để chuẩn hóa.
- `filename_mismatch`: so **basename** của `<filename>` (bỏ mọi thành phần thư mục) với basename
  của ảnh đã ghép, so sánh chính xác và phân biệt hoa/thường. `paths` chứa cả ảnh và XML;
  `details` chứa `declared_filename` và `actual_filename`. Không dùng metadata này để ghép cặp.
- `duplicate_content`: mỗi member của nhóm có đúng một anomaly. `details` tối thiểu gồm
  `group_id`, `sha256`, `member_count`, `labels_consistent`; `paths` gồm ảnh và XML của member.
  Nhãn nhất quán → warning; xung đột → error cho toàn bộ member. Không thêm trường top-level
  `duplicate_groups` vào report; `DuplicateGroup` chỉ được giữ trong bộ nhớ cho US3 và ghi vào
  manifest khi US3 chạy.
- `source_tree_changed`: chỉ dùng khi fingerprint thực sự khác. Lỗi I/O khi kiểm tra fingerprint
  được biểu diễn bằng `source.fingerprint.status = "unavailable"`, không bằng anomaly này.
- Thứ tự anomaly: sắp xếp ổn định theo `code`, rồi `paths` (so sánh tuple đường dẫn), rồi
  `sample_id` (giá trị `null` xếp cuối), rồi `details.object_index` nếu có (giá trị thiếu xếp
  cuối), rồi `reason`. Thứ tự này là một phần của contract.

Severity semantics:

- `error`: chặn split ở chế độ `fail`; bị loại khỏi split ở chế độ `quarantine`.
- `warning`: không chặn; sample vẫn có thể vào split.
- `info`: chỉ ghi nhận, không ảnh hưởng gate.
- Gate counter chỉ đếm anomaly record: `blocking_errors` = số record severity `error`,
  `warnings` = số record severity `warning`; `info` không được cộng vào cả hai.
- `pass_with_quarantine` có thể có `blocking_errors > 0` vì các error đã được xử lý bằng
  quarantine. `pass` yêu cầu `blocking_errors == 0`.

## 7. Trạng thái xử lý của sample

```text
discovered
   │
   ├── unpaired ──► missing_xml / missing_image / ambiguous_pairing (error)
   │
   └── paired
         │
         ├── invalid ──► invalid_xml / unknown_class / invalid_bbox / corrupt_image (error)
         │      ├── quarantined (chỉ khi --on-anomaly quarantine)
         │      └── unwritten (chế độ fail; paired nhưng không được ghi)
         │
         └── valid
               ├── duplicate_conflict (error, nếu nhãn xung đột)
               │      ├── quarantined (chỉ khi --on-anomaly quarantine)
               │      └── unwritten (chế độ fail; paired nhưng không được ghi)
               │
               └── eligible
                     └── assigned(train | validation | test)
                              ├── written
                              └── unwritten (fail mode, source change, verify/write failure)
```

Quy tắc chuyển trạng thái:

- `discovered → paired` chỉ khi exact stem + cùng subset + duy nhất.
- `paired → valid` chỉ khi toàn bộ object hợp lệ; một object lỗi làm sample lỗi.
- `paired → invalid` khi XML/ảnh/class/bbox có lỗi; sample không bao giờ thành `eligible`.
- `valid → eligible` chỉ khi không còn `error` gắn với sample.
- `invalid` hoặc `duplicate_conflict → quarantined` chỉ ở chế độ `quarantine`; ở chế độ `fail`,
  các sample này là `unwritten` vì paired nhưng không được ghi và không được quarantine.
- `eligible → assigned` chỉ khi split thỏa mọi bất biến ở §8.
- `assigned → written` chỉ khi ảnh và nhãn đã ghi thành công.
- `invalid`/`duplicate_conflict` (fail mode) và `eligible/assigned` (fail mode, source thay đổi,
  verify/write thất bại, chưa tới bước ghi hoặc không còn dung lượng split hợp lệ) → `unwritten`.
  `unwritten_samples` phải được đếm trong accounting.
- Khi quarantine loại toàn bộ sample paired, mọi sample đó là `quarantined`; không có sample
  `written`; gate `fail` và exit code `3`, nhưng bản copy `rejected/` và report vẫn theo đúng
  quarantine semantics.
- Không có chuyển trạng thái nào sửa hoặc xóa dữ liệu nguồn.

## 8. Bất biến của split

Các bất biến phải được kiểm tra trong code và trong test:

| ID | Bất biến |
|----|----------|
| INV-01 | Mọi sample `eligible` thuộc đúng một split trong `train`, `validation`, `test` |
| INV-02 | Không có `sample_id` nào xuất hiện ở hai split |
| INV-03 | Không có `output_image` nào xuất hiện ở hai split |
| INV-04 | Không có `sha256` nào xuất hiện ở hai split |
| INV-05 | Tổng số sample của ba split bằng số sample `eligible` |
| INV-06 | Tỷ lệ thực tế xấp xỉ 0.75 / 0.15 / 0.10; sai lệch chỉ do làm tròn largest-remainder hoặc do ràng buộc nguyên tử của nhóm ảnh trùng, và mọi sai lệch ngoài làm tròn phải có `split_distribution_deviation` |
| INV-07 | Tất cả member của một `DuplicateGroup` nằm trong cùng một split |
| INV-08 | Mỗi `MatchedSample` có đúng một ảnh và đúng một XML, cùng subset nguồn |
| INV-09 | Không có cặp ảnh–XML nào được ghép xuyên subset |
| INV-10 | Fingerprint cây nguồn trước và sau chạy giống nhau |
| INV-11 | Mọi sample bị loại khỏi split đều có ít nhất một `AnomalyRecord` mức `error` |
| INV-12 | Manifest ghi đủ 6 class theo đúng thứ tự 0–5 |
| INV-13 | Accounting đúng: `written_samples + quarantined_samples + unwritten_samples + unpaired_images == source_images` và `accounting_ok == true` trước khi ghi output/manifest |
| INV-14 | Mỗi sample paired lỗi trong chế độ quarantine có đúng một bản copy ảnh và một bản copy XML dưới `rejected/`, giữ nguyên đường dẫn tương đối; không có nhãn YOLO trong `rejected/` |
| INV-15 | Mỗi ảnh nguồn được đếm đúng một lần trong accounting, không trùng giữa `written`, `quarantined`, `unwritten`, `unpaired` |

Với **1.800 sample hợp lệ**, mục tiêu largest-remainder 75/15/10 là **1350 train / 270 validation /
180 test**. Trên bộ NEU-DET thực tế, sau khi quarantine `patches_101` và `patches_105` còn
**1.798 sample hợp lệ**, nên cùng công thức largest-remainder cho kết quả **1348/270/180**. Nếu
nhóm ảnh trùng nguyên tử hoặc pool eligible khác khiến không thể đạt chính xác mục tiêu, ưu tiên
giữ toàn nhóm trong một split để chống data leakage, ghi `split_distribution_deviation` và ghi
tỷ lệ thực tế vào manifest.

## 9. Quy ước đếm

- `images`: số `MatchedSample`, không phải số object.
- `objects`: tổng số `<object>` hợp lệ.
- `image_counts_by_class[c]`: số ảnh có **ít nhất một** object lớp `c`.
- `object_counts_by_class[c]`: tổng số object lớp `c`.
- `present_classes`: tập unique class ID của ảnh; dùng cho phân tầng.
- Tổng `image_counts_by_class` có thể lớn hơn `images` vì một ảnh có nhiều lớp.
- `actual_ratio = images / total_eligible_images`; tổng ba tỷ lệ bằng 1.0 (sai số float được
  chuẩn hóa khi ghi JSON).
- `source_images`: số ảnh nguồn phát hiện, là mẫu số của accounting.
- `written_samples`, `quarantined_samples`: đếm sample paired, không đếm object; mỗi sample đóng
  góp đúng một ảnh.
- `unwritten_samples`: đếm sample paired chưa ghi và không quarantine tại thời điểm report, gồm
  sample lỗi trong `fail` mode và sample đang chờ ghi ở first write.
- `unpaired_images`: đếm ảnh nguồn không tạo được sample.
- `unpaired_annotations` chỉ để báo cáo phía XML; không cộng vào `accounted_images`.
- Accounting phải đúng ở **mọi** lần ghi report; first write dùng snapshot chưa ghi, final update
  dùng kết quả thực tế.
- `blocking_errors` và `warnings` đếm anomaly record theo severity; `info` không được cộng.

## 10. Quy ước định danh và tên output

| Đối tượng | Quy tắc |
|-----------|---------|
| `sample_id` | `<source_subset>/<stem>`; nếu single-subset dùng `root/<stem>` |
| `group_id` | `sha256:<hex>` của nội dung ảnh |
| Tên ảnh output | Giữ stem nguồn nếu duy nhất; nếu không, `<subset>_<stem>`; nếu vẫn trùng, thêm 8 ký tự đầu SHA-256 |
| Tên nhãn output | Cùng stem với ảnh output, phần mở rộng `.txt` |
| Đường dẫn ảnh | `images/<split>/<tên>.<ext>` |
| Đường dẫn nhãn | `labels/<split>/<tên>.txt` |
| Đường dẫn rejected (ảnh) | `rejected/images/<source_subset>/<relative_path>` |
| Đường dẫn rejected (XML) | `rejected/annotations/<source_subset>/<relative_path>` |

Quy tắc rejected:

- Chỉ sample **paired** bị lỗi trong chế độ `quarantine` mới được copy vào `rejected/`.
- Giữ nguyên `source_subset` và đường dẫn tương đối dưới `images/` hoặc `annotations/` của
  subset nguồn; dùng `shutil.copy2`, không tạo nhãn YOLO, không chuyển/xóa nguồn.
- Ảnh và XML unpaired chỉ được báo trong report và loại khỏi interim dataset; không copy sang
  `rejected/`.
- Nếu một đường dẫn đích bị trùng do chuẩn hóa filesystem, giữ nguyên đường dẫn gốc cho bản đầu
  tiên và thêm hậu tố `__<8 ký tự SHA-256>` vào basename cho bản sau; quyết định này được ghi
  trong `details` của anomaly tương ứng. Với cây nguồn hợp lệ, đường dẫn tương đối vốn đã duy
  nhất nên trường hợp này không xảy ra.

Không đổi tên, không ghi đè tệp nguồn. Manifest chứa ánh xạ đầy đủ từ nguồn sang output.

## 11. Cấu trúc output

```text
<output>/
├── images/
│   ├── train/
│   ├── validation/
│   └── test/
├── labels/
│   ├── train/
│   ├── validation/
│   └── test/
├── rejected/                 # chỉ khi --on-anomaly quarantine
│   ├── images/
│   │   └── <source_subset>/<relative-path>
│   └── annotations/
│       └── <source_subset>/<relative-path>
├── validation_report.json
└── split_manifest.json
```

- `validation_report.json` được ghi kể cả khi pipeline dừng vì lỗi dữ liệu.
- `split_manifest.json` chỉ được ghi sau khi split, write và verify nguồn/output thành công.
- Pipeline luôn dựng artifact trong thư mục staging cùng cấp (`<output>.staging`) và chỉ commit sau
  khi verify/report hoàn tất; khi `--overwrite` thay thế dataset cũ, dataset đó được giữ ở
  `<output>.previous` cho tới khi commit thành công. Staging/backup không phải một phần của output
  cuối cùng và không được feature 002 đọc.
- Khi chạy thất bại sau khi đã có staging (fail mode, source change, verify failure, split invariant
  hoặc quarantine loại toàn bộ sample), output chỉ chứa report; riêng all-quarantined có thêm
  `rejected/`. Không có `images/`, `labels/` hoặc manifest giả.
- Không có `dataset.yaml` trong feature này; file đó thuộc feature 002.
- Không có thư mục `data/raw` bắt buộc; source có thể nằm ngoài repo.
