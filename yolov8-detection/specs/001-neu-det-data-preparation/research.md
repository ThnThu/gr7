# Research: Chuẩn bị dữ liệu NEU-DET

**Feature**: `001-neu-det-data-preparation` | **Date**: 2026-11-14

**Revision**: 2026-11-14 — cập nhật theo yêu cầu bổ sung: pairing trong từng subset nguồn,
split 75/15/10 phân tầng đa nhãn, CLI source/output tùy ý, class mapping cố định và kiểm thử
mở rộng.

**Revision (US2)**: 2026-11-15 — chốt accounting, rejected layout/scope, duplicate metadata,
gate counters, report lifecycle, fingerprint status, overwrite staging/commit và các edge case
quarantine.

Mọi điểm chưa rõ trong Technical Context đã được giải quyết dưới đây. Không còn
`NEEDS CLARIFICATION`.

## R-001 — Ngôn ngữ, đóng gói và giao diện CLI

- **Decision**: Python 3.11+; package `detection` theo src layout; khai báo trong `pyproject.toml`
  với entry point `detection`. Lệnh `detection prepare` nhận `--source PATH` (bắt buộc) và
  `--output PATH` (mặc định `data/processed/neu-det`). Không có yêu cầu dataset nguồn phải nằm
  trong `data/raw`.
- **Rationale**: Toàn bộ hệ sinh thái YOLOv8/Ultralytics dùng Python; src layout tách mã nguồn
  khỏi dữ liệu và test. Đường dẫn nguồn/đầu ra tùy ý cho phép chạy trên dataset ở ổ đĩa hoặc
  mount khác mà không phải sao chép vào repo. `data/raw` chỉ là quy ước cũ, không phải ràng buộc.
- **Alternatives considered**: Script rời (`scripts/*.py`) — khó tái sử dụng và kiểm thử; package
  phẳng ở thư mục gốc — trộn với `data/`, `configs/`; bắt buộc đặt dataset trong `data/raw` —
  không cần thiết và dễ gây copy dữ liệu lớn.

## R-002 — Discover dataset và phạm vi ghép ảnh–XML

- **Decision**: `--source` là thư mục gốc chứa một hoặc nhiều subset. Mỗi subset có cấu trúc
  `images/` và `annotations/` (ví dụ `train/` và `validation/`). Nếu source trực tiếp có
  `images/` và `annotations/`, coi đó là một single-subset. Ảnh và XML chỉ được ghép khi:
  1. Cùng một subset nguồn;
  2. Stem giống hệt nhau (so sánh chính xác, không fuzzy, không case-insensitive);
  3. Mỗi stem có đúng một ảnh và đúng một XML trong subset đó.

  Không dùng trường `<filename>` trong XML để tìm ảnh, không tìm XML ở subset khác, không tự
  đổi tên hay tạo file còn thiếu.
- **Rationale**: NEU-DET gốc thường có `train/` và `validation/` riêng. Ghép chéo subset có thể
  tạo ra cặp ảnh–nhãn không tồn tại trong dữ liệu gốc, gây rò rỉ hoặc nhãn sai. Exact stem là quy
  tắc đơn giản, kiểm tra được và không che giấu lỗi dữ liệu.
- **Alternatives considered**: Ghép theo `<filename>` — trường này có thể sai hoặc trỏ sang subset
  khác; fuzzy matching tên — dễ ghép nhầm; tìm XML toàn dataset — vi phạm yêu cầu không ghép chéo;
  tự sinh XML rỗng — che giấu dữ liệu thiếu.

## R-003 — Xác thực ảnh và fingerprint nội dung

- **Decision**: Dùng Pillow để mở/verify ảnh và lấy kích thước thật; tính SHA-256 trên nội dung
  ảnh cho mọi ảnh đọc được. Ảnh hỏng là `corrupt_image` (error). Không sửa ảnh.
  - Orchestrator sample validation (T020) so `<size>` với kích thước thật; nếu lệch, ghi warning
    `size_mismatch` với `paths` gồm cả ảnh và XML, và dùng kích thước thật để chuẩn hóa.
  - Orchestrator cũng so basename `<filename>` với tên ảnh đã ghép; nếu khác, ghi warning
    `filename_mismatch` với cả hai path. Không dùng `<filename>` để đổi cặp.
  - Converter và image verifier không tự tạo hai anomaly này để tránh trùng logic/ownership.
