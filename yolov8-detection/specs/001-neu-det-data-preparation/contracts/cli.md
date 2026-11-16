# Contract: CLI `detection prepare`

**Feature**: `001-neu-det-data-preparation` | **Date**: 2026-11-14

Hợp đồng này mô tả giao diện dòng lệnh của pipeline chuẩn bị dữ liệu. Nó không bao gồm huấn
luyện, đánh giá hay suy luận YOLOv8s.

## 1. Cú pháp

```text
detection prepare --source PATH [--output PATH] [--seed INT]
                  [--ratios T,V,TE] [--on-anomaly {fail,quarantine}]
                  [--overwrite]
```

Lệnh con duy nhất của feature này là `prepare`. Không có tương tác, không cần GPU, không cần
mạng.

## 2. Tham số

| Tham số | Bắt buộc | Mặc định | Giá trị hợp lệ | Mô tả |
|---------|----------|----------|----------------|-------|
| `--source PATH` | Có | — | Thư mục tồn tại, đọc được | Dataset NEU-DET gốc. Có thể ở bất kỳ đâu; **không** bắt buộc nằm trong `data/raw` |
| `--output PATH` | Không | `data/processed/neu-det` | Thư mục không trùng/không nằm trong source | Nơi ghi ảnh, nhãn, manifest và report |
| `--seed INT` | Không | `42` | Số nguyên | Seed cố định cho phân bổ split; ghi vào manifest |
| `--ratios T,V,TE` | Không | `0.75,0.15,0.10` | Ba số thực dương, tổng bằng `1.0` (sai số `1e-9`) | Tỷ lệ train/validation/test |
| `--on-anomaly MODE` | Không | `fail` | `fail`, `quarantine` | Cách xử lý bất thường mức `error` |
| `--overwrite` | Không | Tắt | Cờ | Cho phép thay thế an toàn các artifact pipeline sở hữu trong output đã tồn tại; dataset cũ được giữ tới khi commit |

Ghi chú:

- `--source` và `--output` được resolve thành đường dẫn tuyệt đối trước khi kiểm tra và được
  ghi nguyên trạng vào manifest/report.
- `--output` mặc định chỉ là tiện ích; người dùng có thể trỏ ra ngoài repo.
- Không có tham số nào yêu cầu di chuyển, sao chép hoặc đăng ký dataset gốc vào `data/raw`.

## 3. Cấu trúc source được chấp nhận

### 3.1 Nhiều subset (mặc định của NEU-DET)

```text
<source>/
├── train/
│   ├── images/
│   └── annotations/
└── validation/
    ├── images/
    └── annotations/
```

### 3.2 Single-subset

```text
<source>/
├── images/
└── annotations/
```

Quy tắc discover:

- Mỗi thư mục con trực tiếp có cả `images/` và `annotations/` là một subset. Tên thư mục được
  dùng làm tên subset.
- Nếu source trực tiếp có `images/` và `annotations/`, tên subset là `root`.
- Thư mục con chỉ có một trong hai thư mục `images/`/`annotations/` là lỗi cấu trúc: dừng với
  exit code `2`, không tự coi là toàn bộ ảnh/XML thiếu cặp.
