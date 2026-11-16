# Contract: Artifact Formats

**Feature**: `001-neu-det-data-preparation` | **Date**: 2026-11-14

Hợp đồng này mô tả cấu trúc output, định dạng nhãn YOLO, `validation_report.json` và
`split_manifest.json`. Đây là giao diện dữ liệu giữa feature 001 và feature 002.

## 1. Cấu trúc output

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
├── rejected/                 # chỉ tồn tại khi --on-anomaly quarantine
│   ├── images/
│   │   └── <source_subset>/<relative-path>
│   └── annotations/
│       └── <source_subset>/<relative-path>
├── validation_report.json
└── split_manifest.json
```

Quy tắc:

- `images/<split>/` và `labels/<split>/` chứa cùng số tệp; mỗi ảnh có đúng một nhãn.
- `validation_report.json` được ghi kể cả khi pipeline dừng vì lỗi dữ liệu.
- `split_manifest.json` chỉ được ghi sau khi split, write và verify nguồn/output thành công.
- `rejected/` chỉ chứa bản copy của sample **paired** bị lỗi trong chế độ `quarantine`; giữ
  nguyên subset và đường dẫn tương đối của nguồn, dùng `shutil.copy2`, chỉ chứa ảnh gốc và XML
  gốc, không có nhãn YOLO. Dữ liệu nguồn không bị di chuyển hoặc xóa.
- Ảnh/XML unpaired chỉ được ghi trong report, không được copy sang `rejected/`.
- Không có `dataset.yaml`; feature 002 tự tạo từ manifest.
- Khi chạy thất bại sau khi đã có staging (fail mode, source change, verify failure, split invariant
  hoặc all-quarantined), output chỉ chứa `validation_report.json`; riêng all-quarantined có thêm
  `rejected/`. Không có `images/`, `labels/` hay manifest; dataset cũ nếu có nằm ở
  `<output>.previous`.

## 2. Định dạng nhãn YOLO

Mỗi ảnh có một tệp `.txt` cùng stem trong `labels/<split>/`.

### 2.1 Nội dung

- Mỗi dòng: `class_id cx cy w h`
- Phân tách bằng đúng một dấu cách.
- `class_id` là số nguyên `0..5`.
- `cx`, `cy`, `w`, `h` là số thực chuẩn hóa theo chiều rộng/chiều cao ảnh.
- Bốn giá trị tọa độ `cx`, `cy`, `w`, `h` giữ đúng **6 chữ số thập phân**.
- Không có header, không có comment.
- Thứ tự dòng theo thứ tự `<object>` trong XML nguồn.

### 2.2 Ví dụ

```text
0 0.512000 0.433000 0.120000 0.080000
2 0.310000 0.720000 0.200000 0.150000
5 0.840000 0.250000 0.090000 0.070000
```

### 2.3 Ảnh không có object

- Tạo tệp nhãn rỗng (0 byte).
- Ảnh vẫn vào split và vẫn được ghi.
- Report ghi `empty_annotation` mức `info`.

### 2.4 Bất biến

- `w > 0`, `h > 0`, `w <= 1`, `h <= 1`, `0 <= cx <= 1`, `0 <= cy <= 1`.
- Sau khi làm tròn 6 chữ số thập phân, `w` và `h` vẫn phải lớn hơn 0; nếu không, sample bị
  `invalid_bbox` thay vì ghi nhãn zero-size.
- Không có dòng cho object không hợp lệ; nếu một object lỗi, toàn bộ sample bị loại khỏi split.
- Không ghi tọa độ tuyệt đối.
- Không đổi thứ tự class ID.

## 3. `validation_report.json`

### 3.1 Schema

| Trường | Kiểu | Bắt buộc | Mô tả |
|--------|------|----------|-------|
| `schema_version` | string | Có | `"1.0"` |
| `feature` | string | Có | `"001-neu-det-data-preparation"` |
| `generated_at` | string | Có | ISO-8601 UTC |
| `source` | object | Có | `root`, `subsets`, `fingerprint` (gồm `tree_sha256`, `status`, `after_tree_sha256`, `verified_after_run`, `changed`, `error`) |
| `config` | object | Có | `seed`, `ratios`, `on_anomaly`, class mapping, thuật toán; lấy trực tiếp từ CLI |
| `summary` | object | Có | Số lượng ảnh/XML/sample/object, accounting và anomaly |
| `gate` | object | Có | `status`, `blocking_errors`, `warnings` |
| `anomalies` | array | Có | Danh sách `AnomalyRecord`, sắp xếp ổn định theo `code`, `paths`, `sample_id`, object index, `reason` |

Accounting và counter semantics:

```text
accounted_images =
    written_samples
    + quarantined_samples
    + unwritten_samples
    + unpaired_images