- **Rationale**: Pillow đã có trong môi trường (12.3.0), xử lý được JPEG/PNG/BMP và phát hiện ảnh
  hỏng. SHA-256 là cơ sở phát hiện ảnh trùng nội dung, kể cả khác tên hoặc khác subset.
  `imghdr` đã bị loại bỏ khỏi Python mới; OpenCV quá nặng.
- **Alternatives considered**: OpenCV — thêm dependency lớn; chỉ kiểm tra phần mở rộng tệp — không
  phát hiện ảnh hỏng; dùng kích thước trong XML — có thể sai và làm bbox hợp lệ giả.

## R-004 — Quy ước nhãn YOLO

- **Decision**: Mỗi dòng `class_id cx cy w h`, tọa độ chuẩn hóa theo chiều rộng/chiều cao ảnh,
  giữ 6 chữ số thập phân; `class_id` theo thứ tự cố định 0–5. Ảnh có nhiều object tạo nhiều dòng,
  thứ tự dòng theo thứ tự `<object>` trong XML. Ảnh không có object tạo tệp nhãn rỗng (0 byte).
- **Rationale**: Đúng định dạng Ultralytics YOLOv8 mong đợi, ổn định khi so sánh và tái lập.
  Giữ thứ tự XML giúp diff giữa các lần chạy dễ đọc.
- **Alternatives considered**: Lưu tọa độ tuyệt đối — không phải định dạng YOLO; làm tròn 2 chữ số
  — mất độ chính xác với lỗi nhỏ; sắp xếp lại object — không cần thiết và làm khó đối chiếu.

## R-005 — Class mapping cố định

- **Decision**: Một danh sách chuẩn duy nhất, bất biến, dùng chung cho convert, split, manifest
  và feature 002:

  | ID | Tên lớp |
  |----|---------|
  | 0 | `crazing` |
  | 1 | `inclusion` |
  | 2 | `patches` |
  | 3 | `pitted_surface` |
  | 4 | `rolled-in_scale` |
  | 5 | `scratches` |

  Chuẩn hóa tên nguồn bằng `strip()` + `lower()`. Tên không khớp sau chuẩn hóa là lỗi chặn
  `unknown_class`; không fuzzy matching, không tự gán sang lớp khác, không đổi thứ tự.
- **Rationale**: Constitution yêu cầu 6 lớp cố định và không tự gán lớp. Một hằng số duy nhất
  tránh lệch thứ tự giữa các module và bảo đảm `dataset.yaml` của feature 002 dùng đúng mapping.
- **Alternatives considered**: Fuzzy matching / ánh xạ gần đúng — có thể gán sai lớp và vi phạm
  Constitution; hard-code rải rác trong nhiều module — dễ lệch thứ tự.

## R-006 — Chính sách bất thường và validation report

