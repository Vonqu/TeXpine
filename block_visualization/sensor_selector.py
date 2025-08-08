#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
传感器选择器模块（修正版）
========================

修正内容：
1. 保持原有的蓝底高亮样式
2. 确保所有控制器都有手动控制功能
3. 保持原有所有功能不变
4. 添加误差范围设置
"""

from PyQt5.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QCheckBox, QDoubleSpinBox, QSpinBox, QSlider, QFormLayout)
from PyQt5.QtCore import Qt, pyqtSignal

class SensorSelector(QGroupBox):
    """
    传感器选择器（修正版）
    ====================
    
    保持原有样式和功能，新增误差范围设置
    """
    
    # 信号定义
    value_changed = pyqtSignal(float)
    threshold_alert = pyqtSignal(bool, str)
    error_range_changed = pyqtSignal(float)  # 新增：误差范围变更信号
    
    def __init__(self, title, sensor_count=6, parent=None, special_mode=False):
        super().__init__(title, parent)
        self.sensor_count = sensor_count
        self.current_value = 0
        self.sensor_values = [0] * sensor_count
        self.sensor_weights = [0] * sensor_count
        self.special_mode = special_mode
        self.threshold_min = -90
        self.threshold_max = 90
        self.alert_active = False
        
        # 新增：误差范围
        self.error_range = 0.1  # 默认误差范围10%
        
        self.setup_ui()
        self.set_highlighted(False)
    
    def setup_ui(self):
        """设置UI - 保持原有布局和样式"""
        layout = QVBoxLayout()
        
        # 新增：误差范围设置（放在最前面）
        error_range_group = QGroupBox("误差范围设置")
        error_range_layout = QHBoxLayout()
        error_range_label = QLabel("误差范围:")
        self.error_range_spin = QDoubleSpinBox()
        self.error_range_spin.setRange(0.0, 1.0)
        self.error_range_spin.setSingleStep(0.01)
        self.error_range_spin.setValue(0.1)
        self.error_range_spin.setDecimals(2)
        self.error_range_spin.valueChanged.connect(self.on_error_range_changed)
        error_range_layout.addWidget(error_range_label)
        error_range_layout.addWidget(self.error_range_spin)
        error_range_layout.addStretch()
        error_range_group.setLayout(error_range_layout)
        layout.addWidget(error_range_group)
        
        # 传感器选择和权重组（保持原有样式）
        sensor_group = QGroupBox("传感器选择和权重")
        sensor_layout = QVBoxLayout()
        
        self.sensor_checkboxes = []
        self.weight_spinboxes = []
        self.original_value_spins = []
        self.rotate_best_value_spins = []
        self.value_labels = []
        self.norm_labels = []
        
        for i in range(self.sensor_count):
            sensor_row = QHBoxLayout()
            checkbox = QCheckBox(f"传感器 {i+1}")
            self.sensor_checkboxes.append(checkbox)
            sensor_row.addWidget(checkbox)
            
            weight_label = QLabel("权重:")
            sensor_row.addWidget(weight_label)
            weight_spin = QDoubleSpinBox()
            weight_spin.setRange(-10.0, 10.0)
            weight_spin.setSingleStep(0.1)
            weight_spin.setValue(0.0)
            weight_spin.setEnabled(False)
            self.weight_spinboxes.append(weight_spin)
            sensor_row.addWidget(weight_spin)
            sensor_layout.addLayout(sensor_row)
            
            # 为每个传感器添加原始值和最佳值的spinbox
            spin_row = QHBoxLayout()
            ov_label = QLabel("原始值:")
            ov_spin = QSpinBox()
            ov_spin.setRange(0, 4095)
            ov_spin.setValue(2600)
            ov_spin.setVisible(False)
            ov_label.setVisible(False)
            self.original_value_spins.append(ov_spin)
            spin_row.addWidget(ov_label)
            spin_row.addWidget(ov_spin)
            
            rbv_label = QLabel("最佳值:")
            rbv_spin = QSpinBox()
            rbv_spin.setRange(0, 4095)
            rbv_spin.setValue(2350)
            rbv_spin.setVisible(False)
            rbv_label.setVisible(False)
            self.rotate_best_value_spins.append(rbv_spin)
            spin_row.addWidget(rbv_label)
            spin_row.addWidget(rbv_spin)
            sensor_layout.addLayout(spin_row)
            
            # 保存label引用以便后续控制显示
            if not hasattr(self, 'ov_labels'):
                self.ov_labels = []
                self.rbv_labels = []
            self.ov_labels.append(ov_label)
            self.rbv_labels.append(rbv_label)
            
            # 新增：实时值和归一化结果
            value_label = QLabel("当前值: 0")
            norm_label = QLabel("归一化: 0.00")
            value_label.setVisible(False)
            norm_label.setVisible(False)
            self.value_labels.append(value_label)
            self.norm_labels.append(norm_label)
            sensor_layout.addWidget(value_label)
            sensor_layout.addWidget(norm_label)
            
            checkbox.stateChanged.connect(lambda state, idx=i: self.on_sensor_selected(state, idx))
            weight_spin.valueChanged.connect(self.update_combined_value)
        
        sensor_group.setLayout(sensor_layout)
        layout.addWidget(sensor_group)
        
        # 当前值显示
        value_layout = QHBoxLayout()
        value_layout.addWidget(QLabel("当前值:"))
        self.value_label = QLabel("0")
        value_layout.addWidget(self.value_label)
        layout.addLayout(value_layout)
        
        # 手动控制（测试）- 所有控制器都有
        slider_group = QGroupBox("手动控制 (测试)")
        slider_layout = QVBoxLayout()
        self.manual_slider = QSlider(Qt.Horizontal)
        self.manual_slider.setRange(-90, 90)
        self.manual_slider.setValue(0)
        slider_layout.addWidget(self.manual_slider)
        slider_group.setLayout(slider_layout)
        layout.addWidget(slider_group)
        
        # 新增：整体动作正确性Label（仅special_mode显示）
        if self.special_mode:
            self.correct_label = QLabel("当前动作：不正确")
            self.correct_label.setStyleSheet("font-size: 18px; color: red; font-weight: bold;")
            layout.addWidget(self.correct_label)
        
        self.setLayout(layout)
        self.manual_slider.valueChanged.connect(self.update_manual_value)
    
    def on_error_range_changed(self, value):
        """处理误差范围变更"""
        self.error_range = value
        self.error_range_changed.emit(value)
        print(f"{self.title()} 误差范围设置为: {value}")
        
    def get_error_range(self):
        """获取误差范围"""
        return self.error_range
    
    def set_error_range(self, value):
        """设置误差范围"""
        self.error_range_spin.setValue(value)
        self.error_range = value
    
    def on_sensor_selected(self, state, sensor_idx):
        """处理传感器选择"""
        self.weight_spinboxes[sensor_idx].setEnabled(state == Qt.Checked)
        show = (state == Qt.Checked)
        self.original_value_spins[sensor_idx].setVisible(show)
        self.rotate_best_value_spins[sensor_idx].setVisible(show)
        self.ov_labels[sensor_idx].setVisible(show)
        self.rbv_labels[sensor_idx].setVisible(show)
        self.value_labels[sensor_idx].setVisible(show)
        self.norm_labels[sensor_idx].setVisible(show)
        self.update_combined_value()
    
    def update_combined_value(self):
        """更新组合值"""
        total_weight = 0
        weighted_sum = 0
        all_zero = True
        
        for i in range(self.sensor_count):
            if self.sensor_checkboxes[i].isChecked():
                weight = self.weight_spinboxes[i].value()
                if weight != 0:
                    ov = self.original_value_spins[i].value()
                    rbv = self.rotate_best_value_spins[i].value()
                    sensor_val = self.sensor_values[i]
                    # 防止分母为0
                    if ov == rbv:
                        norm = 1.0
                    else:
                        norm = (sensor_val - rbv) / (ov - rbv)
                    norm = max(0.0, min(1.0, norm))
                    total_weight += abs(weight)
                    weighted_sum += norm * weight
                    # 实时显示
                    self.value_labels[i].setText(f"当前值: {sensor_val}")
                    self.norm_labels[i].setText(f"归一化: {norm:.2f}")
                    if abs(norm) > 1e-2:
                        all_zero = False
        
        if total_weight > 0:
            combined_value = weighted_sum / total_weight
            self.current_value = combined_value
            self.value_label.setText(f"{combined_value:.2f}")
            self.value_changed.emit(combined_value)
            self.manual_slider.setValue(int(combined_value * 90))
        
        # 判断所有归一化是否为0（仅special_mode显示）
        if hasattr(self, 'correct_label'):
            if all_zero and total_weight > 0:
                self.correct_label.setText("当前动作：正确")
                self.correct_label.setStyleSheet("font-size: 18px; color: green; font-weight: bold;")
            else:
                self.correct_label.setText("当前动作：不正确")
                self.correct_label.setStyleSheet("font-size: 18px; color: red; font-weight: bold;")
    
    def set_sensor_value(self, sensor_index, value):
        """设置传感器值"""
        if sensor_index < self.sensor_count:
            self.sensor_values[sensor_index] = value
            self.update_combined_value()
    
    def update_manual_value(self, value):
        """更新手动值"""
        self.current_value = value
        self.value_label.setText(str(value))
        self.value_changed.emit(value)
        return value
    
    def set_highlighted(self, highlighted):
        """设置高亮状态 - 保持原有的蓝底样式"""
        if highlighted:
            self.setStyleSheet("QGroupBox { background: #e6f2ff; }")
        else:
            self.setStyleSheet("")
    
    def set_or_rbv_defaults(self, defaults):
        """
        批量设置原始值（or）和最佳值（rbv）的默认值。
        defaults: 列表，每个元素为{'ov': xxx, 'rbv': xxx}
        只对special_mode生效。
        """
        if not self.special_mode:
            return
        for i, d in enumerate(defaults):
            if i < len(self.original_value_spins):
                if 'ov' in d:
                    self.original_value_spins[i].setValue(d['ov'])
                if 'rbv' in d:
                    self.rotate_best_value_spins[i].setValue(d['rbv'])
    
    def get_weights(self):
        """获取当前权重配置"""
        weights = []
        for i in range(self.sensor_count):
            if self.sensor_checkboxes[i].isChecked():
                weights.append(self.weight_spinboxes[i].value())
            else:
                weights.append(0.0)
        return weights
        
    def get_ov_rbv_values(self):
        """获取OV/RBV值"""
        ov_values = [spin.value() for spin in self.original_value_spins]
        rbv_values = [spin.value() for spin in self.rotate_best_value_spins]
        return ov_values, rbv_values