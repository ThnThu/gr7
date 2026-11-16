# Feature Specification: Chuẩn bị dữ liệu NEU-DET cho Object Detection

**Feature Branch**: `001-neu-det-data-preparation`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Chuẩn bị dữ liệu NEU-DET: chuyển annotation XML sang YOLO, kiểm tra class mapping/bounding boxes, chia train/val/test và ghi nhận dữ liệu bất thường."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chuyển annotation nguồn sang định dạng huấn luyện detection (Priority: P1)

Thành viên phụ trách dữ liệu cần biến bộ NEU-DET gốc thành một bộ dữ liệu sẵn sàng cho
Object Detection, trong đó mỗi ảnh có file nhãn tương ứng chứa đúng lớp lỗi và vùng lỗi,
mà không làm thay đổi bất kỳ tệp nào của bộ dữ liệu gốc.

**Why this priority**: Đây là đầu vào bắt buộc của toàn bộ module. Không có dữ liệu được
chuyển đổi đúng thì không thể huấn luyện hay đánh giá YOLOv8s. Hoàn thành story này đã tạo
ra giá trị tối thiểu: một bộ dữ liệu detection dùng được, tách biệt hoàn toàn với dữ liệu gốc.

**Independent Test**: Chạy quy trình chuyển đổi trên bộ NEU-DET gốc và kiểm tra rằng mỗi ảnh
nguồn có đúng một file nhãn tương ứng, mọi nhãn đều thuộc 6 lớp lỗi đã thống nhất, và dấu vân
tay (checksum) của thư mục dữ liệu gốc không thay đổi trước và sau khi chạy.

**Acceptance Scenarios**:

1. **Given** bộ NEU-DET gốc còn nguyên vẹn, **When** chạy quy trình chuyển đổi, **Then** toàn
   bộ ảnh và annotation được ghi vào thư mục dữ liệu đã xử lý riêng, và thư mục gốc không bị
   sửa đổi.
2. **Given** một annotation có nhiều đối tượng lỗi, **When** chuyển đổi, **Then** file nhãn
   chứa đủ số dòng đối tượng, mỗi dòng gồm chỉ số lớp và tọa độ vùng lỗi chuẩn hóa.
3. **Given** một ảnh không có đối tượng lỗi, **When** chuyển đổi, **Then** hệ thống tạo file
   nhãn rỗng hợp lệ, giữ ảnh trong bộ dữ liệu và đưa mục đó vào báo cáo xử lý.

---

### User Story 2 - Kiểm tra tính toàn vẹn dữ liệu trước khi huấn luyện (Priority: P2)

Thành viên phụ trách dữ liệu cần một báo cáo kiểm tra cho biết class mapping có đúng không,
bounding boxes có hợp lệ không, ảnh/annotation nào bị thiếu hoặc bất thường, để phát hiện và
sửa lỗi trước khi tốn thời gian huấn luyện.

**Why this priority**: Lỗi dữ liệu âm thầm (sai lớp, hộp bao vượt biên, thiếu cặp ảnh–nhãn)
sẽ làm kết quả huấn luyện sai lệch mà khó truy nguyên. Kiểm tra trước là điều kiện bắt buộc
theo Constitution của module.

**Independent Test**: Cố ý đưa vào các mẫu lỗi đã biết (lớp không tồn tại, hộp bao vượt biên,
annotation thiếu ảnh) và xác nhận báo cáo liệt kê đúng từng mẫu, đúng vị trí, đúng loại lỗi,
đồng thời không có mẫu hợp lệ nào bị báo sai.

**Acceptance Scenarios**:

1. **Given** một annotation chứa tên lớp không thuộc 6 lớp lỗi của NEU-DET, **When** kiểm tra,
   **Then** mục đó được báo là lỗi class mapping và quy trình dừng hoặc đánh dấu để xử lý,
   không tự động gán sang lớp khác.
2. **Given** một bounding box vượt ra ngoài biên ảnh hoặc có kích thước bằng 0, **When** kiểm
   tra, **Then** mục đó được ghi vào báo cáo bất thường kèm tên ảnh và tọa độ gốc.