- **Decision**: Phân loại bất thường thành `error` (chặn), `warning` (không chặn) và `info`.
  Mọi bất thường được ghi vào `validation_report.json` tại thư mục output, kể cả khi pipeline
  dừng. Mặc định `--on-anomaly fail`: dừng trước khi chia split nếu có `error`. Tùy chọn
  `--on-anomaly quarantine`: sample lỗi bị loại khỏi split, được **copy** sang `rejected/` và
  ghi đầy đủ trong report; dữ liệu nguồn không bị di chuyển hay xóa.

  Các mã bất thường tối thiểu:

  | Mã | Mức | Điều kiện |
  |----|-----|-----------|
  | `missing_xml` | error | Ảnh không có XML cùng stem trong cùng subset |
  | `missing_image` | error | XML không có ảnh cùng stem trong cùng subset |
  | `ambiguous_pairing` | error | Một stem có nhiều ảnh hoặc nhiều XML trong cùng subset |
  | `invalid_xml` | error | XML không parse được hoặc thiếu cấu trúc bắt buộc |
  | `unknown_class` | error | Tên lớp không thuộc 6 lớp sau chuẩn hóa |
  | `invalid_bbox` | error | Bbox không phải số, âm, zero-size, ngược trục hoặc vượt biên |
  | `corrupt_image` | error | Pillow không verify/đọc được ảnh |
  | `empty_annotation` | info | XML hợp lệ nhưng không có object; ảnh vẫn được giữ với nhãn rỗng |
  | `size_mismatch` | warning | `<size>` trong XML khác kích thước ảnh thật |
  | `filename_mismatch` | warning | `<filename>` trong XML khác tên ảnh; không dùng để đổi cặp |
  | `duplicate_content` | warning/error | Cùng SHA-256; warning nếu nhãn nhất quán, error nếu xung đột |
  | `split_distribution_deviation` | warning | Nhóm trùng nguyên tử khiến tỷ lệ split lệch mục tiêu |
  | `split_class_absent` | warning | Một lớp không có mặt trong một split |
  | `source_tree_changed` | error | Fingerprint nguồn sau chạy khác trước chạy |
  | `unsupported_file` | info | Tệp không phải ảnh/XML được bỏ qua và ghi nhận |

  Quy tắc bổ sung:

  - **Gate counters**: `blocking_errors` = số anomaly record severity `error`; `warnings` = số
    record severity `warning`; `info` không cộng vào counter nào. `pass` yêu cầu
    `blocking_errors == 0`; `pass_with_quarantine` có thể có `blocking_errors > 0` vì error đã
    được quarantine xử lý; `fail` có thể có `blocking_errors == 0` khi nguyên nhân là fingerprint
    `unavailable` hoặc verify I/O failure.
  - **Unpaired trong quarantine**: unpaired image/annotation vẫn là error chặn, được ghi report
    và loại khỏi interim dataset nhưng không copy sang `rejected/`. Nếu còn ít nhất một sample
    paired eligible, gate `pass_with_quarantine` và exit `0`; nếu không, gate `fail`, exit `3`.
  - **All-quarantined**: nếu quarantine loại toàn bộ sample paired, gate `fail`, exit `3`, output
    gồm report + `rejected/`, không có `images/`, `labels/` hay manifest; accounting vẫn đủ.
  - **Anomaly ordering**: sắp xếp ổn định theo `code`, `paths`, `sample_id` (null cuối),
    `details.object_index` (thiếu cuối), `reason`. Không phụ thuộc thứ tự phát hiện.
  - **Report lifecycle**: first write sau validate/gate, trước khi ghi dataset; final update sau
    verify. Report ghi nguyên tử; report-write failure là exit `5`.
  - **Filename/size**: `filename_mismatch` và `size_mismatch` do orchestrator tạo; `filename_mismatch`
    không đổi pairing, `size_mismatch` dùng kích thước thật.

- **Rationale**: Đáp ứng FR-005, FR-007, FR-009 và tinh thần "báo cáo và yêu cầu xác nhận" của
  Constitution. Người dùng chủ động chọn fail hay quarantine; không có bỏ qua im lặng. Counter
  theo record giúp report tự giải thích trạng thái gate, kể cả khi error đã được quarantine.
- **Alternatives considered**: Tự động bỏ qua mẫu lỗi — vi phạm nguyên tắc không loại bỏ âm thầm;
  tự động clip bbox — che giấu lỗi annotation; tự tạo XML/ảnh còn thiếu — thay đổi dữ liệu gốc
  hoặc tạo cặp không có thật; đếm gate theo sample — không khớp với danh sách anomaly record.

## R-007 — Chiến lược chia split 75/15/10 phân tầng đa nhãn

- **Decision**:
  - Pool chia gồm các `MatchedSample` đã ghép đúng trong từng subset nguồn; mỗi sample là đơn
    vị nguyên tử (ảnh + XML đi cùng nhau). Chia lại 75/15/10 không phải ghép xuyên subset.
  - Tỷ lệ mặc định **75/15/10** cho train/validation/test; seed mặc định **42**; cả hai ghi vào
    manifest. Với **1.800 sample hợp lệ**, mục tiêu largest-remainder là **1350/270/180** ảnh.
    Trên bộ NEU-DET thực tế, sau khi quarantine `patches_101` và `patches_105` còn 1.798 sample
    hợp lệ nên kết quả là **1348/270/180**.
  - Mỗi sample được biểu diễn bằng `present_classes`: tập hợp tất cả class ID xuất hiện trong
    ảnh (không phải chỉ lớp đầu tiên).
  - Kích thước từng split được chốt bằng largest-remainder trên tổng số sample hợp lệ, tie-break
    theo thứ tự `train`, `validation`, `test`.
  - Ảnh không có object có `present_classes = []`; vẫn tham gia split, được phân bổ theo dung
    lượng còn lại với tie-break tất định, và ghi `empty_annotation` mức `info`.
  - Phân bổ dùng multi-label iterative stratification: ưu tiên lớp hiếm, tính "nhu cầu" còn lại
    của từng split cho mỗi lớp, chọn split có tổng nhu cầu cao nhất; tie-break bằng
    `random.Random(seed)` cục bộ và `sample_id` đã sắp xếp.
  - Ảnh trùng nội dung được gom thành nhóm và gán nguyên tử vào một split (xem R-013).
  - Nếu một nhóm trùng quá lớn khiến không thể đạt đúng mục tiêu 75/15/10 mà vẫn giữ nguyên
    tử, ưu tiên atomicity, ghi warning `split_distribution_deviation` và ghi tỷ lệ thực tế.
  - Sau chia, kiểm tra: tổng đúng, phủ đầy sample hợp lệ, giao theo `sample_id` / output path /
    SHA-256 rỗng.
