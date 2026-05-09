import cv2
import numpy as np

def find_available_label(mask_source, min_label=1, max_label=255):
    used = set(np.unique(mask_source).astype(int).tolist())
    for label in range(min_label, max_label + 1):
        if label not in used:
            return label
    return None

def split_label_with_line(frame, x1, y1, x2, y2, new_label, cut_thickness=1):
    working = frame.copy()

    line_mask = np.zeros(working.shape, dtype=np.uint8)
    cv2.line(line_mask, (x1, y1), (x2, y2), 1, thickness=cut_thickness)

    crossed_labels = working[line_mask > 0]
    crossed_labels = crossed_labels[crossed_labels != 0]

    if crossed_labels.size == 0:
        return frame, None, False, 'Split: draw the line through a labeled cell'

    values, counts = np.unique(crossed_labels, return_counts=True)
    target_label = int(values[np.argmax(counts)])

    object_mask = (working == target_label).astype(np.uint8)
    object_mask[line_mask > 0] = 0

    num_components, comp_map = cv2.connectedComponents(object_mask, connectivity=8)

    if num_components < 3:
        return frame, target_label, False, 'Split: cut did not separate the cell into 2 parts'

    component_areas = []
    for comp_id in range(1, num_components):
        area = int(np.sum(comp_map == comp_id))
        if area > 0:
            component_areas.append((area, comp_id))

    component_areas.sort(reverse=True)

    keep_comp = component_areas[0][1]
    new_comp = component_areas[1][1]

    updated = working.copy()
    updated[updated == target_label] = 0
    updated[comp_map == keep_comp] = target_label
    updated[comp_map == new_comp] = new_label

    # Any extra fragments also go to the new label
    for _, comp_id in component_areas[2:]:
        updated[comp_map == comp_id] = new_label

    return updated, target_label, True, ''