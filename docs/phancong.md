
# BẢNG PHÂN CÔNG CÔNG VIỆC – TOPIC 5

**Đề tài:** Phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp bằng AI.

**Quy mô nhóm:** 06 thành viên.

## 1. Bảng phân công nhiệm vụ

| Thành viên | Vai trò chuyên môn | Nhiệm vụ cụ thể | Sản phẩm bàn giao |
|---|---|---|---|
| **Thành viên 1** | **Data Owner & Preprocessing** | Kiểm tra NEU-DET và NEU-Seg; rà soát ảnh, annotation, mask; phát hiện dữ liệu thiếu, trùng lặp hoặc bất thường; phối hợp thống nhất cách chia train/validation/test; quản lý Demo Set 60 ảnh. | Dataset đã kiểm tra và chuẩn hóa; Data Card; script preprocessing; báo cáo kiểm tra dữ liệu. |
| **Thành viên 2** | **Detection Engineer – YOLOv8s** | Chuẩn bị nhãn NEU-DET theo định dạng YOLO; cấu hình và huấn luyện YOLOv8s; tinh chỉnh siêu tham số; lựa chọn checkpoint tốt nhất trên validation; đánh giá Precision, Recall, mAP và phân tích lỗi Detection. | Checkpoint YOLOv8s; code train/predict; log huấn luyện; bảng chỉ số đánh giá; báo cáo phân tích lỗi. |
| **Thành viên 3** | **Baseline Detection Engineer – YOLOv8n** | Xây dựng và huấn luyện YOLOv8n làm baseline; sử dụng cùng tập dữ liệu và quy trình đánh giá với YOLOv8s; đo thời gian suy luận và so sánh hiệu năng. | Checkpoint YOLOv8n; code train/predict; log huấn luyện; bảng so sánh YOLOv8n và YOLOv8s. |
| **Thành viên 4** | **Segmentation Engineer – U-Net** | Kiểm tra phiên bản NEU-Seg được lựa chọn; xác minh ảnh và mask tương ứng, số lớp và cách mã hóa nhãn; chuẩn hóa ảnh/mask; xây dựng và huấn luyện U-Net; đánh giá IoU, Dice, mIoU và phân tích lỗi phân vùng. | Checkpoint U-Net; code train/predict; log huấn luyện; bảng chỉ số đánh giá; báo cáo phân tích lỗi. |
| **Thành viên 5** | **Baseline Segmentation & Web Application** | Xây dựng phương pháp phân ngưỡng Otsu làm baseline; phát triển giao diện Streamlit/Gradio; xây dựng chức năng tải ảnh, kiểm tra đầu vào và hiển thị kết quả; tích hợp hai nhánh Detection và Segmentation. | Code baseline Otsu; mã nguồn Web App; chức năng tải ảnh và hiển thị kết quả; module tích hợp hai mô hình. |
| **Thành viên 6** | **AI Application & Documentation** | Nghiên cứu và phát triển Captioning/VQA nếu thuộc phạm vi đã được duyệt; xây dựng prompt, JSON grounding và cơ chế phản hồi dự phòng; tổng hợp kết quả thực nghiệm; biên soạn báo cáo và README. | Module Captioning/VQA (nếu được duyệt); báo cáo đồ án; README; hướng dẫn cài đặt và sử dụng. |

## 2. Phân chia trách nhiệm theo nhóm công việc

### 2.1. Nhóm dữ liệu
- **Thành viên 1:** Quản lý, kiểm tra và chuẩn hóa dữ liệu dùng chung.
- Các thành viên phụ trách mô hình phối hợp xác nhận định dạng nhãn, cách chia tập và yêu cầu dữ liệu của từng nhánh.

### 2.2. Nhóm mô hình AI
- **Thành viên 2:** YOLOv8s – Detection chính, sử dụng NEU-DET.
- **Thành viên 3:** YOLOv8n – Baseline Detection, sử dụng cùng tập dữ liệu với YOLOv8s.
- **Thành viên 4:** U-Net – Segmentation chính, sử dụng phiên bản NEU-Seg đã được nhóm xác nhận.

### 2.3. Nhóm ứng dụng và tài liệu
- **Thành viên 5:** Baseline Otsu và ứng dụng Web; tích hợp hai nhánh mô hình.
- **Thành viên 6:** Captioning/VQA (nếu được duyệt), tổng hợp kết quả và tài liệu dự án.

## 3. Nguyên tắc phối hợp và bàn giao

1. **Quản lý dữ liệu tập trung:** Thành viên 1 quản lý thông tin và phiên bản dữ liệu; không tự ý thay đổi hoặc ghi đè dataset đang được thành viên khác sử dụng.
2. **Tách biệt hai nhánh mô hình:** YOLOv8s/YOLOv8n sử dụng dữ liệu Detection; U-Net sử dụng dữ liệu Segmentation. Không mặc định hai dataset có cùng số lớp hoặc cùng hệ nhãn.
3. **Thống nhất dữ liệu trước khi huấn luyện:** Thành viên phụ trách mô hình phải xác nhận số lớp, ánh xạ nhãn, ảnh-mask/annotation tương ứng và cách chia tập trước khi train.
4. **So sánh công bằng:** YOLOv8s và YOLOv8n cần dùng cùng tập đánh giá và cùng quy trình tính chỉ số.
5. **Tích hợp sau khi bàn giao:** Thành viên 5 tích hợp các mô hình dựa trên checkpoint, mã nguồn dự đoán và hướng dẫn sử dụng do thành viên 2 và 4 cung cấp.
6. **Có thể tái lập kết quả:** Mỗi thành viên bàn giao mã nguồn, cấu hình, log, phiên bản thư viện và hướng dẫn chạy tương ứng.



>