- **Rationale**: Một ảnh có thể chứa nhiều lớp; phân tầng theo "lớp chính" sẽ làm lệch phân bố
  của các lớp phụ và có thể khiến một lớp hiếm rơi hết vào một split. Multi-label stratification
  giữ phân bố từng lớp gần tỷ lệ mục tiêu, đồng thời bảo đảm chống rò rỉ ảnh trùng.
- **Alternatives considered**: Chia ngẫu nhiên thuần — mất cân bằng lớp; phân tầng theo lớp đầu
  tiên — bỏ qua các lớp còn lại trong ảnh; chia theo hash tên tệp — tất định nhưng không kiểm
  soát tỷ lệ lớp; dùng `skmultilearn` — thêm dependency không cần thiết.

## R-008 — Định dạng manifest và báo cáo

- **Decision**: JSON có `schema_version` cho `split_manifest.json` và `validation_report.json`.
  Dùng `json` chuẩn, ghi nguyên tử (ghi tệp tạm rồi `os.replace`). Manifest chứa class mapping,
  seed, tỷ lệ, thuật toán split, fingerprint nguồn, thống kê theo split/lớp và danh sách sample.
  Report chứa cấu hình, summary, gate, anomaly list và trạng thái xác minh nguồn.
  - Report được ghi lần đầu sau validate/duplicate audit/gate và sau fingerprint check, trước
    khi ghi ảnh/nhãn; được cập nhật lần cuối sau write/verify.
  - Khi source thay đổi/verify thất bại, report được cập nhật với lỗi và gate `fail` nếu còn ghi
    được.
  - Không ghi được report ở bất kỳ lần nào là exit `5`; không ghi manifest.
- **Rationale**: Dễ đọc bằng máy, không cần PyYAML, phù hợp lưu kết quả và so sánh giữa các lần
  chạy. Ghi nguyên tử tránh manifest/report bị cắt cụt khi lỗi giữa chừng. Vòng đời hai lần ghi
  giúp report tồn tại ngay cả khi run dừng, đồng thời phản ánh đúng số sample thực tế đã ghi.
- **Alternatives considered**: YAML — thêm dependency; CSV — khó biểu diễn cấu trúc lồng nhau
  (counts theo lớp và split); ghi trực tiếp — có thể hỏng tệp nếu tiến trình dừng.

## R-009 — Tính tất định

- **Decision**: Duyệt tệp theo thứ tự sắp xếp (`sample_id`); dùng `random.Random(seed)` cục bộ
  thay vì trạng thái ngẫu nhiên toàn cục; sắp xếp danh sách trước khi ghi; không dùng timestamp
  trong dữ liệu quyết định split (timestamp chỉ ghi ở metadata). Cùng dataset + cấu hình + seed
  phải cho cùng danh sách sample trong từng split.
- **Rationale**: FR-013 và SC-006 yêu cầu chạy lại cho kết quả giống hệt; thứ tự không ổn định
  là nguyên nhân phổ biến làm split thay đổi giữa các lần chạy.
- **Alternatives considered**: `random.shuffle` toàn cục — phụ thuộc thứ tự gọi; `hash()` của
  Python — không ổn định giữa các tiến trình do hash randomization; timestamp làm seed — không
  tái lập được.

## R-010 — Kiểm thử

