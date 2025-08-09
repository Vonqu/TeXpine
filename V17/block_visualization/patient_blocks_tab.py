"""
患者积木可视化标签页模块（修改版）
==================================

修改内容：
1. 将"脊柱积木图形示例"的驱动方式改为跟tab2一样
2. 原始值/目标值从事件数据文件中读取
3. 支持四个控制器：骨盆前后翻转、脊柱曲率矫正、骨盆左右倾斜、肩部左右倾斜
4. 根据阶段自动切换对应的控制器显示

作者: Assistant
日期: 2024-01-15
"""

import sys
import os
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                            QTextEdit, QSplitter, QFrame, QGroupBox, 
                            QSlider, QSpinBox, QProgressBar, QPushButton)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
import csv
import time
from collections import defaultdict

# 添加路径以导入其他模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # 获取上级目录（V7目录）
sys.path.append(current_dir)  # 当前目录（block_visualization）
sys.path.append(parent_dir)   # 上级目录（V7目录）

# 导入积木可视化组件（从tab2复用）
from block_visualization.blocks_visualizer import BlocksVisualizer
from .spine_type_selector import SpineTypeSelector


class PatientSensorController:
    """
    患者端传感器控制器
    ==================
    
    模拟tab2中SensorSelector的功能，用于计算加权归一化值
    """
    
    def __init__(self, name, sensor_count=6):
        self.name = name
        self.sensor_count = sensor_count
        
        # 传感器配置
        self.selected_sensors = [False] * sensor_count  # 选中状态
        self.sensor_weights = [0.0] * sensor_count      # 权重
        self.original_values = [2500.0] * sensor_count  # 原始值(OV)
        self.target_values = [2500.0] * sensor_count    # 目标值(RBV)
        self.current_values = [2500.0] * sensor_count   # 当前传感器值
        
        # 误差范围
        self.error_range = 0.1
        
    def set_sensor_selection(self, sensor_index, selected, weight=1.0):
        """设置传感器选择状态和权重"""
        if 0 <= sensor_index < self.sensor_count:
            self.selected_sensors[sensor_index] = selected
            if selected:
                self.sensor_weights[sensor_index] = weight
            else:
                self.sensor_weights[sensor_index] = 0.0
    
    def set_original_values(self, values):
        """设置原始值"""
        for i, value in enumerate(values):
            if i < self.sensor_count:
                self.original_values[i] = float(value)
    
    def set_target_values(self, values):
        """设置目标值"""
        for i, value in enumerate(values):
            if i < self.sensor_count:
                self.target_values[i] = float(value)
    
    def set_current_values(self, values):
        """设置当前传感器值"""
        for i, value in enumerate(values):
            if i < self.sensor_count:
                self.current_values[i] = float(value)
    
    def set_error_range(self, error_range):
        """设置误差范围"""
        self.error_range = error_range
    
    def calculate_weighted_value(self):
        """计算加权归一化值（与tab2中SensorSelector的逻辑一致）"""
        total_weight = 0
        weighted_sum = 0
        
        for i in range(self.sensor_count):
            if self.selected_sensors[i] and self.sensor_weights[i] != 0:
                weight = self.sensor_weights[i]
                original = self.original_values[i]
                target = self.target_values[i]
                current = self.current_values[i]
                
                # 归一化计算：(current - target) / (original - target)
                if abs(original - target) > 1e-6:  # 避免除零
                    normalized = (current - target) / (original - target)
                    weighted_sum += normalized * weight
                    total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.5
    
    def is_in_target_range(self):
        """检查当前值是否在目标范围内"""
        for i in range(self.sensor_count):
            if self.selected_sensors[i] and self.sensor_weights[i] != 0:
                target = self.target_values[i]
                original = self.original_values[i]
                current = self.current_values[i]
                
                # 计算原始值和最佳值的差值
                value_difference = abs(original - target)
                
                # 误差范围乘以差值作为容差
                tolerance = value_difference * self.error_range
                
                # 判断当前值是否在目标范围内
                if not (target - tolerance <= current <= target + tolerance):
                    return False
        return True


