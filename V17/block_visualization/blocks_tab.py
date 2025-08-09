#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
积木可视化标签页（脊柱类型选择版）
===================================

新增功能：
1. 脊柱侧弯类型选择（C型/S型）
2. 根据类型动态调整阶段数量和描述
3. S型模式的4阶段支持
4. 传感器参数设置的动态显示控制
5. 集成前-k最大分配算法
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
                            QLabel, QGroupBox, QTextEdit, QGridLayout, QComboBox,
                            QFrame, QButtonGroup, QRadioButton)
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from block_visualization.block_control_panel import BlockControlPanel
from block_visualization.blocks_visualizer import BlocksVisualizer
from plot_widget import SensorPlotWidget
from block_visualization.training_recorder import TrainingRecorder
from event_recorder import EventRecorder
from .spine_type_selector import SpineTypeSelector

class BlocksTab(QWidget):
    """
    积木可视化标签页主类（脊柱类型选择版）
    ========================================
    
    新增功能：
    - 脊柱侧弯类型选择
    - 动态阶段管理
    - 传感器参数设置控制
    - 集成前-k最大分配算法
    """
    
    # ====== 对外信号 ======
    alert_signal = pyqtSignal(str)
    spine_type_changed = pyqtSignal(str)  # 新增：脊柱类型变更信号
    
    def __init__(self, sensor_count=6, parent=None):
        print("BlocksTab: 开始初始化...")
        super().__init__(parent)
        
        # ====== 基础配置 ======
        self.sensor_count = sensor_count
        self.stage = 1
        self.events_save_path = ""
        self.is_acquisition_active = False
        self.current_acquisition_id = None
        
        # ====== 新增：脊柱类型配置 ======
        self.spine_type = "C"  # 默认C型
        self.max_stages = 3    # 根据脊柱类型调整最大阶段数
        
        # ====== 阶段配置字典 ======
        self.stage_configs = {
            "C": {
                "max_stages": 3,
                "stage_descriptions": {
                    1: "阶段1：骨盆前后旋转（只调整骨盆前后翻转）",
                    2: "阶段2：脊柱曲率矫正（只调整脊柱曲率矫正）", 
                    3: "阶段3：关节平衡调整（调整骨盆和肩部左右倾斜）"
                },
                "stage_events": {
                    1: [("开始训练", "training_start"), ("完成阶段", "stage_complete")],
                    2: [("开始矫正", "correction_start"), ("矫正完成", "correction_complete")],
                    3: [("开始沉髋", "hip_start"), ("沉髋完成", "hip_complete"),
                        ("开始沉肩", "shoulder_start"), ("沉肩完成", "shoulder_complete")]
                },
                "active_selectors": {
                    1: ["gray_rotation"],
                    2: ["blue_curvature"],
                    3: ["gray_tilt", "green_tilt"]
                }
            },
            "S": {
                "max_stages": 4,
                "stage_descriptions": {
                    1: "阶段1：骨盆前后旋转（只调整骨盆前后翻转）",
                    2: "阶段2：腰椎曲率矫正（只调整腰椎曲率矫正）", 
                    3: "阶段3：胸椎曲率矫正（只调整胸椎曲率矫正）",
                    4: "阶段4：关节平衡调整（只调整肩部左右倾斜）"
                },
                "stage_events": {
                    1: [("开始训练", "training_start"), ("完成阶段", "stage_complete")],
                    2: [("开始腰椎矫正", "lumbar_correction_start"), ("腰椎矫正完成", "lumbar_correction_complete")],
                    3: [("开始胸椎矫正", "thoracic_correction_start"), ("胸椎矫正完成", "thoracic_correction_complete")],
                    4: [("开始肩部调整", "shoulder_adjustment_start"), ("肩部调整完成", "shoulder_adjustment_complete")]
                },
                "active_selectors": {
                    1: ["gray_rotation"],
                    2: ["blue_curvature"],  # 腰椎曲率矫正
                    3: ["gray_tilt"],      # 胸椎曲率矫正（修正）
                    4: ["green_tilt"]      # 只有肩部左右倾斜
                }
            }
        }
        
        # ====== 新增：前-k最大分配相关属性 ======
        self.stage_data_storage = {
            1: {'original_values': None, 'target_values': None},
            2: {'original_values': None, 'target_values': None},
            3: {'original_values': None, 'target_values': None},
            4: {'original_values': None, 'target_values': None}  # S型需要
        }
        
        # ====== 内存优化配置 ======
        self.plot_window_size = 5000
        self.update_interval = 100
        self.data_decimation_factor = 1
        self.last_plot_update = 0
        
        # ====== 绘图数据管理 ======
        self._plot_data = []
        self._plot_data_lock = False
        self._data_update_counter = 0
        self._plot_inited = False
        
        # ====== 性能监控 ======
        self.performance_monitor = {
            'plot_updates_per_sec': 0,
            'data_points_processed': 0,
            'memory_usage_mb': 0,
            'last_monitor_time': 0
        }
        
        # ====== 创建事件记录器 ======
        self.event_recorder = EventRecorder()
        self.event_recorder.set_num_sensors(self.sensor_count)
        
        # ====== 性能优化定时器 ======
        self.performance_timer = QTimer()
        self.performance_timer.timeout.connect(self._update_performance_stats)
        self.performance_timer.start(5000)
        
        # ====== 初始化流程 ======
        print("BlocksTab: 设置UI...")
        self.setup_ui()
        
        print("BlocksTab: 连接信号...")
        self.connect_signals()
        
        print("BlocksTab: 更新阶段UI...")
        self.update_stage_ui()
        
        # ====== 新增：连接前-k最大分配信号 ======
        self._connect_topk_signals()
        
        print("BlocksTab: 初始化完成")

    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        # 只读显示脊柱类型和方向
        self.spine_type_display = SpineTypeSelector(show_only=True)
        main_layout.addWidget(self.spine_type_display)
        
        # ====== 上半部分：可视化和数据曲线 ======
        top_layout = QHBoxLayout()
        
        # 左侧：积木3D可视化
        visualizer_group = self._create_visualizer_group()
        top_layout.addWidget(visualizer_group, 1)
        
        # 右侧：传感器数据曲线和事件标记
        chart_group = self._create_chart_with_events_group()
        top_layout.addWidget(chart_group, 3)
        
        main_layout.addLayout(top_layout, 2)
        
        # ====== 下半部分：控制和记录 ======
        bottom_layout = QHBoxLayout()

        # 创建训练记录器
        print("BlocksTab: 创建训练记录器...")
        self.training_recorder = TrainingRecorder()
        print("BlocksTab: 训练记录器创建完成")
        
        # 左侧：传感器参数设置
        params_group = self._create_sensor_params_group()
        bottom_layout.addWidget(params_group, 2)
        
        # 中间：阶段控制
        stage_group = self._create_stage_control_group()
        bottom_layout.addWidget(stage_group, 1)
        
        # 右侧：数据保存和训练记录
        record_group = self._create_data_record_group()
        bottom_layout.addWidget(record_group, 1)
        
        main_layout.addLayout(bottom_layout, 5)

    def _create_spine_type_selection_group(self):
        """创建脊柱类型和侧弯方向选择组"""
        group = QGroupBox("脊柱侧弯类型和方向选择")
        layout = QVBoxLayout()
        group.setLayout(layout)
        
        # 第一行：脊柱类型选择
        type_layout = QHBoxLayout()
        type_label = QLabel("脊柱类型:")
        type_layout.addWidget(type_label)
        
        # 创建脊柱类型单选按钮组
        self.spine_type_button_group = QButtonGroup()
        
        # C型脊柱侧弯
        self.c_type_radio = QRadioButton("C型脊柱侧弯")
        self.c_type_radio.setChecked(True)  # 默认选中
        self.c_type_radio.setToolTip("C型脊柱侧弯：3个阶段的传统训练模式")
        type_layout.addWidget(self.c_type_radio)
        
        # S型脊柱侧弯
        self.s_type_radio = QRadioButton("S型脊柱侧弯")
        self.s_type_radio.setToolTip("S型脊柱侧弯：4个阶段的扩展训练模式")
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
        self.c_left_radio.setChecked(True)  # 默认选中左凸
        
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
        info_label = QLabel("选择脊柱类型和方向将自动调整训练阶段和可视化效果")
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
            
            print(f"侧弯方向从 {old_direction} 变更为 {new_direction}")
            
            # 更新可视化器
            self._update_visualizer_for_spine_config()
            
            print(f"侧弯方向变更完成：{new_direction}")


    def _on_spine_type_changed(self, button):
        """处理脊柱类型变更"""
        if button == self.c_type_radio:
            new_type = "C"
            # 显示C型方向选择，隐藏S型方向选择
            self.c_direction_widget.setVisible(True)
            self.s_direction_widget.setVisible(False)
            # 设置默认方向
            self.c_left_radio.setChecked(True)
            self.spine_direction = "left"
        else:
            new_type = "S"
            # 显示S型方向选择，隐藏C型方向选择
            self.c_direction_widget.setVisible(False)
            self.s_direction_widget.setVisible(True)
            # 设置默认方向
            self.s_lumbar_left_radio.setChecked(True)
            self.spine_direction = "lumbar_left_thoracic_right"
        
        if new_type != self.spine_type:
            old_type = self.spine_type
            self.spine_type = new_type
            self.max_stages = self.stage_configs[new_type]["max_stages"]
            
            print(f"脊柱类型从 {old_type} 变更为 {new_type}")
            print(f"侧弯方向设置为: {self.spine_direction}")
            
            # 重置到第1阶段
            self.stage = 1
            
            # 更新传感器参数设置的标题和显示状态
            self._update_sensor_params_for_spine_type()
            
            # 更新阶段控制UI
            self.update_stage_ui()
            
            # 重新创建事件按钮
            self._create_all_event_buttons()
            self._update_event_buttons_for_stage(self.stage)
            
            # 更新可视化器
            self._update_visualizer_for_spine_config()
            
            # 发送信号
            self.spine_type_changed.emit(new_type)
            
            print(f"脊柱类型变更完成：{new_type}型，{self.max_stages}个阶段")


    def _update_visualizer_for_spine_config(self):
        """根据脊柱类型和方向更新可视化器"""
        if hasattr(self, 'visualizer'):
            # 设置脊柱类型和方向
            self.visualizer.set_spine_config(self.spine_type, self.spine_direction)
            self.visualizer.update()
            print(f"可视化器已更新：{self.spine_type}型，方向={self.spine_direction}")

    def get_spine_direction(self):
        """获取当前脊柱侧弯方向"""
        return self.spine_direction

    def set_spine_config(self, spine_type, spine_direction):
        self.spine_type = spine_type
        self.spine_direction = spine_direction
        self.spine_type_display.set_spine_config(spine_type, spine_direction)
        self.max_stages = self.stage_configs[spine_type]["max_stages"]
        # 立即刷新参数块标题
        self._update_sensor_params_for_spine_type()
        self._update_visualizer_for_spine_config()
        print(f"tab2脊柱配置已设置为：{spine_type}型，方向={spine_direction}")

    def _create_visualizer_group(self):
        """创建积木可视化组"""
        group = QGroupBox("脊柱积木图形示例")
        layout = QVBoxLayout()
        group.setLayout(layout)
        
        # 3D积木可视化器
        self.visualizer = BlocksVisualizer()
        self.visualizer.setMinimumSize(250, 200)
        layout.addWidget(self.visualizer)
        
        return group

    def _create_chart_with_events_group(self):
        """创建带事件标记的数据曲线组"""
        group = QGroupBox("传感器数据曲线和事件标记")
        layout = QVBoxLayout()
        group.setLayout(layout)
        
        # 使用内存优化的绘图组件
        self.plot_widget = SensorPlotWidget()
        self.plot_widget.setMinimumHeight(300)
        
        # 设置绘图窗口大小限制
        if hasattr(self.plot_widget, 'set_max_data_points'):
            self.plot_widget.set_max_data_points(self.plot_window_size)
        
        layout.addWidget(self.plot_widget)
        
        return group
    
    def set_external_plot_widget(self, plot_widget):
        """设置外部绘图控件"""
        if hasattr(self, 'plot_widget'):
            parent_layout = self.plot_widget.parent().layout()
            if parent_layout:
                parent_layout.removeWidget(self.plot_widget)
                self.plot_widget.deleteLater()
                
                # 设置新的绘图控件的内存限制
                if hasattr(plot_widget, 'set_max_data_points'):
                    plot_widget.set_max_data_points(self.plot_window_size)
                
                parent_layout.addWidget(plot_widget)
                self.plot_widget = plot_widget
                print("BlocksTab: 外部绘图控件设置完成")

    def _create_sensor_params_group(self):
        """创建传感器参数设置组"""
        group = QGroupBox("传感器参数设置")
        layout = QVBoxLayout()
        group.setLayout(layout)
        
        print("BlocksTab: 创建积木控制面板...")
        self.control_panel = BlockControlPanel(self.sensor_count)
        print("BlocksTab: 积木控制面板创建完成")
        
        # 横向排列传感器选择器
        sensors_layout = QHBoxLayout()
        
        if hasattr(self.control_panel, 'gray_rotation'):
            sensors_layout.addWidget(self.control_panel.gray_rotation)
        if hasattr(self.control_panel, 'blue_curvature'):
            sensors_layout.addWidget(self.control_panel.blue_curvature)
        if hasattr(self.control_panel, 'gray_tilt'):
            sensors_layout.addWidget(self.control_panel.gray_tilt)
        if hasattr(self.control_panel, 'green_tilt'):
            sensors_layout.addWidget(self.control_panel.green_tilt)
        
        layout.addLayout(sensors_layout)
        
        # 【保持原有】保存为sensor_params属性，以便主窗口能够访问
        self.sensor_params = group
        
        # 初始化传感器参数设置的标题和显示状态
        self._update_sensor_params_for_spine_type()
        
        return group


    def _update_sensor_params_for_spine_type(self):
        """根据脊柱类型更新传感器参数设置的标题和显示状态"""
        if not hasattr(self, 'control_panel'):
            return
        if self.spine_type == "C":
            titles = {
                "gray_rotation": "骨盆前后翻转",
                "blue_curvature": "脊柱曲率矫正",
                "gray_tilt": "骨盆左右倾斜",
                "green_tilt": "肩部左右倾斜"
            }
        else:  # S型脊柱
            titles = {
                "gray_rotation": "骨盆前后翻转",      # 阶段1
                "blue_curvature": "腰椎曲率矫正",     # 阶段2
                "gray_tilt": "胸椎曲率矫正",         # 阶段3
                "green_tilt": "肩部左右倾斜"         # 阶段4
            }
        # 显示所有选择器
        self.control_panel.gray_rotation.setVisible(True)
        self.control_panel.blue_curvature.setVisible(True)
        self.control_panel.gray_tilt.setVisible(True)
        self.control_panel.green_tilt.setVisible(True)
        # 设置标题
        for selector_name, title in titles.items():
            selector = getattr(self.control_panel, selector_name)
            selector.setTitle(title)
        self._update_sensor_params_highlight()
        print(f"传感器参数设置已更新为{self.spine_type}型脊柱模式")

    def _update_sensor_params_highlight(self):
        """根据脊柱类型和当前阶段更新传感器参数设置的高亮状态"""
        if not hasattr(self, 'control_panel'):
            return
        print(f"更新传感器参数高亮 - 脊柱类型: {self.spine_type}, 阶段: {self.stage}")
        self.control_panel.gray_rotation.set_highlighted(False)
        self.control_panel.blue_curvature.set_highlighted(False)
        self.control_panel.gray_tilt.set_highlighted(False)
        self.control_panel.green_tilt.set_highlighted(False)
        if self.spine_type == "C":
            if self.stage == 1:
                self.control_panel.gray_rotation.set_highlighted(True)
            elif self.stage == 2:
                self.control_panel.blue_curvature.set_highlighted(True)
            elif self.stage == 3:
                self.control_panel.gray_tilt.set_highlighted(True)
                self.control_panel.green_tilt.set_highlighted(True)
        else:  # S型
            if self.stage == 1:
                self.control_panel.gray_rotation.set_highlighted(True)
            elif self.stage == 2:
                self.control_panel.blue_curvature.set_highlighted(True)
            elif self.stage == 3:
                self.control_panel.gray_tilt.set_highlighted(True)
            elif self.stage == 4:
                self.control_panel.green_tilt.set_highlighted(True)
        print(f"高亮状态已更新")

    
    def _create_stage_control_group(self):
        """创建阶段控制组"""
        group = QGroupBox("阶段控制")
        group.setMinimumWidth(280)
        layout = QVBoxLayout()
        group.setLayout(layout)
        # 阶段切换部分
        stage_control_layout = QVBoxLayout()
        # 阶段切换按钮
        stage_buttons_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ 上一阶段")
        self.next_btn = QPushButton("下一阶段 ▶")
        stage_buttons_layout.addWidget(self.prev_btn)
        stage_buttons_layout.addWidget(self.next_btn)
        stage_control_layout.addLayout(stage_buttons_layout)
        # 当前阶段显示
        self.stage_label = QLabel("阶段1: 骨盆前后翻转")
        self.stage_label.setWordWrap(True)
        self.stage_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                border: 1px solid #ddd;
                background-color: #f9f9f9;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        stage_control_layout.addWidget(QLabel("当前阶段:"))
        stage_control_layout.addWidget(self.stage_label)
        # 连接信号
        self.prev_btn.clicked.connect(self.prev_stage)
        self.next_btn.clicked.connect(self.next_stage)
        layout.addLayout(stage_control_layout)
        # 事件记录部分
        events_layout = QVBoxLayout()
        events_layout.addWidget(QLabel("训练事件记录:"))
        # 事件按钮容器
        self.event_buttons_widget = QWidget()
        self.event_buttons_layout = QGridLayout()
        self.event_buttons_widget.setLayout(self.event_buttons_layout)
        # 创建所有事件按钮
        self.event_buttons = {}
        self._create_all_event_buttons()
        events_layout.addWidget(self.event_buttons_widget)
        layout.addLayout(events_layout)
        # 更新事件按钮显示
        self._update_event_buttons_for_stage(self.stage)
        return group

    def _create_data_record_group(self):
        """创建数据保存和训练记录组"""
        group = QGroupBox("训练记录")
        group.setMinimumWidth(280)
        layout = QVBoxLayout()
        group.setLayout(layout)
        
        # 训练记录显示
        self.record_display = QTextEdit()
        self.record_display.setMaximumHeight(500)
        self.record_display.setReadOnly(True)
        self.record_display.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
                font-size: 10px;
                background-color: #f9f9f9;
            }
        """)
        
        layout.addWidget(QLabel("训练记录详情:"))
        layout.addWidget(self.record_display)
        
        # 导出功能
        export_layout = QHBoxLayout()
        self.export_btn = QPushButton("导出记录")
        self.clear_btn = QPushButton("清空记录")
        
        self.export_btn.clicked.connect(self._export_records)
        self.clear_btn.clicked.connect(self._clear_records)
        
        export_layout.addWidget(self.export_btn)
        export_layout.addWidget(self.clear_btn)
        layout.addLayout(export_layout)
        
        return group

    def _create_all_event_buttons(self):
        """根据脊柱类型创建所有阶段的事件按钮"""
        # 清空现有按钮
        if hasattr(self, 'event_buttons'):
            for stage_buttons in self.event_buttons.values():
                for btn in stage_buttons:
                    btn.deleteLater()
        self.event_buttons = {}
        # 清空布局
        if hasattr(self, 'event_buttons_layout'):
            for i in reversed(range(self.event_buttons_layout.count())): 
                self.event_buttons_layout.itemAt(i).widget().setParent(None)
        # 获取当前脊柱类型的事件配置
        current_config = self.stage_configs[self.spine_type]
        stage_events = current_config["stage_events"]
        print(f"创建事件按钮 - 脊柱类型: {self.spine_type}, 阶段数: {current_config['max_stages']}")
        # 创建所有事件按钮
        for stage, events in stage_events.items():
            stage_buttons = []
            for i, (event_name, event_code) in enumerate(events):
                btn = QPushButton(event_name)
                btn.clicked.connect(lambda checked, code=event_code, name=event_name: 
                                self._record_event_with_topk(name, code))
                # 设置按钮样式
                btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 8px;
                        margin: 2px;
                        border: 1px solid #ccc;
                        border-radius: 3px;
                        background-color: #f8f8f8;
                    }
                    QPushButton:hover {
                        background-color: #e8e8e8;
                    }
                    QPushButton:pressed {
                        background-color: #d8d8d8;
                    }
                """)
                stage_buttons.append(btn)
                # 添加到布局（2列显示）
                row = i // 2
                col = i % 2
                self.event_buttons_layout.addWidget(btn, row, col)
                # 初始隐藏
                btn.hide()
                print(f"  创建按钮 - 阶段{stage}: {event_name}")
            self.event_buttons[stage] = stage_buttons

    def _update_event_buttons_for_stage(self, stage):
        """根据当前阶段更新事件按钮显示"""
        # 隐藏所有按钮
        for stage_num, buttons in self.event_buttons.items():
            for btn in buttons:
                btn.hide()
        # 显示当前阶段的按钮
        if stage in self.event_buttons:
            for btn in self.event_buttons[stage]:
                btn.show()
            print(f"显示阶段{stage}的事件按钮")

    # ================================================================
    # 阶段管理方法（修改版）
    # ================================================================
    
    def prev_stage(self):
        """切换到上一个训练阶段"""
        if self.stage > 1:
            old_stage = self.stage
            self.stage -= 1
            self.update_stage_ui()  # 这会调用_update_sensor_params_highlight
            
            if hasattr(self, 'training_recorder') and self.training_recorder:
                self.training_recorder.set_stage(self.stage)
            
            print(f"切换阶段: {old_stage} → {self.stage}")

    def next_stage(self):
        """切换到下一个训练阶段"""
        if self.stage < self.stage_configs[self.spine_type]["max_stages"]:
             old_stage = self.stage
             self.stage += 1
             self.update_stage_ui()  # 这会调用_update_sensor_params_highlight
             if hasattr(self, 'training_recorder') and self.training_recorder:
                 self.training_recorder.set_stage(self.stage)
             print(f"切换阶段: {old_stage} → {self.stage}")

    def set_stage(self, stage):
        """直接设置训练阶段"""
        if 1 <= stage <= self.stage_configs[self.spine_type]["max_stages"]:
             self.stage = stage
             self.update_stage_ui()
             if hasattr(self, 'training_recorder') and self.training_recorder:
                 self.training_recorder.set_stage(self.stage)
             print(f"设置阶段: {stage}")

    def get_stage(self):
        """获取当前训练阶段"""
        return self.stage
    
    def update_stage_ui(self):
        """更新训练阶段UI显示"""
        # 强制刷新参数块标题
        self._update_sensor_params_for_spine_type()
        # 设置阶段默认值
        self.control_panel.set_stage_defaults(self.stage, spine_type=self.spine_type)
        # 更新传感器参数设置的高亮状态
        self._update_sensor_params_highlight()
        # 更新阶段标签文本
        current_config = self.stage_configs[self.spine_type]
        stage_description = current_config["stage_descriptions"].get(
            self.stage, f"阶段{self.stage}: 未知阶段"
        )
        self.stage_label.setText(stage_description)
        # 设置阶段标签样式
        stage_colors = {1: "#FF6B6B", 2: "#4ECDC4", 3: "#45B7D1", 4: "#96CEB4"}
        color = stage_colors.get(self.stage, "#333333")
        self.stage_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                font-size: 14px;
                padding: 5px;
                border-left: 3px solid {color};
                background-color: rgba(255, 255, 255, 0.1);
            }}
        """)
        # 更新上一阶段/下一阶段按钮状态
        self.prev_btn.setEnabled(self.stage > 1)
        self.next_btn.setEnabled(self.stage < self.stage_configs[self.spine_type]["max_stages"])
        # 强制重建事件按钮，确保按钮数量和内容与配置一致
        self._create_all_event_buttons()
        # 更新事件按钮显示
        self._update_event_buttons_for_stage(self.stage)
        # 同步阶段到训练记录器
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.set_stage(self.stage)
        if hasattr(self, 'visualizer'):
            self.visualizer.set_current_stage(self.stage)
            self.visualizer.update()
        print(f"阶段UI更新完成 - {self.spine_type}型阶段{self.stage}")

    # ================================================================
    # 前-k最大分配相关方法（保持原有功能）
    # ================================================================

    def _connect_topk_signals(self):
        """连接前-k最大分配相关信号"""
        try:
            # 连接各个传感器选择器的权重自动分配完成信号
            selectors = [
                ('gray_rotation', self.control_panel.gray_rotation),
                ('blue_curvature', self.control_panel.blue_curvature),
                ('gray_tilt', self.control_panel.gray_tilt),
                ('green_tilt', self.control_panel.green_tilt)
            ]
            
            for selector_name, selector in selectors:
                if hasattr(selector, 'weights_auto_assigned'):
                    selector.weights_auto_assigned.connect(
                        lambda weights, sn=selector_name: self._on_weights_auto_assigned(sn, weights)
                    )
                    print(f"已连接 {selector_name} 的权重自动分配信号")
            
        except Exception as e:
            print(f"连接前-k最大分配信号时出错: {e}")

    def _record_event_with_topk(self, event_name, event_code=None):
        """记录训练事件（集成前-k最大分配）"""
        print(f"\n=== 记录事件（前-k最大分配版）===")
        print(f"事件名称: {event_name}")
        print(f"事件代码: {event_code}")
        print(f"当前阶段: {self.stage}")
        print(f"脊柱类型: {self.spine_type}")
        
        # 获取当前传感器数据
        current_sensor_data = self.event_recorder.current_sensor_data
        if not current_sensor_data:
            print("警告: 当前没有传感器数据")
            return
        
        # 确定阶段键和传感器选择器
        stage_key, selector = self._get_stage_key_and_selector(event_name, event_code)
        if not selector:
            print(f"未找到对应的传感器选择器")
            # 回退到原始记录方法
            self._record_event(event_name, event_code)
            return
        
        print(f"阶段键: {stage_key}")
        print(f"传感器选择器: {type(selector).__name__}")
        
        # 判断是原始值还是目标值事件
        is_original_event = self._is_original_event(event_name, event_code)
        is_target_event = self._is_target_event(event_name, event_code)
        
        print(f"是原始值事件: {is_original_event}")
        print(f"是目标值事件: {is_target_event}")
        
        if is_original_event:
            # 存储原始值
            selector.store_original_values(current_sensor_data)
            self.stage_data_storage[stage_key]['original_values'] = current_sensor_data
            print("原始值已存储")
            
            # 记录原始值事件
            self._record_event(event_name, event_code)
            
        elif is_target_event:
            # 存储目标值
            selector.store_target_values(current_sensor_data)
            self.stage_data_storage[stage_key]['target_values'] = current_sensor_data
            print("目标值已存储")
            
            # 目标值事件不立即记录，等待权重自动分配完成后再记录
            print("等待权重自动分配完成...")
            
        else:
            # 其他事件，使用原始记录方法
            self._record_event(event_name, event_code)
        
        print("=== 事件记录完成 ===\n")

    def _get_stage_key_and_selector(self, event_name, event_code):
        """获取阶段键和对应的传感器选择器（支持S型4阶段）"""
        try:
            current_config = self.stage_configs[self.spine_type]
            active_selectors = current_config["active_selectors"]
            
            if self.stage in active_selectors:
                # 获取当前阶段的活跃选择器
                active_selector_names = active_selectors[self.stage]
                if active_selector_names:
                    # 根据事件名称选择特定的选择器
                    selector_name = self._get_selector_for_event(event_name, event_code, active_selector_names)
                    selector = getattr(self.control_panel, selector_name, None)
                    return self.stage, selector
            
            return None, None
            
        except Exception as e:
            print(f"获取阶段键和选择器时出错: {e}")
            return None, None

    def _get_selector_for_event(self, event_name, event_code, active_selector_names):
        """根据事件名称确定具体的选择器"""
        # 沉肩事件对应 green_tilt
        if "沉肩" in event_name or "shoulder" in str(event_code):
            if "green_tilt" in active_selector_names:
                return "green_tilt"
        
        # 沉髋事件对应 gray_tilt
        if "沉髋" in event_name or "hip" in str(event_code):
            if "gray_tilt" in active_selector_names:
                return "gray_tilt"
        
        # 默认使用第一个活跃选择器
        return active_selector_names[0]

    def _is_original_event(self, event_name, event_code):
        """判断是否为原始值事件（支持S型事件）"""
        original_events = [
            "开始训练", "开始矫正", "开始沉髋", "开始沉肩",
            "开始腰椎矫正", "开始胸椎矫正", "开始肩部调整",
            "training_start", "correction_start", "hip_start", "shoulder_start",
            "lumbar_correction_start", "thoracic_correction_start", "shoulder_adjustment_start"
        ]
        
        return (event_name in original_events) or (event_code in original_events)

    def _is_target_event(self, event_name, event_code):
        """判断是否为目标值事件（支持S型事件）"""
        target_events = [
            "完成阶段", "矫正完成", "沉髋完成", "沉肩完成",
            "腰椎矫正完成", "胸椎矫正完成", "肩部调整完成",
            "stage_complete", "correction_complete", "hip_complete", "shoulder_complete",
            "lumbar_correction_complete", "thoracic_correction_complete", "shoulder_adjustment_complete"
        ]
        
        return (event_name in target_events) or (event_code in target_events)

    def _on_weights_auto_assigned(self, selector_name, weights):
        """处理权重自动分配完成事件"""
        try:
            print(f"\n=== 权重自动分配完成 ===")
            print(f"传感器选择器: {selector_name}")
            print(f"权重: {weights[:3]}...")
            
            # 获取当前传感器数据
            current_sensor_data = self.event_recorder.current_sensor_data
            if not current_sensor_data:
                print("警告: 当前没有传感器数据")
                return
            
            # 确定事件名称和阶段信息
            event_name, stage_key = self._get_target_event_name_for_selector(selector_name)
            if not event_name:
                print(f"未找到 {selector_name} 对应的目标事件名称")
                return
            
            # 获取误差范围
            selector = self._get_selector_by_name(selector_name)
            error_range = selector.get_error_range() if selector else 0.1
            
            print(f"目标事件名称: {event_name}")
            print(f"阶段键: {stage_key}")
            print(f"误差范围: {error_range}")
            
            # 记录权重更新事件
            success = self.event_recorder.record_event(
                event_name=event_name,
                stage=f"阶段{self.stage}",
                additional_data={
                    'event_code': event_name.lower().replace(' ', '_'),
                    'sensor_weights': weights,
                    'error_range': error_range,
                    'auto_assigned': True,
                    'weight_update': True,
                    'selector_name': selector_name,
                    'spine_type': self.spine_type
                }
            )
            
            if success:
                # 更新显示
                from datetime import datetime
                current_time = datetime.now()
                relative_time = 0.0
                if self.event_recorder.acquisition_start_time:
                    time_diff = current_time - self.event_recorder.acquisition_start_time
                    relative_time = time_diff.total_seconds()
                
                record_text = f"[{relative_time:.1f}s] {self.spine_type}型-阶段{self.stage} - {event_name} (权重自动分配)\n"
                record_text += f"  选择器: {selector_name}\n"
                record_text += f"  自动分配权重: {[f'{w:.3f}' for w in weights[:5]]}\n"
                record_text += f"  误差范围: {error_range:.3f}\n"
                record_text += "─" * 50 + "\n"
                
                self.record_display.append(record_text)
                self.record_display.verticalScrollBar().setValue(
                    self.record_display.verticalScrollBar().maximum()
                )
                
                print(f"权重更新事件已记录: {event_name}")
            else:
                print(f"权重更新事件记录失败: {event_name}")
            
            print("=== 权重自动分配处理完成 ===\n")
            
        except Exception as e:
            print(f"处理权重自动分配时出错: {e}")

    def _get_target_event_name_for_selector(self, selector_name):
        """根据传感器选择器名称获取对应的目标事件名称（支持S型）"""
        current_config = self.stage_configs[self.spine_type]
        
        # 根据脊柱类型和当前阶段确定事件名称
        if self.spine_type == "C":
            selector_to_event = {
                'gray_rotation': ('完成阶段', 1),
                'blue_curvature': ('矫正完成', 2),
                'gray_tilt': ('沉髋完成', 3),
                'green_tilt': ('沉肩完成', 3)  # 明确指定green_tilt对应沉肩
            }
        else:  # S型
            selector_to_event = {
                'gray_rotation': ('完成阶段', 1),
                'blue_curvature': ('腰椎矫正完成' if self.stage == 2 else '胸椎矫正完成', self.stage),
                'gray_tilt': ('胸椎矫正完成', 3),
                'green_tilt': ('肩部调整完成', 4)
            }
        
        return selector_to_event.get(selector_name, (None, None))

    def _get_selector_by_name(self, selector_name):
        """根据名称获取传感器选择器实例"""
        try:
            return getattr(self.control_panel, selector_name, None)
        except:
            return None

    def get_stage_data_storage(self):
        """获取阶段数据存储状态"""
        return self.stage_data_storage.copy()

    def clear_stage_data_storage(self):
        """清空阶段数据存储"""
        for stage_key in self.stage_data_storage:
            self.stage_data_storage[stage_key] = {'original_values': None, 'target_values': None}
        
        # 同时清空传感器选择器中的数据
        selectors = [
            self.control_panel.gray_rotation,
            self.control_panel.blue_curvature,
            self.control_panel.gray_tilt,
            self.control_panel.green_tilt
        ]
        
        for selector in selectors:
            if hasattr(selector, 'clear_stored_data'):
                selector.clear_stored_data()
        
        print("阶段数据存储已清空")

    # ================================================================
    # 脊柱类型相关的便捷方法
    # ================================================================
    
    def get_spine_type(self):
        """获取当前脊柱类型"""
        return self.spine_type
    
    def get_max_stages(self):
        """获取当前脊柱类型的最大阶段数"""
        return self.max_stages
    
    def get_stage_description(self, stage=None):
        """获取阶段描述"""
        if stage is None:
            stage = self.stage
        current_config = self.stage_configs[self.spine_type]
        return current_config["stage_descriptions"].get(stage, f"阶段{stage}: 未知阶段")
    
    def get_active_selectors_for_stage(self, stage=None):
        """获取指定阶段的活跃传感器选择器"""
        if stage is None:
            stage = self.stage
        current_config = self.stage_configs[self.spine_type]
        return current_config["active_selectors"].get(stage, [])
    
    def is_s_type_spine(self):
        """判断是否为S型脊柱"""
        return self.spine_type == "S"
    
    def is_c_type_spine(self):
        """判断是否为C型脊柱"""
        return self.spine_type == "C"

    # ================================================================
    # 内存优化的数据处理方法（保持原有）
    # ================================================================
    
    def process_sensor_data(self, data_values):
        """处理传感器数据（内存优化版）"""
        # 验证数据有效性
        if not self._validate_sensor_data(data_values):
            return
        
        # 更新数据计数器
        self._data_update_counter += 1
        self.performance_monitor['data_points_processed'] += 1
        
        # 更新事件记录器的当前传感器数据
        self.event_recorder.set_current_sensor_data(data_values)
        
        # 更新控制面板传感器值
        if hasattr(self, 'control_panel'):
            self.control_panel.process_sensor_data(data_values)
        
        # 内存优化的绘图数据更新
        self._update_plot_data_optimized(data_values)
        
        # 根据抽样因子决定是否更新可视化
        if self._data_update_counter % self.data_decimation_factor == 0:
            self._update_visualization_optimized()
    
    def _update_plot_data_optimized(self, data_values):
        """内存优化的绘图数据更新"""
        # 简单的锁机制，避免并发问题
        if self._plot_data_lock:
            return
        
        try:
            self._plot_data_lock = True
            
            # 添加数据到固定大小的绘图缓冲区
            self._plot_data.append(data_values)
            
            # 保持固定窗口大小
            if len(self._plot_data) > self.plot_window_size:
                # 移除最老的数据点
                excess_count = len(self._plot_data) - self.plot_window_size
                self._plot_data = self._plot_data[excess_count:]
            
        finally:
            self._plot_data_lock = False
    
    def _update_visualization_optimized(self):
        """内存优化的可视化更新"""
        import time
        current_time = time.time()
        
        # 限制更新频率，避免过度绘图
        if current_time - self.last_plot_update < self.update_interval / 1000.0:
            return
        
        try:
            # 初始化曲线图设置（仅首次）
            if not self._plot_inited:
                if self._plot_data:
                    self._init_plot_widget_optimized(self._plot_data[0])
                    self._plot_inited = True
            
            # 获取优化的绘图数据
            plot_data = self._get_optimized_plot_data()
            
            # 更新曲线图显示
            if plot_data and hasattr(self, 'plot_widget'):
                self.plot_widget.update_plot(plot_data)
                self.performance_monitor['plot_updates_per_sec'] += 1
            
            self.last_plot_update = current_time
            
        except Exception as e:
            print(f"可视化更新失败: {e}")
    
    def _get_optimized_plot_data(self):
        """获取优化的绘图数据"""
        if self._plot_data_lock or not self._plot_data:
            return []
        
        try:
            # 如果数据量仍然很大，进行进一步抽样
            if len(self._plot_data) > 2000:
                # 每n个点取一个
                step = len(self._plot_data) // 2000
                sampled_data = self._plot_data[::step]
                return sampled_data
            else:
                return self._plot_data.copy()
                
        except Exception as e:
            print(f"获取绘图数据失败: {e}")
            return []
    
    def _init_plot_widget_optimized(self, sample_data):
        """内存优化的绘图组件初始化"""
        try:
            num_sensors = len(sample_data) - 1  # 减去时间戳列
            colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k'] * 3
            
            if hasattr(self.plot_widget, 'setup_curves'):
                self.plot_widget.setup_curves(num_sensors, colors)
            
            # 设置绘图组件的内存限制
            if hasattr(self.plot_widget, 'set_max_data_points'):
                self.plot_widget.set_max_data_points(self.plot_window_size)
                
            print(f"绘图组件初始化完成，传感器数量: {num_sensors}")
            
        except Exception as e:
            print(f"绘图组件初始化失败: {e}")
    
    def _validate_sensor_data(self, data_values):
        """验证传感器数据的有效性"""
        if not isinstance(data_values, (list, tuple)):
            return False
        
        if len(data_values) < 2:
            return False
        
        try:
            for value in data_values:
                float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _update_performance_stats(self):
        """更新性能统计"""
        try:
            import time
            current_time = time.time()
            
            # 计算更新频率
            if self.performance_monitor['last_monitor_time'] > 0:
                time_diff = current_time - self.performance_monitor['last_monitor_time']
                if time_diff > 0:
                    # 计算每秒绘图更新次数
                    updates_per_sec = self.performance_monitor['plot_updates_per_sec'] / time_diff
                    
                    # 重置计数器
                    self.performance_monitor['plot_updates_per_sec'] = 0
                    self.performance_monitor['last_monitor_time'] = current_time
                    
                    # 估算内存使用
                    data_memory = len(self._plot_data) * len(self._plot_data[0]) * 8 if self._plot_data else 0
                    memory_mb = data_memory / (1024 * 1024)
                    self.performance_monitor['memory_usage_mb'] = memory_mb
                    
                    # 打印性能统计（每30秒一次）
                    if self._data_update_counter % 3000 == 0:
                        print(f"绘图性能: {updates_per_sec:.1f} 更新/秒, "
                              f"内存: {memory_mb:.1f}MB, "
                              f"数据点: {len(self._plot_data)}")
            else:
                self.performance_monitor['last_monitor_time'] = current_time
                
        except Exception as e:
            print(f"性能统计更新失败: {e}")

    # ================================================================
    # 事件记录相关方法（保持原有）
    # ================================================================
    
    def set_events_save_path(self, path):
        """设置事件文件保存路径"""
        self.events_save_path = path
        self.event_recorder.set_events_file_path(path)
        print(f"事件文件保存路径已设置为: {path}")

    def start_acquisition(self):
        """开始数据采集"""
        from datetime import datetime
        self.is_acquisition_active = True
        self.current_acquisition_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.event_recorder.start_new_acquisition()
        
        # 清空绘图数据
        self.clear_plot_data()
        
        # 清空阶段数据存储
        self.clear_stage_data_storage()
        
        print(f"开始新的数据采集，ID: {self.current_acquisition_id}")

    def stop_acquisition(self):
        """停止数据采集"""
        self.is_acquisition_active = False
        self.current_acquisition_id = None
        print("数据采集已停止")

    def _record_event(self, event_name, event_code=None):
        """记录训练事件（原有方法，保持兼容）"""
        from datetime import datetime
        
        # 获取当前阶段对应控制器的权重信息和误差范围
        sensor_weights, error_range = self._get_current_stage_weights_and_error_range(event_name, event_code)
        
        # 更新传感器参数设置模块中的原始值和最佳值
        self._update_sensor_values(event_name, event_code)
        
        # 使用事件记录器记录事件
        success = self.event_recorder.record_event(
            event_name=event_name,
            stage=f"{self.spine_type}型-阶段{self.stage}",
            additional_data={
                'event_code': event_code or event_name.lower().replace(' ', '_'),
                'sensor_weights': sensor_weights,
                'error_range': error_range,
                'spine_type': self.spine_type,
                'max_stages': self.max_stages
            }
        )
        
        if success:
            # 显示在记录窗口
            current_time = datetime.now()
            relative_time = 0.0
            if self.event_recorder.acquisition_start_time:
                time_diff = current_time - self.event_recorder.acquisition_start_time
                relative_time = time_diff.total_seconds()
            
            record_text = f"[{relative_time:.1f}s] {self.spine_type}型-阶段{self.stage} - {event_name}\n"
            
            current_sensor_data = self.event_recorder.current_sensor_data
            if current_sensor_data:
                record_text += f"  原始数据: {[f'{x:.2f}' for x in current_sensor_data[1:]]}\n"
            
            record_text += f"  传感器权重: {[f'{w:.1f}' for w in sensor_weights]}\n"
            record_text += f"  误差范围: {error_range:.2f}\n"
            record_text += "─" * 50 + "\n"
            
            self.record_display.append(record_text)
            self.record_display.verticalScrollBar().setValue(
                self.record_display.verticalScrollBar().maximum()
            )
            
            # 在曲线图上添加事件标记
            if hasattr(self, 'plot_widget') and current_sensor_data:
                current_time_from_sensor = current_sensor_data[0] if current_sensor_data else 0
                self._add_event_marker(current_time_from_sensor, event_name)
            
            # 记录到训练记录器
            if hasattr(self, 'training_recorder') and self.training_recorder:
                record_key = f"{self.spine_type}_stage{self.stage}_{event_code or event_name}"
                self.training_recorder.add_record_data(record_key, {
                    'timestamp': relative_time,
                    'stage': self.stage,
                    'spine_type': self.spine_type,
                    'event_name': event_name,
                    'event_code': event_code or event_name.lower().replace(' ', '_'),
                    'raw_sensor_data': current_sensor_data,
                    'sensor_weights': sensor_weights,
                    'error_range': error_range,
                    'visualization_state': self.get_visualization_state()
                })
            
            print(f"已记录事件: {event_name} ({self.spine_type}型-阶段{self.stage}) - 相对时间: {relative_time:.1f}s")
        else:
            print(f"记录事件失败: {event_name}")

    def _get_current_stage_weights_and_error_range(self, event_name=None, event_code=None):
        """获取当前阶段对应控制器的传感器权重和误差范围（支持S型）"""
        weights = [0.0] * self.sensor_count
        error_range = 0.1
        
        try:
            current_config = self.stage_configs[self.spine_type]
            active_selectors = current_config["active_selectors"]
            
            if self.stage in active_selectors:
                selector_names = active_selectors[self.stage]
                if selector_names:
                    # 根据事件名称选择特定的选择器
                    target_selector = self._get_selector_for_event(event_name, event_code, selector_names)
                    controller = getattr(self.control_panel, target_selector, None)
                    
                    if controller:
                        weights = self._get_controller_weights(controller)
                        error_range = controller.get_error_range()
                        print(f"{self.spine_type}型-阶段{self.stage}权重记录: {target_selector} (事件: {event_name})")
                    
                    # 如果是多选择器阶段且不是特定事件，合并权重
                    if len(selector_names) > 1 and not ("沉肩" in str(event_name) or "沉髋" in str(event_name)):
                        total_weights = weights[:]
                        for other_selector_name in selector_names:
                            if other_selector_name != target_selector:
                                other_controller = getattr(self.control_panel, other_selector_name, None)
                                if other_controller:
                                    other_weights = self._get_controller_weights(other_controller)
                                    for i in range(len(total_weights)):
                                        if i < len(other_weights):
                                            total_weights[i] += other_weights[i]
                                    error_range = (error_range + other_controller.get_error_range()) / 2
                        weights = total_weights
                        print(f"→ 合并多个选择器权重: {selector_names}")
                            
        except Exception as e:
            print(f"获取权重和误差范围失败: {e}")
        
        return weights, error_range

    def _get_controller_weights(self, controller):
        """获取指定控制器的传感器权重"""
        weights = [0.0] * self.sensor_count
        
        try:
            for i in range(self.sensor_count):
                if i < len(controller.sensor_checkboxes):
                    if controller.sensor_checkboxes[i].isChecked():
                        if i < len(controller.weight_spinboxes):
                            weights[i] = controller.weight_spinboxes[i].value()
        except Exception as e:
            print(f"获取控制器权重时出错: {e}")
            
        return weights

    def _add_event_marker(self, timestamp, event_name):
        """在曲线图上添加事件标记"""
        if hasattr(self, 'plot_widget'):
            stage_name = self.get_stage_description()
            
            if hasattr(self.plot_widget, 'add_event_marker'):
                self.plot_widget.add_event_marker(
                    event_name,
                    timestamp,
                    f"{self.spine_type}型-{stage_name}: {event_name}"
                )

    def _clear_records(self):
        """清空训练记录"""
        self.record_display.clear()
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.recording_data = {}
        # 清空阶段数据存储
        self.clear_stage_data_storage()
        print("训练记录已清空")

    def _export_records(self):
        """导出训练记录"""
        if not hasattr(self, 'training_recorder') or not self.training_recorder:
            print("错误: training_recorder 未初始化，无法导出记录")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", "训练记录器未初始化，无法导出记录")
            return
        
        from PyQt5.QtWidgets import QFileDialog
        import os
        
        default_path = os.path.join(os.getcwd(), f"training_records_{self.spine_type}_{self.stage}.xlsx")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出训练记录", default_path, "Excel文件 (*.xlsx)"
        )
        
        if file_path:
            try:
                self.training_recorder.save_records(file_path)
                print(f"训练记录已导出到: {file_path}")
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(self, "成功", f"训练记录已导出到:\n{file_path}")
            except Exception as e:
                print(f"导出失败: {e}")
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def _update_sensor_values(self, event_name, event_code=None):
        """更新传感器参数设置模块中的原始值和最佳值（支持S型）"""
        if not hasattr(self, 'control_panel'):
            return
            
        current_sensor_data = self.event_recorder.current_sensor_data
        if not current_sensor_data or len(current_sensor_data) <= 1:
            return
            
        sensor_values = current_sensor_data[1:]  # 跳过时间戳
        
        # 获取当前阶段的活跃选择器
        current_config = self.stage_configs[self.spine_type]
        active_selectors = current_config["active_selectors"]
        
        if self.stage not in active_selectors:
            return
            
        selector_names = active_selectors[self.stage]
        
        # 根据事件类型和活跃选择器更新对应的控制器
        for selector_name in selector_names:
            controller = getattr(self.control_panel, selector_name, None)
            if not controller:
                continue
                
            # 判断是原始值还是目标值事件
            if self._is_original_event(event_name, event_code):
                # 更新原始值
                for i, value in enumerate(sensor_values):
                    if i < len(controller.original_value_spins):
                        controller.original_value_spins[i].setValue(int(value))
                        
            elif self._is_target_event(event_name, event_code):
                # 更新目标值
                for i, value in enumerate(sensor_values):
                    if i < len(controller.rotate_best_value_spins):
                        controller.rotate_best_value_spins[i].setValue(int(value))

    # ================================================================
    # 信号连接和可视化控制（保持原有）
    # ================================================================

    def connect_signals(self):
        """连接组件间的信号与槽"""
        print("BlocksTab: 开始连接信号...")
        
        if hasattr(self, 'control_panel'):
            self.control_panel.gray_rotation.value_changed.connect(
                lambda v: self.update_param("gray_rotation", v))
            self.control_panel.blue_curvature.value_changed.connect(
                lambda v: self.update_param("blue_curvature", v))
            self.control_panel.gray_tilt.value_changed.connect(
                lambda v: self.update_param("gray_tilt", v))
            self.control_panel.green_tilt.value_changed.connect(
                lambda v: self.update_param("green_tilt", v))
            
            # 阈值警报信号
            self.control_panel.gray_rotation.threshold_alert.connect(
                lambda active, msg: self.handle_alert("骨盆前后翻转", active, msg))
            self.control_panel.blue_curvature.threshold_alert.connect(
                lambda active, msg: self.handle_alert("脊柱曲率矫正" if self.spine_type=="C" else "腰椎曲率矫正", active, msg))
            self.control_panel.gray_tilt.threshold_alert.connect(
                lambda active, msg: self.handle_alert("骨盆左右倾斜" if self.spine_type=="C" else "胸椎曲率矫正", active, msg))
            self.control_panel.green_tilt.threshold_alert.connect(
                lambda active, msg: self.handle_alert("肩部左右倾斜", active, msg))
        
        # 阶段同步到训练记录器
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.set_stage(self.stage)
        
        print("BlocksTab: 信号连接完成")
    
    def update_param(self, param_name, value):
        """更新可视化参数"""
        # 阶段权限检查（根据脊柱类型）
        current_config = self.stage_configs[self.spine_type]
        active_selectors = current_config["active_selectors"]
        
        # 检查当前阶段是否允许使用该参数
        if self.stage in active_selectors:
            stage_selectors = active_selectors[self.stage]
            param_selector_map = {
                "gray_rotation": "gray_rotation",
                "gray_tilt": "gray_tilt",
                "blue_curvature": "blue_curvature",
                "green_tilt": "green_tilt"
            }
            
            if param_selector_map.get(param_name) not in stage_selectors:
                return
        else:
            return
        
        # 更新可视化器参数
        param_mapping = {
            "gray_rotation": "gray_block_rotation",
            "gray_tilt": "gray_block_tilt",
            "blue_curvature": "blue_blocks_curvature",
            "green_tilt": "green_block_tilt"
        }
        
        if param_name in param_mapping:
            visualizer_attr = param_mapping[param_name]
            setattr(self.visualizer, visualizer_attr, value)
            self.visualizer.update()
    
    def handle_alert(self, control_name, active, message):
        """处理传感器阈值警报"""
        # 映射控制器名称到可视化器警报属性
        alert_mapping = {
            "骨盆前后翻转": "gray_rotation_alert",
            "骨盆左右倾斜": "gray_tilt_alert", 
            "脊柱曲率矫正": "blue_curvature_alert",
            "肩部左右倾斜": "green_tilt_alert"
        } 
        
        # 更新可视化器警报状态
        if control_name in alert_mapping:
            alert_attr = alert_mapping[control_name]
            setattr(self.visualizer, alert_attr, active)
            self.visualizer.update()
        
        # 向主窗口发送警报信号
        if active:
            self.alert_signal.emit(f"{control_name}: {message}")

    # ================================================================
    # 组件访问接口方法（保持原有）
    # ================================================================
    
    def get_control_panel(self):
        """获取控制面板实例"""
        return self.control_panel
    
    def get_visualizer(self):
        """获取可视化器实例"""
        return self.visualizer
    
    def get_plot_widget(self):
        """获取曲线图组件实例"""
        return self.plot_widget
    
    def get_training_recorder(self):
        """获取训练记录器实例"""
        return self.training_recorder
    
    def get_visualization_state(self):
        """获取当前可视化状态"""
        return {
            'stage': self.stage,
            'spine_type': self.spine_type,
            'max_stages': self.max_stages,
            'sensor_count': self.sensor_count,
            'gray_rotation': getattr(self.visualizer, 'gray_block_rotation', 0),
            'gray_tilt': getattr(self.visualizer, 'gray_block_tilt', 0),
            'blue_curvature': getattr(self.visualizer, 'blue_blocks_curvature', 0),
            'green_tilt': getattr(self.visualizer, 'green_block_tilt', 0),
            'alerts': {
                'gray_rotation': getattr(self.visualizer, 'gray_rotation_alert', False),
                'gray_tilt': getattr(self.visualizer, 'gray_tilt_alert', False),
                'blue_curvature': getattr(self.visualizer, 'blue_curvature_alert', False),
                'green_tilt': getattr(self.visualizer, 'green_tilt_alert', False)
            },
            'memory_stats': self.get_memory_stats(),
            'stage_data_storage': self.get_stage_data_storage(),
            'active_selectors': self.get_active_selectors_for_stage()
        }
    
    def get_sensor_values(self):
        """获取当前传感器值"""
        return {
            'gray_rotation': getattr(self.control_panel.gray_rotation, 'current_value', 0),
            'gray_tilt': getattr(self.control_panel.gray_tilt, 'current_value', 0),
            'blue_curvature': getattr(self.control_panel.blue_curvature, 'current_value', 0),
            'green_tilt': getattr(self.control_panel.green_tilt, 'current_value', 0)
        }

    def set_sensor_count(self, count):
        """设置传感器数量"""
        if count == self.sensor_count:
            return
        
        print(f"BlocksTab: 传感器数量从 {self.sensor_count} 更改为 {count}")
        
        # 更新传感器数量
        self.sensor_count = count
        
        # 更新控制面板的传感器数量
        if hasattr(self, 'control_panel') and self.control_panel:
            self.control_panel.set_sensor_count(count)
        
        # 更新事件记录器的传感器数量
        if hasattr(self, 'event_recorder') and self.event_recorder:
            self.event_recorder.set_num_sensors(count)
        
        print(f"BlocksTab: 传感器数量更新完成")

    # ================================================================
    # 内存优化控制方法（保持原有）
    # ================================================================
    
    def set_plot_window_size(self, size):
        """设置绘图窗口大小"""
        old_size = self.plot_window_size
        self.plot_window_size = size
        
        # 调整当前数据
        if len(self._plot_data) > size:
            self._plot_data = self._plot_data[-size:]
        
        # 更新绘图组件限制
        if hasattr(self.plot_widget, 'set_max_data_points'):
            self.plot_widget.set_max_data_points(size)
        
        print(f"绘图窗口大小已更新: {old_size} -> {size}")
    
    def set_decimation_factor(self, factor):
        """设置数据抽样因子"""
        self.data_decimation_factor = max(1, factor)
        print(f"数据抽样因子设置为: {factor}")
    
    def get_memory_stats(self):
        """获取内存统计信息"""
        return {
            'plot_data_points': len(self._plot_data),
            'plot_window_size': self.plot_window_size,
            'decimation_factor': self.data_decimation_factor,
            'memory_usage_mb': self.performance_monitor['memory_usage_mb'],
            'data_points_processed': self.performance_monitor['data_points_processed'],
            'plot_updates_per_sec': self.performance_monitor['plot_updates_per_sec']
        }
    
    def clear_plot_data(self):
        """清空绘图数据"""
        if not self._plot_data_lock:
            try:
                self._plot_data_lock = True
                self._plot_data.clear()
                print("绘图数据已清空")
            finally:
                self._plot_data_lock = False
    
    def reset_visualization(self):
        """重置可视化状态"""
        # 重置可视化器参数
        self.visualizer.gray_block_rotation = 0
        self.visualizer.gray_block_tilt = 0
        self.visualizer.blue_blocks_curvature = 0
        self.visualizer.green_block_tilt = 0
        
        # 重置警报状态
        self.visualizer.gray_rotation_alert = False
        self.visualizer.gray_tilt_alert = False
        self.visualizer.blue_curvature_alert = False
        self.visualizer.green_tilt_alert = False
        
        # 清空绘图数据
        self.clear_plot_data()
        
        # 清空阶段数据存储
        self.clear_stage_data_storage()
        
        # 触发重绘
        self.visualizer.update()
        
        # 重置到第一阶段
        self.set_stage(1)
        
        print(f"BlocksTab: 可视化状态已重置（{self.spine_type}型脊柱，前-k最大分配功能已集成）")
    
    def is_alert_active(self):
        """检查是否有警报激活"""
        return any([
            getattr(self.visualizer, 'gray_rotation_alert', False),
            getattr(self.visualizer, 'gray_tilt_alert', False),
            getattr(self.visualizer, 'blue_curvature_alert', False),
            getattr(self.visualizer, 'green_tilt_alert', False)
        ])

    def update_save_path_display(self, path):
        """更新保存路径显示"""
        if hasattr(self, 'save_path_label'):
            if len(path) > 50:
                display_path = "..." + path[-47:]
            else:
                display_path = path
            self.save_path_label.setText(f"当前保存路径: {display_path}")

    # ================================================================
    # 性能优化和调试方法（保持原有）
    # ================================================================
    
    def print_memory_status(self):
        """打印内存状态信息"""
        stats = self.get_memory_stats()
        print("=== BlocksTab 内存状态 ===")
        print(f"脊柱类型: {self.spine_type}")
        print(f"当前阶段: {self.stage}/{self.max_stages}")
        print(f"绘图数据点数: {stats['plot_data_points']}")
        print(f"绘图窗口大小: {stats['plot_window_size']}")
        print(f"抽样因子: {stats['decimation_factor']}")
        print(f"内存使用: {stats['memory_usage_mb']:.1f}MB")
        print(f"处理数据点: {stats['data_points_processed']}")
        print(f"绘图更新频率: {stats['plot_updates_per_sec']:.1f}/秒")
        print("=" * 30)
    
    def optimize_memory_usage(self):
        """手动优化内存使用"""
        try:
            # 清理过期的绘图数据
            if len(self._plot_data) > self.plot_window_size // 2:
                self._plot_data = self._plot_data[-(self.plot_window_size // 2):]
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            print("手动内存优化完成")
            
        except Exception as e:
            print(f"手动内存优化失败: {e}")
    
    def set_performance_mode(self, mode="balanced"):
        """设置性能模式"""
        if mode == "high_performance":
            # 高性能模式：更小的窗口，更高的抽样率
            self.set_plot_window_size(2000)
            self.set_decimation_factor(2)
            self.update_interval = 50
            print("已切换到高性能模式")
            
        elif mode == "memory_saver":
            # 内存节省模式：很小的窗口，高抽样率
            self.set_plot_window_size(1000)
            self.set_decimation_factor(5)
            self.update_interval = 200
            print("已切换到内存节省模式")
            
        elif mode == "balanced":
            # 平衡模式：默认设置
            self.set_plot_window_size(5000)
            self.set_decimation_factor(1)
            self.update_interval = 100
            print("已切换到平衡模式")
            
        else:
            print(f"未知的性能模式: {mode}")
    
    def get_performance_recommendations(self):
        """获取性能优化建议"""
        stats = self.get_memory_stats()
        recommendations = []
        
        if stats['memory_usage_mb'] > 100:
            recommendations.append("内存使用过高，建议减小绘图窗口大小")
        
        if stats['plot_updates_per_sec'] < 5:
            recommendations.append("绘图更新频率过低，建议增加抽样因子")
        
        if stats['plot_data_points'] > 10000:
            recommendations.append("绘图数据点过多，建议启用内存节省模式")
        
        if not recommendations:
            recommendations.append("当前性能状态良好")
        
        return recommendations

    # ================================================================
    # 新增：脊柱类型集成调试和监控方法
    # ================================================================
    
    def print_spine_type_status(self):
        """打印脊柱类型状态信息"""
        print("=== 脊柱类型状态 ===")
        print(f"脊柱类型: {self.spine_type}")
        print(f"最大阶段数: {self.max_stages}")
        print(f"当前阶段: {self.stage}")
        print(f"阶段描述: {self.get_stage_description()}")
        print(f"活跃选择器: {self.get_active_selectors_for_stage()}")
        
        # 打印各阶段数据存储状态
        for stage_key in range(1, self.max_stages + 1):
            data = self.stage_data_storage.get(stage_key, {})
            has_original = data.get('original_values') is not None
            has_target = data.get('target_values') is not None
            print(f"阶段{stage_key}数据: 原始值={has_original}, 目标值={has_target}")
        
        print("=" * 30)
    
    def validate_spine_type_integration(self):
        """验证脊柱类型集成的完整性"""
        validation_results = {
            'spine_type_selection': True,
            'stage_management': True,
            'event_buttons': True,
            'sensor_params_visibility': True,
            'errors': []
        }
        
        try:
            # 验证脊柱类型选择组件
            if not hasattr(self, 'spine_type_button_group'):
                validation_results['spine_type_selection'] = False
                validation_results['errors'].append("缺少脊柱类型选择按钮组")
            
            # 验证阶段管理
            if self.max_stages != self.stage_configs[self.spine_type]["max_stages"]:
                validation_results['stage_management'] = False
                validation_results['errors'].append("最大阶段数与配置不匹配")
            
            # 验证事件按钮
            expected_stages = list(range(1, self.max_stages + 1))
            for stage in expected_stages:
                if stage not in self.event_buttons:
                    validation_results['event_buttons'] = False
                    validation_results['errors'].append(f"缺少阶段{stage}的事件按钮")
            
            # 验证传感器参数可见性
            current_config = self.stage_configs[self.spine_type]
            active_selectors = current_config["active_selectors"]
            if self.stage in active_selectors:
                expected_selectors = active_selectors[self.stage]
                all_selectors = {
                    "gray_rotation": self.control_panel.gray_rotation,
                    "blue_curvature": self.control_panel.blue_curvature,
                    "gray_tilt": self.control_panel.gray_tilt,
                    "green_tilt": self.control_panel.green_tilt
                }
                
                for selector_name, selector_widget in all_selectors.items():
                    expected_visible = selector_name in expected_selectors
                    actual_visible = selector_widget.isVisible()
                    if expected_visible != actual_visible:
                        validation_results['sensor_params_visibility'] = False
                        validation_results['errors'].append(
                            f"传感器选择器 {selector_name} 可见性不正确: "
                            f"期望={expected_visible}, 实际={actual_visible}"
                        )
            
        except Exception as e:
            validation_results['errors'].append(f"验证过程中出错: {e}")
        
        # 打印验证结果
        print("=== 脊柱类型集成验证结果 ===")
        for key, value in validation_results.items():
            if key != 'errors':
                status = "✓" if value else "✗"
                print(f"{status} {key}: {value}")
        
        if validation_results['errors']:
            print("错误详情:")
            for error in validation_results['errors']:
                print(f"  - {error}")
        else:
            print("✓ 所有验证项目通过")
        
        print("=" * 35)
        
        return validation_results

    def get_spine_type_statistics(self):
        """获取脊柱类型使用统计"""
        stats = {
            'current_spine_type': self.spine_type,
            'max_stages': self.max_stages,
            'current_stage': self.stage,
            'stages_with_data': 0,
            'active_selectors_count': len(self.get_active_selectors_for_stage()),
            'total_event_buttons': sum(len(buttons) for buttons in self.event_buttons.values()),
            'visible_event_buttons': len(self.event_buttons.get(self.stage, [])),
            'stage_progress': f"{self.stage}/{self.max_stages}"
        }
        
        # 统计有数据的阶段
        for stage_key in range(1, self.max_stages + 1):
            data = self.stage_data_storage.get(stage_key, {})
            if data.get('original_values') is not None and data.get('target_values') is not None:
                stats['stages_with_data'] += 1
        
        return stats

    # ================================================================
    # 资源清理
    # ================================================================

    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            # 停止性能监控定时器
            if hasattr(self, 'performance_timer'):
                self.performance_timer.stop()
            
            # 清空绘图数据
            self.clear_plot_data()
            
            # 清空阶段数据存储
            self.clear_stage_data_storage()
            
            print(f"BlocksTab: 资源清理完成（{self.spine_type}型脊柱，包含前-k最大分配数据）")
        except Exception as e:
            print(f"BlocksTab: 资源清理失败: {e}")

    # ================================================================
    # 新增：便捷方法供外部调用
    # ================================================================
    
    def switch_spine_type(self, spine_type):
        """程序化切换脊柱类型"""
        if spine_type == "C":
            self.c_type_radio.setChecked(True)
        elif spine_type == "S":
            self.s_type_radio.setChecked(True)
        else:
            print(f"未知的脊柱类型: {spine_type}")
    
    def get_spine_type_config(self):
        """获取当前脊柱类型的完整配置"""
        return self.stage_configs[self.spine_type].copy()
    
    def is_stage_valid(self, stage):
        """检查阶段是否有效"""
        return 1 <= stage <= self.max_stages
    
    def get_stage_events(self, stage=None):
        """获取指定阶段的事件列表"""
        if stage is None:
            stage = self.stage
        current_config = self.stage_configs[self.spine_type]
        return current_config["stage_events"].get(stage, [])
    
    def trigger_topk_allocation(self, stage_key=None):
        """手动触发前-k最大分配（调试用）"""
        if stage_key is None:
            stage_key, selector = self._get_stage_key_and_selector("", "")
        else:
            # 根据阶段键获取选择器
            current_config = self.stage_configs[self.spine_type]
            active_selectors = current_config["active_selectors"]
            
            if stage_key in active_selectors:
                selector_names = active_selectors[stage_key]
                if selector_names:
                    selector = getattr(self.control_panel, selector_names[0], None)
                else:
                    selector = None
            else:
                selector = None
        
        if selector and hasattr(selector, 'apply_top_k_allocation'):
            print(f"手动触发{self.spine_type}型-阶段{stage_key}的前-k最大分配")
            selector.apply_top_k_allocation()
        else:
            print(f"无法触发{self.spine_type}型-阶段{stage_key}的前-k最大分配：选择器不存在或不支持")
    
    def set_all_k_values(self, k_value):
        """设置所有传感器选择器的k值"""
        selectors = ['gray_rotation', 'blue_curvature', 'gray_tilt', 'green_tilt']
        updated_count = 0
        
        for selector_name in selectors:
            selector = getattr(self.control_panel, selector_name, None)
            if selector and hasattr(selector, 'k_spinbox'):
                selector.k_spinbox.setValue(k_value)
                updated_count += 1
        
        print(f"已设置 {updated_count} 个传感器选择器的k值为: {k_value}")
        
    def get_all_k_values(self):
        """获取所有传感器选择器的k值"""
        selectors = ['gray_rotation', 'blue_curvature', 'gray_tilt', 'green_tilt']
        k_values = {}
        
        for selector_name in selectors:
            selector = getattr(self.control_panel, selector_name, None)
            if selector and hasattr(selector, 'k_spinbox'):
                k_values[selector_name] = selector.k_spinbox.value()
        
        return k_values