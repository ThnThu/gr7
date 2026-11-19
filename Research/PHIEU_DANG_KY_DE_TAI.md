# PHIẾU ĐĂNG KÝ ĐỀ TÀI NGHIÊN CỨU

**Tên đề tài:** Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp bằng AI

**Hướng nghiên cứu:** AI dự đoán (học có giám sát cho thị giác máy tính)

**Nhóm thực hiện:** Nhóm 7 — [CẦN XÁC NHẬN: danh sách họ tên, MSSV thành viên]

**Giảng viên hướng dẫn:** [CẦN XÁC NHẬN]

**Thời gian thực hiện:** 8 tuần — [CẦN XÁC NHẬN: mốc bắt đầu/kết thúc cụ thể]

---

## 1. Tên đề tài

**Ứng dụng AI phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp bằng AI.**

Đề tài tập trung vào bài toán nhận diện khuyết tật trên ảnh bề mặt sản phẩm công nghiệp bằng các mô hình học sâu. Trong phạm vi tổng thể, hệ thống được thiết kế gồm hai nhiệm vụ thị giác độc lập: (i) phát hiện vị trí và loại lỗi (Object Detection) và (ii) phân vùng vùng lỗi ở mức điểm ảnh (Semantic Segmentation). Tầng ứng dụng có thể bổ sung mô tả/hỏi đáp tiếng Việt từ kết quả có cấu trúc (JSON) bằng LLM/prompt có sẵn; đây là phần hỗ trợ trình bày, không thay thế nhiệm vụ thị giác.

## 2. Bối cảnh nghiên cứu

Kiểm tra bề mặt (surface inspection) là bước quan trọng trong dây chuyền sản xuất thép và nhiều ngành công nghiệp chế tạo nhằm phát hiện sớm khuyết tật, giảm lỗi sản phẩm và ổn định chất lượng. Các bộ dữ liệu công khai về lỗi bề mặt thép (như NEU-DET, NEU-Seg) và sự phát triển của mạng nơ-ron tích chập/mô hình phát hiện đối tượng hiện đại tạo điều kiện để nghiên cứu, so sánh và xây dựng nguyên mẫu hỗ trợ kiểm tra tự động dựa trên ảnh tĩnh.

## 3. Vấn đề nghiên cứu

Bài toán đặt ra là: từ một ảnh bề mặt sản phẩm, hệ thống cần **xác định loại lỗi**, **định vị vùng lỗi** (hộp bao) và/hoặc **phân vùng vùng lỗi** (mặt nạ điểm ảnh) với độ tin cậy có thể đánh giá được trên dữ liệu kiểm thử độc lập. Thách thức gồm: sự đa dạng hình thái lỗi, lỗi nhỏ/độ tương phản thấp, mất cân bằng dữ liệu, yêu cầu chuẩn bị nhãn nhất quán và đảm bảo đánh giá trung thực (không rò rỉ giữa tập huấn luyện/kiểm thử).

## 4. Động lực và ý nghĩa

- **Ý nghĩa thực tiễn:** hỗ trợ nhân viên QC/QA quan sát, sàng lọc và lưu vết khuyết tật, giảm phụ thuộc hoàn toàn vào kiểm tra thủ công.
- **Ý nghĩa học thuật/kỹ thuật:** rèn luyện quy trình hoàn chỉnh từ chuẩn bị dữ liệu, huấn luyện, đánh giá đến tích hợp demo; so sánh mô hình/baseline theo cùng giao thức.
- **Giới hạn vai trò:** hệ thống là công cụ hỗ trợ; **người kiểm tra (QC) xác nhận kết quả cuối**, hệ thống **không tự động loại bỏ sản phẩm**.

## 5. Mục tiêu nghiên cứu

### 5.1. Mục tiêu tổng quát

Xây dựng và đánh giá nguyên mẫu ứng dụng AI hỗ trợ phát hiện và phân vùng lỗi bề mặt sản phẩm công nghiệp từ ảnh tĩnh, trong đó nhiệm vụ phát hiện đối tượng (NEU-DET/YOLOv8s) và nhiệm vụ phân vùng (NEU-Seg/U-Net) được thực hiện và đánh giá **độc lập**.

### 5.2. Mục tiêu kỹ thuật (dự kiến)