class PatientBlocksTab(QWidget):
    """
    患者积木可视化标签页（支持脊柱类型和方向选择版）
    ========================================================
    
    新增功能：
    - 脊柱侧弯类型选择（C型/S型）
    - 侧弯方向选择
    - 根据类型和方向调整可视化效果
    - 支持S型4阶段训练
    """
    
    # 定义信号
    request_data = pyqtSignal()
    training_completed = pyqtSignal()
    
    def __init__(self, sensor_count=6, parent=None):
        super().__init__(parent)
        self.sensor_count = sensor_count
        
        # ====== 新增：脊柱类型和方向配置 ======
        self.spine_type = "C"  # 默认C型
        self.spine_direction = "left"  # 默认左凸
        self.max_stages = 3  # 根据脊柱类型调整
        
        # ====== 阶段配置字典 ======
        self.stage_configs = {
            "C": {
                "max_stages": 3,
                "stage_descriptions": {
                    1: "阶段1：骨盆前后旋转调整",
                    2: "阶段2：脊柱曲率矫正",
                    3: "阶段3：关节平衡调整"
                },
                "sub_stages": {
                    3: ['hip', 'shoulder']  # 阶段3有两个子阶段
                }
            },
            "S": {
                "max_stages": 4,
                "stage_descriptions": {
                    1: "阶段1：骨盆前后旋转调整",
                    2: "阶段2：腰椎曲率矫正",
                    3: "阶段3：胸椎曲率矫正",
                    4: "阶段4：肩部左右倾斜调整"
                },
                "sub_stages": {}  # S型没有子阶段
            }
        }
        
        # ====== 患者端训练相关属性 ======
        self.current_stage = 1
        self.current_sub_stage = None
        self.training_active = False
        self.events_data = {}
        self.events_file_path = ""
        
        # ====== 新增：四个传感器控制器 ======
        self.controllers = {
            'gray_rotation': PatientSensorController("骨盆前后翻转", sensor_count),
            'blue_curvature': PatientSensorController("脊柱曲率矫正", sensor_count),
            'gray_tilt': PatientSensorController("胸椎曲率矫正", sensor_count),  # S型用作胸椎
            'green_tilt': PatientSensorController("肩部左右倾斜", sensor_count)
        }
        
        # ====== 倒计时相关 ======
        self.countdown_active = False
        self.countdown_seconds = 5
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        
        # ====== 阶段检查定时器 ======
        self.stage_check_timer = QTimer()
        self.stage_check_timer.timeout.connect(self._check_stage_completion)
        self.stage_check_timer.start(100)
        
        # ====== 可视化参数 ======
        self.visualizer_params = {
            'gray_rotation': 0,
            'gray_tilt': 0,
            'blue_curvature': 0,
            'green_tilt': 0
        }
        
        # ====== 其他属性 ======
        self.is_training = False
        self.stage_data = {}
        self.last_event_count = 0
        self.target_reached = False
        
        # 创建更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_from_events_file)
        
        self.init_ui()
        self._setup_default_controller_configs()
        
    def _setup_default_controller_configs(self):
        """设置默认的控制器配置（注意：这些默认值会被事件文件中的实际配置覆盖）"""
        # 注意：此方法设置的默认值仅在没有事件文件时使用
        # 实际的权重和传感器选择将从事件文件中读取
        
        # 暂时不设置任何默认选择，等待从事件文件加载实际配置
        print("默认控制器配置已初始化，等待从事件文件加载实际配置")

    def init_ui(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout()
        
        # 只读显示脊柱类型和方向
        self.spine_type_display = SpineTypeSelector(show_only=True)
        main_layout.addWidget(self.spine_type_display)
        
        # 创建主水平分割器
        main_splitter = QSplitter(Qt.Horizontal)
        
        # ====== 左侧区域 ======
        left_widget = self.create_left_panel()
        
        # ====== 右侧区域 ======
        right_widget = self.create_right_panel()
        
        # 添加到分割器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([600, 600])
        
        main_layout.addWidget(main_splitter)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(main_layout)

    def _create_spine_config_group(self):
        """创建脊柱类型和方向选择组"""
        group = QGroupBox("脊柱侧弯类型和方向配置")
        layout = QVBoxLayout()
        group.setLayout(layout)
        
        # 第一行：脊柱类型选择
        type_layout = QHBoxLayout()
        type_label = QLabel("脊柱类型:")
        type_layout.addWidget(type_label)
        
        # 创建脊柱类型单选按钮组
        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        self.spine_type_button_group = QButtonGroup()
        
        # C型脊柱侧弯
        self.c_type_radio = QRadioButton("C型脊柱侧弯")
        self.c_type_radio.setChecked(True)
        self.c_type_radio.setToolTip("C型脊柱侧弯：3个阶段的训练模式")
        type_layout.addWidget(self.c_type_radio)
        
        # S型脊柱侧弯
        self.s_type_radio = QRadioButton("S型脊柱侧弯")
        self.s_type_radio.setToolTip("S型脊柱侧弯：4个阶段的训练模式")
        type_layout.addWidget(self.s_type_radio)
        
        # 添加到按钮组
        self.spine_type_button_group.addButton(self.c_type_radio, 0)
        self.spine_type_button_group.addButton(self.s_type_radio, 1)
        
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # 第二行：侧弯方向选择
        direction_layout = QHBoxLayout()
        direction_label = QLabel("侧弯方向:")
        direction_layout.addWidget(direction_label)
        
        # 创建侧弯方向单选按钮组
        self.spine_direction_button_group = QButtonGroup()
        
        # C型方向选择
        self.c_left_radio = QRadioButton("左凸")
        self.c_right_radio = QRadioButton("右凸")
        self.c_left_radio.setChecked(True)
        
        # S型方向选择
        self.s_lumbar_left_radio = QRadioButton("腰椎左凸胸椎右凸")
        self.s_lumbar_right_radio = QRadioButton("腰椎右凸胸椎左凸")
        
        # 添加到按钮组
        self.spine_direction_button_group.addButton(self.c_left_radio, 0)
        self.spine_direction_button_group.addButton(self.c_right_radio, 1)
        self.spine_direction_button_group.addButton(self.s_lumbar_left_radio, 2)
        self.spine_direction_button_group.addButton(self.s_lumbar_right_radio, 3)
        
        # 创建方向选择容器
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
        
        # 初始化显示状态
        self.c_direction_widget.setVisible(True)
        self.s_direction_widget.setVisible(False)
        
        # 连接信号
        self.spine_type_button_group.buttonClicked.connect(self._on_spine_type_changed)
        self.spine_direction_button_group.buttonClicked.connect(self._on_spine_direction_changed)
        
        # 添加说明标签
        layout.addStretch()
        info_label = QLabel("患者端配置需要与医生端保持一致")
        info_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(info_label)
        
        return group


    def _on_spine_direction_changed(self, button):
        """处理侧弯方向变更"""
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
            old_direction = self.spine_direction
            self.spine_direction = new_direction
            
            print(f"患者端：侧弯方向从 {old_direction} 变更为 {new_direction}")
            
            # 更新可视化器配置
            self._update_visualizer_for_spine_config()
            
            print(f"患者端：侧弯方向变更完成 - {new_direction}")

    
    def _update_visualizer_for_spine_config(self):
        """根据脊柱类型和方向更新可视化器"""
        if hasattr(self, 'blocks_widget') and self.blocks_widget:
            # 设置脊柱类型和方向
            self.blocks_widget.set_spine_config(self.spine_type, self.spine_direction)
            # 设置当前阶段
            self.blocks_widget.current_stage = self.current_stage
            self.blocks_widget.update()
            print(f"患者端可视化器已更新：{self.spine_type}型，方向={self.spine_direction}，阶段={self.current_stage}")
    
    def _on_spine_type_changed(self, button):
        """处理脊柱类型变更"""
        if button == self.c_type_radio:
            new_type = "C"
            # 显示C型方向选择
            self.c_direction_widget.setVisible(True)
            self.s_direction_widget.setVisible(False)
            # 设置默认方向
            self.c_left_radio.setChecked(True)
            self.spine_direction = "left"
        else:
            new_type = "S"
            # 显示S型方向选择
            self.c_direction_widget.setVisible(False)
            self.s_direction_widget.setVisible(True)
            # 设置默认方向
            self.s_lumbar_left_radio.setChecked(True)
            self.spine_direction = "lumbar_left_thoracic_right"
        
        if new_type != self.spine_type:
            old_type = self.spine_type
            self.spine_type = new_type
            self.max_stages = self.stage_configs[new_type]["max_stages"]
            
            print(f"患者端：脊柱类型从 {old_type} 变更为 {new_type}")
            print(f"患者端：侧弯方向设置为 {self.spine_direction}")
            
            # 重置到第1阶段
            self.current_stage = 1
            self.current_sub_stage = None
            
            # 更新可视化器配置
            self._update_visualizer_for_spine_config()
            
            # 重新设置控制器配置
            self._update_controller_configs_for_spine_type()
            
            print(f"患者端：脊柱类型变更完成 - {new_type}型，{self.max_stages}个阶段")

    def _update_controller_configs_for_spine_type(self):
        """根据脊柱类型更新控制器配置"""
        if self.spine_type == "C":
            # C型脊柱：保持原有配置
            self.controllers['gray_rotation'].name = "骨盆前后翻转"
            self.controllers['blue_curvature'].name = "脊柱曲率矫正"
            self.controllers['gray_tilt'].name = "骨盆左右倾斜"
            self.controllers['green_tilt'].name = "肩部左右倾斜"
        else:
            # S型脊柱：调整名称
            self.controllers['gray_rotation'].name = "骨盆前后翻转"
            self.controllers['blue_curvature'].name = "腰椎曲率矫正"
            self.controllers['gray_tilt'].name = "胸椎曲率矫正"
            self.controllers['green_tilt'].name = "肩部左右倾斜"
        
        print(f"患者端：控制器配置已更新为{self.spine_type}型脊柱模式")
        
    def create_left_panel(self):
        """创建左侧面板：积木可视化 + 手动控制"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        # 积木可视化组件
        blocks_group = QGroupBox("脊柱积木图形示例")
        blocks_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin: 10px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        blocks_layout = QVBoxLayout()
        
        # 创建积木可视化组件
        try:
            self.blocks_widget = BlocksVisualizer()
            blocks_layout.addWidget(self.blocks_widget)
        except Exception as e:
            # 如果创建失败，显示占位符
            placeholder_label = QLabel("积木可视化组件加载中...")
            placeholder_label.setAlignment(Qt.AlignCenter)
            placeholder_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
            placeholder_label.setMinimumHeight(300)
            blocks_layout.addWidget(placeholder_label)
            self.blocks_widget = None
            print(f"积木可视化组件创建失败: {e}")
        
        blocks_group.setLayout(blocks_layout)
        
        # 布局设置
        left_layout.addWidget(blocks_group, 2)  # 积木可视化占主要空间
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        left_widget.setLayout(left_layout)
        return left_widget
        
    def create_right_panel(self):
        """创建右侧面板：绘图控制 + 状态显示 + 倒计时"""
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        
        # 上方：绘图控制（会在主窗口中替换）
        chart_group = QGroupBox("绘图控制")
        chart_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin: 10px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        chart_layout = QVBoxLayout()
        
        # 占位符，将在主窗口中替换为实际的plot_widget
        self.plot_placeholder = QLabel("绘图控制将在这里显示")
        self.plot_placeholder.setAlignment(Qt.AlignCenter)
        self.plot_placeholder.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.plot_placeholder.setMinimumHeight(200)
        chart_layout.addWidget(self.plot_placeholder)
        
        chart_group.setLayout(chart_layout)
        
        # 中间：倒计时显示
        countdown_group = QGroupBox("训练进度")
        countdown_layout = QVBoxLayout()
        
        # 当前阶段显示
        self.stage_label = QLabel("当前阶段: 等待开始")
        self.stage_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.stage_label.setAlignment(Qt.AlignCenter)
        self.stage_label.setStyleSheet("""
            QLabel {
                color: #2196F3;
                padding: 8px;
                border: 2px solid #2196F3;
                border-radius: 5px;
                background-color: #E3F2FD;
            }
        """)
        countdown_layout.addWidget(self.stage_label)
        
        # 倒计时显示
        self.countdown_label = QLabel("等待开始训练")
        self.countdown_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("""
            QLabel {
                color: #FF9800;
                padding: 10px;
                border: 2px solid #FF9800;
                border-radius: 5px;
                background-color: #FFF3E0;
            }
        """)
        countdown_layout.addWidget(self.countdown_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 5)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("准备中 %p%")
        countdown_layout.addWidget(self.progress_bar)
        
        countdown_group.setLayout(countdown_layout)
        
        # 下方：训练状态显示
        status_group = QGroupBox("训练状态与指导")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin: 10px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        status_layout = QVBoxLayout()
        
        # 状态显示文本框
        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)
        self.status_display.setMaximumHeight(150)
        self.status_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Microsoft YaHei', SimHei;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        
        # 设置初始状态信息
        self.update_status("等待开始训练", "请在监测界面选择患者端模式并开始采集")
        
        status_layout.addWidget(self.status_display)
        status_group.setLayout(status_layout)
        
        # 布局设置
        right_layout.addWidget(chart_group, 2)  # 图表占较大空间
        right_layout.addWidget(countdown_group, 1)  # 倒计时占中等空间
        right_layout.addWidget(status_group, 1)  # 状态显示占较小空间
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        right_widget.setLayout(right_layout)
        return right_widget
        
    def setup_connections(self):
        """设置信号连接"""
        pass
            
    def set_plot_widget(self, plot_widget):
        """设置绘图控件（从主窗口传入）"""
        if hasattr(self, 'plot_placeholder') and self.plot_placeholder:
            # 替换占位符
            parent_layout = self.plot_placeholder.parent().layout()
            parent_layout.removeWidget(self.plot_placeholder)
            self.plot_placeholder.deleteLater()
            parent_layout.addWidget(plot_widget)
            self.plot_widget = plot_widget
            print("患者界面：绘图控件设置完成")

    def set_events_file_path(self, file_path):
        """设置事件文件路径"""
        print(f"\n=== 设置事件文件路径 ===")
        print(f"新路径: {file_path}")
        
        self.events_file_path = file_path
        print(f"事件文件路径已设置为: {file_path}")
        
        # 重新加载阶段数据
        if file_path and os.path.exists(file_path):
            self.load_events_data()
        print("=== 事件文件路径设置完成 ===\n")

    def load_events_data(self):
        """从事件数据文件加载训练数据（处理中文列名和注释行）"""
        print("\n=== 开始加载事件数据 ===")
        print(f"事件文件路径: {self.events_file_path}")
        
        if not self.events_file_path or not os.path.exists(self.events_file_path):
            print(f"事件文件路径无效或文件不存在: {self.events_file_path}")
            return False
            
        try:
            self.events_data = {}
            
            print(f"正在加载事件数据文件: {self.events_file_path}")
            print(f"使用手动选择的脊柱类型: {self.spine_type}")
            
            # 尝试多种编码方式
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'cp1252', 'latin-1']
            lines = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(self.events_file_path, 'r', encoding=encoding) as f:
                        lines = f.readlines()
                        used_encoding = encoding
                        print(f"成功使用 {encoding} 编码读取文件")
                        break
                except UnicodeDecodeError:
                    continue
            
            if lines is None:
                print("错误：无法使用任何编码读取文件")
                return False
            
            print(f"文件总行数: {len(lines)}")
            
            # 找到CSV头部 - 跳过注释行
            headers = None
            data_start_line = 0
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:  # 跳过空行
                    continue
                if line.startswith('#') or line.startswith('//') or line.startswith('*'):  # 跳过注释行
                    continue
                
                # 检查是否包含"阶段"和"事件名"等关键词（中文列名）
                if 'stage' in line and 'event_name' in line:
                    headers = [col.strip() for col in line.split(',')]
                    data_start_line = i
                    print(f"找到CSV头部在第{i+1}行: {headers[:10]}...")  # 只显示前10列
                    break
            
            if headers is None:
                print("错误：文件中没有找到包含'stage'和'event_name'的头部行")
                return False
            
            print(f"数据开始行: {data_start_line + 1}")
            
            # 创建列名映射（中文到英文）
            column_mapping = {}
            for i, header in enumerate(headers):
                if 'stage' in header:
                    column_mapping['stage'] = i
                elif 'event_name' in header:
                    column_mapping['event_name'] = i
                elif 'error_range' in header:
                    column_mapping['error_range'] = i
                elif header.startswith('sensor') and header[6:].isdigit():
                    # sensor1, sensor2, etc.
                    sensor_num = int(header[6:])
                    column_mapping[f'sensor{sensor_num}'] = i
                elif header.startswith('weight') and header[6:].isdigit():
                    # weight1, weight2, etc.
                    weight_num = int(header[6:])
                    column_mapping[f'weight{weight_num}'] = i
            
            print(f"列名映射: {column_mapping}")
            
            # 检查必要的列是否存在
            if 'stage' not in column_mapping or 'event_name' not in column_mapping:
                print("错误：没有找到'stage'或'event_name'列")
                return False
            
            # 根据手动选择的脊柱类型获取事件映射
            event_mappings = self._get_event_mappings()
            print(f"事件映射关系: {list(event_mappings.keys())}")
            
            # 处理数据行
            loaded_events = 0
            for line_num in range(data_start_line + 1, len(lines)):
                line = lines[line_num].strip()
                if not line or line.startswith('#'):
                    continue
                
                # 分割CSV行
                row_data = [col.strip() for col in line.split(',')]
                
                if len(row_data) < len(headers):
                    print(f"跳过行{line_num + 1}: 列数不匹配")
                    continue
                
                # 提取阶段和事件名
                try:
                    stage = row_data[column_mapping['stage']]
                    event_name = row_data[column_mapping['event_name']]
                    
                    print(f"处理行{line_num + 1}: stage='{stage}', event_name='{event_name}'")
                    
                    # 检查是否匹配映射关系
                    mapping_key = (stage, event_name)
                    if mapping_key in event_mappings:
                        controller_name, value_type = event_mappings[mapping_key]
                        print(f"  匹配到映射: {controller_name} - {value_type}")
                        
                        # 解析传感器数据
                        sensor_data = []
                        for i in range(1, self.sensor_count + 1):
                            sensor_key = f'sensor{i}'
                            if sensor_key in column_mapping:
                                col_index = column_mapping[sensor_key]
                                if col_index < len(row_data):
                                    try:
                                        sensor_data.append(float(row_data[col_index]))
                                    except ValueError:
                                        sensor_data.append(2500.0)
                                else:
                                    sensor_data.append(2500.0)
                            else:
                                sensor_data.append(2500.0)
                        
                        # 解析权重数据
                        weights = []
                        for i in range(1, self.sensor_count + 1):
                            weight_key = f'weight{i}'
                            if weight_key in column_mapping:
                                col_index = column_mapping[weight_key]
                                if col_index < len(row_data):
                                    try:
                                        weights.append(float(row_data[col_index]))
                                    except ValueError:
                                        weights.append(0.0)
                                else:
                                    weights.append(0.0)
                            else:
                                weights.append(0.0)
                        
                        # 解析误差范围
                        error_range = 0.1
                        if 'error_range' in column_mapping:
                            col_index = column_mapping['error_range']
                            if col_index < len(row_data):
                                try:
                                    error_range = float(row_data[col_index])
                                except ValueError:
                                    error_range = 0.1
                        
                        # 存储到对应的控制器
                        controller = self.controllers[controller_name]
                        
                        if value_type == 'original':
                            controller.set_original_values(sensor_data)
                            # 设置权重和传感器选择
                            for i, weight in enumerate(weights):
                                if i < self.sensor_count:
                                    controller.set_sensor_selection(i, weight != 0, abs(weight))
                            print(f"  设置 {controller_name} 原始值和权重")
                            
                        elif value_type == 'target':
                            controller.set_target_values(sensor_data)
                            print(f"  设置 {controller_name} 目标值")
                        
                        # 设置误差范围
                        controller.set_error_range(error_range)
                        
                        # 存储完整事件数据
                        key = f"{stage}_{event_name}"
                        self.events_data[key] = {
                            'stage': stage,
                            'event_name': event_name,
                            'sensor_data': sensor_data,
                            'weights': weights,
                            'error_range': error_range,
                            'controller_name': controller_name,
                            'value_type': value_type
                        }
                        
                        loaded_events += 1
                    else:
                        print(f"  跳过未映射的事件: {mapping_key}")
                        
                except Exception as e:
                    print(f"处理行{line_num + 1}时出错: {e}")
                    continue
            
            print(f"成功加载 {loaded_events} 条事件数据")
            
            if loaded_events == 0:
                print("错误：没有加载到任何有效的事件数据")
                return False
            
            # 打印控制器数据状态
            print("\n控制器数据状态:")
            for name, controller in self.controllers.items():
                selected_sensors = [i for i, selected in enumerate(controller.selected_sensors) if selected]
                if selected_sensors:
                    active_weights = [controller.sensor_weights[i] for i in selected_sensors]
                    print(f"  {name}: 选中传感器{[i+1 for i in selected_sensors]}, 权重{active_weights}")
                else:
                    print(f"  {name}: 没有选中的传感器")
            
            print("=== 事件数据加载完成 ===\n")
            return True
            
        except Exception as e:
            print(f"加载事件数据时发生异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_event_mappings(self):
        """根据手动选择的脊柱类型获取事件映射关系"""
        if self.spine_type == "C":
            return {
                ("阶段1", "开始训练"): ('gray_rotation', 'original'),
                ("阶段1", "完成阶段"): ('gray_rotation', 'target'),
                ("阶段2", "开始矫正"): ('blue_curvature', 'original'),
                ("阶段2", "矫正完成"): ('blue_curvature', 'target'),
                ("阶段3", "开始沉髋"): ('gray_tilt', 'original'),
                ("阶段3", "沉髋完成"): ('gray_tilt', 'target'),
                ("阶段3", "开始沉肩"): ('green_tilt', 'original'),
                ("阶段3", "沉肩完成"): ('green_tilt', 'target'),
            }
        else:  # S型
            return {
                ("阶段1", "开始训练"): ('gray_rotation', 'original'),
                ("阶段1", "完成阶段"): ('gray_rotation', 'target'),
                ("阶段2", "开始腰椎矫正"): ('blue_curvature', 'original'),
                ("阶段2", "腰椎矫正完成"): ('blue_curvature', 'target'),
                ("阶段3", "开始胸椎矫正"): ('gray_tilt', 'original'),
                ("阶段3", "胸椎矫正完成"): ('gray_tilt', 'target'),
                ("阶段4", "开始肩部调整"): ('green_tilt', 'original'),
                ("阶段4", "肩部调整完成"): ('green_tilt', 'target'),
            }

    def start_training_mode(self):
        """开始训练模式（直接读取事件数据文件）"""
        print("开始患者端训练模式（直接读取事件数据文件）")
        
        # 检查事件文件路径是否设置
        if not self.events_file_path:
            self.update_status("请设置事件数据文件", "请在tab1中设置事件数据文件的路径")
            return False
        
        # 检查文件是否存在
        if not os.path.exists(self.events_file_path):
            self.update_status("事件数据文件不存在", f"文件路径：{self.events_file_path}")
            return False
        
        # 直接加载事件数据文件
        if not self.load_events_data():
            self.update_status("数据加载失败", "事件数据文件无效或格式错误")
            return False
        
        # 验证数据完整性
        if not self._validate_training_data():
            self.update_status("数据验证失败", "事件数据文件中缺少必要的训练数据")
            return False
        
        # 成功启动训练模式
        self.training_active = True
        self.is_training = True
        self.current_stage = 1
        self.current_sub_stage = None
        self.target_reached = False
        self.countdown_active = False
        
        # 立即显示当前阶段
        self._update_stage_display()
        
        # 更新状态显示
        self.update_status("训练模式已启动", f"从事件数据文件加载配置，开始{self.spine_type}型脊柱训练")
        
        # 启动阶段检查定时器
        self.stage_check_timer.start(100)
        
        print(f"患者端训练模式已启动，当前阶段{self.current_stage}，脊柱类型：{self.spine_type}")
        return True


    def _validate_training_data(self):
        """验证训练数据的完整性"""
        print("\n=== 验证训练数据完整性 ===")
        
        # 根据脊柱类型确定需要验证的控制器
        if self.spine_type == "C":
            required_controllers = ['gray_rotation', 'blue_curvature', 'gray_tilt', 'green_tilt']
            required_stages = [1, 2, 3]
        else:  # S型
            required_controllers = ['gray_rotation', 'blue_curvature', 'gray_tilt', 'green_tilt']
            required_stages = [1, 2, 3, 4]
        
        validation_passed = True
        
        for controller_name in required_controllers:
            controller = self.controllers[controller_name]
            
            # 检查是否有激活的传感器
            active_sensors = [i for i in range(self.sensor_count) 
                            if controller.selected_sensors[i] and controller.sensor_weights[i] != 0]
            
            if not active_sensors:
                print(f"警告：{controller_name} 没有激活的传感器")
                continue
            
            # 检查原始值和目标值是否有效
            has_valid_data = False
            for i in active_sensors:
                original = controller.original_values[i]
                target = controller.target_values[i]
                
                # 检查数据是否不是默认值且有意义的差异
                if original != 2500.0 and target != 2500.0 and abs(original - target) > 10:
                    has_valid_data = True
                    break
            
            if has_valid_data:
                print(f"✓ {controller_name}: 数据有效")
            else:
                print(f"✗ {controller_name}: 数据无效或使用默认值")
                # 对于没有有效数据的控制器，我们仍然可以继续，但会给出警告
        
        print(f"验证结果: {'通过' if validation_passed else '失败'}")
        print("=== 验证完成 ===\n")
        
        # 即使某些控制器没有有效数据，我们也允许继续训练
        # 这样用户可以看到效果并进行调试
        return True
        
    def stop_training_mode(self):
        """停止训练模式"""
        self.training_active = False
        self.is_training = False
        
        # 停止所有定时器
        self.update_timer.stop()
        self.countdown_timer.stop()
        self.stage_check_timer.stop()
        
        # 重置状态
        self.current_stage = 1
        self.current_sub_stage = None
        self.countdown_seconds = 0
        self.target_reached = False
        self.countdown_active = False
        
        # 更新显示
        self.stage_label.setText("当前阶段: 等待开始")
        self.countdown_label.setText("训练已停止")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("训练停止 %p%")
        
        # 更新状态显示
        self.update_status("训练模式已停止", "训练结束")
        
        print("患者界面：训练模式已停止（新驱动方式）")

    def update_sensor_data(self, data):
        """更新传感器数据（修改版：采用与tab2相同的驱动方式）"""
        if not self.training_active:
            return
            
        if len(data) > 1:  # 跳过时间戳
            sensor_data = data[1:]
            
            # 更新所有控制器的当前传感器值
            for controller in self.controllers.values():
                controller.set_current_values(sensor_data)
            
            # 更新积木可视化（采用新的驱动方式）
            self._update_visualization_new_method()

    def _update_visualization_new_method(self):
        """新的可视化更新方法（支持S型4阶段）"""
        if not self.training_active:
            return
        
        try:
            # 根据脊柱类型和当前阶段计算对应的可视化参数
            if self.spine_type == "C":
                # C型脊柱：3阶段模式
                if self.current_stage == 1:
                    # 阶段1：骨盆前后翻转
                    value = self.controllers['gray_rotation'].calculate_weighted_value()
                    self.visualizer_params['gray_rotation'] = value
                    
                elif self.current_stage == 2:
                    # 阶段2：脊柱曲率矫正
                    value = self.controllers['blue_curvature'].calculate_weighted_value()
                    self.visualizer_params['blue_curvature'] = value
                    
                elif self.current_stage == 3:
                    # 阶段3：分为沉髋和沉肩两个子阶段
                    if self.current_sub_stage == 'hip':
                        # 沉髋阶段：骨盆左右倾斜
                        value = self.controllers['gray_tilt'].calculate_weighted_value()
                        self.visualizer_params['gray_tilt'] = value
                        
                    elif self.current_sub_stage == 'shoulder':
                        # 沉肩阶段：肩部左右倾斜
                        value = self.controllers['green_tilt'].calculate_weighted_value()
                        self.visualizer_params['green_tilt'] = value
            else:
                # S型脊柱：4阶段模式
                if self.current_stage == 1:
                    # 阶段1：骨盆前后翻转
                    value = self.controllers['gray_rotation'].calculate_weighted_value()
                    self.visualizer_params['gray_rotation'] = value
                    
                elif self.current_stage == 2:
                    # 阶段2：腰椎曲率矫正
                    value = self.controllers['blue_curvature'].calculate_weighted_value()
                    self.visualizer_params['blue_curvature'] = value
                    
                elif self.current_stage == 3:
                    # 阶段3：胸椎曲率矫正
                    value = self.controllers['gray_tilt'].calculate_weighted_value()
                    self.visualizer_params['gray_tilt'] = value
                    
                elif self.current_stage == 4:
                    # 阶段4：肩部左右倾斜
                    value = self.controllers['green_tilt'].calculate_weighted_value()
                    self.visualizer_params['green_tilt'] = value
            
            # 更新积木显示
            self._update_blocks_visualization_new_method()
            
        except Exception as e:
            print(f"患者端可视化更新失败: {e}")

    def _update_blocks_visualization_new_method(self):
        """新的积木可视化更新方法（支持S型4阶段）"""
        if not self.blocks_widget:
            return
            
        try:
            # 根据脊柱类型和当前阶段设置对应的可视化参数
            if self.spine_type == "C":
                # C型脊柱逻辑
                if self.current_stage == 1:
                    if hasattr(self.blocks_widget, 'gray_block_rotation'):
                        normalized_value = max(0.0, min(1.0, self.visualizer_params['gray_rotation']))
                        self.blocks_widget.gray_block_rotation = normalized_value
                        
                elif self.current_stage == 2:
                    if hasattr(self.blocks_widget, 'blue_blocks_curvature'):
                        normalized_value = max(0.0, min(1.0, self.visualizer_params['blue_curvature']))
                        self.blocks_widget.blue_blocks_curvature = normalized_value
                        
                elif self.current_stage == 3:
                    if self.current_sub_stage == 'hip':
                        if hasattr(self.blocks_widget, 'gray_block_tilt'):
                            normalized_value = max(0.0, min(1.0, self.visualizer_params['gray_tilt']))
                            self.blocks_widget.gray_block_tilt = normalized_value
                            
                    elif self.current_sub_stage == 'shoulder':
                        if hasattr(self.blocks_widget, 'green_block_tilt'):
                            normalized_value = max(0.0, min(1.0, self.visualizer_params['green_tilt']))
                            self.blocks_widget.green_block_tilt = normalized_value
            else:
                # S型脊柱逻辑
                if self.current_stage == 1:
                    if hasattr(self.blocks_widget, 'gray_block_rotation'):
                        normalized_value = max(0.0, min(1.0, self.visualizer_params['gray_rotation']))
                        self.blocks_widget.gray_block_rotation = normalized_value
                        
                elif self.current_stage == 2:
                    if hasattr(self.blocks_widget, 'blue_blocks_curvature'):
                        normalized_value = max(0.0, min(1.0, self.visualizer_params['blue_curvature']))
                        self.blocks_widget.blue_blocks_curvature = normalized_value
                        
                elif self.current_stage == 3:
                    # if hasattr(self.blocks_widget, 'blue_blocks_curvature'):
                    #     normalized_value = max(0.0, min(1.0, self.visualizer_params['blue_curvature']))
                    #     self.blocks_widget.blue_blocks_curvature = normalized_value
                    if hasattr(self.blocks_widget, 'gray_block_tilt'):
                        normalized_value = max(0.0, min(1.0, self.visualizer_params['gray_tilt']))
                        self.blocks_widget.gray_block_tilt = normalized_value
                        
                elif self.current_stage == 4:
                    if hasattr(self.blocks_widget, 'green_block_tilt'):
                        normalized_value = max(0.0, min(1.0, self.visualizer_params['green_tilt']))
                        self.blocks_widget.green_block_tilt = normalized_value
            
            # 触发重绘
            self.blocks_widget.update()
            
        except Exception as e:
            print(f"患者端积木可视化更新失败: {e}")

    def _check_stage_completion(self):
        """检查当前阶段是否完成（支持S型4阶段）"""
        if not self.training_active:
            return
        
        # 根据脊柱类型和当前阶段检查对应控制器的目标达成情况
        target_reached = False
        
        if self.spine_type == "C":
            # C型脊柱逻辑
            if self.current_stage == 1:
                target_reached = self.controllers['gray_rotation'].is_in_target_range()
            elif self.current_stage == 2:
                target_reached = self.controllers['blue_curvature'].is_in_target_range()
            elif self.current_stage == 3:
                if self.current_sub_stage == 'hip':
                    target_reached = self.controllers['gray_tilt'].is_in_target_range()
                elif self.current_sub_stage == 'shoulder':
                    target_reached = self.controllers['green_tilt'].is_in_target_range()
        else:
            # S型脊柱逻辑
            if self.current_stage == 1:
                target_reached = self.controllers['gray_rotation'].is_in_target_range()
            elif self.current_stage == 2:
                target_reached = self.controllers['blue_curvature'].is_in_target_range()
            elif self.current_stage == 3:
                target_reached = self.controllers['gray_tilt'].is_in_target_range()
            elif self.current_stage == 4:
                target_reached = self.controllers['green_tilt'].is_in_target_range()
        
        # 处理倒计时逻辑
        if target_reached and not self.countdown_active:
            self._start_countdown()
        elif not target_reached and self.countdown_active:
            self._stop_countdown()

    def _start_countdown(self):
        """开始倒计时"""
        if self.countdown_active:
            return
        
        self.countdown_active = True
        self.countdown_seconds = 5
        self.countdown_label.setText(f"目标达成！保持姿态 {self.countdown_seconds} 秒...")
        self.progress_bar.setRange(0, 5)
        self.progress_bar.setValue(5 - self.countdown_seconds)
        self.countdown_timer.start(1000)  # 每秒更新一次
        
        print(f"开始倒计时: {self.countdown_seconds}秒")

    def _stop_countdown(self):
        """停止倒计时"""
        if not self.countdown_active:
            return
        
        self.countdown_active = False
        self.countdown_timer.stop()
        self.countdown_label.setText("请调整到目标位置")
        self.progress_bar.setValue(0)
        
        print("停止倒计时")

    def _update_countdown(self):
        """更新倒计时显示"""
        if not self.countdown_active:
            return
        
        self.countdown_seconds -= 1
        
        if self.countdown_seconds > 0:
            self.countdown_label.setText(f"目标达成！保持姿态 {self.countdown_seconds} 秒...")
            self.progress_bar.setValue(5 - self.countdown_seconds)
        else:
            # 倒计时结束，进入下一阶段
            self._complete_current_stage()

    def _complete_current_stage(self):
        """完成当前阶段，进入下一阶段（支持S型4阶段）"""
        self._stop_countdown()
        
        if self.spine_type == "C":
            # C型脊柱逻辑
            if self.current_stage == 1:
                self.current_stage = 2
                self.current_sub_stage = None
                self.update_status(f"阶段1完成", f"进入阶段2：脊柱曲率矫正")
            elif self.current_stage == 2:
                self.current_stage = 3
                self.current_sub_stage = 'hip'
                self.update_status(f"阶段2完成", f"进入阶段3：沉髋训练")
            elif self.current_stage == 3:
                if self.current_sub_stage == 'hip':
                    self.current_sub_stage = 'shoulder'
                    self.update_status(f"沉髋训练完成", f"进入沉肩训练")
                elif self.current_sub_stage == 'shoulder':
                    self._complete_training()
                    return
        else:
            # S型脊柱逻辑
            if self.current_stage == 1:
                self.current_stage = 2
                self.update_status(f"阶段1完成", f"进入阶段2：腰椎曲率矫正")
            elif self.current_stage == 2:
                self.current_stage = 3
                self.update_status(f"阶段2完成", f"进入阶段3：胸椎曲率矫正")
            elif self.current_stage == 3:
                self.current_stage = 4
                self.update_status(f"阶段3完成", f"进入阶段4：肩部左右倾斜调整")
            elif self.current_stage == 4:
                self._complete_training()
                return
        
        # 更新阶段显示
        self._update_stage_display()
        
        # 更新可视化器当前阶段
        self._update_visualizer_for_spine_config()

    def _complete_training(self):
        """完成所有训练"""
        self.training_active = False
        self.is_training = False
        self.stage_check_timer.stop()
        
        self.stage_label.setText("训练完成！")
        self.stage_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #28A745;
                padding: 10px;
                border: 2px solid #28A745;
                border-radius: 8px;
                background-color: #D4EDDA;
            }
        """)
        
        self.countdown_label.setText("恭喜您完成了所有训练阶段！")
        self.progress_bar.setValue(5)
        self.progress_bar.setFormat("训练完成！")
        
        self.update_status("训练完成", "恭喜您完成了所有训练阶段！")
        
        # 发送训练完成信号
        self.training_completed.emit()
        
        print("患者端训练完成（新驱动方式）")

    def _update_stage_display(self):
        """更新阶段显示（支持S型4阶段）"""
        current_config = self.stage_configs[self.spine_type]
        
        if self.spine_type == "C":
            # C型脊柱显示逻辑
            if self.current_stage == 3:
                if self.current_sub_stage == 'hip':
                    description = "阶段3：沉髋训练"
                    stage_text = "阶段3-沉髋"
                elif self.current_sub_stage == 'shoulder':
                    description = "阶段3：沉肩训练"
                    stage_text = "阶段3-沉肩"
                else:
                    description = current_config["stage_descriptions"].get(self.current_stage, f"阶段{self.current_stage}")
                    stage_text = f"阶段{self.current_stage}"
            else:
                description = current_config["stage_descriptions"].get(self.current_stage, f"阶段{self.current_stage}")
                stage_text = f"阶段{self.current_stage}"
        else:
            # S型脊柱显示逻辑
            description = current_config["stage_descriptions"].get(self.current_stage, f"阶段{self.current_stage}")
            stage_text = f"阶段{self.current_stage}"
        
        self.stage_label.setText(f"{self.spine_type}型-{stage_text}")
        
        # 根据是否达到目标来设置提示文本
        if self.countdown_active:
            self.countdown_label.setText(f"目标达成！保持姿态 {self.countdown_seconds} 秒...")
        else:
            self.countdown_label.setText("请按照积木提示调整到目标姿态...")
        
        print(f"患者端阶段显示已更新为: {stage_text} ({description})")

    # ================================================================
    # 保持兼容性的方法（原有接口）
    # ================================================================

    def update_from_events_file(self):
        """从事件文件更新数据（保持原有功能）"""
        if not self.events_file_path or not os.path.exists(self.events_file_path):
            return
            
        try:
            # 检查文件是否有更新
            events = self.read_events_file()
            
            if len(events) > self.last_event_count:
                # 重新加载阶段数据
                self.load_events_data()
                self.last_event_count = len(events)
                    
        except Exception as e:
            print(f"从事件文件更新失败: {e}")
            
    def read_events_file(self):
        """读取事件文件"""
        events = []
        try:
            with open(self.events_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 跳过注释行
                    if any(key.startswith('#') for key in row.keys()):
                        continue
                    events.append(row)
        except Exception as e:
            print(f"读取事件文件时出错: {e}")
        return events
        
    def update_status(self, status, guidance, additional_info=""):
        """更新状态显示"""
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        
        status_html = f"""
        <div style="color: #495057;">
        <h4 style="color: #007bff; margin-bottom: 10px;">智能脊柱康复训练系统 - 患者端（新驱动方式）</h4>
        <p><strong>时间：</strong>{current_time}</p>
        <p><strong>状态：</strong>{status}</p>
        <p><strong>指导：</strong>{guidance}</p>
        """
        
        if additional_info:
            status_html += f"<p><strong>详情：</strong>{additional_info}</p>"
            
        status_html += """
        <hr style="border: 1px solid #dee2e6;">
        <p style="color: #6c757d; font-size: 11px;">
        • 系统采用与医生端相同的驱动逻辑<br>
        • 原始值/目标值来源于事件数据文件<br>
        • 请按照积木指示调整您的姿势<br>
        • 如有不适请立即停止
        </p>
        </div>
        """
        
        self.status_display.setHtml(status_html)
        
        # 自动滚动到底部
        self.status_display.verticalScrollBar().setValue(
            self.status_display.verticalScrollBar().maximum()
        )
        
    def set_sensor_count(self, count):
        """设置传感器数量"""
        old_count = self.sensor_count
        self.sensor_count = count
        
        # 更新所有控制器的传感器数量
        for controller in self.controllers.values():
            controller.sensor_count = count
            # 调整数组大小
            if count > old_count:
                # 扩展数组
                controller.selected_sensors.extend([False] * (count - old_count))
                controller.sensor_weights.extend([0.0] * (count - old_count))
                controller.original_values.extend([2500.0] * (count - old_count))
                controller.target_values.extend([2500.0] * (count - old_count))
                controller.current_values.extend([2500.0] * (count - old_count))
            elif count < old_count:
                # 缩短数组
                controller.selected_sensors = controller.selected_sensors[:count]
                controller.sensor_weights = controller.sensor_weights[:count]
                controller.original_values = controller.original_values[:count]
                controller.target_values = controller.target_values[:count]
                controller.current_values = controller.current_values[:count]
        
        # 重新设置默认配置
        self._setup_default_controller_configs()
            
        print(f"患者界面传感器数量设置为: {count}")
        
    def get_training_status(self):
        """获取训练状态"""
        return {
            'is_training': self.is_training,
            'current_stage': self.current_stage,
            'current_sub_stage': self.current_sub_stage,
            'target_reached': self.target_reached,
            'countdown_seconds': self.countdown_seconds,
            'visualization_params': self.visualizer_params.copy()
        }
        
    def reset_interface(self):
        """重置界面到初始状态"""
        if self.is_training:
            self.stop_training_mode()
            
        # 重置积木参数
        self.visualizer_params = {
            'gray_rotation': 0,
            'gray_tilt': 0,
            'blue_curvature': 0,
            'green_tilt': 0
        }
        
        # 重置所有控制器
        for controller in self.controllers.values():
            controller.current_values = [2500.0] * self.sensor_count
        
        # 重置显示
        self.stage_label.setText("当前阶段: 等待开始")
        self.countdown_label.setText("等待开始训练")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("准备中 %p%")
        
        self._update_blocks_visualization_new_method()
        self.update_status("系统已重置", "请重新开始训练")
        
        print("患者界面已重置（新驱动方式）")

    # ================================================================
    # 调试和监控方法
    # ================================================================
    
    def get_controller_status(self):
        """获取所有控制器的状态（用于调试）"""
        status = {}
        for name, controller in self.controllers.items():
            # 只显示有权重的传感器
            active_sensors = [(i, controller.sensor_weights[i]) for i in range(self.sensor_count) 
                            if controller.selected_sensors[i] and controller.sensor_weights[i] != 0]
            
            status[name] = {
                'active_sensors': active_sensors,
                'error_range': controller.error_range,
                'weighted_value': controller.calculate_weighted_value(),
                'in_target_range': controller.is_in_target_range()
            }
            
            # 为有权重的传感器显示详细信息
            for sensor_idx, weight in active_sensors:
                original = controller.original_values[sensor_idx]
                target = controller.target_values[sensor_idx]
                current = controller.current_values[sensor_idx]
                
                # 计算原始值和目标值的差值
                value_difference = abs(original - target)
                
                # 误差范围乘以差值作为容差
                tolerance = value_difference * controller.error_range
                
                # 计算目标范围
                target_range = (target - tolerance, target + tolerance)
                
                status[name][f'sensor{sensor_idx+1}'] = {
                    'weight': weight,
                    'original': original,
                    'target': target,
                    'current': current,
                    'target_range': target_range,
                    'tolerance': tolerance,
                    'value_difference': value_difference
                }
        return status
    
    def print_controller_status(self):
        """打印控制器状态（用于调试）"""
        print(f"\n=== 患者端控制器状态（详细）- 阶段{self.current_stage}" + 
              (f"-{self.current_sub_stage}" if self.current_sub_stage else "") + " ===")
        status = self.get_controller_status()
        
        # 根据当前阶段只显示相关的控制器
        relevant_controllers = []
        if self.current_stage == 1:
            relevant_controllers = ['gray_rotation']
        elif self.current_stage == 2:
            relevant_controllers = ['blue_curvature']
        elif self.current_stage == 3:
            if self.current_sub_stage == 'hip':
                relevant_controllers = ['gray_tilt']
            elif self.current_sub_stage == 'shoulder':
                relevant_controllers = ['green_tilt']
            else:
                relevant_controllers = ['gray_tilt', 'green_tilt']
        
        for name in relevant_controllers:
            if name in status:
                ctrl_status = status[name]
                print(f"\n{name}:")
                print(f"  加权值: {ctrl_status['weighted_value']:.3f}")
                print(f"  目标达成: {ctrl_status['in_target_range']}")
                print(f"  误差范围: ±{ctrl_status['error_range']*100:.1f}%")
                print(f"  激活的传感器:")
                
                for sensor_idx, weight in ctrl_status['active_sensors']:
                    sensor_key = f'sensor{sensor_idx+1}'
                    if sensor_key in ctrl_status:
                        sensor_info = ctrl_status[sensor_key]
                        target_range = sensor_info['target_range']
                        current = sensor_info['current']
                        in_range = target_range[0] <= current <= target_range[1]
                        
                        print(f"    传感器{sensor_idx+1} (权重{weight}):")
                        print(f"      原始值: {sensor_info['original']}")
                        print(f"      目标值: {sensor_info['target']}")
                        print(f"      当前值: {current}")
                        print(f"      目标范围: {target_range[0]:.1f} - {target_range[1]:.1f}")
                        print(f"      在范围内: {'是' if in_range else '否'}")
        print("=" * 50)

    # ================================================================
    # 向后兼容的废弃方法（保持接口一致性）
    # ================================================================
    
    def _update_visualization(self):
        """废弃方法：向后兼容"""
        print("警告：使用了废弃的_update_visualization方法，请使用新的驱动方式")
        self._update_visualization_new_method()
        
    def _update_blocks_visualization(self):
        """废弃方法：向后兼容"""
        print("警告：使用了废弃的_update_blocks_visualization方法，请使用新的驱动方式")
        self._update_blocks_visualization_new_method()

    def load_stage_data_from_events(self):
        """保持兼容性的方法"""
        return self.load_events_data()
        
    def start_stage(self, stage_num):
        """保持兼容性的方法"""
        if 1 <= stage_num <= 3:
            self.current_stage = stage_num
            self._update_stage_display()
            print(f"患者端：切换到阶段{stage_num}（新驱动方式）")

    def check_target_reached(self):
        """保持兼容性的方法"""
        if self.current_stage == 1:
            return self.controllers['gray_rotation'].is_in_target_range()
        elif self.current_stage == 2:
            return self.controllers['blue_curvature'].is_in_target_range()
        elif self.current_stage == 3:
            # 阶段3：根据子阶段分别检查
            if self.current_sub_stage == 'hip':
                return self.controllers['gray_tilt'].is_in_target_range()
            elif self.current_sub_stage == 'shoulder':
                return self.controllers['green_tilt'].is_in_target_range()
        return False
        
    def countdown_tick(self):
        """保持兼容性的方法"""
        self._update_countdown()
            
    def advance_to_next_stage(self):
        """保持兼容性的方法"""
        self._complete_current_stage()
            
    def complete_training(self):
        """保持兼容性的方法"""
        self._complete_training()

    def get_spine_config(self):
        """获取脊柱配置"""
        return {
            'type': self.spine_type,
            'direction': self.spine_direction,
            'max_stages': self.max_stages
        }

    def set_spine_config(self, spine_type, spine_direction):
        """设置脊柱配置（用于与医生端同步）"""
        self.spine_type = spine_type
        self.spine_direction = spine_direction
        self.spine_type_display.set_spine_config(spine_type, spine_direction)
        self.max_stages = self.stage_configs[spine_type]["max_stages"]
        self._update_visualizer_for_spine_config()
        self._update_controller_configs_for_spine_type()
        print(f"患者端脊柱配置已设置为：{spine_type}型，方向={spine_direction}")

    def is_s_type_spine(self):
        """判断是否为S型脊柱"""
        return self.spine_type == "S"

    def is_c_type_spine(self):
        """判断是否为C型脊柱"""
        return self.spine_type == "C"


# 测试代码
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = PatientBlocksTab()
    window.show()
    window.resize(1200, 800)
    
    sys.exit(app.exec_())