from PyQt5.QtWidgets import QLabel, QMenu, QAction
from PyQt5.QtGui import QImage, QPixmap, QCursor, QPainter, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QRect

from tools.tool_modes import ToolMode
from tools.mask_ops import flood_fill_mask_region

class MyImageLabel(QLabel):

    mouseMoved = pyqtSignal(int, int)
    eraserAct = pyqtSignal(int, int, int, int)
    penAct = pyqtSignal(int, int, int, int)
    deleteAct = pyqtSignal(int, int)
    copyAct = pyqtSignal(int, int)
    pasteAct = pyqtSignal()
    commitAct = pyqtSignal()
    pickAct = pyqtSignal(int, int)
    fillAct = pyqtSignal(int, int)
    mergeAct = pyqtSignal(int, int)
    splitAct = pyqtSignal(int, int, int, int)
    toolSizeChanged = pyqtSignal(int)

    polygonFinished = pyqtSignal(list)
    polygonPreviewChanged = pyqtSignal(list)
    polygonCanceled = pyqtSignal()
    polygonPointAdded = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.lx = 0
        self.ly = 0
        self.rx = 0
        self.ry = 0

        self.f_lx = 0
        self.f_ly = 0
        self.f_rx = 0
        self.f_ry = 0

        self.select_rect = QRect(0, 0, 0, 0)
        self.right_click_loc = (0, 0)
        self.mode = ToolMode.MOUSE
        self.tool_size = 5
        self.img = None
        self.left_button_pressed = False
        self.split_start = None

        self.polygon_points = []
        self.polygon_hover_point = None

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        copy_action = QAction('Copy', self)
        paste_action = QAction('Paste', self)
        delete_action = QAction('Delete', self)

        ox, oy = self.get_original_pos(*self.right_click_loc)
        copy_action.triggered.connect(lambda: self.copyAct.emit(ox, oy))
        paste_action.triggered.connect(lambda: self.pasteAct.emit())
        delete_action.triggered.connect(lambda: self.deleteAct.emit(ox, oy))
        menu.addAction(copy_action)
        menu.addAction(paste_action)
        menu.addAction(delete_action)
        menu.exec(ev.globalPos())
        return super().contextMenuEvent(ev)

    def set_mode(self, mode):
        self.mode = ToolMode(mode)
        if self.mode in (ToolMode.ERASER, ToolMode.PEN, ToolMode.SPLIT):
            scale = self.get_now_scale()
            self.tool_size = max(int(round(scale)), 1)

        if self.mode != ToolMode.POLYGON:
            self.polygon_points = []
            self.polygon_hover_point = None    
        self.update_tool()

    def update_tool(self):
        if self.mode in (ToolMode.ERASER, ToolMode.PEN, ToolMode.SPLIT):
            pixmap = QPixmap(self.tool_size * 2, self.tool_size * 2)
            pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(255, 0, 0, 150))
            painter.setPen(QColor(0, 0, 0))
            painter.drawRect(0, 0, self.tool_size * 2, self.tool_size * 2)
            painter.end()

            cursor = QCursor(pixmap, self.tool_size, self.tool_size)
            self.setCursor(cursor)
        elif self.mode == ToolMode.EYEDROPPER:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def get_tool_diameter_in_image(self):
        if self.img is None:
            return 1
        scale = self.get_now_scale()
        return max(int(round((self.tool_size * 2) / scale)), 1)

    def now_rect(self, x, y):
        ox, oy = self.get_original_pos(x, y)
        scale = self.get_now_scale()
        ts_scaled = int(round(self.tool_size / scale))
        loc = [ox - ts_scaled, ox + ts_scaled, oy - ts_scaled, oy + ts_scaled]
        if loc[0] == loc[1]:
            loc[1] += 1
        if loc[2] == loc[3]:
            loc[3] += 1
        return loc

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier and self.img is not None:
            pos = event.pos()
            data_x, data_y = self.get_original_pos(pos.x(), pos.y())
            if data_x < 10:
                data_x = 0
            if data_y < 10:
                data_y = 0

            lw = data_x - self.f_lx
            rw = self.f_rx - data_x

            uw = data_y - self.f_ly
            dw = self.f_ry - data_y

            p = event.angleDelta().y() // 6

            t_lx = self.f_lx + p * lw / (lw + rw)
            t_rx = self.f_rx - p * rw / (lw + rw)
            t_ly = self.f_ly + p * uw / (uw + dw)
            t_ry = self.f_ry - p * dw / (uw + dw)

            if t_lx < 0:
                t_rx -= t_lx
                t_lx = 0
            if t_ly < 0:
                t_ry -= t_ly
                t_ly = 0

            if t_rx >= self.img.width():
                diff = t_rx - self.img.width() + 1
                t_lx -= diff

            if t_ry >= self.img.height():
                diff = t_ry - self.img.height() + 1
                t_ly -= diff

            if t_rx - t_lx > 10 and t_ry - t_ly > 10:
                t_lx = max(t_lx, 0)
                t_ly = max(t_ly, 0)
                t_rx = min(t_rx, self.img.width() - 1)
                t_ry = min(t_ry, self.img.height() - 1)
                self.f_lx = t_lx
                self.f_ly = t_ly
                self.f_rx = t_rx
                self.f_ry = t_ry

                self.lx = int(round(self.f_lx))
                self.ly = int(round(self.f_ly))
                self.rx = int(round(self.f_rx))
                self.ry = int(round(self.f_ry))
            print(f'{p} {t_lx} {t_rx} {t_ly} {t_ry}')
            self.show_image()
        else:
            delta = event.angleDelta().y() // 120
            self.tool_size += delta
            if self.tool_size < 1:
                self.tool_size = 1
            self.update_tool()

            self.toolSizeChanged.emit(self.tool_size)
        return super().wheelEvent(event)

    def mouseMoveEvent(self, ev):
        x, y = ev.x(), ev.y()
        ox, oy = self.get_original_pos(x, y)
        self.mouseMoved.emit(ox, oy)

        if self.mode == ToolMode.ERASER and self.left_button_pressed:
            self.eraserAct.emit(*self.now_rect(x, y))
        if self.mode == ToolMode.PEN and self.left_button_pressed:
            self.penAct.emit(*self.now_rect(x, y))
        if self.mode == ToolMode.POLYGON:
            self.polygon_hover_point = (ox, oy)
            self.show_image()

        return super().mouseMoveEvent(ev)

    def mousePressEvent(self, event):
        print(f'Mouse pressed {self.mode}')
        if event.button() == Qt.LeftButton:
            self.left_button_pressed = True

            focused = self.window().focusWidget()
            if focused is not None and focused is not self:
                focused.clearFocus()

            self.setFocus(Qt.MouseFocusReason)

        if event.button() == Qt.RightButton:
            self.right_click_loc = event.x(), event.y()

            focused = self.window().focusWidget()
            if focused is not None and focused is not self:
                focused.clearFocus()

            self.setFocus(Qt.MouseFocusReason)

        if self.mode == ToolMode.MOUSE and event.button() == Qt.LeftButton:
            pos = event.pos()
            self.select_rect.setTopLeft(pos)

        if self.mode == ToolMode.ERASER and self.left_button_pressed:
            x, y = event.x(), event.y()
            self.eraserAct.emit(*self.now_rect(x, y))

        if self.mode == ToolMode.PEN and self.left_button_pressed:
            x, y = event.x(), event.y()
            self.penAct.emit(*self.now_rect(x, y))

        if self.mode == ToolMode.EYEDROPPER and event.button() == Qt.LeftButton:
            ox, oy = self.get_original_pos(event.x(), event.y())
            self.pickAct.emit(ox, oy)

        if self.mode == ToolMode.FILL and event.button() == Qt.LeftButton:
            ox, oy = self.get_original_pos(event.x(), event.y())
            self.fillAct.emit(ox, oy)

        if self.mode == ToolMode.MERGE and event.button() == Qt.LeftButton:
            ox, oy = self.get_original_pos(event.x(), event.y())
            self.mergeAct.emit(ox, oy)

        if self.mode == ToolMode.SPLIT and event.button() == Qt.LeftButton:
            self.split_start = self.get_original_pos(event.x(), event.y())

        if self.mode == ToolMode.POLYGON and event.button() == Qt.RightButton:
            self.polygonCanceled.emit()
            return
        
        if self.mode == ToolMode.POLYGON and event.button() == Qt.LeftButton:
            ox, oy = self.get_original_pos(event.x(), event.y())
            self.polygonPointAdded.emit(ox, oy)
            return

        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        print('Mouse released')
        if event.button() == Qt.LeftButton:
            self.left_button_pressed = False

        if self.mode == ToolMode.MOUSE and event.button() == Qt.LeftButton:
            pos = event.pos()
            self.select_rect.setBottomRight(pos)
            tl = self.select_rect.topLeft()
            br = self.select_rect.bottomRight()

            lx, ly = self.get_original_pos(tl.x(), tl.y())
            rx, ry = self.get_original_pos(br.x(), br.y())
            self.lx, self.ly, self.rx, self.ry = lx, ly, rx, ry

            if rx - lx < 10 or ry - ly < 10:
                self.lx = 0
                self.ly = 0
                self.rx = self.img.width() - 1 if self.img else 0
                self.ry = self.img.height() - 1 if self.img else 0

            self.f_lx = float(self.lx)
            self.f_ly = float(self.ly)
            self.f_rx = float(self.rx)
            self.f_ry = float(self.ry)
        elif self.mode in (ToolMode.ERASER, ToolMode.PEN) and event.button() == Qt.LeftButton:
            self.commitAct.emit()

        elif self.mode == ToolMode.SPLIT and event.button() == Qt.LeftButton:
            if self.split_start is not None:
                x1, y1 = self.split_start
                x2, y2 = self.get_original_pos(event.x(), event.y())
                self.splitAct.emit(x1, y1, x2, y2)
                self.split_start = None

        self.show_image()

    def get_original_pos(self, x, y):
        if self.img is None:
            return 0, 0
        scale = self.get_now_scale()
        ox = int(round(x / scale)) + self.lx
        oy = int(round(y / scale)) + self.ly
        if ox >= self.img.width() - 1:
            ox = self.img.width() - 1
        if oy >= self.img.height():
            oy = self.img.height() - 1
        return ox, oy

    def load_image(self, img: QImage):
        self.img = img
        w, h = self.img.width(), self.img.height()
        if self.rx == 0 and self.ry == 0:
            self.rx = w - 1
            self.ry = h - 1
            self.f_rx = float(self.rx)
            self.f_ry = float(self.ry)
        self.show_image()

    def set_tool_size(self, size):
        self.tool_size = max(int(size), 1)
        self.update_tool()

    def show_image(self):
        if self.img is None:
            return

        print(self.lx, self.ly, self.rx, self.ry)

        this_frame_img = QImage.copy(
            self.img,
            QRect(self.lx, self.ly, self.rx - self.lx + 1, self.ry - self.ly + 1),
        )

        width = this_frame_img.width()
        height = this_frame_img.height()

        scale = self.get_now_scale()

        scaled_img = this_frame_img.scaled(
            int(round(width * scale)),
            int(round(height * scale)),
        )

        pixmap = QPixmap.fromImage(scaled_img)

        if self.mode == ToolMode.POLYGON and self.polygon_points:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor(0, 255, 0))

            scaled_points = []
            for px, py in self.polygon_points:
                sx = int(round((px - self.lx) * scale))
                sy = int(round((py - self.ly) * scale))
                scaled_points.append((sx, sy))

            for i in range(len(scaled_points) - 1):
                x1, y1 = scaled_points[i]
                x2, y2 = scaled_points[i + 1]
                painter.drawLine(x1, y1, x2, y2)

            for x, y in scaled_points:
                painter.drawEllipse(x - 3, y - 3, 6, 6)

            if self.polygon_hover_point is not None and len(scaled_points) > 0:
                hx, hy = self.polygon_hover_point
                hsx = int(round((hx - self.lx) * scale))
                hsy = int(round((hy - self.ly) * scale))
                lx, ly = scaled_points[-1]
                painter.drawLine(lx, ly, hsx, hsy)

            painter.end()

        self.setPixmap(pixmap)

    def set_polygon_points(self, points):
        self.polygon_points = list(points)
        if not self.polygon_points:
            self.polygon_hover_point = None
        self.show_image()

    def get_now_scale(self):
        container_width = self.width()
        container_height = self.height()

        image_width = self.rx - self.lx + 1
        image_height = self.ry - self.ly + 1

        scale = min(container_width / image_width, container_height / image_height)
        return scale