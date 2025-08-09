#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
控制面板模块，包含设置和控制组件（添加UDP功能）
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QLabel, QComboBox, QPushButton, QSpinBox, 
                            QLineEdit, QFileDialog, QGroupBox, QCheckBox,
                            QColorDialog, QStackedWidget, QButtonGroup, QFormLayout,
                            QScrollArea, QDoubleSpinBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIntValidator
import serial.tools.list_ports
import time
from block_visualization.spine_type_selector import SpineTypeSelector

class ControlPanel(QWidget):
    """控制面板类，用于显示设置选项和传感器控制"""
    
    # 定义信号
    path_changed = pyqtSignal(str)
    curve_visibility_changed = pyqtSignal(int, bool)
    curve_color_changed = pyqtSignal(int, object)
    curve_name_changed = pyqtSignal(int, str)
    acquisition_started = pyqtSignal()  # 采集开始信号
    acquisition_stopped = pyqtSignal()  # 采集停止信号
    data_path_changed = pyqtSignal(str)  # 数据文件路径变更信号
    events_path_changed = pyqtSignal(str)  # 事件文件路径变更信号
    sensor_count_changed = pyqtSignal(int)  # 传感器数量变更信号
    mode_changed = pyqtSignal(str)  # 模式变更信号（"doctor" 或 "patient"）
    udp_settings_changed = pyqtSignal(bool, str, int)  # UDP设置变更信号（启用, 地址, 端口）
    filter_params_changed = pyqtSignal(dict)  # 滤波参数变更信号
    enhancement_params_changed = pyqtSignal(dict)  # 数据增强参数变更信号
    
    def __init__(self, parent=None):
        print("ControlPanel: 开始初始化...")
        super().__init__(parent)
        
        # 控制面板数据
        self.visibility_checkboxes = []  # 可见性复选框
        self.color_buttons = []  # 颜色按钮
        self.curve_labels = []  # 曲线标签
        self.is_acquisition_active = False  # 采集状态标志
        
        # 文件路径
        self.data_save_path = ""  # 所有数据保存路径
        self.events_save_path = ""  # 事件数据保存路径
        
        # 初始化UI
        print("ControlPanel: 开始初始化UI...")
        self._init_ui()
        print("ControlPanel: UI初始化完成")
        
    def _init_ui(self):
        """初始化用户界面"""
        print("ControlPanel: 开始创建布局...")
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 设置滚动区域背景颜色
        scroll_area.setStyleSheet("QScrollArea { background-color: rgb(252, 252, 252); }")
        
        # 创建内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # 设置内容容器的最小宽度，确保内容不会被压缩
        content_widget.setMinimumWidth(280)
        
        # 新增：用户模式选择组
        mode_group = QGroupBox("用户模式选择")
        mode_layout = QHBoxLayout()
        
        self.doctor_checkbox = QCheckBox("医生端")
        self.patient_checkbox = QCheckBox("患者端")
        
        # 创建按钮组，确保只能选择一个
        self.mode_button_group = QButtonGroup()
        self.mode_button_group.addButton(self.doctor_checkbox)
        self.mode_button_group.addButton(self.patient_checkbox)
        self.mode_button_group.setExclusive(True)
        
        # 默认选择医生端
        self.doctor_checkbox.setChecked(True)
        
        # 连接信号
        self.doctor_checkbox.toggled.connect(self.on_mode_changed)
        self.patient_checkbox.toggled.connect(self.on_mode_changed)
        
        mode_layout.addWidget(self.doctor_checkbox)
        mode_layout.addWidget(self.patient_checkbox)
        mode_layout.addStretch()
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # 新增：脊柱类型选择器，插入到用户模式选择和串口设置之间
        self.spine_type_selector = SpineTypeSelector()
        layout.addWidget(self.spine_type_selector)
        
        # 串口设置组
        print("ControlPanel: 创建串口设置组...")
        serial_group = QGroupBox("串口设置")
        serial_layout = QGridLayout()
        
        # 数据源类型选择
        self.source_type_label = QLabel("数据源类型:")
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(["有线串口", "蓝牙串口"])
        self.source_type_combo.currentIndexChanged.connect(self.on_source_type_changed)
        
        # 端口选择
        self.port_label = QLabel("选择串口:")
        self.port_combo = QComboBox()
        
        # 刷新端口按钮
        self.refresh_port_btn = QPushButton("刷新")
        self.refresh_port_btn.clicked.connect(self.refresh_ports)
        
        # 波特率选择
        self.baud_label = QLabel("波特率:")
        self.baud_combo = QComboBox()
        baud_rates = ["9600", "19200", "38400", "57600", "115200"]
        self.baud_combo.addItems(baud_rates)
        self.baud_combo.setCurrentText("115200")
        
        # 传感器数量
        self.sensor_num_label = QLabel("传感器数量:")
        self.sensor_num_spin = QSpinBox()
        self.sensor_num_spin.setRange(1, 20)
        self.sensor_num_spin.setValue(6)  # 恢复默认值为7
        self.sensor_num_spin.valueChanged.connect(self.on_sensor_count_changed)  # 连接信号
        
        # 采集时间
        self.duration_label = QLabel("采集时长(秒):")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 3600)
        self.duration_spin.setValue(0)
        self.duration_spin.setSpecialValueText("无限制")
        
        # 添加到布局
        serial_layout.addWidget(self.source_type_label, 0, 0)
        serial_layout.addWidget(self.source_type_combo, 0, 1, 1, 2)
        serial_layout.addWidget(self.port_label, 1, 0)
        serial_layout.addWidget(self.port_combo, 1, 1)
        serial_layout.addWidget(self.refresh_port_btn, 1, 2)
        serial_layout.addWidget(self.baud_label, 2, 0)
        serial_layout.addWidget(self.baud_combo, 2, 1, 1, 2)
        serial_layout.addWidget(self.sensor_num_label, 3, 0)
        serial_layout.addWidget(self.sensor_num_spin, 3, 1, 1, 2)
        serial_layout.addWidget(self.duration_label, 4, 0)
        serial_layout.addWidget(self.duration_spin, 4, 1, 1, 2)
        
        serial_group.setLayout(serial_layout)
        layout.addWidget(serial_group)
        
        # 文件保存设置组 - 修改为两个文件路径
        print("ControlPanel: 创建文件保存设置组...")
        file_group = QGroupBox("文件保存设置")
        file_layout = QVBoxLayout()
        
        # 所有数据文件路径设置
        data_path_layout = QHBoxLayout()
        self.data_path_label = QLabel("所有数据文件路径:")
        self.data_path_edit = QLineEdit()
        self.data_path_edit.setReadOnly(True)
        self.data_path_edit.setPlaceholderText("保存时间戳和传感器数据")
        self.data_path_btn = QPushButton("选择路径")
        self.data_path_btn.clicked.connect(self.select_data_path)
        data_path_layout.addWidget(self.data_path_label)
        data_path_layout.addWidget(self.data_path_edit)
        data_path_layout.addWidget(self.data_path_btn)
        file_layout.addLayout(data_path_layout)
        
        # 事件数据文件路径设置
        events_path_layout = QHBoxLayout()
        self.events_path_label = QLabel("事件数据文件路径:")
        self.events_path_edit = QLineEdit()
        self.events_path_edit.setReadOnly(True)
        self.events_path_edit.setPlaceholderText("保存触发事件时的时间戳、事件名称和传感器数据")
        self.events_path_btn = QPushButton("选择路径")
        self.events_path_btn.clicked.connect(self.select_events_path)
        events_path_layout.addWidget(self.events_path_label)
        events_path_layout.addWidget(self.events_path_edit)
        events_path_layout.addWidget(self.events_path_btn)
        file_layout.addLayout(events_path_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 新增：UDP通信设置组
        print("ControlPanel: 创建UDP通信设置组...")
        udp_group = QGroupBox("脊柱数据UDP通信")
        udp_layout = QFormLayout(udp_group)
        
        self.udp_enable_cb = QCheckBox("启用UDP发送到Unity")
        self.udp_host_edit = QLineEdit("127.0.0.1")
        self.udp_port_edit = QLineEdit("6667")
        self.udp_port_edit.setValidator(QIntValidator(1, 65535))
        
        # 添加说明标签
        udp_info_label = QLabel("发送四个阶段的加权归一化值和误差范围")
        udp_info_label.setStyleSheet("color: #666; font-size: 10px;")
        
        udp_layout.addRow(self.udp_enable_cb)
        udp_layout.addRow("目标地址:", self.udp_host_edit)
        udp_layout.addRow("端口:", self.udp_port_edit)
        udp_layout.addRow(udp_info_label)
        
        # 连接UDP设置变更信号
        self.udp_enable_cb.stateChanged.connect(self.on_udp_settings_changed)
        self.udp_host_edit.textChanged.connect(self.on_udp_settings_changed)
        self.udp_port_edit.textChanged.connect(self.on_udp_settings_changed)
        
        layout.addWidget(udp_group)
        
        # 新增：卡尔曼滤波参数设置组
        print("ControlPanel: 创建卡尔曼滤波参数设置组...")
        filter_group = QGroupBox("卡尔曼滤波参数")
        filter_layout = QFormLayout(filter_group)
        
        self.filter_enable_cb = QCheckBox("启用卡尔曼滤波")
        self.filter_enable_cb.setChecked(True)  # 默认启用
        
        # 过程噪声设置
        self.process_noise_spin = QSpinBox()
        self.process_noise_spin.setRange(1, 1000)  # 0.001 - 1.0 (显示为1-1000)
        self.process_noise_spin.setValue(10)  # 默认0.01
        self.process_noise_spin.setSuffix(" (×0.001)")
        self.process_noise_spin.setToolTip("过程噪声：值越大滤波越平滑，但响应越慢")
        
        # 测量噪声设置
        self.measurement_noise_spin = QSpinBox()
        self.measurement_noise_spin.setRange(10, 10000)  # 0.01 - 10.0 (显示为10-10000)
        self.measurement_noise_spin.setValue(100)  # 默认0.1
        self.measurement_noise_spin.setSuffix(" (×0.001)")
        self.measurement_noise_spin.setToolTip("测量噪声：值越大越信任原始数据，滤波效果越弱")
        
        # 添加说明标签
        filter_info_label = QLabel("用于减少传感器数据噪声，提高数据质量")
        filter_info_label.setStyleSheet("color: #666; font-size: 10px;")
        
        filter_layout.addRow(self.filter_enable_cb)
        filter_layout.addRow("过程噪声:", self.process_noise_spin)
        filter_layout.addRow("测量噪声:", self.measurement_noise_spin)
        filter_layout.addRow(filter_info_label)
        
        # 连接滤波参数变更信号
        self.filter_enable_cb.stateChanged.connect(self.on_filter_params_changed)
        self.process_noise_spin.valueChanged.connect(self.on_filter_params_changed)
        self.measurement_noise_spin.valueChanged.connect(self.on_filter_params_changed)
        
        layout.addWidget(filter_group)
        
        # === 数据增强设置组 ===
        enhancement_group = QGroupBox("数据增强设置")
        enhancement_layout = QVBoxLayout(enhancement_group)
        self.enhancement_enable_cb = QCheckBox("启用数据增强")
        self.enhancement_enable_cb.setChecked(False)
        self.enhancement_method_combo = QComboBox()
        self.enhancement_method_combo.addItems([
            "运动检测和锁定", "趋势增强", "局部对比增强", "梯度加速度增强", "分段归一化增强"
        ])
        self.enhancement_param_stack = QStackedWidget()
        # 运动检测和锁定参数
        motion_group = QGroupBox()
        motion_layout = QFormLayout(motion_group)
        self.motion_diff_window_spin = QSpinBox(); self.motion_diff_window_spin.setRange(1, 50); self.motion_diff_window_spin.setValue(5)
        self.motion_thresh_spin = QDoubleSpinBox(); self.motion_thresh_spin.setRange(0.001, 1.0); self.motion_thresh_spin.setDecimals(3); self.motion_thresh_spin.setValue(0.015)
        self.motion_gain_spin = QDoubleSpinBox(); self.motion_gain_spin.setRange(0.1, 10.0); self.motion_gain_spin.setDecimals(2); self.motion_gain_spin.setValue(2.5)
        self.lock_smoothing_spin = QDoubleSpinBox(); self.lock_smoothing_spin.setRange(0.1, 0.99); self.lock_smoothing_spin.setDecimals(2); self.lock_smoothing_spin.setValue(0.95)
        motion_layout.addRow("差分窗口:", self.motion_diff_window_spin)
        motion_layout.addRow("运动阈值:", self.motion_thresh_spin)
        motion_layout.addRow("运动增益:", self.motion_gain_spin)
        motion_layout.addRow("锁定平滑:", self.lock_smoothing_spin)
        self.enhancement_param_stack.addWidget(motion_group)
        # 趋势增强参数
        trend_group = QGroupBox()
        trend_layout = QFormLayout(trend_group)
        self.trend_alpha_spin = QDoubleSpinBox(); self.trend_alpha_spin.setRange(0.1, 2.0); self.trend_alpha_spin.setDecimals(2); self.trend_alpha_spin.setValue(0.8)
        self.trend_gamma_spin = QDoubleSpinBox(); self.trend_gamma_spin.setRange(1.0, 5.0); self.trend_gamma_spin.setDecimals(2); self.trend_gamma_spin.setValue(3.0)
        trend_layout.addRow("Alpha参数:", self.trend_alpha_spin)
        trend_layout.addRow("Gamma参数:", self.trend_gamma_spin)
        self.enhancement_param_stack.addWidget(trend_group)
        # 局部对比增强参数
        local_group = QGroupBox()
        local_layout = QFormLayout(local_group)
        self.local_window_spin = QSpinBox(); self.local_window_spin.setRange(3, 51); self.local_window_spin.setSingleStep(2); self.local_window_spin.setValue(11)
        self.local_gain_spin = QDoubleSpinBox(); self.local_gain_spin.setRange(0.1, 5.0); self.local_gain_spin.setDecimals(2); self.local_gain_spin.setValue(2.0)
        local_layout.addRow("窗口大小:", self.local_window_spin)
        local_layout.addRow("增益系数:", self.local_gain_spin)
        self.enhancement_param_stack.addWidget(local_group)
        # 梯度加速度增强参数
        gradient_group = QGroupBox()
        gradient_layout = QFormLayout(gradient_group)
        self.gradient_alpha_spin = QDoubleSpinBox(); self.gradient_alpha_spin.setRange(0.1, 2.0); self.gradient_alpha_spin.setDecimals(2); self.gradient_alpha_spin.setValue(0.6)
        self.gradient_beta_spin = QDoubleSpinBox(); self.gradient_beta_spin.setRange(0.1, 2.0); self.gradient_beta_spin.setDecimals(2); self.gradient_beta_spin.setValue(0.4)
        gradient_layout.addRow("Alpha参数:", self.gradient_alpha_spin)
        gradient_layout.addRow("Beta参数:", self.gradient_beta_spin)
        self.enhancement_param_stack.addWidget(gradient_group)
        # 分段归一化增强参数
        segment_group = QGroupBox()
        segment_layout = QFormLayout(segment_group)
        self.segment_threshold_spin = QDoubleSpinBox(); self.segment_threshold_spin.setRange(0.001, 1.0); self.segment_threshold_spin.setDecimals(3); self.segment_threshold_spin.setValue(0.05)
        self.segment_scale_spin = QDoubleSpinBox(); self.segment_scale_spin.setRange(0.1, 10.0); self.segment_scale_spin.setDecimals(1); self.segment_scale_spin.setValue(2.0)
        segment_layout.addRow("阈值:", self.segment_threshold_spin)
        segment_layout.addRow("缩放系数:", self.segment_scale_spin)
        self.enhancement_param_stack.addWidget(segment_group)
        # 二次滤波设置
        self.second_filter_enable_cb = QCheckBox("启用二次滤波")
        self.second_filter_enable_cb.setChecked(True)
        self.second_filter_method_combo = QComboBox()
        self.second_filter_method_combo.addItems(["卡尔曼滤波", "Butterworth滤波", "Savitzky-Golay滤波"])
        self.second_filter_method_combo.setCurrentText("卡尔曼滤波")
        self.second_filter_param_stack = QStackedWidget()
        # 二次卡尔曼滤波参数
        second_kalman_group = QGroupBox()
        second_kalman_layout = QFormLayout(second_kalman_group)
        self.second_kalman_process_noise_spin = QDoubleSpinBox(); self.second_kalman_process_noise_spin.setRange(0.001, 1.0); self.second_kalman_process_noise_spin.setDecimals(3); self.second_kalman_process_noise_spin.setValue(0.001)
        self.second_kalman_measurement_noise_spin = QDoubleSpinBox(); self.second_kalman_measurement_noise_spin.setRange(0.01, 10.0); self.second_kalman_measurement_noise_spin.setDecimals(3); self.second_kalman_measurement_noise_spin.setValue(0.1)
        second_kalman_layout.addRow("过程噪声:", self.second_kalman_process_noise_spin)
        second_kalman_layout.addRow("测量噪声:", self.second_kalman_measurement_noise_spin)
        self.second_filter_param_stack.addWidget(second_kalman_group)
        # 二次Butterworth滤波参数
        second_butter_group = QGroupBox()
        second_butter_layout = QFormLayout(second_butter_group)
        self.second_butter_cutoff_spin = QDoubleSpinBox(); self.second_butter_cutoff_spin.setRange(0.01, 10.0); self.second_butter_cutoff_spin.setDecimals(2); self.second_butter_cutoff_spin.setValue(0.5)
        self.second_butter_fs_spin = QDoubleSpinBox(); self.second_butter_fs_spin.setRange(1.0, 1000.0); self.second_butter_fs_spin.setDecimals(1); self.second_butter_fs_spin.setValue(125.0)
        self.second_butter_order_spin = QSpinBox(); self.second_butter_order_spin.setRange(1, 10); self.second_butter_order_spin.setValue(4)
        second_butter_layout.addRow("截止频率:", self.second_butter_cutoff_spin)
        second_butter_layout.addRow("采样频率:", self.second_butter_fs_spin)
        second_butter_layout.addRow("阶数:", self.second_butter_order_spin)
        self.second_filter_param_stack.addWidget(second_butter_group)
        # 二次Savitzky-Golay滤波参数
        second_sg_group = QGroupBox()
        second_sg_layout = QFormLayout(second_sg_group)
        self.second_sg_window_spin = QSpinBox(); self.second_sg_window_spin.setRange(3, 51); self.second_sg_window_spin.setSingleStep(2); self.second_sg_window_spin.setValue(21)
        self.second_sg_poly_spin = QSpinBox(); self.second_sg_poly_spin.setRange(1, 5); self.second_sg_poly_spin.setValue(3)
        second_sg_layout.addRow("窗口长度:", self.second_sg_window_spin)
        second_sg_layout.addRow("多项式阶数:", self.second_sg_poly_spin)
        self.second_filter_param_stack.addWidget(second_sg_group)
        # 组合增强设置
        enhancement_layout.addWidget(self.enhancement_enable_cb)
        enhancement_layout.addWidget(self.enhancement_method_combo)
        enhancement_layout.addWidget(self.enhancement_param_stack)
        enhancement_layout.addWidget(self.second_filter_enable_cb)
        enhancement_layout.addWidget(self.second_filter_method_combo)
        enhancement_layout.addWidget(self.second_filter_param_stack)
        enhancement_group.setLayout(enhancement_layout)
        layout.addWidget(enhancement_group)
        # 信号连接
        self.enhancement_enable_cb.stateChanged.connect(self.on_enhancement_params_changed)
        self.enhancement_method_combo.currentIndexChanged.connect(self.on_enhancement_params_changed)
        self.motion_diff_window_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.motion_thresh_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.motion_gain_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.lock_smoothing_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.trend_alpha_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.trend_gamma_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.local_window_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.local_gain_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.gradient_alpha_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.gradient_beta_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.segment_threshold_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.segment_scale_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.second_filter_enable_cb.stateChanged.connect(self.on_enhancement_params_changed)
        self.second_filter_method_combo.currentIndexChanged.connect(self.on_enhancement_params_changed)
        self.second_kalman_process_noise_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.second_kalman_measurement_noise_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.second_butter_cutoff_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.second_butter_fs_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.second_butter_order_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.second_sg_window_spin.valueChanged.connect(self.on_enhancement_params_changed)
        self.second_sg_poly_spin.valueChanged.connect(self.on_enhancement_params_changed)
        # 切换增强方法时切换参数面板
        self.enhancement_method_combo.currentIndexChanged.connect(self.enhancement_param_stack.setCurrentIndex)
        self.second_filter_method_combo.currentIndexChanged.connect(self.second_filter_param_stack.setCurrentIndex)
        
        # 曲线可见性控制组
        print("ControlPanel: 创建曲线可见性控制组...")
        self.visibility_group = QGroupBox("曲线可见性")
        self.visibility_layout = QGridLayout()
        self.visibility_group.setLayout(self.visibility_layout)
        layout.addWidget(self.visibility_group)
        
        # 控制按钮组
        print("ControlPanel: 创建控制按钮组...")
        control_group = QGroupBox("控制")
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始采集")
        self.stop_btn = QPushButton("停止采集")
        self.stop_btn.setEnabled(False)
        
        self.start_btn.clicked.connect(self.start_acquisition)
        self.stop_btn.clicked.connect(self.stop_acquisition)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置内容容器为滚动区域的部件
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
        # 初始刷新串口列表
        print("ControlPanel: 初始刷新串口列表...")
        self.refresh_ports()
        print("ControlPanel: 布局创建完成")
        
    def on_mode_changed(self):
        """处理模式变更"""
        if self.doctor_checkbox.isChecked():
            self.mode_changed.emit("doctor")
            print("切换到医生端模式")
        elif self.patient_checkbox.isChecked():
            self.mode_changed.emit("patient")
            print("切换到患者端模式")
            
    def get_current_mode(self):
        """获取当前模式"""
        if self.doctor_checkbox.isChecked():
            return "doctor"
        elif self.patient_checkbox.isChecked():
            return "patient"
        return "doctor"  # 默认医生端
        
    def on_sensor_count_changed(self, count):
        """处理传感器数量变更"""
        self.sensor_count_changed.emit(count)
        print(f"传感器数量已更改为: {count}")
        
    def on_udp_settings_changed(self):
        """UDP设置变更处理"""
        enabled = self.udp_enable_cb.isChecked()
        host = self.udp_host_edit.text()
        try:
            port = int(self.udp_port_edit.text())
        except ValueError:
            port = 6667
        
        self.udp_settings_changed.emit(enabled, host, port)
    
    def on_filter_params_changed(self):
        """卡尔曼滤波参数变更处理"""
        # 获取当前滤波参数
        filter_params = self.get_filter_params()
        # 发送信号通知主窗口更新滤波器参数
        self.filter_params_changed.emit(filter_params)
    
    def get_filter_params(self):
        """获取卡尔曼滤波参数"""
        enabled = self.filter_enable_cb.isChecked()
        process_noise = self.process_noise_spin.value() / 1000.0  # 转换为实际值
        measurement_noise = self.measurement_noise_spin.value() / 1000.0  # 转换为实际值
        
        return {
            'enabled': enabled,
            'process_noise': process_noise,
            'measurement_noise': measurement_noise
        }
    
    def set_filter_params(self, enabled, process_noise, measurement_noise):
        """设置卡尔曼滤波参数"""
        self.filter_enable_cb.setChecked(enabled)
        self.process_noise_spin.setValue(int(process_noise * 1000))  # 转换为显示值
        self.measurement_noise_spin.setValue(int(measurement_noise * 1000))  # 转换为显示值
        
    def on_source_type_changed(self, index):
        """处理数据源类型变更"""
        print("ControlPanel: 处理数据源类型变更...")
        self.refresh_ports()
        print("ControlPanel: 数据源类型变更处理完成")
        
    def refresh_ports(self):
        """刷新可用串口列表"""
        self.port_combo.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("无可用串口")
    
    def select_data_path(self):
        """选择所有数据文件保存路径"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择所有数据文件保存路径", "", "CSV文件 (*.csv)"
        )
        if file_path:
            self.data_save_path = file_path
            self.data_path_edit.setText(file_path)
            self.data_path_changed.emit(file_path)
    
    def select_events_path(self):
        """选择事件数据文件保存路径"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择事件数据文件保存路径", "", "CSV文件 (*.csv)"
        )
        if file_path:
            self.events_save_path = file_path
            self.events_path_edit.setText(file_path)
            self.events_path_changed.emit(file_path)
    
    def get_data_save_path(self):
        """获取所有数据文件保存路径"""
        return self.data_path_edit.text()
    
    def get_events_save_path(self):
        """获取事件数据文件保存路径"""
        return self.events_path_edit.text()
    
    def get_udp_settings(self):
        """获取UDP设置"""
        return {
            'enabled': self.udp_enable_cb.isChecked(),
            'host': self.udp_host_edit.text(),
            'port': int(self.udp_port_edit.text()) if self.udp_port_edit.text().isdigit() else 6667
        }
    
    def start_acquisition(self):
        """开始数据采集"""
        if not self.is_acquisition_active:
            self.is_acquisition_active = True
            self.set_acquisition_active(True)
            self.acquisition_started.emit()
    
    def stop_acquisition(self):
        """停止数据采集"""
        if self.is_acquisition_active:
            self.is_acquisition_active = False
            self.set_acquisition_active(False)
            self.acquisition_stopped.emit()
    
    def get_port(self):
        """获取当前选择的串口"""
        return self.port_combo.currentText()
        
    def get_baud_rate(self):
        """获取当前选择的波特率"""
        return int(self.baud_combo.currentText())
        
    def get_num_sensors(self):
        """获取传感器数量"""
        return self.sensor_num_spin.value()
        
    def get_duration(self):
        """获取采集时长，如果为0则返回None（无限制）"""
        duration = self.duration_spin.value()
        return duration if duration > 0 else None
        
    def get_source_type(self):
        """获取数据源类型
        
        Returns:
            str: "serial" 或 "bluetooth"
        """
        source_type = self.source_type_combo.currentIndex()
        return "serial" if source_type == 0 else "bluetooth"
        
    def set_acquisition_active(self, active):
        """设置采集状态，更新按钮状态
        
        Args:
            active: 是否处于采集状态
        """
        self.start_btn.setEnabled(not active)
        self.stop_btn.setEnabled(active)
        
    def update_curve_visibility_controls(self, num_sensors, colors=None):
        """更新曲线可见性控制
        
        Args:
            num_sensors: 传感器数量
            colors: 颜色列表，如果为None则使用默认颜色
        """
        print("ControlPanel: 开始更新曲线可见性控制...")
        # 清除现有控件
        while self.visibility_layout.count():
            item = self.visibility_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 清除现有数据
        self.visibility_checkboxes = []
        self.color_buttons = []
        self.curve_labels = []
        
        # 默认颜色
        if colors is None:
            colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k'] * 3  # 循环使用这些颜色
        
        # 标题行
        self.visibility_layout.addWidget(QLabel("曲线"), 0, 0)
        self.visibility_layout.addWidget(QLabel("颜色"), 0, 1)
        self.visibility_layout.addWidget(QLabel("可见性"), 0, 2)
        self.visibility_layout.addWidget(QLabel("名称"), 0, 3)
        
        # 为每个传感器创建控制项
        for i in range(num_sensors):
            # 行号（从1开始，因为0行是表头）
            row = i + 1
            
            # 曲线编号
            self.visibility_layout.addWidget(QLabel(f"{i+1}"), row, 0)
            
            # 颜色按钮
            color_button = QPushButton()
            color_button.setFixedSize(20, 20)
            color_button.setStyleSheet(f"background-color: {self.color_to_css(colors[i % len(colors)])};")
            color_button.clicked.connect(lambda checked, idx=i: self.change_curve_color(idx))
            self.visibility_layout.addWidget(color_button, row, 1)
            self.color_buttons.append(color_button)
            
            # 可见性复选框
            visibility_check = QCheckBox()
            visibility_check.setChecked(True)
            visibility_check.stateChanged.connect(lambda state, idx=i: self.toggle_curve_visibility(idx, state))
            self.visibility_layout.addWidget(visibility_check, row, 2)
            self.visibility_checkboxes.append(visibility_check)
            
            # 曲线名称标签
            curve_name = QLineEdit(f"传感器 {i+1}")
            curve_name.textChanged.connect(lambda text, idx=i: self.change_curve_name(idx, text))
            self.visibility_layout.addWidget(curve_name, row, 3)
            self.curve_labels.append(curve_name)
        
        # 调整布局
        self.visibility_layout.setColumnStretch(3, 1)  # 让名称列可以伸展
        print("ControlPanel: 曲线可见性控制更新完成")
    
    def color_to_css(self, color):
        """将pyqtgraph颜色转换为CSS颜色"""
        color_map = {
            'r': 'red',
            'g': 'green',
            'b': 'blue',
            'c': 'cyan',
            'm': 'magenta',
            'y': 'yellow',
            'k': 'black'
        }
        return color_map.get(color, color)
        
    def change_curve_color(self, index):
        """更改曲线颜色"""
        color_dialog = QColorDialog(self)
        if color_dialog.exec_():
            color = color_dialog.selectedColor()
            
            # 更新按钮颜色
            self.color_buttons[index].setStyleSheet(f"background-color: {color.name()};")
            
            # 发送信号
            self.curve_color_changed.emit(index, color)
            
    def toggle_curve_visibility(self, index, state):
        """切换曲线可见性"""
        # 发送信号
        self.curve_visibility_changed.emit(index, state == Qt.Checked)
    
    def change_curve_name(self, index, text):
        """更新曲线名称"""
        # 发送信号
        self.curve_name_changed.emit(index, text)
        
    def get_curve_names(self):
        """获取所有曲线名称
        
        Returns:
            list: 曲线名称列表
        """
        return [label.text() for label in self.curve_labels]

    def on_enhancement_params_changed(self):
        params = self.get_enhancement_params()
        self.enhancement_params_changed.emit(params)

    def get_enhancement_params(self):
        enabled = self.enhancement_enable_cb.isChecked()
        method_idx = self.enhancement_method_combo.currentIndex()
        method_map = {
            0: 'motion_and_lock', 
            1: 'trend', 
            2: 'local_contrast', 
            3: 'gradient', 
            4: 'segment'
        }
        method = method_map.get(method_idx, 'motion_and_lock')
        enhancement_params = {}
        if method == 'motion_and_lock':
            enhancement_params = {
                'diff_window': self.motion_diff_window_spin.value(),
                'motion_thresh': self.motion_thresh_spin.value(),
                'motion_gain': self.motion_gain_spin.value(),
                'lock_smoothing': self.lock_smoothing_spin.value()
            }
        elif method == 'trend':
            enhancement_params = {
                'alpha': self.trend_alpha_spin.value(),
                'gamma': self.trend_gamma_spin.value()
            }
        elif method == 'local_contrast':
            enhancement_params = {
                'window_size': self.local_window_spin.value(),
                'gain': self.local_gain_spin.value()
            }
        elif method == 'gradient':
            enhancement_params = {
                'alpha': self.gradient_alpha_spin.value(),
                'beta': self.gradient_beta_spin.value()
            }
        elif method == 'segment':
            enhancement_params = {
                'threshold': self.segment_threshold_spin.value(),
                'scale': self.segment_scale_spin.value()
            }
        second_filter_enabled = self.second_filter_enable_cb.isChecked()
        second_filter_method_idx = self.second_filter_method_combo.currentIndex()
        second_filter_method_map = {0: 'kalman', 1: 'butterworth', 2: 'savitzky_golay'}
        second_filter_method = second_filter_method_map.get(second_filter_method_idx, 'kalman')
        second_filter_params = {}
        if second_filter_method == 'kalman':
            second_filter_params = {
                'process_noise': self.second_kalman_process_noise_spin.value(),
                'measurement_noise': self.second_kalman_measurement_noise_spin.value()
            }
        elif second_filter_method == 'butterworth':
            second_filter_params = {
                'cutoff_freq': self.second_butter_cutoff_spin.value(),
                'fs': self.second_butter_fs_spin.value(),
                'order': self.second_butter_order_spin.value(),
                'btype': 'low'
            }
        elif second_filter_method == 'savitzky_golay':
            second_filter_params = {
                'window_size': self.second_sg_window_spin.value(),
                'order': self.second_sg_poly_spin.value()
            }
        return {
            'enabled': enabled,
            'method': method,
            'enhancement_params': enhancement_params,
            'second_filter': {
                'enabled': second_filter_enabled,
                'method': second_filter_method,
                'params': second_filter_params
            }
        }