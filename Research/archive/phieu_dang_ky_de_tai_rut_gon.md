# PHIẾU ĐĂNG KÝ ĐỀ TÀI NGHIÊN CỨU

**Tên đề tài:** Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh

**Hướng nghiên cứu:** AI dự đoán · **Nhóm:** 7 · **Thời gian:** 8 tuần

**Sinh viên thực hiện:** ................................... · **Giảng viên hướng dẫn:** ...................................

## 1. Tên đề tài

**Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ hình ảnh.** Đề tài gồm hai nhiệm vụ độc lập: Object Detection bằng YOLOv8s và Semantic Segmentation bằng U-Net.

## 2. Hướng chính

**AI dự đoán.** Mô hình học có giám sát quan hệ giữa ảnh và nhãn để dự đoán loại lỗi, vị trí và vùng lỗi trên ảnh chưa thấy; kết quả được đánh giá bằng độ khớp với nhãn chuẩn trên tập test.

## 3. Người sử dụng và vấn đề

- **Đối tượng:** nhân viên kiểm tra chất lượng (QC/QA), bộ phận kiểm định, người nghiên cứu bề mặt vật liệu.
- **Khó khăn:** kiểm tra thủ công tốn thời gian, phụ thuộc kinh nghiệm, thiếu nhất quán; khó phát hiện lỗi nhỏ, độ tương phản thấp; khó lưu vết giữa các lô.
- **Nhu cầu:** biết loại lỗi, vị trí (Bounding Box) và vùng ảnh hưởng (Mask) để đánh giá mức độ và ra quyết định.
- **Vai trò hệ thống:** hỗ trợ quan sát, sàng lọc; nhân viên QC xác nhận kết quả cuối. Hệ thống không thay thế hoàn toàn con người.

## 4. Mục tiêu

**Tổng quát:** xây dựng ứng dụng phân tích ảnh bề mặt sản phẩm, trả về kết quả phát hiện và phân vùng lỗi bằng hai mô hình Deep Learning độc lập, có đánh giá thực nghiệm trên dữ liệu chưa dùng để huấn luyện.

**Cụ thể:** (1) kiểm kê, chuẩn bị NEU-DET và NEU-Seg; (2) fine-tune YOLOv8s từ trọng số COCO cho 6 lớp lỗi; (3) huấn luyện U-Net trên NEU-Seg cho 3 lớp lỗi có mask; (4) đánh giá riêng từng mô hình trên tập test; (5) tích hợp hai mô hình vào một ứng dụng hiển thị đồng thời hai kết quả; (6) phân tích lỗi, giới hạn và khả năng ứng dụng; (7) **[Mở rộng]** nghiên cứu Decision Fusion sau khi hoàn thành phần bắt buộc.

**Đầu ra:** Detection trả về danh sách Bounding Box kèm tên lớp và độ tin cậy; Segmentation trả về mask cùng kích thước ảnh, mỗi pixel thuộc nền hoặc một trong ba lớp lỗi. Ứng dụng hiển thị hai kết quả trên cùng ảnh, không gộp thành một đầu ra duy nhất. Nhóm không đặt trước mức mAP, IoU hay Dice khi chưa có kết quả thực nghiệm.

## 5. Dữ liệu

**NEU-DET** · Object Detection · 6 lớp `crazing`, `inclusion`, `patches`, `pitted_surface`, `rolled-in_scale`, `scratches`; nhãn Bounding Box dạng Pascal VOC XML. **[Đã khảo sát]** 1.800 ảnh 200×200, 4.189 box, 123 ảnh đa lớp; cấu trúc 1.440 ảnh train / 360 ảnh validation. **[Dự kiến]** dùng 360 ảnh validation làm test, chia 1.440 ảnh train thành train/validation 80/20; kiểm tra trùng lặp và lỗi nhãn trước khi chốt.

**NEU-Seg** · Semantic Segmentation · 4.470 ảnh (3.630 training / 840 test), mask `uint8` 4 giá trị 0–3: 0 là nền, 1–3 là ba lớp lỗi. Chỉ dùng 3.630 ảnh training, tách một phần làm validation để chọn checkpoint; giữ 840 ảnh test cho báo cáo cuối. **[Cần xác minh]** tên và ánh xạ ba giá trị mask theo tài liệu dataset; khảo sát sơ bộ trên ảnh dùng chung với NEU-DET cho thấy tương ứng `inclusion`, `patches`, `scratches`. NEU-Seg không có mask cho `crazing`, `pitted_surface`, `rolled-in_scale`; không suy mask từ Bounding Box.

