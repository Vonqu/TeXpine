
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
                            QSlider, QSpinBox, QProgressBar, QPushButton,
                            QRadioButton, QButtonGroup, QSizePolicy)
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
                current = self.current_values[i]
                tolerance = abs(target * self.error_range)
                
                if not (target - tolerance <= current <= target + tolerance):
                    return False
        return True


class PatientBlocksTab(QWidget):
    """
    患者积木可视化标签页（修改版）
    =============================
    
    新增功能：
    - 采用与tab2相同的驱动方式
    - 从事件数据文件读取原始值/目标值
    - 支持四个控制器对应四种动作
    """
    
    # 定义信号
    request_data = pyqtSignal()      # 请求数据信号
    training_completed = pyqtSignal()  # 训练完成信号
    
    def __init__(self, sensor_count=6, parent=None):
        super().__init__(parent)
        self.sensor_count = sensor_count
        
        # ====== 新增：脊柱类型和方向配置 ======
        self.spine_type = "C"  # 默认C型
        self.spine_direction = "left"  # 默认左凸
        self.max_stages = 5 if self.spine_type=='S' else 4  # 根据脊柱类型调整
        
        # ====== 阶段配置字典 ======
        self.stage_configs = {
            "C": {
                "max_stages": 4,
                
"stage_descriptions": {
    1: "阶段1：骨盆前后翻转",
    2: "阶段2：脊柱曲率矫正-单段",
    3: "阶段3：骨盆左右倾斜",
    4: "阶段4：肩部左右倾斜"
}
,
                "sub_stages": {
                    3: ['hip', 'shoulder']  # 阶段3有两个子阶段
                }
            },
            
"S": {
    "max_stages": 5,
    "stage_descriptions": {
        1: "阶段1：骨盆前后翻转",
        2: "阶段2A：上胸段曲率矫正",
        3: "阶段2B：腰段曲率矫正",
        4: "阶段3：骨盆左右倾斜",
        5: "阶段4：肩部左右倾斜"
    },
    "sub_stages": {}
}
}

        
        # ====== 患者端训练相关属性 ======
        self.current_stage = 1
        self.current_sub_stage = None  # 新增：用于阶段3的子阶段 ('hip' 或 'shoulder')
        self.training_active = False
        self.events_data = {}  # 存储从事件文件读取的数据
        self.events_file_path = ""  # 事件文件路径
        
        # ====== 新增：四个传感器控制器 ======
        self.controllers = {
            'gray_rotation': PatientSensorController("骨盆前后翻转", sensor_count),    # 阶段1
            'blue_curvature': PatientSensorController("脊柱曲率矫正", sensor_count),   # 阶段2  
            'gray_tilt': PatientSensorController("骨盆左右倾斜", sensor_count),        # 阶段3沉髋
            'green_tilt': PatientSensorController("肩部左右倾斜", sensor_count)        # 阶段3沉肩
        }
        
        # ====== 倒计时相关 ======
        self.countdown_active = False
        self.countdown_seconds = 5
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        
        # ====== 阶段检查定时器 ======
        self.stage_check_timer = QTimer()
        self.stage_check_timer.timeout.connect(self._check_stage_completion)
        self.stage_check_timer.start(100)  # 每100ms检查一次
        
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
    
    def _create_spine_config_group(self):
        """创建脊柱类型和方向选择组"""
        group = QGroupBox("脊柱侧弯类型和方向选择")
        layout = QVBoxLayout()
        group.setLayout(layout)
        from PyQt5.QtGui import QFont
        _small = QFont(); _small.setPointSize(9)
        # 紧凑化：缩小边距/间距、限定高度
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        group.setMaximumHeight(140)
        try:
            group.setStyleSheet('QGroupBox{margin-top:4px;} QGroupBox::title{left:8px;padding:0 4px;font-size:11px;}')
        except Exception:
            pass
        
        # 第一行：脊柱类型选择
        type_layout = QHBoxLayout()
        type_label = QLabel("脊柱类型:"); 
        type_label.setFont(_small)
        type_layout.addWidget(type_label)
        
        # 创建脊柱类型单选按钮组
        self.spine_type_button_group = QButtonGroup()
        
        # C型脊柱侧弯
        self.c_type_radio = QRadioButton("C型脊柱侧弯"); c_type_radio = QRadioButton("C型脊柱侧弯").split('=')[0] if False else None
        self.c_type_radio.setChecked(True)
        self.c_type_radio.setToolTip("C型脊柱侧弯：3个阶段的训练模式")
        type_layout.addWidget(self.c_type_radio)
        
        # S型脊柱侧弯
        self.s_type_radio = QRadioButton("S型脊柱侧弯"); s_type_radio = QRadioButton("S型脊柱侧弯").split('=')[0] if False else None
        self.s_type_radio.setToolTip("S型脊柱侧弯：4个阶段的训练模式")
        type_layout.addWidget(self.s_type_radio)
        
        # 添加到按钮组
        self.spine_type_button_group.addButton(self.c_type_radio, 0)
        self.spine_type_button_group.addButton(self.s_type_radio, 1)
        
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # 第二行：侧弯方向选择
        direction_layout = QHBoxLayout()
        direction_label = QLabel("侧弯方向:"); direction_label.setFont(_small)
        direction_layout.addWidget(direction_label)
        
        # 创建侧弯方向单选按钮组
        self.spine_direction_button_group = QButtonGroup()
        
        # C型方向选择
        self.c_left_radio = QRadioButton("左凸"); c_left_radio = QRadioButton("左凸").split('=')[0] if False else None
        self.c_right_radio = QRadioButton("右凸"); c_right_radio = QRadioButton("右凸").split('=')[0] if False else None
        self.c_left_radio.setChecked(True)
        
        # S型方向选择
        self.s_lumbar_left_radio = QRadioButton("腰椎左凸胸椎右凸"); s_lumbar_left_radio = QRadioButton("腰椎左凸胸椎右凸").split('=')[0] if False else None
        self.s_lumbar_right_radio = QRadioButton("腰椎右凸胸椎左凸"); s_lumbar_right_radio = QRadioButton("腰椎右凸胸椎左凸").split('=')[0] if False else None
        
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
        
        # 默认显示C型方向选择
        direction_layout.addWidget(self.c_direction_widget)
        direction_layout.addWidget(self.s_direction_widget)
        self.s_direction_widget.hide()  # 默认隐藏S型选择
        
        layout.addLayout(direction_layout)
        
        # 添加说明文字
        info_label = QLabel("选择脊柱类型和方向将自动调整训练阶段和可视化效果")
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        layout.addWidget(info_label)
        # 统一缩小单选按钮字体
        try:
            for rb in group.findChildren(QRadioButton):
                rb.setFont(_small)
        except Exception:
            pass
        
        # 连接信号
        self.spine_type_button_group.buttonClicked.connect(self._on_spine_type_changed)
        self.spine_direction_button_group.buttonClicked.connect(self._on_spine_direction_changed)
        
        return group
    
    def _on_spine_type_changed(self, button):
        """处理脊柱类型变化"""
        if button == self.c_type_radio:
            self.spine_type = "C"
            self.max_stages = 4
            self.c_direction_widget.show()
            self.s_direction_widget.hide()
            # 默认选择左凸
            self.c_left_radio.setChecked(True)
            self.spine_direction = "left"
        elif button == self.s_type_radio:
            self.spine_type = "S"
            self.max_stages = 5  # 修复：S型应该是5阶段
            # 显示S型方向选择，隐藏C型
            self.c_direction_widget.hide()
            self.s_direction_widget.show()
            # 默认选择腰椎左凸胸椎右凸
            self.s_lumbar_left_radio.setChecked(True)
            self.spine_direction = "lumbar_left"
        
        print(f"脊柱类型已更改为: {self.spine_type}型，最大阶段数: {self.max_stages}")
        self._update_controller_configs_for_spine_type()
        self._update_visualizer_for_spine_config()
        # 切换类型后重建训练卡片
        try:
            self._rebuild_training_modules()
        except Exception as _e:
            print('重建训练卡片失败:', _e)
    
    def _on_spine_direction_changed(self, button):
        """处理脊柱方向变化"""
        if button == self.c_left_radio:
            self.spine_direction = "left"
        elif button == self.c_right_radio:
            self.spine_direction = "right"
        elif button == self.s_lumbar_left_radio:
            self.spine_direction = "lumbar_left"
        elif button == self.s_lumbar_right_radio:
            self.spine_direction = "lumbar_right"
        
        print(f"脊柱方向已更改为: {self.spine_direction}")
        self._update_visualizer_for_spine_config()
    
    def _update_controller_configs_for_spine_type(self):
        """根据脊柱类型更新控制器配置"""
        # 这里可以根据脊柱类型调整控制器的默认配置
        # 例如，S型可能需要不同的传感器权重分配
        print(f"正在为{self.spine_type}型脊柱更新控制器配置...")
        
        # 可以在这里添加特定于脊柱类型的配置逻辑
        # 例如：不同类型的脊柱可能需要不同的传感器组合
    
    def _update_visualizer_for_spine_config(self):
        """根据脊柱配置更新可视化效果"""
        # 这里可以根据脊柱类型和方向调整可视化参数
        print(f"正在为{self.spine_type}型{self.spine_direction}方向脊柱更新可视化效果...")
        
        # 可以在这里添加特定于脊柱配置的可视化调整逻辑

    def init_ui(self):
        """初始化用户界面"""
        # 创建主水平分割器
        main_splitter = QSplitter(Qt.Horizontal)
        
        # ====== 左侧区域 ======
        left_widget = self.create_left_panel()
        
        # ====== 右侧区域 ======
        right_widget = self.create_right_panel()
        
        # 添加到分割器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([600, 600])  # 设置初始比例
        
        # 设置主布局
        main_layout = QHBoxLayout()
        main_layout.addWidget(main_splitter)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(main_layout)
        
    def create_left_panel(self):
        """创建左侧面板：4个积木可视化模块"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        # ====== 新增：脊柱类型和方向选择区域 ======
        spine_config_group = self._create_spine_config_group()
        left_layout.addWidget(spine_config_group)
        spine_config_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        spine_config_group.setMaximumHeight(140)
        
        # 创建4个积木可视化模块的网格布局
        from PyQt5.QtWidgets import QGridLayout
        grid_layout = QGridLayout()
        
        # 创建4个积木可视化组件
        self.blocks_widgets = {}
        module_configs = [
            ('gray_rotation', '骨盆前后反转', 0, 0),
            ('blue_curvature', '脊柱曲率矫正', 0, 1),
            ('gray_tilt', '骨盆左右倾斜', 1, 0),
            ('green_tilt', '肩部左右倾斜', 1, 1)
        ]
        
        for controller_name, display_name, row, col in module_configs:
            # 创建包装器，添加标题
            wrapper_widget = QWidget()
            wrapper_layout = QVBoxLayout()
            
            # 添加标题
            title_label = QLabel(display_name)
            title_label.setFont(QFont("Arial", 10, QFont.Bold))
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("""
                QLabel {
                    color: #2196F3;
                    padding: 5px;
                    border: 1px solid #2196F3;
                    border-radius: 3px;
                    background-color: #E3F2FD;
                    margin-bottom: 5px;
                }
            """)
            
            # 创建单个积木可视化组件
            try:
                blocks_widget = BlocksVisualizer()
                blocks_widget.setMinimumSize(200, 280)
                blocks_widget.setMaximumSize(250, 320)
            except Exception as e:
                # 如果创建失败，显示占位符
                blocks_widget = QLabel("积木可视化组件加载中...")
                blocks_widget.setAlignment(Qt.AlignCenter)
                blocks_widget.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
                blocks_widget.setMinimumSize(200, 280)
                blocks_widget.setMaximumSize(250, 320)
                print(f"积木可视化组件创建失败: {e}")
            
            wrapper_layout.addWidget(title_label)
            wrapper_layout.addWidget(blocks_widget)
            wrapper_layout.setContentsMargins(5, 5, 5, 5)
            wrapper_widget.setLayout(wrapper_layout)
            
            # 设置边框样式
            wrapper_widget.setStyleSheet("""
                QWidget {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: white;
                    margin: 2px;
                }
            """)
            
            self.blocks_widgets[controller_name] = blocks_widget
            grid_layout.addWidget(wrapper_widget, row, col)
        
        left_layout.addLayout(grid_layout)
        left_layout.setContentsMargins( 6, 6, 6, 6 )
        
        left_widget.setLayout(left_layout)
        return left_widget
        
    def create_right_panel(self):
        """创建右侧面板：训练模块 + 状态显示（C:4/S:5 动态）"""
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)
        
        # === 训练模块（动态）===
        modules_group = QGroupBox("训练模块")
        modules_layout = QVBoxLayout()
        from PyQt5.QtWidgets import QGridLayout
        grid_layout = QGridLayout()
        
        # 保存句柄，供后续重建使用
        self.training_modules_group = modules_group
        self.training_modules_layout = modules_layout
        self.training_grid_layout = grid_layout
        self.training_modules = {}
        
        def _build_module_configs():
            if getattr(self, 'spine_type', 'C') == 'S':
                self.max_stages = 5
                return [
                    ('gray_rotation', '骨盆前后反转', 0, 0),
                    ('blue_curvature_up', '脊柱曲率矫正·胸段', 0, 1),
                    ('blue_curvature_down', '脊柱曲率矫正·腰段', 1, 0),
                    ('gray_tilt', '骨盆左右倾斜', 1, 1),
                    ('green_tilt', '肩部左右倾斜', 2, 0),
                ]
            else:
                self.max_stages = 4
                return [
                    ('gray_rotation', '骨盆前后反转', 0, 0),
                    ('blue_curvature', '脊柱曲率矫正', 0, 1),
                    ('gray_tilt', '骨盆左右倾斜', 1, 0),
                    ('green_tilt', '肩部左右倾斜', 1, 1),
                ]
        
        for key, title, row, col in _build_module_configs():
            card = self.create_training_module(key, title)
            self.training_modules[key] = card
            grid_layout.addWidget(card, row, col)
        
        modules_layout.addLayout(grid_layout)
        modules_group.setLayout(modules_layout)

        
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
        self.status_display.setMaximumHeight(120)
        self.status_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Microsoft YaHei', SimHei;
                font-size: 11px;
                line-height: 1.3;
            }
        """)
        
        # 设置初始状态信息
        self.update_status("等待开始训练", "请在监测界面选择患者端模式并开始采集")
        
        status_layout.addWidget(self.status_display)
        status_group.setLayout(status_layout)
        
        # 布局设置
        right_layout.insertWidget(0, modules_group, 3)  # 训练模块占主要空间
        right_layout.addWidget(status_group, 1)   # 状态显示占较小空间
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        right_widget.setLayout(right_layout)
        return right_widget
        
    def create_training_module(self, controller_name, display_name):
        """创建单个训练模块"""
        module_widget = QWidget()
        module_layout = QVBoxLayout()
        
        # 模块标题
        title_label = QLabel(display_name)
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #2196F3;
                padding: 5px;
                border: 1px solid #2196F3;
                border-radius: 3px;
                background-color: #E3F2FD;
            }
        """)
        module_layout.addWidget(title_label)
        
        # 小型可视化区域（占位符）
        viz_widget = QLabel("可视化")
        viz_widget.setAlignment(Qt.AlignCenter)
        viz_widget.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-height: 80px;
                max-height: 80px;
            }
        """)
        module_layout.addWidget(viz_widget)
        
        # 数值显示区域
        values_layout = QVBoxLayout()
        
        # 原始值显示
        original_label = QLabel("原始值: --")
        original_label.setFont(QFont("Arial", 9))
        original_label.setStyleSheet("color: #666; padding: 2px;")
        values_layout.addWidget(original_label)
        
        # 归一化值显示
        normalized_label = QLabel("归一化值: --")
        normalized_label.setFont(QFont("Arial", 9))
        normalized_label.setStyleSheet("color: #666; padding: 2px;")
        values_layout.addWidget(normalized_label)
        
        module_layout.addLayout(values_layout)
        
        # 完成状态按钮
        complete_button = QPushButton("未完成")
        complete_button.setEnabled(False)
        complete_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px;
                font-size: 9px;
                font-weight: bold;
            }
        """)
        module_layout.addWidget(complete_button)
        
        # 存储组件引用
        module_widget.title_label = title_label
        module_widget.viz_widget = viz_widget
        module_widget.original_label = original_label
        module_widget.normalized_label = normalized_label
        module_widget.complete_button = complete_button
        module_widget.controller_name = controller_name
        
        module_widget.setLayout(module_layout)
        module_widget.setStyleSheet("""
            QWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: white;
                margin: 2px;
            }
        """)
        
        return module_widget
    
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
        """从事件数据文件加载训练数据"""
        print("\n=== 开始加载事件数据 ===")
        if not self.events_file_path or not os.path.exists(self.events_file_path):
            print(f"事件文件路径无效或文件不存在: {self.events_file_path}")
            return False
            
        try:
            self.events_data = {}
            
            print(f"正在加载事件数据文件: {self.events_file_path}")
            print(f"文件是否存在: {os.path.exists(self.events_file_path)}")
            print(f"文件大小: {os.path.getsize(self.events_file_path)} 字节")
            
            with open(self.events_file_path, 'r', encoding='utf-8') as f:
                # 读取所有行
                lines = f.readlines()
                
                # 找到第一个非注释行且非空行作为CSV头部
                headers = None
                data_start_line = 0
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        headers = line.split(',')
                        data_start_line = i
                        break
                
                if headers is None:
                    print("文件中没有找到有效的CSV头部")
                    return False
                    
                print(f"CSV头部: {headers}")
                print(f"数据开始行: {data_start_line + 1}")
                
                # 创建CSV读取器，跳过注释行和空行
                reader = csv.DictReader(
                    (line for line in lines[data_start_line:] if line.strip() and not line.strip().startswith('#')),
                    fieldnames=headers
                )
                
                # 定义事件映射关系
                event_mappings = {
                    # 阶段1 -> 骨盆前后翻转
                    ("阶段1", "开始训练"): ('gray_rotation', 'original'),
                    ("阶段1", "完成阶段"): ('gray_rotation', 'target'),
                    
                    # 阶段2 -> 脊柱曲率矫正
                    ("阶段2", "开始矫正"): ('blue_curvature', 'original'),
                    ("阶段2", "矫正完成"): ('blue_curvature', 'target'),
                    
                    # 阶段3沉髋 -> 骨盆左右倾斜
                    ("阶段3", "开始沉髋"): ('gray_tilt', 'original'),
                    ("阶段3", "沉髋完成"): ('gray_tilt', 'target'),
                    
                    # 阶段3沉肩 -> 肩部左右倾斜
                    ("阶段3", "开始沉肩"): ('green_tilt', 'original'),
                    ("阶段3", "沉肩完成"): ('green_tilt', 'target'),
                }
                
                for row in reader:
                    stage = row.get('stage', '').strip()
                    event_name = row.get('event_name', '').strip()
                    
                    # 检查是否匹配映射关系
                    mapping_key = (stage, event_name)
                    if mapping_key in event_mappings:
                        controller_name, value_type = event_mappings[mapping_key]
                        
                        # 解析传感器数据（跳过时间戳）
                        sensor_data = []
                        for i in range(1, self.sensor_count + 1):
                            sensor_key = f'sensor{i}'
                            try:
                                if sensor_key in row and row[sensor_key].strip():
                                    value = float(row[sensor_key])
                                    sensor_data.append(value)
                                else:
                                    sensor_data.append(2500.0)
                            except (ValueError, AttributeError) as e:
                                print(f"警告：传感器{i}数据转换失败 ({row.get(sensor_key, 'N/A')})")
                                sensor_data.append(2500.0)
                        
                        # 解析权重数据
                        weights = []
                        for i in range(1, self.sensor_count + 1):
                            weight_key = f'weight{i}'
                            try:
                                if weight_key in row and row[weight_key].strip():
                                    weight = float(row[weight_key])
                                    weights.append(weight)
                                else:
                                    weights.append(0.0)
                            except (ValueError, AttributeError) as e:
                                print(f"警告：权重{i}转换失败 ({row.get(weight_key, 'N/A')})")
                                weights.append(0.0)
                        
                        # 解析误差范围
                        try:
                            error_range = float(row.get('error_range', '0.1'))
                        except (ValueError, TypeError):
                            error_range = 0.1
                            print(f"警告：使用默认误差范围 0.1")
                        
                        # 获取对应的控制器
                        controller = self.controllers[controller_name]
                        
                        # 设置传感器数据和权重
                        if value_type == 'original':
                            # 设置原始值
                            controller.set_original_values(sensor_data)
                            print(f"\n设置 {controller_name} 原始值:")
                            for i, value in enumerate(sensor_data):
                                print(f"  传感器{i+1}: {value:.2f}")
                            
                            # 设置权重和传感器选择
                            for i, weight in enumerate(weights):
                                if i < self.sensor_count:
                                    is_selected = abs(weight) > 0
                                    controller.set_sensor_selection(i, is_selected, abs(weight))
                                    if is_selected:
                                        print(f"  传感器{i+1}权重: {abs(weight):.2f}")
                            
                        elif value_type == 'target':
                            # 设置目标值
                            controller.set_target_values(sensor_data)
                            print(f"\n设置 {controller_name} 目标值:")
                            for i, value in enumerate(sensor_data):
                                if controller.selected_sensors[i]:  # 只显示选中的传感器
                                    print(f"  传感器{i+1}: {value:.2f}")
                        
                        # 设置误差范围
                        controller.set_error_range(error_range)
                        print(f"  误差范围: ±{error_range*100:.1f}%")
                        
                        # 存储完整事件数据
                        key = f"{stage}_{event_name}"
                        self.events_data[key] = {
                            'stage': stage,
                            'event_name': event_name,
                            'sensor_data': sensor_data,
                            'weights': weights,
                            'error_range': error_range,
                            'controller_name': controller_name,
                            'value_type': value_type,
                            'timestamp': float(row.get('time(s)', 0))  # 保存时间戳
                        }
            
            print(f"\n成功加载 {len(self.events_data)} 条事件数据")
            print(f"\n控制器配置状态:")
            for name, controller in self.controllers.items():
                print(f"\n{name}:")
                # 只显示选中的传感器信息
                selected_sensors = [i for i, selected in enumerate(controller.selected_sensors) if selected]
                if selected_sensors:
                    print("  选中的传感器:")
                    for i in selected_sensors:
                        print(f"    传感器{i+1}:")
                        print(f"      权重: {controller.sensor_weights[i]:.2f}")
                        print(f"      原始值: {controller.original_values[i]:.2f}")
                        print(f"      目标值: {controller.target_values[i]:.2f}")
                    print(f"    误差范围: ±{controller.error_range*100:.1f}%")
                else:
                    print("  没有选中的传感器")
            
            print("\n=== 事件数据加载完成 ===\n")
            return True
            
        except Exception as e:
            print(f"加载事件数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start_training_mode(self):
        """开始训练模式（同时启动4个训练线程）"""
        print("开始患者端训练模式（4线程并行）")
        
        # 首先加载事件数据
        if not self.load_events_data():
            print("无法加载事件数据，训练模式启动失败")
            return False
        
        # 设置训练状态
        self.training_active = True
        self.current_stage = 1
        self.is_training = True
        self.target_reached = False
        self.countdown_active = False
        
        # 同时启动所有4个控制器
        controllers = self._all_controller_keys()
        for controller_name in controllers:
            if hasattr(self, 'start_controller'):
                self.start_controller(controller_name)
        
        # 启动数据更新定时器
        if hasattr(self, 'data_timer') and not self.data_timer.isActive():
            self.data_timer.start(100)  # 100ms更新一次
        
        # 启动阶段检查定时器
        self.stage_check_timer.start(100)  # 每100ms检查一次
        
        # 更新状态显示
        self.update_status("训练模式已启动", "4个训练模块同时运行")
        
        print("患者界面：4个训练模块同时启动")
        return True
        
    def stop_training_mode(self):
        """停止训练模式（停止所有4个训练线程）"""
        self.training_active = False
        self.is_training = False
        
        # 停止所有控制器线程
        controllers = self._all_controller_keys()
        for controller_name in controllers:
            if hasattr(self, 'controllers') and controller_name in self.controllers:
                if hasattr(self, 'stop_controller'):
                    self.stop_controller(controller_name)
        
        # 停止所有定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        if hasattr(self, 'countdown_timer'):
            self.countdown_timer.stop()
        if hasattr(self, 'stage_check_timer'):
            self.stage_check_timer.stop()
        if hasattr(self, 'data_timer'):
            self.data_timer.stop()
        
        # 重置状态
        self.countdown_seconds = 0
        self.target_reached = False
        self.countdown_active = False
        
        # 更新显示
        if hasattr(self, 'stage_label'):
            self.stage_label.setText("当前阶段: 等待开始")
        if hasattr(self, 'countdown_label'):
            self.countdown_label.setText("训练已停止")
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("训练停止 %p%")
        
        # 更新状态显示
        self.update_status("训练模式已停止", "所有训练线程已停止")
        
        print("患者界面：所有4个训练线程已停止")

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
            
            # 强制同步数据到医生端（如果处于患者端模式）
            self._sync_data_to_doctor_mode(data)

    def _update_visualization_new_method(self):
        """新的可视化更新方法（同时更新4个模块）"""
        if not self.training_active:
            return
        
        try:
            # 同时计算所有4个控制器的可视化参数
            for controller_name, controller in self.controllers.items():
                value = controller.calculate_weighted_value()
                self.visualizer_params[controller_name] = value
            
            # 更新积木显示
            self._update_blocks_visualization_new_method()
            
            # 更新训练模块显示
            self._update_training_modules()
            
        except Exception as e:
            print(f"新方法更新可视化失败: {e}")
    
    def _sync_data_to_doctor_mode(self, data):
        """同步数据到医生端模式"""
        try:
            # 检查是否有父窗口的数据管理器
            if hasattr(self, 'parent') and self.parent:
                parent_window = self.parent
                # 查找数据管理器
                if hasattr(parent_window, 'data_manager'):
                    data_manager = parent_window.data_manager
                    # 如果数据管理器处于患者端模式，强制同步数据
                    if hasattr(data_manager, 'is_patient_mode') and data_manager.is_patient_mode:
                        # 立即添加数据点，触发同步
                        data_manager.add_data_point(data)
                        print(f"强制同步数据到医生端: {data[:3]}...")  # 只显示前3个值
        except Exception as e:
            print(f"数据同步失败: {e}")

    def _update_blocks_visualization_new_method(self):
        """新方法：更新所有积木可视化模块"""
        if not hasattr(self, 'blocks_widgets') or not self.blocks_widgets:
            return
        
        try:
            # 为每个积木可视化组件单独更新对应的参数
            for controller_name, blocks_widget in self.blocks_widgets.items():
                if hasattr(blocks_widget, 'update_visualization'):
                    # 创建参数字典，只激活当前模块对应的参数
                    params = {
                        'gray_rotation': 0,
                        'blue_curvature': 0,
                        'gray_tilt': 0,
                        'green_tilt': 0
                    }
                    
                    # 设置当前模块的参数值
                    if controller_name in self.visualizer_params:
                        params[controller_name] = self.visualizer_params[controller_name]
                    
                    # 更新积木显示
                    blocks_widget.update_visualization(
                        gray_rotation=params['gray_rotation'],
                        blue_curvature=params['blue_curvature'],
                        gray_tilt=params['gray_tilt'],
                        green_tilt=params['green_tilt']
                    )
                elif hasattr(blocks_widget, 'update'):
                    # 如果是简单的QWidget，直接触发重绘
                    blocks_widget.update()
        except Exception as e:
            print(f"新方法更新积木可视化失败: {e}")

    def _update_training_modules(self):
        """更新训练模块显示"""
        if not hasattr(self, 'training_modules'):
            return
            
        for controller_name, module_widget in self.training_modules.items():
            controller = self.controllers[controller_name]
            
            # 计算原始值（选中传感器的加权平均）
            original_value = self._calculate_weighted_average(controller.original_values, controller.sensor_weights, controller.selected_sensors)
            
            # 计算归一化值
            normalized_value = controller.calculate_weighted_value()
            
            # 更新显示
            module_widget.original_label.setText(f"原始值: {original_value:.1f}")
            module_widget.normalized_label.setText(f"归一化值: {normalized_value:.3f}")
            
            # 更新完成状态
            is_complete = controller.is_in_target_range()
            if is_complete:
                module_widget.complete_button.setText("已完成")
                module_widget.complete_button.setStyleSheet("""
                    QPushButton {
                        background-color: #28a745;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        padding: 5px;
                        font-size: 9px;
                        font-weight: bold;
                    }
                """)
            else:
                module_widget.complete_button.setText("未完成")
                module_widget.complete_button.setStyleSheet("""
                    QPushButton {
                        background-color: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        padding: 5px;
                        font-size: 9px;
                        font-weight: bold;
                    }
                """)
    
    def _calculate_weighted_average(self, values, weights, selected):
        """计算加权平均值"""
        total_weight = 0
        weighted_sum = 0
        
        for i in range(len(values)):
            if selected[i] and weights[i] != 0:
                weighted_sum += values[i] * weights[i]
                total_weight += weights[i]
        
        return weighted_sum / total_weight if total_weight > 0 else 0
    
    
    def _check_stage_completion(self):
        """检查当前阶段是否完成（按阶段对应模块判定）"""
        if not self.training_active:
            return

        # 确定当前阶段对应的控制器
        controller_name = self._controller_for_current_stage()
        if not controller_name or controller_name not in getattr(self, 'controllers', {}):
            return

        reached = self.controllers[controller_name].is_in_target_range()

        # 处理倒计时逻辑
        if reached and not self.countdown_active:
            self._start_countdown()
        elif not reached and self.countdown_active:
            self._stop_countdown()

    def _start_countdown(self):
        """开始倒计时"""
        if self.countdown_active:
            return
        
        self.countdown_active = True
        self.countdown_seconds = 5
        
        # 更新状态显示
        self.update_status("所有目标达成！", f"保持当前姿态 {self.countdown_seconds} 秒完成训练")
        
        self.countdown_timer.start(1000)  # 每秒更新一次
        
        print(f"开始倒计时: {self.countdown_seconds}秒")

    def _stop_countdown(self):
        """停止倒计时"""
        if not self.countdown_active:
            return
        
        self.countdown_active = False
        self.countdown_timer.stop()
        
        # 更新状态显示
        self.update_status("继续调整姿态", "请按照各模块提示调整到目标位置")
        
        print("停止倒计时")

        
    def _update_countdown(self):
        """更新倒计时显示"""
        if not self.countdown_active:
            return

        self.countdown_seconds -= 1

        if self.countdown_seconds > 0:
            self.update_status("目标达成！", f"保持当前姿态 {self.countdown_seconds} 秒完成当前阶段")
        else:
            # 倒计时结束，完成当前阶段
            self._complete_current_stage()
    
            
    def _complete_current_stage(self):
        """完成当前阶段并进入下一阶段或结束"""
        # 停止倒计时
        self._stop_countdown()
        # 进入下一阶段
        self.current_stage = int(getattr(self, 'current_stage', 1)) + 1
        # 获取最大阶段
        stype = getattr(self, 'spine_type', 'C')
        max_stages = 5 if stype == 'S' else 4
        if self.current_stage > max_stages:
            # 所有阶段完成
            self._complete_training()
            return
        # 更新提示
        try:
            self.stage_label.setText(f"当前阶段: {self.current_stage}/{max_stages}")
        except Exception:
            pass
        self.update_status("阶段完成", f"进入下一阶段（{self.current_stage}/{max_stages}）")
    
    def _complete_training(self):
            self.training_active = False
            self.is_training = False
            self.stage_check_timer.stop()
            self.countdown_timer.stop()
            
            self.update_status("训练完成", "恭喜您完成了所有训练模块！")
            
            # 发送训练完成信号
            self.training_completed.emit()
            
            print("患者端训练完成（新驱动方式）")
    
    def _update_stage_display(self):
            """更新阶段显示（保持兼容性）"""
            # 新版本中不再需要阶段显示，因为所有模块同时运行
            pass
    
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
                    status[name][f'sensor{sensor_idx+1}'] = {
                        'weight': weight,
                        'original': controller.original_values[sensor_idx],
                        'target': controller.target_values[sensor_idx],
                        'current': controller.current_values[sensor_idx],
                        'target_range': (
                            controller.target_values[sensor_idx] * (1 - controller.error_range),
                            controller.target_values[sensor_idx] * (1 + controller.error_range)
                        )
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
            """获取当前脊柱配置"""
            return {
                'spine_type': self.spine_type,
                'spine_direction': self.spine_direction,
                'max_stages': self.max_stages
            }
        
    def set_spine_config(self, spine_type, spine_direction):
            """设置脊柱配置"""
            self.spine_type = spine_type
            self.spine_direction = spine_direction
            self.max_stages = self.stage_configs[spine_type]['max_stages']
            
            # 更新UI状态
            if spine_type == "C":
                self.c_type_radio.setChecked(True)
                self.c_direction_widget.show()
                self.s_direction_widget.hide()
                if spine_direction == "left":
                    self.c_left_radio.setChecked(True)
                else:
                    self.c_right_radio.setChecked(True)
            else:
                self.s_type_radio.setChecked(True)
                self.c_direction_widget.hide()
                self.s_direction_widget.show()
                if spine_direction == "lumbar_left":
                    self.s_lumbar_left_radio.setChecked(True)
                else:
                    self.s_lumbar_right_radio.setChecked(True)
            
            # 更新控制器配置和可视化
            self._update_controller_configs_for_spine_type()
            self._update_visualizer_for_spine_config()
        
    def is_s_type_spine(self):
            """检查是否为S型脊柱"""
            return self.spine_type == "S"
        
    def is_c_type_spine(self):
            """检查是否为C型脊柱"""
            return self.spine_type == "C"
    
    def _rebuild_training_modules(self):
        """根据 C/S 类型重建患者端训练卡片"""
        if not hasattr(self, 'training_grid_layout'):
            return
        # 清空现有卡片
        try:
            for i in reversed(range(self.training_grid_layout.count())):
                item = self.training_grid_layout.itemAt(i)
                w = item.widget() if item else None
                if w: w.setParent(None)
        except Exception:
            pass
        self.training_modules = {}
        # 重新构建
        if getattr(self, 'spine_type', 'C') == 'S':
            configs = [
                ('gray_rotation', '骨盆前后反转', 0, 0),
                ('blue_curvature_up', '脊柱曲率矫正·胸段', 0, 1),
                ('blue_curvature_down', '脊柱曲率矫正·腰段', 1, 0),
                ('gray_tilt', '骨盆左右倾斜', 1, 1),
                ('green_tilt', '肩部左右倾斜', 2, 0),
            ]
        else:
            configs = [
                ('gray_rotation', '骨盆前后反转', 0, 0),
                ('blue_curvature', '脊柱曲率矫正', 0, 1),
                ('gray_tilt', '骨盆左右倾斜', 1, 0),
                ('green_tilt', '肩部左右倾斜', 1, 1),
            ]
        for key, title, row, col in configs:
            card = self.create_training_module(key, title)
            self.training_modules[key] = card
            self.training_grid_layout.addWidget(card, row, col)

    def _all_controller_keys(self):
        return (['gray_rotation','blue_curvature_up','blue_curvature_down','gray_tilt','green_tilt']
                if getattr(self,'spine_type','C') == 'S'
                else ['gray_rotation','blue_curvature','gray_tilt','green_tilt'])

    def _controller_for_current_stage(self):
        """根据当前阶段和脊柱类型确定对应的控制器"""
        if getattr(self, 'spine_type', 'C') == 'S':
            # S型脊柱5阶段
            stage_controller_map = {
                1: 'gray_rotation',
                2: 'blue_curvature_up', 
                3: 'blue_curvature_down',
                4: 'gray_tilt',
                5: 'green_tilt'
            }
        else:
            # C型脊柱4阶段
            stage_controller_map = {
                1: 'gray_rotation',
                2: 'blue_curvature',
                3: 'gray_tilt', 
                4: 'green_tilt'
            }
        
        return stage_controller_map.get(self.current_stage, 'gray_rotation')

# 测试代码
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = PatientBlocksTab()
    window.show()
    window.resize(1200, 800)
    
    sys.exit(app.exec_())