accounting_ok = accounted_images == source_images
```

- `unwritten_samples` đếm mọi sample paired chưa ghi và không quarantine tại thời điểm report,
  gồm sample lỗi trong `fail` mode, sample bị chặn bởi gate/source change/verify failure, và
  sample đang chờ ghi ở first write; không đếm sample đã quarantine.
- Accounting phải đúng ở mọi lần ghi report. Ở first write chưa có sample nào được ghi, nên
  sample paired chưa ghi được tính vào `unwritten_samples`; final update chuyển sample đã ghi
  sang `written_samples`.
- `quarantined_samples` đếm sample paired bị loại trong chế độ `quarantine` và được copy sang
  `rejected/`.
- `unpaired_images` đếm ảnh nguồn không tạo được sample; `unpaired_annotations` chỉ để báo cáo
  và không cộng vào `accounted_images`.
- `blocking_errors` = số `AnomalyRecord` severity `error`; `warnings` = số record severity
  `warning`; record `info` không được cộng vào cả hai.
- `pass_with_quarantine` có thể có `blocking_errors > 0` vì lỗi đã được quarantine xử lý.
  `pass` yêu cầu `blocking_errors == 0`.
- `anomalies` sắp xếp ổn định theo thứ tự: `code` tăng dần, `paths` (so sánh tuple) tăng dần,
  `sample_id` tăng dần với `null` xếp cuối, `details.object_index` tăng dần nếu có (thiếu xếp
  cuối), `reason` tăng dần.

### 3.2 Ví dụ

```json
{
  "schema_version": "1.0",
  "feature": "001-neu-det-data-preparation",
  "generated_at": "2026-11-14T10:00:00Z",
  "source": {
    "root": "/mnt/datasets/NEU-DET",
    "subsets": ["train", "validation"],
    "fingerprint": {
      "algorithm": "sha256",
      "tree_sha256": "sha256:8f14e45fceea167a5a36dedd4bea25436a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d",
      "status": "verified_unchanged",
      "after_tree_sha256": "sha256:8f14e45fceea167a5a36dedd4bea25436a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d",
      "verified_after_run": true,
      "changed": [],
      "error": null
    }
  },
  "config": {
    "seed": 42,
    "ratios": {
      "train": 0.75,
      "validation": 0.15,
      "test": 0.1
    },
    "on_anomaly": "fail",
    "stratification": "multilabel_iterative",
    "duplicate_policy": "content_group_atomic",
    "class_mapping": [
      {"id": 0, "name": "crazing"},
      {"id": 1, "name": "inclusion"},
      {"id": 2, "name": "patches"},
      {"id": 3, "name": "pitted_surface"},
      {"id": 4, "name": "rolled-in_scale"},
      {"id": 5, "name": "scratches"}
    ]
  },
  "summary": {
    "source_images": 1800,
    "source_annotations": 1800,
    "matched_samples": 1800,
    "unpaired_images": 0,
    "unpaired_annotations": 0,
    "eligible_samples": 1800,
    "quarantined_samples": 0,
    "unwritten_samples": 0,
    "written_samples": 1800,
    "accounted_images": 1800,
    "accounting_ok": true,
    "objects_total": 2600,
    "objects_by_class": {
      "0": 430,
      "1": 420,
      "2": 450,
      "3": 410,
      "4": 440,
      "5": 450
    },
    "anomaly_counts": {
      "missing_xml": 0,
      "missing_image": 0,
      "ambiguous_pairing": 0,
      "invalid_xml": 0,
      "unknown_class": 0,
      "invalid_bbox": 0,
      "corrupt_image": 0,
      "empty_annotation": 0,
      "size_mismatch": 0,
      "filename_mismatch": 0,
      "duplicate_content": 0,
      "split_distribution_deviation": 0,
      "split_class_absent": 0,
      "source_tree_changed": 0,
      "unsupported_file": 0
    }
  },
  "gate": {
    "status": "pass",
    "blocking_errors": 0,
    "warnings": 0
  },
  "anomalies": []
}
```

Ví dụ trên là report **cuối** sau khi ghi thành công. Ở first write (trước khi ghi dataset),
`written_samples` bằng `0` và mọi sample paired chưa ghi nằm trong `unwritten_samples`;
`accounting_ok` vẫn phải là `true`.

### 3.3 `AnomalyRecord`

| Trường | Kiểu | Bắt buộc | Mô tả |
|--------|------|----------|-------|
| `code` | string | Có | Mã trong bảng §6 của [data-model.md](../data-model.md) |
| `severity` | string | Có | `error`, `warning`, `info` |
| `scope` | string | Có | `dataset`, `subset`, `image`, `annotation`, `sample`, `split` |
| `sample_id` | string/null | Có | `null` nếu không gắn với sample |
| `source_subset` | string/null | Có | Subset nguồn |
| `paths` | array[string] | Có | Đường dẫn tương đối trong source; có thể rỗng với anomaly cấp `dataset`/`split` |
| `reason` | string | Có | Giải thích ngắn |
| `details` | object | Có | Chi tiết bổ sung; có thể rỗng |

Ví dụ một bản ghi lỗi:

```json
{
  "code": "missing_xml",
  "severity": "error",
  "scope": "image",
  "sample_id": null,
  "source_subset": "train",
  "paths": ["train/images/crazing_0001.jpg"],
  "reason": "No XML with the same stem in subset 'train'",
  "details": {
    "stem": "crazing_0001",
    "expected_xml": "train/annotations/crazing_0001.xml"
  }
}
```

Ví dụ một bản ghi cảnh báo:

```json
{
  "code": "size_mismatch",
  "severity": "warning",
  "scope": "sample",
  "sample_id": "train/crazing_0002",
  "source_subset": "train",
  "paths": [
    "train/images/crazing_0002.jpg",
    "train/annotations/crazing_0002.xml"
  ],
  "reason": "XML size differs from actual image size; actual size used for normalization",
  "details": {
    "declared": {"width": 200, "height": 200},
    "actual": {"width": 204, "height": 200}
  }
}
```

Ví dụ `filename_mismatch` (metadata không đổi cặp):

```json
{
  "code": "filename_mismatch",
  "severity": "warning",
  "scope": "annotation",
  "sample_id": "train/crazing_0003",
  "source_subset": "train",
  "paths": [
    "train/images/crazing_0003.jpg",
    "train/annotations/crazing_0003.xml"
  ],
  "reason": "XML <filename> basename differs from the paired image filename; pairing is unchanged",
  "details": {
    "declared_filename": "crazing_0002.jpg",
    "actual_filename": "crazing_0003.jpg"
  }
}
```

Ví dụ `duplicate_content` (một record cho mỗi member; nhãn xung đột):

```json
{
  "code": "duplicate_content",
  "severity": "error",
  "scope": "sample",
  "sample_id": "validation/crazing_0001",
  "source_subset": "validation",
  "paths": [
    "validation/images/crazing_0001.jpg",
    "validation/annotations/crazing_0001.xml"
  ],
  "reason": "Image content is duplicated by another sample with conflicting labels",
  "details": {
    "group_id": "sha256:0b1f2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
    "sha256": "sha256:0b1f2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
    "member_count": 2,
    "labels_consistent": false
  }
}
```

### 3.4 `gate.status`

| Giá trị | Ý nghĩa | Manifest được ghi? | Exit code |
|---------|---------|--------------------|-----------|
| `pass` | Không có lỗi chặn | Có | `0` |
| `pass_with_quarantine` | Sample paired lỗi đã bị quarantine, còn ít nhất một sample eligible; unpaired error vẫn có thể tồn tại | Có | `0` |
| `fail` | Có lỗi chặn trong `fail` mode, quarantine loại toàn bộ sample paired, accounting sai, source thay đổi, verify thất bại, hoặc fingerprint không kiểm tra được | Không | `3` hoặc `5` |

### 3.5 Vòng đời ghi report

- **First write**: sau validate, duplicate audit và gate, sau khi fingerprint được tính lại,
  trước khi ghi bất kỳ ảnh/nhãn interim nào. Report đầu tiên phải có đủ anomaly, accounting tại
  thời điểm đó (sample chưa ghi nằm trong `unwritten_samples`), gate và fingerprint status.
- **Final update**: sau write và verify, report được cập nhật để phản ánh `written_samples`,
  `quarantined_samples`, `unwritten_samples`, fingerprint cuối và gate cuối.
- **Failure update**: khi source thay đổi hoặc verify thất bại, report được cập nhật với lỗi và
  `gate.status = "fail"` nếu vẫn ghi được report.
- Report được ghi nguyên tử (temp file + `os.replace`). Nếu không ghi được report, pipeline dừng
  với exit code `5`, không ghi manifest và không coi là thành công.
- `split_manifest.json` chỉ được ghi khi mọi bất biến đạt và report cuối đã ghi thành công.
- Nếu lỗi xảy ra trước khi có thể tạo output/staging (source không tồn tại, output không hợp lệ,
  không tạo được staging), không có report; lỗi được báo qua stderr và exit code.
- `anomaly_counts` chứa đủ tất cả mã đã biết, kể cả mã có số lượng 0.
- `anomalies` là mảng phẳng; mỗi bản ghi độc lập, không lồng nhau.

## 4. `split_manifest.json`

### 4.1 Schema

| Trường | Kiểu | Bắt buộc | Mô tả |
|--------|------|----------|-------|
| `schema_version` | string | Có | `"1.0"` |
| `generated_at` | string | Có | ISO-8601 UTC |
| `dataset` | object | Có | `name`, `source_root`, `source_fingerprint` (object như §5), `source_subsets` |
| `config` | object | Có | Seed, ratios, stratification, duplicate policy, `on_anomaly`, class mapping |
| `classes` | array | Có | 6 cặp `{id, name}` theo thứ tự 0–5 |
| `totals` | object | Có | `images`, `objects`, `image_counts_by_class`, `object_counts_by_class` |
| `splits` | object | Có | Khóa `train`, `validation`, `test`; giá trị là `Split` |
| `duplicate_groups` | array | Có | Danh sách `DuplicateGroup` |
| `invariants` | object | Có | Kết quả kiểm tra sau chia |

### 4.2 Ví dụ

Ví dụ dưới đây dùng cấu hình mặc định **75/15/10** với seed **42** cho 1.800 ảnh, tương ứng
**1350/270/180** ảnh.

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-11-14T10:00:00Z",
  "dataset": {
    "name": "NEU-DET",
    "source_root": "/mnt/datasets/NEU-DET",
    "source_fingerprint": {
      "algorithm": "sha256",
      "tree_sha256": "sha256:8f14e45fceea167a5a36dedd4bea25436a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d",
      "status": "verified_unchanged",
      "after_tree_sha256": "sha256:8f14e45fceea167a5a36dedd4bea25436a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d",
      "verified_after_run": true,
      "changed": [],
      "error": null
    },
    "source_subsets": ["train", "validation"]
  },
  "config": {
    "seed": 42,
    "ratios": {
      "train": 0.75,
      "validation": 0.15,
      "test": 0.1
    },
    "stratification": "multilabel_iterative",
    "duplicate_policy": "content_group_atomic",
    "on_anomaly": "fail",
    "class_mapping": [
      {"id": 0, "name": "crazing"},
      {"id": 1, "name": "inclusion"},
      {"id": 2, "name": "patches"},
      {"id": 3, "name": "pitted_surface"},
      {"id": 4, "name": "rolled-in_scale"},
      {"id": 5, "name": "scratches"}
    ]
  },
  "classes": [
    {"id": 0, "name": "crazing"},
    {"id": 1, "name": "inclusion"},
    {"id": 2, "name": "patches"},
    {"id": 3, "name": "pitted_surface"},
    {"id": 4, "name": "rolled-in_scale"},
    {"id": 5, "name": "scratches"}
  ],
  "totals": {
    "images": 1800,
    "objects": 2600,
    "image_counts_by_class": {
      "0": 310,
      "1": 310,
      "2": 310,
      "3": 310,
      "4": 310,
      "5": 310
    },
    "object_counts_by_class": {
      "0": 430,
      "1": 420,
      "2": 450,
      "3": 410,
      "4": 440,
      "5": 450
    }
  },
  "splits": {
    "train": {
      "images": 1350,
      "objects": 1950,
      "target_ratio": 0.75,
      "actual_ratio": 0.75,
      "image_counts_by_class": {
        "0": 233,
        "1": 233,
        "2": 233,
        "3": 233,
        "4": 232,
        "5": 232
      },
      "object_counts_by_class": {
        "0": 322,
        "1": 315,
        "2": 338,
        "3": 307,
        "4": 330,
        "5": 338
      },
      "source_subset_counts": {
        "train": 1080,
        "validation": 270
      },
      "assignments": [
        {
          "sample_id": "train/crazing_0001",
          "source_subset": "train",
          "source_image": "train/images/crazing_0001.jpg",
          "source_xml": "train/annotations/crazing_0001.xml",
          "output_image": "images/train/crazing_0001.jpg",
          "output_label": "labels/train/crazing_0001.txt",
          "sha256": "sha256:0b1f2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
          "present_classes": [0, 2],
          "object_count": 3
        },
        {
          "sample_id": "validation/crazing_0001",
          "source_subset": "validation",
          "source_image": "validation/images/crazing_0001.jpg",
          "source_xml": "validation/annotations/crazing_0001.xml",
          "output_image": "images/train/validation_crazing_0001.jpg",
          "output_label": "labels/train/validation_crazing_0001.txt",
          "sha256": "sha256:0b1f2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
          "present_classes": [0, 2],
          "object_count": 3
        }
      ]
    },
    "validation": {
      "images": 270,
      "objects": 390,
      "target_ratio": 0.15,
      "actual_ratio": 0.15,
      "image_counts_by_class": {
        "0": 46,
        "1": 46,
        "2": 46,
        "3": 46,
        "4": 47,
        "5": 47
      },
      "object_counts_by_class": {
        "0": 65,
        "1": 63,
        "2": 68,
        "3": 61,
        "4": 66,
        "5": 67
      },
      "source_subset_counts": {
        "train": 216,
        "validation": 54
      },
      "assignments": []
    },
    "test": {
      "images": 180,
      "objects": 260,
      "target_ratio": 0.1,
      "actual_ratio": 0.1,
      "image_counts_by_class": {
        "0": 31,
        "1": 31,
        "2": 31,
        "3": 31,
        "4": 31,
        "5": 31
      },
      "object_counts_by_class": {
        "0": 43,
        "1": 42,
        "2": 44,
        "3": 42,
        "4": 44,
        "5": 45
      },
      "source_subset_counts": {
        "train": 144,
        "validation": 36
      },
      "assignments": []
    }
  },
  "duplicate_groups": [
    {
      "group_id": "sha256:0b1f2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
      "sha256": "sha256:0b1f2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
      "members": ["train/crazing_0001", "validation/crazing_0001"],
      "labels_consistent": true,
      "assigned_split": "train",
      "state": "grouped"
    }
  ],
  "invariants": {
    "pairwise_disjoint_sample_id": true,
    "pairwise_disjoint_output_path": true,
    "pairwise_disjoint_sha256": true,
    "all_eligible_assigned": true,
    "duplicate_groups_atomic": true,
    "no_cross_subset_pairing": true,
    "source_unchanged": true,
    "class_mapping_fixed": true
  }
}
```

