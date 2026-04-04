import numpy as np
from collections import deque

def copy_mask_region(mask_frame, x, y, copied_frame):
    mask_val = mask_frame[y, x]
    mask_bool = mask_frame == mask_val
    copied_frame[:] = 0
    copied_frame[mask_bool] = mask_val
    return int(mask_val), copied_frame

def paste_mask_region(mask_frame, copied_frame):
    mask_bool = copied_frame != 0
    mask_frame[mask_bool] = copied_frame[mask_bool]
    return mask_frame

def delete_mask_region(mask_frame, x, y):
    mask_val = mask_frame[y, x]
    mask_bool = mask_frame == mask_val
    mask_frame[mask_bool] = 0
    return int(mask_val), mask_frame

def apply_mask_brush(mask_data, current_frame, xl, xr, yl, yr, value, multi_edit=False, left_frame=None, right_frame=None):
    if multi_edit:
        mask_data[left_frame:right_frame + 1, yl:yr, xl:xr] = value
    else:
        mask_data[current_frame, yl:yr, xl:xr] = value
    return mask_data

def count_cells(mask_frame):
    return max(int(np.unique(mask_frame).shape[0] - 1), 0)

def flood_fill_mask_region(mask_frame, x, y, new_label):
    h, w = mask_frame.shape[:2]

    if not (0 <= x < w and 0 <= y < h):
        return None, mask_frame, False

    old_label = int(mask_frame[y, x])
    new_label = int(new_label)

    if old_label == new_label:
        return old_label, mask_frame, False

    updated = mask_frame.copy()
    visited = np.zeros((h, w), dtype=bool)
    q = deque([(x, y)])
    visited[y, x] = True

    while q:
        cx, cy = q.popleft()

        if updated[cy, cx] != old_label:
            continue

        updated[cy, cx] = new_label

        for nx, ny in (
            (cx - 1, cy),
            (cx + 1, cy),
            (cx, cy - 1),
            (cx, cy + 1),
        ):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                visited[ny, nx] = True
                if updated[ny, nx] == old_label:
                    q.append((nx, ny))

    return old_label, updated, True