- Phần mở rộng ảnh được chấp nhận: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`
  (không phân biệt hoa/thường khi discover, nhưng ghép cặp dùng stem chính xác).
- XML phải có phần mở rộng `.xml`.
- Tệp khác được bỏ qua và ghi `unsupported_file` mức `info`.
- Nếu **cả** ảnh và XML đều không có, dừng với exit code `2` (source rỗng hoặc sai cấu trúc).
- Nếu một trong hai thư mục tồn tại nhưng rỗng, pipeline vẫn tiếp tục discover/pair và ghi
  `missing_xml` hoặc `missing_image` cho từng tệp ở phía còn lại; không thoát sớm.

## 4. Hành vi

Thứ tự thực hiện cố định:

1. **Kiểm tra tham số và đường dẫn**: source tồn tại; output không nằm trong source; ratios hợp
   lệ; output đã tồn tại và không rỗng thì cần `--overwrite`.
2. **Fingerprint nguồn lần đầu**: ghi nhận toàn bộ tệp nguồn trước khi xử lý.
3. **Discover**: liệt kê subset, ảnh, XML theo thứ tự sắp xếp ổn định.
4. **Pair**: ghép ảnh–XML **chỉ trong cùng subset** theo exact stem. Ảnh thiếu XML, XML thiếu
   ảnh, stem trùng/không rõ được ghi anomaly; không tự ghép, không tự tạo file.
5. **Validate + convert**: orchestrator gọi `verify_image()` và `convert_annotation()` hiện có;
   kiểm tra XML, class mapping, ảnh, `<size>`, `<filename>` và mọi bounding box; sinh nhãn YOLO
   trong bộ nhớ. Không lặp lại logic XML/class/bbox trong pipeline.
6. **Duplicate audit**: tính SHA-256, gom nhóm sample eligible trùng nội dung, kiểm tra nhãn
   nhất quán; mỗi member nhận một anomaly `duplicate_content`.
7. **Fingerprint sau validate**: tính lại fingerprint nguồn, kể cả khi gate sẽ `fail`; phân biệt
   `verified_unchanged`, `changed`, `unavailable`.
8. **Gate + first report + staging**: áp dụng `--on-anomaly`; tạo staging; ghi
   `validation_report.json` lần đầu kể cả khi gate `fail`, trước khi ghi ảnh/nhãn.
9. **Split**: chia 75/15/10 multi-label, seed cố định, group-aware; kiểm tra disjoint.
10. **Write**: copy ảnh, ghi nhãn YOLO; trong `quarantine` mode copy sample paired lỗi sang
    `rejected/` theo đúng layout nguồn.
11. **Verify + final report**: đối chiếu fingerprint nguồn sau chạy; kiểm tra lại bất biến split,
    accounting và đếm file; cập nhật `validation_report.json` lần cuối. Chỉ khi mọi bất biến đạt,
    ghi `split_manifest.json` nguyên tử.
12. **Commit**: chỉ commit staging thành output sau khi report cuối (và manifest nếu thành công)
    hoàn tất; nếu không, dừng với exit code `3` hoặc `5` và giữ output cũ an toàn.

Sau khi ghép, các sample hợp lệ được gộp vào một pool chung để chia lại 75/15/10. Mỗi sample là
đơn vị nguyên tử: ảnh và XML của nó luôn đi cùng một split. Việc chia lại này không phải ghép
ảnh–XML xuyên subset nguồn.

`seed`, `ratios` và `on_anomaly` từ CLI phải được truyền vào `ConversionOptions`/pipeline và
dùng để dựng `config` của report (và manifest ở US3). Không dùng giá trị mặc định ngầm trong
report khi người dùng đã truyền giá trị khác.

## 5. Chính sách bất thường

### 5.1 `--on-anomaly fail` (mặc định)

- Nếu có bất kỳ anomaly mức `error`, pipeline **không** tạo split, **không** ghi ảnh/nhãn.
- Mọi sample paired không được ghi trong `fail` mode — kể cả sample lỗi và sample hợp lệ — được
  đếm là `unwritten_samples`; không sample nào bị quarantine.
- `validation_report.json` vẫn được ghi với `gate.status = "fail"` trong staging và được commit
  thành output report-only (xem §6).
- Exit code `3`.

### 5.2 `--on-anomaly quarantine`

- Sample paired có `error` bị loại khỏi interim dataset và được **copy** sang `rejected/`:
  - `rejected/images/<source_subset>/<relative-path>`
  - `rejected/annotations/<source_subset>/<relative-path>`
  - Dùng `shutil.copy2`; chỉ copy ảnh gốc và XML gốc; không tạo nhãn YOLO; không di chuyển,
    không xóa nguồn.
- Chỉ sample **paired** bị lỗi mới được copy. Ảnh/XML unpaired vẫn là anomaly `error` chặn,
  được ghi trong report và loại khỏi interim dataset nhưng **không** được copy sang `rejected/`.
- Mỗi sample bị quarantine được đếm trong `quarantined_samples`; mọi ảnh nguồn vẫn phải thỏa
  `accounted_images == source_images`.
- Nếu còn ít nhất một sample paired eligible:
  - Gate `pass_with_quarantine`, exit code `0`, kể cả khi `blocking_errors > 0` do unpaired
    error.
  - Report liệt kê từng sample bị loại và từng unpaired asset.
- Nếu không còn sample paired eligible nào:
  - Gate `fail`, exit code `3`.
  - `rejected/` và report vẫn theo quarantine semantics: sample paired lỗi đã được copy sang
    `rejected/`; không có `images/`, `labels/` hay `split_manifest.json`.
- Warning và info không chặn split; luôn được ghi trong report.
- Không có chế độ bỏ qua im lặng.

### 5.3 Duplicate content

- Audit chỉ chạy trên sample eligible đã validate thành công; nhóm có ít nhất 2 member cùng
  SHA-256.
- Mỗi member nhận đúng một `duplicate_content` với `details` gồm `group_id`, `sha256`,
  `member_count`, `labels_consistent`.
- Nhãn nhất quán (multiset `(class_id, cx, cy, w, h)` sau chuẩn hóa, không phụ thuộc thứ tự
  XML): warning; giữ nguyên nhóm cho split.
- Nhãn xung đột: error cho toàn bộ nhóm. `fail` mode dừng với exit `3`; `quarantine` mode loại
  và copy toàn bộ nhóm sang `rejected/`.
- `DuplicateGroup` chỉ được giữ trong bộ nhớ; report không có trường top-level
  `duplicate_groups`.

### 5.4 Gate counters

- `blocking_errors` = số anomaly record severity `error`.
- `warnings` = số anomaly record severity `warning`.
- Record `info` không được cộng vào cả hai counter.
- `pass` yêu cầu `blocking_errors == 0`.
- `pass_with_quarantine` có thể có `blocking_errors > 0` vì error đã được quarantine xử lý.
- `fail` có thể có `blocking_errors == 0` khi nguyên nhân là fingerprint `unavailable` hoặc
  verify I/O failure.

## 6. Ghi đè output và commit an toàn

### 6.1 Quy tắc cơ bản

- Nếu `--output` đã tồn tại và không rỗng:
  - Không có `--overwrite`: exit code `4`, không ghi gì.
  - Có `--overwrite`: dùng staging/commit dưới đây; tuyệt đối không đụng tới source.
- Nếu `--output` trùng hoặc nằm trong `--source`: exit code `2` trước khi ghi bất kỳ tệp nào.
- Nếu `--output` nằm ngoài source nhưng là thư mục cha của source: cũng bị từ chối để tránh
  ghi đè gián tiếp.
- `--overwrite` chỉ thay thế các artifact do pipeline sở hữu: `images/`, `labels/`,
  `rejected/`, `validation_report.json`, `split_manifest.json`. Tệp/thư mục không liên quan
  trong output được giữ nguyên.

### 6.2 Staging và commit

Pipeline không xóa dataset cũ trước khi run mới vượt qua validate/gate:

1. Tạo staging cùng cấp với output: `<output>.staging` (cùng filesystem để rename nguyên tử).
   Nếu staging còn sót từ lần chạy lỗi trước, nội dung pipeline-owned của nó được dọn trước khi
   dùng.
2. Dựng toàn bộ artifact mới trong staging: report lần đầu sau gate, ảnh/nhãn/rejected, report
   cuối, manifest (nếu thành công).
3. Chỉ commit khi report cuối đã ghi xong:
   - Output chưa tồn tại hoặc rỗng: rename/chuyển artifact từ staging vào output.
   - Output đã có dataset: chuyển các artifact cũ do pipeline sở hữu sang
     `<output>.previous` (thay backup cũ nếu có), rồi chuyển artifact mới từ staging vào output.
   - Output chỉ là report-only failure artifact từ lần trước: thay các artifact pipeline-owned
     của report-only đó bằng artifact tương ứng từ staging; giữ nguyên tệp không liên quan và
     `<output>.previous` đang chứa dataset hợp lệ gần nhất.
4. Sau một lần chạy **thành công** (`pass`/`pass_with_quarantine`), `<output>.previous` của dataset
   vừa bị thay thế được xóa best-effort; nếu xóa lỗi, output mới vẫn hợp lệ. Failure commit
   (report-only hoặc all-quarantined) **không** xóa `<output>.previous` để dataset hợp lệ gần nhất
   vẫn khôi phục được.

`<output>.staging` và `<output>.previous` là artifact tạm, không thuộc output contract; feature
002 không được đọc chúng.

### 6.3 Failure output và retry

- **Validation/gate fail (`fail` mode):** staging chỉ chứa `validation_report.json`; commit tạo
  output report-only (cộng các tệp không liên quan đã có) và chuyển dataset cũ sang
  `<output>.previous`. Không có `images/`, `labels/`, `rejected/` hay manifest.
- **All-quarantined:** staging chứa `validation_report.json` + `rejected/`; commit tạo failure
  output gồm report và rejected copies, chuyển dataset cũ sang `<output>.previous`; không có
  `images/`, `labels/` hay manifest.
- **Source change / verify failure:** report trong staging được cập nhật với lỗi và gate `fail`.
  Nếu report vẫn ghi được, commit failure output report-only: dataset cũ (nếu có) chuyển sang
  `<output>.previous`, ảnh/nhãn/rejected mới không được commit và bị bỏ cùng staging. Nếu report
  không ghi được hoặc commit lỗi, exit code `5`; dataset cũ vẫn ở output hoặc `<output>.previous`.
- **Split/accounting invariant failure:** tương tự source/verify failure — chỉ commit report-only
  với gate `fail`, không commit images/labels/manifest.
- **Report write failure:** exit code `5`; không commit manifest/output mới; dataset cũ không bị
  xóa.
- **Retry sau report-only failure:**
  - Không có `--overwrite`: output không rỗng nên retry trả exit code `4`, bảo vệ report và
    dataset cũ trong `<output>.previous`.
  - Có `--overwrite`: retry được phép thay report-only bằng kết quả mới một cách an toàn; nếu
    retry thành công, output mới thay thế và backup cũ được dọn theo §6.2.
- **Commit lỗi giữa chừng:** exit code `5`; `<output>.previous` vẫn giữ dataset cũ. Người dùng
  chạy lại với `--overwrite` sau khi kiểm tra ổ đĩa/quyền; pipeline dọn staging còn sót trước khi
  dựng lại.

## 7. Exit code

| Code | Ý nghĩa |
|------|---------|
| `0` | Thành công (`pass` hoặc `pass_with_quarantine`); có thể có warning/info và `blocking_errors > 0` đã được quarantine xử lý |
| `2` | Lỗi sử dụng/cấu hình/đường dẫn/cấu trúc source (bao gồm output nằm trong source, ratios sai, source thiếu) |
| `3` | Lỗi dữ liệu chặn (`gate.status = fail`), quarantine loại toàn bộ sample, source thay đổi sau chạy, hoặc bất biến split/accounting bị vi phạm |
| `4` | Output đã tồn tại mà không có `--overwrite` (kể cả output report-only từ lần chạy lỗi trước) |
| `5` | Lỗi I/O ngoài dự kiến: không đọc/ghi được, không tạo được staging, không ghi được report, fingerprint check `unavailable`, hết dung lượng, … |

Exit code là hợp đồng ổn định cho script và CI. Thông báo lỗi chi tiết ghi ra stderr; kết quả
có cấu trúc nằm trong JSON, không phụ thuộc stdout.

## 8. Ví dụ

Chạy với dataset ngoài repo và output tùy chọn:

```bash
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/work/neu-det-processed \
  --seed 42 \
  --ratios 0.75,0.15,0.10 \
  --on-anomaly fail
