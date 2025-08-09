#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
传感器选择器模块（前-k最大分配版）
================================

新增功能：
1. 添加"被选传感器数量"控制
2. 实现前-k最大分配算法
3. 自动权重计算和分配
4. 支持原始值和目标值的存储与应用
"""

import numpy as np
import time
from PyQt5.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
                            QCheckBox, QDoubleSpinBox, QSpinBox, QSlider, QFormLayout, 
                            QWidget, QScrollArea, QPushButton)
from PyQt5.QtCore import Qt, pyqtSignal

class SensorSelector(QGroupBox):
    """
    传感器选择器（前-k最大分配版）
    ============================
    
    新增功能：
    - 前-k最大分配算法
    - 自动权重计算
    - 原始值/目标值存储
    """
    
    # 信号定义
    value_changed = pyqtSignal(float)
    threshold_alert = pyqtSignal(bool, str)
    error_range_changed = pyqtSignal(float)
    weights_auto_assigned = pyqtSignal(list)  # 新增：权重自动分配完成信号
    
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
        
        # 误差范围
        self.error_range = 0.1
        
        # 前-k最大分配相关属性
        self.k_value = min(3, sensor_count)
        self.original_values = [2600.0] * sensor_count
        self.target_values = [2350.0] * sensor_count
        self.has_original_data = False
        self.has_target_data = False
        
        # 权重分配模式
        self.current_weight_mode = "auto"  # "auto" 或 "manual"
        
        # 传感器相关控件列表
        self.sensor_checkboxes = []
        self.weight_spinboxes = []
        self.original_value_spins = []
        self.rotate_best_value_spins = []
        self.value_labels = []
        self.norm_labels = []
        self.ov_labels = []
        self.rbv_labels = []
        self.sensor_rows = []
        
        # 传感器组容器
        self.sensor_group = None
        self.sensor_layout = None
        
        # 滚动区域相关属性
        self.scroll_area = None
        self.sensor_container = None
        
        # k值选择和按钮控件
        self.k_spinbox = None
        self.auto_assign_btn = None
        self.manual_save_btn = None
        self.weight_mode_group = None
        self.auto_mode_radio = None
        self.manual_mode_radio = None
        self.data_status_label = None
        self.mode_status_label = None
        
        self.setup_ui()
        self.set_highlighted(False)
    
    def setup_ui(self):
        """设置UI - 新增前-k最大分配控件"""
        layout = QVBoxLayout()
        
        # 新增：被选传感器数量控制
        k_control_group = self._create_k_control_group()
        layout.addWidget(k_control_group)
        
        # 误差范围设置
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
        
        # 传感器选择和权重组
        self.sensor_group = QGroupBox("传感器选择和权重")
        self.sensor_layout = QVBoxLayout()
        
        # 初始化传感器控件
        self._create_sensor_controls()
        
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 设置滚动区域样式
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: rgb(243, 243, 243);
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: rgb(243, 243, 243);
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建容器widget
        self.sensor_container = QWidget()
        self.sensor_container.setLayout(self.sensor_layout)
        self.sensor_container.setStyleSheet("background-color: rgb(243, 243, 243);")
        
        # 将容器添加到滚动区域
        self.scroll_area.setWidget(self.sensor_container)
        
        # 将滚动区域添加到传感器组
        sensor_group_layout = QVBoxLayout()
        sensor_group_layout.addWidget(self.scroll_area)
        self.sensor_group.setLayout(sensor_group_layout)
        
        layout.addWidget(self.sensor_group)
        
        # 当前值显示
        value_layout = QHBoxLayout()
        value_layout.addWidget(QLabel("当前值:"))
        self.value_label = QLabel("0")
        value_layout.addWidget(self.value_label)
        layout.addLayout(value_layout)
        
        # 手动控制（测试）
        slider_group = QGroupBox("手动控制 (测试)")
        slider_layout = QVBoxLayout()
        self.manual_slider = QSlider(Qt.Horizontal)
        self.manual_slider.setRange(-90, 90)
        self.manual_slider.setValue(0)
        slider_layout.addWidget(self.manual_slider)
        slider_group.setLayout(slider_layout)
        layout.addWidget(slider_group)
        
        # 整体动作正确性Label（仅special_mode显示）
        if self.special_mode:
            self.correct_label = QLabel("当前动作：不正确")
            self.correct_label.setStyleSheet("font-size: 18px; color: red; font-weight: bold;")
            layout.addWidget(self.correct_label)
        
        self.setLayout(layout)
        self.manual_slider.valueChanged.connect(self.update_manual_value)
    
    # def _create_k_control_group(self):
    #     """创建被选传感器数量控制组"""
    #     k_group = QGroupBox("被选传感器数量和权重分配模式")
    #     k_layout = QVBoxLayout()
        
    #     # 第一行：k值选择
    #     k_row = QHBoxLayout()
    #     k_label = QLabel("选择数量:")
    #     self.k_spinbox = QSpinBox()
    #     self.k_spinbox.setRange(1, self.sensor_count)
    #     self.k_spinbox.setValue(self.k_value)
    #     self.k_spinbox.valueChanged.connect(self.on_k_value_changed)
        
    #     k_row.addWidget(k_label)
    #     k_row.addWidget(self.k_spinbox)
    #     k_row.addStretch()
    #     k_layout.addLayout(k_row)
        
    #     # 第二行：权重分配模式选择
    #     mode_row = QHBoxLayout()
    #     mode_label = QLabel("权重分配模式:")
        
    #     # 权重分配模式选择
    #     from PyQt5.QtWidgets import QRadioButton, QButtonGroup
    #     self.weight_mode_group = QButtonGroup()
    #     self.auto_mode_radio = QRadioButton("自动分配")
    #     self.manual_mode_radio = QRadioButton("手动分配")
    #     self.auto_mode_radio.setChecked(True)  # 默认自动分配
        
    #     self.weight_mode_group.addButton(self.auto_mode_radio, 0)
    #     self.weight_mode_group.addButton(self.manual_mode_radio, 1)
        
    #     # 连接模式切换信号
    #     self.weight_mode_group.buttonClicked.connect(self.on_weight_mode_changed)
        
    #     mode_row.addWidget(mode_label)
    #     mode_row.addWidget(self.auto_mode_radio)
    #     mode_row.addWidget(self.manual_mode_radio)
    #     mode_row.addStretch()
    #     k_layout.addLayout(mode_row)
        
    #     # 第三行：按钮区域
    #     button_row = QHBoxLayout()
        
    #     # 自动分配按钮
    #     self.auto_assign_btn = QPushButton("应用前-k最大分配")
    #     self.auto_assign_btn.clicked.connect(self.apply_top_k_allocation)
    #     self.auto_assign_btn.setEnabled(False)
        
    #     # 手动保存按钮
    #     self.manual_save_btn = QPushButton("保存权重到文件")
    #     self.manual_save_btn.clicked.connect(self.save_manual_weights)
    #     self.manual_save_btn.setEnabled(False)
    #     self.manual_save_btn.setVisible(False)  # 初始隐藏
        
    #     button_row.addWidget(self.auto_assign_btn)
    #     button_row.addWidget(self.manual_save_btn)
    #     button_row.addStretch()
    #     k_layout.addLayout(button_row)
        
    #     # 第四行：数据状态显示（分两行显示）
    #     status_layout = QVBoxLayout()
    #     self.data_status_label = QLabel("数据状态: 等待数据")
    #     self.data_status_label.setStyleSheet("color: gray;")
    #     self.data_status_label.setWordWrap(True)  # 允许换行
        
    #     # 额外的状态信息
    #     self.mode_status_label = QLabel("当前模式: 自动分配")
    #     self.mode_status_label.setStyleSheet("color: blue; font-size: 10px;")
        
    #     status_layout.addWidget(self.data_status_label)
    #     status_layout.addWidget(self.mode_status_label)
    #     k_layout.addLayout(status_layout)
        
    #     k_group.setLayout(k_layout)
    #     return k_group
    
    def _create_k_control_group(self):
        """创建被选传感器数量控制组"""
        k_group = QGroupBox("被选传感器数量和权重分配模式")
        k_layout = QVBoxLayout()
        
        # 第一行：权重分配模式选择
        mode_row = QHBoxLayout()
        mode_label = QLabel("权重分配模式:")
        
        # 权重分配模式选择
        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        self.weight_mode_group = QButtonGroup()
        self.auto_mode_radio = QRadioButton("自动分配")
        self.manual_mode_radio = QRadioButton("手动分配")
        self.auto_mode_radio.setChecked(True)  # 默认自动分配
        
        self.weight_mode_group.addButton(self.auto_mode_radio, 0)
        self.weight_mode_group.addButton(self.manual_mode_radio, 1)
        
        # 连接模式切换信号
        self.weight_mode_group.buttonClicked.connect(self.on_weight_mode_changed)
        
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.auto_mode_radio)
        mode_row.addWidget(self.manual_mode_radio)
        mode_row.addStretch()
        k_layout.addLayout(mode_row)
        
        # 第二行：k值选择（仅自动分配模式显示）
        k_row = QHBoxLayout()
        k_label = QLabel("选择数量:")
        self.k_spinbox = QSpinBox()
        self.k_spinbox.setRange(1, self.sensor_count)
        self.k_spinbox.setValue(self.k_value)
        self.k_spinbox.valueChanged.connect(self.on_k_value_changed)
        
        k_row.addWidget(k_label)
        k_row.addWidget(self.k_spinbox)
        k_row.addStretch()
        
        # 创建k值选择容器，用于显示/隐藏
        self.k_selection_widget = QWidget()
        self.k_selection_widget.setLayout(k_row)
        k_layout.addWidget(self.k_selection_widget)
        
        # 第三行：按钮区域
        button_row = QHBoxLayout()
        
        # 保存权重到文件按钮（自动模式）
        self.save_weights_btn = QPushButton("保存权重到文件")
        self.save_weights_btn.clicked.connect(self.save_current_weights)
        self.save_weights_btn.setEnabled(False)
        
        # 复位按钮
        self.reset_auto_btn = QPushButton("复位为自动分配结果")
        self.reset_auto_btn.clicked.connect(self.reset_to_auto_result)
        self.reset_auto_btn.setEnabled(False)
        self.reset_auto_btn.setVisible(False)  # 初始隐藏
        
        # 手动保存按钮
        self.manual_save_btn = QPushButton("保存权重到文件")
        self.manual_save_btn.clicked.connect(self.save_manual_weights)
        self.manual_save_btn.setEnabled(False)
        self.manual_save_btn.setVisible(False)  # 初始隐藏
        
        button_row.addWidget(self.save_weights_btn)
        button_row.addWidget(self.reset_auto_btn)
        button_row.addWidget(self.manual_save_btn)
        button_row.addStretch()
        k_layout.addLayout(button_row)
        
        # 第四行：数据状态显示
        status_layout = QVBoxLayout()
        self.data_status_label = QLabel("数据状态: 等待数据")
        self.data_status_label.setStyleSheet("color: gray;")
        self.data_status_label.setWordWrap(True)
        
        self.mode_status_label = QLabel("当前模式: 自动分配")
        self.mode_status_label.setStyleSheet("color: blue; font-size: 10px;")
        
        status_layout.addWidget(self.data_status_label)
        status_layout.addWidget(self.mode_status_label)
        k_layout.addLayout(status_layout)
        
        k_group.setLayout(k_layout)
        return k_group

    def save_current_weights(self):
        """保存当前权重到文件（手动保存按钮）"""
        print(f"\n=== {self.title()}: 手动保存当前权重到文件 ===")
        
        # 获取当前权重（用户可能已手动修改过）
        final_weights = [0.0] * self.sensor_count
        selected_sensors = []
        
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                selected_sensors.append(i)
                if i < len(self.weight_spinboxes):
                    final_weights[i] = self.weight_spinboxes[i].value()
        
        print(f"保存的权重: {[f'{w:.3f}' for w in final_weights if w > 0]}")
        print(f"选中的传感器: {[i+1 for i in selected_sensors]}")
        
        # 验证权重
        total_weight = sum(final_weights)
        if abs(total_weight - 1.0) > 1e-6:
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "权重归一化", 
                f"权重总和为 {total_weight:.3f}，不等于1。\n是否自动归一化使权重和为1？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 归一化权重
                if total_weight > 0:
                    for i in range(self.sensor_count):
                        if final_weights[i] > 0:
                            final_weights[i] = final_weights[i] / total_weight
                            self.weight_spinboxes[i].setValue(final_weights[i])
                    print("✓ 权重已归一化")
            else:
                print("❌ 用户取消保存")
                return
        
        # 发送权重保存完成信号
        self.weights_auto_assigned.emit(final_weights)
        
        print(f"权重已手动保存到事件文件，权重和: {sum(final_weights):.6f}")
        print(f"=== 手动保存完成 ===\n")
        
        # 显示成功消息
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "成功", 
                            f"权重已保存到事件文件\n"
                            f"选中传感器: {len(selected_sensors)} 个\n"
                            f"权重总和: {sum(final_weights):.3f}")

    def reset_to_auto_result(self):
        """复位为自动分配结果"""
        if not hasattr(self, 'auto_allocation_result') or not self.auto_allocation_result:
            print(f"{self.title()}: 没有自动分配结果可以复位")
            return
        
        print(f"\n=== {self.title()}: 复位为自动分配结果 ===")
        
        result = self.auto_allocation_result
        
        # 清空所有传感器的选择和权重
        for i in range(self.sensor_count):
            self.sensor_checkboxes[i].setChecked(False)
            self.weight_spinboxes[i].setValue(0.0)
        
        # 恢复自动分配结果
        for i, (sensor_idx, weight) in enumerate(zip(result['indices'], result['weights'])):
            self.sensor_checkboxes[sensor_idx].setChecked(True)
            self.weight_spinboxes[sensor_idx].setValue(weight)
            print(f"恢复传感器{sensor_idx+1}: 权重={weight:.3f}")
        
        # 恢复k值
        if 'k_value' in result:
            self.k_spinbox.setValue(result['k_value'])
            self.k_value = result['k_value']
        
        # 更新组合值
        self.update_combined_value()
        
        # 更新状态
        self.mode_status_label.setText("当前模式: 自动分配")
        self.mode_status_label.setStyleSheet("color: blue; font-size: 10px;")
        
        # 在自动模式下复位后隐藏复位按钮
        if self.current_weight_mode == "auto":
            self.reset_auto_btn.setVisible(False)
        
        print(f"已复位为自动分配结果: k={result['k_value']}")
        print(f"=== 复位完成 ===\n")

    def auto_assign_and_save(self):
        """自动分配权重并保存到文件"""
        if not (self.has_original_data and self.has_target_data):
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "警告", "请先记录原始值和目标值")
            return
        
        print(f"\n=== {self.title()}: 自动分配权重并保存 ===")
        
        # 执行自动分配
        self.apply_auto_allocation()
        
        # 获取当前权重
        final_weights = [0.0] * self.sensor_count
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                if i < len(self.weight_spinboxes):
                    final_weights[i] = self.weight_spinboxes[i].value()
        
        # 发送权重保存完成信号
        self.weights_auto_assigned.emit(final_weights)
        
        # 重置按钮样式
        self.auto_assign_save_btn.setStyleSheet("")
        self.mode_status_label.setText("当前模式: 自动分配")
        self.mode_status_label.setStyleSheet("color: blue; font-size: 10px;")
        
        print(f"权重已保存到事件文件")
        print(f"=== 自动分配并保存完成 ===\n")
        
        # 显示成功消息
        from PyQt5.QtWidgets import QMessageBox
        selected_count = sum(1 for w in final_weights if w > 0)
        QMessageBox.information(self, "成功", 
                            f"自动分配完成并已保存到事件文件\n"
                            f"选中传感器: {selected_count} 个\n"
                            f"权重总和: {sum(final_weights):.3f}")
    
    def on_k_value_changed(self, value):
        """处理k值变更"""
        self.k_value = value
        print(f"{self.title()}: 被选传感器数量设置为 {value}")
        
        # 在自动分配模式下，k值变化时提示用户需要重新分配
        if self.current_weight_mode == "auto":
            self.mode_status_label.setText("当前模式: 自动分配 (k值已变更)")
            self.mode_status_label.setStyleSheet("color: orange; font-size: 10px;")
    
    def on_weight_mode_changed(self, button):
        """处理权重分配模式切换"""
        mode_id = self.weight_mode_group.id(button)
        
        if mode_id == 0:  # 自动分配模式
            self.current_weight_mode = "auto"
            
            # 显示/隐藏相关控件
            self.k_selection_widget.setVisible(True)
            self.save_weights_btn.setVisible(True)
            self.manual_save_btn.setVisible(False)
            
            # 如果之前有自动分配结果，显示复位按钮
            if hasattr(self, 'auto_allocation_result') and self.auto_allocation_result:
                self.reset_auto_btn.setVisible(True)
                self.reset_auto_btn.setEnabled(True)
            else:
                self.reset_auto_btn.setVisible(False)
            
            # 更新状态
            self.mode_status_label.setText("当前模式: 自动分配")
            self.mode_status_label.setStyleSheet("color: blue; font-size: 10px;")
            print(f"{self.title()}: 切换到自动分配模式")
            
            # 如果有完整数据，立即执行自动分配
            if self.has_original_data and self.has_target_data:
                self.apply_auto_allocation()
            
        elif mode_id == 1:  # 手动分配模式
            self.current_weight_mode = "manual"
            
            # 显示/隐藏相关控件
            self.k_selection_widget.setVisible(False)
            self.save_weights_btn.setVisible(False)
            
            # 在手动分配模式下，如果有自动分配结果，显示复位按钮
            if hasattr(self, 'auto_allocation_result') and self.auto_allocation_result:
                self.reset_auto_btn.setVisible(True)
                self.reset_auto_btn.setEnabled(True)
                self.reset_auto_btn.setText("复位为自动分配结果")
            else:
                self.reset_auto_btn.setVisible(False)
            
            self.manual_save_btn.setVisible(True)
            self.manual_save_btn.setEnabled(True)
            
            # 更新状态
            self.mode_status_label.setText("当前模式: 手动分配")
            self.mode_status_label.setStyleSheet("color: green; font-size: 10px;")
            print(f"{self.title()}: 切换到手动分配模式")
        
        # 更新界面状态
        self._update_ui_for_mode()

    
    
    def _update_ui_for_mode(self):
        """根据当前模式更新UI状态"""
        if self.current_weight_mode == "auto":
            # 自动模式：只有当数据完整时才启用按钮
            self.save_weights_btn.setEnabled(self.has_original_data and self.has_target_data)
        elif self.current_weight_mode == "manual":
            # 手动模式：总是启用保存按钮
            self.manual_save_btn.setEnabled(True)
    
    def save_manual_weights(self):
        """保存手动设置的权重（手动分配模式）"""
        print(f"\n=== {self.title()}: 保存手动权重 ===")
        
        # 获取手动设置的权重
        manual_weights = []
        selected_sensors = []
        total_weight = 0
        
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                selected_sensors.append(i)
                if i < len(self.weight_spinboxes):
                    weight = self.weight_spinboxes[i].value()
                    manual_weights.append(weight)
                    total_weight += weight
                else:
                    manual_weights.append(0.0)
            else:
                manual_weights.append(0.0)
        
        print(f"选中的传感器: {[i+1 for i in selected_sensors]}")
        print(f"手动设置的权重: {[f'{w:.3f}' for w in manual_weights if w > 0]}")
        print(f"权重总和: {total_weight:.3f}")
        
        # 验证是否有选中的传感器
        if len(selected_sensors) == 0:
            print("❌ 没有选中任何传感器")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "警告", "请至少选中一个传感器")
            return
        
        # 检查是否有手动设置的权重
        has_manual_weights = any(manual_weights[i] > 0 for i in selected_sensors)
        
        if has_manual_weights:
            # 情况1：用户手动指定了权重
            if abs(total_weight - 1.0) > 1e-6:
                # 权重和不为1，询问用户是否归一化
                from PyQt5.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, "权重归一化", 
                    f"权重总和为 {total_weight:.3f}，不等于1。\n是否自动归一化使权重和为1？",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # 归一化权重
                    for i in selected_sensors:
                        if manual_weights[i] > 0:
                            manual_weights[i] = manual_weights[i] / total_weight
                            self.weight_spinboxes[i].setValue(manual_weights[i])
                    
                    print("✓ 权重已归一化")
                    print(f"归一化后权重: {[f'{w:.3f}' for w in manual_weights if w > 0]}")
                else:
                    print("❌ 用户取消归一化")
                    return
            
            final_weights = manual_weights
            print("✓ 使用手动指定的权重")
            
        else:
            # 情况2：用户只选择了传感器，没有指定权重 - 自动分配
            if self.has_original_data and self.has_target_data:
                # 基于差异值自动分配权重
                print("用户未指定权重，基于差异值自动分配...")
                final_weights = self._auto_assign_weights_for_selected_sensors(selected_sensors)
                
                # 更新UI显示
                for i, weight in enumerate(final_weights):
                    if i < len(self.weight_spinboxes):
                        self.weight_spinboxes[i].setValue(weight)
                        
                print(f"自动分配的权重: {[f'{w:.3f}' for w in final_weights if w > 0]}")
            else:
                # 没有原始值和目标值，平均分配
                print("没有原始值和目标值，平均分配权重...")
                final_weights = [0.0] * self.sensor_count
                avg_weight = 1.0 / len(selected_sensors)
                
                for i in selected_sensors:
                    final_weights[i] = avg_weight
                    self.weight_spinboxes[i].setValue(avg_weight)
                
                print(f"平均分配的权重: {avg_weight:.3f}")
        
        # 验证最终权重
        final_sum = sum(final_weights)
        print(f"最终权重和: {final_sum:.6f}")
        
        # 更新组合值
        self.update_combined_value()
        
        # 发送权重保存完成信号
        self.weights_auto_assigned.emit(final_weights)
        
        print(f"=== 手动权重保存完成 ===\n")
        
        # 显示成功消息
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "成功", 
                            f"权重已保存到事件文件\n"
                            f"选中传感器: {len(selected_sensors)} 个\n"
                            f"权重总和: {final_sum:.3f}")



        
        # 根据当前模式自动保存权重
        if self.current_weight_mode == "auto":
            # 自动分配模式：自动选择传感器、分配权重并立即保存
            if self.has_original_data and self.has_target_data:
                print(f"{self.title()}: 自动分配模式 - 执行自动分配并保存")
                self.apply_auto_allocation_and_save()
        else:
            # 手动分配模式：保存用户手动设置的权重
            print(f"{self.title()}: 手动分配模式 - 保存用户手动设置的权重")
            self.save_manual_weights_auto()

    def save_manual_weights_auto(self):
        """自动保存手动设置的权重（点击完成阶段时调用）"""
        print(f"\n=== {self.title()}: 保存手动设置的权重 ===")
        
        # 获取手动设置的权重
        manual_weights = []
        selected_sensors = []
        total_weight = 0
        
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                selected_sensors.append(i)
                if i < len(self.weight_spinboxes):
                    weight = self.weight_spinboxes[i].value()
                    manual_weights.append(weight)
                    total_weight += weight
                else:
                    manual_weights.append(0.0)
            else:
                manual_weights.append(0.0)
        
        print(f"选中的传感器: {[i+1 for i in selected_sensors]}")
        print(f"手动设置的权重: {[f'{w:.3f}' for w in manual_weights if w > 0]}")
        print(f"权重总和: {total_weight:.3f}")
        
        # 验证是否有选中的传感器
        if len(selected_sensors) == 0:
            print("❌ 没有选中任何传感器，使用默认权重")
            # 如果没有选择传感器，给所有传感器平均权重
            avg_weight = 1.0 / self.sensor_count
            manual_weights = [avg_weight] * self.sensor_count
            for i in range(self.sensor_count):
                self.sensor_checkboxes[i].setChecked(True)
                self.weight_spinboxes[i].setValue(avg_weight)
            final_weights = manual_weights
        else:
            # 检查是否有手动设置的权重
            has_manual_weights = any(manual_weights[i] > 0 for i in selected_sensors)
            
            if has_manual_weights:
                # 情况1：用户手动指定了权重
                if abs(total_weight - 1.0) > 1e-6:
                    # 权重和不为1，自动归一化
                    print(f"权重和不为1，自动归一化...")
                    if total_weight > 0:
                        for i in selected_sensors:
                            if manual_weights[i] > 0:
                                manual_weights[i] = manual_weights[i] / total_weight
                                self.weight_spinboxes[i].setValue(manual_weights[i])
                        print("✓ 权重已自动归一化")
                        print(f"归一化后权重: {[f'{w:.3f}' for w in manual_weights if w > 0]}")
                
                final_weights = manual_weights
                print("✓ 使用手动指定的权重")
                
            else:
                # 情况2：用户只选择了传感器，没有指定权重 - 自动分配
                if self.has_original_data and self.has_target_data:
                    # 基于差异值自动分配权重
                    print("用户未指定权重，基于差异值自动分配...")
                    final_weights = self._auto_assign_weights_for_selected_sensors(selected_sensors)
                    
                    # 更新UI显示
                    for i, weight in enumerate(final_weights):
                        if i < len(self.weight_spinboxes):
                            self.weight_spinboxes[i].setValue(weight)
                            
                    print(f"自动分配的权重: {[f'{w:.3f}' for w in final_weights if w > 0]}")
                else:
                    # 没有原始值和目标值，平均分配
                    print("没有原始值和目标值，平均分配权重...")
                    final_weights = [0.0] * self.sensor_count
                    avg_weight = 1.0 / len(selected_sensors)
                    
                    for i in selected_sensors:
                        final_weights[i] = avg_weight
                        self.weight_spinboxes[i].setValue(avg_weight)
                    
                    print(f"平均分配的权重: {avg_weight:.3f}")
        
        # 验证最终权重
        final_sum = sum(final_weights)
        print(f"最终权重和: {final_sum:.6f}")
        
        # 更新组合值
        self.update_combined_value()
        
        # 发送权重保存完成信号
        self.weights_auto_assigned.emit(final_weights)
        
        print(f"=== 手动权重自动保存完成 ===\n")

    
    def apply_auto_allocation(self):
        """应用自动分配（仅分配，不保存）- 确保保存分配结果"""
        if not (self.has_original_data and self.has_target_data):
            return
        
        print(f"\n=== {self.title()}: 应用自动分配 ===")
        
        # 计算差异值并选择前k个传感器
        differences = []
        for i in range(self.sensor_count):
            original_val = self.original_values[i] if i < len(self.original_values) else 2600.0
            target_val = self.target_values[i] if i < len(self.target_values) else 2350.0
            diff = abs(target_val - original_val)
            differences.append((i, diff))
        
        # 按差异值降序排序，选择前k个
        differences.sort(key=lambda x: x[1], reverse=True)
        top_k_indices = [idx for idx, _ in differences[:self.k_value]]
        top_k_diffs = [diff for _, diff in differences[:self.k_value]]
        
        # 计算权重
        total_diff = sum(top_k_diffs)
        if total_diff > 0:
            weights = [diff / total_diff for diff in top_k_diffs]
            # 确保权重和严格等于1（处理浮点误差）
            weights_sum = sum(weights)
            if abs(weights_sum - 1.0) > 1e-6:
                weights = [w / weights_sum for w in weights]
        else:
            weights = [1.0 / self.k_value] * self.k_value
        
        # 清空所有传感器的选择和权重
        for i in range(self.sensor_count):
            self.sensor_checkboxes[i].setChecked(False)
            self.weight_spinboxes[i].setValue(0.0)
        
        # 应用前k个传感器的选择和权重
        for i, (sensor_idx, weight) in enumerate(zip(top_k_indices, weights)):
            self.sensor_checkboxes[sensor_idx].setChecked(True)
            self.weight_spinboxes[sensor_idx].setValue(weight)
        
        # 【关键】保存自动分配结果，用于复位功能
        self.auto_allocation_result = {
            'indices': top_k_indices,
            'weights': weights,
            'k_value': self.k_value,
            'timestamp': time.time()  # 添加时间戳
        }
        
        # 【关键】启用并显示复位按钮
        self.reset_auto_btn.setEnabled(True)
        self.reset_auto_btn.setVisible(True)
        self.reset_auto_btn.setText("复位为自动分配结果")
        
        # 更新组合值
        self.update_combined_value()
        
        print(f"自动分配完成: 选择传感器 {[i+1 for i in top_k_indices]}")
        print(f"复位按钮已启用")
        print(f"=== 自动分配完成 ===\n")

    def auto_save_weights(self):
        """自动保存权重（点击完成阶段时调用）"""
        print(f"\n=== {self.title()}: 自动保存权重 ===")
        
        # 获取当前权重
        final_weights = [0.0] * self.sensor_count
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                if i < len(self.weight_spinboxes):
                    final_weights[i] = self.weight_spinboxes[i].value()
        
        # 发送权重保存完成信号
        self.weights_auto_assigned.emit(final_weights)
        
        print(f"权重已自动保存到事件文件")
        print(f"=== 自动保存完成 ===\n")
    
    def _auto_assign_weights_for_selected_sensors(self, selected_sensors):
        """为选中的传感器自动分配权重"""
        weights = [0.0] * self.sensor_count
        
        if not self.has_original_data or not self.has_target_data:
            # 没有数据时平均分配
            avg_weight = 1.0 / len(selected_sensors)
            for sensor_idx in selected_sensors:
                weights[sensor_idx] = avg_weight
            return weights
        
        # 计算选中传感器的差异值
        selected_diffs = []
        for i in selected_sensors:
            original_val = self.original_values[i] if i < len(self.original_values) else 2600.0
            target_val = self.target_values[i] if i < len(self.target_values) else 2350.0
            diff = abs(target_val - original_val)
            selected_diffs.append(diff)
        
        # 基于差异值分配权重
        total_diff = sum(selected_diffs)
        if total_diff > 0:
            for i, sensor_idx in enumerate(selected_sensors):
                weights[sensor_idx] = selected_diffs[i] / total_diff
        else:
            # 差异值都为0，平均分配
            avg_weight = 1.0 / len(selected_sensors)
            for sensor_idx in selected_sensors:
                weights[sensor_idx] = avg_weight
        
        return weights
    


    def store_original_values(self, sensor_data):
        """存储原始值数据"""
        if len(sensor_data) > 1:  # 跳过时间戳
            self.original_values = sensor_data[1:self.sensor_count+1]
            # 补全数据
            while len(self.original_values) < self.sensor_count:
                self.original_values.append(2600.0)
        else:
            self.original_values = [2600.0] * self.sensor_count
        
        self.has_original_data = True
        self._update_data_status()
        self._update_original_value_spins()
        print(f"{self.title()}: 原始值已存储 {self.original_values[:3]}...")
        
        # 在存储原始值时，根据模式处理权重
        # if self.current_weight_mode == "manual":
        #     # 手动分配模式：记录当前的手动权重配置到事件文件
        #     print(f"{self.title()}: 手动分配模式 - 记录当前权重配置")
        #     self._record_current_manual_weights_to_event()

    def _record_current_manual_weights_to_event(self):
        """记录当前手动权重配置到事件文件（用于原始值记录时）"""
        print(f"\n=== {self.title()}: 记录当前手动权重配置 ===")
        
        # 获取当前权重配置
        current_weights = []
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                if i < len(self.weight_spinboxes):
                    current_weights.append(self.weight_spinboxes[i].value())
                else:
                    current_weights.append(0.0)
            else:
                current_weights.append(0.0)
        
        print(f"当前权重配置: {[f'{w:.3f}' for w in current_weights if w > 0]}")
        
        # 发送权重配置信号（这会在"开始训练"事件中记录权重）
        self.weights_auto_assigned.emit(current_weights)
        
        print(f"当前权重配置已记录")
        print(f"=== 权重配置记录完成 ===\n")
    
    

    def _save_current_manual_weights(self):
        """保存当前手动权重配置（手动分配模式专用）"""
        print(f"\n=== {self.title()}: 保存手动权重配置 ===")
        
        # 获取当前手动设置的权重
        manual_weights = []
        selected_sensors = []
        total_weight = 0
        
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                selected_sensors.append(i)
                if i < len(self.weight_spinboxes):
                    weight = self.weight_spinboxes[i].value()
                    manual_weights.append(weight)
                    total_weight += weight
                else:
                    manual_weights.append(0.0)
            else:
                manual_weights.append(0.0)
        
        print(f"选中的传感器: {[i+1 for i in selected_sensors]}")
        print(f"手动设置的权重: {[f'{w:.3f}' for w in manual_weights if w > 0]}")
        print(f"权重总和: {total_weight:.3f}")
        
        # 验证权重配置
        if len(selected_sensors) == 0:
            print("⚠️ 没有选中任何传感器，使用平均权重")
            # 如果没有选择传感器，给所有传感器平均权重
            avg_weight = 1.0 / self.sensor_count
            manual_weights = [avg_weight] * self.sensor_count
            for i in range(self.sensor_count):
                self.sensor_checkboxes[i].setChecked(True)
                self.weight_spinboxes[i].setValue(avg_weight)
            final_weights = manual_weights
        else:
            # 检查是否有手动设置的权重
            has_manual_weights = any(manual_weights[i] > 0 for i in selected_sensors)
            
            if has_manual_weights:
                # 用户手动指定了权重
                if abs(total_weight - 1.0) > 1e-6:
                    # 权重和不为1，自动归一化
                    print(f"权重和不为1，自动归一化...")
                    if total_weight > 0:
                        for i in selected_sensors:
                            if manual_weights[i] > 0:
                                manual_weights[i] = manual_weights[i] / total_weight
                                self.weight_spinboxes[i].setValue(manual_weights[i])
                        print("✓ 权重已自动归一化")
                
                final_weights = manual_weights
                print("✓ 使用手动指定的权重")
            else:
                # 用户只选择了传感器，没有指定权重 - 平均分配
                print("用户未指定权重，平均分配...")
                final_weights = [0.0] * self.sensor_count
                avg_weight = 1.0 / len(selected_sensors)
                
                for i in selected_sensors:
                    final_weights[i] = avg_weight
                    self.weight_spinboxes[i].setValue(avg_weight)
                
                print(f"平均分配的权重: {avg_weight:.3f}")
        
        # 验证最终权重
        final_sum = sum(final_weights)
        print(f"最终权重和: {final_sum:.6f}")
        
        # 更新组合值
        self.update_combined_value()
        
        # 发送权重保存完成信号（这会触发事件记录到文件）
        self.weights_auto_assigned.emit(final_weights)
        
        print(f"手动权重配置已保存到事件文件")
        print(f"=== 手动权重保存完成 ===\n")

    def _execute_auto_allocation_and_save(self):
        """执行自动分配并保存权重（自动分配模式专用）"""
        print(f"\n=== {self.title()}: 执行前-k最大分配 ===")
        
        # 计算差异值并选择前k个传感器
        differences = []
        for i in range(self.sensor_count):
            original_val = self.original_values[i] if i < len(self.original_values) else 2600.0
            target_val = self.target_values[i] if i < len(self.target_values) else 2350.0
            diff = abs(target_val - original_val)
            differences.append((i, diff))
            print(f"传感器{i+1}: 原始值={original_val:.1f}, 目标值={target_val:.1f}, 差异={diff:.1f}")
        
        # 按差异值降序排序，选择前k个
        differences.sort(key=lambda x: x[1], reverse=True)
        top_k_indices = [idx for idx, _ in differences[:self.k_value]]
        top_k_diffs = [diff for _, diff in differences[:self.k_value]]
        
        print(f"选择的前{self.k_value}个传感器: {[i+1 for i in top_k_indices]}")
        print(f"对应的差异值: {[f'{d:.1f}' for d in top_k_diffs]}")
        
        # 计算权重
        total_diff = sum(top_k_diffs)
        if total_diff > 0:
            weights = [diff / total_diff for diff in top_k_diffs]
            # 确保权重和严格等于1（处理浮点误差）
            weights_sum = sum(weights)
            if abs(weights_sum - 1.0) > 1e-6:
                weights = [w / weights_sum for w in weights]
        else:
            # 如果所有差异都为0，平均分配权重
            weights = [1.0 / self.k_value] * self.k_value
        
        print(f"权重计算结果: {[f'{w:.3f}' for w in weights]}")
        print(f"权重和: {sum(weights):.6f}")
        
        # 清空所有传感器的选择和权重
        for i in range(self.sensor_count):
            self.sensor_checkboxes[i].setChecked(False)
            self.weight_spinboxes[i].setValue(0.0)
        
        # 应用前k个传感器的选择和权重
        for i, (sensor_idx, weight) in enumerate(zip(top_k_indices, weights)):
            self.sensor_checkboxes[sensor_idx].setChecked(True)
            self.weight_spinboxes[sensor_idx].setValue(weight)
            print(f"✓ 传感器{sensor_idx+1}: 已勾选，权重={weight:.3f}")
        
        # 更新组合值
        self.update_combined_value()
        
        # 准备最终权重数组并保存到事件文件
        final_weights = [0.0] * self.sensor_count
        for i, (sensor_idx, weight) in enumerate(zip(top_k_indices, weights)):
            final_weights[sensor_idx] = weight
        
        # 发送权重保存完成信号（这会触发事件记录到文件）
        self.weights_auto_assigned.emit(final_weights)
        
        print(f"前-k最大分配完成并已保存到事件文件")
        print(f"=== 自动分配并保存完成 ===\n")

    
    def store_target_values(self, sensor_data):
        """存储目标值数据并根据模式自动处理权重"""
        if len(sensor_data) > 1:  # 跳过时间戳
            self.target_values = sensor_data[1:self.sensor_count+1]
            while len(self.target_values) < self.sensor_count:
                self.target_values.append(2350.0)
        else:
            self.target_values = [2350.0] * self.sensor_count
        
        self.has_target_data = True
        self._update_data_status()
        self._update_target_value_spins()
        print(f"{self.title()}: 目标值已存储 {self.target_values[:3]}...")
        
        # 根据当前模式处理权重
        if self.current_weight_mode == "auto":
            # 自动分配模式：执行前-k最大分配并保存权重
            if self.has_original_data and self.has_target_data:
                print(f"{self.title()}: 自动分配模式 - 执行前-k最大分配并保存")
                self._execute_auto_allocation_and_save()
        else:
            # 手动分配模式：保存当前的手动权重配置
            print(f"{self.title()}: 手动分配模式 - 保存当前手动权重")
            self._save_current_manual_weights()
    
    def _update_data_status(self):
        """更新数据状态显示"""
        if self.has_original_data and self.has_target_data:
            self.data_status_label.setText("数据状态: 原始值和目标值已就绪")
            self.data_status_label.setStyleSheet("color: green;")
        elif self.has_original_data:
            self.data_status_label.setText("数据状态: 仅有原始值")
            self.data_status_label.setStyleSheet("color: orange;")
        elif self.has_target_data:
            self.data_status_label.setText("数据状态: 仅有目标值")
            self.data_status_label.setStyleSheet("color: orange;")
        else:
            self.data_status_label.setText("数据状态: 等待数据")
            self.data_status_label.setStyleSheet("color: gray;")
        
        # 更新UI状态
        self._update_ui_for_mode()
    
    

    def on_weight_value_changed(self):
        """处理权重值变化 - 增强复位按钮显示逻辑"""
        # 【关键】检查是否需要显示复位按钮
        self._check_and_update_reset_button()

    def _check_and_update_reset_button(self):
        """检查并更新复位按钮的显示状态"""
        # 只有在有自动分配结果时才可能显示复位按钮
        if not hasattr(self, 'auto_allocation_result') or not self.auto_allocation_result:
            self.reset_auto_btn.setVisible(False)
            return
        
        # 检查当前配置是否与自动分配结果不同
        result = self.auto_allocation_result
        current_differs = self._is_current_config_different_from_auto()
        
        if current_differs:
            # 当前配置与自动分配结果不同，显示复位按钮
            self.reset_auto_btn.setVisible(True)
            self.reset_auto_btn.setEnabled(True)
            self.reset_auto_btn.setText("复位为自动分配结果")
            
            # 更新状态提示
            if self.current_weight_mode == "auto":
                self.mode_status_label.setText("当前模式: 自动分配 (已手动修改)")
                self.mode_status_label.setStyleSheet("color: orange; font-size: 10px;")
            
            print(f"{self.title()}: 检测到手动修改，复位按钮已显示")
        else:
            # 当前配置与自动分配结果相同
            if self.current_weight_mode == "auto":
                # 自动模式下，配置相同时隐藏复位按钮
                self.reset_auto_btn.setVisible(False)
                self.mode_status_label.setText("当前模式: 自动分配")
                self.mode_status_label.setStyleSheet("color: blue; font-size: 10px;")
            else:
                # 手动模式下，即使配置相同也显示复位按钮（用户可能想回到自动结果）
                self.reset_auto_btn.setVisible(True)
                self.reset_auto_btn.setEnabled(True)

    def _is_current_config_different_from_auto(self):
        """检查当前配置是否与自动分配结果不同"""
        if not hasattr(self, 'auto_allocation_result') or not self.auto_allocation_result:
            return False
        
        result = self.auto_allocation_result
        auto_indices = set(result['indices'])
        auto_weights_dict = {idx: weight for idx, weight in zip(result['indices'], result['weights'])}
        
        # 检查当前选中的传感器
        current_selected = set()
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                current_selected.add(i)
        
        # 如果选中的传感器不同，则配置不同
        if current_selected != auto_indices:
            return True
        
        # 如果选中的传感器相同，检查权重是否不同
        for i in current_selected:
            if i < len(self.weight_spinboxes):
                current_weight = self.weight_spinboxes[i].value()
                auto_weight = auto_weights_dict.get(i, 0.0)
                # 允许小的浮点误差
                if abs(current_weight - auto_weight) > 1e-3:
                    return True
        
        return False


    
    def apply_top_k_allocation(self):
        """应用前-k最大分配算法（优化版：权重约束）"""
        if not (self.has_original_data and self.has_target_data):
            print(f"{self.title()}: 数据不完整，无法应用前-k最大分配")
            return
        
        print(f"\n=== {self.title()}: 应用前-k最大分配（权重约束版）===")
        print(f"k值: {self.k_value}")
        print(f"原始值: {self.original_values[:3]}...")
        print(f"目标值: {self.target_values[:3]}...")
        
        # 计算每个传感器的差异值
        differences = []
        for i in range(self.sensor_count):
            original_val = self.original_values[i] if i < len(self.original_values) else 2600.0
            target_val = self.target_values[i] if i < len(self.target_values) else 2350.0
            diff = abs(target_val - original_val)
            differences.append((i, diff))
            print(f"传感器{i+1}: 原始值={original_val:.1f}, 目标值={target_val:.1f}, 差异={diff:.1f}")
        
        # 按差异值降序排序，选择前k个
        differences.sort(key=lambda x: x[1], reverse=True)
        top_k_indices = [idx for idx, _ in differences[:self.k_value]]
        top_k_diffs = [diff for _, diff in differences[:self.k_value]]
        
        print(f"选择的前{self.k_value}个传感器索引: {top_k_indices}")
        print(f"对应的差异值: {[f'{d:.1f}' for d in top_k_diffs]}")
        
        # 计算权重：满足约束条件
        # 约束：(1) 权重 ≥ 0, (2) Σ权重 = 1
        # 目标：最大化 Σ(|最佳值-原始值| × 权重)
        
        total_diff = sum(top_k_diffs)
        if total_diff > 0:
            # 按差异值比例分配权重，确保权重和为1
            weights = [diff / total_diff for diff in top_k_diffs]
            
            # 验证约束条件
            weights_sum = sum(weights)
            print(f"权重计算结果: {[f'{w:.3f}' for w in weights]}")
            print(f"权重和: {weights_sum:.3f}")
            print(f"目标函数值: {sum(d * w for d, w in zip(top_k_diffs, weights)):.1f}")
            
            # 确保权重和严格等于1（处理浮点误差）
            if abs(weights_sum - 1.0) > 1e-6:
                weights = [w / weights_sum for w in weights]
                print(f"权重归一化后: {[f'{w:.3f}' for w in weights]}")
                print(f"归一化后权重和: {sum(weights):.6f}")
        else:
            # 如果所有差异都为0，平均分配权重
            weights = [1.0 / self.k_value] * self.k_value
            print(f"差异值均为0，采用平均分配: {[f'{w:.3f}' for w in weights]}")
        
        # 清空所有传感器的选择和权重
        for i in range(self.sensor_count):
            self.sensor_checkboxes[i].setChecked(False)
            self.weight_spinboxes[i].setValue(0.0)
        
        # 应用前k个传感器的选择和权重
        for i, (sensor_idx, weight) in enumerate(zip(top_k_indices, weights)):
            self.sensor_checkboxes[sensor_idx].setChecked(True)
            self.weight_spinboxes[sensor_idx].setValue(weight)
            print(f"传感器{sensor_idx+1}: 权重={weight:.3f}")
        
        # 验证最终权重约束
        total_assigned_weight = sum(weights)
        print(f"最终验证 - 权重和: {total_assigned_weight:.6f}")
        print(f"权重非负性: {all(w >= 0 for w in weights)}")
        
        # 更新组合值
        self.update_combined_value()
        
        # 发送权重分配完成信号
        final_weights = [0.0] * self.sensor_count
        for i, (sensor_idx, weight) in enumerate(zip(top_k_indices, weights)):
            final_weights[sensor_idx] = weight
        
        self.weights_auto_assigned.emit(final_weights)
        
        # 自动分配完成后，如果用户想修改，提示切换到手动模式
        if self.current_weight_mode == "auto":
            self.mode_status_label.setText("当前模式: 自动分配 (如需修改请切换到手动模式)")
            self.mode_status_label.setStyleSheet("color: blue; font-size: 10px;")
        
        print(f"=== 前-k最大分配完成（权重约束满足）===\n")
    
    def _update_original_value_spins(self):
        """更新原始值SpinBox的显示"""
        for i in range(len(self.original_value_spins)):
            if i < len(self.original_values):
                self.original_value_spins[i].setValue(int(self.original_values[i]))
    
    def _update_target_value_spins(self):
        """更新目标值SpinBox的显示"""
        for i in range(len(self.rotate_best_value_spins)):
            if i < len(self.target_values):
                self.rotate_best_value_spins[i].setValue(int(self.target_values[i]))
    
    def apply_top_k_allocation(self):
        """应用前-k最大分配算法（优化版：权重约束）"""
        if not (self.has_original_data and self.has_target_data):
            print(f"{self.title()}: 数据不完整，无法应用前-k最大分配")
            return
        
        print(f"\n=== {self.title()}: 应用前-k最大分配（权重约束版）===")
        print(f"k值: {self.k_value}")
        print(f"原始值: {self.original_values[:3]}...")
        print(f"目标值: {self.target_values[:3]}...")
        
        # 计算每个传感器的差异值
        differences = []
        for i in range(self.sensor_count):
            original_val = self.original_values[i] if i < len(self.original_values) else 2600.0
            target_val = self.target_values[i] if i < len(self.target_values) else 2350.0
            diff = abs(target_val - original_val)
            differences.append((i, diff))
            print(f"传感器{i+1}: 原始值={original_val:.1f}, 目标值={target_val:.1f}, 差异={diff:.1f}")
        
        # 按差异值降序排序，选择前k个
        differences.sort(key=lambda x: x[1], reverse=True)
        top_k_indices = [idx for idx, _ in differences[:self.k_value]]
        top_k_diffs = [diff for _, diff in differences[:self.k_value]]
        
        print(f"选择的前{self.k_value}个传感器索引: {top_k_indices}")
        print(f"对应的差异值: {[f'{d:.1f}' for d in top_k_diffs]}")
        
        # 计算权重：满足约束条件
        # 约束：(1) 权重 ≥ 0, (2) Σ权重 = 1
        # 目标：最大化 Σ(|最佳值-原始值| × 权重)
        
        total_diff = sum(top_k_diffs)
        if total_diff > 0:
            # 按差异值比例分配权重，确保权重和为1
            weights = [diff / total_diff for diff in top_k_diffs]
            
            # 验证约束条件
            weights_sum = sum(weights)
            print(f"权重计算结果: {[f'{w:.3f}' for w in weights]}")
            print(f"权重和: {weights_sum:.3f}")
            print(f"目标函数值: {sum(d * w for d, w in zip(top_k_diffs, weights)):.1f}")
            
            # 确保权重和严格等于1（处理浮点误差）
            if abs(weights_sum - 1.0) > 1e-6:
                weights = [w / weights_sum for w in weights]
                print(f"权重归一化后: {[f'{w:.3f}' for w in weights]}")
                print(f"归一化后权重和: {sum(weights):.6f}")
        else:
            # 如果所有差异都为0，平均分配权重
            weights = [1.0 / self.k_value] * self.k_value
            print(f"差异值均为0，采用平均分配: {[f'{w:.3f}' for w in weights]}")
        
        # 清空所有传感器的选择和权重
        for i in range(self.sensor_count):
            self.sensor_checkboxes[i].setChecked(False)
            self.weight_spinboxes[i].setValue(0.0)
        
        # 应用前k个传感器的选择和权重
        for i, (sensor_idx, weight) in enumerate(zip(top_k_indices, weights)):
            self.sensor_checkboxes[sensor_idx].setChecked(True)
            self.weight_spinboxes[sensor_idx].setValue(weight)
            print(f"传感器{sensor_idx+1}: 权重={weight:.3f}")
        
        # 验证最终权重约束
        total_assigned_weight = sum(weights)
        print(f"最终验证 - 权重和: {total_assigned_weight:.6f}")
        print(f"权重非负性: {all(w >= 0 for w in weights)}")
        
        # 更新组合值
        self.update_combined_value()
        
        # 发送权重分配完成信号
        final_weights = [0.0] * self.sensor_count
        for i, (sensor_idx, weight) in enumerate(zip(top_k_indices, weights)):
            final_weights[sensor_idx] = weight
        
        self.weights_auto_assigned.emit(final_weights)
        
        print(f"=== 前-k最大分配完成（权重约束满足）===\n")
    
    def get_current_weights(self):
        """获取当前权重配置"""
        weights = []
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                if i < len(self.weight_spinboxes):
                    weights.append(self.weight_spinboxes[i].value())
                else:
                    weights.append(0.0)
            else:
                weights.append(0.0)
        return weights
    
    def get_original_target_values(self):
        """获取原始值和目标值"""
        return {
            'original_values': self.original_values.copy(),
            'target_values': self.target_values.copy(),
            'has_original_data': self.has_original_data,
            'has_target_data': self.has_target_data
        }
    
    def clear_stored_data(self):
        """清空存储的数据"""
        self.original_values = [2600.0] * self.sensor_count
        self.target_values = [2350.0] * self.sensor_count
        self.has_original_data = False
        self.has_target_data = False
        self._update_data_status()
        print(f"{self.title()}: 已清空存储的数据")
    

    def _create_sensor_controls(self):
        """创建传感器控件（增强版）"""
        # 清空现有控件列表
        self.sensor_checkboxes = []
        self.weight_spinboxes = []
        self.original_value_spins = []
        self.rotate_best_value_spins = []
        self.value_labels = []
        self.norm_labels = []
        self.ov_labels = []
        self.rbv_labels = []
        self.sensor_rows = []
        
        # 创建传感器控件
        for i in range(self.sensor_count):
            # 创建传感器行的主容器
            sensor_row_widget = QWidget()
            sensor_row_main_layout = QVBoxLayout()
            sensor_row_widget.setLayout(sensor_row_main_layout)
            
            # 第一行：复选框和权重
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
            weight_spin.setDecimals(3)
            self.weight_spinboxes.append(weight_spin)
            sensor_row.addWidget(weight_spin)
            
            sensor_row_main_layout.addLayout(sensor_row)
            
            # 第二行：原始值和最佳值的spinbox
            spin_row = QHBoxLayout()
            ov_label = QLabel("原始值:")
            ov_spin = QSpinBox()
            ov_spin.setRange(0, 4095)
            ov_spin.setValue(2600)
            ov_spin.setVisible(False)
            ov_label.setVisible(False)
            self.original_value_spins.append(ov_spin)
            self.ov_labels.append(ov_label)
            spin_row.addWidget(ov_label)
            spin_row.addWidget(ov_spin)
            
            rbv_label = QLabel("最佳值:")
            rbv_spin = QSpinBox()
            rbv_spin.setRange(0, 4095)
            rbv_spin.setValue(2350)
            rbv_spin.setVisible(False)
            rbv_label.setVisible(False)
            self.rotate_best_value_spins.append(rbv_spin)
            self.rbv_labels.append(rbv_label)
            spin_row.addWidget(rbv_label)
            spin_row.addWidget(rbv_spin)
            
            sensor_row_main_layout.addLayout(spin_row)
            
            # 第三行：实时值和归一化结果
            value_label = QLabel("当前值: 0")
            norm_label = QLabel("归一化: 0.00")
            value_label.setVisible(False)
            norm_label.setVisible(False)
            self.value_labels.append(value_label)
            self.norm_labels.append(norm_label)
            sensor_row_main_layout.addWidget(value_label)
            sensor_row_main_layout.addWidget(norm_label)
            
            # 连接信号
            checkbox.stateChanged.connect(lambda state, idx=i: self.on_sensor_selected(state, idx))
            weight_spin.valueChanged.connect(self.on_weight_value_changed)  # 新增权重变化信号
            weight_spin.valueChanged.connect(self.update_combined_value)
            
            # 添加到布局
            self.sensor_layout.addWidget(sensor_row_widget)
            self.sensor_rows.append(sensor_row_widget)
        
        # 初始化传感器值和权重列表
        self.sensor_values = [0] * self.sensor_count
        self.sensor_weights = [0] * self.sensor_count
    
    def set_sensor_count(self, count):
        """动态设置传感器数量"""
        if count == self.sensor_count:
            return
        
        print(f"{self.title()} 传感器数量从 {self.sensor_count} 更改为 {count}")
        
        # 保存当前状态
        old_states = self._save_current_states()
        
        # 更新传感器数量
        old_count = self.sensor_count
        self.sensor_count = count
        
        # 更新k值范围
        if hasattr(self, 'k_spinbox') and self.k_spinbox:
            self.k_spinbox.setRange(1, count)
            if self.k_value > count:
                self.k_value = count
                self.k_spinbox.setValue(count)
        
        # 调整存储的数据长度
        self._resize_stored_data(old_count, count)
        
        # 清除现有的传感器控件
        self._clear_sensor_controls()
        
        # 重新创建传感器控件
        self._create_sensor_controls()
        
        # 恢复之前的状态
        self._restore_states(old_states)
        
        print(f"{self.title()} 传感器数量更新完成")
    
    def _resize_stored_data(self, old_count, new_count):
        """调整存储数据的长度"""
        if new_count > old_count:
            # 增加传感器，补充默认值
            self.original_values.extend([2600.0] * (new_count - old_count))
            self.target_values.extend([2350.0] * (new_count - old_count))
        elif new_count < old_count:
            # 减少传感器，截断数据
            self.original_values = self.original_values[:new_count]
            self.target_values = self.target_values[:new_count]
    
    # 保持原有方法不变
    def _save_current_states(self):
        """保存当前传感器状态"""
        states = {
            'checked': [],
            'weights': [],
            'original_values': [],
            'rotate_best_values': []
        }
        
        try:
            for i in range(min(len(self.sensor_checkboxes), self.sensor_count)):
                states['checked'].append(self.sensor_checkboxes[i].isChecked())
                states['weights'].append(self.weight_spinboxes[i].value())
                states['original_values'].append(self.original_value_spins[i].value())
                states['rotate_best_values'].append(self.rotate_best_value_spins[i].value())
        except (IndexError, AttributeError):
            pass
        
        return states
    
    def _restore_states(self, states):
        """恢复传感器状态"""
        if not states:
            return
        
        try:
            for i in range(min(len(self.sensor_checkboxes), len(states['checked']))):
                if i < len(states['checked']):
                    self.sensor_checkboxes[i].setChecked(states['checked'][i])
                if i < len(states['weights']):
                    self.weight_spinboxes[i].setValue(states['weights'][i])
                if i < len(states['original_values']):
                    self.original_value_spins[i].setValue(states['original_values'][i])
                if i < len(states['rotate_best_values']):
                    self.rotate_best_value_spins[i].setValue(states['rotate_best_values'][i])
        except (IndexError, AttributeError):
            pass
    
    def _clear_sensor_controls(self):
        """清除现有的传感器控件"""
        for sensor_row_widget in self.sensor_rows:
            self.sensor_layout.removeWidget(sensor_row_widget)
            sensor_row_widget.deleteLater()
        
        self.sensor_rows.clear()
        self.sensor_checkboxes.clear()
        self.weight_spinboxes.clear()
        self.original_value_spins.clear()
        self.rotate_best_value_spins.clear()
        self.value_labels.clear()
        self.norm_labels.clear()
        self.ov_labels.clear()
        self.rbv_labels.clear()
    
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
        """处理传感器选择 - 增强复位按钮显示逻辑"""
        if sensor_idx >= len(self.weight_spinboxes):
            return
        
        self.weight_spinboxes[sensor_idx].setEnabled(state == Qt.Checked)
        show = (state == Qt.Checked)
        
        # 显示/隐藏相关控件
        if sensor_idx < len(self.original_value_spins):
            self.original_value_spins[sensor_idx].setVisible(show)
        if sensor_idx < len(self.rotate_best_value_spins):
            self.rotate_best_value_spins[sensor_idx].setVisible(show)
        if sensor_idx < len(self.ov_labels):
            self.ov_labels[sensor_idx].setVisible(show)
        if sensor_idx < len(self.rbv_labels):
            self.rbv_labels[sensor_idx].setVisible(show)
        if sensor_idx < len(self.value_labels):
            self.value_labels[sensor_idx].setVisible(show)
        if sensor_idx < len(self.norm_labels):
            self.norm_labels[sensor_idx].setVisible(show)
        
        # 【关键】检查是否需要显示复位按钮
        self._check_and_update_reset_button()
        
        self.update_combined_value()
    
    def update_combined_value(self):
        """更新组合值"""
        total_weight = 0
        weighted_sum = 0
        all_zero = True
        
        for i in range(self.sensor_count):
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                if i < len(self.weight_spinboxes):
                    weight = self.weight_spinboxes[i].value()
                    if weight != 0:
                        ov = self.original_value_spins[i].value() if i < len(self.original_value_spins) else 2600
                        rbv = self.rotate_best_value_spins[i].value() if i < len(self.rotate_best_value_spins) else 2350
                        sensor_val = self.sensor_values[i] if i < len(self.sensor_values) else 0
                        
                        # 防止分母为0
                        if ov == rbv:
                            norm = 1.0
                        else:
                            norm = (sensor_val - rbv) / (ov - rbv)
                        norm = max(0.0, min(1.0, norm))
                        total_weight += abs(weight)
                        weighted_sum += norm * weight
                        
                        # 实时显示
                        if i < len(self.value_labels):
                            self.value_labels[i].setText(f"当前值: {int(sensor_val)}")
                        if i < len(self.norm_labels):
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
        if sensor_index < len(self.sensor_values):
            self.sensor_values[sensor_index] = value
            self.update_combined_value()
    
    def update_manual_value(self, value):
        """更新手动值"""
        self.current_value = value
        self.value_label.setText(str(value))
        self.value_changed.emit(value)
        return value
    
    def set_highlighted(self, highlighted):
        """设置高亮状态"""
        if highlighted:
            self.setStyleSheet("QGroupBox { background: #e6f2ff; }")
            if hasattr(self, 'scroll_area') and self.scroll_area:
                self.scroll_area.setStyleSheet("""
                    QScrollArea {
                        background-color: rgb(227, 239, 252);
                        border: none;
                    }
                    QScrollArea > QWidget > QWidget {
                        background-color: rgb(227, 239, 252);
                    }
                    QScrollBar:vertical {
                        background-color: #f0f0f0;
                        width: 12px;
                        border-radius: 6px;
                    }
                    QScrollBar::handle:vertical {
                        background-color: #c0c0c0;
                        border-radius: 6px;
                        min-height: 20px;
                    }
                    QScrollBar::handle:vertical:hover {
                        background-color: #a0a0a0;
                    }
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        height: 0px;
                    }
                """)
            if hasattr(self, 'sensor_container') and self.sensor_container:
                self.sensor_container.setStyleSheet("background-color: rgb(227, 239, 252);")
        else:
            self.setStyleSheet("")
            if hasattr(self, 'scroll_area') and self.scroll_area:
                self.scroll_area.setStyleSheet("""
                    QScrollArea {
                        background-color: rgb(243, 243, 243);
                        border: none;
                    }
                    QScrollArea > QWidget > QWidget {
                        background-color: rgb(243, 243, 243);
                    }
                    QScrollBar:vertical {
                        background-color: #f0f0f0;
                        width: 12px;
                        border-radius: 6px;
                    }
                    QScrollBar::handle:vertical {
                        background-color: #c0c0c0;
                        border-radius: 6px;
                        min-height: 20px;
                    }
                    QScrollBar::handle:vertical:hover {
                        background-color: #a0a0a0;
                    }
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        height: 0px;
                    }
                """)
            if hasattr(self, 'sensor_container') and self.sensor_container:
                self.sensor_container.setStyleSheet("background-color: rgb(243, 243, 243);")
    
    def set_or_rbv_defaults(self, defaults):
        """批量设置原始值和最佳值的默认值"""
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
            if i < len(self.sensor_checkboxes) and self.sensor_checkboxes[i].isChecked():
                if i < len(self.weight_spinboxes):
                    weights.append(self.weight_spinboxes[i].value())
                else:
                    weights.append(0.0)
            else:
                weights.append(0.0)
        return weights
        
    def get_ov_rbv_values(self):
        """获取OV/RBV值"""
        ov_values = []
        rbv_values = []
        
        for i in range(self.sensor_count):
            if i < len(self.original_value_spins):
                ov_values.append(self.original_value_spins[i].value())
            else:
                ov_values.append(2600)
            
            if i < len(self.rotate_best_value_spins):
                rbv_values.append(self.rotate_best_value_spins[i].value())
            else:
                rbv_values.append(2350)
        
        return ov_values, rbv_values