**Lưu ý:** giấy phép và điều khoản sử dụng của cả hai bộ **[Cần xác minh]**; hai bộ có ảnh trùng nội dung nên cần kiểm tra chồng lấn. **Phương án thay thế:** nếu dữ liệu không truy cập được hoặc nhãn không đạt, nhóm tìm bộ công khai tương đương có mask và giấy phép rõ ràng, báo giảng viên trước khi thay; không đổi phạm vi hai mô hình.

## 6. Phạm vi

**Bắt buộc:** khảo sát bài toán và hướng tiếp cận; chuẩn bị dữ liệu, kiểm tra nhãn và rò rỉ dữ liệu; xây dựng, huấn luyện YOLOv8s cho Detection và U-Net cho Segmentation; đánh giá độc lập từng mô hình; xây dựng ứng dụng tải ảnh, chạy hai nhánh và hiển thị đồng thời kết quả; phân tích lỗi, giới hạn và khả năng ứng dụng.

**Tầng ứng dụng (mở rộng ở giao diện):** Captioning/VQA tiếng Việt từ JSON kết quả bằng LLM/prompt có sẵn, không fine-tune, không sửa box/mask; có template fallback khi LLM lỗi, timeout hoặc không có mạng.

**Mở rộng nghiên cứu không bắt buộc:** Decision Fusion đối chiếu Bounding Box với Mask trên các lớp có mặt ở cả hai bộ dữ liệu; đánh giá so với từng mô hình riêng lẻ. Chỉ triển khai khi phần bắt buộc đã hoàn thành và còn đủ thời gian, dữ liệu, tài nguyên. Việc hai mô hình cùng nằm trong một ứng dụng **không** được gọi là Model Fusion.

## 7. Phương pháp

**Baseline bắt buộc:** Detection dùng **B-D1 — YOLOv8n** (cùng họ, dung lượng nhỏ) fine-tune cùng split, seed và cấu hình; Segmentation dùng **B-S1 — phân ngưỡng Otsu** (mốc không học sâu, phân vùng nhị phân nền–lỗi). **Tùy chọn nếu đủ GPU:** B-D2 Faster R-CNN ResNet50-FPN và B-S2 U-Net encoder ResNet34 pretrained. Không dùng zero-shot COCO làm baseline định lượng; nếu có, chỉ ghi chú định tính về khoảng cách miền.

**Đề xuất:** YOLOv8s pretrained COCO, fine-tune trên NEU-DET với 6 lớp, đầu vào 640×640 (letterbox), đầu ra box/lớp/confidence. U-Net encoder–decoder huấn luyện từ đầu, 4 kênh đầu ra, mất mát kết hợp Cross-Entropy và Dice, ưu tiên cấu hình lightweight nếu thiếu GPU/RAM. Hai nhánh nhận cùng ảnh gốc, tiền xử lý riêng, suy luận độc lập; ứng dụng hiển thị box và mask cạnh nhau. **Tầng ứng dụng:** JSON từ hai nhánh → LLM/prompt có sẵn sinh mô tả tiếng Việt và trả lời 5–10 câu hỏi mẫu; không fine-tune LLM/VLM, không tạo box/mask mới.

**Quy trình:** chuẩn bị dữ liệu → tiền xử lý → huấn luyện → đánh giá trên test → tích hợp → kiểm thử và phân tích lỗi.

## 8. Sản phẩm

Ứng dụng demo chạy hai nhánh, hiển thị đồng thời kết quả Detection, Segmentation và khung Captioning/VQA tiếng Việt sinh từ JSON; mô hình YOLOv8s đã fine-tune; mô hình U-Net đã huấn luyện; mã nguồn huấn luyện, suy luận, ứng dụng; dữ liệu mẫu và tài liệu mô tả dataset, cách chia tập; hướng dẫn cài đặt và tái lập; báo cáo thực nghiệm, bảng so sánh và phân tích lỗi. **[Mở rộng, không bắt buộc]** module Decision Fusion và báo cáo đánh giá tương ứng.

## 9. Đánh giá

| Mô hình | Chỉ số | Tập đánh giá |
|---|---|---|
| YOLOv8s | Precision, Recall, mAP@0.5, mAP@0.5:0.95 | 360 ảnh test NEU-DET |
| U-Net | IoU từng lớp, Dice, mIoU, Pixel Precision, Pixel Recall | 840 ảnh test NEU-Seg |
| Captioning/VQA | Độ nhất quán với JSON, hallucination, độ đọc hiểu, độ trễ | 20–30 ảnh demo + 5–10 câu hỏi mẫu |

