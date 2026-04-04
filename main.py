import os
import sys
from collections import deque
from datetime import datetime

import bigfish.stack as bf_stack
import cv2
import matplotlib
import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QRadioButton,
    QShortcut,
)

from color_mapper import ColorMapper
from tools.label_tools import format_label_text, get_label_display_rgb
from tools.mask_ops import (
    apply_mask_brush,
    copy_mask_region,
    count_cells,
    delete_mask_region,
    paste_mask_region,
)
from tools.tool_modes import ToolMode
from ui_window import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.color_mapper = ColorMapper()

        self.actionload.triggered.connect(self.open_files)
        self.actionsave.triggered.connect(self.save)
        self.frame_slider.valueChanged.connect(self.change_frame)

        self.selected_colormap = self.colormap_combo.currentIndex()
        self.colormap_combo.currentIndexChanged.connect(self.update_colormap)

        self.normalize_checkBox.stateChanged.connect(self.update_image)
        self.big_fish_checkBox.stateChanged.connect(self.update_image)
        self.mask_checkbox.stateChanged.connect(self.update_image)
        self.tif_checkbox.stateChanged.connect(self.update_image)

        self.image_label.mouseMoved.connect(self.mouse_moved)
        self.image_label.eraserAct.connect(self.erase_mask)
        self.image_label.penAct.connect(self.draw_mask)
        self.image_label.copyAct.connect(self.copy_mask)
        self.image_label.pasteAct.connect(self.paste_mask)
        self.image_label.deleteAct.connect(self.delete_mask)
        self.image_label.commitAct.connect(self.commit_mask)
        self.image_label.pickAct.connect(self.pick_label)

        self.radio_mouse.toggled.connect(self.change_mode)
        self.radio_pen.toggled.connect(self.change_mode)
        self.radio_eraser.toggled.connect(self.change_mode)

        self.pushButton_left.clicked.connect(self.go_left)
        self.pushButton_right.clicked.connect(self.go_right)

        self.total_frames = 0
        self.current_frame = 0
        self.tif_array = None
        self.big_fish_array = None
        self.mask_data = None

        self.copyed_frame = None

        self.current_backup = None
        self.mask_stack = deque(maxlen=10)

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

        self.shortcut_eraser = QShortcut(QKeySequence("Ctrl+E"), self)
        self.shortcut_eraser.setContext(Qt.WindowShortcut)
        self.shortcut_eraser.activated.connect(lambda: self.radio_eraser.setChecked(True))

        self.shortcut_pen = QShortcut(QKeySequence("Ctrl+P"), self)
        self.shortcut_pen.setContext(Qt.WindowShortcut)
        self.shortcut_pen.activated.connect(lambda: self.radio_pen.setChecked(True))

        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.setContext(Qt.WindowShortcut)
        self.shortcut_save.activated.connect(self.save)

        self.image_label.setFocusPolicy(Qt.ClickFocus)

        # preview lives next to the Label spinbox
        self.label_color_preview = QLabel(self.centralwidget)
        self.label_color_preview.setFixedSize(24, 24)
        self.label_color_preview.setStyleSheet("border: 1px solid black;")

        self.label_color_text = QLabel(self.centralwidget)
        self.label_color_text.setText("")

        self.horizontalLayout_3.addWidget(self.label_color_preview)
        self.horizontalLayout_3.addWidget(self.label_color_text)

        self.radio_picker = QRadioButton("Eyedropper", self.groupBox)
        self.verticalLayout.addWidget(self.radio_picker)
        self.radio_picker.toggled.connect(self.change_mode)

        self.label_spinBox.valueChanged.connect(self.update_selected_label_preview)
        self.update_selected_label_preview()

        self.setAcceptDrops(True)

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

    def change_mode(self):
        if self.tif_array is None and self.mask_data is None:
            return

        if self.radio_mouse.isChecked():
            self.image_label.set_mode(ToolMode.MOUSE)
        elif self.radio_eraser.isChecked():
            self.image_label.set_mode(ToolMode.ERASER)
        elif self.radio_pen.isChecked():
            self.image_label.set_mode(ToolMode.PEN)
        elif hasattr(self, 'radio_picker') and self.radio_picker.isChecked():
            self.image_label.set_mode(ToolMode.EYEDROPPER)

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

    def mouse_moved(self, x, y):
        if self.mask_data is None:
            self.detail_label.setText(f'{x} {y} -')
        else:
            self.detail_label.setText(f'{x} {y} {self.mask_data[self.current_frame, y, x]}')

    def erase_mask(self, xl, xr, yl, yr):
        print('erase')
        if self.mask_data is None:
            return
        if self.current_backup is None:
            self.current_backup = self.mask_data.copy()
        self.mask_data = apply_mask_brush(
            self.mask_data,
            self.current_frame,
            xl,
            xr,
            yl,
            yr,
            0,
            multi_edit=self.multieditor_checkBox.isChecked(),
            left_frame=self.l_spinBox.value(),
            right_frame=self.r_spinBox.value(),
        )
        self.update_image()

    def draw_mask(self, xl, xr, yl, yr):
        print('draw')
        if self.mask_data is None:
            return
        if self.current_backup is None:
            self.current_backup = self.mask_data.copy()
        self.mask_data = apply_mask_brush(
            self.mask_data,
            self.current_frame,
            xl,
            xr,
            yl,
            yr,
            self.label_spinBox.value(),
            multi_edit=self.multieditor_checkBox.isChecked(),
            left_frame=self.l_spinBox.value(),
            right_frame=self.r_spinBox.value(),
        )
        self.update_image()

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

        self.big_fish_array = bf_stack.rescale(self.tif_array, 0)
        print(f'Rescaled result: {self.big_fish_array.shape}')

        self.current_frame = 0
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(self.total_frames - 1)
        self.frame_slider.setValue(0)
        self.frame_label.setText(f'{self.current_frame} / {self.total_frames - 1}')
        self.radio_mouse.setChecked(True)

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
            mapped_data = matplotlib.colormaps['viridis'](norm_data)[:, :, :3]
            colored_data = (mapped_data * 255).astype(np.uint8)
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

    def update_image(self):
        tif_frame = self.load_tif_frame()
        mask_frame = self.load_mask_frame()
        cnt = int(self.tif_checkbox.isChecked()) + int(self.mask_checkbox.isChecked())

        if cnt == 0:
            self.image_label.clear()
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

        if self.mask_data is not None:
            val = count_cells(self.mask_data[self.current_frame])
            self.stat_label.setText(f'Current cells: {val}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())