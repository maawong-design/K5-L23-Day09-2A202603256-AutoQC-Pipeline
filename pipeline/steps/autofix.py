"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict
from pathlib import Path

import yaml

from ..common import ERROR, parse_yolo_line


_DROP_LINE_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
_REMOVE_IMAGE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _format_number(value):
    """Bước phụ: ghi tọa độ gọn, ổn định, không đổi sang dạng số mũ."""
    return f"{value:.10f}".rstrip("0").rstrip(".") or "0"


def _clipped_line(text):
    """Bước phụ: cắt các cạnh box vào [0, 1], trả None nếu không còn diện tích."""
    try:
        class_id, cx, cy, width, height = parse_yolo_line(text)
    except (ValueError, OverflowError):
        return None
    if width <= 0 or height <= 0:
        return None

    left = max(0.0, cx - width / 2)
    top = max(0.0, cy - height / 2)
    right = min(1.0, cx + width / 2)
    bottom = min(1.0, cy + height / 2)
    if right <= left or bottom <= top:
        return None

    new_cx, new_cy = (left + right) / 2, (top + bottom) / 2
    new_width, new_height = right - left, bottom - top
    return " ".join(map(_format_number, (class_id, new_cx, new_cy, new_width, new_height)))


def fix(ds, issues, cfg):
    # Bước 1: chỉ nhận lỗi bắt buộc; gom các thao tác xóa ảnh để xử lý trước.
    errors = [issue for issue in issues if issue.severity == ERROR]
    remove_stems = {}
    for issue in errors:
        if issue.code.startswith("DUP_IMAGE_") or issue.code in _REMOVE_IMAGE_CODES:
            remove_stems.setdefault(issue.image, issue)

    fixes = []
    removed = set()

    # Bước 2: xóa ảnh lỗi cùng nhãn của nó, mỗi ảnh chỉ ghi một thay đổi.
    for stem, issue in remove_stems.items():
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)
        if image_path is None and not label_path.exists():
            continue
        before = image_path.name if image_path is not None else "(không còn ảnh)"
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        label_path.unlink(missing_ok=True)
        removed.add(stem)
        fixes.append({"image": stem, "line": None, "action": "remove_image",
                      "before": before, "after": "đã xóa ảnh và nhãn"})

    # Bước 3: chuyển các ảnh thiếu nhãn sang người gán, không tự tạo file rỗng.
    needs_label = set()
    for issue in errors:
        if issue.code == "MISSING_LABEL_FILE" and issue.image not in removed:
            if issue.image not in needs_label:
                fixes.append({"image": issue.image, "line": None, "action": "needs_label",
                              "before": "(không có file)", "after": "chuyển người gán"})
                needs_label.add(issue.image)

    # Bước 4: sửa tên lớp trong data.yaml khi check báo cấu hình tên lớp sai.
    if any(issue.code == "BAD_CLASS_NAME" and issue.image == "data.yaml" for issue in errors):
        yaml_path = ds.yaml_path
        try:
            original_text = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""
            data = yaml.safe_load(original_text) or {}
        except (OSError, yaml.YAMLError):
            original_text, data = "", {}
        if not isinstance(data, dict):
            data = {}
        expected_names = {i: name for i, name in enumerate(cfg["classes"])}
        current = data.get("names", {})
        try:
            current_names = dict(enumerate(current)) if isinstance(current, list) else {
                int(key): value for key, value in current.items()
            }
        except (AttributeError, TypeError, ValueError):
            current_names = {}
        if current_names != expected_names or not yaml_path.exists():
            data["names"] = expected_names
            updated_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
            yaml_path.write_text(updated_text, encoding="utf-8")
            fixes.append({"image": "data.yaml", "line": None, "action": "rename_classes",
                          "before": original_text.strip(), "after": updated_text.strip()})

    # Bước 5: gom lỗi theo ảnh và số dòng gốc để tránh lệch chỉ số khi xóa nhiều dòng.
    line_ops = defaultdict(lambda: defaultdict(set))
    for issue in errors:
        if issue.image in removed or issue.line is None:
            continue
        if issue.code in _DROP_LINE_CODES or issue.code == "BOX_OUT_OF_IMAGE":
            line_ops[issue.image][issue.line].add(issue.code)

    # Bước 6: ưu tiên xóa dòng nếu dòng có nhiều lỗi; nếu chỉ tràn thì cắt box.
    for stem, operations in line_ops.items():
        label_path = ds.label_path(stem)
        if stem in removed or not label_path.exists():
            continue
        original_text = label_path.read_text(encoding="utf-8", errors="replace")
        original_lines = original_text.splitlines()
        trailing_newline = original_text.endswith(("\n", "\r"))
        updated_lines = []
        changed = False

        for line_number, text in enumerate(original_lines, 1):
            codes = operations.get(line_number, set())
            if codes & _DROP_LINE_CODES:
                fixes.append({"image": stem, "line": line_number, "action": "drop_line",
                              "before": text, "after": ""})
                changed = True
                continue

            if "BOX_OUT_OF_IMAGE" in codes:
                clipped = _clipped_line(text)
                if clipped is None:
                    fixes.append({"image": stem, "line": line_number, "action": "drop_line",
                                  "before": text, "after": ""})
                    changed = True
                    continue
                if clipped != text:
                    fixes.append({"image": stem, "line": line_number, "action": "clip_box",
                                  "before": text, "after": clipped})
                    updated_lines.append(clipped)
                    changed = True
                    continue

            updated_lines.append(text)

        # Bước 7: ghi một lần cho mỗi file, giữ dấu xuống dòng cuối nếu file vốn có.
        if changed:
            updated_text = "\n".join(updated_lines)
            if trailing_newline and updated_lines:
                updated_text += "\n"
            label_path.write_text(updated_text, encoding="utf-8")

    return fixes
