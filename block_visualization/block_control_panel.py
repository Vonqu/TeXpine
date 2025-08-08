#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
积木控制面板模块（修正版）
========================

修正内容：
1. 确保四个传感器选择器模块完全对齐
2. 所有模块都有手动控制功能
3. 保持原有的蓝底高亮样式
4. 添加误差范围设置功能
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout
from PyQt5.QtCore import pyqtSignal

# 导入修正后的SensorSelector
from block_visualization.sensor_selector import SensorSelector

class BlockControlPanel(QWidget):
    """
    积木控制面板（修正版）
    ====================
    
    确保四个模块功能一致且对齐
    """
    
    # 新增信号
    error_range_changed = pyqtSignal(str, float)  # 控制器名称，误差范围值
    
    def __init__(self, sensor_count=6, parent=None):
        super().__init__(parent)
        self.sensor_count = sensor_count
        self.setup_ui()
        self.connect_error_range_signals()
        
    def setup_ui(self):
        """设置UI - 确保四个模块完全对齐"""
        layout = QHBoxLayout(self)
        layout.setSpacing(10)  # 缩小间距
        
        # 创建四个传感器选择器，确保参数完全一致
        self.gray_rotation = SensorSelector("骨盆前后翻转", self.sensor_count, special_mode=True)
        self.blue_curvature = SensorSelector("脊柱曲率矫正", self.sensor_count, special_mode=True)
        self.gray_tilt = SensorSelector("骨盆左右倾斜", self.sensor_count, special_mode=True)  # 修改：添加special_mode
        self.green_tilt = SensorSelector("肩部左右倾斜", self.sensor_count, special_mode=True)  # 修改：添加special_mode
        
        # 设置固定宽度和高度，确保对齐
        for control in [self.gray_rotation, self.blue_curvature, self.gray_tilt, self.green_tilt]:
            control.setFixedWidth(250)
            control.setMinimumHeight(450)  # 增加高度以容纳误差范围设置和手动控制
            layout.addWidget(control)
            
        layout.addStretch()
        
    def connect_error_range_signals(self):
        """连接误差范围变更信号"""
        self.gray_rotation.error_range_changed.connect(
            lambda value: self.error_range_changed.emit("gray_rotation", value)
        )
        self.blue_curvature.error_range_changed.connect(
            lambda value: self.error_range_changed.emit("blue_curvature", value)
        )
        self.gray_tilt.error_range_changed.connect(
            lambda value: self.error_range_changed.emit("gray_tilt", value)
        )
        self.green_tilt.error_range_changed.connect(
            lambda value: self.error_range_changed.emit("green_tilt", value)
        )
        
    def get_error_ranges(self):
        """获取所有控制器的误差范围"""
        return {
            'gray_rotation': self.gray_rotation.get_error_range(),
            'blue_curvature': self.blue_curvature.get_error_range(),
            'gray_tilt': self.gray_tilt.get_error_range(),
            'green_tilt': self.green_tilt.get_error_range()
        }
        
    def get_stage_error_range(self, stage):
        """根据阶段获取对应的误差范围"""
        error_ranges = self.get_error_ranges()
        
        if stage == 1:
            return error_ranges['gray_rotation']
        elif stage == 2:
            return error_ranges['blue_curvature']
        elif stage == 3:
            # 阶段3使用两个控制器，返回平均值
            return (error_ranges['gray_tilt'] + error_ranges['green_tilt']) / 2
        else:
            return 0.1  # 默认值
    
    def process_sensor_data(self, data_values):
        """处理传感器数据（保持原有功能）"""
        sensor_values = data_values[1:]
        for i, value in enumerate(sensor_values):
            if i < self.sensor_count:
                self.gray_rotation.set_sensor_value(i, value)
                self.gray_tilt.set_sensor_value(i, value)
                self.blue_curvature.set_sensor_value(i, value)
                self.green_tilt.set_sensor_value(i, value)
                
    def highlight_stage(self, stage):
        """高亮当前阶段对应的控制器（保持原有蓝底样式）"""
        # 1: 只高亮灰色方块前后翻转
        # 2: 只高亮蓝色方块曲率排列
        # 3: 高亮灰色左右倾斜和绿色左右倾斜
        self.gray_rotation.set_highlighted(stage == 1)
        self.blue_curvature.set_highlighted(stage == 2)
        self.gray_tilt.set_highlighted(stage == 3)
        self.green_tilt.set_highlighted(stage == 3)
        
    def set_stage_defaults(self, stage):
        """根据阶段设置OV和RBV的默认值（保持原有功能）"""
        # 阶段1：只调整骨盆前后翻转，其他默认
        if stage == 1:
            # 只需设置gray_rotation，其他保持默认
            self.gray_rotation.set_or_rbv_defaults([
                {'ov': 2600, 'rbv': 2350},  # 传感器1
                {'ov': 2600, 'rbv': 2350},  # 传感器2
                {'ov': 2600, 'rbv': 2350},  # 传感器3                                                
                {'ov': 2600, 'rbv': 2350},  # 传感器4
                {'ov': 2600, 'rbv': 2350},  # 传感器5
                {'ov': 2900, 'rbv': 2500}   # 传感器6
            ])
        # 阶段2：脊柱曲率矫正
        elif stage == 2:
            self.blue_curvature.set_or_rbv_defaults([
                {'ov': 2600, 'rbv': 2350},  # 传感器1
                {'ov': 2600, 'rbv': 2350},  # 传感器2
                {'ov': 2600, 'rbv': 2350},  # 传感器3                                                
                {'ov': 2600, 'rbv': 2350},  # 传感器4
                {'ov': 2600, 'rbv': 2350},  # 传感器5
                {'ov': 2900, 'rbv': 2500}   # 传感器6
            ])
        # 阶段3：骨盆和肩部左右倾斜
        elif stage == 3:
            self.gray_tilt.set_or_rbv_defaults([
                {'ov': 2600, 'rbv': 2350},  # 传感器1
                {'ov': 2600, 'rbv': 2350},  # 传感器2
                {'ov': 2600, 'rbv': 2350},  # 传感器3                                                
                {'ov': 2990, 'rbv': 2650},  # 传感器4
                {'ov': 2600, 'rbv': 2350},  # 传感器5
                {'ov': 2600, 'rbv': 2500}   # 传感器6
            ])
            self.green_tilt.set_or_rbv_defaults([
                {'ov': 2600, 'rbv': 2350},  # 传感器1
                {'ov': 2600, 'rbv': 2350},  # 传感器2
                {'ov': 2600, 'rbv': 2350},  # 传感器3                                                
                {'ov': 2600, 'rbv': 2350},  # 传感器4
                {'ov': 2600, 'rbv': 2350},  # 传感器5
                {'ov': 2900, 'rbv': 2500}   # 传感器6
            ])