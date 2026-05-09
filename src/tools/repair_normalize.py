import cv2
import numpy as np


def _extract_label_components(frame):
    components = []
    duplicate_groups = 0
    duplicate_regions = 0

    for source_label in np.unique(frame):
        source_label = int(source_label)
        if source_label == 0:
            continue

        label_mask = (frame == source_label).astype(np.uint8)
        component_count, component_map, stats, centroids = cv2.connectedComponentsWithStats(
            label_mask,
            connectivity=8,
        )

        if component_count > 2:
            duplicate_groups += 1
            duplicate_regions += component_count - 2

        label_components = []
        for component_id in range(1, component_count):
            ys, xs = np.where(component_map == component_id)
            if xs.size == 0:
                continue

            left = int(stats[component_id, cv2.CC_STAT_LEFT])
            top = int(stats[component_id, cv2.CC_STAT_TOP])
            width = int(stats[component_id, cv2.CC_STAT_WIDTH])
            height = int(stats[component_id, cv2.CC_STAT_HEIGHT])
            area = int(stats[component_id, cv2.CC_STAT_AREA])
            centroid_x = float(centroids[component_id][0])
            centroid_y = float(centroids[component_id][1])

            label_components.append(
                {
                    "source_label": source_label,
                    "ys": ys,
                    "xs": xs,
                    "area": area,
                    "centroid": (centroid_x, centroid_y),
                    "bbox": (left, top, width, height),
                }
            )

        label_components.sort(
            key=lambda item: (
                -item["area"],
                item["centroid"][1],
                item["centroid"][0],
            )
        )
        components.extend(label_components)

    return components, duplicate_groups, duplicate_regions


def _next_unused_label(used_labels, max_label):
    for label in range(1, max_label + 1):
        if label not in used_labels:
            return label
    return None


def _allocate_preferred_label(used_labels, max_label, preferred_labels):
    for preferred_label in preferred_labels:
        preferred_label = int(preferred_label)
        if 1 <= preferred_label <= max_label and preferred_label not in used_labels:
            used_labels.add(preferred_label)
            return preferred_label

    label = _next_unused_label(used_labels, max_label)
    if label is None:
        raise ValueError(
            f"Repair and normalize needs more than {max_label} labels. "
            f"Increase the label range or reduce tracked cells."
        )

    used_labels.add(label)
    return label


def _match_by_overlap(components, prev_frame, assignments):
    overlap_candidates = []

    for curr_index, component in enumerate(components):
        if curr_index in assignments:
            continue

        prev_labels, counts = np.unique(
            prev_frame[component["ys"], component["xs"]],
            return_counts=True,
        )

        for prev_label, count in zip(prev_labels, counts):
            prev_label = int(prev_label)
            if prev_label == 0:
                continue

            overlap_ratio = float(count) / float(max(component["area"], 1))
            overlap_candidates.append(
                (int(count), overlap_ratio, curr_index, prev_label)
            )

    overlap_candidates.sort(reverse=True)

    used_prev_labels = set(assignments.values())
    for _, _, curr_index, prev_label in overlap_candidates:
        if curr_index in assignments or prev_label in used_prev_labels:
            continue

        assignments[curr_index] = prev_label
        used_prev_labels.add(prev_label)


def _match_by_distance(components, prev_components, assignments):
    distance_candidates = []

    matched_prev = set(assignments.values())

    for curr_index, component in enumerate(components):
        if curr_index in assignments:
            continue

        cx, cy = component["centroid"]
        area = float(max(component["area"], 1))

        for prev_label, prev_component in prev_components.items():
            if prev_label in matched_prev:
                continue

            px, py = prev_component["centroid"]
            prev_area = float(max(prev_component["area"], 1))
            distance = float(np.hypot(cx - px, cy - py))
            size_scale = max(np.sqrt(area), np.sqrt(prev_area))
            distance_limit = max(12.0, size_scale * 2.5)

            if distance > distance_limit:
                continue

            area_similarity = min(area, prev_area) / max(area, prev_area)
            distance_candidates.append(
                (-area_similarity, distance, curr_index, prev_label)
            )

    distance_candidates.sort()

    for _, _, curr_index, prev_label in distance_candidates:
        if curr_index in assignments or prev_label in matched_prev:
            continue

        assignments[curr_index] = prev_label
        matched_prev.add(prev_label)


