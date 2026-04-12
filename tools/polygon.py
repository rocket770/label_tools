import cv2
import numpy as np

def polygon_is_valid(points):
    return points is not None and len(points) >= 3

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

def apply_polygon_to_mask(mask_frame, points, target_label, fill_holes=False):
    if not polygon_is_valid(points):
        return mask_frame, False

    region = rasterize_polygon_mask(mask_frame.shape, points)

    if fill_holes:
        region = fill_mask_holes(region)

    updated = mask_frame.copy()
    before = updated.copy()
    updated[region > 0] = target_label

    changed = not np.array_equal(before, updated)
    return updated, changed