# PHIẾU ĐĂNG KÝ ĐỀ TÀI — NHÓM 7

**Tên đề tài:** Topic 5 — Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh

**Hướng chính:** AI dự đoán · **Thời gian:** 8 tuần · **Sinh viên thực hiện:** ................................... · **Giảng viên hướng dẫn:** ...................................

| Mục | Nội dung |
|---|---|
| 1. Tên đề tài | **Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh.** Hai nhiệm vụ độc lập: Object Detection 6 lớp bằng YOLOv8s và Semantic Segmentation 3 lớp bằng U-Net. |
| 2. Hướng chính | **AI dự đoán.** Học có giám sát từ ảnh và nhãn để phát hiện loại lỗi, vị trí (Bounding Box) và vùng lỗi (Mask) trên ảnh tĩnh chưa thấy; kết quả đối chiếu nhãn chuẩn trên tập test. |
| 3. Người sử dụng và vấn đề | **Nhân viên QC/QA** kiểm tra bề mặt sản phẩm. Kiểm tra thủ công tốn thời gian, phụ thuộc kinh nghiệm, khó phát hiện lỗi nhỏ và khó lưu vết. Hệ thống hỗ trợ quan sát, sàng lọc và lưu vết; QC xác nhận kết quả cuối, hệ thống không tự loại sản phẩm. |
| 4. Mục tiêu | Xây dựng ứng dụng trả về box/lớp/confidence và mask 3 lớp lỗi; đánh giá độc lập từng mô hình trên test. Mục tiêu đo lường là so sánh tương đối với baseline cùng nhiệm vụ, không đặt trước mAP/IoU tuyệt đối. Hoàn thành demo web 3 khung: Detection, Segmentation và mô tả tiếng Việt. |
| 5. Dữ liệu | **NEU-DET:** 1.800 ảnh 200×200, 6 lớp, 4.189 box; chia 1.152/288/360. **NEU-Seg:** 4.470 ảnh (3.630/840), mask 0–3 cho inclusion/patches/scratches; chia 3.267/363/840. Giấy phép đang xác minh; đã kiểm tra 900 ảnh trùng nội dung giữa hai bộ; phương án thay thế là bộ công khai tương đương có mask và giấy phép rõ ràng. |
| 6. Phạm vi | **Bắt buộc:** Detection 6 lớp + Segmentation 3 lớp, huấn luyện và đánh giá độc lập với B-D1/B-S1, demo web 3 khung (2 kết quả thị giác + ngôn ngữ), phân tích lỗi. **Mở rộng ứng dụng:** Captioning/VQA tiếng Việt từ JSON bằng LLM/prompt có sẵn, không fine-tune, không sửa box/mask. **Ngoài phạm vi:** video/realtime, fine-tune VLM/LLM lớn, mạng đa nhiệm, fusion trong luồng chính. |
| 7. Phương pháp và Baseline | **Detection:** YOLOv8s pretrained COCO fine-tune 6 lớp, 640×640; **Segmentation:** U-Net từ đầu, 4 kênh, 256×256, loss CE+Dice. **Baseline bắt buộc:** B-D1 YOLOv8n và B-S1 phân ngưỡng Otsu (B-D2 Faster R-CNN, B-S2 U-Net pretrained nếu đủ GPU). **Tầng ứng dụng:** JSON → LLM/prompt có sẵn sinh mô tả và trả lời 5–10 câu hỏi mẫu, có template fallback. |
| 8. Sản phẩm | Demo web 3 khung (Detection, Segmentation, Captioning/VQA); checkpoint YOLOv8s và U-Net; mã nguồn huấn luyện, suy luận, ứng dụng; dữ liệu mẫu, mô tả dataset và split; hướng dẫn cài đặt/tái lập; báo cáo thực nghiệm có bảng so với baseline và phân tích lỗi. |
| 9. Đánh giá | **Detection:** Precision, Recall, mAP@0.5, mAP@0.5:0.95 trên 360 ảnh test NEU-DET. **Segmentation:** IoU từng lớp, Dice, mIoU, Pixel Precision/Recall trên 840 ảnh test NEU-Seg; so B-S1 bằng IoU/Dice nhị phân. **Captioning/VQA:** độ nhất quán với JSON, hallucination, độ trễ trên 20–30 ảnh và 5–10 câu hỏi; không gộp vào bảng thị giác. |
| 10. Kế hoạch 8 tuần và Rủi ro | Tuần 1 chốt phạm vi; tuần 2 chuẩn bị dữ liệu và thiết kế đánh giá; tuần 3 chạy B-D1/B-S1; tuần 4–5 huấn luyện YOLOv8s/U-Net; tuần 6 tích hợp demo và Captioning/VQA; tuần 7 đánh giá, phân tích lỗi; tuần 8 báo cáo, bàn giao. **Rủi ro:** thiếu GPU → U-Net lightweight, giảm batch, Colab/Kaggle; nhãn không đồng nhất → audit, không tự sửa; một nhánh lỗi → bọc ngoại lệ riêng; LLM bịa/chậm/offline → prompt chỉ dùng JSON, timeout, template fallback, nút tắt. |

**Ghi chú:** giấy phép NEU-DET/NEU-Seg và audit 182 ảnh box–mask bất nhất cần chốt trước tuần 3.
