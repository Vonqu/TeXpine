#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
积木可视化标签页（完整版）
========================

功能特性：
1. 内存优化的数据处理
2. 阶段3的四个新按钮
3. 误差范围支持
4. 固定窗口绘图
5. 性能监控
6. 保持原有样式
7. 修复阶段3权重记录错误
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
                            QLabel, QGroupBox, QTextEdit, QGridLayout)
from PyQt5.QtCore import pyqtSignal, QTimer
from block_visualization.block_control_panel import BlockControlPanel
from block_visualization.blocks_visualizer import BlocksVisualizer
from block_visualization.training_recorder import TrainingRecorder
from plot_widget import SensorPlotWidget
from event_recorder import EventRecorder

class BlocksTab(QWidget):
    """
    积木可视化标签页主类
    ====================
    """
    
    # ====== 对外信号 ======
    alert_signal = pyqtSignal(str)
    
    def __init__(self, sensor_count=6, parent=None):
        print("BlocksTab: 开始初始化...")
        super().__init__(parent)
        
        # ====== 基础配置 ======
        self.sensor_count = sensor_count
        self.stage = 1
        # 新增：脊柱类型与阶段总数（C=4, S=5）
        self.spine_type = "C"
        self.max_stages = 4  # 默认C型4阶段

        self.events_save_path = ""
        self.is_acquisition_active = False
        self.current_acquisition_id = None
        
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
        
        # ====== 创建训练记录器 ======
        self.training_recorder = TrainingRecorder()
        
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
        
        print("BlocksTab: 初始化完成")

    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        
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
        # S型：胸/腰两段曲率控件（默认由 set_spine_type 控制显隐）
        if hasattr(self.control_panel, 'blue_curvature_up'):
            sensors_layout.addWidget(self.control_panel.blue_curvature_up)
        if hasattr(self.control_panel, 'blue_curvature_down'):
            sensors_layout.addWidget(self.control_panel.blue_curvature_down)
        if hasattr(self.control_panel, 'gray_tilt'):
            sensors_layout.addWidget(self.control_panel.gray_tilt)
        if hasattr(self.control_panel, 'green_tilt'):
            sensors_layout.addWidget(self.control_panel.green_tilt)
        
        layout.addLayout(sensors_layout)
        # 初始化按脊柱类型显示正确卡片
        try:
            if hasattr(self.control_panel, 'set_spine_type'):
                self.control_panel.set_spine_type(getattr(self, 'spine_type', 'C'))
        except Exception as _e:
            print('init set_spine_type failed:', _e)
        return group

    def _create_stage_control_group(self):
        """创建阶段控制组"""
        group = QGroupBox("阶段控制")
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
        layout = QVBoxLayout()
        group.setLayout(layout)
        
        # 使用training_recorder组件替代原有的record_display
        layout.addWidget(self.training_recorder)
        
        # 为了兼容性，保留record_display的引用
        self.record_display = self.training_recorder.record_display
        
        return group

    def _create_all_event_buttons(self):
        """初始化事件按钮容器，并根据 C/S 构建一次"""
        self.stage_events = {}
        self.event_buttons = {}
        # 如果还没有布局，创建一个
        if not hasattr(self, 'event_buttons_layout') or self.event_buttons_layout is None:
            from PyQt5.QtWidgets import QGridLayout, QWidget
            self.event_buttons_widget = QWidget()
            self.event_buttons_layout = QGridLayout()
            self.event_buttons_widget.setLayout(self.event_buttons_layout)
        # 首次构建
        try:
            self._rebuild_event_buttons()
        except Exception as _e:
            print("_rebuild_event_buttons 初次构建失败:", _e)
    
    def _rebuild_event_buttons(self):
        """根据脊柱类型重建事件按钮"""
        # 清除现有按钮
        if hasattr(self, 'event_buttons'):
            for stage_buttons in self.event_buttons.values():
                for btn in stage_buttons:
                    btn.setParent(None)
        
        self.event_buttons = {}
        
        # 根据脊柱类型定义按钮配置
        spine_type = getattr(self, 'spine_type', 'C')
        
        if spine_type == 'S':
            # S型脊柱（5阶段）
            button_configs = {
                1: [("开始训练", "training_start"), ("完成阶段", "stage_complete")],
                2: [("开始矫正(胸段)", "correction_start_up"), ("矫正完成(胸段)", "correction_complete_up")],
                3: [("开始矫正(腰段)", "correction_start_down"), ("矫正完成(腰段)", "correction_complete_down")],
                4: [("开始沉髋", "hip_start"), ("沉髋完成", "hip_complete")],
                5: [("开始沉肩", "shoulder_start"), ("沉肩完成", "shoulder_complete")]
            }
        else:
            # C型脊柱（4阶段）
            button_configs = {
                1: [("开始训练", "training_start"), ("完成阶段", "stage_complete")],
                2: [("开始矫正", "correction_start"), ("矫正完成", "correction_complete")],
                3: [("开始沉髋", "hip_start"), ("沉髋完成", "hip_complete"),
                    ("开始沉肩", "shoulder_start"), ("沉肩完成", "shoulder_complete")],
                4: [("完成训练", "training_complete")]
            }
        
        # 创建按钮
        row = 0
        for stage, buttons in button_configs.items():
            stage_buttons = []
            col = 0
            
            for button_text, button_code in buttons:
                btn = QPushButton(button_text)
                btn.setMinimumHeight(35)
                btn.setStyleSheet(self._get_button_style(button_code))
                
                # 连接点击事件
                btn.clicked.connect(lambda checked, text=button_text, code=button_code: 
                                   self._handle_event_button_click(text, code))
                
                # 添加到布局
                self.event_buttons_layout.addWidget(btn, row, col)
                stage_buttons.append(btn)
                col += 1
                
                # 创建对应的按钮属性（为了兼容主窗口的连接逻辑）
                if button_code == "hip_start":
                    self.start_hip_btn = btn
                elif button_code == "hip_complete":
                    self.end_hip_btn = btn
                elif button_code == "shoulder_start":
                    self.start_shoulder_btn = btn
                elif button_code == "shoulder_complete":
                    self.end_shoulder_btn = btn
            
            self.event_buttons[stage] = stage_buttons
            row += 1
    
    def _get_button_style(self, button_code):
        """获取按钮样式"""
        if "start" in button_code or "开始" in button_code:
            # 开始类按钮 - 蓝色
            return """
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
                QPushButton:pressed {
                    background-color: #004085;
                }
            """
        elif "complete" in button_code or "完成" in button_code:
            # 完成类按钮 - 绿色
            return """
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1e7e34;
                }
                QPushButton:pressed {
                    background-color: #155724;
                }
            """
        else:
            # 默认按钮样式
            return """
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #545b62;
                }
                QPushButton:pressed {
                    background-color: #3d4449;
                }
            """
    
    def _handle_event_button_click(self, button_text, button_code):
        """处理事件按钮点击"""
        print(f"事件按钮被点击: {button_text} ({button_code})")
        
        # 调用事件记录器记录事件
        if hasattr(self, 'event_recorder'):
            try:
                # 获取当前传感器数据
                if hasattr(self, 'control_panel'):
                    sensor_data = []
                    for i in range(self.event_recorder.sensor_count):
                        try:
                            sensor_data.append(getattr(self.control_panel, f'sensor_{i+1}_value', 2500.0))
                        except:
                            sensor_data.append(2500.0)
                    
                    # 记录事件
                    self.event_recorder.record_event(
                        event_name=button_text,
                        event_code=button_code,
                        stage=f"阶段{self.stage}",
                        sensor_data=sensor_data
                    )
                    
                    print(f"事件已记录: {button_text}")
                    
            except Exception as e:
                print(f"记录事件时出错: {e}")
        
        # 更新训练记录器
        if hasattr(self, 'training_recorder'):
            try:
                if "开始" in button_text:
                    # 将按钮代码转换为阶段标识符
                    if button_code == "hip_start":
                        self.training_recorder.start_stage('3a')
                    elif button_code == "shoulder_start":
                        self.training_recorder.start_stage('3b')
                    else:
                        self.training_recorder.start_stage(str(self.stage))
                elif "完成" in button_text:
                    if button_code == "hip_complete":
                        self.training_recorder.complete_stage('3a')
                    elif button_code == "shoulder_complete":
                        self.training_recorder.complete_stage('3b')
                    else:
                        self.training_recorder.complete_stage(str(self.stage))
            except Exception as e:
                print(f"更新训练记录器时出错: {e}")
    
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

    # ================================================================
    # 内存优化的数据处理方法
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
    # 事件记录相关方法
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
        
        print(f"开始新的数据采集，ID: {self.current_acquisition_id}")

    def stop_acquisition(self):
        """停止数据采集"""
        self.is_acquisition_active = False
        self.current_acquisition_id = None
        print("数据采集已停止")
    
    def _force_update_sensor_data(self):
        """强制更新传感器数据，解决校准阶段数据延迟问题"""
        try:
            # 通过父窗口获取最新的传感器数据
            if hasattr(self, 'parent') and self.parent():
                main_window = self.parent()
                # 如果主窗口有最新的传感器数据，立即更新到事件记录器
                if hasattr(main_window, 'latest_sensor_data') and main_window.latest_sensor_data:
                    self.event_recorder.set_current_sensor_data(main_window.latest_sensor_data)
                    print(f"已强制更新传感器数据: {main_window.latest_sensor_data[:3]}...")
                # 如果有数据管理器，从中获取最新数据
                elif hasattr(main_window, 'data_manager') and main_window.data_manager:
                    latest_data = main_window.data_manager.get_latest_data()
                    if latest_data:
                        self.event_recorder.set_current_sensor_data(latest_data)
                        print(f"从数据管理器获取最新数据: {latest_data[:3]}...")
            
            # 立即更新绘图数据
            if hasattr(self, 'plot_widget') and self.event_recorder.current_sensor_data:
                self._update_plot_data_optimized(self.event_recorder.current_sensor_data)
                
        except Exception as e:
            print(f"强制更新传感器数据时出错: {e}")

    def _record_event(self, event_name, event_code=None):
        """记录训练事件（增强版：收集更详细的校准数据）"""
        from datetime import datetime
        
        # 立即获取最新的传感器数据，解决延迟问题
        self._force_update_sensor_data()
        
        # 获取当前阶段对应控制器的权重信息和误差范围（传入事件信息）
        sensor_weights, error_range = self._get_current_stage_weights_and_error_range(event_name, event_code)
        
        # 获取详细的校准数据（增强功能）
        calibration_data = self._get_detailed_calibration_data(event_name, event_code)
        
        # 更新传感器参数设置模块中的原始值和最佳值
        self._update_sensor_values(event_name, event_code)
        
        # 使用事件记录器记录事件
        success = self.event_recorder.record_event(
            event_name=event_name,
            stage=f"阶段{self.stage}",
            additional_data={
                'event_code': event_code or event_name.lower().replace(' ', '_'),
                'sensor_weights': sensor_weights,
                'error_range': error_range,
                'calibration_data': calibration_data  # 增强：添加详细校准数据
            }
        )
        
        if success:
            # 显示在记录窗口（增强版显示）
            current_time = datetime.now()
            relative_time = 0.0
            if self.event_recorder.acquisition_start_time:
                time_diff = current_time - self.event_recorder.acquisition_start_time
                relative_time = time_diff.total_seconds()
            
            record_text = f"[{relative_time:.1f}s] 阶段{self.stage} - {event_name}\n"
            
            current_sensor_data = self.event_recorder.current_sensor_data
            if current_sensor_data:
                record_text += f"  📊 原始数据: {[f'{x:.0f}' for x in current_sensor_data[1:]]}\n"
            
            record_text += f"  ⚖️ 传感器权重: {[f'{w:.1f}' for w in sensor_weights]}\n"
            record_text += f"  🎯 误差范围: {error_range:.3f}\n"
            
            # 增强：显示校准过程信息
            if calibration_data:
                if 'ov_values' in calibration_data:
                    record_text += f"  🔧 原始值(OV): {[f'{x:.0f}' for x in calibration_data['ov_values']]}\n"
                if 'bv_values' in calibration_data:
                    record_text += f"  ✅ 最佳值(BV): {[f'{x:.0f}' for x in calibration_data['bv_values']]}\n"
                if 'normalized_values' in calibration_data:
                    record_text += f"  📐 归一化值: {[f'{x:.3f}' for x in calibration_data['normalized_values']]}\n"
                if 'combined_value' in calibration_data:
                    record_text += f"  🎯 加权组合值: {calibration_data['combined_value']:.3f}\n"
                if 'calibration_status' in calibration_data:
                    record_text += f"  {calibration_data['calibration_status']}\n"
            
            record_text += "─" * 50 + "\n"
            
            self.record_display.append(record_text)
            self.record_display.verticalScrollBar().setValue(
                self.record_display.verticalScrollBar().maximum()
            )
            
            # 在曲线图上添加事件标记
            if hasattr(self, 'plot_widget') and current_sensor_data:
                current_time_from_sensor = current_sensor_data[0] if current_sensor_data else 0
                self._add_event_marker(current_time_from_sensor, event_name)
            
            # 记录到训练记录器（增强版数据）
            if hasattr(self, 'training_recorder') and self.training_recorder:
                # 生成唯一的记录键，包含时间戳避免覆盖
                import time
                timestamp_ms = int(time.time() * 1000)
                record_key = f"stage{self.stage}_{event_code or event_name}_{timestamp_ms}"
                self.training_recorder.add_record_data(record_key, {
                    'timestamp': relative_time,
                    'stage': self.stage,
                    'event_name': event_name,
                    'event_code': event_code or event_name.lower().replace(' ', '_'),
                    'raw_sensor_data': current_sensor_data,
                    'sensor_weights': sensor_weights,
                    'error_range': error_range,
                    'calibration_data': calibration_data,  # 增强：添加校准详细数据
                    'visualization_state': self.get_visualization_state()
                })
            
            print(f"已记录事件: {event_name} (阶段{self.stage}) - 相对时间: {relative_time:.1f}s, 误差范围: {error_range}")
        else:
            print(f"记录事件失败: {event_name}")
    
    def _get_detailed_calibration_data(self, event_name, event_code=None):
        """获取详细的校准数据（增强功能）"""
        try:
            calibration_data = {}
            
            # 获取当前阶段对应的控制器
            current_controller = None
            if self.stage == 1:
                current_controller = self.control_panel.gray_rotation
            elif self.stage == 2:
                current_controller = (self.control_panel.blue_curvature_up
                    if getattr(self, 'spine_type', 'C') == 'S' and hasattr(self.control_panel, 'blue_curvature_up')
                    else self.control_panel.blue_curvature)
            elif self.stage == 3:
                if getattr(self, 'spine_type', 'C') == 'S' and hasattr(self.control_panel, 'blue_curvature_down'):
                    controller = self.control_panel.blue_curvature_down
                    weights = self._get_controller_weights(controller)
                    error_range = controller.get_error_range()
                    print('阶段3权重记录: 腰段曲率')
                else:
                    # 根据事件类型选择控制器
                    if (event_code and ("hip" in event_code.lower())) or (event_name and ("沉髋" in event_name)):
                        current_controller = self.control_panel.gray_tilt
                    elif (event_code and ("shoulder" in event_code.lower())) or (event_name and ("沉肩" in event_name)):
                        current_controller = self.control_panel.green_tilt
                    else:
                        current_controller = self.control_panel.gray_tilt  # 默认
            elif self.stage == 4:
                current_controller = self.control_panel.green_tilt
            
            if not current_controller:
                return calibration_data
            
            # 获取OV/BV值
            try:
                ov_values = []
                bv_values = []
                
                # 获取原始值
                if hasattr(current_controller, 'original_value_spins'):
                    ov_values = [spin.value() for spin in current_controller.original_value_spins]
                
                # 获取最佳值（根据控制器类型）
                if hasattr(current_controller, 'rotate_best_value_spins'):
                    bv_values = [spin.value() for spin in current_controller.rotate_best_value_spins]
                elif hasattr(current_controller, 'curvature_best_value_spins'):
                    bv_values = [spin.value() for spin in current_controller.curvature_best_value_spins]
                elif hasattr(current_controller, 'lateral_best_value_spins'):
                    bv_values = [spin.value() for spin in current_controller.lateral_best_value_spins]
                elif hasattr(current_controller, 'torsion_best_value_spins'):
                    bv_values = [spin.value() for spin in current_controller.torsion_best_value_spins]
                
                calibration_data['ov_values'] = ov_values
                calibration_data['bv_values'] = bv_values
                
                # 计算归一化值
                if ov_values and bv_values and self.event_recorder.current_sensor_data:
                    sensor_data = self.event_recorder.current_sensor_data[1:]  # 跳过时间戳
                    normalized_values = []
                    
                    for i, sensor_val in enumerate(sensor_data[:len(ov_values)]):
                        if i < len(ov_values) and i < len(bv_values):
                            ov = ov_values[i]
                            bv = bv_values[i]
                            if ov != bv:  # 避免除零
                                norm = (sensor_val - bv) / (ov - bv)
                                norm = max(0, min(1, norm))  # 限制在0-1范围
                            else:
                                norm = 0.0
                            normalized_values.append(norm)
                    
                    calibration_data['normalized_values'] = normalized_values
                    
                    # 计算加权组合值
                    sensor_weights, _ = self._get_current_stage_weights_and_error_range(event_name, event_code)
                    if sensor_weights and normalized_values:
                        weighted_sum = sum(w * n for w, n in zip(sensor_weights, normalized_values) if w > 0)
                        total_weight = sum(w for w in sensor_weights if w > 0)
                        if total_weight > 0:
                            combined_value = weighted_sum / total_weight
                            calibration_data['combined_value'] = combined_value
                            
                            # 添加校准状态评估
                            if '完成' in event_name:
                                if combined_value < 0.05:
                                    calibration_data['calibration_status'] = "🟢 校准效果: 优秀"
                                elif combined_value < 0.1:
                                    calibration_data['calibration_status'] = "🟡 校准效果: 良好"  
                                else:
                                    calibration_data['calibration_status'] = "🔴 校准效果: 需改善"
                            elif '开始' in event_name:
                                calibration_data['calibration_status'] = "🔧 开始校准记录"
                
            except Exception as e:
                print(f"获取校准数据时出错: {e}")
            
            return calibration_data
            
        except Exception as e:
            print(f"获取详细校准数据失败: {e}")
            return {}

    def _get_current_stage_weights_and_error_range(self, event_name=None, event_code=None):
        """获取当前阶段对应控制器的传感器权重和误差范围（修复版）"""
        weights = [0.0] * self.sensor_count
        error_range = 0.1
        
        try:
            if self.stage == 1:
                controller = self.control_panel.gray_rotation
                weights = self._get_controller_weights(controller)
                error_range = controller.get_error_range()
                print(f"阶段1权重记录: 骨盆前后翻转")
                
            elif self.stage == 2:
                controller = (self.control_panel.blue_curvature_up
                    if getattr(self, 'spine_type', 'C') == 'S' and hasattr(self.control_panel, 'blue_curvature_up')
                    else self.control_panel.blue_curvature)
                weights = self._get_controller_weights(controller)
                error_range = controller.get_error_range()
                print(f"阶段2权重记录: 脊柱曲率矫正")
                
            elif self.stage == 3:
                if getattr(self, 'spine_type', 'C') == 'S' and hasattr(self.control_panel, 'blue_curvature_down'):
                    controller = self.control_panel.blue_curvature_down
                    weights = self._get_controller_weights(controller)
                    error_range = controller.get_error_range()
                    print('阶段3权重记录: 腰段曲率')
                else:
                    # 【修复关键部分】阶段3：根据具体事件分别记录不同控制器的权重
                    print(f"阶段3权重记录 - 事件名称: '{event_name}', 事件代码: '{event_code}'")
                    
                    # 修复：使用正确的事件代码和名称判断逻辑
                    if (event_code and ("hip" in event_code.lower())) or (event_name and ("沉髋" in event_name)):
                        # 沉髋相关事件：使用骨盆左右倾斜控制器
                        controller = self.control_panel.gray_tilt  # 骨盆左右倾斜
                        weights = self._get_controller_weights(controller)
                        error_range = controller.get_error_range()
                        print(f"→ 记录沉髋事件权重: 使用骨盆左右倾斜控制器")
                        
                    elif (event_code and ("shoulder" in event_code.lower())) or (event_name and ("沉肩" in event_name)):
                        # 沉肩相关事件：使用肩部左右倾斜控制器
                        controller = self.control_panel.green_tilt  # 肩部左右倾斜
                        weights = self._get_controller_weights(controller)
                        error_range = controller.get_error_range()
                        print(f"→ 记录沉肩事件权重: 使用肩部左右倾斜控制器")
                        
                    else:
                        # 其他阶段3事件：合并两个控制器的权重（保持兼容性）
                        gray_weights = self._get_controller_weights(self.control_panel.gray_tilt)
                        green_weights = self._get_controller_weights(self.control_panel.green_tilt)
                        for i in range(min(len(weights), len(gray_weights), len(green_weights))):
                            weights[i] = gray_weights[i] + green_weights[i]
                        error_range = (self.control_panel.gray_tilt.get_error_range() + 
                                    self.control_panel.green_tilt.get_error_range()) / 2
                        print(f"→ 记录阶段3通用事件权重: 合并两个控制器权重")
                    
            elif self.stage == 4:
                # 阶段4：骨盆左右倾斜（C型脊柱的第4阶段）或者肩部左右倾斜（S型脊柱的第4阶段）
                if getattr(self, 'spine_type', 'C') == 'S':
                    # S型脊柱第4阶段：骨盆左右倾斜
                    controller = self.control_panel.gray_tilt
                    weights = self._get_controller_weights(controller)
                    error_range = controller.get_error_range()
                    print(f"阶段4权重记录: S型脊柱骨盆左右倾斜")
                else:
                    # C型脊柱第4阶段：肩部左右倾斜
                    controller = self.control_panel.green_tilt
                    weights = self._get_controller_weights(controller)
                    error_range = controller.get_error_range()
                    print(f"阶段4权重记录: C型脊柱肩部左右倾斜")
                    
            elif self.stage == 5:
                # 阶段5：仅S型脊柱使用，肩部左右倾斜
                if getattr(self, 'spine_type', 'C') == 'S':
                    controller = self.control_panel.green_tilt
                    weights = self._get_controller_weights(controller)
                    error_range = controller.get_error_range()
                    print(f"阶段5权重记录: S型脊柱肩部左右倾斜")
                else:
                    print(f"警告: C型脊柱不应该有第5阶段")
                    
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
            stage_names = {1: "骨盆前后旋转", 2: "脊柱曲率矫正", 3: "关节平衡调整"}
            stage_name = stage_names.get(self.stage, f"阶段{self.stage}")
            
            if hasattr(self.plot_widget, 'add_event_marker'):
                self.plot_widget.add_event_marker(
                    event_name,
                    timestamp,
                    f"{stage_name}: {event_name}"
                )

    def _clear_records(self):
        """清空训练记录"""
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.clear_records()
        print("训练记录已清空")

    def _export_records(self):
        """导出训练记录"""
        if not hasattr(self, 'training_recorder') or not self.training_recorder:
            print("错误: training_recorder 未初始化，无法导出记录")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", "训练记录器未初始化，无法导出记录")
            return
        
        # 直接调用training_recorder的save_records方法
        self.training_recorder.save_records()
        print("训练记录导出完成")


    # ================================================================
    # 阶段管理方法（合并修复版：全部放在类内部）
    # ================================================================


    def prev_stage(self):

        """切换到上一个训练阶段"""

        try:

            min_stage = 1

            if self.stage > min_stage:

                old_stage = self.stage

                self.stage -= 1

                self.update_stage_ui()

                # 同步给训练记录器

                if hasattr(self, 'training_recorder') and self.training_recorder:

                    self.training_recorder.set_stage(self.stage)

                print(f"切换阶段: {old_stage} → {self.stage}")

            else:

                print("已是最小阶段，无法再往前")

        except Exception as e:

            print(f"prev_stage 切换失败: {e}")

    

    def next_stage(self):
        """切换到下一个训练阶段"""
        if self.stage < getattr(self, 'max_stages', 4):
            old_stage = self.stage
            self.stage += 1
            self.update_stage_ui()
            
            if hasattr(self, 'training_recorder') and self.training_recorder:
                self.training_recorder.set_stage(self.stage)
            
            print(f"切换阶段: {old_stage} → {self.stage}")



    def set_stage(self, stage):
        """直接设置训练阶段"""
        if 1 <= stage <= getattr(self, 'max_stages', 4):
            self.stage = stage
            self.update_stage_ui()
            
            if hasattr(self, 'training_recorder') and self.training_recorder:
                self.training_recorder.set_stage(self.stage)
            
            print(f"设置阶段: {stage}")

    
    def update_stage_ui(self):
        """更新训练阶段UI显示"""
        # 更新控制面板状态
        self.control_panel.highlight_stage(self.stage)
        self.control_panel.set_stage_defaults(self.stage)
        
        # 更新阶段切换按钮的启用状态
        if hasattr(self, 'prev_btn') and hasattr(self, 'next_btn'):
            self.prev_btn.setEnabled(self.stage > 1)
            self.next_btn.setEnabled(self.stage < getattr(self, 'max_stages', 4))
        
        # 动态阶段描述（C型4阶段，S型5阶段）
        stage_descriptions = (
            {
                1: "阶段1：骨盆前后翻转（只调整骨盆前后翻转）",
                2: "阶段2：脊柱曲率矫正-单段（只调整脊柱曲率矫正）",
                3: "阶段3：骨盆左右倾斜（只调整骨盆左右倾斜）",
                4: "阶段4：肩部左右倾斜（只调整肩部左右倾斜）",
            } if getattr(self, 'spine_type', 'C') != 'S' else {
                1: "阶段1：骨盆前后翻转",
                2: "阶段2A：上胸段曲率矫正",
                3: "阶段2B：腰段曲率矫正",
                4: "阶段3：骨盆左右倾斜",
                5: "阶段4：肩部左右倾斜",
            }
        )

        
        self.stage_label.setText(stage_descriptions.get(self.stage, "未知阶段"))
        
        # 设置阶段标签样式
        stage_colors = {1: "#FF6B6B", 2: "#4ECDC4", 3: "#45B7D1", 4: "#F7B801", 5: "#8E44AD"}
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
        
        # 更新事件按钮显示
        if hasattr(self, '_update_event_buttons_for_stage'):
            self._update_event_buttons_for_stage(self.stage)
        
        # 同步阶段到训练记录器
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.set_stage(self.stage)
            
        # 显示当前最大阶段数（调试用）
        print(f"阶段UI更新完成: {self.stage}/{getattr(self, 'max_stages', 4)} (脊柱类型: {getattr(self, 'spine_type', 'C')})")
    

    # ================================================================
    # 组件访问接口方法
    # ================================================================

    def connect_signals(self):
        """连接组件间的信号与槽"""
        print("BlocksTab: 开始连接信号...")
    
        if hasattr(self, 'control_panel'):
            self.control_panel.gray_rotation.value_changed.connect(
                lambda v: self.update_param("gray_rotation", v))
            self.control_panel.gray_tilt.value_changed.connect(
                lambda v: self.update_param("gray_tilt", v))
            self.control_panel.blue_curvature.value_changed.connect(
                lambda v: self.update_param("blue_curvature", v))
            self.control_panel.green_tilt.value_changed.connect(
                lambda v: self.update_param("green_tilt", v))
        
            # 阈值警报信号
            self.control_panel.gray_rotation.threshold_alert.connect(
                lambda active, msg: self.handle_alert("骨盆前后翻转", active, msg))
            self.control_panel.blue_curvature.threshold_alert.connect(
                lambda active, msg: self.handle_alert("脊柱曲率矫正", active, msg))
            self.control_panel.gray_tilt.threshold_alert.connect(
                lambda active, msg: self.handle_alert("骨盆左右倾斜", active, msg))
            self.control_panel.green_tilt.threshold_alert.connect(
                lambda active, msg: self.handle_alert("肩部左右倾斜", active, msg))
    
        # 阶段同步到训练记录器
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.set_stage(self.stage)
        
            # 连接阶段按钮到训练记录器
            if hasattr(self, 'start_training_btn'):
                self.start_training_btn.clicked.connect(lambda: self.training_recorder.start_stage(1))
            if hasattr(self, 'complete_stage_btn'):
                self.complete_stage_btn.clicked.connect(lambda: self.training_recorder.complete_stage(1))
            if hasattr(self, 'start_correction_btn'):
                self.start_correction_btn.clicked.connect(lambda: self.training_recorder.start_stage(2))
            if hasattr(self, 'complete_correction_btn'):
                self.complete_correction_btn.clicked.connect(lambda: self.training_recorder.complete_stage(2))
            if hasattr(self, 'start_hip_btn'):
                self.start_hip_btn.clicked.connect(lambda: self.training_recorder.start_stage('3a'))
            if hasattr(self, 'end_hip_btn'):
                self.end_hip_btn.clicked.connect(lambda: self.training_recorder.complete_stage('3a'))
            if hasattr(self, 'start_shoulder_btn'):
                self.start_shoulder_btn.clicked.connect(lambda: self.training_recorder.start_stage('3b'))
            if hasattr(self, 'end_shoulder_btn'):
                self.end_shoulder_btn.clicked.connect(lambda: self.training_recorder.complete_stage('3b'))
    
        print("BlocksTab: 信号连接完成")


    
    
    def update_spine_type(self, spine_type):
        """更新脊柱类型"""
        print(f"BlocksTab: 更新脊柱类型为 {spine_type}")
        self.spine_type = str(spine_type).upper() if spine_type else "C"
        # C=4阶段, S=5阶段
        self.max_stages = 5 if self.spine_type == "S" else 4
        # 通知控制面板切换 C/S 显示
        try:
            if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'set_spine_type'):
                self.control_panel.set_spine_type(self.spine_type)
        except Exception as _e:
            print('set_spine_type 调用失败:', _e)
        # 事件按钮根据类型重建
        try:
            if hasattr(self, '_rebuild_event_buttons'):
                self._rebuild_event_buttons()
        except Exception as _e:
            print('_rebuild_event_buttons 失败:', _e)
        # 切换类型后如果当前阶段超出上限则回退
        if getattr(self, 'stage', 1) > self.max_stages:
            self.stage = self.max_stages
        # 更新记录器
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.set_spine_type(spine_type)
        # 刷新阶段UI
        try:
            self.update_stage_ui()
        except Exception as _e:
            print("update_stage_ui尚未可用或刷新失败：", _e)

    
    def update_spine_direction(self, spine_direction):
        """更新脊柱方向"""
        print(f"BlocksTab: 更新脊柱方向为 {spine_direction}")
        if hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.set_spine_direction(spine_direction)

    # ================================================================
    # 信号连接和可视化控制
    # ================================================================
    
    def update_param(self, param_name, value):
        """更新可视化参数"""
        # 阶段权限检查
        stage_param_map = {
            1: ["gray_rotation"],
            2: ["blue_curvature"], 
            3: ["gray_tilt", "green_tilt"]
        }
        
        if param_name not in stage_param_map.get(self.stage, []):
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
    # 阶段管理方法
    # ================================================================
        
    def get_stage(self):
        """获取当前训练阶段"""
        return self.stage
    
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
            'memory_stats': self.get_memory_stats()
        }
    
    def get_sensor_values(self):
        """获取当前传感器值"""
        return {
            'gray_rotation': getattr(self.control_panel.gray_rotation, 'current_value', 0),
            'gray_tilt': getattr(self.control_panel.gray_tilt, 'current_value', 0),
            'blue_curvature': getattr(self.control_panel.blue_curvature, 'current_value', 0),
            'green_tilt': getattr(self.control_panel.green_tilt, 'current_value', 0)
        }

    # ================================================================
    # 内存优化控制方法
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
        
        # 触发重绘
        self.visualizer.update()
        
        # 重置到第一阶段
        self.set_stage(1)
        
        print("BlocksTab: 可视化状态已重置（内存已优化）")
    
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
    # 性能优化和调试方法
    # ================================================================
    
    def print_memory_status(self):
        """打印内存状态信息"""
        stats = self.get_memory_stats()
        print("=== BlocksTab 内存状态 ===")
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
            
            print("BlocksTab: 资源清理完成")
        except Exception as e:
            print(f"BlocksTab: 资源清理失败: {e}")

    
    def _update_sensor_values(self, event_name, event_code=None):
        """更新传感器参数设置模块中的原始值和最佳值（S/C 统一版）"""
        if not hasattr(self, 'control_panel'):
            return

        # 如有“完成阶段”事件，尽量同步最新数据与图表
        if "完成阶段" in (event_name or "") and hasattr(self, 'event_recorder'):
            if hasattr(self.event_recorder, 'get_latest_sensor_data'):
                latest = self.event_recorder.get_latest_sensor_data()
                if latest and len(latest) > 1:
                    self.event_recorder.current_sensor_data = latest
            if hasattr(self, 'plot_widget') and hasattr(self.plot_widget, 'force_next_update'):
                self.plot_widget.force_next_update()

        current = getattr(self.event_recorder, 'current_sensor_data', None)
        if not current or len(current) <= 1:
            return
        sensor_values = current[1:]  # 去时间戳

        def write_values(ctrl, which):
            if not ctrl:
                return
            if which == "ov":  # 原始
                spins = getattr(ctrl, 'original_value_spins', [])
            else:              # 最佳
                spins = (getattr(ctrl, 'curvature_best_value_spins', None) or
                         getattr(ctrl, 'rotate_best_value_spins', None) or
                         getattr(ctrl, 'lateral_best_value_spins', None) or
                         getattr(ctrl, 'torsion_best_value_spins', None) or [])
            for i, v in enumerate(sensor_values):
                if i < len(spins):
                    spins[i].setValue(int(v))

        s_type = getattr(self, 'spine_type', 'C')

        if self.stage == 1:
            ctrl = self.control_panel.gray_rotation
            if "开始" in event_name:
                write_values(ctrl, "ov")
            elif "完成" in event_name:
                write_values(ctrl, "bv")

        elif self.stage == 2:
            ctrl = (self.control_panel.blue_curvature_up
                    if s_type == 'S' and hasattr(self.control_panel, 'blue_curvature_up')
                    else self.control_panel.blue_curvature)
            if "开始" in event_name:
                write_values(ctrl, "ov")
            elif "完成" in event_name or "矫正完成" in event_name:
                write_values(ctrl, "bv")

        elif self.stage == 3:
            if s_type == 'S' and hasattr(self.control_panel, 'blue_curvature_down'):
                ctrl = self.control_panel.blue_curvature_down
                if "开始" in event_name:
                    write_values(ctrl, "ov")
                elif "完成" in event_name or "矫正完成" in event_name:
                    write_values(ctrl, "bv")
            else:
                # C型：按事件区分沉髋/沉肩
                is_hip = (event_code and "hip" in event_code.lower()) or ("沉髋" in (event_name or ""))
                is_shoulder = (event_code and "shoulder" in event_code.lower()) or ("沉肩" in (event_name or ""))
                if is_hip:
                    ctrl = self.control_panel.gray_tilt
                elif is_shoulder:
                    ctrl = self.control_panel.green_tilt
                else:
                    ctrl = None
                if ctrl:
                    if "开始" in event_name:
                        write_values(ctrl, "ov")
                    elif "完成" in event_name:
                        write_values(ctrl, "bv")

        elif self.stage == 4:
            ctrl = self.control_panel.gray_tilt if s_type == 'S' else self.control_panel.green_tilt
            if "开始" in event_name:
                write_values(ctrl, "ov")
            elif "完成" in event_name:
                write_values(ctrl, "bv")

        elif self.stage == 5 and s_type == 'S':
            ctrl = self.control_panel.green_tilt
            if "开始" in event_name:
                write_values(ctrl, "ov")
            elif "完成" in event_name:
                write_values(ctrl, "bv")

        # 完成阶段后把数据写进训练记录器
        if ("完成阶段" in (event_name or "")) and hasattr(self, 'training_recorder') and self.training_recorder:
            self.training_recorder.complete_stage(self.stage, sensor_values)
