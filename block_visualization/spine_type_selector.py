from PyQt5.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup
from PyQt5.QtCore import pyqtSignal

class SpineTypeSelector(QWidget):
    spine_type_changed = pyqtSignal(str)
    spine_direction_changed = pyqtSignal(str)

    def __init__(self, parent=None, show_only=False):
        super().__init__(parent)
        self.show_only = show_only
        self.spine_type = "C"  # 默认C型
        self.spine_direction = "left"  # 默认左凸
        self._init_ui()
        self._connect_signals()

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
        if self.show_only:
            self.c_type_radio.setEnabled(False)
            self.s_type_radio.setEnabled(False)
            self.c_left_radio.setEnabled(False)
            self.c_right_radio.setEnabled(False)
            self.s_lumbar_left_radio.setEnabled(False)
            self.s_lumbar_right_radio.setEnabled(False)

    def _connect_signals(self):
        if not self.show_only:
            self.spine_type_button_group.buttonClicked.connect(self._on_spine_type_changed)
            self.spine_direction_button_group.buttonClicked.connect(self._on_spine_direction_changed)

    def _on_spine_type_changed(self, button):
        if button == self.c_type_radio:
            self.spine_type = "C"
            self.c_direction_widget.setVisible(True)
            self.s_direction_widget.setVisible(False)
            # 重置为C型的默认方向
            self.c_left_radio.setChecked(True)
            self.spine_direction = "left"
        elif button == self.s_type_radio:
            self.spine_type = "S"
            self.c_direction_widget.setVisible(False)
            self.s_direction_widget.setVisible(True)
            # 重置为S型的默认方向
            self.s_lumbar_left_radio.setChecked(True)
            self.spine_direction = "lumbar_left"
        
        self.spine_type_changed.emit(self.spine_type)
        self.spine_direction_changed.emit(self.spine_direction)

    def _on_spine_direction_changed(self, button):
        if button == self.c_left_radio:
            self.spine_direction = "left"
        elif button == self.c_right_radio:
            self.spine_direction = "right"
        elif button == self.s_lumbar_left_radio:
            self.spine_direction = "lumbar_left"
        elif button == self.s_lumbar_right_radio:
            self.spine_direction = "lumbar_right"
        
        self.spine_direction_changed.emit(self.spine_direction)

    def set_spine_config(self, spine_type, spine_direction):
        """设置脊柱配置"""
        self.spine_type = spine_type
        self.spine_direction = spine_direction
        
        # 更新UI状态
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
            if spine_direction == "lumbar_left":
                self.s_lumbar_left_radio.setChecked(True)
            else:
                self.s_lumbar_right_radio.setChecked(True)

    def get_spine_config(self):
        return {"type": self.spine_type, "direction": self.spine_direction}