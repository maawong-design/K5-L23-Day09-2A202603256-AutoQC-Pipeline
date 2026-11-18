"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    # Bước 1: nạp dự đoán đã cache nếu caller chưa truyền chúng vào.
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    # Bước 2: lấy các ngưỡng để hai hướng so khớp dùng cấu hình thống nhất.
    rules = cfg["second_opinion"]
    min_conf = rules["conf"]
    min_area_px = rules["min_area_px"]
    fp_conf = rules["fp_conf"]
    iou_missing = rules["iou_missing"]
    iou_match = rules["iou_match"]
    iou_loose = rules["iou_loose"]
    issues = []

    # Bước 3: duyệt ảnh theo thứ tự dataset; bỏ ảnh thiếu file nhãn hoặc thiếu cache.
    for image_path in ds.image_files():
        stem = image_path.stem
        if stem not in preds:
            continue
        source_lines = ds.read_label_lines(stem)
        if source_lines is None:
            continue
        image_size = ds.image_size(stem)
        if image_size is None:
            image_width = image_height = None
        else:
            image_width, image_height = image_size

        # Bước 4: parse nhãn hợp lệ nhưng vẫn giữ số dòng vật lý cho false positive.
        labels = []
        for line, text in source_lines:
            try:
                box = parse_yolo_line(text)
            except (ValueError, OverflowError):
                continue
            class_id, _, _, width, height = box
            if not 0 <= class_id < len(ds.classes) or width <= 0 or height <= 0:
                continue
            labels.append((line, box))

        # Bước 5: tách dự đoán cho so thiếu nhãn và so false positive theo hai ngưỡng riêng.
        model_rows = []
        for row in preds.get(stem, []):
            try:
                if len(row) != 6:
                    continue
                raw_class, raw_conf, cx, cy, width, height = row
                class_value = float(raw_class)
                class_id = int(class_value)
                conf = float(raw_conf)
                box_values = tuple(float(value) for value in (cx, cy, width, height))
            except (TypeError, ValueError, OverflowError):
                continue
            # Bước phụ: chỉ dùng giá trị đã chuẩn hóa; cache sai kiểu không được làm dừng pipeline.
            if class_value != class_id or not 0 <= class_id < len(ds.classes):
                continue
            if box_values[2] <= 0 or box_values[3] <= 0:
                continue
            if not all(value == value and abs(value) != float("inf")
                       for value in (class_value, conf, *box_values)):
                continue
            model_rows.append((class_id, conf, box_values))

        fp_predictions = [row for row in model_rows if row[1] >= fp_conf]
        candidates = []
        if image_width is not None and image_height is not None:
            for row in model_rows:
                class_id, conf, box = row
                area_px = box[2] * image_width * box[3] * image_height
                if conf >= min_conf and area_px >= min_area_px:
                    candidates.append(row)

        # Bước 6: mỗi dự đoán đủ tin cậy phát sinh tối đa một cảnh báo nhãn.
        for class_id, conf, pred_box in candidates:
            overlaps = [(iou_xywh(pred_box, label[1][1:]), label[1][0]) for label in labels]
            matching = [(iou, label_class) for iou, label_class in overlaps if iou >= iou_missing]
            if not matching:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                                    "model thấy vật thể chưa có box nhãn tương ứng", extra={"conf": conf}))
                continue

            same_class = [iou for iou, label_class in matching if label_class == class_id]
            if same_class:
                best_iou = max(same_class)
                if best_iou < iou_loose:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        "box nhãn cùng lớp có thể quá lỏng hoặc lệch", extra={
                                            "conf": conf, "iou": best_iou,
                                        }))
                continue

            best_other_iou = max(iou for iou, _ in matching)
            if best_other_iou >= iou_match:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                    "model và nhãn có thể bất đồng về lớp của vật thể", extra={
                                        "conf": conf, "iou": best_other_iou,
                                    }))

        # Bước 7: gắn cờ từng dòng nhãn không khớp dự đoán nào đủ fp_conf.
        for line, label_box in labels:
            overlaps = [iou_xywh(label_box[1:], pred_box)
                        for _, _, pred_box in fp_predictions]
            best_iou = max(overlaps, default=0.0)
            if best_iou < iou_missing:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    "box nhãn không khớp dự đoán nào của model", line,
                                    {"iou": best_iou}))

    return issues
