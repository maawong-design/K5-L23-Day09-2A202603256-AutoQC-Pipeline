"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    # Bước 1: lấy các ngưỡng từ cấu hình và chuẩn bị danh sách issue.
    rules = cfg["label_format"]
    overflow_tol = rules["overflow_tol"]
    min_box_px = rules["min_box_px"]
    max_box_frac = rules["max_box_frac"]
    dup_box_iou = rules["dup_box_iou"]
    issues = []

    # Bước 2: duyệt file và dòng theo thứ tự ổn định; line giữ số dòng vật lý gốc.
    for label_file in ds.label_files():
        stem = label_file.stem
        image_size = ds.image_size(stem)
        previous_boxes = []
        for line, text in ds.read_label_lines(stem) or []:
            # Bước 3: xác thực cú pháp, ID lớp và kích thước trước khi xét hình học.
            try:
                box = parse_yolo_line(text)
            except (ValueError, OverflowError) as exc:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem,
                                    f"dòng nhãn không đúng định dạng YOLO: {exc}", line))
                continue

            class_id, cx, cy, width, height = box
            if not 0 <= class_id < len(ds.classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"ID lớp {class_id} nằm ngoài khoảng hợp lệ", line,
                                    {"class_id": class_id}))
                continue
            if width <= 0 or height <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem,
                                    "chiều rộng và chiều cao của box phải lớn hơn 0", line))
                continue

            # Bước 4: đo mức tràn lớn nhất của bốn cạnh so với khung ảnh chuẩn hóa.
            left, top = cx - width / 2, cy - height / 2
            right, bottom = cx + width / 2, cy + height / 2
            overflow = max(0.0, -left, -top, right - 1.0, bottom - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box tràn khung ảnh {overflow:.6g}", line,
                                    {"overflow": overflow}))

            # Bước 5: so box hiện tại với các dòng hợp lệ đứng trước, cùng lớp.
            for prev_class, prev_box in previous_boxes:
                if prev_class == class_id and iou_xywh(box[1:], prev_box) > dup_box_iou:
                    issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                        "box lặp với một dòng nhãn đứng trước", line,
                                        {"iou": iou_xywh(box[1:], prev_box)}))
                    break

            # Bước 6: cảnh báo box quá nhỏ theo cạnh ngắn tính bằng pixel.
            if image_size is not None:
                image_width, image_height = image_size
                shortest_edge_px = min(width * image_width, height * image_height)
                if shortest_edge_px < min_box_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                        f"cạnh ngắn của box chỉ {shortest_edge_px:.6g} px", line,
                                        {"shortest_edge_px": shortest_edge_px}))

            # Bước 7: cảnh báo box chiếm phần quá lớn của ảnh và lưu làm ứng viên so trùng.
            if width * height > max_box_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                    f"box chiếm {width * height:.6g} diện tích chuẩn hóa", line,
                                    {"area_frac": width * height}))
            previous_boxes.append((class_id, box[1:]))

    return issues