Captioning/VQA chỉ đánh giá tính nhất quán với JSON và chất lượng trình bày; không dùng mAP/IoU và không gộp vào bảng thị giác. Chỉ báo cáo trên tập test không tham gia huấn luyện hoặc chọn checkpoint; ghi rõ tỉ lệ chia và seed. Bộ kiểm thử gồm ảnh một lỗi, nhiều lỗi, lỗi nhỏ/độ tương phản thấp, nhiều lớp lỗi; kiểm thử ứng dụng với ảnh hợp lệ, sai định dạng, thiếu tệp và lỗi một nhánh. Phân tích dương tính giả, âm tính giả, nhầm lớp, sai biên mask, bỏ sót lỗi nhỏ. Đo thời gian suy luận riêng từng nhánh và toàn pipeline nếu có điều kiện, ghi rõ phần cứng. Không so sánh trực tiếp mAP của Detection với IoU của Segmentation vì hai chỉ số đo hai nhiệm vụ khác nhau.

## 10. Kế hoạch và rủi ro

| Thời gian | Công việc | Kết quả |
|---|---|---|
| Tuần 1 | Khảo sát, xác định phạm vi | Phiếu đăng ký, tình huống sử dụng |
| Tuần 2 | Chuẩn bị dữ liệu, thiết kế đánh giá | Dữ liệu, mô tả dataset |
| Tuần 3 | Xây dựng baseline | Kết quả cơ sở |
| Tuần 4–5 | Huấn luyện hai mô hình | Hai mô hình kiểm thử được |
| Tuần 6 | Tích hợp ứng dụng, tầng Captioning/VQA, xử lý lỗi | Bản demo 3 khung: Detection, Segmentation, Ngôn ngữ |
| Tuần 7 | Đánh giá, phân tích | Bảng kết quả, phân tích lỗi |
| Tuần 8 | Hoàn thiện báo cáo, bàn giao | Demo, mã nguồn, hướng dẫn |

**Rủi ro và biện pháp:** thiếu GPU/RAM → U-Net lightweight, giảm batch size, dùng Colab/Kaggle, lưu checkpoint theo epoch; huấn luyện kéo dài → giới hạn epoch, dừng sớm, ưu tiên mô hình nhỏ; nhãn không đồng nhất → kiểm kê, đối chiếu XML/mask, không tự sửa nhãn khi chưa có quy trình; xung đột thư viện → khóa phiên bản, môi trường ảo; khác tiền xử lý → tách cấu hình, kiểm thử từng nhánh trước khi ghép; khó tích hợp, hiển thị → chuẩn hóa đầu ra trung gian, hiển thị độc lập từng nhánh; LLM bịa/chậm/offline → prompt chỉ dùng JSON, timeout, template fallback, nút tắt và không chặn kết quả thị giác.

## 11. Kết quả và giới hạn dự kiến

**Kết quả:** ứng dụng tải một ảnh, trả về loại lỗi kèm Bounding Box, vùng lỗi ở cấp điểm ảnh và đoạn mô tả/hỏi đáp tiếng Việt sinh từ JSON; hai mô hình được huấn luyện, đánh giá độc lập theo bộ chỉ số ở mục 9; bảng phân tích lỗi và nhận xét khả năng hỗ trợ nhân viên QC.

**Giới hạn:** NEU-DET chỉ có ảnh 200×200 với 6 lớp, nhãn có thể nhiễu, không đại diện ảnh độ phân giải cao hoặc điều kiện sản xuất khác; NEU-Seg chỉ có mask cho 3 lớp và không suy mask từ box; hai bộ dữ liệu công khai khác điều kiện ánh sáng, vật liệu, thiết bị chụp so với thực tế; Captioning/VQA chỉ diễn giải JSON, không bổ sung bằng chứng thị giác và không được đánh giá bằng mAP/IoU; Decision Fusion (mở rộng) chỉ đối chiếu được các lớp chung; không khẳng định hệ thống hoạt động tốt với mọi vật liệu, ánh sáng hoặc dạng lỗi ngoài dữ liệu huấn luyện.

---

**Cần xác minh trước khi nộp:** (1) giấy phép NEU-DET và NEU-Seg; (2) audit 182 ảnh box–mask bất nhất và 11 cặp gần trùng NEU-Seg; (3) tính toàn vẹn cách chia dữ liệu (900 ảnh trùng, XML/ảnh lệch thư mục, box trùng) và 60 ảnh demo both-test; (4) GPU/RAM và thời gian huấn luyện; (5) không dùng checkpoint U-Net chưa rõ nguồn gốc; (6) danh sách lớp chung cho Decision Fusion; (7) phần cứng đo thời gian suy luận; (8) đồng bộ `define_and_design_v2.ipynb`, phiếu 1 trang và sơ đồ trong `assets/define-design/`.
