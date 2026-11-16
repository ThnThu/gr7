<!--
Sync Impact Report
==================
Version change: N/A (template scaffold) → 1.0.0
Modified principles:
  - [PRINCIPLE_1_NAME] → I. Phạm vi Detection-Only (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Toàn vẹn và truy xuất nguồn gốc dữ liệu
  - [PRINCIPLE_3_NAME] → III. Kiểm soát mô hình và cấu hình
  - [PRINCIPLE_4_NAME] → IV. Đánh giá trung thực
  - [PRINCIPLE_5_NAME] → V. Tái lập (Reproducibility)
  - (mới) → VI. Chất lượng mã nguồn và cộng tác
Added sections:
  - Ràng buộc bổ sung (Môi trường, Checkpoint, Cấu trúc module)
  - Quy trình phát triển và Cổng chất lượng
Removed sections: None
Templates/commands: không cần sửa; các template và command đọc constitution tại runtime.
Follow-up TODOs: None
-->

# YOLOv8 Detection Module Constitution

<!-- Module độc lập thuộc project AI Industrial Defect. Phạm vi: Object Detection với YOLOv8s trên NEU-DET. -->

## Core Principles

### I. Phạm vi Detection-Only (NON-NEGOTIABLE)

Module này CHỈ thực hiện Object Detection. Mọi thành viên PHẢI tuân thủ:

- KHÔNG triển khai Segmentation, U-Net hoặc bất kỳ nhiệm vụ nào ngoài Detection.
- KHÔNG tự ý thay đổi kiến trúc YOLOv8s (backbone, neck, head, loss mặc định).
- KHÔNG tự ý bổ sung chức năng ngoài phạm vi đã được nhóm phê duyệt.
- KHÔNG sửa đổi tài liệu Define/Design chung của nhóm.
- Module PHẢI hoạt động độc lập với module Segmentation: không import, không phụ thuộc
  runtime, không chia sẻ trạng thái ẩn.

**Rationale**: Giữ ranh giới trách nhiệm rõ ràng, tránh xung đột với module Segmentation và
bảo toàn thiết kế đã thống nhất của nhóm.

### II. Toàn vẹn và truy xuất nguồn gốc dữ liệu

- Dataset PHẢI là NEU-DET. Dataset gốc PHẢI được giữ nguyên, chỉ đọc, không ghi đè.
- Chuyển đổi annotation XML → định dạng YOLO PHẢI diễn ra trong một thư mục dữ liệu đã xử lý
  riêng biệt; không trộn lẫn với dữ liệu gốc.
- Trước khi training PHẢI kiểm tra và ghi nhận: class mapping, tọa độ bounding boxes, ảnh lỗi,
  annotation thiếu/sai, và các bất thường dữ liệu khác.
- KHÔNG tự ý loại bỏ mẫu dữ liệu. Nếu buộc phải loại bỏ, PHẢI nêu lý do và ghi nhận rõ ràng
  (số lượng, tiêu chí, nơi lưu log) để có thể kiểm tra lại.

**Rationale**: Dữ liệu là nguồn gốc của mọi kết quả; thay đổi không được truy vết sẽ làm mất
khả năng tái lập và so sánh giữa các lần huấn luyện.

### III. Kiểm soát mô hình và cấu hình

- Mô hình chính PHẢI là YOLOv8s.
- PHẢI phân biệt rõ ràng pretrained weights (ví dụ `yolov8s.pt` gốc) và weights sau khi tự
  training; mỗi loại PHẢI có đường dẫn và metadata riêng.
- Cấu hình training (dataset, hyperparameters, augmentation, seed, epochs, batch size, image
  size, optimizer, device) PHẢI được lưu lại cùng phiên bản mã nguồn tương ứng.
- KHÔNG thay đổi model hoặc hyperparameters quan trọng mà không ghi nhận lý do, giá trị cũ,
  giá trị mới và kết quả ảnh hưởng.

**Rationale**: Mọi thay đổi mô hình phải giải thích được và so sánh được; cấu hình không lưu
lại thì kết quả không thể tái lập.

### IV. Đánh giá trung thực

- PHẢI báo cáo tối thiểu các chỉ số: Precision, Recall, mAP50, mAP50-95.
- Đánh giá PHẢI thực hiện trên tập validation/test phù hợp với split đã công bố.
- TUYỆT ĐỐI KHÔNG dùng test set để điều chỉnh training, chọn hyperparameters hoặc chọn
  checkpoint. Mọi điều chỉnh chỉ dựa trên validation set.
- Kết quả PHẢI được lưu lại (file, log hoặc báo cáo) và gắn với cấu hình/checkpoint tương ứng.

**Rationale**: Chỉ số chỉ có giá trị khi được đo trên dữ liệu chưa từng dùng để tối ưu; dùng
test set để tinh chỉnh là làm sai lệch đánh giá.

### V. Tái lập (Reproducibility)

- PHẢI lưu training configuration, kết quả đánh giá và quản lý checkpoint rõ ràng (đặt tên,
  thư mục, phiên bản).
- PHẢI ghi nhận môi trường chạy và phiên bản thư viện (Python, PyTorch, Ultralytics,
  CUDA/driver, GPU) cùng với mỗi lần huấn luyện quan trọng.
- PHẢI đặt seed và ghi lại các yếu tố ảnh hưởng đến tính ngẫu nhiên khi có thể.
- Kết quả công bố PHẢI đủ thông tin để một thành viên khác tái chạy và đối chiếu.

**Rationale**: Kết quả không tái lập được thì không thể xác minh, so sánh hay bàn giao.

### VI. Chất lượng mã nguồn và cộng tác

- Code PHẢI dễ đọc, có chú thích cho các bước xử lý dữ liệu và training.
- PHẢI ưu tiên cấu trúc module rõ ràng (tách bước convert dữ liệu, validate, train, evaluate,
  inference) và tránh code trùng lặp.
- KHÔNG tạo file hoặc thư mục không cần thiết.
- KHÔNG chỉnh sửa file của thành viên khác nếu không được cho phép.
- Mọi thay đổi PHẢI tuân thủ Define và Design đã được nhóm thống nhất.

**Rationale**: Mã nguồn là tài sản chung của nhóm; cấu trúc rõ ràng và tôn trọng quyền sở hữu
giúp giảm lỗi tích hợp và chi phí bảo trì.

## Ràng buộc bổ sung (Môi trường, Checkpoint, Cấu trúc module)

- **Môi trường**: Mỗi lần training PHẢI ghi lại phiên bản Python, PyTorch, Ultralytics và
  thông tin GPU/CUDA. Khuyến nghị lưu danh sách package (ví dụ `pip freeze`) đi kèm run.
- **Checkpoint**: Checkpoint tốt nhất và checkpoint cuối PHẢI được phân biệt; checkpoint dùng
  để báo cáo PHẢI trỏ tới đúng run và đúng cấu hình.
- **Cấu trúc dữ liệu**: Dữ liệu gốc, dữ liệu đã chuyển đổi, cấu hình, runs và weights PHẢI nằm
  ở thư mục riêng, không ghi đè lẫn nhau.
- **Không mở rộng phạm vi**: Mọi nhu cầu nằm ngoài Detection (ví dụ segmentation, dịch vụ
  triển khai, giao diện) PHẢI được báo cáo và chờ phê duyệt, không tự triển khai.

## Quy trình phát triển và Cổng chất lượng

Mọi thay đổi PHẢI đi qua chu trình: **Specify → Plan → Tasks → Implement → Analyze**.

1. **Specify**: Xác định rõ yêu cầu Detection, phạm vi và tiêu chí chấp nhận.
2. **Plan**: Kiểm tra tài liệu hiện có trước khi lập kế hoạch; nêu rõ dữ liệu, mô hình, cấu
   hình, cách đánh giá và rủi ro.
3. **Tasks**: Chia nhỏ công việc, gắn với file/thư mục cụ thể, không vượt phạm vi.
4. **Implement**: Thực hiện đúng kế hoạch, ghi chú các bước xử lý dữ liệu và training.
5. **Analyze**: Đối chiếu kết quả với Constitution, tiêu chí đánh giá và ghi nhận sai lệch.

**Cổng chất lượng trước khi báo cáo kết quả**:

- [ ] Dataset gốc không bị thay đổi; dữ liệu chuyển đổi nằm ở thư mục riêng.
- [ ] Class mapping và bounding boxes đã được kiểm tra, có ghi nhận.
- [ ] Cấu hình training và môi trường đã được lưu.
- [ ] Đủ 4 chỉ số Precision, Recall, mAP50, mAP50-95 trên validation/test.
- [ ] Test set không được dùng để điều chỉnh.
- [ ] Checkpoint và kết quả đánh giá truy vết được về đúng run.
- [ ] Không có thay đổi ngoài phạm vi Detection.

**Xử lý xung đột**: Nếu yêu cầu mâu thuẫn với Constitution hoặc phạm vi project, thành viên
PHẢI báo cáo và yêu cầu xác nhận thay vì tự ý quyết định. Không có ngoại lệ ngầm.

## Governance

- Constitution này là nguồn quy tắc cao nhất của module YOLOv8 Detection; khi mâu thuẫn với
  thói quen, tài liệu phụ hoặc đề xuất cá nhân, Constitution được ưu tiên.
- **Sửa đổi**: Mọi thay đổi Constitution PHẢI được đề xuất, nêu lý do, được nhóm phê duyệt và
  ghi lại ngày cùng phiên bản. Không sửa đổi âm thầm.
- **Phiên bản**: Áp dụng Semantic Versioning.
  - MAJOR: xóa hoặc định nghĩa lại nguyên tắc theo cách không tương thích.
  - MINOR: thêm nguyên tắc/mục mới hoặc mở rộng đáng kể hướng dẫn.
  - PATCH: làm rõ, sửa câu chữ, tinh chỉnh không thay đổi ngữ nghĩa.
- **Tuân thủ**: Mọi thay đổi mã nguồn, dữ liệu, cấu hình và báo cáo PHẢI được rà soát theo
  Constitution. Sai lệch PHẢI được nêu rõ và xử lý trước khi hoàn tất.
- **Phạm vi áp dụng**: Chỉ áp dụng cho module YOLOv8 Detection; không sửa đổi hoặc ràng buộc
  module Segmentation và tài liệu Define/Design chung của nhóm.

**Version**: 1.0.0 | **Ratified**: 2026-11-13 | **Last Amended**: 2026-11-13
