from PyQt5.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup
from PyQt5.QtCore import pyqtSignal

class SpineTypeSelector(QWidget):
    spine_type_changed = pyqtSignal(str)
    spine_direction_changed = pyqtSignal(str)

    def __init__(self, parent=None, show_only=False):
        super().__init__(parent)
        self.show_only = show_only
        self.spine_type = "C"
        self.spine_direction = "left"
        self._init_ui()

    def _init_ui(self):
        group = QGroupBox("脊柱侧弯类型和方向选择")
        layout = QVBoxLayout()
        group.setLayout(layout)

        # 脊柱类型
        type_layout = QHBoxLayout()
        type_label = QLabel("脊柱类型:")
        type_layout.addWidget(type_label)
        self.spine_type_button_group = QButtonGroup()
        self.c_type_radio = QRadioButton("C型脊柱侧弯")
        self.s_type_radio = QRadioButton("S型脊柱侧弯")
        self.c_type_radio.setChecked(True)
        self.spine_type_button_group.addButton(self.c_type_radio, 0)
        self.spine_type_button_group.addButton(self.s_type_radio, 1)
        type_layout.addWidget(self.c_type_radio)
        type_layout.addWidget(self.s_type_radio)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # 方向
        direction_layout = QHBoxLayout()
        direction_label = QLabel("侧弯方向:")
        direction_layout.addWidget(direction_label)
        self.spine_direction_button_group = QButtonGroup()
        self.c_left_radio = QRadioButton("左凸")
        self.c_right_radio = QRadioButton("右凸")
        self.s_lumbar_left_radio = QRadioButton("腰椎左凸胸椎右凸")
        self.s_lumbar_right_radio = QRadioButton("腰椎右凸胸椎左凸")
        self.c_left_radio.setChecked(True)
        self.spine_direction_button_group.addButton(self.c_left_radio, 0)
        self.spine_direction_button_group.addButton(self.c_right_radio, 1)
        self.spine_direction_button_group.addButton(self.s_lumbar_left_radio, 2)
        self.spine_direction_button_group.addButton(self.s_lumbar_right_radio, 3)
        self.c_direction_widget = QWidget()
        c_direction_layout = QHBoxLayout()
        c_direction_layout.addWidget(self.c_left_radio)
        c_direction_layout.addWidget(self.c_right_radio)
        c_direction_layout.addStretch()
        self.c_direction_widget.setLayout(c_direction_layout)
        self.s_direction_widget = QWidget()
        s_direction_layout = QHBoxLayout()
        s_direction_layout.addWidget(self.s_lumbar_left_radio)
        s_direction_layout.addWidget(self.s_lumbar_right_radio)
        s_direction_layout.addStretch()
        self.s_direction_widget.setLayout(s_direction_layout)
        direction_layout.addWidget(self.c_direction_widget)
        direction_layout.addWidget(self.s_direction_widget)
        direction_layout.addStretch()
        layout.addLayout(direction_layout)
        self.c_direction_widget.setVisible(True)
        self.s_direction_widget.setVisible(False)
        layout.addStretch()
        info_label = QLabel("选择脊柱类型和方向将自动调整训练阶段和可视化效果")
        info_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(info_label)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(group)
        self.setLayout(main_layout)
        # 只读模式
        for widget in [self.c_type_radio, self.s_type_radio, self.c_left_radio, self.c_right_radio, self.s_lumbar_left_radio, self.s_lumbar_right_radio]:
            widget.setEnabled(not self.show_only)
        if not self.show_only:
            self.spine_type_button_group.buttonClicked.connect(self._on_spine_type_changed)
            self.spine_direction_button_group.buttonClicked.connect(self._on_spine_direction_changed)

    def _on_spine_type_changed(self, button):
        if button == self.c_type_radio:
            new_type = "C"
            self.c_direction_widget.setVisible(True)
            self.s_direction_widget.setVisible(False)
            self.c_left_radio.setChecked(True)
            self.spine_direction = "left"
        else:
            new_type = "S"
            self.c_direction_widget.setVisible(False)
            self.s_direction_widget.setVisible(True)
            self.s_lumbar_left_radio.setChecked(True)
            self.spine_direction = "lumbar_left_thoracic_right"
        if new_type != self.spine_type:
            self.spine_type = new_type
            self.spine_type_changed.emit(new_type)
        self.spine_direction_changed.emit(self.spine_direction)

    def _on_spine_direction_changed(self, button):
        if button == self.c_left_radio:
            new_direction = "left"
        elif button == self.c_right_radio:
            new_direction = "right"
        elif button == self.s_lumbar_left_radio:
            new_direction = "lumbar_left_thoracic_right"
        elif button == self.s_lumbar_right_radio:
            new_direction = "lumbar_right_thoracic_left"
        else:
            return
        if new_direction != self.spine_direction:
            self.spine_direction = new_direction
            self.spine_direction_changed.emit(new_direction)

    def set_spine_config(self, spine_type, spine_direction):
        if spine_type == "C":
            self.c_type_radio.setChecked(True)
            self.c_direction_widget.setVisible(True)
            self.s_direction_widget.setVisible(False)
            if spine_direction == "left":
                self.c_left_radio.setChecked(True)
            else:
                self.c_right_radio.setChecked(True)
        else:
            self.s_type_radio.setChecked(True)
            self.c_direction_widget.setVisible(False)
            self.s_direction_widget.setVisible(True)
            if spine_direction == "lumbar_left_thoracic_right":
                self.s_lumbar_left_radio.setChecked(True)
            else:
                self.s_lumbar_right_radio.setChecked(True)
        self.spine_type = spine_type
        self.spine_direction = spine_direction

    def get_spine_config(self):
        return {"type": self.spine_type, "direction": self.spine_direction} 