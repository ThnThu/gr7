# Feature Specification: Pipeline huấn luyện, đánh giá và suy luận YOLOv8s

**Feature Branch**: `002-yolov8s-detection-pipeline`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "YOLOv8s Industrial Surface Defect Detection — prepare dataset configuration, train YOLOv8s from pretrained weights, save configs/logs/checkpoints, evaluate with Precision/Recall/mAP50/mAP50-95, run inference on individual images and visualize detections."

**Phụ thuộc**: Feature `001-neu-det-data-preparation` cung cấp dữ liệu NEU-DET đã chuyển đổi,
đã kiểm tra và manifest split train/validation/test. Feature này không lặp lại phần chuẩn bị
dữ liệu.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Huấn luyện YOLOv8s từ pretrained weights (Priority: P1)

Thành viên phụ trách mô hình cần huấn luyện YOLOv8s trên bộ NEU-DET đã chuẩn bị, bắt đầu từ
pretrained weights, và nhận được weights sau huấn luyện cùng cấu hình, log và checkpoint được
lưu lại đầy đủ.

**Why this priority**: Không có mô hình đã huấn luyện thì không thể đánh giá hay suy luận. Đây
là story tạo ra giá trị cốt lõi của module: một mô hình phát hiện 6 loại lỗi bề mặt thép.

**Independent Test**: Chạy huấn luyện trên một tập con nhỏ của dữ liệu đã chuẩn bị với cấu hình
rút gọn, xác nhận quá trình kết thúc thành công, tạo ra weights, file cấu hình, log và checkpoint;
sau đó dùng weights đó để chạy một lần dự đoán minh họa.

**Acceptance Scenarios**:

1. **Given** dữ liệu đã chuẩn bị và manifest hợp lệ từ feature 001, **When** bắt đầu huấn luyện
   với cấu hình đã chọn, **Then** mô hình được khởi tạo từ pretrained weights và quá trình
   huấn luyện chạy trên đúng các split train/validation.
2. **Given** quá trình huấn luyện kết thúc, **When** kiểm tra thư mục kết quả, **Then** có
   weights tốt nhất, weights cuối, cấu hình đã dùng, log huấn luyện và checkpoint có thể truy
   vết về đúng lần chạy.
3. **Given** cấu hình huấn luyện được lưu, **When** một thành viên khác mở lại, **Then** họ
   thấy đủ tham số quan trọng (epochs, batch size, image size, optimizer, learning rate,
   augmentation, seed, device) và có thể chạy lại.
4. **Given** tài nguyên phần cứng không đủ cho cấu hình ban đầu, **When** huấn luyện khởi động
   hoặc gặp lỗi hết bộ nhớ, **Then** hệ thống báo rõ và yêu cầu điều chỉnh cấu hình; mọi thay
   đổi phải được ghi nhận, không âm thầm hạ cấu hình.

---

### User Story 2 - Đánh giá mô hình bằng bốn chỉ số bắt buộc (Priority: P2)

Thành viên nhóm cần đánh giá mô hình đã huấn luyện trên validation và test để biết chất lượng
phát hiện theo từng lớp lỗi, với đầy đủ Precision, Recall, mAP50, mAP50-95, và một báo cáo gắn
với đúng checkpoint và cấu hình.

**Why this priority**: Chỉ số đánh giá là bằng chứng định lượng cho toàn bộ module và là điều
kiện bắt buộc theo Constitution. Story này có thể chạy độc lập ngay khi có weights.

**Independent Test**: Chạy đánh giá trên một checkpoint đã có và kiểm tra báo cáo chứa đủ bốn
chỉ số cho tổng thể và cho cả 6 lớp, đúng split, đúng checkpoint, không có số liệu bị thiếu.

**Acceptance Scenarios**:

1. **Given** một checkpoint đã huấn luyện, **When** chạy đánh giá trên validation set, **Then**
   báo cáo chứa Precision, Recall, mAP50, mAP50-95 cho tổng thể và từng lớp trong 6 lớp.
2. **Given** quá trình chọn checkpoint và hyperparameters đã hoàn tất trên validation, **When**
   chạy đánh giá cuối cùng trên test set, **Then** test set chỉ được dùng một lần để báo cáo,
   không dùng để điều chỉnh.
3. **Given** một báo cáo đánh giá, **When** mở báo cáo, **Then** thấy rõ checkpoint, cấu hình,
   split, thời điểm và phiên bản môi trường tương ứng.
4. **Given** dữ liệu hoặc checkpoint không khớp lớp, **When** chạy đánh giá, **Then** hệ thống
   dừng và báo lỗi rõ ràng thay vì tạo báo cáo sai.

---

### User Story 3 - Suy luận và trực quan hóa trên một ảnh (Priority: P3)

Người dùng cần đưa vào một ảnh bề mặt thép và nhận lại kết quả phát hiện: các vùng lỗi kèm tên
lớp và độ tin cậy, được vẽ bounding box trên ảnh để dễ kiểm tra bằng mắt.

**Why this priority**: Đây là đầu ra dễ thấy nhất của module và là cách kiểm chứng mô hình hoạt
động đúng trên ảnh thực tế, nhưng phụ thuộc vào weights từ story 1.