Trong ví dụ trên, tất cả mảng `assignments` đều được rút gọn để dễ đọc; trong output thật, mỗi
split liệt kê đầy đủ sample của mình. Hai sample trùng nội dung `train/crazing_0001` và
`validation/crazing_0001` nằm cùng split `train`; sample thứ hai được đổi tên output thành
`validation_crazing_0001.*` theo quy tắc chống trùng tên ở [data-model.md](../data-model.md) §10.

### 4.3 `Split` object

| Trường | Kiểu | Mô tả |
|--------|------|-------|
| `images` | int | Số sample |
| `objects` | int | Tổng object |
| `target_ratio` | float | Tỷ lệ cấu hình |
| `actual_ratio` | float | `images / totals.images` |
| `image_counts_by_class` | map[string, int] | Số ảnh có ít nhất một object của lớp |
| `object_counts_by_class` | map[string, int] | Tổng object theo lớp |
| `source_subset_counts` | map[string, int] | Số sample theo subset nguồn |
| `assignments` | array | Danh sách sample, sắp xếp theo `sample_id` |

### 4.4 `SplitAssignment` object

| Trường | Kiểu | Mô tả |
|--------|------|-------|
| `sample_id` | string | `<source_subset>/<stem>` |
| `source_subset` | string | Subset nguồn |
| `source_image` | string | Đường dẫn tương đối trong source |
| `source_xml` | string | Đường dẫn tương đối trong source |
| `output_image` | string | Đường dẫn tương đối trong output |
| `output_label` | string | Đường dẫn tương đối trong output |
| `sha256` | string | Hash nội dung ảnh |
| `present_classes` | array[int] | Tập unique class ID của ảnh, sắp xếp tăng dần |
| `object_count` | int | Số object |