| Mã | Mục tiêu kỹ thuật | Trạng thái |
|---|---|---|
| O1 | Chuẩn bị dữ liệu NEU-DET: chuyển VOC XML sang nhãn YOLO, kiểm tra tính toàn vẹn, sinh báo cáo/manifest và chia tập tái lập được | **Kế hoạch/đang triển khai (Feature 001)** — [CẦN XÁC NHẬN: mức hoàn thành nghiệm thu] |
| O2 | Huấn luyện và tinh chỉnh YOLOv8s cho phát hiện 6 lớp lỗi trên NEU-DET; chọn checkpoint tốt nhất theo tập validation | **Kế hoạch** |
| O3 | Đánh giá YOLOv8s trên tập test độc lập (Precision, Recall, mAP@0.5, mAP@0.5:0.95) và phân tích lỗi | **Kế hoạch** |
| O4 | Huấn luyện/đánh giá U-Net trên NEU-Seg (3 lớp lỗi có mask) theo giao thức riêng | **Kế hoạch** (phụ thuộc thành viên/nguồn lực — [CẦN XÁC NHẬN]) |
| O5 | Tích hợp demo hiển thị đồng thời kết quả Detection, Segmentation và (tùy chọn) mô tả ngôn ngữ từ JSON | **Kế hoạch** |

> Ghi chú: mục tiêu và chỉ số mục tiêu **không** được diễn giải như kết quả thực nghiệm đã đạt được.

## 6. Câu hỏi nghiên cứu / mục tiêu đánh giá

- RQ1: Pipeline chuẩn bị dữ liệu có bảo toàn tính toàn vẹn nhãn, ánh xạ lớp đúng và tái lập được cách chia tập trên NEU-DET hay không?
- RQ2: YOLOv8s (sau tinh chỉnh) đạt hiệu năng phát hiện như thế nào trên tập test NEU-DET so với baseline cùng nhiệm vụ khi huấn luyện cùng điều kiện? ([CẦN XÁC NHẬN: baseline chính thức B-D1 YOLOv8n hay cấu hình khác])
- RQ3: Các dạng lỗi nào dễ nhầm/bỏ sót và nguyên nhân chính (dữ liệu, nhãn, đặc trưng hình thái) là gì?
- RQ4 (hệ thống tổng thể): Kết quả Detection và Segmentation độc lập có thể được trình bày đồng thời và giải thích nhất quán cho người dùng QC hay không?

## 7. Phạm vi và giới hạn

### 7.1. Trong phạm vi

- **Detection (NEU-DET):** phát hiện 6 lớp lỗi bề mặt thép bằng YOLOv8s; chuẩn bị nhãn YOLO, huấn luyện, đánh giá và phân tích lỗi (trọng tâm phân công Thành viên 2).
- **Segmentation (NEU-Seg):** phân vùng 3 lớp lỗi có mask bằng U-Net; huấn luyện/đánh giá độc lập theo bộ chỉ số phân vùng. NEU-Seg và NEU-DET là hai bộ dữ liệu/nhánh nhiệm vụ riêng; **không gộp thành một dataset chung**.
- **Tầng ứng dụng:** hiển thị kết quả thị giác; tùy chọn sinh mô tả/hỏi đáp tiếng Việt từ JSON bằng LLM/prompt có sẵn, **không fine-tune**, có cơ chế fallback khi lỗi/timeout/offline; tầng này **không tạo/sửa box, mask hay nhãn**.
- **Baseline:** so sánh trong cùng nhiệm vụ (ví dụ Detection so với baseline detection; Segmentation so với baseline segmentation). Không so sánh trực tiếp mAP với IoU/Dice.

### 7.2. Ngoài phạm vi

- Video/thời gian thực; triển khai dây chuyền sản xuất tự động.
- Fine-tune VLM/LLM lớn; huấn luyện mạng đa nhiệm chung cho detection và segmentation.
- Gộp trọng số/đặc trưng hoặc hợp nhất đầu ra thành một mô hình duy nhất trong luồng chính (Model/Decision Fusion chỉ là hướng mở rộng không bắt buộc, nếu có phải báo cáo tách biệt — [CẦN XÁC NHẬN: có triển khai hay không]).
- Suy luận mask cho các lớp NEU-DET không có mask trong NEU-Seg.

### 7.3. Giới hạn dự kiến

- NEU-DET: ảnh kích thước nhỏ (200×200), 6 lớp, điều kiện thu thập khác môi trường sản xuất thực tế; nhãn có thể tồn tại bất thường cần kiểm tra.
- NEU-Seg: chỉ cung cấp mask cho 3 lớp (theo khảo sát sơ bộ: `inclusion`, `patches`, `scratches`) — [CẦN XÁC NHẬN: ánh xạ giá trị mask 0–3 theo tài liệu chính thức].
- Kết quả phụ thuộc tài nguyên tính toán, thời gian huấn luyện và chất lượng dữ liệu sau kiểm tra.

