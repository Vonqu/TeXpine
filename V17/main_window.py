#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口模块（修改版） - 实现新的交互逻辑 + UDP发送功能
=====================================

修改内容：
1. 实现医生端/患者端模式切换
2. tab3复用tab1的绘图控制和tab2的积木可视化
3. 实现基于模式的事件记录和积木控制逻辑
4. 新增UDP发送功能, 实时发送四个阶段的加权归一化值和误差范围
5. 修复数据采集和绘图问题
6. 修复蓝牙接收器初始化问题

功能职责：
1. 系统总入口，负责整体架构搭建和模块集成
2. 管理三个主要标签页：监测、积木可视化（医生端）、积木可视化（患者端）
3. 协调数据采集、处理和显示的整体流程
4. 处理医生端/患者端模式切换逻辑
5. UDP数据发送到Unity
"""

import sys
import os
import csv
import json
import socket
import time
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QSplitter, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtGui import QFont

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

print("1. 开始导入模块...")

from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QTabWidget, QVBoxLayout, QApplication, QGroupBox
from PyQt5.QtCore import Qt, pyqtSlot

print("2. 导入PyQt5模块完成")

# 导入数据采集层模块
from serial_thread import SerialThread
from bluetooth_receiver import BluetoothReceiver

# 导入数据处理层模块
from data_manager import DataManager

# 导入界面控制层模块
from control_panel import ControlPanel
try:
    from plot_widget import SensorPlotWidget
    print("成功导入 SensorPlotWidget")
except ImportError as e:
    print(f"导入 SensorPlotWidget 失败: {e}")
    print(f"当前 Python 路径: {sys.path}")
    raise

# 导入功能模块层模块
from block_visualization.blocks_tab_manager import BlocksTabManager
from block_visualization.patient_blocks_tab import PatientBlocksTab

# 导入事件记录器
from event_recorder import EventRecorder

from block_visualization.sensor_selector import SensorSelector
from kalman_filter import MultiSensorKalmanFilter
from butterworth_filter import MultiSensorButterworthFilter
from savitzky_golay_filter import MultiSensorSavitzkyGolayFilter
from data_enhancement import DataEnhancement

# 导入JSON编码器（如果存在）
try:
    from jsonencoder import NumpyEncoder
except ImportError:
    # 如果没有jsonencoder模块，创建一个简单的编码器
    import json
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.float32, np.float64, np.int32, np.int64)):
                return float(obj)
            return super().default(obj)

print("3. 导入所有自定义模块完成")

from block_visualization.spine_type_selector import SpineTypeSelector


class SpineDataSender:
    """脊柱数据UDP发送器"""
    
    def __init__(self, host='127.0.0.1', port=6667, enable=False):
        self.host = host
        self.port = port
        self.enable = enable
        self.socket = None
        self.error_count = 0
        self.sent_count = 0
        self.last_status_time = 0
        
        # 存储从事件文件加载的阶段配置
        self.stage_configs = {
            'gray_rotation': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1},
            'blue_curvature': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1},
            'gray_tilt': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1},
            'green_tilt': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1}
        }
        
        self.events_file_loaded = False


        self.stage_sensor_mapping = {
            # C型脊柱映射（保持原有）
            "C": {
                1: {
                    'name': '骨盆前后翻转',
                    'original_event': '开始训练',
                    'target_event': '完成阶段',
                    'sensor_indices': [0, 1]
                },
                2: {
                    'name': '脊柱曲率矫正', 
                    'original_event': '开始矫正',
                    'target_event': '矫正完成',
                    'sensor_indices': [2, 3]
                },
                3: {
                    'name': '关节平衡调整',
                    'original_event': '开始沉髋',
                    'target_event': '沉髋完成',
                    'sensor_indices': [4, 5]
                }
            },
            # S型脊柱映射（新增）
            "S": {
                1: {
                    'name': '骨盆前后翻转',
                    'original_event': '开始训练',
                    'target_event': '完成阶段',
                    'sensor_indices': [0, 1]
                },
                2: {
                    'name': '腰椎曲率矫正',
                    'original_event': '开始腰椎矫正',
                    'target_event': '腰椎矫正完成',
                    'sensor_indices': [2, 3]
                },
                3: {
                    'name': '胸椎曲率矫正',
                    'original_event': '开始胸椎矫正',
                    'target_event': '胸椎矫正完成',
                    'sensor_indices': [4, 5]
                },
                4: {
                    'name': '关节平衡调整',
                    'original_event': '开始肩部调整',
                    'target_event': '肩部调整完成',
                    'sensor_indices': [6, 7]
                }
            }
        }
        
        if self.enable:
            self.init_socket()
    
    def init_socket(self):
        """初始化UDP Socket"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"脊柱数据Socket已初始化，准备发送到 {self.host}:{self.port}")
            self.error_count = 0
            self.sent_count = 0
            self.last_status_time = time.time()
            return True
        except Exception as e:
            print(f"脊柱数据Socket初始化失败: {e}")
            self.socket = None
            self.enable = False
            return False
    
    def load_events_file(self, events_file_path, sensor_count=7):
        """从事件文件加载阶段配置数据"""
        if not events_file_path or not os.path.exists(events_file_path):
            print(f"事件文件不存在或路径无效: {events_file_path}")
            return False
        
        try:
            print(f"正在加载事件文件用于UDP发送: {events_file_path}")
            
            # 事件映射配置
            event_mappings = {
                ("阶段1", "开始训练"): ('gray_rotation', 'original'),
                ("阶段1", "完成阶段"): ('gray_rotation', 'target'),
                ("阶段2", "开始矫正"): ('blue_curvature', 'original'),
                ("阶段2", "矫正完成"): ('blue_curvature', 'target'),
                ("阶段3", "开始沉髋"): ('gray_tilt', 'original'),
                ("阶段3", "沉髋完成"): ('gray_tilt', 'target'),
                ("阶段3", "开始沉肩"): ('green_tilt', 'original'),
                ("阶段3", "沉肩完成"): ('green_tilt', 'target'),
            }
            
            with open(events_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # 找到CSV头部
                headers = None
                data_start_line = 0
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        headers = line.split(',')
                        data_start_line = i
                        break
                
                if headers is None:
                    print("UDP发送器：文件中没有找到有效的CSV头部")
                    return False
                
                # 创建CSV读取器
                reader = csv.DictReader(
                    (line for line in lines[data_start_line:] if line.strip() and not line.strip().startswith('#')),
                    fieldnames=headers
                )
                
                # 解析数据
                for row in reader:
                    stage = row.get('stage', '').strip()
                    event_name = row.get('event_name', '').strip()
                    
                    mapping_key = (stage, event_name)
                    if mapping_key in event_mappings:
                        controller_name, value_type = event_mappings[mapping_key]
                        
                        # 解析传感器数据
                        sensor_data = []
                        for i in range(1, sensor_count + 1):
                            sensor_key = f'sensor{i}'
                            if sensor_key in row and row[sensor_key]:
                                try:
                                    sensor_data.append(float(row[sensor_key]))
                                except ValueError:
                                    sensor_data.append(2500.0)
                            else:
                                sensor_data.append(2500.0)
                        
                        # 解析权重数据
                        weights = []
                        for i in range(1, sensor_count + 1):
                            weight_key = f'weight{i}'
                            if weight_key in row and row[weight_key]:
                                try:
                                    weights.append(float(row[weight_key]))
                                except ValueError:
                                    weights.append(0.0)
                            else:
                                weights.append(0.0)
                        
                        # 解析误差范围
                        try:
                            error_range = float(row.get('error_range', 0.1))
                        except:
                            error_range = 0.1
                        
                        # 存储到配置中
                        config = self.stage_configs[controller_name]
                        
                        if value_type == 'original':
                            config['original_values'] = sensor_data
                            config['weights'] = weights
                            config['error_range'] = error_range
                            print(f"UDP发送器加载 {controller_name} 原始值: {sensor_data[:3]}...")
                        elif value_type == 'target':
                            config['target_values'] = sensor_data
                            print(f"UDP发送器加载 {controller_name} 目标值: {sensor_data[:3]}...")
            
            self.events_file_loaded = True
            print("UDP发送器：事件文件加载完成")
            
            # 验证加载的数据
            self._validate_loaded_data()
            return True
            
        except Exception as e:
            print(f"UDP发送器：加载事件文件失败: {e}")
            return False
    
    def _validate_loaded_data(self):
        """验证加载的数据完整性"""
        print("\n=== UDP发送器：验证加载的阶段数据 ===")
        for stage_name, config in self.stage_configs.items():
            has_original = len(config['original_values']) > 0
            has_target = len(config['target_values']) > 0
            has_weights = any(w != 0 for w in config['weights'])
            
            status = "✓" if (has_original and has_target and has_weights) else "✗"
            print(f"{status} {stage_name}: 原始值={has_original}, 目标值={has_target}, 权重={has_weights}, 误差范围={config['error_range']}")
    
    def send_spine_data(self, sensor_data):
        """发送脊柱数据到Unity"""
        if not self.enable or not self.socket:
            return False
        
        current_time = time.time()
        
        try:
            # 计算四个阶段的加权归一化值
            stage_values = self._calculate_all_stage_values(sensor_data)
            
            # 获取四个阶段的误差范围
            stage_error_ranges = self._get_all_error_ranges()
            
            # 准备数据包
            data_package = {
                "timestamp": current_time,
                "sensor_data": sensor_data,
                "stage_values": stage_values,
                "stage_error_ranges": stage_error_ranges,
                "sensor_count": len(sensor_data),
                "events_file_loaded": self.events_file_loaded
            }
            
            # 转换为JSON并发送
            json_data = json.dumps(data_package, cls=NumpyEncoder)
            self.socket.sendto(json_data.encode(), (self.host, self.port))
            
            self.sent_count += 1
            
            # 每10秒输出一次状态
            if current_time - self.last_status_time >= 10:
                print(f"脊柱数据发送状态: 已发送 {self.sent_count} 个数据包，错误 {self.error_count} 次")
                self.last_status_time = current_time
            
            return True
            
        except Exception as e:
            self.error_count += 1
            if self.error_count % 50 == 1:
                print(f"发送脊柱数据失败: {e}")
            
            # 连续失败过多时重新初始化
            if self.error_count >= 500:
                print(f"连续 {self.error_count} 次发送失败，尝试重新初始化Socket...")
                if self.socket:
                    self.socket.close()
                self.socket = None
                self.init_socket()
                self.error_count = 0  # 重置错误计数
            
            return False
    
    def _calculate_all_stage_values(self, sensor_data):
        """计算四个阶段的加权归一化值"""
        stage_values = {}
        
        for stage_name, config in self.stage_configs.items():
            stage_values[stage_name] = self._calculate_stage_weighted_value(sensor_data, config)
        
        return stage_values
    
    def _calculate_stage_weighted_value(self, sensor_data, config):
        """计算单个阶段的加权归一化值"""
        if not self.events_file_loaded:
            # 如果没有加载事件文件，使用简化计算
            return self._calculate_simple_weighted_value(sensor_data, config.get('weights', []))
        
        original_values = config.get('original_values', [])
        target_values = config.get('target_values', [])
        weights = config.get('weights', [])
        
        if not original_values or not target_values or not weights:
            return 0.5  # 默认值
        
        total_weight = 0
        weighted_sum = 0
        
        for i, sensor_val in enumerate(sensor_data):
            if i < len(weights) and i < len(original_values) and i < len(target_values):
                weight = abs(weights[i])
                if weight == 0:
                    continue
                
                original_val = original_values[i]
                target_val = target_values[i]
                
                # 计算0-1映射（原始值=1，目标值=0）
                if abs(original_val - target_val) > 1e-6:
                    normalized = (sensor_val - target_val) / (original_val - target_val)
                    # 限制在0-1范围内
                    normalized = max(0.0, min(1.0, normalized))
                else:
                    normalized = 0.5
                
                weighted_sum += normalized * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.5
    
    def _calculate_simple_weighted_value(self, sensor_data, weights):
        """简化的加权归一化值计算（当没有事件文件时使用）"""
        total_weight = 0
        weighted_sum = 0
        
        for i, sensor_val in enumerate(sensor_data):
            if i < len(weights) and weights[i] != 0:
                weight = abs(weights[i])
                # 简化的归一化：假设传感器值在2000-3000范围内
                normalized = (sensor_val - 2500) / 500 + 0.5
                normalized = max(0.0, min(1.0, normalized))
                
                weighted_sum += normalized * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.5
    
    def _get_all_error_ranges(self):
        """获取所有阶段的误差范围"""
        return {
            stage_name: config.get('error_range', 0.1)
            for stage_name, config in self.stage_configs.items()
        }
    
    def update_weights_from_control_panel(self, control_panel):
        """从控制面板更新权重配置"""
        try:
            controllers = [
                ('gray_rotation', control_panel.gray_rotation),
                ('blue_curvature', control_panel.blue_curvature),
                ('gray_tilt', control_panel.gray_tilt),
                ('green_tilt', control_panel.green_tilt)
            ]
            
            for stage_name, controller in controllers:
                weights = []
                sensor_count = len(self.stage_configs[stage_name].get('weights', [7]))
                for i in range(max(sensor_count, 7)):  # 至少7个传感器
                    if i < len(controller.sensor_checkboxes):
                        if controller.sensor_checkboxes[i].isChecked():
                            if i < len(controller.weight_spinboxes):
                                weights.append(controller.weight_spinboxes[i].value())
                            else:
                                weights.append(0.0)
                        else:
                            weights.append(0.0)
                    else:
                        weights.append(0.0)
                
                # 更新权重（但保持原始值和目标值不变）
                if not self.events_file_loaded:
                    self.stage_configs[stage_name]['weights'] = weights
                
                # 更新误差范围
                if hasattr(controller, 'get_error_range'):
                    self.stage_configs[stage_name]['error_range'] = controller.get_error_range()
                    
        except Exception as e:
            print(f"从控制面板更新权重失败: {e}")
    
    def close(self):
        """关闭Socket连接"""
        if self.socket:
            self.socket.close()
            self.socket = None


class SensorMonitorMainWindow(QMainWindow):
    """
    传感器监测应用主窗口（修改版）
    =============================
    
    新增功能：
    1. 医生端/患者端模式切换
    2. 复用组件逻辑
    3. 基于模式的事件处理
    4. UDP数据发送功能
    5. 修复蓝牙接收器初始化问题
    """
    
    def __init__(self):
        print("4. 开始初始化主窗口...")
        super().__init__()
        self.setWindowTitle("智能服装传感器监测与可视化")
        self.resize(1920, 1080)
        
        print("5. 开始创建组件...")
        
        # ====== 数据处理核心组件 ======
        self.data_manager = DataManager()
        self.data_count = 0
        print("6. 数据管理器创建完成")
        
        # ====== 界面控制组件 ======
        self.control_panel = ControlPanel()
        
        # ====== 设置初始传感器数量 ======
        initial_sensor_count = self.control_panel.get_num_sensors()
        print(f"6.1. 初始传感器数量设置为: {initial_sensor_count}")
        
        # ====== 卡尔曼滤波器 ======
        self.kalman_filter = MultiSensorKalmanFilter(
            num_sensors=initial_sensor_count,
            process_noise=0.01,
            measurement_noise=0.1
        )
        print("6.2. 卡尔曼滤波器创建完成")
        
        # ====== 事件记录器 ======
        self.event_recorder = EventRecorder()
        print("7. 事件记录器创建完成")
        
        # 创建三个独立的绘图组件用于三个tab
        self.plot_widget_tab1 = SensorPlotWidget()  # tab1专用
        self.plot_widget_tab2 = SensorPlotWidget()  # tab2专用 
        self.plot_widget_tab3 = SensorPlotWidget()  # tab3专用
        print("8. 界面控制组件创建完成")
        
        # 设置事件记录器的传感器数量
        self.event_recorder.set_num_sensors(initial_sensor_count)
        print(f"9. 事件记录器传感器数量设置为: {initial_sensor_count}")
        
        # ====== 数据采集组件 ======
        self.serial_thread = None
        self.bluetooth_receiver = None

        # ====== 功能模块组件 ======
        self.blocks_manager = BlocksTabManager(sensor_count=initial_sensor_count)
        blocks_tab = self.blocks_manager.get_tab_widget()
        if hasattr(blocks_tab, 'event_recorder'):
            blocks_tab.event_recorder.set_num_sensors(initial_sensor_count)
        
        # 设置父窗口引用，用于获取当前模式
        self.blocks_manager.set_parent_window(self)
        print("10. 积木可视化管理器创建完成")
        
        # ====== 患者积木可视化标签页 ======
        try:
            self.patient_blocks_tab = PatientBlocksTab(sensor_count=initial_sensor_count)
            print("11. 患者积木可视化标签页创建完成")
        except Exception as e:
            print(f"创建患者积木可视化标签页时发生错误: {e}")
            self.patient_blocks_tab = None

        # ====== 当前模式 ======
        self.current_mode = "doctor"  # 默认医生端模式

        # ====== 患者端映射数据 ======
        self.patient_mode_mapping_data = {
            'original_values': {},  # 存储各阶段原始值
            'target_values': {},    # 存储各阶段目标值
            'loaded': False         # 是否已加载映射数据
        }

        self.add_save_weights_to_events_functionality()
    
        print("前-k最大分配功能已集成完成")
        
        # ====== UDP发送器 ======
        self.spine_data_sender = SpineDataSender(
            host='127.0.0.1', 
            port=6667, 
            enable=False  # 默认禁用，可通过设置启用
        )
        print("12. UDP发送器初始化完成")
        
        # 设置UI
        print("13. 开始初始化UI...")
        self._init_ui()
        print("14. UI初始化完成")
        
        # 连接信号与槽
        print("15. 开始连接信号与槽...")
        self._connect_signals()
        print("16. 信号与槽连接完成")

        # 【新增】添加阶段和传感器的映射关系
        self.stage_sensor_mapping = {
            # 阶段1：骨盆前后翻转
            1: {
                'name': '骨盆前后翻转',
                'original_event': '开始训练',
                'target_event': '完成阶段',
                'sensor_indices': [0, 1]  # 对应sensor1, sensor2的索引
            },
            # 阶段2：脊柱曲率矫正
            2: {
                'name': '脊柱曲率矫正', 
                'original_event': '开始矫正',
                'target_event': '矫正完成',
                'sensor_indices': [2, 3]  # 对应sensor3, sensor4的索引
            },
            # 阶段3a：骨盆左右倾斜
            '3a': {
                'name': '骨盆左右倾斜',
                'original_event': '开始沉髋',
                'target_event': '沉髋结束',
                'sensor_indices': [4, 5]  # 对应sensor5, sensor6的索引
            },
            # 阶段3b：肩部左右倾斜
            '3b': {
                'name': '肩部左右倾斜',
                'original_event': '开始沉肩',
                'target_event': '沉肩结束',
                'sensor_indices': [6, 7]  # 对应sensor7, sensor8的索引
            }
        }
        
        # 【新增】动态阶段映射配置
        self.dynamic_stage_mapping = {
            # 阶段1：骨盆前后翻转 - 总是使用前两个传感器
            1: {
                'name': '骨盆前后翻转',
                'original_event': '开始训练',
                'target_event': '完成阶段',
                'sensor_indices': [0, 1]  # 总是使用sensor1, sensor2
            },
            # 阶段2：脊柱曲率矫正 - 使用第3、4个传感器（如果存在）
            2: {
                'name': '脊柱曲率矫正', 
                'original_event': '开始矫正',
                'target_event': '矫正完成',
                'sensor_indices': [2, 3]  # 使用sensor3, sensor4
            },
            # 阶段3a：骨盆左右倾斜 - 使用第5、6个传感器（如果存在）
            '3a': {
                'name': '骨盆左右倾斜',
                'original_event': '开始沉髋',
                'target_event': '沉髋结束',
                'sensor_indices': [4, 5]  # 使用sensor5, sensor6
            },
            # 阶段3b：肩部左右倾斜 - 使用第7、8个传感器（如果存在）
            '3b': {
                'name': '肩部左右倾斜',
                'original_event': '开始沉肩',
                'target_event': '沉肩结束',
                'sensor_indices': [6, 7]  # 使用sensor7, sensor8
            }
        }
    
    def _init_ui(self):
        """初始化用户界面"""
        print("17. 开始创建UI布局...")

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局(垂直分割)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # ====== 创建标签页容器 ======
        self.tab_widget = QTabWidget()
        
        # tab1: 监测标签页（传感器数据监测）
        monitor_widget = self._create_monitor_tab_with_controls()
        self.tab_widget.addTab(monitor_widget, "传感器监测")
        
        # tab2: 积木可视化标签页（医生端）
        blocks_tab = self._create_blocks_tab_with_plot()
        self.tab_widget.addTab(blocks_tab, "积木可视化")

        # tab3: 患者积木可视化标签页
        if self.patient_blocks_tab is not None:
            patient_tab = self._create_patient_tab_with_plot()
            self.tab_widget.addTab(patient_tab, "积木可视化-患者")

        main_layout.addWidget(self.tab_widget)

    def _create_monitor_tab_with_controls(self):
        """创建包含控制面板的监测标签页"""
        monitor_widget = QWidget()
        monitor_layout = QHBoxLayout()
        monitor_widget.setLayout(monitor_layout)
        # 创建图表区域
        chart_widget = QWidget()
        chart_layout = QVBoxLayout()
        chart_widget.setLayout(chart_layout)
        chart_layout.addWidget(self.plot_widget_tab1)
        # 添加到分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.control_panel)
        splitter.addWidget(chart_widget)
        splitter.setSizes([300, 700])
        monitor_layout.addWidget(splitter)
        # 信号同步：从control_panel.spine_type_selector发射
        self.control_panel.spine_type_selector.spine_type_changed.connect(self._sync_spine_type_to_tabs)
        self.control_panel.spine_type_selector.spine_direction_changed.connect(self._sync_spine_direction_to_tabs)
        return monitor_widget

    def _sync_spine_type_to_tabs(self, spine_type):
        # tab2
        blocks_tab = self.blocks_manager.get_tab_widget()
        if hasattr(blocks_tab, 'set_spine_config'):
            blocks_tab.set_spine_config(spine_type, self.control_panel.spine_type_selector.spine_direction)
        # tab3
        if self.patient_blocks_tab and hasattr(self.patient_blocks_tab, 'set_spine_config'):
            self.patient_blocks_tab.set_spine_config(spine_type, self.control_panel.spine_type_selector.spine_direction)
    def _sync_spine_direction_to_tabs(self, spine_direction):
        # tab2
        blocks_tab = self.blocks_manager.get_tab_widget()
        if hasattr(blocks_tab, 'set_spine_config'):
            blocks_tab.set_spine_config(self.control_panel.spine_type_selector.spine_type, spine_direction)
        # tab3
        if self.patient_blocks_tab and hasattr(self.patient_blocks_tab, 'set_spine_config'):
            self.patient_blocks_tab.set_spine_config(self.control_panel.spine_type_selector.spine_type, spine_direction)

    def _create_blocks_tab_with_plot(self):
        """创建带绘图控制的积木可视化标签页"""
        # 获取原始的积木标签页
        blocks_tab = self.blocks_manager.get_tab_widget()
        
        # 设置外部绘图控件
        blocks_tab.set_external_plot_widget(self.plot_widget_tab2)
        
        return blocks_tab

    def _create_patient_tab_with_plot(self):
        """创建患者标签页并设置绘图控件"""
        if self.patient_blocks_tab:
            # 设置绘图控件
            self.patient_blocks_tab.set_plot_widget(self.plot_widget_tab3)
        return self.patient_blocks_tab

    def _connect_signals(self):
        """连接信号与槽"""
        # ====== 控制面板信号连接 ======
        # 数据保存路径变更
        self.control_panel.data_path_changed.connect(self.data_manager.set_save_path)
        self.control_panel.events_path_changed.connect(self.event_recorder.set_events_file_path)
        
        # 添加事件文件路径变更的调试信息
        def on_events_path_changed(path):
            print(f"\n=== 事件文件路径变更 ===")
            print(f"新路径: {path}")
            print(f"路径是否存在: {os.path.exists(path) if path else False}")
            if path and os.path.exists(path):
                print(f"文件大小: {os.path.getsize(path)} 字节")
            self.event_recorder.set_events_file_path(path)
            # 同时更新患者标签页的事件文件路径
            if self.patient_blocks_tab:
                print("更新患者标签页的事件文件路径")
                self.patient_blocks_tab.set_events_file_path(path)
            print("=== 事件文件路径更新完成 ===\n")
            
        self.control_panel.events_path_changed.connect(on_events_path_changed)

        # 【新增】连接tab2阶段控制模块的按钮信号
        self._connect_stage_control_signals()

        # 传感器数量变更
        self.control_panel.sensor_count_changed.connect(self.event_recorder.set_num_sensors)
        
        # 【新增】连接传感器数量变更到tab2的传感器选择器
        self.control_panel.sensor_count_changed.connect(self.update_tab2_sensor_count)
        
        # 【新增】连接传感器数量变更到积木可视化标签页
        self.control_panel.sensor_count_changed.connect(
            lambda count: self.blocks_manager.get_tab_widget().set_sensor_count(count)
        )
        
        # 新增：模式变更信号
        self.control_panel.mode_changed.connect(self.on_mode_changed)
        
        # 新增：UDP设置变更信号
        self.control_panel.udp_settings_changed.connect(self.on_udp_settings_changed)
        
        # 新增：滤波参数变更信号
        self.control_panel.filter_params_changed.connect(self.on_filter_params_changed)
        
        # 连接积木可视化Tab的事件路径设置
        self.control_panel.events_path_changed.connect(
            lambda path: self.blocks_manager.get_tab_widget().set_events_save_path(path)
        )
        
        # 连接患者标签页的事件路径设置
        if self.patient_blocks_tab:
            self.control_panel.events_path_changed.connect(self.patient_blocks_tab.set_events_file_path)
        
        # 连接传感器数量变更到积木可视化Tab的事件记录器
        self.control_panel.sensor_count_changed.connect(
            lambda count: self.blocks_manager.get_tab_widget().event_recorder.set_num_sensors(count)
        )
        
        # 连接传感器数量变更到患者积木可视化Tab
        if self.patient_blocks_tab:
            self.control_panel.sensor_count_changed.connect(self.patient_blocks_tab.set_sensor_count)
        
        # 三个绘图控件的显示控制（共用控制面板设置）
        for plot_widget in [self.plot_widget_tab1, self.plot_widget_tab2, self.plot_widget_tab3]:
            self.control_panel.curve_visibility_changed.connect(plot_widget.set_curve_visibility)
            self.control_panel.curve_color_changed.connect(plot_widget.set_curve_color)
            self.control_panel.curve_name_changed.connect(plot_widget.set_curve_name)
        
        # 数据采集控制
        self.control_panel.acquisition_started.connect(self.start_acquisition)
        self.control_panel.acquisition_stopped.connect(self.stop_acquisition)

        # ====== 积木可视化模块信号连接 ======
        self.blocks_manager.alert_signal.connect(self.show_alert)
        self.control_panel.data_path_changed.connect(
            lambda path: self.blocks_manager.get_tab_widget().update_save_path_display(path)
        )

        # 传感器数量变更
        self.control_panel.sensor_count_changed.connect(self.event_recorder.set_num_sensors)
        
        # 【新增】连接传感器数量变更到卡尔曼滤波器
        self.control_panel.sensor_count_changed.connect(self.update_kalman_filter_sensor_count)

        # 新增：增强参数变更信号
        self.control_panel.enhancement_params_changed.connect(self.on_enhancement_params_changed)

    def update_tab2_sensor_count(self, count):
        """更新tab2中所有传感器选择器的传感器数量"""
        try:
            print(f"\n=== 更新tab2传感器数量 ===")
            print(f"新的传感器数量: {count}")
            
            # 【新增】首先更新阶段映射配置
            self.update_stage_mapping_for_sensor_count(count)
            
            # 获取tab2的积木可视化组件
            blocks_tab = self.blocks_manager.get_tab_widget()
            
            # 查找所有的传感器选择器组件
            sensor_selectors = self._find_all_sensor_selectors(blocks_tab)
            
            if sensor_selectors:
                print(f"找到 {len(sensor_selectors)} 个传感器选择器")
                
                # 更新每个传感器选择器的数量
                for i, selector in enumerate(sensor_selectors):
                    try:
                        selector.set_sensor_count(count)
                        print(f"  ✓ 第{i+1}个传感器选择器数量已更新")
                    except Exception as e:
                        print(f"  ✗ 第{i+1}个传感器选择器更新失败: {e}")
                        
                print("tab2传感器数量更新完成")
            else:
                print("警告: 在tab2中未找到传感器选择器")
                
        except Exception as e:
            print(f"更新tab2传感器数量时出错: {e}")
            import traceback
            traceback.print_exc()

    def update_stage_mapping_for_sensor_count(self, sensor_count):
        """根据传感器数量动态更新阶段映射配置"""
        try:
            print(f"\n=== 更新阶段映射配置 ===")
            print(f"传感器数量: {sensor_count}")
            
            # 创建新的动态映射
            new_mapping = {}
            
            # 阶段1：骨盆前后翻转 - 总是使用前两个传感器
            if sensor_count >= 2:
                new_mapping[1] = {
                    'name': '骨盆前后翻转',
                    'original_event': '开始训练',
                    'target_event': '完成阶段',
                    'sensor_indices': [0, 1]
                }
                print("  ✓ 阶段1: 骨盆前后翻转 - 传感器[0,1]")
            
            # 阶段2：脊柱曲率矫正 - 使用第3、4个传感器（如果存在）
            if sensor_count >= 4:
                new_mapping[2] = {
                    'name': '脊柱曲率矫正',
                    'original_event': '开始矫正',
                    'target_event': '矫正完成',
                    'sensor_indices': [2, 3]
                }
                print("  ✓ 阶段2: 脊柱曲率矫正 - 传感器[2,3]")
            
            # 阶段3a：骨盆左右倾斜 - 使用第5、6个传感器（如果存在）
            if sensor_count >= 6:
                new_mapping['3a'] = {
                    'name': '骨盆左右倾斜',
                    'original_event': '开始沉髋',
                    'target_event': '沉髋结束',
                    'sensor_indices': [4, 5]
                }
                print("  ✓ 阶段3a: 骨盆左右倾斜 - 传感器[4,5]")
            
            # 阶段3b：肩部左右倾斜 - 使用第7、8个传感器（如果存在）
            if sensor_count >= 8:
                new_mapping['3b'] = {
                    'name': '肩部左右倾斜',
                    'original_event': '开始沉肩',
                    'target_event': '沉肩结束',
                    'sensor_indices': [6, 7]
                }
                print("  ✓ 阶段3b: 肩部左右倾斜 - 传感器[6,7]")
            
            # 更新阶段映射
            self.stage_sensor_mapping = new_mapping
            print(f"阶段映射更新完成，共 {len(new_mapping)} 个阶段")
            
            return new_mapping
            
        except Exception as e:
            print(f"更新阶段映射配置时出错: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _find_all_sensor_selectors(self, parent_widget):
        """递归查找所有SensorSelector组件"""
        
        
        selectors = []
        
        try:
            # 方法1：直接查找SensorSelector类型的子组件
            if hasattr(parent_widget, 'findChildren'):
                selectors.extend(parent_widget.findChildren(SensorSelector))
            
            # 方法2：通过已知的属性名查找
            known_selector_attrs = [
                'gray_rotation', 'blue_curvature', 'gray_tilt', 'green_tilt',
                'selector1', 'selector2', 'selector3', 'selector4',
                'rotation_selector', 'curvature_selector', 'tilt_selector'
            ]
            
            for attr_name in known_selector_attrs:
                if hasattr(parent_widget, attr_name):
                    attr_value = getattr(parent_widget, attr_name)
                    if isinstance(attr_value, SensorSelector):
                        if attr_value not in selectors:
                            selectors.append(attr_value)
                            print(f"  通过属性名找到传感器选择器: {attr_name}")
            
            # 方法3：检查control_panel中的传感器选择器
            if hasattr(parent_widget, 'control_panel') and parent_widget.control_panel:
                control_panel = parent_widget.control_panel
                for attr_name in known_selector_attrs:
                    if hasattr(control_panel, attr_name):
                        attr_value = getattr(control_panel, attr_name)
                        if isinstance(attr_value, SensorSelector):
                            if attr_value not in selectors:
                                selectors.append(attr_value)
                                print(f"  通过control_panel找到传感器选择器: {attr_name}")
            
            # 方法4：检查父窗口本身的control_panel
            if hasattr(self, 'control_panel') and self.control_panel:
                for attr_name in known_selector_attrs:
                    if hasattr(self.control_panel, attr_name):
                        attr_value = getattr(self.control_panel, attr_name)
                        if isinstance(attr_value, SensorSelector):
                            if attr_value not in selectors:
                                selectors.append(attr_value)
                                print(f"  通过主窗口control_panel找到传感器选择器: {attr_name}")
            
        except Exception as e:
            print(f"查找传感器选择器时出错: {e}")
        
        return selectors

    def on_udp_settings_changed(self, enabled, host, port):
        """处理UDP设置变更"""
        print(f"UDP设置变更: 启用={enabled}, 地址={host}:{port}")
        
        self.spine_data_sender.enable = enabled
        self.spine_data_sender.host = host
        self.spine_data_sender.port = port
        
        if enabled and not self.spine_data_sender.socket:
            self.spine_data_sender.init_socket()
        elif not enabled and self.spine_data_sender.socket:
            self.spine_data_sender.close()

    def on_filter_params_changed(self, filter_params):
        """处理滤波参数变更"""
        print(f"滤波参数变更: 启用={filter_params['enabled']}, "
              f"过程噪声={filter_params['process_noise']:.3f}, "
              f"测量噪声={filter_params['measurement_noise']:.3f}")
        
        # 更新卡尔曼滤波器参数
        if filter_params['enabled']:
            self.kalman_filter.update_filter_parameters(
                process_noise=filter_params['process_noise'],
                measurement_noise=filter_params['measurement_noise']
            )
            print("卡尔曼滤波器参数已实时更新")
        else:
            print("卡尔曼滤波已禁用")

    # 【新增方法】连接阶段控制信号
    def _connect_stage_control_signals(self):
        """连接阶段控制模块的按钮信号"""
        try:
            blocks_tab = self.blocks_manager.get_tab_widget()
            
            # 连接脊柱类型变更信号
            if hasattr(blocks_tab, 'spine_type_changed'):
                blocks_tab.spine_type_changed.connect(self._on_spine_type_changed)
            
            # 方法1：如果blocks_tab有具体的按钮属性
            # C型事件按钮映射
            c_type_button_mappings = [
                ('start_training_btn', '开始训练', 1),
                ('complete_stage_btn', '完成阶段', 1),
                ('start_correction_btn', '开始矫正', 2),
                ('complete_correction_btn', '矫正完成', 2),
                ('start_hip_btn', '开始沉髋', 3),
                ('end_hip_btn', '沉髋完成', 3),
                ('start_shoulder_btn', '开始沉肩', 3),
                ('end_shoulder_btn', '沉肩完成', 3),
            ]
            
            # S型事件按钮映射
            s_type_button_mappings = [
                ('start_training_btn', '开始训练', 1),
                ('complete_stage_btn', '完成阶段', 1),
                ('start_lumbar_correction_btn', '开始腰椎矫正', 2),
                ('lumbar_correction_complete_btn', '腰椎矫正完成', 2),
                ('start_thoracic_correction_btn', '开始胸椎矫正', 3),
                ('thoracic_correction_complete_btn', '胸椎矫正完成', 3),
                ('start_shoulder_adjustment_btn', '开始肩部调整', 4),
                ('shoulder_adjustment_complete_btn', '肩部调整完成', 4),
            ]
            
            # 合并所有按钮映射
            all_button_mappings = c_type_button_mappings + s_type_button_mappings
            
            connected_count = 0
            for btn_attr, event_name, stage_key in all_button_mappings:
                if hasattr(blocks_tab, btn_attr):
                    button = getattr(blocks_tab, btn_attr)
                    if hasattr(button, 'clicked'):
                        button.clicked.connect(
                            lambda checked, en=event_name, sk=stage_key: self.on_stage_button_clicked(en, sk)
                        )
                        connected_count += 1
                        print(f"已连接按钮: {btn_attr} -> {event_name}")
            
            # 方法2：如果blocks_tab有阶段控制组件
            if hasattr(blocks_tab, 'stage_control'):
                stage_control = blocks_tab.stage_control
                for btn_attr, event_name, stage_key in all_button_mappings:
                    if hasattr(stage_control, btn_attr):
                        button = getattr(stage_control, btn_attr)
                        if hasattr(button, 'clicked'):
                            button.clicked.connect(
                                lambda checked, en=event_name, sk=stage_key: self.on_stage_button_clicked(en, sk)
                            )
                            connected_count += 1
                            print(f"已连接阶段控制按钮: {btn_attr} -> {event_name}")
            
            # 方法3：如果blocks_tab有自定义的连接方法
            if hasattr(blocks_tab, 'connect_stage_signals'):
                blocks_tab.connect_stage_signals(self.on_stage_button_clicked)
                print("通过自定义方法连接阶段信号")
            
            if connected_count > 0:
                print(f"✓ 成功连接了 {connected_count} 个阶段控制按钮")
            else:
                print("⚠ 未找到可连接的阶段控制按钮，请检查blocks_tab的结构")
                
        except Exception as e:
            print(f"连接阶段控制信号失败: {e}")


    def _on_spine_type_changed(self, spine_type):
        """处理脊柱类型变更事件"""
        print(f"脊柱类型已变更为: {spine_type}")
        
        # 更新UDP发送器的阶段配置（如果需要）
        if hasattr(self, 'spine_data_sender') and self.spine_data_sender:
            # 可以在这里更新UDP发送器的配置
            pass
        
        # 更新患者端映射数据结构（如果需要）
        if hasattr(self, 'patient_mode_mapping_data'):
            # 根据脊柱类型调整患者端映射
            if spine_type == "S":
                # S型需要4个阶段的映射数据
                self.patient_mode_mapping_data = {
                    'original_values': {1: [], 2: [], 3: [], 4: []},
                    'target_values': {1: [], 2: [], 3: [], 4: []},
                    'loaded': False
                }
            else:
                # C型保持3个阶段
                self.patient_mode_mapping_data = {
                    'original_values': {1: [], 2: [], 3: []},
                    'target_values': {1: [], 2: [], 3: []},
                    'loaded': False
                }
    
    
    def on_stage_button_clicked(self, event_name, stage_key):
        """
        处理阶段控制模块按钮点击事件（支持S型脊柱）
        
        Args:
            event_name: 事件名称，如 '开始训练', '完成阶段', '开始腰椎矫正' 等
            stage_key: 阶段键，如 1, 2, 3, 4
        """
        print(f"\n=== 阶段按钮被点击 ===")
        print(f"事件名称: {event_name}")
        print(f"阶段键: {stage_key}")
        
        # 获取当前脊柱类型
        blocks_tab = self.blocks_manager.get_tab_widget()
        spine_type = blocks_tab.get_spine_type() if hasattr(blocks_tab, 'get_spine_type') else "C"
        
        print(f"脊柱类型: {spine_type}")
        
        # 获取当前传感器数据
        current_sensor_data = self.event_recorder.get_current_sensor_data()
        if not current_sensor_data:
            print("警告: 当前没有传感器数据")
            return
        
        print(f"当前传感器数据: {current_sensor_data[:8]}...")
        
        # 检查阶段映射
        if spine_type not in self.stage_sensor_mapping:
            print(f"未找到脊柱类型 {spine_type} 的映射配置")
            return
        
        spine_mapping = self.stage_sensor_mapping[spine_type]
        if stage_key not in spine_mapping:
            print(f"未找到脊柱类型 {spine_type} 阶段 {stage_key} 的映射配置")
            return
        
        stage_mapping = spine_mapping[stage_key]
        
        # 获取对应的传感器选择器
        sensor_selector = self._get_sensor_selector_for_stage(stage_key, spine_type)
        if not sensor_selector:
            print(f"未找到脊柱类型 {spine_type} 阶段 {stage_key} 的传感器选择器")
            return
        
        # 获取当前权重分配模式
        current_mode = sensor_selector.current_weight_mode
        print(f"当前权重分配模式: {current_mode}")
        
        # 确定是原始值还是目标值事件
        if event_name == stage_mapping['original_event']:
            # 原始值事件
            print(f"处理原始值事件: {event_name}")
            
            # 存储原始值
            sensor_selector.store_original_values(current_sensor_data)
            print(f"原始值已存储到 {stage_mapping['name']}")
            
            # 记录原始值事件
            self._record_simple_event(event_name, stage_key, current_sensor_data, spine_type)
            
        elif event_name == stage_mapping['target_event']:
            # 目标值事件
            print(f"处理目标值事件: {event_name}")
            
            # 存储目标值
            sensor_selector.store_target_values(current_sensor_data)
            print(f"目标值已存储到 {stage_mapping['name']}")
            
        else:
            print(f"事件 '{event_name}' 不匹配脊柱类型 {spine_type} 阶段 {stage_key} 的预期事件")
            return
        
        print("=== 处理完成 ===\n")

    def _record_simple_event(self, event_name, stage_key, sensor_data, spine_type="C"):
        """记录简单事件（支持脊柱类型）"""
        try:
            # 记录事件（包含脊柱类型信息）
            self.event_recorder.record_event(
                event_name=event_name,
                stage=f"{spine_type}型-阶段{stage_key}",
                additional_data={
                    'spine_type': spine_type,
                    'stage_key': stage_key
                }
            )
            
            print(f"简单事件已记录: {event_name} ({spine_type}型-阶段{stage_key})")
            
        except Exception as e:
            print(f"记录简单事件时出错: {e}")

    def _record_stage_event_with_weights(self, event_name, stage_key, sensor_data, sensor_selector):
        """记录阶段事件（目标值事件，包含自动分配的权重）"""
        try:
            # 获取自动分配后的权重
            weights = sensor_selector.get_weights() if sensor_selector else [0.0] * self.control_panel.get_num_sensors()
            
            # 获取误差范围
            error_range = sensor_selector.get_error_range() if sensor_selector else 0.1
            
            # 准备额外数据
            additional_data = {
                'sensor_weights': weights,
                'error_range': error_range,
                'auto_assigned': True  # 标记这是自动分配的权重
            }
            
            # 记录事件
            self.event_recorder.record_event(
                event_name=event_name,
                stage=f"阶段{stage_key}",
                additional_data=additional_data
            )
            
            print(f"阶段事件已记录（包含自动权重）: {event_name}")
            print(f"权重: {weights[:3]}...")
            
        except Exception as e:
            print(f"记录阶段事件时出错: {e}")

    def add_save_weights_to_events_functionality(self):
        """添加"保存权重到事件文件"功能"""
        try:
            # 获取所有阶段的传感器选择器
            stage_selectors = {
                1: self._get_sensor_selector_for_stage(1),
                2: self._get_sensor_selector_for_stage(2),
                '3a': self._get_sensor_selector_for_stage('3a'),
                '3b': self._get_sensor_selector_for_stage('3b')
            }
            
            # 为每个阶段创建"保存权重到事件文件"的逻辑
            for stage_key, selector in stage_selectors.items():
                if selector:
                    # 连接权重自动分配完成信号
                    selector.weights_auto_assigned.connect(
                        lambda weights, sk=stage_key: self._on_weights_auto_assigned(sk, weights)
                    )
            
        except Exception as e:
            print(f"添加保存权重功能时出错: {e}")

    def _on_weights_auto_assigned(self, stage_key, weights):
        """处理权重自动分配完成事件（修改版）"""
        try:
            print(f"\n=== 权重分配完成，保存到事件文件 ===")
            print(f"阶段: {stage_key}")
            print(f"权重: {[f'{w:.3f}' for w in weights if w > 0]}")
            
            # 获取当前传感器数据
            current_sensor_data = self.event_recorder.get_current_sensor_data()
            if not current_sensor_data:
                print("警告: 当前没有传感器数据")
                return
            
            # 获取对应的传感器选择器
            sensor_selector = self._get_sensor_selector_for_stage(stage_key)
            if not sensor_selector:
                print(f"未找到阶段 {stage_key} 的传感器选择器")
                return
            
            # 确定事件名称（使用目标事件名称，如"完成阶段"）
            stage_mapping = self.stage_sensor_mapping.get(stage_key)
            if not stage_mapping:
                print(f"未找到阶段 {stage_key} 的映射配置")
                return
            
            # 使用目标事件名称
            event_name = stage_mapping['target_event']
            
            # 获取误差范围
            error_range = sensor_selector.get_error_range()
            
            # 获取当前权重分配模式
            weight_mode = sensor_selector.current_weight_mode
            
            # 准备额外数据
            additional_data = {
                'sensor_weights': weights,
                'error_range': error_range,
                'weight_mode': weight_mode,  # 标记是自动分配还是手动分配
                'auto_assigned': (weight_mode == "auto"),
                'stage_completed': True  # 标记这是阶段完成事件
            }
            
            # 记录目标值事件（包含权重信息）
            self.event_recorder.record_event(
                event_name=event_name,
                stage=f"阶段{stage_key}",
                additional_data=additional_data
            )
            
            print(f"目标值事件已记录（包含权重）: {event_name}")
            print(f"权重模式: {weight_mode}")
            print(f"权重和: {sum(weights):.6f}")
            print("=== 权重保存到事件文件完成 ===\n")
            
        except Exception as e:
            print(f"处理权重分配时出错: {e}")
            import traceback
            traceback.print_exc()

    def _record_stage_event(self, event_name, stage_key, sensor_data, sensor_selector):
        """记录阶段事件（原始值事件）"""
        try:
            # 获取当前权重（可能还是默认值）
            weights = sensor_selector.get_weights() if sensor_selector else [0.0] * self.control_panel.get_num_sensors()
            
            # 获取误差范围
            error_range = sensor_selector.get_error_range() if sensor_selector else 0.1
            
            # 准备额外数据
            additional_data = {
                'sensor_weights': weights,
                'error_range': error_range
            }
            
            # 记录事件
            self.event_recorder.record_event(
                event_name=event_name,
                stage=f"阶段{stage_key}",
                additional_data=additional_data
            )
            
            print(f"阶段事件已记录: {event_name}")
            
        except Exception as e:
            print(f"记录阶段事件时出错: {e}")

    def _get_sensor_selector_for_stage(self, stage_key, spine_type="C"):
        """获取指定阶段的传感器选择器（支持脊柱类型）"""
        try:
            # 获取积木可视化标签页
            blocks_tab = self.blocks_manager.get_tab_widget()
            
            # 根据脊柱类型和阶段键获取对应的传感器选择器
            if spine_type == "C":
                # C型脊柱选择器映射
                stage_selector_mapping = {
                    1: 'gray_rotation',          # 阶段1: 骨盆前后翻转
                    2: 'blue_curvature',         # 阶段2: 脊柱曲率矫正
                    3: 'gray_tilt'               # 阶段3: 关节平衡调整（主要使用骨盆左右倾斜）
                }
            else:  # S型脊柱
                # S型脊柱选择器映射
                stage_selector_mapping = {
                    1: 'gray_rotation',          # 阶段1: 骨盆前后翻转
                    2: 'blue_curvature',         # 阶段2: 腰椎曲率矫正
                    3: 'blue_curvature',         # 阶段3: 胸椎曲率矫正（复用）
                    4: 'green_tilt'              # 阶段4: 关节平衡调整（只使用肩部左右倾斜）
                }
            
            selector_name = stage_selector_mapping.get(stage_key)
            if not selector_name:
                return None
            
            # 从传感器参数设置模块获取选择器
            if hasattr(blocks_tab, 'sensor_params'):
                sensor_params = blocks_tab.sensor_params
                if hasattr(sensor_params, selector_name):
                    return getattr(sensor_params, selector_name)
            
            # 或者从控制面板获取
            if hasattr(blocks_tab, 'control_panel') and hasattr(blocks_tab.control_panel, selector_name):
                return getattr(blocks_tab.control_panel, selector_name)
            
            return None
            
        except Exception as e:
            print(f"获取传感器选择器时出错: {e}")
            return None
    
    # 【新增方法】更新tab2传感器参数
    def update_tab2_sensor_parameters(self, stage_key, stage_mapping, action_type, sensor_data):
        """
        更新tab2中传感器参数设置模块的数值
        
        Args:
            stage_key: 阶段键
            stage_mapping: 阶段映射配置
            action_type: 'original' 或 'target'
            sensor_data: 当前传感器数据列表
        
        Returns:
            bool: 更新是否成功
        """
        try:
            # 获取tab2的积木可视化组件
            blocks_tab = self.blocks_manager.get_tab_widget()
            
            # 检查是否有传感器参数设置组件
            if not hasattr(blocks_tab, 'sensor_params'):
                print("错误: tab2中未找到sensor_params组件")
                return False
            
            sensor_params = blocks_tab.sensor_params
            stage_name = stage_mapping['name']
            sensor_indices = stage_mapping['sensor_indices']
            
            print(f"更新阶段: {stage_name}")
            print(f"传感器索引: {sensor_indices}")
            
            # 根据阶段名称找到对应的参数组
            parameter_group = self._find_parameter_group(sensor_params, stage_name)
            if not parameter_group:
                print(f"未找到阶段 '{stage_name}' 的参数组")
                return False
            
            # 更新参数组中的SpinBox控件
            return self._update_spinboxes_in_group(parameter_group, action_type, sensor_data, sensor_indices)
                
        except Exception as e:
            print(f"更新传感器参数时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # 【新增方法】查找参数组
    def _find_parameter_group(self, sensor_params, stage_name):
        """查找指定阶段的参数组"""
        try:
            from PyQt5.QtWidgets import QGroupBox
            
            # 预定义的阶段名称关键词
            stage_keywords = {
                '骨盆前后翻转': ['骨盆', '前后', '翻转', 'pelvic', 'anterior', 'posterior'],
                '脊柱曲率矫正': ['脊柱', '曲率', '矫正', 'spinal', 'curvature', 'correction'],
                '骨盆左右倾斜': ['骨盆', '左右', '倾斜', 'pelvic', 'lateral'],
                '肩部左右倾斜': ['肩部', '肩膀', '左右', '倾斜', 'shoulder', 'lateral']
            }
            
            keywords = stage_keywords.get(stage_name, [])
            
            # 方法1: 通过属性名查找
            for attr_name in dir(sensor_params):
                if not attr_name.startswith('_'):
                    attr_value = getattr(sensor_params, attr_name)
                    if isinstance(attr_value, QGroupBox):
                        attr_lower = attr_name.lower()
                        if any(keyword in attr_lower for keyword in keywords):
                            print(f"通过属性名找到参数组: {stage_name} -> {attr_name}")
                            return attr_value
            
            # 方法2: 通过findChildren查找
            if hasattr(sensor_params, 'findChildren'):
                all_groups = sensor_params.findChildren(QGroupBox)
                for group in all_groups:
                    group_title = group.title().lower() if hasattr(group, 'title') else ""
                    group_name = group.objectName().lower() if hasattr(group, 'objectName') else ""
                    
                    if any(keyword in group_title or keyword in group_name for keyword in keywords):
                        print(f"通过title/name找到参数组: {stage_name} -> {group_title or group_name}")
                        return group
            
            return None
            
        except Exception as e:
            print(f"查找参数组失败: {e}")
            return None
    
    # 【新增方法】更新参数组中的SpinBox
    def _update_spinboxes_in_group(self, group_widget, action_type, sensor_data, sensor_indices):
        """更新参数组中的SpinBox控件"""
        try:
            from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox
            
            # 查找所有SpinBox控件
            all_spinboxes = []
            if hasattr(group_widget, 'findChildren'):
                all_spinboxes = group_widget.findChildren(QSpinBox) + group_widget.findChildren(QDoubleSpinBox)
            
            print(f"在参数组中找到 {len(all_spinboxes)} 个SpinBox控件")
            print(f"传感器数据长度: {len(sensor_data)}")
            print(f"需要更新的传感器索引: {sensor_indices}")
            
            # 预定义的控件名称模式
            type_patterns = {
                'original': ['original', 'start', 'init', '原始', '初始'],
                'target': ['target', 'best', 'goal', 'end', '最佳', '目标', '结束']
            }
            
            updated_count = 0
            skipped_count = 0
            
            # 遍历需要更新的传感器
            for sensor_idx in sensor_indices:
                if sensor_idx >= len(sensor_data):
                    print(f"  ⚠ 传感器索引 {sensor_idx} 超出数据范围 (数据长度: {len(sensor_data)})")
                    skipped_count += 1
                    continue
                
                sensor_value = sensor_data[sensor_idx]
                sensor_name = f"sensor{sensor_idx + 1}"
                
                print(f"  处理传感器 {sensor_name} (索引{sensor_idx}): 值={sensor_value}")
                
                # 查找对应的SpinBox
                target_spinbox = None
                
                for spinbox in all_spinboxes:
                    spinbox_name = spinbox.objectName().lower() if hasattr(spinbox, 'objectName') else ""
                    
                    # 检查是否包含传感器名称和类型
                    if sensor_name in spinbox_name:
                        type_patterns_list = type_patterns.get(action_type, [])
                        if any(pattern in spinbox_name for pattern in type_patterns_list):
                            target_spinbox = spinbox
                            print(f"    找到匹配的SpinBox: {spinbox_name}")
                            break
                
                # 如果找到了对应的SpinBox，更新其值
                if target_spinbox:
                    try:
                        # 检查值的范围
                        min_val = target_spinbox.minimum()
                        max_val = target_spinbox.maximum()
                        
                        original_value = sensor_value
                        if sensor_value < min_val:
                            sensor_value = min_val
                            print(f"    值 {original_value} 小于最小值 {min_val}，调整为 {sensor_value}")
                        elif sensor_value > max_val:
                            sensor_value = max_val
                            print(f"    值 {original_value} 大于最大值 {max_val}，调整为 {sensor_value}")
                        
                        # 设置值
                        target_spinbox.setValue(sensor_value)
                        updated_count += 1
                        
                        print(f"    ✓ 更新 {sensor_name} {action_type}: {sensor_value}")
                        
                    except Exception as e:
                        print(f"    ✗ 设置 {sensor_name} {action_type} 失败: {e}")
                else:
                    print(f"    ⚠ 未找到 {sensor_name} {action_type} 的SpinBox")
                    skipped_count += 1
            
            success = updated_count > 0
            print(f"更新结果: 成功 {updated_count} 个，跳过 {skipped_count} 个")
            return success
            
        except Exception as e:
            print(f"更新SpinBox失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def on_mode_changed(self, mode):
        """处理模式变更"""
        self.current_mode = mode
        print(f"模式切换为: {mode}")
        
        if mode == "patient":
            # 患者端模式：如果正在采集，立即启动患者界面的训练模式
            if self.patient_blocks_tab:
                # 设置事件文件路径
                events_save_path = self.control_panel.get_events_save_path()
                print(f"患者端模式：事件文件路径 = {events_save_path}")
                if events_save_path:
                    self.patient_blocks_tab.set_events_file_path(events_save_path)
                    print("患者端模式：事件文件路径已设置")
                else:
                    print("患者端模式：警告 - 事件文件路径未设置")
                
                # 如果当前正在采集数据，立即启动训练模式
                if hasattr(self, 'serial_thread') and self.serial_thread and self.serial_thread.isRunning():
                    print("患者端模式：串口采集正在运行，启动训练模式")
                    result = self.patient_blocks_tab.start_training_mode()
                    print(f"患者端模式：训练模式启动结果 = {result}")
                elif hasattr(self, 'bluetooth_receiver') and self.bluetooth_receiver and self.bluetooth_receiver.isRunning():
                    print("患者端模式：蓝牙采集正在运行，启动训练模式")
                    result = self.patient_blocks_tab.start_training_mode()
                    print(f"患者端模式：训练模式启动结果 = {result}")
                else:
                    print("患者端模式：当前没有数据采集在运行")
                    
        elif mode == "doctor":
            # 医生端模式：停止患者界面的训练模式
            if self.patient_blocks_tab:
                self.patient_blocks_tab.stop_training_mode()
                print("医生端模式：患者训练模式已停止")
    

    # def load_patient_mapping_data(self):
    #     """加载患者端数据映射所需的原始值和目标值（修正版 - 使用最后一次同名事件）"""
    #     events_save_path = self.control_panel.get_events_save_path()
    #     if not events_save_path or not os.path.exists(events_save_path):
    #         print("事件文件不存在，无法加载映射数据")
    #         return False
            
    #     try:
    #         import csv
            
    #         print(f"\n=== 开始加载映射数据（使用最后一次同名事件）===")
    #         print(f"事件文件路径: {events_save_path}")
    #         print(f"文件大小: {os.path.getsize(events_save_path)} 字节")
            
    #         # 修正：使用正确的事件名称映射
    #         event_mapping = {
    #             '开始训练': {'stage': 1, 'type': 'original'},
    #             '完成阶段': {'stage': 1, 'type': 'target'},
    #             '开始矫正': {'stage': 2, 'type': 'original'},
    #             '矫正完成': {'stage': 2, 'type': 'target'},
    #             '开始沉髋': {'stage': 3, 'type': 'original'},
    #             '沉髋完成': {'stage': 3, 'type': 'target'},
    #             '开始沉肩': {'stage': 3, 'type': 'original'},
    #             '沉肩完成': {'stage': 3, 'type': 'target'}
    #         }
            
    #         print(f"预期的事件名称: {list(event_mapping.keys())}")
            
    #         # 初始化数据结构
    #         self.patient_mode_mapping_data['original_values'] = {}
    #         self.patient_mode_mapping_data['target_values'] = {}
            
    #         # 【新增】用于跟踪同名事件的计数器和最新数据
    #         event_counters = {}
    #         latest_event_data = {}
            
    #         # 先读取文件内容进行调试
    #         print("\n--- 文件内容预览 ---")
    #         with open(events_save_path, 'r', encoding='utf-8') as f:
    #             lines = f.readlines()
    #             for i, line in enumerate(lines[:10]):  # 只显示前10行
    #                 print(f"行{i+1}: {line.strip()}")
    #             if len(lines) > 10:
    #                 print(f"... 总共{len(lines)}行")
            
    #         # 重新打开文件进行解析
    #         found_events = []
    #         with open(events_save_path, 'r', encoding='utf-8') as f:
    #             lines = f.readlines()
                
    #             # 找到第一个非注释行、非空行（即表头行）
    #             header_line_index = -1
    #             for i, line in enumerate(lines):
    #                 line = line.strip()
    #                 if line and not line.startswith('#'):
    #                     header_line_index = i
    #                     print(f"找到表头行在第{i+1}行: {line}")
    #                     break
                
    #             if header_line_index == -1:
    #                 print("错误: 找不到表头行")
    #                 return False
                
    #             # 从表头行开始重新创建CSV内容
    #             csv_content = '\n'.join(lines[header_line_index:])
                
    #             # 使用StringIO创建CSV reader
    #             from io import StringIO
    #             csv_file = StringIO(csv_content)
    #             reader = csv.DictReader(csv_file)
                
    #             # 打印CSV标题
    #             if reader.fieldnames:
    #                 print(f"\nCSV标题行: {reader.fieldnames}")
    #             else:
    #                 print("警告: 无法读取CSV标题行")
    #                 return False
                
    #             row_count = 0
    #             actual_data_row = 0
    #             for row in reader:
    #                 row_count += 1
                    
    #                 # 检查是否为空行（所有字段都为空）
    #                 if all(not str(value).strip() for value in row.values()):
    #                     print(f"跳过空行 {row_count}")
    #                     continue
                    
    #                 actual_data_row += 1
    #                 print(f"\n处理数据行{actual_data_row} (文件行{header_line_index + 1 + row_count})")
                    
    #                 event_name = row.get('event_name', '').strip()
    #                 stage = row.get('stage', '').strip()
                    
    #                 print(f"\n行{row_count}: event_name='{event_name}', stage='{stage}'")
                    
    #                 # 记录所有找到的事件
    #                 if event_name:
    #                     found_events.append(event_name)
                    
    #                 if event_name in event_mapping:
    #                     mapping_info = event_mapping[event_name]
    #                     target_stage = mapping_info['stage']
    #                     data_type = mapping_info['type']
                        
    #                     # 【新增】更新事件计数器
    #                     event_key = f"{event_name}_{target_stage}_{data_type}"
    #                     if event_key not in event_counters:
    #                         event_counters[event_key] = 0
    #                     event_counters[event_key] += 1
                        
    #                     print(f"  匹配成功! 目标阶段: {target_stage}, 数据类型: {data_type}")
    #                     print(f"  这是第 {event_counters[event_key]} 次出现此事件")
                        
    #                     # 提取传感器数据
    #                     sensor_data = []
    #                     num_sensors = self.control_panel.get_num_sensors()
    #                     print(f"  提取{num_sensors}个传感器的数据...")
                        
    #                     for i in range(1, num_sensors + 1):
    #                         sensor_key = f'sensor{i}'
    #                         if sensor_key in row and row[sensor_key]:
    #                             try:
    #                                 value = float(row[sensor_key])
    #                                 sensor_data.append(value)
    #                                 if i <= 3:  # 只显示前3个传感器的值
    #                                     print(f"    {sensor_key}: {value}")
    #                             except ValueError as e:
    #                                 print(f"    {sensor_key}: 转换失败 ({row[sensor_key]}) - 使用默认值2500")
    #                                 sensor_data.append(2500.0)
    #                         else:
    #                             print(f"    {sensor_key}: 不存在 - 使用默认值2500")
    #                             sensor_data.append(2500.0)
                        
    #                     # 【修改】无条件存储/更新数据（使用最后一次的数据）
    #                     if data_type == 'original':
    #                         # 检查是否已有旧数据
    #                         if target_stage in self.patient_mode_mapping_data['original_values']:
    #                             print(f"  更新原始值到阶段{target_stage}: {sensor_data[:3]}... (覆盖之前的数据)")
    #                         else:
    #                             print(f"  存储原始值到阶段{target_stage}: {sensor_data[:3]}...")
                            
    #                         self.patient_mode_mapping_data['original_values'][target_stage] = sensor_data
    #                         latest_event_data[f"original_{target_stage}"] = {
    #                             'data': sensor_data,
    #                             'count': event_counters[event_key],
    #                             'row': actual_data_row
    #                         }
                            
    #                     else:  # target
    #                         # 检查是否已有旧数据
    #                         if target_stage in self.patient_mode_mapping_data['target_values']:
    #                             print(f"  更新目标值到阶段{target_stage}: {sensor_data[:3]}... (覆盖之前的数据)")
    #                         else:
    #                             print(f"  存储目标值到阶段{target_stage}: {sensor_data[:3]}...")
                            
    #                         self.patient_mode_mapping_data['target_values'][target_stage] = sensor_data
    #                         latest_event_data[f"target_{target_stage}"] = {
    #                             'data': sensor_data,
    #                             'count': event_counters[event_key],
    #                             'row': actual_data_row
    #                         }
    #                 else:
    #                     if event_name:
    #                         print(f"  未匹配的事件名称: '{event_name}'")
            
    #         print(f"\n--- 解析结果 ---")
    #         print(f"总共处理了{row_count}行数据")
    #         print(f"找到的所有事件名称: {list(set(found_events))}")
            
    #         # 【新增】显示同名事件统计信息
    #         print(f"\n--- 同名事件统计 ---")
    #         for event_key, count in event_counters.items():
    #             if count > 1:
    #                 print(f"  {event_key}: 出现 {count} 次 (使用最后一次)")
    #             else:
    #                 print(f"  {event_key}: 出现 {count} 次")
            
    #         # 【新增】显示最终使用的数据信息
    #         print(f"\n--- 最终使用的数据 ---")
    #         for data_key, info in latest_event_data.items():
    #             print(f"  {data_key}: 第{info['count']}次出现 (数据行{info['row']}) - {info['data'][:3]}...")
            
    #         print(f"\n成功加载的阶段数据:")
    #         print(f"  原始值阶段: {list(self.patient_mode_mapping_data['original_values'].keys())}")
    #         print(f"  目标值阶段: {list(self.patient_mode_mapping_data['target_values'].keys())}")
            
    #         # 检查数据完整性
    #         success = False
    #         for stage in [1, 2, 3]:
    #             has_original = stage in self.patient_mode_mapping_data['original_values']
    #             has_target = stage in self.patient_mode_mapping_data['target_values']
                
    #             if has_original and has_target:
    #                 original_info = latest_event_data.get(f"original_{stage}", {})
    #                 target_info = latest_event_data.get(f"target_{stage}", {})
    #                 print(f"  阶段{stage}: 数据完整 ✓ (原始值第{original_info.get('count', 1)}次, 目标值第{target_info.get('count', 1)}次)")
    #                 success = True
    #             elif has_original:
    #                 original_info = latest_event_data.get(f"original_{stage}", {})
    #                 print(f"  阶段{stage}: 仅有原始值 ⚠️ (第{original_info.get('count', 1)}次)")
    #             elif has_target:
    #                 target_info = latest_event_data.get(f"target_{stage}", {})
    #                 print(f"  阶段{stage}: 仅有目标值 ⚠️ (第{target_info.get('count', 1)}次)")
    #             else:
    #                 print(f"  阶段{stage}: 无数据 ✗")
            
    #         if success:
    #             self.patient_mode_mapping_data['loaded'] = True
    #             print("\n✓ 映射数据加载成功（使用最后一次同名事件数据）")
                
    #             # 设置数据管理器的映射数据
    #             if hasattr(self.data_manager, 'set_patient_mapping_data'):
    #                 self.data_manager.set_patient_mapping_data(self.patient_mode_mapping_data)
    #                 print("✓ 已设置数据管理器的映射数据")
                
    #             return True
    #         else:
    #             print("\n✗ 映射数据加载失败: 没有找到完整的阶段数据")
    #             return False
            
    #     except Exception as e:
    #         print(f"\n✗ 加载患者端映射数据失败: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         return False


    def load_patient_mapping_data(self):
        """加载患者端数据映射所需的原始值和目标值（支持S型脊柱）"""
        events_save_path = self.control_panel.get_events_save_path()
        if not events_save_path or not os.path.exists(events_save_path):
            print("事件文件不存在，无法加载映射数据")
            return False
            
        try:
            import csv
            
            print(f"\n=== 开始加载映射数据（支持S型脊柱）===")
            print(f"事件文件路径: {events_save_path}")
            
            # 扩展事件名称映射以支持S型
            event_mapping = {
                # C型事件（保持原有）
                '开始训练': {'stage': 1, 'type': 'original'},
                '完成阶段': {'stage': 1, 'type': 'target'},
                '开始矫正': {'stage': 2, 'type': 'original'},
                '矫正完成': {'stage': 2, 'type': 'target'},
                '开始沉髋': {'stage': 3, 'type': 'original'},
                '沉髋完成': {'stage': 3, 'type': 'target'},
                '开始沉肩': {'stage': 3, 'type': 'original'},
                '沉肩完成': {'stage': 3, 'type': 'target'},
                
                # S型事件（新增）
                '开始腰椎矫正': {'stage': 2, 'type': 'original'},
                '腰椎矫正完成': {'stage': 2, 'type': 'target'},
                '开始胸椎矫正': {'stage': 3, 'type': 'original'},
                '胸椎矫正完成': {'stage': 3, 'type': 'target'},
                '开始肩部调整': {'stage': 4, 'type': 'original'},
                '肩部调整完成': {'stage': 4, 'type': 'target'}
            }
            
            # 获取当前脊柱类型
            blocks_tab = self.blocks_manager.get_tab_widget()
            spine_type = blocks_tab.get_spine_type() if hasattr(blocks_tab, 'get_spine_type') else "C"
            
            print(f"当前脊柱类型: {spine_type}")
            
            # 根据脊柱类型初始化数据结构
            if spine_type == "S":
                max_stages = 4
                self.patient_mode_mapping_data = {
                    'original_values': {1: [], 2: [], 3: [], 4: []},
                    'target_values': {1: [], 2: [], 3: [], 4: []},
                    'loaded': False
                }
            else:
                max_stages = 3
                self.patient_mode_mapping_data = {
                    'original_values': {1: [], 2: [], 3: []},
                    'target_values': {1: [], 2: [], 3: []},
                    'loaded': False
                }
            
            # 解析CSV文件（保持原有逻辑，但支持更多阶段）
            with open(events_save_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # 找到表头行
                header_line_index = -1
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        header_line_index = i
                        break
                
                if header_line_index == -1:
                    print("错误: 找不到表头行")
                    return False
                
                # 创建CSV读取器
                csv_content = '\n'.join(lines[header_line_index:])
                from io import StringIO
                csv_file = StringIO(csv_content)
                reader = csv.DictReader(csv_file)
                
                # 解析数据
                for row in reader:
                    # 检查是否为空行
                    if all(not str(value).strip() for value in row.values()):
                        continue
                    
                    event_name = row.get('event_name', '').strip()
                    stage_info = row.get('stage', '').strip()
                    
                    # 从stage信息中提取脊柱类型
                    if spine_type in stage_info or f"{spine_type}型" in stage_info:
                        if event_name in event_mapping:
                            mapping_info = event_mapping[event_name]
                            target_stage = mapping_info['stage']
                            data_type = mapping_info['type']
                            
                            # 只处理当前最大阶段范围内的数据
                            if target_stage <= max_stages:
                                # 提取传感器数据
                                sensor_data = []
                                num_sensors = self.control_panel.get_num_sensors()
                                
                                for i in range(1, num_sensors + 1):
                                    sensor_key = f'sensor{i}'
                                    if sensor_key in row and row[sensor_key]:
                                        try:
                                            sensor_data.append(float(row[sensor_key]))
                                        except ValueError:
                                            sensor_data.append(2500.0)
                                    else:
                                        sensor_data.append(2500.0)
                                
                                # 存储数据
                                if data_type == 'original':
                                    if target_stage not in self.patient_mode_mapping_data['original_values']:
                                        self.patient_mode_mapping_data['original_values'][target_stage] = sensor_data
                                else:  # target
                                    if target_stage not in self.patient_mode_mapping_data['target_values']:
                                        self.patient_mode_mapping_data['target_values'][target_stage] = sensor_data
            
            # 检查数据完整性
            success = False
            for stage in range(1, max_stages + 1):
                has_original = stage in self.patient_mode_mapping_data['original_values']
                has_target = stage in self.patient_mode_mapping_data['target_values']
                
                if has_original and has_target:
                    print(f"  阶段{stage}: 数据完整 ✓")
                    success = True
                elif has_original:
                    print(f"  阶段{stage}: 仅有原始值 ⚠️")
                elif has_target:
                    print(f"  阶段{stage}: 仅有目标值 ⚠️")
                else:
                    print(f"  阶段{stage}: 无数据 ✗")
            
            if success:
                self.patient_mode_mapping_data['loaded'] = True
                print(f"\n✓ {spine_type}型脊柱映射数据加载成功")
                
                # 设置数据管理器的映射数据
                if hasattr(self.data_manager, 'set_patient_mapping_data'):
                    self.data_manager.set_patient_mapping_data(self.patient_mode_mapping_data)
                
                return True
            else:
                print(f"\n✗ {spine_type}型脊柱映射数据加载失败: 没有找到完整的阶段数据")
                return False
            
        except Exception as e:
            print(f"\n✗ 加载患者端映射数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False


    def calculate_sensor_mapping(self, sensor_values):
        """计算传感器数据的0-1映射值"""
        if not self.patient_mode_mapping_data['loaded']:
            return sensor_values  # 如果没有加载映射数据，返回原始值
        
        # 获取当前阶段（假设患者端标签页有当前阶段信息）
        current_stage = 1  # 默认阶段1
        if self.patient_blocks_tab and hasattr(self.patient_blocks_tab, 'current_stage'):
            current_stage = self.patient_blocks_tab.current_stage
        
        # 获取该阶段的原始值和目标值
        original_values = self.patient_mode_mapping_data['original_values'].get(current_stage, [])
        target_values = self.patient_mode_mapping_data['target_values'].get(current_stage, [])
        
        if not original_values or not target_values:
            print(f"阶段{current_stage}的映射数据不完整")
            return sensor_values
        
        mapped_values = []
        for i, sensor_val in enumerate(sensor_values):
            if i < len(original_values) and i < len(target_values):
                original_val = original_values[i]
                target_val = target_values[i]
                
                # 计算0-1映射（原始值=1，目标值=0）
                if original_val != target_val:
                    if original_val > target_val:  # 递减情况
                        if sensor_val >= original_val:
                            mapped_val = 1.0
                        elif sensor_val <= target_val:
                            mapped_val = 0.0
                        else:
                            mapped_val = (sensor_val - target_val) / (original_val - target_val)
                    else:  # 递增情况
                        if sensor_val <= original_val:
                            mapped_val = 1.0
                        elif sensor_val >= target_val:
                            mapped_val = 0.0
                        else:
                            mapped_val = (original_val - sensor_val) / (original_val - target_val)
                else:
                    mapped_val = 0.5  # 原始值等于目标值的情况
                
                mapped_values.append(mapped_val)
            else:
                mapped_values.append(0.5)  # 默认值
        
        return mapped_values

    @pyqtSlot()
    def start_acquisition(self):
        """启动数据采集 - 改进患者端模式处理"""
        # 检查串口
        port = self.control_panel.get_port()
        if port == "无可用串口":
            QMessageBox.warning(self, "错误", "没有可用的串口，请检查连接")
            return
            
        # 检查保存路径
        data_save_path = self.control_panel.get_data_save_path()
        if not data_save_path:
            QMessageBox.warning(self, "错误", "请先设置所有数据保存路径")
            return
            
        events_save_path = self.control_panel.get_events_save_path()
        if not events_save_path:
            QMessageBox.warning(self, "错误", "请先设置事件数据保存路径")
            return
        
        # 检查是否选择了模式
        current_mode = self.control_panel.get_current_mode()
        if not current_mode:
            QMessageBox.warning(self, "错误", "请先选择医生端或患者端模式")
            return
            
        try:
            # 患者端模式：加载映射数据
            if current_mode == "patient":
                print("患者端模式：开始加载映射数据...")
                success = self.load_patient_mapping_data()
                if success:
                    print("患者端模式：映射数据加载成功")
                    # 设置数据管理器为患者端模式
                    if hasattr(self.data_manager, 'set_patient_mode'):
                        self.data_manager.set_patient_mode(True)
                    if hasattr(self.data_manager, 'set_patient_mapping_data'):
                        self.data_manager.set_patient_mapping_data(self.patient_mode_mapping_data)
                    
                    # 调试：检查映射状态
                    if hasattr(self.data_manager, 'debug_mapping_status'):
                        self.data_manager.debug_mapping_status()
                else:
                    print("患者端模式：映射数据加载失败，但继续启动采集")
                    
            # 获取设置
            source_type = self.control_panel.get_source_type()
            baud_rate = self.control_panel.get_baud_rate()
            num_sensors = self.control_panel.get_num_sensors()
            duration = self.control_panel.get_duration()
            
            # 设置数据管理器的保存路径
            self.data_manager.set_save_path(data_save_path)
            
            # 设置事件记录器参数
            self.event_recorder.set_num_sensors(num_sensors)
            self.event_recorder.start_new_acquisition()
            
            # 清空数据并开始新的采集会话
            self.data_manager.clear_data()
            self.data_manager.start_acquisition() 
            
            # 【新增】重置卡尔曼滤波器
            self.kalman_filter.reset_filters()
            print("卡尔曼滤波器已重置，准备开始新的数据采集")
            
            # 【新增】更新卡尔曼滤波器参数
            filter_params = self.control_panel.get_filter_params()
            if filter_params['enabled']:
                self.kalman_filter.update_filter_parameters(
                    process_noise=filter_params['process_noise'],
                    measurement_noise=filter_params['measurement_noise']
                )
                print(f"卡尔曼滤波参数已更新: 过程噪声={filter_params['process_noise']:.3f}, "
                      f"测量噪声={filter_params['measurement_noise']:.3f}")
            else:
                print("卡尔曼滤波已禁用")
            
            # 设置图表（根据模式选择性设置）
            colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k'] * 3
            
            if current_mode == "doctor":
                # 医生端模式：设置tab1和tab2
                self.plot_widget_tab1.setup_curves(num_sensors, colors)
                self.plot_widget_tab2.setup_curves(num_sensors, colors)
            elif current_mode == "patient":
                # 患者端模式：设置tab1和tab3
                self.plot_widget_tab1.setup_curves(num_sensors, colors)
                self.plot_widget_tab3.setup_curves(num_sensors, colors)
                
                # 立即启动患者端训练模式
                if self.patient_blocks_tab:
                    # 设置事件文件路径
                    print(f"患者端采集开始：设置事件文件路径 = {events_save_path}")
                    self.patient_blocks_tab.set_events_file_path(events_save_path)
                    # 启动训练模式，立即显示阶段1
                    print("患者端采集开始：启动训练模式")
                    result = self.patient_blocks_tab.start_training_mode()
                    print(f"患者端采集开始：训练模式启动结果 = {result}")
                    if result:
                        print("患者端采集开始：训练模式已启动，显示阶段1")
                    else:
                        print("患者端采集开始：训练模式启动失败")
            
            # 更新曲线可见性控制
            self.control_panel.update_curve_visibility_controls(num_sensors, colors)

            # 启动数据采集
            if source_type == "serial":
                self._start_serial_acquisition(port, baud_rate, num_sensors, duration)
            else:
                self._start_bluetooth_acquisition(port, baud_rate, num_sensors, duration)
                
            # 通知积木可视化模块开始采集
            blocks_tab = self.blocks_manager.get_tab_widget()
            if hasattr(blocks_tab, 'start_acquisition'):
                blocks_tab.start_acquisition()
                
            # 更新UDP发送器配置
            if self.spine_data_sender.enable:
                # 更新权重配置
                self.spine_data_sender.update_weights_from_control_panel(self.control_panel)
                # 加载事件文件配置
                if events_save_path and os.path.exists(events_save_path):
                    self.spine_data_sender.load_events_file(events_save_path, self.control_panel.get_num_sensors())
                
            QMessageBox.information(self, "成功", "数据采集已启动")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动数据采集时发生错误：\n{str(e)}")
            print(f"启动采集失败: {e}")
            import traceback
            traceback.print_exc()

    def _start_serial_acquisition(self, port, baud_rate, num_sensors, duration):
        """启动串口数据采集"""
        if self.bluetooth_receiver and self.bluetooth_receiver.isRunning():
            self.bluetooth_receiver.stop()
            self.bluetooth_receiver.wait()

        # 创建串口采集线程 - 修复参数传递
        try:
            # 方案1：尝试标准参数格式
            self.serial_thread = SerialThread(port, baud_rate, num_sensors)
        except TypeError:
            try:
                # 方案2：尝试关键字参数
                self.serial_thread = SerialThread(port=port, baud_rate=baud_rate, num_sensors=num_sensors)
            except TypeError:
                try:
                    # 方案3：只传递必要参数
                    self.serial_thread = SerialThread(port, baud_rate)
                    if hasattr(self.serial_thread, 'set_num_sensors'):
                        self.serial_thread.set_num_sensors(num_sensors)
                except TypeError:
                    # 方案4：最简单的参数
                    self.serial_thread = SerialThread(port)
                    if hasattr(self.serial_thread, 'set_baud_rate'):
                        self.serial_thread.set_baud_rate(baud_rate)
                    if hasattr(self.serial_thread, 'set_num_sensors'):
                        self.serial_thread.set_num_sensors(num_sensors)
        
        # 设置持续时间
        if duration and hasattr(self.serial_thread, 'set_duration'):
            self.serial_thread.set_duration(duration)
    
        # 连接信号 - 修复信号连接
        self.serial_thread.data_received.connect(self.process_sensor_data)
        self.serial_thread.error_occurred.connect(self.handle_serial_error)
    
        # 启动线程
        self.serial_thread.start()
        print(f"串口采集已启动: {port}@{baud_rate}")
    
   
    def _create_bluetooth_receiver_safely(self):
        """安全地创建蓝牙接收器"""
        try:
            # 方案1：传递data_manager参数（根据错误信息）
            return BluetoothReceiver(self.data_manager)
        except TypeError as e:
            if "missing 1 required positional argument: 'data_manager'" in str(e):
                print("确认需要data_manager参数")
                raise e
            else:
                # 尝试其他参数组合
                try:
                    return BluetoothReceiver()
                except TypeError:
                    try:
                        return BluetoothReceiver(port="COM1")  # 默认端口
                    except TypeError:
                        # 如果都失败了，重新抛出原始错误
                        raise e
        except Exception as e:
            print(f"创建蓝牙接收器时发生未知错误: {e}")
            raise e




    def _start_bluetooth_acquisition(self, port, baud_rate, num_sensors, duration):
        """启动蓝牙数据采集 - 修复连接状态检查问题"""
        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_thread.stop()
            self.serial_thread.wait()
            self.serial_thread = None
        
        # 停止现有的蓝牙连接
        if self.bluetooth_receiver:
            try:
                if hasattr(self.bluetooth_receiver, 'stop'):
                    self.bluetooth_receiver.stop()
                if hasattr(self.bluetooth_receiver, 'wait'):
                    self.bluetooth_receiver.wait(1000)
            except:
                pass
            self.bluetooth_receiver = None
        
        # 创建新的蓝牙接收器
        try:
            self.bluetooth_receiver = self._create_bluetooth_receiver_safely()
            print("蓝牙接收器创建成功")
        except Exception as e:
            print(f"创建蓝牙接收器失败: {e}")
            QMessageBox.warning(self, "错误", f"无法创建蓝牙接收器：{e}")
            return
        
        # 连接信号
        if hasattr(self.bluetooth_receiver, 'data_received'):
            self.bluetooth_receiver.data_received.connect(self.process_sensor_data)
        if hasattr(self.bluetooth_receiver, 'error_occurred'):
            self.bluetooth_receiver.error_occurred.connect(self.handle_bluetooth_error)
        
        # 配置接收器参数
        if hasattr(self.bluetooth_receiver, 'set_num_sensors'):
            self.bluetooth_receiver.set_num_sensors(num_sensors)
        if duration and hasattr(self.bluetooth_receiver, 'set_duration'):
            self.bluetooth_receiver.set_duration(duration)
        
        # 实际连接蓝牙设备
        if not self.bluetooth_receiver.connect(port, baud_rate):
            QMessageBox.warning(self, "错误", "无法连接到蓝牙设备")
            return
            
        print(f"蓝牙设备已连接到 {port}，波特率 {baud_rate}")
        
        # 启动数据接收
        if not self.bluetooth_receiver.start_receiving():
            QMessageBox.warning(self, "错误", "无法启动数据接收")
            return
            
        print("蓝牙数据接收已启动")
        
        # 启动数据接收定时器（作为备用方案）
        self._start_bluetooth_data_polling()


    def _force_bluetooth_start(self):
        """强制启动蓝牙数据接收"""
        try:
            print("尝试强制启动蓝牙数据接收...")
            
            # 强制设置所有可能的连接状态
            if self.bluetooth_receiver:
                # 设置连接标志
                for attr in dir(self.bluetooth_receiver):
                    if 'connect' in attr.lower() and not attr.startswith('_'):
                        try:
                            if callable(getattr(self.bluetooth_receiver, attr)):
                                continue  # 跳过方法
                            setattr(self.bluetooth_receiver, attr, True)
                            print(f"设置属性 {attr} = True")
                        except:
                            pass
                
                # 尝试直接调用run方法（如果是QThread）
                if hasattr(self.bluetooth_receiver, 'run'):
                    import threading
                    self.bluetooth_thread = threading.Thread(
                        target=self.bluetooth_receiver.run, 
                        daemon=True
                    )
                    self.bluetooth_thread.start()
                    print("在独立线程中启动蓝牙接收器")
                    return True
                
                # 尝试设置为运行状态并手动触发数据接收
                if hasattr(self.bluetooth_receiver, 'start_receiving'):
                    # 强制设置运行状态
                    self.bluetooth_receiver._connected = True
                    self.bluetooth_receiver.start_receiving()
                    print("强制启动数据接收")
                    return True
            
            return False
            
        except Exception as e:
            print(f"强制启动失败: {e}")
            return False
        
    def _start_bluetooth_data_polling(self):
        """启动蓝牙数据轮询（备用方案）"""
        try:
            from PyQt5.QtCore import QTimer
            
            # 创建定时器进行数据轮询
            if not hasattr(self, 'bluetooth_polling_timer'):
                self.bluetooth_polling_timer = QTimer()
                self.bluetooth_polling_timer.timeout.connect(self._poll_bluetooth_data)
            
            # 每100ms检查一次数据
            self.bluetooth_polling_timer.start(100)
            print("启动蓝牙数据轮询定时器")
            
        except Exception as e:
            print(f"启动数据轮询失败: {e}")

    def _poll_bluetooth_data(self):
        """轮询蓝牙数据（备用数据获取方法）"""
        if not self.bluetooth_receiver:
            return
        
        try:
            # 方法1：尝试各种数据获取方法
            data_methods = [
                'get_data', 'read_data', 'receive_data', 'poll_data',
                'get_latest_data', 'fetch_data', 'receive', 'read'
            ]
            
            for method_name in data_methods:
                if hasattr(self.bluetooth_receiver, method_name):
                    try:
                        method = getattr(self.bluetooth_receiver, method_name)
                        if callable(method):
                            data = method()
                            if data:
                                print(f"通过 {method_name} 获取到数据: {data[:5] if len(data) > 5 else data}")
                                self.process_sensor_data(data)
                                return
                    except Exception as e:
                        continue
            
            # 方法2：检查数据属性
            data_attrs = ['data', 'latest_data', 'current_data', 'buffer']
            for attr_name in data_attrs:
                if hasattr(self.bluetooth_receiver, attr_name):
                    try:
                        data = getattr(self.bluetooth_receiver, attr_name)
                        if data and data != getattr(self, f'_last_{attr_name}', None):
                            print(f"通过属性 {attr_name} 获取到数据")
                            setattr(self, f'_last_{attr_name}', data)
                            self.process_sensor_data(data)
                            return
                    except Exception as e:
                        continue
                        
        except Exception as e:
            # 静默处理轮询错误，避免刷屏
            if not hasattr(self, '_poll_error_count'):
                self._poll_error_count = 0
            self._poll_error_count += 1
            if self._poll_error_count % 50 == 1:  # 每50次错误打印一次
                print(f"蓝牙数据轮询错误: {e}")

    def _check_bluetooth_status(self):
        """检查蓝牙状态（基本模式）"""
        try:
            # 尝试多种方法获取数据
            data = None
            
            if hasattr(self.bluetooth_receiver, 'get_latest_data'):
                data = self.bluetooth_receiver.get_latest_data()
            elif hasattr(self.bluetooth_receiver, 'poll'):
                data = self.bluetooth_receiver.poll()
            elif hasattr(self.bluetooth_receiver, 'check_data'):
                data = self.bluetooth_receiver.check_data()
            elif hasattr(self.bluetooth_receiver, 'data'):
                # 检查是否有data属性
                temp_data = getattr(self.bluetooth_receiver, 'data', None)
                if temp_data and temp_data != getattr(self, '_last_bluetooth_data', None):
                    data = temp_data
                    self._last_bluetooth_data = temp_data
            
            if data:
                self.process_sensor_data(data)
                
        except Exception as e:
            print(f"检查蓝牙状态时出错: {e}")


    @pyqtSlot()
    def stop_acquisition(self):
        """停止数据采集 - 改进蓝牙停止逻辑"""
        try:
            # 停止蓝牙轮询定时器
            if hasattr(self, 'bluetooth_polling_timer'):
                self.bluetooth_polling_timer.stop()
                print("蓝牙轮询定时器已停止")
            
            # 停止串口采集
            if hasattr(self, 'serial_thread') and self.serial_thread:
                if self.serial_thread.isRunning():
                    self.serial_thread.stop()
                    self.serial_thread.wait(3000)
                    if self.serial_thread.isRunning():
                        print("警告：串口线程未能正常停止，强制终止")
                        self.serial_thread.terminate()
                        self.serial_thread.wait(1000)
                self.serial_thread = None
                print("串口采集已停止")
                
            # 停止蓝牙采集 - 改进的停止逻辑
            if hasattr(self, 'bluetooth_receiver') and self.bluetooth_receiver:
                try:
                    print("正在停止蓝牙采集...")
                    
                    # 尝试多种停止方法
                    stop_methods = [
                        'stop_receiving', 'stop', 'close', 'disconnect', 
                        'terminate', 'quit', 'end', 'shutdown'
                    ]
                    
                    stopped = False
                    for method_name in stop_methods:
                        if hasattr(self.bluetooth_receiver, method_name):
                            try:
                                method = getattr(self.bluetooth_receiver, method_name)
                                if callable(method):
                                    method()
                                    print(f"蓝牙采集已停止（{method_name}方法）")
                                    stopped = True
                                    break
                            except Exception as e:
                                print(f"停止方法 {method_name} 失败: {e}")
                                continue
                    
                    # 如果是QThread，等待结束
                    if hasattr(self.bluetooth_receiver, 'wait'):
                        try:
                            self.bluetooth_receiver.wait(3000)
                            if hasattr(self.bluetooth_receiver, 'isRunning') and self.bluetooth_receiver.isRunning():
                                print("警告：蓝牙线程未能正常停止，强制终止")
                                if hasattr(self.bluetooth_receiver, 'terminate'):
                                    self.bluetooth_receiver.terminate()
                                    self.bluetooth_receiver.wait(1000)
                        except Exception as e:
                            print(f"等待蓝牙线程结束失败: {e}")
                    
                    self.bluetooth_receiver = None
                    print("蓝牙接收器已清理")
                    
                except Exception as e:
                    print(f"停止蓝牙采集时出错: {e}")
                    self.bluetooth_receiver = None
                
            # 重置错误计数
            if hasattr(self, '_bluetooth_error_count'):
                self._bluetooth_error_count = 0
            
            # ... 其余的停止逻辑保持不变 ...
            
            # 显示数据统计
            stats = self.data_manager.get_data_stats()
            print(f"采集完成 - 内存数据: {stats.get('display_data_count', 0)}, "
                  f"总数据: {stats.get('total_data_count', 0)}, "
                  f"原始数据: {stats.get('raw_data_count', 0)}")
            
            # 保存传感器数据到"所有数据文件路径"
            sensor_names = self.control_panel.get_curve_names()
            success = self.data_manager.save_data(
                parent_widget=self, 
                num_sensors=self.control_panel.get_num_sensors(),
                sensor_names=sensor_names
            )
            
            if success:
                # 保存训练记录
                training_records_path = self.control_panel.get_data_save_path().replace('.csv', '_training_records.xlsx')
                training_recorder = self.blocks_manager.get_training_recorder()
                if training_recorder:
                    try:
                        training_recorder.save_records(training_records_path)
                        print(f"训练记录已保存到: {training_records_path}")
                    except Exception as e:
                        print(f"保存训练记录失败: {e}")
            
            # 停止积木可视化模块的采集模式
            if hasattr(self.blocks_manager.get_tab_widget(), 'stop_acquisition'):
                self.blocks_manager.get_tab_widget().stop_acquisition()
                
            # 停止患者端训练模式
            if self.patient_blocks_tab:
                self.patient_blocks_tab.stop_training_mode()
                print("患者端训练模式已停止")
                
            # 重置数据管理器的患者端模式
            if self.current_mode == "patient":
                if hasattr(self.data_manager, 'set_patient_mode'):
                    self.data_manager.set_patient_mode(False)
                    print("数据管理器已退出患者端模式")
                
            # 显示保存完成信息
            events_count = self.event_recorder.get_events_count()
            data_save_path = self.control_panel.get_data_save_path()
            
            # 【新增】获取卡尔曼滤波统计信息
            filter_stats = self.kalman_filter.get_filter_stats()
            
            QMessageBox.information(
                self, "采集完成", 
                f"数据采集已完成！\n"
                f"已保存 {stats.get('total_data_count', 0)} 个滤波后数据点到：\n{data_save_path}\n"
                f"已保存 {stats.get('raw_data_count', 0)} 个原始数据点\n"
                f"卡尔曼滤波处理：{filter_stats['filtered_count']} 个数据点\n"
                f"已记录 {events_count} 个事件\n"
                f"滤波参数：过程噪声={filter_stats['process_noise']:.3f}, 测量噪声={filter_stats['measurement_noise']:.3f}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止数据采集时发生错误：\n{str(e)}")
            print(f"停止采集失败: {e}")
            import traceback
            traceback.print_exc()

    def process_sensor_data(self, data):
        """处理接收到的传感器数据（集成卡尔曼滤波）"""
        try:
            # 数据计数
            self.data_count += 1
            
            # 【新增】检查是否启用卡尔曼滤波
            filter_params = self.control_panel.get_filter_params()
            if filter_params['enabled']:
                # 进行卡尔曼滤波处理
                filtered_data, raw_data = self.kalman_filter.filter_data_with_timestamp(data)
                
                # 添加数据到数据管理器（保存滤波后的数据用于显示）
                self.data_manager.add_data_point(filtered_data)
                
                # 【新增】同时保存原始数据到数据管理器
                # 为原始数据添加标识，以便区分
                raw_data_with_flag = raw_data.copy()
                raw_data_with_flag.insert(0, "RAW")  # 添加标识
                self.data_manager.add_raw_data_point(raw_data_with_flag)
                
                # 使用滤波后的数据进行后续处理
                processed_data = filtered_data
            else:
                # 不进行滤波，直接使用原始数据
                filtered_data = data
                raw_data = data
                
                # 添加数据到数据管理器
                self.data_manager.add_data_point(data)
                
                # 使用原始数据进行后续处理
                processed_data = data
            
            # 更新事件记录器的当前传感器数据（使用处理后的数据）
            self.event_recorder.set_current_sensor_data(processed_data)
            
            # 获取显示数据用于图表更新（使用处理后的数据）
            display_data = self.data_manager.get_display_data()
            if display_data:
                # 根据当前模式选择性更新图表
                current_mode = self.control_panel.get_current_mode()
                
                if current_mode == "doctor":
                    # 医生端模式：更新tab1和tab2的图表
                    self.plot_widget_tab1.update_plot(display_data)
                    self.plot_widget_tab2.update_plot(display_data)
                    
                    # 传递给积木可视化模块
                    self.blocks_manager.process_sensor_data(processed_data)
                    
                elif current_mode == "patient":
                    # 患者端模式：更新tab1和tab3的图表
                    self.plot_widget_tab1.update_plot(display_data)
                    self.plot_widget_tab3.update_plot(display_data)
                    
                    # 传递给患者积木可视化标签页
                    if self.patient_blocks_tab:
                        self.patient_blocks_tab.update_sensor_data(processed_data)
                
            # UDP发送数据（使用处理后的数据）
            if self.spine_data_sender.enable and len(processed_data) > 1:
                sensor_data = processed_data[1:]  # 跳过时间戳（如果第一个元素是时间戳）
                self.spine_data_sender.send_spine_data(sensor_data)
                
            # 【新增】定期打印滤波统计信息
            if filter_params['enabled'] and self.data_count % 1000 == 0:
                filter_stats = self.kalman_filter.get_filter_stats()
                print(f"卡尔曼滤波统计 - 处理数据点: {filter_stats['filtered_count']}, "
                      f"传感器数量: {filter_stats['num_sensors']}")
                
        except Exception as e:
            print(f"处理传感器数据时出错: {e}")
            import traceback
            traceback.print_exc()

    def handle_serial_error(self, error_msg):
        """处理串口错误"""
        print(f"串口错误: {error_msg}")
        QMessageBox.warning(self, "串口错误", f"串口通信出现错误：\n{error_msg}")
        
    def handle_bluetooth_error(self, error_msg):
        """处理蓝牙错误 - 改进版"""
        print(f"蓝牙错误: {error_msg}")
        
        # 如果是连接相关错误，尝试解决
        if "未连接" in error_msg or "not connected" in error_msg.lower():
            print("检测到连接状态错误，尝试修复...")
            
            # 尝试重新设置连接状态
            try:
                if self.bluetooth_receiver:
                    success = self._bypass_bluetooth_connection_check()
                    if success:
                        print("连接状态修复成功，继续数据接收")
                        return  # 不显示错误对话框
            except Exception as e:
                print(f"连接状态修复失败: {e}")
        
        # 对于其他错误或修复失败的情况，显示警告
        # 但不要立即停止，给用户选择
        if hasattr(self, '_bluetooth_error_count'):
            self._bluetooth_error_count += 1
        else:
            self._bluetooth_error_count = 1
        
        # 只在前几次错误时显示对话框，避免刷屏
        if self._bluetooth_error_count <= 3:
            reply = QMessageBox.question(
                self, "蓝牙通信错误", 
                f"蓝牙通信出现错误：\n{error_msg}\n\n"
                "这可能是连接状态检查的问题。\n"
                "是否继续尝试接收数据？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                # 用户选择停止
                self.stop_acquisition()

    def show_alert(self, message):
        """显示警报信息"""
        QMessageBox.warning(self, "传感器警报", message)

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        try:
            if self.serial_thread and self.serial_thread.isRunning():
                self.serial_thread.stop()
                self.serial_thread.wait(2000)
                if self.serial_thread.isRunning():
                    self.serial_thread.terminate()
                    
            if self.bluetooth_receiver and self.bluetooth_receiver.isRunning():
                self.bluetooth_receiver.stop()
                self.bluetooth_receiver.wait(2000)
                if self.bluetooth_receiver.isRunning():
                    self.bluetooth_receiver.terminate()
                    
            # 关闭UDP发送器
            if self.spine_data_sender:
                self.spine_data_sender.close()
                
            event.accept()
        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            event.accept()

    def _bypass_bluetooth_connection_check(self):
        """绕过蓝牙连接检查，强制启动数据接收"""
        try:
            if not self.bluetooth_receiver:
                return False
                
            # 强制设置连接状态
            self.bluetooth_receiver.is_connected = True
            
            # 尝试直接启动数据接收
            if hasattr(self.bluetooth_receiver, 'start_receiving'):
                self.bluetooth_receiver.start_receiving()
                return True
                
            return False
            
        except Exception as e:
            print(f"绕过连接检查失败: {e}")
            return False

    def update_kalman_filter_sensor_count(self, new_sensor_count):
        """更新卡尔曼滤波器的传感器数量"""
        self.kalman_filter.set_num_sensors(new_sensor_count)
        print(f"卡尔曼滤波器的传感器数量已更新为: {new_sensor_count}")

    def on_enhancement_params_changed(self, enhancement_params):
        enabled = enhancement_params['enabled']
        method = enhancement_params['method']
        enhancement_params_dict = enhancement_params['enhancement_params']
        second_filter = enhancement_params['second_filter']
        self.data_enhancement.set_enhancement_enabled(enabled)
        self.data_enhancement.set_enhancement_method(method)
        if method == 'motion_and_lock':
            self.data_enhancement.set_motion_and_lock_params(
                diff_window=enhancement_params_dict.get('diff_window', 5),
                motion_thresh=enhancement_params_dict.get('motion_thresh', 0.015),
                motion_gain=enhancement_params_dict.get('motion_gain', 2.5),
                lock_smoothing=enhancement_params_dict.get('lock_smoothing', 0.95)
            )
        elif method == 'trend':
            self.data_enhancement.set_trend_enhancement_params(
                alpha=enhancement_params_dict.get('alpha', 0.8),
                gamma=enhancement_params_dict.get('gamma', 3.0)
            )
        elif method == 'local_contrast':
            self.data_enhancement.set_local_contrast_params(
                window_size=enhancement_params_dict.get('window_size', 11),
                gain=enhancement_params_dict.get('gain', 2.0)
            )
        elif method == 'gradient':
            self.data_enhancement.set_gradient_enhancement_params(
                alpha=enhancement_params_dict.get('alpha', 0.6),
                beta=enhancement_params_dict.get('beta', 0.4)
            )
        elif method == 'segment':
            self.data_enhancement.set_segment_enhancement_params(
                threshold=enhancement_params_dict.get('threshold', 0.05),
                scale=enhancement_params_dict.get('scale', 2.0)
            )
        self.data_enhancement.set_second_filter_enabled(second_filter['enabled'])
        self.data_enhancement.set_second_filter_method(second_filter['method'])
        self.data_enhancement.set_second_filter_params(second_filter['method'], second_filter['params'])


if __name__ == "__main__":
    try:
        print("17. 程序开始启动...")
        # 启用高DPI支持
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 创建应用实例
        app = QApplication(sys.argv)
        print("18. 创建应用实例完成")
        
        # 设置应用程序样式
        app.setStyle('Fusion')
        
        # 创建并显示主窗口
        print("19. 开始创建主窗口...")
        window = SensorMonitorMainWindow()
        print("20. 主窗口创建完成")
        window.show()
        print("21. 主窗口显示完成")
        
        # 运行应用程序
        print("22. 开始运行应用程序...")
        sys.exit(app.exec_())
    except Exception as e:
        print(f"程序启动错误: {str(e)}")
        import traceback
        print("错误堆栈:")
        print(traceback.format_exc())
        sys.exit(1)