- **Decision**: pytest với unit test cho `classes`, `converter`, `validator`, `splitter`,
  `manifest` và integration test cho toàn pipeline; tạo mẫu VOC nhỏ trong `tmp_path` thay vì
  commit dữ liệu mẫu. Bắt buộc có test cho:
  1. Ảnh thiếu XML (`missing_xml`), XML thiếu ảnh (`missing_image`).
  2. Ảnh và XML cùng stem nhưng khác subset — không được ghép, cả hai báo thiếu cặp.
  3. Bbox không hợp lệ: zero-size, ngược trục, âm, vượt biên, không phải số.
  4. Một ảnh nhiều object thuộc nhiều lớp: đủ dòng nhãn, `present_classes` đầy đủ.
  5. Ảnh trùng nội dung giữa các subset: cùng nhóm, cùng split, không rò rỉ SHA-256.
  6. Split 75/15/10, seed cố định, chạy lại giống hệt, disjoint.
  7. Nguồn bất biến: hash cây nguồn trước/sau giống nhau.
  8. CLI với `--source`/`--output` ngoài `data/raw`.
  9. Report schema: đủ field, zero-valued anomaly counts, accounting, gate counters, anomaly
     ordering.
  10. Duplicate: một anomaly/member, metadata nhóm, consistent warning, conflict error/quarantine
      toàn nhóm.
  11. Quarantine: rejected mirror path, unpaired không copy, pass_with_quarantine khi còn sample
      eligible, all-quarantined fail.
  12. Overwrite: dataset cũ không mất khi run mới fail, report-only output, retry exit `4`/thay
      report an toàn.
  13. Fingerprint: unchanged/changed/unavailable; không tạo `source_tree_changed` giả.
  14. Report lifecycle: first write trước dataset, final update sau verify, report-write failure
      exit `5`.
  15. `filename_mismatch` và `size_mismatch` có cả ảnh + XML path; pairing không đổi.
  16. Pairing-specific tests nằm trong `test_discovery.py`; `test_validator.py` test orchestration,
      không lặp lại discovery tests.
- **Rationale**: Không tăng kích thước repo, kiểm soát được từng tình huống bất thường, chạy
  nhanh và độc lập với dataset thật. Các test trên khóa chặt các yêu cầu mới.
- **Alternatives considered**: Commit ảnh mẫu — tăng dung lượng và khó bao phủ lỗi hiếm; test
  trên dataset thật — chậm, không tất định, phụ thuộc môi trường.

## R-011 — Hiệu năng, copy ảnh và bất biến nguồn

- **Decision**: Xử lý tuần tự; chỉ đọc metadata ảnh và hash nội dung. Ảnh đầu ra được **copy**
  sang thư mục đã xử lý; không dùng hard link hoặc symlink. Fingerprint toàn bộ cây nguồn
  (đường dẫn tương đối + SHA-256 nội dung) trước khi chạy và xác minh lại sau khi chạy.
  Không cần GPU.
- **Rationale**: 1.800 ảnh không cần song song hóa; copy bảo đảm tuyệt đối rằng mọi thay đổi
  trên output về sau không thể ghi ngược vào inode của dữ liệu gốc. Hard link tiết kiệm dung
  lượng nhưng tạo rủi ro sửa nguồn ngoài ý muốn; symlink có thể đứt khi di chuyển thư mục.
- **Alternatives considered**: Hard link — rủi ro ghi ngược nguồn; symlink — không độc lập và
  dễ đứt; đa tiến trình — phức tạp không cần thiết.

## R-012 — Phụ thuộc cho feature sau

- **Decision**: Không thêm Ultralytics/PyYAML trong feature này. `dataset.yaml` và huấn luyện
  thuộc feature 002.
- **Rationale**: Giữ phạm vi hẹp, tránh cài đặt nặng khi chưa cần. Môi trường hiện tại là
  Python 3.14.9; khi làm feature 002 cần kiểm tra khả năng tương thích của Ultralytics và có thể
  cần Python 3.11/3.12.
- **Alternatives considered**: Cài sẵn toàn bộ stack — tăng rủi ro xung đột dependency trước khi
  cần.

## R-013 — Phát hiện ảnh trùng và chống rò rỉ