## 8. Người dùng mục tiêu và bài toán thực tiễn

- **Người dùng mục tiêu:** nhân viên kiểm tra chất lượng (QC/QA), bộ phận kiểm định, người nghiên cứu/giảng dạy về kiểm tra bề mặt.
- **Bài toán thực tiễn:** kiểm tra thủ công tốn thời gian, dễ thiếu nhất quán, khó phát hiện lỗi nhỏ và khó lưu vết theo lô/ảnh. Ứng dụng hỗ trợ cung cấp vị trí/loại lỗi và (ở nhánh phân vùng) vùng ảnh hưởng để phục vụ quan sát và đối chiếu.
- **Nguyên tắc sử dụng:** kết quả AI chỉ mang tính hỗ trợ; quyết định chấp nhận/loại sản phẩm thuộc về con người và quy trình QC của đơn vị.

## 9. Mô tả dữ liệu

### 9.1. NEU-DET (Object Detection)

- **Loại bài toán:** Object Detection.
- **Số lượng:** 1.800 ảnh (kích thước 200×200 theo mô tả bộ dữ liệu).
- **Số lớp:** 6 lớp lỗi bề mặt: `crazing`, `inclusion`, `patches`, `pitted_surface`, `rolled-in_scale`, `scratches`.
- **Nhãn:** Bounding box dạng Pascal VOC XML.
- **Cấu trúc nguồn quan sát trong kho dự án:** `train/` (ảnh + chú thích) và `validation/` (ảnh + chú thích) — [CẦN XÁC NHẬN: mô tả chính thức từ nguồn dữ liệu gốc].
- **Tình trạng/giấy phép:** [CẦN XÁC NHẬN: giấy phép và điều khoản sử dụng NEU-DET].

### 9.2. NEU-Seg (Semantic Segmentation)

- **Loại bài toán:** Semantic Segmentation.
- **Số lượng:** 4.470 ảnh (3.630 training / 840 test theo mô tả dự án).
- **Nhãn:** mask `uint8` giá trị 0–3 (0: nền; 1–3: ba lớp lỗi) — [CẦN XÁC NHẬN: ánh xạ tên lớp theo tài liệu chính thức].
- **Phạm vi lớp:** chỉ 3 lớp có mask; không suy mask từ bounding box NEU-DET.
- **Tình trạng/giấy phép:** [CẦN XÁC NHẬN: giấy phép và điều khoản sử dụng NEU-Seg].

### 9.3. Lưu ý dữ liệu

- Hai bộ dữ liệu phục vụ hai nhiệm vụ/nhánh mô hình khác nhau, được chuẩn bị và đánh giá riêng.
- Cần rà soát trùng lặp/chồng lấn nội dung giữa các tập/bộ khi thực nghiệm (nếu áp dụng) và ghi nhận trong báo cáo dữ liệu — [CẦN XÁC NHẬN: kết quả audit trùng lặp cuối cùng].

## 10. Chính sách chia tập dữ liệu (NEU-DET, Feature 001)

Áp dụng cho pipeline chuẩn bị dữ liệu phát hiện đối tượng (NEU-DET):

| Tập | Tỷ lệ | Số ảnh mục tiêu | Ghi chú |
|---|---:|---:|---|
| Train | 75% | 1.350 | Huấn luyện mô hình |
| Validation | 15% | 270 | Chọn siêu tham số/checkpoint |
| Test | 10% | 180 | Đánh giá cuối, không dùng để chọn mô hình |
| **Tổng** | **100%** | **1.800** | Toàn bộ ảnh NEU-DET sau khi xử lý hợp lệ theo chính sách |

- **Random seed:** `42` (tái lập kết quả chia tập khi dữ liệu và cấu hình không đổi).
- **Chiến lược chia:** **phân tầng đa nhãn (deterministic multi-label stratification)** theo tập lớp xuất hiện trong mỗi ảnh, nhằm giữ phân bố lớp ổn định giữa các tập.
- **Chống rò rỉ dữ liệu:** **duplicate-group leakage prevention** — các mẫu trùng nội dung (duplicate group) được xử lý nguyên tử để không rơi vào các tập khác nhau; trường hợp xung đột nhãn trong nhóm trùng được ghi nhận và xử lý theo chính sách bất thường của Feature 001.
- **Nguyên tắc:** không chỉnh sửa/xóa dữ liệu gốc; mọi quyết định loại/cách ly (nếu có) phải được ghi trong báo cáo kiểm tra và manifest theo đặc tả Feature 001.