3. **Given** một ảnh không có annotation hoặc một annotation không có ảnh, **When** kiểm tra,
   **Then** cặp không khớp được liệt kê rõ ràng trong báo cáo.
4. **Given** tất cả dữ liệu hợp lệ, **When** kiểm tra, **Then** báo cáo kết luận đạt và không
   còn cảnh báo chặn huấn luyện.
5. **Given** hai ảnh có cùng nội dung và nhãn nhất quán, **When** kiểm tra, **Then** báo cáo ghi
   nhận nhóm trùng ở mức cảnh báo, giữ cả hai mẫu và không làm mất thông tin nhóm.
6. **Given** hai ảnh có cùng nội dung nhưng nhãn xung đột, **When** kiểm tra, **Then** toàn bộ
   nhóm được báo là lỗi chặn; ở chế độ quarantine, cả nhóm được đưa vào khu vực cách ly thay vì
   chỉ một đại diện.
7. **Given** chế độ quarantine và còn ít nhất một mẫu ghép hợp lệ, **When** có mẫu lỗi và asset
   không ghép được, **Then** mẫu lỗi được sao chép vào khu vực cách ly theo đúng vị trí nguồn,
   asset không ghép chỉ được báo cáo, và quy trình vẫn kết luận đạt kèm cách ly.
8. **Given** chế độ quarantine và không còn mẫu ghép hợp lệ nào, **When** kiểm tra, **Then** quy
   trình kết luận thất bại, nhưng báo cáo và bản sao cách ly vẫn được tạo theo đúng chính sách.
9. **Given** một lần chạy thất bại khi thư mục đầu ra đã có dữ liệu hợp lệ, **When** ghi đè,
   **Then** dữ liệu hợp lệ cũ không bị mất và thư mục đầu ra không bị hiểu nhầm là kết quả của
   lần chạy lỗi.
10. **Given** báo cáo của một lần chạy, **When** đọc phần tổng hợp, **Then** việc phân loại và
    đối soát mọi ảnh nguồn tuân theo yêu cầu accounting chuẩn tắc của FR-008 và
    `accounting_ok = true`.

---

### User Story 3 - Tạo split tái lập và bản ghi dữ liệu đã xử lý (Priority: P3)

Thành viên nhóm cần chia dữ liệu thành train/validation/test theo cách tái lập được, có bản
ghi (manifest) mô tả từng split, để mọi người huấn luyện và đánh giá trên cùng một cách chia
và không xảy ra rò rỉ dữ liệu giữa các split.

**Why this priority**: Kết quả chỉ so sánh được khi cách chia dữ liệu ổn định. Đây là nền tảng
cho đánh giá trung thực ở giai đoạn sau, nhưng có thể triển khai sau khi đã có dữ liệu sạch.

**Independent Test**: Chạy tạo split hai lần với cùng cấu hình và seed, xác nhận danh sách ảnh
trong từng split giống nhau 100%; kiểm tra không có ảnh nào xuất hiện ở nhiều hơn một split.

**Acceptance Scenarios**:

1. **Given** dữ liệu đã chuyển đổi và kiểm tra hợp lệ, **When** tạo split, **Then** mỗi ảnh
   thuộc đúng một split trong train/validation/test và tỷ lệ xấp xỉ cấu hình đã chọn.
2. **Given** cùng dữ liệu, cấu hình và seed, **When** tạo split lại, **Then** kết quả phân bổ
   ảnh giống hệt lần trước.
3. **Given** một split đã tạo, **When** mở manifest, **Then** thấy được danh sách ảnh, số lượng
   theo lớp, tỷ lệ split, seed và thời điểm tạo.

---

### Edge Cases