### 4.5 `invariants`

| Khóa | Ý nghĩa |
|------|---------|
| `pairwise_disjoint_sample_id` | Không sample nào ở hai split |
| `pairwise_disjoint_output_path` | Không output path nào ở hai split |
| `pairwise_disjoint_sha256` | Không nội dung ảnh nào ở hai split |
| `all_eligible_assigned` | Mọi sample hợp lệ đều có split |
| `duplicate_groups_atomic` | Mọi member của nhóm trùng nằm cùng split |
| `no_cross_subset_pairing` | Không có cặp ảnh–XML xuyên subset |
| `source_unchanged` | Fingerprint nguồn trước/sau giống nhau |
| `class_mapping_fixed` | 6 class đúng thứ tự 0–5 |

Nếu bất kỳ giá trị nào là `false`, pipeline phải dừng với exit code `3` và không ghi manifest
thành công.

## 5. Fingerprint nguồn

Fingerprint xuất hiện trong cả report và manifest:

```json
{
  "algorithm": "sha256",
  "tree_sha256": "sha256:8f14e45fceea167a5a36dedd4bea25436a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d",
  "status": "verified_unchanged",
  "after_tree_sha256": "sha256:8f14e45fceea167a5a36dedd4bea25436a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d",
  "verified_after_run": true,
  "changed": [],
  "error": null
}
```

