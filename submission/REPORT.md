# Báo cáo Day 09 — Mai Văn Phong, 2A202603256

## 1. Kết luận
Pipeline kết luận **Hold**: nhận 202/224 ảnh, loại 22 ảnh hỏng, nhỏ, trùng hoặc rò rỉ. Sau review mô phỏng 80 ảnh, không còn lỗi bắt buộc nhưng 58/202 ảnh còn cảnh báo (28,71%), vượt ngưỡng 10%; `clean_v1` chỉ là bản nháp.

## 2. Lỗi và phân việc
Vòng 1 có 58 lỗi bắt buộc và 267 cảnh báo. Intake loại 2 ảnh hỏng, 3 ảnh nhỏ, 8 trùng chính xác, 5 ứng viên rò rỉ và 4 gần trùng. Autofix ghi 35 hành động: xóa 20 dòng, cắt 8 box, chuẩn hóa tên lớp 1 lần; 6 ảnh thiếu file nhãn chuyển người gán, không tạo nhãn giả.

Cảnh báo người xử lý: `EMPTY_LABEL` 12 ảnh, `BOX_TINY` 6 dòng/4 ảnh, `BOX_HUGE` 3 dòng, `CLASS_RARE` 4 cờ. Cảnh báo model: `POSSIBLE_MISSING` 152 cờ/86 ảnh, `POSSIBLE_LOOSE_BOX` 44/36, `POSSIBLE_WRONG_CLASS` 21/20, `POSSIBLE_FALSE_POS` 25/24. Hàng đợi xếp theo trọng số và độ tin cậy; ngân sách dùng hết 80/143 ảnh. Trong 80 ảnh có 74 ảnh mang cờ ngữ nghĩa; vòng 2 có 187 cảnh báo (124 thiếu box, 30 lỏng, 21 sai lớp, 12 false positive). Đây là cảnh báo, chưa phải lỗi đã xác nhận.

## 3. Calibration hai ngưỡng
| Tham số | Mặc định → chọn | Precision / Recall | Đánh đổi |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → **14** | Gần trùng: 1,00/0,50 → 1,00/0,67; chính xác: 1,00/1,00 | Ngưỡng 16 tăng recall lên 0,83 nhưng xem raw thấy 6 ứng viên test và 2 cặp nội bộ ở khoảng cách 16 là ảnh khác nhau. Chọn 14 để tránh xóa nhầm; bỏ sót cặp thật `img_0084`/`img_0074` ở khoảng cách 16. |
| `second_opinion.conf` | 0,25 → **0,25** | Sai lớp 0,56/0,83; thiếu box 0,50/1,00; box lỏng 0,29/0,40; false positive 0,36/1,00 | Giữ recall thiếu box 1,00; 0,1 giảm precision mà không tăng recall, còn từ 0,4 làm giảm recall box lỏng. |

Calib chỉ có 6 cặp gần trùng được chèn, không có `LEAK_TEST`; do đó không đủ để chọn ngưỡng nếu chưa xem ảnh raw.

## 4. Cửa chặn và điểm mù
Chạy `--budget 0` cho **Rework** (mã 20), còn 6 lỗi bắt buộc và không tạo manifest export. Gate chặn khi thiếu lượt review. Calibration chỉ bắt 2/5 box lỏng (recall 0,40); pHash 14 bỏ sót cặp thật ở khoảng cách 16 để tránh false positive. Model cũng có thể cùng sai với nhãn.

## 5. Train raw vs clean
**Chưa chạy:** chưa có runtime Colab/T4 trong phiên làm việc. Chưa có mAP50 theo seed hoặc độ lệch chuẩn; chưa thể kết luận clean tốt hơn raw. Notebook đã cấu hình cho repo này.

## 6. Quyết định, AI và CVAT
**Quyết định: Hold.** Muốn xuống dưới 10% cần xử lý cảnh báo ở ít nhất 38/58 ảnh (còn tối đa 20/202) và không để phát sinh lỗi bắt buộc.

- **Prompt:** viết bốn module theo `GUIDE.md`/docstring, xử lý ca biên và comment từng bước.
- **Kiểm tra:** 79 pytest xanh, calibration trên lỗi chèn sẵn, chạy pipeline và xem ảnh các cặp pHash trên raw.
- **Lần AI sai:** ban đầu chọn pHash 16 chỉ dựa trên calib; raw cho thấy 8 cặp khác nhau ở khoảng cách 16, nên hạ xuống 14.

CVAT precheck trên 20 ảnh đầu hàng đợi với `width < 20` tìm 10 box ở 4 ảnh (`img_0020`: 4, `img_0067`: 1, `img_0030`: 4, `img_0210`: 1); chỉ dòng 9 của `img_0030` đồng thời là `BOX_TINY` (<12 px). `can_review` đánh dấu object cần người xem; pipeline thể hiện nhu cầu tương tự qua cảnh báo/hàng đợi. Gói import ở `work/cvat_task_top20_yolo11.zip`; project/filter CVAT chưa được tạo.