- Annotation trỏ tới ảnh không tồn tại, hoặc ảnh không có annotation đi kèm.
- File annotation rỗng hoặc không đọc được (hỏng, sai định dạng).
- Tên lớp không thuộc 6 lớp NEU-DET, hoặc khác nhau chỉ bởi chữ hoa/chữ thường/khoảng trắng.
- Bounding box vượt biên ảnh, có chiều rộng/chiều cao bằng 0 hoặc âm, hoặc nằm ngoài hoàn toàn.
- Ảnh trùng lặp hoặc tên tệp trùng giữa các thư mục nguồn.
- Ảnh trùng nội dung nhưng nhãn xung đột; một nhóm trùng có thể bị cách ly toàn bộ.
- Metadata `<filename>` trong XML khác tên ảnh đã ghép; cặp ghép vẫn giữ nguyên và chỉ cảnh báo.
- Ảnh hỏng hoặc không đọc được nhưng vẫn có annotation.
- Thư mục dữ liệu đã xử lý đã tồn tại từ lần chạy trước, kể cả khi lần trước chỉ tạo báo cáo.
- Thư mục đầu ra tồn tại nhưng rỗng: được phép dùng mà không cần `--overwrite`.
- Ghi đè thất bại giữa chừng hoặc không ghi được báo cáo.
- Source thay đổi trong lúc chạy, hoặc không đọc được để kiểm tra lại checksum.
- Dataset có lớp hiếm hoặc mất cân bằng khiến split ngẫu nhiên không giữ được tỷ lệ lớp.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST đọc bộ dữ liệu NEU-DET gốc và xác định được toàn bộ ảnh cùng
  annotation đi kèm.
- **FR-002**: Hệ thống MUST chuyển đổi annotation nguồn sang định dạng nhãn Object Detection
  (chỉ số lớp và tọa độ bounding box chuẩn hóa) mà không thay đổi nội dung bộ dữ liệu gốc.
- **FR-003**: Hệ thống MUST ghi toàn bộ dữ liệu đã chuyển đổi vào một thư mục đã xử lý riêng,
  tách biệt với thư mục dữ liệu gốc.
- **FR-004**: Hệ thống MUST ánh xạ tên lớp nguồn sang đúng 6 lớp lỗi NEU-DET: `crazing`,
  `inclusion`, `patches`, `pitted_surface`, `rolled-in_scale`, `scratches`, và MUST giữ nguyên
  thứ tự ánh xạ này giữa chuyển đổi, huấn luyện và đánh giá.
- **FR-005**: Hệ thống MUST từ chối hoặc đánh dấu rõ mọi annotation có tên lớp không nằm trong
  danh sách 6 lớp; MUST NOT tự động gán sang lớp khác.
- **FR-006**: Hệ thống MUST kiểm tra mọi bounding box sau chuyển đổi: tọa độ nằm trong khoảng
  hợp lệ, chiều rộng và chiều cao lớn hơn 0, và hộp bao không vượt biên ảnh.
- **FR-007**: Hệ thống MUST phát hiện và báo cáo các cặp ảnh–annotation không khớp, ảnh hỏng,
  annotation rỗng hoặc không đọc được.
- **FR-008**: Hệ thống MUST tạo báo cáo kiểm tra cho mỗi lần chạy, ghi rõ số lượng ảnh,
  số lượng đối tượng theo lớp, danh sách bất thường kèm đường dẫn và lý do, trạng thái đạt/chặn,
  checksum nguồn và cách phân loại mọi ảnh nguồn thành đã ghi, đã cách ly, chưa ghi hoặc không
  ghép được.
- **FR-009**: Hệ thống MUST không tự động loại bỏ bất kỳ mẫu dữ liệu nào. Nếu một mẫu bị loại,
  hệ thống MUST ghi nhận mẫu đó, lý do loại và tiêu chí áp dụng vào báo cáo. Ở chế độ cách ly,
  chỉ mẫu ghép ảnh–annotation bị lỗi mới được sao chép vào khu vực cách ly theo đúng vị trí
  nguồn; asset không ghép được chỉ được báo cáo và không được sao chép.
- **FR-010**: Hệ thống MUST chia dữ liệu đã xử lý thành train, validation và test, với tỷ lệ
  và seed do người dùng cấu hình.
- **FR-011**: Hệ thống MUST bảo đảm mỗi ảnh chỉ thuộc đúng một split, không có rò rỉ dữ liệu
  giữa train, validation và test.