> **Lưu ý:** đây là **chính sách đã chốt** cho Feature 001. Không sử dụng các tỷ lệ/cách chia thay thế làm quyết định đã phê duyệt trong tài liệu này.

## 11. Phương pháp đề xuất

### 11.1. Tổng quan hệ thống

Hệ thống gồm hai nhánh thị giác **độc lập** trên cùng ảnh đầu vào:

- **Nhánh Detection:** YOLOv8s (pretrained, fine-tune trên NEU-DET) → đầu ra bounding box, nhãn lớp, độ tin cậy.
- **Nhánh Segmentation:** U-Net (huấn luyện trên NEU-Seg) → đầu ra mask phân vùng theo lớp.

Kết quả hai nhánh được thu thập và hiển thị đồng thời. Nếu bật tầng ngôn ngữ, mô-đun Captioning/VQA chỉ nhận JSON kết quả để sinh mô tả/câu trả lời tiếng Việt (LLM/prompt có sẵn, không fine-tune, có fallback). **YOLOv8s không thực hiện nhiệm vụ segmentation.**

### 11.2. Pipeline chuẩn bị dữ liệu (NEU-DET)

1. Khám phá và ghép cặp ảnh–chú thích trong từng tập nguồn.
2. Xác minh ảnh, phân tích VOC XML, kiểm tra class mapping và bounding box.
3. Phát hiện và ghi nhận bất thường (thiếu cặp, lớp không hợp lệ, tọa độ sai, trùng nội dung, v.v.) theo chính sách fail/quarantine đã cấu hình.
4. Chuyển đổi sang nhãn YOLO chuẩn hóa; tạo split train/validation/test (75/15/10, seed 42, stratification đa nhãn, chống rò rỉ nhóm trùng).
5. Sinh `validation_report.json`, `split_manifest.json` và cấu trúc dữ liệu đầu ra phục vụ huấn luyện — **kế hoạch theo đặc tả Feature 001**; [CẦN XÁC NHẬN: trạng thái nghiệm thu và đường dẫn artifact thực tế].

### 11.3. Huấn luyện và suy luận (dự kiến)

- **Detection:** fine-tune YOLOv8s với đầu vào và siêu tham số phù hợp tài nguyên; chọn checkpoint tốt nhất trên validation. [CẦN XÁC NHẬN: kích thước đầu vào, epoch, batch, công cụ huấn luyện cụ thể].
- **Segmentation:** huấn luyện U-Net (4 kênh đầu ra) với hàm mất mát phù hợp (ví dụ kết hợp Cross-Entropy và Dice) và chiến lược chọn checkpoint trên validation. [CẦN XÁC NHẬN: cấu hình chi tiết, encoder, kích thước ảnh].
- **Suy luận:** tiền xử lý riêng cho từng nhánh, không chia sẻ trọng số/đặc trưng.

## 12. Baseline và mô hình đề xuất

| Nhiệm vụ | Baseline | Mô hình đề xuất | Trạng thái |
|---|---|---|---|
| Object Detection (NEU-DET, 6 lớp) | [CẦN XÁC NHẬN: B-D1 YOLOv8n cùng điều kiện — theo thiết kế dự án; hoặc baseline khác được phê duyệt] | YOLOv8s (fine-tune từ trọng số pretrained, ví dụ COCO) | Kế hoạch |
| Semantic Segmentation (NEU-Seg, 3 lớp lỗi) | [CẦN XÁC NHẬN: B-S1 Otsu/hoặc baseline khác theo thiết kế dự án] | U-Net (huấn luyện trên NEU-Seg) | Kế hoạch |

Không khẳng định kết quả huấn luyện, mAP/IoU/Dice hay so sánh định lượng khi chưa có thực nghiệm.

## 13. Chỉ số đánh giá

### 13.1. Detection (NEU-DET, tập test)

- Precision, Recall
- mAP@0.5, mAP@0.5:0.95

Đánh giá trên tập test độc lập (180 ảnh theo chính sách chia 75/15/10), không dùng để chọn checkpoint/siêu tham số.

### 13.2. Segmentation (NEU-Seg, tập test)

- IoU từng lớp, mIoU, Dice
- Pixel Precision, Pixel Recall

Đánh giá trên tập test NEU-Seg theo giao thức riêng của nhánh phân vùng.

