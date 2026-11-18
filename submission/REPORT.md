# Báo cáo Day 09 — Mai Văn Phong, 2A202603256

## 1. Kết luận trước
Pipeline kết luận **Hold**. Intake nhận 202/224 ảnh và loại 22 ảnh (hỏng, sai kích thước, trùng hoặc bị gắn cờ rò rỉ). Dataset nháp có 202 ảnh; sau khi review mô phỏng 80 ảnh, không còn lỗi bắt buộc nhưng 58/202 ảnh vẫn có cảnh báo (28,71%), vượt ngưỡng Hold 10%.

## 2. Lỗi và phân việc
Vòng 1 ghi 58 lỗi bắt buộc và 267 cảnh báo. Số dưới đây là số cờ; số ảnh/dòng được nêu riêng khi khác số cờ.

| Mã lỗi | Số cờ (ảnh/dòng) | Ai xử lý | Xử lý |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2 ảnh | Máy | Loại ảnh hỏng ở intake |
| `BAD_SIZE` | 3 ảnh | Máy | Loại ảnh quá nhỏ |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy | Giữ ảnh đầu, loại bản trùng |
| `LEAK_TEST` | 5 ảnh | Máy | Loại ứng viên trùng test/val |
| `DUP_IMAGE_NEAR` | 4 ảnh | Máy | Loại ảnh pHash gần trùng |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Chuyển người gán; máy không tạo nhãn |
| `BAD_CLASS_NAME` | 2 cờ, 1 `data.yaml` | Máy | Đưa `names` về đúng thứ tự lớp |
| `BAD_FORMAT` | 3 dòng | Máy | Xóa dòng không đúng 5 cột số |
| `BAD_CLASS_ID` | 6 dòng | Máy | Xóa dòng có ID ngoài khoảng |
| `BOX_ZERO` | 4 dòng | Máy | Xóa box có cạnh bằng 0 |
| `DUP_BOX` | 7 dòng | Máy | Xóa dòng lặp phía sau |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy | Cắt box vào khung ảnh |
| `EMPTY_LABEL` | 12 ảnh | Người | Phân biệt ảnh nền với ảnh thiếu nhãn |
| `BOX_TINY` | 6 dòng, 4 ảnh | Người | Xem lại box nhỏ |
| `BOX_HUGE` | 3 dòng | Người | Xác nhận box phủ phần lớn ảnh |
| `CLASS_RARE` | 4 cờ, cấp dataset | Người | Xem lại phân bố lớp |
| `POSSIBLE_MISSING` | 152 cờ, 86 ảnh | Người | Model nghi thiếu box |
| `POSSIBLE_LOOSE_BOX` | 44 cờ, 36 ảnh | Người | Model nghi box lỏng/lệch |
| `POSSIBLE_WRONG_CLASS` | 21 cờ, 20 ảnh | Người | Model bất đồng lớp |
| `POSSIBLE_FALSE_POS` | 25 cờ, 24 ảnh | Người | Model không khớp box nhãn |

Hàng đợi xếp theo tổng trọng số cảnh báo và độ tin cậy model; lỗi thiếu nhãn và bất đồng lớp có trọng số cao. Ví dụ, `img_0160` đứng đầu (35,692) với `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`. Ngân sách 80/143 ảnh được dùng hết. Trong 80 ảnh này có 74 ảnh mang cờ ngữ nghĩa; vòng 2 ghi 187 cờ ngữ nghĩa (124 thiếu box, 30 box lỏng, 21 bất đồng lớp, 12 false positive). Đây là số cảnh báo của model, không phải 187 lỗi đã được xác nhận.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 14 | `DUP_IMAGE_NEAR`: 1.00 / 0.50 → 1.00 / 0.67; `DUP_IMAGE_EXACT`: 1.00 / 1.00 → 1.00 / 1.00 | 14 giữ precision calib 1.00; xem raw thấy 6 cặp test và 2 cặp nội bộ ở dist=16 là ảnh khác nhau, nên ưu tiên tránh xóa nhầm. |
| `second_opinion.conf` | 0.25 | 0.25 | Giữ nguyên: WRONG_CLASS 0.56 / 0.83; MISSING 0.50 / 1.00; LOOSE_BOX 0.29 / 0.40; FALSE_POS 0.36 / 1.00 | 0.25 giữ recall MISSING ở 1.00; 0.1 không tăng recall MISSING nhưng giảm precision, còn từ 0.4 trở lên làm recall LOOSE_BOX giảm. |

Calib chỉ có 6 lỗi trùng gần được chèn và không có `LEAK_TEST`: ngưỡng 16 đạt precision 1.00 trong calib nhưng khi xem raw, 6 ứng viên `LEAK_TEST` và hai cặp nội bộ `img_0011`/`img_0008`, `img_0177`/`img_0113` ở dist=16 là ảnh khác nhau. Ngưỡng 14 tránh xóa nhầm 8 ảnh nhưng bỏ sót cặp trùng thật `img_0084`/`img_0074` ở dist=16.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
Chạy `pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` cho kết luận **Rework**, mã thoát 20, còn 6 lỗi bắt buộc và không tạo `work/exp_nb/clean_v1/manifest.json`. Điều này xác nhận thiếu lượt người review thì gate chặn xuất bản.

Hai điểm mù có bằng chứng: (1) ở `second_opinion.conf=0.25`, calibration chỉ bắt 2/5 box lỏng (recall 0.40), bỏ sót 3/5; (2) ngưỡng pHash 14 bỏ sót cặp trùng thật `img_0084`/`img_0074` ở dist=16 để tránh các false positive đã thấy trên raw. Cờ từ model chỉ là cảnh báo; model có thể cùng sai với nhãn.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Chưa có phiên Colab/T4 kết nối trong workspace. Vì vậy chưa có mAP50 theo seed hay độ lệch chuẩn và chưa thể kết luận clean tốt hơn raw.

## 6. Quyết định và ghi chú AI
**Quyết định: Hold.** Để đạt Release, cần xử lý cảnh báo trên ít nhất 38 trong 58 ảnh còn cảnh báo (để còn tối đa 20/202 ảnh, dưới 10%) và không để phát sinh lỗi bắt buộc.

AI được dùng để viết bốn module theo `GUIDE.md`; đã rà diff, chạy 79 test, calibration và xem trực quan các cặp pHash. Một lần AI sai: ban đầu chọn pHash 16 chỉ dựa trên calib; xem ảnh raw phát hiện 8 cặp khác nhau bị gộp ở dist=16, nên hạ ngưỡng xuống 14 và chạy lại pipeline.

CVAT precheck cho 20 ảnh đầu hàng đợi: `width < 20` tìm 10 box trong `img_0020` (4), `img_0067` (1), `img_0030` (4), `img_0210` (1); chỉ box dòng 9 của `img_0030` cũng là `BOX_TINY` theo ngưỡng cạnh ngắn dưới 12 px. Thuộc tính `can_review` dùng để người gán đánh dấu object cần xem lại; pipeline biểu diễn nhu cầu đó qua cảnh báo và hàng đợi có trọng số. Gói YOLO 1.1 đã chuẩn bị tại `work/cvat_task_top20_yolo11.zip`; project và filter trong giao diện CVAT chưa được tạo vì workspace không có kết nối CVAT.
