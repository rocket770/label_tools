import cv2
import numpy as np


def polygon_is_valid(points):
    return points is not None and len(points) >= 3


def _orientation(a, b, c):
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if value == 0:
        return 0
    return 1 if value > 0 else 2


def _on_segment(a, b, c):
    return (
        min(a[0], c[0]) <= b[0] <= max(a[0], c[0])
        and min(a[1], c[1]) <= b[1] <= max(a[1], c[1])
    )


def _segments_intersect(p1, q1, p2, q2):
    o1 = _orientation(p1, q1, p2)
    o2 = _orientation(p1, q1, q2)
    o3 = _orientation(p2, q2, p1)
    o4 = _orientation(p2, q2, q1)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and _on_segment(p1, p2, q1):
        return True
    if o2 == 0 and _on_segment(p1, q2, q1):
        return True
    if o3 == 0 and _on_segment(p2, p1, q2):
        return True
    if o4 == 0 and _on_segment(p2, q1, q2):
        return True

    return False


def polygon_self_intersects(points):
    point_count = len(points)
    if point_count < 4:
        return False

    for i in range(point_count):
        p1 = points[i]
        q1 = points[(i + 1) % point_count]

        for j in range(i + 1, point_count):
            if j == i:
                continue

            if j == i + 1 or (i == 0 and j == point_count - 1):
                continue

            p2 = points[j]
            q2 = points[(j + 1) % point_count]

            if _segments_intersect(p1, q1, p2, q2):
                return True

    return False


def rasterize_polygon_mask(shape, points):
    h, w = shape
    poly = np.array(points, dtype=np.int32)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [poly], 1)
    return mask


def fill_mask_holes(binary_mask):
    mask_255 = (binary_mask > 0).astype(np.uint8) * 255
    h, w = mask_255.shape

    flood = mask_255.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(flood, flood_mask, (0, 0), 255)

    flood_inv = cv2.bitwise_not(flood)
    filled = cv2.bitwise_or(mask_255, flood_inv)
    return (filled > 0).astype(np.uint8)


def apply_polygon_to_mask(
    mask_frame,
    points,
    target_label,
    fill_holes=False,
    apply_scope="background",
):
    if not polygon_is_valid(points):
        return mask_frame, False, "Polygon: need at least 3 points"

    if polygon_self_intersects(points):
        return mask_frame, False, "Polygon: shape crosses over itself"

    region = rasterize_polygon_mask(mask_frame.shape, points)

    if fill_holes:
        region = fill_mask_holes(region)

    updated = mask_frame.copy()
    fill_region = region > 0
    if apply_scope == "background":
        fill_region &= mask_frame == 0
    elif apply_scope == "mask":
        fill_region &= mask_frame != 0
    elif apply_scope != "both":
        return mask_frame, False, f"Polygon: unknown apply scope '{apply_scope}'"

    updated[fill_region] = target_label

    changed = not np.array_equal(mask_frame, updated)
    if not changed:
        if apply_scope == "background":
            return mask_frame, False, "Polygon: no background pixels inside selection"
        if apply_scope == "mask":
            return mask_frame, False, "Polygon: no labeled pixels inside selection"
        return mask_frame, False, "Polygon: no changes made"

    return updated, True, f"Polygon applied with label {target_label}"