- `tree_sha256` là hash của danh sách `(relative_path, size, sha256)` đã sắp xếp, đo trước xử lý.
- `status`:
  - `verified_unchanged`: fingerprint sau khớp trước; `verified_after_run = true`.
  - `changed`: fingerprint sau khác trước; `verified_after_run = false`, `changed` liệt kê tệp
    thêm/sửa/xóa, report có `source_tree_changed` mức `error`, exit `3`.
  - `unavailable`: không hoàn tất được phép kiểm tra vì lỗi I/O; `verified_after_run = false`,
    `changed` rỗng, `error` mô tả lỗi, gate `fail`, exit `5`. Không tạo anomaly
    `source_tree_changed` và không được coi là bằng chứng nguồn đã đổi.
- Fingerprint được tính lại sau validate, kể cả khi gate sẽ `fail`, và tính lại lần cuối sau
  write/verify trên đường thành công.
- `entries` (danh sách từng tệp) có thể được ghi đầy đủ trong report/manifest; ví dụ trên rút
  gọn. Tối thiểu phải có `tree_sha256`, `status`, `verified_after_run` và `changed`.
- Manifest chỉ được ghi khi `status = verified_unchanged`; do đó manifest không bao giờ chứa
  `changed` hoặc `unavailable`.

## 6. Quy tắc ghi tệp

