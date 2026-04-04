import numpy as np

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