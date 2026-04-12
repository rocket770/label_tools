from tools.polygon import apply_polygon_to_mask


class PolygonToolController:
    def __init__(self, window):
        self.window = window
        self.points = []

    def is_close_to_start(self, x, y):
        if not self.points:
            return False

        first_x, first_y = self.points[0]
        close_dist = int(self.window.polygon_close_dist_spinBox.value())

        dx = x - first_x
        dy = y - first_y
        return (dx * dx + dy * dy) <= (close_dist * close_dist)

    def handle_point(self, x, y):
        if self.window.mask_data is None:
            self.window.msg_label.setText("Polygon: no mask loaded")
            return

        if len(self.points) >= 3 and self.is_close_to_start(x, y):
            self.apply_polygon(self.points.copy())
            self.reset()
            return

        self.points.append((x, y))
        self.window.image_label.set_polygon_points(self.points)
        self.window.msg_label.setText(f"Polygon points: {len(self.points)}")

    def cancel(self):
        self.reset(message="Polygon canceled")

    def reset(self, message=None):
        self.points = []
        self.window.image_label.set_polygon_points([])
        if message is not None:
            self.window.msg_label.setText(message)

    def apply_polygon(self, points):
        if self.window.mask_data is None:
            self.window.msg_label.setText("Polygon: no mask loaded")
            return

        if len(points) < 3:
            self.window.msg_label.setText("Polygon: need at least 3 points")
            return

        if self.window.current_backup is None:
            self.window.current_backup = self.window.mask_data.copy()

        target_label = int(self.window.label_spinBox.value())
        fill_holes = self.window.polygon_fill_holes_checkBox.isChecked()
        apply_scope = self.apply_scope()

        updated_frame, changed, message = apply_polygon_to_mask(
            self.window.mask_data[self.window.current_frame],
            points,
            target_label,
            fill_holes=fill_holes,
            apply_scope=apply_scope,
        )

        if not changed:
            self.window.current_backup = None
            self.window.msg_label.setText(message)
            return

        self.window.mask_data[self.window.current_frame] = updated_frame
        self.window.update_image()
        self.window.commit_mask()
        self.window.msg_label.setText(message)

    def apply_scope(self):
        selected_index = self.window.polygon_apply_to_comboBox.currentIndex()
        if selected_index == 0:
            return "background"
        if selected_index == 1:
            return "mask"
        return "both"
