from tools.mask_ops import apply_mask_brush


class BrushToolController:
    def __init__(self, window):
        self.window = window

    def erase(self, xl, xr, yl, yr):
        self._apply_brush(xl, xr, yl, yr, label_value=0)

    def draw(self, xl, xr, yl, yr):
        self._apply_brush(
            xl,
            xr,
            yl,
            yr,
            label_value=int(self.window.label_spinBox.value()),
        )

    def _apply_brush(self, xl, xr, yl, yr, label_value):
        if self.window.mask_data is None:
            return

        if self.window.current_backup is None:
            self.window.current_backup = self.window.mask_data.copy()

        self.window.mask_data = apply_mask_brush(
            self.window.mask_data,
            self.window.current_frame,
            xl,
            xr,
            yl,
            yr,
            label_value,
            multi_edit=self.window.multieditor_checkBox.isChecked(),
            left_frame=self.window.l_spinBox.value(),
            right_frame=self.window.r_spinBox.value(),
        )
        self.window.update_image()