- **Decision**: Tính SHA-256 nội dung ảnh. Chỉ audit các sample **eligible** đã validate thành
  công; gom các ảnh cùng hash (nhóm >= 2 member) thành `DuplicateGroup`.
  - Mỗi member nhận đúng một anomaly `duplicate_content`; `details` gồm `group_id`, `sha256`,
    `member_count`, `labels_consistent`; `paths` gồm ảnh và XML của member.
  - `labels_consistent` so **multiset** `(class_id, cx, cy, w, h)` sau chuẩn hóa và làm tròn 6
    chữ số; thứ tự `<object>` trong XML không tham gia so sánh.
  - Nhất quán: warning; giữ nguyên nhóm và gán nguyên tử vào một split.
  - Xung đột: error cho toàn bộ member; `fail` mode dừng exit `3`; `quarantine` mode loại và copy
    toàn nhóm sang `rejected/`. Mọi member đều được đếm trong accounting.
  - `DuplicateGroup` chỉ giữ trong bộ nhớ cho US3; report không có trường top-level
    `duplicate_groups` (manifest US3 mới ghi).
  - Sau chia, kiểm tra không có SHA-256 nào xuất hiện ở hai split.
- **Rationale**: Ảnh trùng nội dung ở hai split là rò rỉ dữ liệu trực tiếp, làm đánh giá test
  không trung thực. Gom nhóm nguyên tử vừa bảo toàn dữ liệu vừa chặn rò rỉ. Một anomaly/member
  giúp report giải thích được từng sample thay vì chỉ một đại diện nhóm.
- **Alternatives considered**: Loại bỏ bản trùng — vi phạm nguyên tắc không loại bỏ im lặng và
  làm mất mẫu; để chúng phân bố ngẫu nhiên — rò rỉ; chỉ so sánh tên tệp — bỏ sót ảnh đổi tên;
  chỉ so `present_classes` — bỏ sót xung đột tọa độ cùng lớp; so theo thứ tự object — báo xung
  đột giả khi XML đảo thứ tự.

## R-014 — Tên tệp output và xung đột tên

- **Decision**: Tên output ưu tiên giữ nguyên stem nguồn. Nếu stem không duy nhất trên toàn bộ
  dataset đầu ra, dùng `<source_subset>_<stem>`; nếu vẫn trùng, thêm 8 ký tự đầu của SHA-256.
  Ánh xạ `source_image` → `output_image` được ghi trong manifest. Không đổi tên tệp nguồn.
- **Rationale**: NEU-DET có thể có cùng tên file ở `train/` và `validation/`; ghi đè output sẽ
  làm mất mẫu. Quy tắc deterministic giúp chạy lại cho cùng tên tệp.
- **Alternatives considered**: Giữ nguyên tên và để ghi đè — mất dữ liệu; luôn prefix toàn bộ —
  tên dài và khó đọc; dùng UUID — không tất định.

## R-015 — Fingerprint nguồn

- **Decision**: Trước khi xử lý, tính fingerprint của cây nguồn: danh sách tệp được sắp xếp theo
  đường dẫn tương đối, mỗi mục gồm đường dẫn + kích thước + SHA-256 nội dung; fingerprint tổng
  là SHA-256 của danh sách đó. Ghi vào report/manifest.
  - Tính lại sau validate, **kể cả khi gate sẽ `fail`**, và tính lại lần cuối sau write/verify
    trên đường thành công.
  - `status = verified_unchanged` khi khớp; `verified_after_run = true`.
  - `status = changed` khi khác; `changed` liệt kê khác biệt, report có `source_tree_changed`
    error, exit `3`.
  - `status = unavailable` khi không hoàn tất được phép kiểm tra vì lỗi I/O; `changed` rỗng,
    `error` mô tả lỗi, gate `fail`, exit `5`. Không tạo `source_tree_changed` và không coi là
    bằng chứng nguồn đã đổi.
- **Rationale**: SC-004 yêu cầu checksum nguồn trước/sau giống nhau; fingerprint cấp cây phát
  hiện cả tệp bị sửa, thêm, đổi tên hoặc xóa. Ba trạng thái tránh báo sai "source changed" khi
  thực chất chỉ là lỗi đọc/ổ đĩa.
- **Alternatives considered**: Chỉ hash ảnh — bỏ sót XML bị sửa; chỉ dùng mtime/size — không đủ
  tin cậy; không kiểm tra — không chứng minh được bất biến nguồn; dùng boolean duy nhất — không
  phân biệt changed với unavailable.

## R-016 — Accounting ảnh nguồn