### 13.3. Tầng ứng dụng (nếu triển khai)

- Độ nhất quán với JSON đầu vào, tỷ lệ thông tin sai/hallucination, độ rõ ràng, độ trễ (ví dụ trên 20–30 ảnh demo và 5–10 câu hỏi mẫu — [CẦN XÁC NHẬN]). Chỉ số tầng ứng dụng **không** thay thế và **không** gộp chung với mAP/IoU.

## 14. Quy trình thực nghiệm (dự kiến)

1. **Chuẩn bị & kiểm tra dữ liệu:** rà soát NEU-DET/NEU-Seg, kiểm tra nhãn, chạy pipeline Feature 001, xác nhận báo cáo/manifest và split.
2. **Thiết lập baseline:** huấn luyện/chạy baseline theo cùng split và giao thức đo.
3. **Huấn luyện mô hình đề xuất:** tinh chỉnh YOLOv8s (và huấn luyện U-Net nếu thuộc phạm vi thực hiện).
4. **Đánh giá:** tính chỉ số trên tập test; ghi lại cấu hình, seed, phiên bản.
5. **Phân tích lỗi:** confusion/false positive/false negative, lỗi nhỏ, trường hợp khó; đề xuất cải tiến.
6. **Tích hợp & kiểm thử demo:** kiểm tra hiển thị hai nhánh độc lập và (nếu có) tầng ngôn ngữ/fallback.
7. **Báo cáo:** tổng hợp phương pháp, kết quả, giới hạn và khuyến nghị.

## 15. Kết quả kỳ vọng và sản phẩm bàn giao

### 15.1. Kết quả kỳ vọng

- Bộ dữ liệu NEU-DET đã chuẩn hóa cho huấn luyện detection với split tái lập được và báo cáo kiểm tra minh bạch.
- Mô hình YOLOv8s được huấn luyện/tinh chỉnh và đánh giá định lượng trên tập test (khi hoàn thành thực nghiệm).
- Báo cáo phân tích lỗi và nhận xét về khả năng hỗ trợ QC trong phạm vi dữ liệu nghiên cứu.

### 15.2. Sản phẩm bàn giao (dự kiến)

| Hạng mục | Mô tả | Phạm vi/Owner dự kiến |
|---|---|---|
| Dữ liệu chuẩn bị | Nhãn YOLO, cấu trúc dữ liệu xử lý, `validation_report.json`, `split_manifest.json`, tài liệu cấu hình | Feature 001 / Thành viên 2 (phần detection data) |
| Mã nguồn detection | Script/module tiền xử lý, huấn luyện, suy luận YOLOv8s | Thành viên 2 |
| Checkpoint & log | Checkpoint tốt nhất, log huấn luyện | Thành viên 2 — [CẦN XÁC NHẬN: khi thực nghiệm hoàn tất] |
| Đánh giá | Bảng Precision/Recall/mAP@0.5/mAP@0.5:0.95, phân tích lỗi | Thành viên 2 — [CẦN XÁC NHẬN] |
| Segmentation | Mô hình/mã/báo cáo U-Net và chỉ số IoU/Dice/mIoU... | Thành viên phụ trách — [CẦN XÁC NHẬN] |
| Demo & tài liệu | Ứng dụng/demo, hướng dẫn chạy, báo cáo tổng hợp | Nhóm — [CẦN XÁC NHẬN] |

## 16. Phân công thành viên

| Thành viên | Vai trò | Nhiệm vụ chính | Sản phẩm dự kiến |
|---|---|---|---|
| Thành viên 1 | Data Owner & Preprocessing | Kiểm tra NEU-DET/NEU-Seg, rà soát nhãn/mask, phát hiện bất thường, phối hợp split, quản lý demo set | Dataset kiểm tra/chuẩn hóa, Data Card, script preprocessing, báo cáo kiểm tra dữ liệu |
| **Thành viên 2** | **Detection Engineer – YOLOv8s** | Chuẩn bị nhãn NEU-DET theo định dạng YOLO; cấu hình và huấn luyện YOLOv8s; tinh chỉnh siêu tham số; chọn checkpoint tốt nhất trên validation; đánh giá Precision, Recall, mAP@0.5, mAP@0.5:0.95; phân tích lỗi detection | Checkpoint YOLOv8s, code train/predict, log huấn luyện, bảng chỉ số đánh giá, báo cáo phân tích lỗi |
| Thành viên 3 | Baseline Detection – YOLOv8n | Xây dựng/huấn luyện baseline YOLOv8n cùng điều kiện; so sánh với YOLOv8s; đo suy luận (nếu có) | Kết quả baseline, so sánh hiệu năng/tốc độ — [CẦN XÁC NHẬN] |
| Thành viên 4 | Segmentation Engineer – U-Net | Chuẩn bị NEU-Seg, huấn luyện U-Net, đánh giá IoU/Dice/mIoU, phân tích lỗi phân vùng | Checkpoint/mã/báo cáo segmentation — [CẦN XÁC NHẬN] |
| Thành viên 5 | Application/Integration | Tích hợp demo, hiển thị kết quả, xử lý lỗi nhánh, (tùy chọn) tầng Captioning/VQA từ JSON | Ứng dụng demo, tài liệu triển khai — [CẦN XÁC NHẬN] |
| Thành viên 6 | Evaluation & Report | Thiết kế đánh giá, tổng hợp kết quả, viết báo cáo, phối hợp kiểm thử | Báo cáo tổng hợp, bảng so sánh — [CẦN XÁC NHẬN] |