- Tất cả tệp text dùng UTF-8, kết thúc bằng newline.
- JSON dùng indent 2, `ensure_ascii = false`, không có comment.
- Ghi JSON nguyên tử: tạo tệp tạm trong cùng thư mục rồi `os.replace`.
- Không ghi bất kỳ tệp nào vào source.
- Ảnh output là bản copy; không hard link, không symlink.
- Tên tệp output tuân theo [data-model.md](../data-model.md) §10.
- Pipeline dựng artifact trong staging cùng cấp (`<output>.staging`) trước khi commit; khi
  `--overwrite`, dataset cũ được giữ ở `<output>.previous`. Staging/backup là artifact tạm, không
  thuộc contract output. Chỉ commit sau khi report cuối và verify hoàn tất; chi tiết ở
  [cli.md](./cli.md) §6.
- Report-only failure output chỉ chứa `validation_report.json` (fail mode) hoặc
  `validation_report.json` + `rejected/` (quarantine loại toàn bộ sample paired); không có
  `images/`, `labels/` hoặc manifest.

## 7. Tương thích với feature 002

Feature 002 có thể:

- Đọc `split_manifest.json` để lấy đường dẫn `images/train`, `images/validation`, `images/test`
  và `labels/...`.
- Đọc `classes` để tạo `dataset.yaml` với đúng 6 lớp theo thứ tự 0–5.
- Đọc `invariants` và `gate` để từ chối dữ liệu không hợp lệ trước khi huấn luyện.
- Không được coi output chỉ có `validation_report.json` (hoặc report + `rejected/`) là dataset
  hợp lệ; không có `split_manifest.json` nghĩa là chưa có dataset để huấn luyện.

Feature 002 không được sửa các tệp trong output của feature 001; nếu cần cấu hình khác, phải
tạo output mới.