def repair_and_normalize_mask_stack(mask_data, max_label=255):
    mask_array = np.asarray(mask_data)
    if mask_array.ndim != 3:
        raise ValueError("Repair and normalize expects a 3D mask stack.")

    duplicate_groups = 0
    duplicate_regions = 0
    overlap_matches = 0
    distance_matches = 0
    tracks_created = 0

    prev_components = {}
    prev_frame = np.zeros(mask_array.shape[1:], dtype=np.int32)
    track_frames = []
    track_label_counts = {}
    track_lengths = {}
    next_track_id = 1

    for frame_index in range(mask_array.shape[0]):
        components, frame_duplicate_groups, frame_duplicate_regions = _extract_label_components(
            mask_array[frame_index]
        )
        duplicate_groups += frame_duplicate_groups
        duplicate_regions += frame_duplicate_regions

        frame_output = np.zeros(mask_array.shape[1:], dtype=np.int32)
        assignments = {}

        if frame_index > 0 and prev_components:
            _match_by_overlap(components, prev_frame, assignments)
            overlap_matches += len(assignments)

            overlap_assigned = len(assignments)
            _match_by_distance(components, prev_components, assignments)
            distance_matches += len(assignments) - overlap_assigned

        for curr_index, component in enumerate(components):
            track_id = assignments.get(curr_index)
            if track_id is None:
                track_id = next_track_id
                next_track_id += 1
                tracks_created += 1

            frame_output[component["ys"], component["xs"]] = int(track_id)

            label_counts = track_label_counts.setdefault(track_id, {})
            source_label = int(component["source_label"])
            label_counts[source_label] = label_counts.get(source_label, 0) + 1
            track_lengths[track_id] = track_lengths.get(track_id, 0) + 1

        track_frames.append(frame_output)

        prev_frame = frame_output
        prev_components = {}
        for component in components:
            track_id = int(frame_output[component["ys"][0], component["xs"][0]])
            prev_components[track_id] = {
                "centroid": component["centroid"],
                "area": component["area"],
                "bbox": component["bbox"],
            }

    used_labels = set()
    track_to_label = {}
    resolved_by_fallback = 0

    sorted_tracks = sorted(
        track_label_counts,
        key=lambda track_id: (
            -max(track_label_counts[track_id].values()),
            -track_lengths.get(track_id, 0),
            min(track_label_counts[track_id]),
            track_id,
        ),
    )

    for track_id in sorted_tracks:
        preferred_labels = [
            label
            for label, _ in sorted(
                track_label_counts[track_id].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        assigned_label = _allocate_preferred_label(
            used_labels,
            max_label,
            preferred_labels,
        )
        if assigned_label != int(preferred_labels[0]):
            resolved_by_fallback += 1
        track_to_label[track_id] = assigned_label

    label_lookup = np.zeros(next_track_id, dtype=np.int32)
    for track_id, label in track_to_label.items():
        label_lookup[int(track_id)] = int(label)

    normalized = np.zeros_like(mask_array)
    for frame_index, track_frame in enumerate(track_frames):
        normalized[frame_index] = label_lookup[track_frame].astype(
            mask_array.dtype,
            copy=False,
        )

    changed_frames = int(
        np.count_nonzero(
            np.any(normalized.astype(np.int32) != mask_array.astype(np.int32), axis=(1, 2))
        )
    )

    report = {
        "frames_processed": int(mask_array.shape[0]),
        "duplicate_label_groups": int(duplicate_groups),
        "duplicate_regions_repaired": int(duplicate_regions),
        "overlap_matches": int(overlap_matches),
        "distance_matches": int(distance_matches),
        "tracks_created": int(tracks_created),
        "fallback_labels_used": int(resolved_by_fallback),
        "changed_frames": changed_frames,
        "max_label_used": int(normalized.max()) if normalized.size else 0,
    }

    return normalized, report