**Independent Test**: Dùng một ảnh mẫu và một checkpoint đã có, chạy suy luận, xác nhận kết quả
trả về danh sách phát hiện (lớp, độ tin cậy, tọa độ) và ảnh trực quan có bounding box, nhãn lớp
và confidence.

**Acceptance Scenarios**:

1. **Given** một ảnh hợp lệ và weights đã huấn luyện, **When** chạy suy luận, **Then** hệ thống
   trả về danh sách vùng lỗi với lớp, độ tin cậy và tọa độ.
2. **Given** kết quả suy luận, **When** yêu cầu trực quan hóa, **Then** ảnh đầu ra hiển thị
   bounding box, tên lớp và confidence cho từng phát hiện.
3. **Given** một ảnh không có lỗi được phát hiện, **When** chạy suy luận, **Then** hệ thống trả
   về kết quả rỗng hợp lệ và ảnh không có bounding box, không báo lỗi giả.
4. **Given** ảnh đầu vào hỏng hoặc không đọc được, **When** chạy suy luận, **Then** hệ thống báo
   lỗi rõ ràng và không tạo kết quả giả.

---

### Edge Cases

- Dữ liệu đã chuẩn bị hoặc manifest từ feature 001 không tồn tại, thiếu split hoặc sai cấu trúc.
- Số lớp trong dataset configuration không khớp 6 lớp NEU-DET hoặc sai thứ tự lớp.
- Pretrained weights không tồn tại, sai định dạng hoặc không tải được.
- Hết bộ nhớ GPU/CPU khi huấn luyện hoặc khi suy luận với ảnh lớn.
- Huấn luyện bị gián đoạn giữa chừng; cần phân biệt checkpoint dùng để tiếp tục và checkpoint
  dùng để báo cáo.
- Validation set rỗng hoặc chỉ có một lớp sau khi chia.
- Test set bị dùng lặp lại cho nhiều lần điều chỉnh.
- Ảnh đầu vào có kích thước, định dạng hoặc số kênh màu khác thường.
- Ảnh có nhiều lỗi chồng lấn hoặc lỗi rất nhỏ.
- Ngưỡng confidence quá thấp gây nhiều phát hiện nhiễu, hoặc quá cao gây bỏ sót.
- Thư mục kết quả của lần chạy trước đã tồn tại.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST chỉ sử dụng dữ liệu đã được feature 001 chuẩn bị và kiểm tra; MUST
  NOT đọc trực tiếp hoặc sửa đổi bộ dữ liệu NEU-DET gốc để huấn luyện.
- **FR-002**: Hệ thống MUST tạo dataset configuration khai báo đường dẫn train/validation/test và
  danh sách 6 lớp theo đúng thứ tự: `crazing`, `inclusion`, `patches`, `pitted_surface`,
  `rolled-in_scale`, `scratches`.
- **FR-003**: Hệ thống MUST kiểm tra dataset configuration trước khi huấn luyện: đủ 6 lớp, đúng
  thứ tự, đường dẫn tồn tại, split không rỗng; MUST dừng với lỗi rõ ràng nếu không đạt.
- **FR-004**: Hệ thống MUST huấn luyện YOLOv8s với khởi tạo từ pretrained weights; MUST phân
  biệt rõ pretrained weights và weights sau huấn luyện trong tên và đường dẫn lưu trữ.
- **FR-005**: Hệ thống MUST lưu cấu hình huấn luyện đầy đủ, tối thiểu gồm: dataset configuration,
  epochs, batch size, image size, optimizer, learning rate, augmentation, seed, device và
  pretrained weights đã dùng.
- **FR-006**: Hệ thống MUST lưu log huấn luyện theo epoch và checkpoint, phân biệt checkpoint tốt
  nhất và checkpoint cuối; mỗi checkpoint MUST truy vết được về lần chạy và cấu hình tương ứng.
- **FR-007**: Hệ thống MUST ghi nhận tài nguyên phần cứng và phiên bản thư viện/môi trường của
  mỗi lần huấn luyện quan trọng.
- **FR-008**: Hệ thống MUST chọn cấu hình huấn luyện phù hợp với tài nguyên phần cứng sẵn có và
  MUST báo lỗi rõ ràng khi tài nguyên không đủ; mọi điều chỉnh cấu hình MUST được ghi nhận.
- **FR-009**: Hệ thống MUST đánh giá mô hình trên validation và test, báo cáo tối thiểu
  Precision, Recall, mAP50, mAP50-95 cho tổng thể và cho từng lớp.
- **FR-010**: Hệ thống MUST chỉ dùng validation set để chọn checkpoint và điều chỉnh; MUST NOT
  dùng test set để điều chỉnh huấn luyện hoặc chọn hyperparameters.
- **FR-011**: Hệ thống MUST lưu báo cáo đánh giá gắn với checkpoint, cấu hình, split, thời điểm
  và môi trường tương ứng.
- **FR-012**: Hệ thống MUST cho phép chạy suy luận trên một ảnh đầu vào bằng weights đã huấn
  luyện và trả về danh sách phát hiện gồm lớp, độ tin cậy và tọa độ bounding box.
