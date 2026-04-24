import os
import sys
from collections import deque
from datetime import datetime

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QShortcut,
)

from color_mapper import ColorMapper
from tools.label_tools import format_label_text, get_label_display_rgb
from tools.brush_controller import BrushToolController
from tools.mask_ops import (
    copy_mask_region,
    count_cells,
    delete_mask_region,
    paste_mask_region,
    flood_fill_mask_region,
)
from tools.merge import merge_labels_in_range
from tools.repair_normalize import repair_and_normalize_mask_stack
from tools.split import find_available_label, split_label_with_line
from tools.polygon_controller import PolygonToolController
from tools.tool_registry import (
    ToolRegistry,
    build_default_tool_registrations,
)
from ui_window import Ui_MainWindow


def rescale_stack_to_uint16(stack):
    stack = np.asarray(stack)
    rescaled = np.zeros_like(stack, dtype=np.uint16)

    for index, frame in enumerate(stack):
        frame_float = frame.astype(np.float32, copy=False)
        min_val = float(frame_float.min())
        max_val = float(frame_float.max())

        if max_val <= min_val:
            continue

        scaled = (frame_float - min_val) * (65535.0 / (max_val - min_val))
        rescaled[index] = np.clip(scaled, 0, 65535).astype(np.uint16)

    return rescaled