- **FR-012**: Hệ thống MUST tạo manifest cho bộ dữ liệu đã xử lý, ghi rõ phiên bản cấu hình,
  seed, tỷ lệ split, số lượng ảnh/đối tượng theo split và theo lớp, và thời điểm tạo.
- **FR-013**: Hệ thống MUST cho phép chạy lại quy trình và tạo ra kết quả phân bổ giống hệt
  khi dữ liệu, cấu hình và seed không đổi.
- **FR-014**: Hệ thống MUST từ chối ghi vào thư mục đầu ra đã tồn tại và **không rỗng** khi
  người dùng chưa cung cấp `--overwrite`; MUST in cảnh báo rõ ràng ra stderr và trả exit code
  `4`. `--overwrite` là xác nhận tường minh của người dùng để thay thế output không rỗng. Thư
  mục đầu ra tồn tại nhưng rỗng MUST được chấp nhận mà không cần `--overwrite`. Khi được xác
  nhận, hệ thống MUST không phá hủy dữ liệu hợp lệ cũ trước khi lần chạy mới vượt qua kiểm tra;
  nếu lần chạy mới thất bại, thư mục đầu ra không được giả làm kết quả hợp lệ và dữ liệu cũ vẫn
  phải khôi phục được.
- **FR-015**: Hệ thống MUST báo lỗi rõ ràng và dừng an toàn khi dữ liệu nguồn thiếu, sai cấu
  trúc hoặc không đọc được, thay vì tiếp tục với dữ liệu không đầy đủ.

### Key Entities *(include if feature involves data)*

- **Ảnh nguồn (Source Image)**: ảnh bề mặt thép trong NEU-DET, có định danh duy nhất và thuộc
  bộ dữ liệu gốc chỉ đọc.
- **Annotation nguồn (Source Annotation)**: mô tả vùng lỗi trên ảnh nguồn, gồm tên lớp và
  bounding box gốc.
- **Lớp lỗi (Defect Class)**: một trong 6 lớp NEU-DET; có tên chuẩn, chỉ số lớp cố định và thứ
  tự ánh xạ bất biến.
- **Nhãn đã chuyển đổi (Converted Label)**: biểu diễn vùng lỗi sẵn sàng cho huấn luyện detection,
  gồm chỉ số lớp và tọa độ chuẩn hóa.
- **Bản ghi bất thường (Anomaly Record)**: một vấn đề dữ liệu được phát hiện, gồm đối tượng
  liên quan, loại vấn đề, vị trí và lý do.
- **Split**: tập con train, validation hoặc test; mỗi ảnh chỉ thuộc một split.
- **Manifest dữ liệu**: bản ghi tổng hợp của một lần xử lý, dùng để truy vết và tái lập.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Việc phân loại và đối soát mọi ảnh nguồn tuân theo yêu cầu accounting chuẩn tắc
  của FR-008; mỗi ảnh nguồn được giải thích đúng một lần và `accounting_ok = true` ở mọi lần
  report được ghi.
- **SC-002**: Trong dataset đã ghi thành công, 100% object trong nhãn YOLO phát ra có `class_id`
  thuộc đúng khoảng `0..5`, và số object lớp không xác định trong output là `0`. Mọi object có
  tên lớp không xác định trong annotation nguồn MUST được đếm và báo cáo là `unknown_class`
  trong `validation_report.json`; sample chứa chúng MUST tuân theo chính sách fail/quarantine
  đã chọn và MUST NOT được ghi vào dataset. Tiêu chí này không tuyên bố rằng 100% annotation
  nguồn đã được ánh xạ, vì sample nguồn không hợp lệ có thể bị từ chối hoặc cách ly. Acceptance
  test MUST xác minh: (1) mọi nhãn phát ra có `class_id` hợp lệ; (2) không có object
  unknown-class nào trong output dataset; (3) anomaly unknown-class từ nguồn được đếm và báo
  cáo đúng.