```

Dùng output mặc định:

```bash
detection prepare --source /mnt/datasets/NEU-DET
```

Chế độ quarantine:

```bash
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/work/neu-det-processed \
  --on-anomaly quarantine
```

Chạy lại và thay thế output cũ:

```bash
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/work/neu-det-processed \
  --overwrite
```

Lệnh sai (output nằm trong source) phải bị từ chối:

```bash
# Exit code 2; không ghi gì vào source
detection prepare \
  --source /mnt/datasets/NEU-DET \
  --output /mnt/datasets/NEU-DET/processed
```

## 9. Bảo đảm

CLI cam kết:

- Không ghi, sửa, đổi tên, di chuyển hoặc xóa bất kỳ tệp nào trong `--source`.
- Không ghép ảnh với XML khác subset nguồn.
- Không tự sửa XML, không clip bbox, không tự gán class, không tạo cặp còn thiếu.
- Mọi bất thường có bản ghi trong `validation_report.json`; report được ghi nguyên tử theo vòng
  đời first write → final update.
- Class mapping luôn là `0..5` theo đúng thứ tự cố định.
- Split mặc định 75/15/10, tất định theo seed, không trùng ảnh giữa các split.
- Ảnh trùng nội dung luôn nằm cùng một split; nếu ràng buộc nguyên tử khiến không thể đạt chính
  xác tỷ lệ mục tiêu, ưu tiên chống data leakage và ghi `split_distribution_deviation` cùng tỷ lệ
  thực tế vào report/manifest.
- Manifest ghi đủ cấu hình, nguồn, seed, tỷ lệ và danh sách sample để tái lập.
- Accounting luôn thỏa `written_samples + quarantined_samples + unwritten_samples +
  unpaired_images == source_images`; nếu không, pipeline dừng trước khi ghi output.
- `--overwrite` không phá dataset cũ trước khi run mới qua validate; dataset cũ được giữ ở
  `<output>.previous` khi bị thay thế và chỉ dọn sau commit thành công.

## 10. Ngoài phạm vi

- Huấn luyện, đánh giá hoặc suy luận YOLOv8s.
- Tạo `dataset.yaml` hoặc cấu hình Ultralytics.
- Tăng cường dữ liệu, cân bằng lớp trong huấn luyện.
- Sửa dữ liệu nguồn, chuẩn hóa lại dataset, hoặc tải dataset từ mạng.
- Giao diện người dùng, API, dịch vụ nền.