def apply_viridis_colormap(image_data):
    return cv2.applyColorMap(image_data, cv2.COLORMAP_VIRIDIS)

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.color_mapper = ColorMapper()
        self.brush_tool = BrushToolController(self)
        self.polygon_tool = PolygonToolController(self)

        self._init_state()
        self._connect_general_signals()
        self._setup_tool_registry()
        self._setup_shortcuts()
        self._init_ui_state()

        self.setAcceptDrops(True)

    def _init_state(self):
        self.total_frames = 0
        self.current_frame = 0
        self.tif_array = None
        self.big_fish_array = None
        self.mask_data = None
        self.copyed_frame = None
        self.current_backup = None
        self.mask_stack = deque(maxlen=10)
        self.pending_merge_label = None
        self.selected_colormap = self.colormap_combo.currentIndex()

    def _connect_general_signals(self):
        self.actionload.triggered.connect(self.open_files)
        self.actionsave.triggered.connect(self.save)
        self.actionRepairNormalize.triggered.connect(self.repair_and_normalize_masks)
        self.frame_slider.valueChanged.connect(self.change_frame)
        self.colormap_combo.currentIndexChanged.connect(self.update_colormap)

        self.normalize_checkBox.stateChanged.connect(self.update_image)
        self.big_fish_checkBox.stateChanged.connect(self.update_image)
        self.mask_checkbox.stateChanged.connect(self.update_image)
        self.tif_checkbox.stateChanged.connect(self.update_image)
        self.show_cell_ids_checkBox.stateChanged.connect(self.update_image)

        self.image_label.mouseMoved.connect(self.mouse_moved)
        self.image_label.copyAct.connect(self.copy_mask)
        self.image_label.pasteAct.connect(self.paste_mask)
        self.image_label.deleteAct.connect(self.delete_mask)
        self.image_label.commitAct.connect(self.commit_mask)

        self.pushButton_left.clicked.connect(self.go_left)
        self.pushButton_right.clicked.connect(self.go_right)

        self.tool_size_spinBox.valueChanged.connect(self.on_tool_size_changed)
        self.image_label.toolSizeChanged.connect(self.tool_size_spinBox.setValue)
        self.polygon_preview_checkBox.toggled.connect(
            self.image_label.set_polygon_preview_enabled
        )

        self.label_spinBox.valueChanged.connect(self.update_selected_label_preview)

    def _setup_tool_registry(self):
        self.tool_registry = ToolRegistry(
            self,
            self.image_label,
            self.tool_options_stackedWidget,
            self.tool_options_none_page,
        )

        for registration in build_default_tool_registrations(self):
            self.tool_registry.register(registration)

    def _setup_shortcuts(self):
        self.shortcut_cancel = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_cancel.setContext(Qt.WindowShortcut)
        self.shortcut_cancel.activated.connect(self.cancel_action)

        self.shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_left.setContext(Qt.WindowShortcut)
        self.shortcut_left.activated.connect(self.go_left)

        self.shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_right.setContext(Qt.WindowShortcut)
        self.shortcut_right.activated.connect(self.go_right)

        self.shortcut_multi_edit = QShortcut(QKeySequence("Ctrl+M"), self)
        self.shortcut_multi_edit.setContext(Qt.WindowShortcut)
        self.shortcut_multi_edit.activated.connect(
            lambda: self.multieditor_checkBox.setChecked(
                not self.multieditor_checkBox.isChecked()
            )
        )

        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.setContext(Qt.WindowShortcut)
        self.shortcut_save.activated.connect(self.save)

    def _init_ui_state(self):
        self.image_label.setFocusPolicy(Qt.ClickFocus)
        self.tool_help_status_label = QLabel(self)
        self.tool_help_status_label.setText("Select a tool to see a short usage hint.")
        self.statusbar.addPermanentWidget(self.tool_help_status_label, 1)
        self.image_label.set_polygon_preview_enabled(
            self.polygon_preview_checkBox.isChecked()
        )
        self.on_tool_size_changed(self.tool_size_spinBox.value())
        self.update_selected_label_preview()
        self.tool_registry.initialize()

    def set_tool_help(self, text):
        self.tool_help_status_label.setText(text or "Select a tool to see a short usage hint.")

    def update_tool_options_height(self):
        current_page = self.tool_options_stackedWidget.currentWidget()
        if current_page is None:
            return

        page_layout = current_page.layout()
        page_height = (
            page_layout.sizeHint().height()
            if page_layout is not None
            else current_page.sizeHint().height()
        )
        page_height = max(page_height, 0)

        self.tool_options_stackedWidget.setFixedHeight(page_height)
        self.tool_options_groupBox.adjustSize()
        self.centralwidget.layout().activate()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            for u in urls:
                print(u)
                fn = u.toLocalFile()
                if fn.endswith('.tif'):
                    self.open_tif_file(fn)
                elif fn.endswith('.npz'):
                    self.open_npz_file(fn)
            self.update_image()

    def go_left(self):
        self.frame_slider.setValue(max(self.current_frame - 1, 0))
        self.change_frame()

    def go_right(self):
        self.frame_slider.setValue(min(self.current_frame + 1, self.total_frames - 1))
        self.change_frame()

    def copy_mask(self, x, y):
        if self.mask_data is None:
            return
        mask_val, self.copyed_frame = copy_mask_region(
            self.mask_data[self.current_frame],
            x,
            y,
            self.copyed_frame,
        )
        print(mask_val)

    def paste_mask(self):
        if self.mask_data is None:
            return
        print('Paste')
        self.mask_data[self.current_frame] = paste_mask_region(
            self.mask_data[self.current_frame],
            self.copyed_frame,
        )
        self.update_image()

    def delete_mask(self, x, y):
        if self.mask_data is None:
            return
        print('Delete')
        _, self.mask_data[self.current_frame] = delete_mask_region(
            self.mask_data[self.current_frame],
            x,
            y,
        )
        self.update_image()

    def update_selected_label_preview(self):
        label_val = int(self.label_spinBox.value())
        r, g, b = get_label_display_rgb(self.color_mapper.color_table, label_val)

        self.label_color_preview.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
        )
        self.label_color_text.setText(format_label_text(label_val))

    def pick_label(self, x, y):
        if self.mask_data is None:
            return

        label_val = int(self.mask_data[self.current_frame, y, x])
        self.detail_label.setText(f'{x} {y} {label_val}')

        if label_val != 0:
            self.label_spinBox.setValue(label_val)
            self.update_selected_label_preview()
            self.msg_label.setText(f'Picked label: {label_val}')
        else:
            self.msg_label.setText('Picked background (0), current label unchanged')

    def save(self):
        if self.mask_data is not None:
            path = self.mask_fn_label.text()
            folder = os.path.dirname(path)
            now = datetime.now()
            formatted_time = now.strftime("%Y_%m_%d_%H_%M_%S")
            file_name = os.path.splitext(os.path.basename(path))[0] + f'_{formatted_time}.npz'
            fn = os.path.join(folder, file_name)
            np.savez_compressed(fn, self.mask_data)
            self.msg_label.setText(f'File saved: {file_name}')

    def repair_and_normalize_masks(self):
        if self.mask_data is None:
            self.msg_label.setText('Repair and normalize: no mask loaded')
            return

        self.current_backup = self.mask_data.copy()
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            repaired_mask, report = repair_and_normalize_mask_stack(self.mask_data)
        except ValueError as exc:
            self.current_backup = None
            self.msg_label.setText(str(exc))
            QMessageBox.warning(self, 'Repair and Normalize', str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        if np.array_equal(repaired_mask, self.mask_data):
            self.current_backup = None
            summary = 'Repair and normalize found no ID changes to apply'
            self.msg_label.setText(summary)
            QMessageBox.information(self, 'Repair and Normalize', summary)
            return

        self.mask_data = repaired_mask
        self.copyed_frame = np.zeros(
            (repaired_mask.shape[1], repaired_mask.shape[2]),
            dtype=repaired_mask.dtype,
        )
        self.update_image()
        self.commit_mask()

        summary = (
            'Repair and normalize updated '
            f'{report["changed_frames"]} frame(s), repaired '
            f'{report["duplicate_regions_repaired"]} duplicate region(s), '
            f'and used labels up to {report["max_label_used"]}'
        )
        details = (
            f'Frames processed: {report["frames_processed"]}\n'
            f'Frames changed: {report["changed_frames"]}\n'
            f'Duplicate label groups found: {report["duplicate_label_groups"]}\n'
            f'Duplicate disconnected regions repaired: {report["duplicate_regions_repaired"]}\n'
            f'Matched by overlap: {report["overlap_matches"]}\n'
            f'Matched by distance: {report["distance_matches"]}\n'
            f'Tracks created: {report["tracks_created"]}\n'
            f'Fallback labels used: {report["fallback_labels_used"]}\n'
            f'Max label used: {report["max_label_used"]}'
        )
        self.msg_label.setText(summary)
        QMessageBox.information(self, 'Repair and Normalize', details)

    def on_tool_size_changed(self, value):
        self.image_label.set_tool_size(value)

    def mouse_moved(self, x, y):
        if self.mask_data is None:
            self.detail_label.setText(f'{x} {y} -')
        else:
            self.detail_label.setText(f'{x} {y} {self.mask_data[self.current_frame, y, x]}')

    def commit_mask(self):
        print('commit')
        if self.current_backup is not None:
            self.mask_stack.append(self.current_backup)
            self.current_backup = None

    def cancel_action(self):
        print('undo')
        if len(self.mask_stack) != 0:
            self.mask_data = self.mask_stack.pop()
            self.update_image()

    def change_frame(self):
        self.current_frame = self.frame_slider.value()
        self.frame_label.setText(f'{self.current_frame} / {self.total_frames - 1}')
        if not self.multieditor_checkBox.isChecked():
            self.l_spinBox.setValue(self.current_frame)
            self.r_spinBox.setValue(self.current_frame)
        self.update_image()

    def update_colormap(self):
        self.selected_colormap = self.colormap_combo.currentIndex()
        self.update_image()

    def open_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'select files', filter='Images (*.tif *.npy *.npz)')

        for fn in file_paths:
            if fn.endswith('.tif'):
                self.open_tif_file(fn)
            elif fn.endswith('.npz'):
                self.open_npz_file(fn)

        self.update_image()

    def open_tif_file(self, fn):
        self.tif_fn_label.setText('Loaded')
        with Image.open(fn) as image:
            self.total_frames = image.n_frames
            self.tif_array = np.zeros((image.n_frames, image.height, image.width), dtype=np.uint16)
            for i in range(image.n_frames):
                image.seek(i)
                self.tif_array[i] = np.array(image)

        self.big_fish_array = rescale_stack_to_uint16(self.tif_array)
        print(f'Rescaled result: {self.big_fish_array.shape}')

        max_frame = self.total_frames - 1

        self.current_frame = 0
        
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(max_frame)
        self.frame_slider.setValue(0)

        self.frame_label.setText(f'{self.current_frame} / {max_frame}')

        self.radio_mouse.setChecked(True)

        self.l_spinBox.setMaximum(max_frame)
        self.r_spinBox.setMaximum(max_frame)

    def open_npz_file(self, fn):
        self.mask_fn_label.setText('Loaded')
        data = np.load(fn)['arr_0']
        self.mask_data = data
        self.copyed_frame = np.zeros((data.shape[1], data.shape[2]), dtype=data.dtype)
        self.radio_mouse.setChecked(True)

    def load_tif_frame(self):
        if self.tif_array is None:
            self.tif_checkbox.setChecked(False)
            self.tif_fn_label.setText('None')
            return None

        image_data = self.tif_array[self.current_frame]
        if self.normalize_checkBox.isChecked():
            min_val = image_data.min()
            max_val = image_data.max()
            norm_data = np.interp(image_data, (min_val, max_val), (0, 255)).astype(np.uint8)
            colored_data = cv2.applyColorMap(norm_data, self.selected_colormap)
        elif self.big_fish_checkBox.isChecked():
            min_val = 0
            max_val = 65535
            norm_data = np.interp(self.big_fish_array[self.current_frame], (min_val, max_val), (0, 255)).astype(np.uint8)
            colored_data = apply_viridis_colormap(norm_data)
        else:
            min_val = 0
            max_val = 65535
            norm_data = np.interp(image_data, (min_val, max_val), (0, 255)).astype(np.uint8)
            colored_data = cv2.applyColorMap(norm_data, self.selected_colormap)

        return colored_data

    def load_mask_frame(self):
        if self.mask_data is None:
            self.mask_checkbox.setChecked(False)
            self.mask_fn_label.setText('None')
            return None

        mask_data = self.mask_data[self.current_frame].astype(np.uint8)
        return self.color_mapper.apply_custom_color_map_with_alpha(mask_data, 128)

    def build_cell_id_overlays(self):
        if self.mask_data is None or not self.show_cell_ids_checkBox.isChecked():
            return []

        mask_frame = self.mask_data[self.current_frame].astype(np.uint8)
        overlays = []

        for label_val in np.unique(mask_frame):
            label_val = int(label_val)
            if label_val == 0:
                continue

            label_mask = (mask_frame == label_val).astype(np.uint8)
            component_count, component_map = cv2.connectedComponents(label_mask, connectivity=8)

            for component_id in range(1, component_count):
                component_mask = (component_map == component_id).astype(np.uint8)
                area = int(component_mask.sum())
                if area == 0:
                    continue

                distance = cv2.distanceTransform(component_mask, cv2.DIST_L2, 5)
                _, max_distance, _, max_location = cv2.minMaxLoc(distance)

                if max_distance <= 0:
                    ys, xs = np.where(component_mask > 0)
                    if len(xs) == 0:
                        continue
                    anchor_x = int(xs[len(xs) // 2])
                    anchor_y = int(ys[len(ys) // 2])
                else:
                    anchor_x = int(max_location[0])
                    anchor_y = int(max_location[1])

                overlays.append(
                    {
                        "x": anchor_x,
                        "y": anchor_y,
                        "text": str(label_val),
                        "area": area,
                    }
                )

        overlays.sort(key=lambda item: item["area"], reverse=True)
        return overlays

    def update_image(self):
        tif_frame = self.load_tif_frame()
        mask_frame = self.load_mask_frame()
        cnt = int(self.tif_checkbox.isChecked()) + int(self.mask_checkbox.isChecked())

        if cnt == 0:
            self.image_label.clear()
            self.image_label.set_cell_id_overlays([])
        else:
            if tif_frame is not None:
                width, height, _ = tif_frame.shape
            if mask_frame is not None:
                width, height, _ = mask_frame.shape
            if cnt == 2:
                mask_rgb = mask_frame[:, :, :3]
                mask_alpha = mask_frame[:, :, 3] / 255.0
                tif_rgb = tif_frame[:, :, :3]
                blended_rgb = tif_rgb * (1 - mask_alpha[..., None]) + mask_rgb * mask_alpha[..., None]
                blended_rgb = blended_rgb.astype(np.uint8)
                data = blended_rgb.data
            else:
                if self.tif_checkbox.isChecked():
                    data = tif_frame.data
                else:
                    data = mask_frame[:, :, :3].copy().data
            qimg = QImage(data, width, height, QImage.Format_RGB888)
            self.image_label.load_image(qimg)
            self.image_label.set_cell_id_overlays(self.build_cell_id_overlays())

        if self.mask_data is not None:
            val = count_cells(self.mask_data[self.current_frame])
            self.stat_label.setText(f'Current cells: {val}')

    def fill_mask(self, x, y):
        print("fill_mask called", x, y)
        if self.mask_data is None:
            return

        if self.current_backup is None:
            self.current_backup = self.mask_data.copy()

        target_label = int(self.label_spinBox.value())

        if self.multieditor_checkBox.isChecked():
            left_frame = self.l_spinBox.value()
            right_frame = self.r_spinBox.value()

            changed_any = False
            for frame_idx in range(left_frame, right_frame + 1):
                old_label, updated_frame, changed = flood_fill_mask_region(
                    self.mask_data[frame_idx],
                    x,
                    y,
                    target_label,
                )
                if changed:
                    self.mask_data[frame_idx] = updated_frame
                    changed_any = True

            if changed_any:
                self.msg_label.setText(f'Filled region(s) with label {target_label}')
                self.update_image()
                self.commit_mask()
            else:
                self.current_backup = None
                self.msg_label.setText('Fill skiped: source label already matches selected label')
        else:
            old_label, updated_frame, changed = flood_fill_mask_region(
                self.mask_data[self.current_frame],
                x,
                y,
                target_label,
            )

            if changed:
                self.mask_data[self.current_frame] = updated_frame
                self.update_image()
                self.commit_mask()
                self.msg_label.setText(f'Filled label {old_label} -> {target_label}')
            else:
                self.current_backup = None
                self.msg_label.setText('Fill skipped: source label already matches selected label')

    def merge_labels(self, x, y):
        if self.mask_data is None:
            return

        clicked_label = int(self.mask_data[self.current_frame, y, x])

        if clicked_label == 0:
            self.msg_label.setText('Merge: clicked background')
            return

        if self.pending_merge_label is None:
            self.pending_merge_label = clicked_label
            self.label_spinBox.setValue(clicked_label)
            self.update_selected_label_preview()
            self.msg_label.setText(
                f'Merge: selected label {clicked_label}. Click the second label to merge into it.'
            )
            return

        keep_label = self.pending_merge_label
        merge_label = clicked_label

        if merge_label == keep_label:
            self.msg_label.setText('Merge: second click is the same label, choose a different cell')
            return

        if self.multieditor_checkBox.isChecked():
            left_frame = self.l_spinBox.value()
            right_frame = self.r_spinBox.value()
        else:
            left_frame = self.current_frame
            right_frame = self.current_frame

        if self.current_backup is None:
            self.current_backup = self.mask_data.copy()

        updated_mask, changed_frames = merge_labels_in_range(
            self.mask_data,
            keep_label,
            merge_label,
            left_frame,
            right_frame,
        )

        if changed_frames:
            self.mask_data = updated_mask
            self.update_image()
            self.commit_mask()
            self.msg_label.setText(f'Merged label {merge_label} into {keep_label}')
        else:
            self.current_backup = None
            self.msg_label.setText('Merge: nothing chaged in selected frame range')

        self.pending_merge_label = None

    def split_label(self, x1, y1, x2, y2):
        if self.mask_data is None:
            return

        current_frame_mask = self.mask_data[self.current_frame]

        new_label = find_available_label(self.mask_data)

        if new_label is None:
            self.msg_label.setText('Split: no free label IDs left (1-255)')
            return

        if self.current_backup is None:
            self.current_backup = self.mask_data.copy()

        cut_thickness = self.image_label.get_tool_diameter_in_image()

        updated_frame, target_label, changed, message = split_label_with_line(
            current_frame_mask,
            x1,
            y1,
            x2,
            y2,
            new_label=new_label,
            cut_thickness=cut_thickness,
        )

        if not changed:
            self.current_backup = None
            self.msg_label.setText(message)
            return

        self.mask_data[self.current_frame] = updated_frame
        self.label_spinBox.setValue(new_label)
        self.update_selected_label_preview()
        self.update_image()
        self.commit_mask()

        self.msg_label.setText(f'Split label {target_label} into {target_label} and {new_label}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())