> Bảng trên tổng hợp từ phân công dự án; chi tiết có thể điều chỉnh theo thống nhất nhóm — [CẦN XÁC NHẬN].

## 17. Kế hoạch thời gian (dự kiến)

| Tuần | Nội dung chính | Kết quả mong đợi |
|---|---|---|
| 1 | Khảo sát, chốt phạm vi, rà soát tài liệu/nguồn dữ liệu | Phiếu đăng ký, mô tả bài toán, kế hoạch chi tiết |
| 2 | Chuẩn bị dữ liệu, thiết kế giao thức đánh giá, chạy/hoàn thiện Feature 001 | Bộ dữ liệu chuẩn bị (dự kiến), báo cáo kiểm tra |
| 3 | Thiết lập baseline (Detection/Segmentation theo phạm vi) | Kết quả baseline ban đầu — [CẦN XÁC NHẬN] |
| 4–5 | Huấn luyện/tinh chỉnh mô hình đề xuất | Mô hình và log thí nghiệm — [CẦN XÁC NHẬN] |
| 6 | Tích hợp demo, (tùy chọn) tầng ngôn ngữ, kiểm thử lỗi | Bản demo — [CẦN XÁC NHẬN] |
| 7 | Đánh giá trên test, phân tích lỗi, so sánh baseline | Bảng kết quả, phân tích — [CẦN XÁC NHẬN] |
| 8 | Hoàn thiện báo cáo, slide, bàn giao mã/tài liệu | Hồ sơ bàn giao — [CẦN XÁC NHẬN] |

## 18. Tài liệu tham khảo

1. K. Song và Y. Yan, “A noise robust method based on completed local binary patterns for hot-rolled steel strip surface defects,” *Applied Surface Science*, 285, 2013. (NEU surface defect database — [CẦN XÁC NHẬN: trích dẫn chính xác theo nguồn sử dụng])
2. NEU-DET Dataset (Surface Defect Database) — [CẦN XÁC NHẬN: URL/DOI và điều khoản truy cập].
3. NEU-Seg Dataset — [CẦN XÁC NHẬN: URL/DOI, phiên bản, điều khoản truy cập].
4. Ultralytics YOLOv8 Documentation — [CẦN XÁC NHẬN: phiên bản tài liệu/phần mềm sử dụng].
5. O. Ronneberger, P. Fischer, và T. Brox, “U-Net: Convolutional Networks for Biomedical Image Segmentation,” *MICCAI*, 2015.
6. Tài liệu thiết kế nội bộ dự án: `define_and_design_v2.ipynb`, thư mục `assets/define-design/`, đặc tả Feature 001 (`yolov8-detection/specs/001-neu-det-data-preparation/`).

---

**Ghi chú quản lý tài liệu:** Tệp `PHIEU_DANG_KY_DE_TAI.md` là nguồn soạn thảo chính; `PHIEU_DANG_KY_DE_TAI.docx` là bản phục vụ nộp/trình bày. Các phiên bản đăng ký cũ (nếu có) được lưu trong `Research/archive/` và không dùng làm bản chính thức. Nội dung tài liệu này mô tả đề xuất/kế hoạch và các quyết định kỹ thuật đã chốt (trong đó có chính sách chia tập NEU-DET 75/15/10, seed 42); tài liệu **không** thay thế biên bản phê duyệt của giảng viên/hội đồng. Mọi mục đánh dấu **[CẦN XÁC NHẬN]** cần được bổ sung trước khi nộp chính thức.
