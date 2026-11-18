"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    # Bước 1: chuẩn hóa tập ảnh để mẫu số không đếm lặp.
    stems = set(image_stems)
    n_images = len(stems)
    reviewed = set(reviewed or ())

    # Bước 2: lỗi bắt buộc luôn chặn, kể cả lỗi cấp dataset hoặc ảnh đã được xem.
    n_errors = sum(issue.severity == ERROR for issue in issues)

    # Bước 3: đếm số ảnh còn cảnh báo; bỏ issue cấp dataset và ảnh đã review.
    warn_images = {
        issue.image for issue in issues
        if issue.severity == WARN
        and issue.image in stems
        and issue.image not in reviewed
    }
    n_warn_images = len(warn_images)
    warn_ratio = n_warn_images / n_images if n_images else 0.0
    threshold = cfg["gate"]["warn_ratio_hold"]

    # Bước 4: áp dụng thứ tự ưu tiên Rework, Hold rồi Release.
    if n_errors:
        decision = "Rework"
        reasons = [f"Còn {n_errors} lỗi bắt buộc (ERROR); cần sửa trước khi phát hành."]
    elif warn_ratio >= threshold:
        decision = "Hold"
        reasons = [
            f"{n_warn_images}/{n_images} ảnh còn cảnh báo ({warn_ratio:.4f}), "
            f"đạt/vượt ngưỡng giữ {threshold:.4f}; cần người xem thêm."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; {n_warn_images}/{n_images} ảnh còn cảnh báo "
            f"({warn_ratio:.4f}), dưới ngưỡng giữ {threshold:.4f}."
        ]

    # Bước 5: trả số liệu và tỷ lệ đã làm tròn cho báo cáo.
    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": round(warn_ratio, 4),
        "reasons": reasons,
    }
