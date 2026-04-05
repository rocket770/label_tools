import numpy as np

def merge_labels_in_range(mask_data, keep_label, merge_label, left_frame, right_frame):
    updated = mask_data.copy()
    changed_frames = []

    for frame_idx in range(left_frame, right_frame + 1):
        frame = updated[frame_idx]
        if np.any(frame == merge_label):
            frame = frame.copy()
            frame[frame == merge_label] = keep_label
            updated[frame_idx] = frame
            changed_frames.append(frame_idx)

    return updated, changed_frames