- **Decision**: Report có `unwritten_samples` và dùng công thức:

  ```text
  accounted_images =
      written_samples + quarantined_samples + unwritten_samples + unpaired_images
  accounting_ok = accounted_images == source_images
  ```

  - `written_samples`: sample paired đã ghi interim dataset.
  - `quarantined_samples`: sample paired bị loại và copy sang `rejected/`.
  - `unwritten_samples`: mọi sample paired chưa ghi và không quarantine tại thời điểm report —
    sample lỗi trong `fail` mode, sample bị chặn bởi gate/source change/verify failure, và sample
    đang chờ ghi ở report đầu tiên.
  - `unpaired_images`: ảnh nguồn không tạo được sample.
  - `unpaired_annotations` chỉ báo phía XML, không cộng vào `accounted_images`.
  - `accounting_ok = false` chặn ghi output/manifest.
  - Accounting phải đúng ở mọi lần ghi report; first write tính sample chưa ghi vào
    `unwritten_samples`, final update chuyển chúng sang `written_samples`.
- **Rationale**: SC-001 yêu cầu mọi ảnh nguồn được giải thích. Nếu chỉ dùng
  `written + quarantined + unpaired`, fail mode sẽ làm mất dấu các sample paired không được ghi.
- **Alternatives considered**: Dùng `eligible_samples` thay `written_samples` — sai khi verify/write
  thất bại; đếm XML vào `accounted_images` — trộn đơn vị ảnh và XML; bỏ `unwritten_samples` —
  report không cân.

## R-017 — Rejected layout và scope

- **Decision**: Trong `quarantine` mode, chỉ sample paired lỗi được copy:

  ```text
  rejected/images/<source_subset>/<relative-path>
  rejected/annotations/<source_subset>/<relative-path>
  ```

  Dùng `shutil.copy2`; giữ ảnh gốc và XML gốc; không tạo nhãn YOLO; không move/delete nguồn.
  Unpaired image/annotation chỉ được ghi report và loại khỏi interim dataset, không copy.
  Đường dẫn tương đối vốn duy nhất trong một subset; nếu filesystem chuẩn hóa gây trùng, bản đầu
  giữ nguyên path, bản sau thêm `__<8 ký tự SHA-256>` và ghi quyết định vào `details`.
- **Rationale**: Giữ nguyên layout giúp điều tra lỗi đối chiếu trực tiếp với nguồn; không copy
  unpaired tránh tạo cảm giác "đã xử lý" cho asset chưa từng là sample.
- **Alternatives considered**: Copy tất cả asset lỗi — lẫn unpaired, khó phân biệt; đổi tên theo
  output naming — mất liên hệ với nguồn; nén/bundle — khó kiểm tra thủ công.

## R-018 — Overwrite staging/commit và retry

- **Decision**: Pipeline luôn dựng artifact trong staging trước khi commit; `--overwrite` không xóa
  dataset cũ trước khi run mới qua validate/gate.
  - Dựng artifact mới trong `<output>.staging` cùng cấp.
  - Khi commit, chuyển artifact cũ do pipeline sở hữu sang `<output>.previous`, rồi chuyển
    artifact mới vào output; tệp không liên quan trong output được giữ.
  - Failure output:
    - `fail` mode: chỉ `validation_report.json`.
    - All-quarantined: report + `rejected/`.
    - Source change / verify / split-invariant failure: report-only với gate `fail`, dataset cũ
      chuyển sang `<output>.previous`; ảnh/nhãn mới không commit.
  - Retry không `--overwrite`: output không rỗng → exit `4`, dataset cũ ở `<output>.previous`.
  - Retry có `--overwrite`: thay report-only an toàn; không đụng backup dataset cũ cho tới khi
    commit thành công.
  - Report-write/commit failure: exit `5`; không ghi manifest; backup vẫn giữ dataset cũ.
- **Rationale**: FR-014 yêu cầu xác nhận trước khi ghi đè, nhưng không được biến một input lỗi
  thành mất dataset hợp lệ. Staging/commit tách "chuẩn bị" khỏi "thay thế".
- **Alternatives considered**: Xóa output ngay khi bắt đầu — mất dữ liệu nếu validate fail; ghi
  trực tiếp đè từng file — output trộn hai lần chạy; đổi tên output cũ thành timestamp — khó
  đoán và không cần thiết.