- **FR-013**: Hệ thống MUST tạo ảnh trực quan cho kết quả suy luận, hiển thị bounding box, tên
  lớp và confidence score.
- **FR-014**: Hệ thống MUST xử lý an toàn trường hợp không có phát hiện nào và trường hợp ảnh
  đầu vào không hợp lệ, với thông báo rõ ràng.
- **FR-015**: Hệ thống MUST lưu kết quả suy luận (danh sách phát hiện và ảnh trực quan) vào thư
  mục riêng, không ghi đè dữ liệu gốc hoặc kết quả của lần chạy khác mà không xác nhận.
- **FR-016**: Hệ thống MUST bảo đảm chạy lại với cùng dữ liệu, cấu hình và seed tạo ra kết quả
  tương đương và có thể đối chiếu.
- **FR-017**: Hệ thống MUST không thay đổi kiến trúc YOLOv8s và không triển khai bất kỳ nhiệm vụ
  nào ngoài Object Detection.

### Key Entities *(include if feature involves data)*

- **Dataset configuration**: khai báo đường dẫn các split và danh sách 6 lớp theo thứ tự cố định.
- **Training run**: một lần huấn luyện, có định danh duy nhất và liên kết tới cấu hình, log,
  checkpoint và môi trường.
- **Training configuration**: tập tham số điều khiển huấn luyện, đủ để chạy lại.
- **Checkpoint**: trạng thái mô hình được lưu trong quá trình huấn luyện; phân biệt tốt nhất,
  cuối cùng và checkpoint tiếp tục.
- **Trained weights**: trọng số sau huấn luyện, tách biệt với pretrained weights.
- **Evaluation report**: kết quả định lượng trên validation/test, gồm bốn chỉ số bắt buộc.
- **Detection result**: một phát hiện trên ảnh, gồm lớp, confidence và bounding box.
- **Visualization artifact**: ảnh đã vẽ bounding box, tên lớp và confidence.
- **Environment record**: phiên bản môi trường và tài nguyên phần cứng của lần chạy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% lần huấn luyện hợp lệ tạo ra được weights sử dụng được cho suy luận và đánh giá.
- **SC-002**: 100% báo cáo đánh giá chứa đủ bốn chỉ số Precision, Recall, mAP50, mAP50-95 cho
  tổng thể và cho cả 6 lớp.
- **SC-003**: 100% lần chạy truy vết được từ weights/báo cáo về đúng cấu hình, checkpoint, log
  và môi trường.
- **SC-004**: Chạy lại với cùng dữ liệu, cấu hình và seed cho kết quả đánh giá chênh lệch không
  quá 1 điểm phần trăm so với lần trước.
- **SC-005**: 100% ảnh đầu vào hợp lệ tạo ra kết quả suy luận (kể cả rỗng hợp lệ) và ảnh trực
  quan tương ứng.
- **SC-006**: 0 lần test set được dùng để điều chỉnh huấn luyện hoặc chọn checkpoint.
- **SC-007**: Huấn luyện hoàn tất trong giới hạn tài nguyên phần cứng của nhóm mà không thất bại
  do hết bộ nhớ; nếu phải điều chỉnh cấu hình, 100% điều chỉnh được ghi nhận.
- **SC-008**: Một thành viên khác có thể đi từ dữ liệu đã chuẩn bị đến ảnh suy luận có trực quan
  hóa bằng cách làm theo tài liệu và cấu hình đã lưu, không cần hỏi thêm.

## Assumptions

- Feature 001 đã hoàn tất và cung cấp dữ liệu đã chuyển đổi, đã kiểm tra cùng manifest split
  train/validation/test.
- Pretrained YOLOv8s weights có sẵn và hợp lệ tại thời điểm huấn luyện.
- Nhóm có GPU với dung lượng bộ nhớ hạn chế; cấu hình mặc định sẽ thận trọng và có thể điều
  chỉnh, nhưng mọi thay đổi phải được ghi lại.
- Sáu lớp lỗi và thứ tự lớp là cố định theo Constitution; thay đổi là thay đổi phạm vi.
- Suy luận chỉ áp dụng cho ảnh đơn lẻ, không gồm video, luồng camera hoặc xử lý hàng loạt quy mô lớn.
- Đánh giá trên validation dùng để chọn checkpoint; test set chỉ dùng một lần cho báo cáo cuối.
- Người dùng là thành viên nhóm có quyền truy cập dữ liệu, weights và thư mục kết quả của module.

## Out of Scope

- Chuyển đổi, kiểm tra và chia dữ liệu NEU-DET (thuộc feature 001).
- Segmentation, U-Net hoặc bất kỳ nhiệm vụ ngoài Object Detection.
- Thay đổi kiến trúc YOLOv8s hoặc thay YOLOv8s bằng mô hình khác.
- Huấn luyện phân tán, tối ưu hyperparameters tự động quy mô lớn hoặc model ensemble.
- Triển khai dịch vụ, API, giao diện người dùng hoặc tích hợp với module Segmentation.
- Sửa đổi tài liệu Define/Design chung của nhóm.