- **SC-003**: 100% bounding box trong dữ liệu đã xử lý hợp lệ về biên và kích thước; số hộp
  bao không hợp lệ còn lại là 0.
- **SC-004**: Checksum của toàn bộ thư mục dữ liệu gốc trước và sau khi chạy là giống nhau.
- **SC-005**: 0 ảnh xuất hiện ở nhiều hơn một split.
- **SC-006**: Chạy lại quy trình với cùng dữ liệu, cấu hình và seed cho ra phân bổ split giống
  nhau 100%.
- **SC-007**: Mỗi lần chạy thành công tạo ra một báo cáo và một manifest đầy đủ; mỗi lần chạy
  thất bại tạo báo cáo giải thích lỗi (khi còn ghi được) và không tạo manifest giả. Một thành
  viên khác có thể đọc manifest để biết chính xác dữ liệu nào được dùng cho split nào, và đọc
  báo cáo để biết mẫu nào bị cách ly/chưa ghi.
- **SC-008**: Smoke test hiệu năng dùng bộ dữ liệu tổng hợp 1.800 ảnh nhỏ (64×64 JPEG) hoàn tất
  pipeline trong vòng 10 phút. Đây là kỳ vọng smoke test không gating, **không** phải cam kết
  hiệu năng trên dataset NEU-DET thật; hiệu năng trên dataset thật không được thiết lập bởi
  smoke test này.

## Assumptions

- Bộ NEU-DET gốc gồm 1.800 ảnh, 6 lớp lỗi (mỗi lớp khoảng 300 ảnh), annotation dạng Pascal VOC
  XML và ảnh JPEG; dữ liệu nguồn ở trạng thái chỉ đọc.
- Tỷ lệ split mặc định là 75% train / 15% validation / 10% test, chia phân tầng theo **tập tất cả
  các lớp xuất hiện trong từng ảnh** (multi-label); seed mặc định là 42. Với 1.800 ảnh, mục tiêu
  tương ứng là 1350 / 270 / 180 ảnh. Tỷ lệ và seed có thể cấu hình nhưng giá trị dùng để
  báo cáo phải được ghi lại.
- Nhóm dùng chung một quy ước tên lớp và thứ tự lớp; thay đổi quy ước này là thay đổi phạm vi
  và phải được phê duyệt.
- Mỗi ảnh có thể chứa một hoặc nhiều đối tượng lỗi; ảnh không có đối tượng vẫn được giữ và
  ghi nhận thay vì tự động loại bỏ.
- Ảnh trùng nội dung được đối xử theo nhóm: nhãn nhất quán thì giữ và cảnh báo, nhãn xung đột
  thì là lỗi chặn và có thể bị cách ly toàn nhóm.
- Khu vực cách ly giữ nguyên vị trí tương đối của ảnh và annotation nguồn để phục vụ điều tra;
  đây là bản sao, không phải di chuyển dữ liệu gốc.
- Ghi đè chỉ thay thế dữ liệu đã xử lý sau khi lần chạy mới vượt qua kiểm tra; dữ liệu hợp lệ cũ
  phải khôi phục được nếu lần chạy mới thất bại.
- Quy trình chỉ chuẩn bị dữ liệu; việc huấn luyện, tăng cường dữ liệu và đánh giá mô hình thuộc
  các feature sau.
- Người dùng là thành viên nhóm có quyền truy cập bộ dữ liệu và thư mục làm việc của module.
- Module Segmentation không được import, không bị phụ thuộc và không bị ảnh hưởng bởi feature này.

## Out of Scope

- Huấn luyện, tinh chỉnh hoặc thay đổi kiến trúc YOLOv8s.
- Segmentation, U-Net hoặc bất kỳ nhiệm vụ ngoài Object Detection.
- Tăng cường dữ liệu (augmentation) và các kỹ thuật cân bằng lớp trong huấn luyện.
- Đánh giá mô hình bằng Precision, Recall, mAP50, mAP50-95 (thuộc feature đánh giá).
- Triển khai dịch vụ, giao diện người dùng hoặc tích hợp với module khác.
- Sửa đổi tài liệu Define/Design chung của nhóm.
