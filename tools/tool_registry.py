from dataclasses import dataclass, field

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

from tools.tool_modes import ToolMode


@dataclass
class ToolRegistration:
    mode: ToolMode
    button: object
    option_page: object
    shortcut: object = None
    signal_bindings: list = field(default_factory=list)
    on_activate: object = None
    on_deactivate: object = None


class ToolRegistry:
    def __init__(self, window, image_label, stacked_widget, default_page):
        self.window = window
        self.image_label = image_label
        self.stacked_widget = stacked_widget
        self.default_page = default_page
        self.registrations = {}
        self.button_modes = {}
        self.shortcuts = []
        self.active_mode = None

    def register(self, registration):
        self.registrations[registration.mode] = registration
        self.button_modes[registration.button] = registration.mode
        registration.button.toggled.connect(self._handle_button_toggled)

        for signal_name, handler in registration.signal_bindings:
            getattr(self.image_label, signal_name).connect(handler)

        if registration.shortcut is not None:
            self.shortcuts.append(
                self._create_shortcut(registration.shortcut, registration.button)
            )

    def initialize(self):
        for button, mode in self.button_modes.items():
            if button.isChecked():
                self.activate_mode(mode)
                return

        self.show_option_page(None)

    def current_mode(self):
        return self.active_mode

    def activate_mode(self, mode):
        if mode == self.active_mode:
            self.show_option_page(mode)
            return

        previous = self.registrations.get(self.active_mode)
        if previous is not None and previous.on_deactivate is not None:
            previous.on_deactivate(self.window)

        registration = self.registrations[mode]
        if registration.on_activate is not None:
            registration.on_activate(self.window)

        self.image_label.set_mode(mode)
        self.show_option_page(mode)
        self.active_mode = mode

    def show_option_page(self, mode):
        registration = self.registrations.get(mode)
        page = self.default_page if registration is None else registration.option_page
        self.stacked_widget.setCurrentWidget(page)

    def _handle_button_toggled(self, checked):
        if not checked:
            return

        button = self.window.sender()
        mode = self.button_modes.get(button)
        if mode is not None:
            self.activate_mode(mode)

    def _create_shortcut(self, shortcut_value, button):
        shortcut = QShortcut(QKeySequence(shortcut_value), self.window)
        shortcut.setContext(Qt.WindowShortcut)
        shortcut.activated.connect(lambda checked_button=button: checked_button.setChecked(True))
        return shortcut


def activate_split_tool(window):
    if window.multieditor_checkBox.isChecked():
        window.multieditor_checkBox.blockSignals(True)
        window.multieditor_checkBox.setChecked(False)
        window.multieditor_checkBox.blockSignals(False)

    window.multieditor_checkBox.setEnabled(False)
    window.l_spinBox.setValue(window.current_frame)
    window.r_spinBox.setValue(window.current_frame)


def deactivate_split_tool(window):
    window.multieditor_checkBox.setEnabled(True)


def deactivate_merge_tool(window):
    window.pending_merge_label = None


def deactivate_polygon_tool(window):
    window.polygon_tool.reset()


def build_default_tool_registrations(window):
    return [
        ToolRegistration(
            mode=ToolMode.MOUSE,
            button=window.radio_mouse,
            option_page=window.tool_options_none_page,
        ),
        ToolRegistration(
            mode=ToolMode.ERASER,
            button=window.radio_eraser,
            option_page=window.tool_options_brush_page,
            shortcut="Ctrl+E",
            signal_bindings=[("eraserAct", window.brush_tool.erase)],
        ),
        ToolRegistration(
            mode=ToolMode.PEN,
            button=window.radio_pen,
            option_page=window.tool_options_brush_page,
            shortcut="Ctrl+P",
            signal_bindings=[("penAct", window.brush_tool.draw)],
        ),
        ToolRegistration(
            mode=ToolMode.FILL,
            button=window.radio_fill,
            option_page=window.tool_options_none_page,
            shortcut="Ctrl+F",
            signal_bindings=[("fillAct", window.fill_mask)],
        ),
        ToolRegistration(
            mode=ToolMode.EYEDROPPER,
            button=window.radio_picker,
            option_page=window.tool_options_none_page,
            signal_bindings=[("pickAct", window.pick_label)],
        ),
        ToolRegistration(
            mode=ToolMode.MERGE,
            button=window.radio_merge,
            option_page=window.tool_options_none_page,
            signal_bindings=[("mergeAct", window.merge_labels)],
            on_deactivate=deactivate_merge_tool,
        ),
        ToolRegistration(
            mode=ToolMode.SPLIT,
            button=window.radio_split,
            option_page=window.tool_options_brush_page,
            signal_bindings=[("splitAct", window.split_label)],
            on_activate=activate_split_tool,
            on_deactivate=deactivate_split_tool,
        ),
        ToolRegistration(
            mode=ToolMode.POLYGON,
            button=window.radio_polygon,
            option_page=window.tool_options_polygon_page,
            signal_bindings=[
                ("polygonPointAdded", window.polygon_tool.handle_point),
                ("polygonCanceled", window.polygon_tool.cancel),
            ],
            on_deactivate=deactivate_polygon_tool,
        ),
    ]
