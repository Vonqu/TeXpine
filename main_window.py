#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口模块（修改版） - 实现新的交互逻辑 + UDP发送功能
=====================================

修改内容：
1. 实现医生端/患者端模式切换
2. tab3复用tab1的绘图控制和tab2的积木可视化
3. 实现基于模式的事件记录和积木控制逻辑
4. 新增UDP发送功能,实时发送四个阶段的加权归一化值和误差范围
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

# print("2. 导入PyQt5模块完成")

# 导入数据采集层模块
from serial_thread import SerialThread
from bluetooth_receiver import BluetoothReceiver

# 导入数据处理层模块
from data_manager import DataManager

# 导入界面控制层模块
from control_panel import ControlPanel
try:
    from plot_widget import SensorPlotWidget
    # print("成功导入 SensorPlotWidget")
except ImportError as e:
    # print(f"导入 SensorPlotWidget 失败: {e}")
    # print(f"当前 Python 路径: {sys.path}")
    raise

# 导入功能模块层模块
from block_visualization.blocks_tab_manager import BlocksTabManager
from block_visualization.patient_blocks_tab import PatientBlocksTab

# 导入事件记录器
from event_recorder import EventRecorder
from event_logger import EventLogger

from block_visualization.sensor_selector import SensorSelector
from block_visualization.spine_type_selector import SpineTypeSelector
from fliter_processing.butterworth_filter import MultiSensorButterworthFilter
from fliter_processing.kalman_filter import MultiSensorKalmanFilter
from fliter_processing.savitzky_golay_filter import MultiSensorSavitzkyGolayFilter


# 如果没有jsonencoder模块，创建一个简单的编码器
import json
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float32, np.float64, np.int32, np.int64)):
            return float(obj)
        return super().default(obj)

# print("3. 导入所有自定义模块完成")


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
        self.control_panel = None  # 初始化为None
        
        # 存储从事件文件加载的阶段配置
        self.stage_configs = {
            'gray_rotation': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1},
            'blue_curvature': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1},
            'gray_tilt': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1},
            'green_tilt': {'original_values': [], 'target_values': [], 'weights': [], 'error_range': 0.1}
        }
        
        self.events_file_loaded = False
        
        # 脊柱类型配置（默认C型）
        self.spine_type = "C"
        self.spine_direction = "left"
        
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
            
            # 计算6个归一化训练指标
            training_indicators = self._calculate_training_indicators(sensor_data)
            
            # 计算spine_curve字段（根据脊柱类型自动切换计算方式）
            spine_curve = self._calculate_spine_curve(stage_values)
            
            # 准备数据包
            data_package = {
                "timestamp": current_time,
                "sensor_data": sensor_data,
                "stage_values": stage_values,
                "stage_error_ranges": stage_error_ranges,
                "training_indicators": training_indicators,  # 新增6个归一化参数
                "spine_curve": spine_curve,  # 新增spine_curve字段
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
            if self.control_panel is None:
                print("警告: control_panel未设置，使用默认值0.5")
                return 0.5
            return self._calculate_simple_weighted_value(sensor_data, config.get('weights', []))
        
        original_values = config.get('original_values', [])
        target_values = config.get('target_values', [])
        weights = config.get('weights', [])
        
        if not original_values or not target_values or not weights:
            # 从控制面板获取当前参数
            try:
                controllers = {
                    'gray_rotation': self.control_panel.gray_rotation,
                    'blue_curvature': self.control_panel.blue_curvature,
                    'gray_tilt': self.control_panel.gray_tilt,
                    'green_tilt': self.control_panel.green_tilt
                }
                
                # 根据stage_name找到对应的控制器
                for stage_name, controller in controllers.items():
                    if stage_name in str(config):  # 简单的匹配检查
                        # 获取控制器的参数
                        weights = []
                        original_values = []
                        target_values = []
                        
                        for i in range(len(sensor_data)):
                            if i < len(controller.sensor_checkboxes):
                                if controller.sensor_checkboxes[i].isChecked():
                                    if i < len(controller.weight_spinboxes):
                                        weights.append(controller.weight_spinboxes[i].value())
                                        # 获取原始值和目标值
                                        if hasattr(controller, f'sensor{i+1}_original') and hasattr(controller, f'sensor{i+1}_target'):
                                            original_values.append(getattr(controller, f'sensor{i+1}_original').value())
                                            target_values.append(getattr(controller, f'sensor{i+1}_target').value())
                                        else:
                                            original_values.append(2500)
                                            target_values.append(2500)
                                    else:
                                        weights.append(0.0)
                                        original_values.append(2500)
                                        target_values.append(2500)
                            else:
                                weights.append(0.0)
                                original_values.append(2500)
                                target_values.append(2500)
                        break
            except Exception as e:
                print(f"获取控制面板参数失败: {e}")
                return 0.5
        
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
        try:
            # 从控制面板获取当前参数
            controllers = {
                'gray_rotation': self.control_panel.gray_rotation,
                'blue_curvature': self.control_panel.blue_curvature,
                'gray_tilt': self.control_panel.gray_tilt,
                'green_tilt': self.control_panel.green_tilt
            }
            
            # 使用第一个有效的控制器参数
            for controller in controllers.values():
                if hasattr(controller, 'sensor_checkboxes') and hasattr(controller, 'weight_spinboxes'):
                    weights = []
                    original_values = []
                    target_values = []
                    
                    for i in range(len(sensor_data)):
                        if i < len(controller.sensor_checkboxes):
                            if controller.sensor_checkboxes[i].isChecked():
                                if i < len(controller.weight_spinboxes):
                                    weights.append(controller.weight_spinboxes[i].value())
                                    # 获取原始值和目标值
                                    if hasattr(controller, f'sensor{i+1}_original') and hasattr(controller, f'sensor{i+1}_target'):
                                        original_values.append(getattr(controller, f'sensor{i+1}_original').value())
                                        target_values.append(getattr(controller, f'sensor{i+1}_target').value())
                                    else:
                                        original_values.append(2500)
                                        target_values.append(2500)
                                else:
                                    weights.append(0.0)
                                    original_values.append(2500)
                                    target_values.append(2500)
                        else:
                            weights.append(0.0)
                            original_values.append(2500)
                            target_values.append(2500)
                    break
            
            # 使用获取到的参数计算归一化值
            total_weight = 0
            weighted_sum = 0
            
            for i, sensor_val in enumerate(sensor_data):
                if i < len(weights) and weights[i] != 0:
                    weight = abs(weights[i])
                    original_val = original_values[i]
                    target_val = target_values[i]
                    
                    # 使用与主计算相同的归一化逻辑
                    if abs(original_val - target_val) > 1e-6:
                        normalized = (sensor_val - target_val) / (original_val - target_val)
                        normalized = max(0.0, min(1.0, normalized))
                    else:
                        normalized = 0.5
                    
                    weighted_sum += normalized * weight
                    total_weight += weight
            
            return weighted_sum / total_weight if total_weight > 0 else 0.5
            
        except Exception as e:
            print(f"简化加权计算失败: {e}")
            # 如果出错，使用默认的简化计算
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
    
    def _calculate_training_indicators(self, sensor_data):
        """计算6个归一化训练指标"""
        try:
            # 确保传感器数据有效
            if not sensor_data or len(sensor_data) < 7:
                return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            
            # 获取传感器数据（假设前7个传感器）
            sensors = sensor_data[:7]
            
            # 1. 骨盆前后翻转 (基于传感器1和2的差值)
            pelvis_forward_backward = abs(sensors[0] - sensors[1]) / 100.0
            pelvis_forward_backward = min(max(pelvis_forward_backward, 0.0), 1.0)
            
            # 2. 脊柱曲率矫正 (基于中间传感器的曲率)
            if len(sensors) >= 5:
                spine_curvature = abs(sensors[2] - (sensors[1] + sensors[3]) / 2) / 50.0
            else:
                spine_curvature = 0.0
            spine_curvature = min(max(spine_curvature, 0.0), 1.0)
            
            # 3. 骨盆左右倾斜 (基于传感器0和6的差值)
            pelvis_left_right = abs(sensors[0] - sensors[6]) / 80.0
            pelvis_left_right = min(max(pelvis_left_right, 0.0), 1.0)
            
            # 4. 肩部左右倾斜 (基于传感器4和5的差值)
            if len(sensors) >= 6:
                shoulder_left_right = abs(sensors[4] - sensors[5]) / 60.0
            else:
                shoulder_left_right = 0.0
            shoulder_left_right = min(max(shoulder_left_right, 0.0), 1.0)
            
            # 5. 沉肩 (基于肩部传感器的平均值)
            if len(sensors) >= 6:
                shoulder_drop = (sensors[4] + sensors[5]) / 200.0
            else:
                shoulder_drop = 0.0
            shoulder_drop = min(max(shoulder_drop, 0.0), 1.0)
            
            # 6. 沉髋 (基于髋部传感器的平均值)
            hip_drop = (sensors[0] + sensors[6]) / 200.0
            hip_drop = min(max(hip_drop, 0.0), 1.0)
            
            return [
                pelvis_forward_backward,
                spine_curvature,
                pelvis_left_right,
                shoulder_left_right,
                shoulder_drop,
                hip_drop
            ]
            
        except Exception as e:
            print(f"计算训练指标失败: {e}")
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    def _calculate_spine_curve(self, stage_values):
        """根据脊柱类型计算spine_curve字段
        
        对于C型：由单一 blue_curvature 计算的归一化值
        对于S型：由上下两段 blue_curvature_up / blue_curvature_down 先各算归一化，再取 max(norm_up, norm_dn)
        """
        try:
            if self.spine_type == "C":
                # C型脊柱：使用单一blue_curvature的归一化值
                blue_curvature = stage_values.get('blue_curvature', 0.5)
                return blue_curvature
            
            elif self.spine_type == "S":
                # S型脊柱：使用上下两段blue_curvature分别归一化后取最大值
                blue_curvature_up = stage_values.get('blue_curvature_up', 0.5)
                blue_curvature_down = stage_values.get('blue_curvature_down', 0.5)
                
                # 取两个归一化值的最大值
                spine_curve = max(blue_curvature_up, blue_curvature_down)
                return spine_curve
            
            else:
                # 未知脊柱类型，返回默认值
                return 0.5
                
        except Exception as e:
            print(f"计算spine_curve时出错: {e}")
            return 0.5
    
    def set_spine_type(self, spine_type):
        """设置脊柱类型"""
        self.spine_type = spine_type
        print(f"SpineDataSender: 脊柱类型设置为 {spine_type}")
    
    def set_spine_direction(self, spine_direction):
        """设置脊柱方向"""
        self.spine_direction = spine_direction
        print(f"SpineDataSender: 脊柱方向设置为 {spine_direction}")
    
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

    def set_control_panel(self, control_panel):
        """设置control_panel引用"""
        self.control_panel = control_panel
        print("UDP发送器已设置control_panel引用")


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
        
        # ====== 事件记录器 ======
        self.event_recorder = EventRecorder()
        # ====== 操作日志记录器 ======
        self.event_logger = EventLogger()
        print("7. 事件记录器创建完成")
        
        # ====== 界面控制组件 ======
        self.control_panel = ControlPanel()
        
        # 创建三个独立的绘图组件用于三个tab
        self.plot_widget_tab1 = SensorPlotWidget()  # tab1专用
        self.plot_widget_tab2 = SensorPlotWidget()  # tab2专用 
        self.plot_widget_tab3 = SensorPlotWidget()  # tab3专用
        print("8. 界面控制组件创建完成")
        
        # ====== 设置初始传感器数量 ======
        initial_sensor_count = self.control_panel.get_num_sensors()
        self.event_recorder.set_num_sensors(initial_sensor_count)
        print(f"9. 初始传感器数量设置为: {initial_sensor_count}")
        
        # ====== 数据处理器 ======
        # 创建三种滤波器
        self.butterworth_filter = MultiSensorButterworthFilter(
            num_sensors=initial_sensor_count,
            cutoff_freq=2.0,
            fs=100.0,
            order=4,
            btype='low'
        )
        
        self.kalman_filter = MultiSensorKalmanFilter(
            num_sensors=initial_sensor_count,
            process_noise=0.01,
            measurement_noise=0.1
        )
        
        self.sg_filter = MultiSensorSavitzkyGolayFilter(
            num_sensors=initial_sensor_count,
            window_length=11,
            polyorder=3
        )
        
        print("10. 数据处理器初始化完成")
        
        # ====== 模式设置 ======
        self.current_mode = "doctor"  # 默认为医生端模式
        print("11. 当前模式设置为: 医生端")
        
        # ====== 应用状态管理 ======
        self.app_state = {
            "mode": "serial",  # 或 "bluetooth"
            "acquisition_active": False,
            "current_sensor_data": None,
            "filter_enabled": False,
            "filter_type": "butterworth",
            "filter_params": {
                "butterworth": {"cutoff_freq": 10.0, "order": 4},
                "kalman": {"process_noise": 0.01, "measurement_noise": 0.1},
                "savitzky_golay": {"window_length": 5, "polyorder": 2}
            },
            "udp_enabled": False,
            "udp_host": "127.0.0.1",
            "udp_port": 6667,
            "scoliosis": {
                "type": "C",  # C型或S型
                "dir": "L",   # L(左凸)或R(右凸)
                "stages": {
                    "C": {
                        "max_stages": 4,
                        "stage_descriptions": {
                            1: "阶段1：骨盆前后翻转",
                            2: "阶段2：脊柱曲率矫正-单段",
                            3: "阶段3：骨盆左右倾斜",
                            4: "阶段4：肩部左右倾斜"
                        }
                    },
                    "S": {
                        "max_stages": 5,
                        "stage_descriptions": {
                            1: "阶段1：骨盆前后翻转",
                            2: "阶段2-A：上胸段曲率矫正",
                            3: "阶段2-B：腰段曲率矫正",
                            4: "阶段3：骨盆左右倾斜",
                            5: "阶段4：肩部左右倾斜"
                        }
                    }
                }
            }
        }
        print("11.5. 应用状态管理初始化完成")
        
        # ====== 数据采集组件 ======
        self.serial_thread = None
        self.bluetooth_receiver = None

        # ====== 功能模块组件 ======
        self.blocks_manager = BlocksTabManager()
        blocks_tab = self.blocks_manager.get_tab_widget()
        if hasattr(blocks_tab, 'event_recorder'):
            blocks_tab.event_recorder.set_num_sensors(initial_sensor_count)
        
        # 设置父窗口引用，用于获取当前模式
        self.blocks_manager.set_parent_window(self)
        print("12. 积木可视化管理器创建完成")
        
        # ====== 患者积木可视化标签页 ======
        try:
            self.patient_blocks_tab = PatientBlocksTab(sensor_count=initial_sensor_count)
            print("13. 患者积木可视化标签页创建完成")
        except Exception as e:
            print(f"创建患者积木可视化标签页时发生错误: {e}")
            self.patient_blocks_tab = None
            
        # ====== UDP发送器 ======
        self.spine_data_sender = SpineDataSender(
            host='127.0.0.1', 
            port=6667, 
            enable=False  # 默认禁用，可通过设置启用
        )
        # 设置control_panel引用
        self.spine_data_sender.set_control_panel(self.control_panel)
        print("14. UDP发送器初始化完成")
        
        # 设置UI
        # print("15. 开始初始化UI...")
        self._init_ui()
        # print("16. UI初始化完成")
        
        # 连接信号与槽
        # print("17. 开始连接信号与槽...")
        self._connect_signals()
        # print("18. 信号与槽连接完成")
        
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
        # print("17. 开始创建UI布局...")

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
        self.tab_widget.addTab(blocks_tab, "医生端（校准）")

        # tab3: 患者积木可视化标签页
        if self.patient_blocks_tab is not None:
            patient_tab = self._create_patient_tab_with_plot()
            self.tab_widget.addTab(patient_tab, "患者端（训练）")

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
        splitter.setSizes([300, 700])  # 恢复原始宽度
        
        monitor_layout.addWidget(splitter)
        
        # 信号同步：从control_panel.spine_type_selector发射
        self.control_panel.spine_type_selector.spine_type_changed.connect(self._sync_spine_type_to_tabs)
        self.control_panel.spine_type_selector.spine_direction_changed.connect(self._sync_spine_direction_to_tabs)
        
        return monitor_widget

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
        
        # 新增：脊柱类型和方向变更信号
        self.control_panel.spine_type_changed.connect(self.on_spine_type_changed)
        self.control_panel.spine_direction_changed.connect(self.on_spine_direction_changed)
        
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
        self.control_panel.sensor_count_changed.connect(self.update_butterworth_filter_sensor_count)
        self.control_panel.sensor_count_changed.connect(self.update_kalman_filter_sensor_count)
        self.control_panel.sensor_count_changed.connect(self.update_sg_filter_sensor_count)
        


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
        enabled = filter_params['enabled']
        method = filter_params['method']
        params = filter_params['params']
        print(f"滤波参数变更: 启用={enabled}, 方法={method}, 参数={params}")
    
    def _sync_spine_type_to_tabs(self, spine_type):
        """同步脊柱类型到所有标签页"""
        print(f"MainWindow: 同步脊柱类型到所有标签页: {spine_type}")
        self.app_state["scoliosis"]["type"] = spine_type
        
        # 更新UDP发送器的脊柱类型
        if hasattr(self, 'spine_data_sender') and self.spine_data_sender:
            self.spine_data_sender.set_spine_type(spine_type)
            print(f"UDP发送器脊柱类型已更新: {spine_type}")
        
        # 同步到第二个tab（blocks_manager）
        if hasattr(self, 'blocks_manager'):
            blocks_tab = self.blocks_manager.get_tab_widget()
            if hasattr(blocks_tab, 'spine_type_selector'):
                blocks_tab.spine_type_selector.set_spine_type(spine_type)
            if hasattr(blocks_tab, 'update_spine_type'):
                blocks_tab.update_spine_type(spine_type)
        
        # 同步到第三个tab（patient_blocks_tab）
        if hasattr(self, 'patient_blocks_tab') and self.patient_blocks_tab:
            if hasattr(self.patient_blocks_tab, 'spine_type_selector'):
                self.patient_blocks_tab.spine_type_selector.set_spine_type(spine_type)
            if hasattr(self.patient_blocks_tab, 'update_spine_type'):
                self.patient_blocks_tab.update_spine_type(spine_type)
    
    def _sync_spine_direction_to_tabs(self, spine_direction):
        """同步脊柱方向到所有标签页"""
        print(f"MainWindow: 同步脊柱方向到所有标签页: {spine_direction}")
        self.app_state["scoliosis"]["dir"] = spine_direction
        
        # 更新UDP发送器的脊柱方向
        if hasattr(self, 'spine_data_sender') and self.spine_data_sender:
            self.spine_data_sender.set_spine_direction(spine_direction)
            print(f"UDP发送器脊柱方向已更新: {spine_direction}")
        
        # 同步到第二个tab（blocks_manager）
        if hasattr(self, 'blocks_manager'):
            blocks_tab = self.blocks_manager.get_tab_widget()
            if hasattr(blocks_tab, 'spine_type_selector'):
                blocks_tab.spine_type_selector.set_spine_direction(spine_direction)
            if hasattr(blocks_tab, 'update_spine_direction'):
                blocks_tab.update_spine_direction(spine_direction)
        
        # 同步到第三个tab（patient_blocks_tab）
        if hasattr(self, 'patient_blocks_tab') and self.patient_blocks_tab:
            if hasattr(self.patient_blocks_tab, 'spine_type_selector'):
                self.patient_blocks_tab.spine_type_selector.set_spine_direction(spine_direction)
            if hasattr(self.patient_blocks_tab, 'update_spine_direction'):
                self.patient_blocks_tab.update_spine_direction(spine_direction)

    def on_spine_type_changed(self, spine_type):
        """处理脊柱类型变更"""
        print(f"MainWindow: 脊柱类型已更新: {spine_type}")
        self.app_state["scoliosis"]["type"] = spine_type
        
        # 更新UDP发送器的脊柱类型
        if hasattr(self, 'spine_data_sender') and self.spine_data_sender:
            self.spine_data_sender.set_spine_type(spine_type)
            print(f"UDP发送器脊柱类型已更新: {spine_type}")
        
        # 通知相关组件更新
        if hasattr(self, 'blocks_manager'):
            blocks_tab = self.blocks_manager.get_tab_widget()
            if hasattr(blocks_tab, 'update_spine_type'):
                blocks_tab.update_spine_type(spine_type)
        
        if hasattr(self, 'patient_blocks_tab') and self.patient_blocks_tab:
            if hasattr(self.patient_blocks_tab, 'update_spine_type'):
                self.patient_blocks_tab.update_spine_type(spine_type)
    
    def on_spine_direction_changed(self, spine_direction):
        """处理脊柱方向变更"""
        print(f"MainWindow: 脊柱方向已更新: {spine_direction}")
        # 转换方向格式
        direction_map = {
            "left": "L",
            "right": "R",
            "lumbar_left": "L",
            "lumbar_right": "R"
        }
        self.app_state["scoliosis"]["dir"] = direction_map.get(spine_direction, "L")
        
        # 通知相关组件更新
        if hasattr(self, 'blocks_manager'):
            blocks_tab = self.blocks_manager.get_tab_widget()
            if hasattr(blocks_tab, 'update_spine_direction'):
                blocks_tab.update_spine_direction(spine_direction)
        
        if hasattr(self, 'patient_blocks_tab') and self.patient_blocks_tab:
            if hasattr(self.patient_blocks_tab, 'update_spine_direction'):
                self.patient_blocks_tab.update_spine_direction(spine_direction)
        if method == 'butterworth' and enabled:
            self.butterworth_filter.update_filter_parameters(
                cutoff_freq=params['cutoff_freq'],
                fs=params['fs'],
                order=params['order'],
                btype=params['btype']
            )
        elif method == 'kalman' and enabled:
            params = filter_params['params']
            self.kalman_filter.update_filter_parameters(
                process_noise=params['process_noise'],
                measurement_noise=params['measurement_noise']
            )
            print(f"卡尔曼滤波参数已更新: 过程噪声={params['process_noise']:.3f}, "
                  f"测量噪声={params['measurement_noise']:.3f}")
        elif method == 'savitzky_golay' and enabled:
            self.sg_filter.update_filter_parameters(
                window_length=params['window_length'],
                polyorder=params['polyorder']
            )
        else:
            print("未知的滤波方法")




    # 【新增方法】连接阶段控制信号
    def _connect_stage_control_signals(self):
        """连接阶段控制模块的按钮信号"""
        try:
            blocks_tab = self.blocks_manager.get_tab_widget()
            
            # 方法1：如果blocks_tab有具体的按钮属性
            button_mappings = [
                # (按钮属性名, 事件名称, 阶段键)
                ('start_training_btn', '开始训练', 1),
                ('complete_stage_btn', '完成阶段', 1),
                ('start_correction_btn', '开始矫正', 2),
                ('complete_correction_btn', '矫正完成', 2),
                ('start_hip_btn', '开始沉髋', '3a'),
                ('end_hip_btn', '沉髋结束', '3a'),
                ('start_shoulder_btn', '开始沉肩', '3b'),
                ('end_shoulder_btn', '沉肩结束', '3b'),
            ]
            
            connected_count = 0
            for btn_attr, event_name, stage_key in button_mappings:
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
                for btn_attr, event_name, stage_key in button_mappings:
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
    
    def on_stage_button_clicked(self, event_name, stage_key):
        """处理阶段按钮点击事件"""
        try:
            print(f"\n=== 阶段按钮被点击 ===")
            print(f"事件名称: {event_name}")
            print(f"阶段键: {stage_key}")
            
            # 强制刷新当前传感器数据，确保获取最新值
            if hasattr(self, 'plot_widget_tab1') and self.plot_widget_tab1:
                self.plot_widget_tab1.update()  # 强制更新图表
            
            # 获取当前传感器数据（确保是最新的）
            current_sensor_data = self.event_recorder.get_current_sensor_data()
            if not current_sensor_data:
                print("警告: 当前没有传感器数据")
                return
            
            print(f"当前传感器数据: {current_sensor_data[:8]}...")
            
            # 检查阶段映射
            if stage_key not in self.stage_sensor_mapping:
                print(f"未找到阶段 {stage_key} 的映射配置")
                return
            
            stage_mapping = self.stage_sensor_mapping[stage_key]
            
            # 确定是原始值还是最佳值
            if event_name == stage_mapping['original_event']:
                action_type = 'original'
            elif event_name == stage_mapping['target_event']:
                action_type = 'target'
            else:
                print(f"事件 '{event_name}' 不匹配阶段 {stage_key} 的预期事件")
                return
            
            print(f"动作类型: {action_type}")
            print(f"目标阶段: {stage_mapping['name']}")
            
            # 获取传感器选择器
            sensor_selector = self._get_sensor_selector_for_stage(stage_key)
            
            # 记录事件
            if action_type == 'target':
                self._record_stage_event_with_weights(event_name, stage_key, current_sensor_data, sensor_selector)
            else:
                self._record_stage_event(event_name, stage_key, current_sensor_data, sensor_selector)
            
            # 显示事件记录摘要
            latest_event = self.event_recorder.get_latest_event()
            if latest_event:
                print("\n=== 最新事件记录 ===")
                time_info = latest_event.get('time_info', {})
                print(f"记录时间: {time_info.get('absolute_time', 'N/A')}")
                print(f"训练时长: {time_info.get('elapsed_minutes', 0):.2f}分钟")
                print(f"事件ID: {latest_event.get('event_id', 'N/A')}")
                
                # 显示事件统计摘要
                print("\n=== 训练进度摘要 ===")
                print(self.event_recorder.get_event_summary())
                print("==================\n")
            
            # 更新tab2的传感器参数设置
            success = self.update_tab2_sensor_parameters(stage_key, stage_mapping, action_type, current_sensor_data)
            
            if success:
                print("✓ 传感器参数更新成功")
            else:
                print("✗ 传感器参数更新失败")
            
            print("=== 处理完成 ===\n")
            
        except Exception as e:
            print(f"处理阶段按钮点击事件时出错: {e}")
            import traceback
            traceback.print_exc()

    def _record_simple_event(self, event_name, stage_key, sensor_data):
        """记录简单事件（不包含权重信息）"""
        try:
            # 记录事件（不包含权重）
            self.event_recorder.record_event(
                event_name=event_name,
                stage=f"阶段{stage_key}",
                additional_data={}  # 空的额外数据
            )
            
            print(f"简单事件已记录: {event_name}")
            
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

    def _get_sensor_selector_for_stage(self, stage_key):
        """获取指定阶段的传感器选择器"""
        try:
            # 获取积木可视化标签页
            blocks_tab = self.blocks_manager.get_tab_widget()
            
            # 根据阶段键获取对应的传感器选择器
            stage_selector_mapping = {
                1: 'gray_rotation',          # 阶段1: 骨盆前后翻转
                2: 'blue_curvature',         # 阶段2: 脊柱曲率矫正
                '3a': 'gray_tilt',          # 阶段3a: 骨盆左右倾斜
                '3b': 'green_tilt'          # 阶段3b: 肩部左右倾斜
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
            if hasattr(self, 'control_panel') and hasattr(self.control_panel, selector_name):
                return getattr(self.control_panel, selector_name)
            
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
        print(f"\n=== 模式切换 ===")
        print(f"从 {self.current_mode} 切换到 {mode}")
        # 记录模式切换
        self.event_logger.log_mode_change(self.current_mode, mode)
        self.current_mode = mode
        
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
    
    def load_patient_mapping_data(self):
        """加载患者端数据映射所需的原始值和目标值（修正版）"""
        events_save_path = self.control_panel.get_events_save_path()
        if not events_save_path or not os.path.exists(events_save_path):
            print("事件文件不存在，无法加载映射数据")
            return False
            
        try:
            import csv
            
            print(f"\n=== 开始加载映射数据 ===")
            print(f"事件文件路径: {events_save_path}")
            print(f"文件大小: {os.path.getsize(events_save_path)} 字节")
            
            # 修正：使用正确的事件名称映射
            event_mapping = {
                '开始训练': {'stage': 1, 'type': 'original'},
                '完成阶段': {'stage': 1, 'type': 'target'},
                '开始矫正': {'stage': 2, 'type': 'original'},
                '矫正完成': {'stage': 2, 'type': 'target'},
                '开始沉髋': {'stage': 3, 'type': 'original'},
                '沉髋完成': {'stage': 3, 'type': 'target'},
                '开始沉肩': {'stage': 3, 'type': 'original'},
                '沉肩完成': {'stage': 3, 'type': 'target'}
            }
            
            print(f"预期的事件名称: {list(event_mapping.keys())}")
            
            # 初始化数据结构
            self.patient_mode_mapping_data['original_values'] = {}
            self.patient_mode_mapping_data['target_values'] = {}
            
            # 先读取文件内容进行调试
            print("\n--- 文件内容预览 ---")
            with open(events_save_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:10]):  # 只显示前10行
                    print(f"行{i+1}: {line.strip()}")
                if len(lines) > 10:
                    print(f"... 总共{len(lines)}行")
            
            # 重新打开文件进行解析
            found_events = []
            with open(events_save_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # 找到第一个非注释行、非空行（即表头行）
                header_line_index = -1
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        header_line_index = i
                        print(f"找到表头行在第{i+1}行: {line}")
                        break
                
                if header_line_index == -1:
                    print("错误: 找不到表头行")
                    return False
                
                # 从表头行开始重新创建CSV内容
                csv_content = '\n'.join(lines[header_line_index:])
                
                # 使用StringIO创建CSV reader
                from io import StringIO
                csv_file = StringIO(csv_content)
                reader = csv.DictReader(csv_file)
                
                # 打印CSV标题
                if reader.fieldnames:
                    print(f"\nCSV标题行: {reader.fieldnames}")
                else:
                    print("警告: 无法读取CSV标题行")
                    return False
                
                row_count = 0
                actual_data_row = 0
                for row in reader:
                    row_count += 1
                    
                    # 检查是否为空行（所有字段都为空）
                    if all(not str(value).strip() for value in row.values()):
                        print(f"跳过空行 {row_count}")
                        continue
                    
                    actual_data_row += 1
                    print(f"\n处理数据行{actual_data_row} (文件行{header_line_index + 1 + row_count})")
                    
                    event_name = row.get('event_name', '').strip()
                    stage = row.get('stage', '').strip()
                    
                    print(f"\n行{row_count}: event_name='{event_name}', stage='{stage}'")
                    
                    # 记录所有找到的事件
                    if event_name:
                        found_events.append(event_name)
                    
                    if event_name in event_mapping:
                        mapping_info = event_mapping[event_name]
                        target_stage = mapping_info['stage']
                        data_type = mapping_info['type']
                        
                        print(f"  匹配成功! 目标阶段: {target_stage}, 数据类型: {data_type}")
                        
                        # 提取传感器数据
                        sensor_data = []
                        num_sensors = self.control_panel.get_num_sensors()
                        print(f"  提取{num_sensors}个传感器的数据...")
                        
                        for i in range(1, num_sensors + 1):
                            sensor_key = f'sensor{i}'
                            if sensor_key in row and row[sensor_key]:
                                try:
                                    value = float(row[sensor_key])
                                    sensor_data.append(value)
                                    if i <= 3:  # 只显示前3个传感器的值
                                        print(f"    {sensor_key}: {value}")
                                except ValueError as e:
                                    print(f"    {sensor_key}: 转换失败 ({row[sensor_key]}) - 使用默认值2500")
                                    sensor_data.append(2500.0)
                            else:
                                print(f"    {sensor_key}: 不存在 - 使用默认值2500")
                                sensor_data.append(2500.0)
                        
                        # 存储数据
                        if data_type == 'original':
                            if target_stage not in self.patient_mode_mapping_data['original_values']:
                                self.patient_mode_mapping_data['original_values'][target_stage] = sensor_data
                                print(f"  存储原始值到阶段{target_stage}: {sensor_data[:3]}...")
                            else:
                                print(f"  阶段{target_stage}的原始值已存在，跳过")
                        else:  # target
                            if target_stage not in self.patient_mode_mapping_data['target_values']:
                                self.patient_mode_mapping_data['target_values'][target_stage] = sensor_data
                                print(f"  存储目标值到阶段{target_stage}: {sensor_data[:3]}...")
                            else:
                                print(f"  阶段{target_stage}的目标值已存在，跳过")
                    else:
                        if event_name:
                            print(f"  未匹配的事件名称: '{event_name}'")
            
            print(f"\n--- 解析结果 ---")
            print(f"总共处理了{row_count}行数据")
            print(f"找到的所有事件名称: {list(set(found_events))}")
            print(f"成功加载的阶段数据:")
            print(f"  原始值阶段: {list(self.patient_mode_mapping_data['original_values'].keys())}")
            print(f"  目标值阶段: {list(self.patient_mode_mapping_data['target_values'].keys())}")
            
            # 检查数据完整性
            success = False
            for stage in [1, 2, 3]:
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
                print("\n✓ 映射数据加载成功")
                
                # 设置数据管理器的映射数据
                if hasattr(self.data_manager, 'set_patient_mapping_data'):
                    self.data_manager.set_patient_mapping_data(self.patient_mode_mapping_data)
                    print("✓ 已设置数据管理器的映射数据")
                
                return True
            else:
                print("\n✗ 映射数据加载失败: 没有找到完整的阶段数据")
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
            # 获取设置
            source_type = self.control_panel.get_source_type()
            baud_rate = self.control_panel.get_baud_rate()
            num_sensors = self.control_panel.get_num_sensors()
            duration = self.control_panel.get_duration()
            
            # 记录采集开始
            self.event_logger.log_acquisition_start(source_type, {
                'port': port,
                'baud_rate': baud_rate,
                'num_sensors': num_sensors,
                'duration': duration,
                'mode': current_mode
            })
            
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
                params = filter_params['params']
                if filter_params['method'] == 'kalman':
                    self.kalman_filter.update_filter_parameters(
                        process_noise=params['process_noise'],
                        measurement_noise=params['measurement_noise']
                    )
                    print(f"卡尔曼滤波参数已更新: 过程噪声={params['process_noise']:.3f}, "
                          f"测量噪声={params['measurement_noise']:.3f}")
                elif filter_params['method'] == 'butterworth':
                    self.butterworth_filter.update_filter_parameters(
                        cutoff_freq=params['cutoff_freq'],
                        fs=params['fs'],
                        order=params['order'],
                        btype=params['btype']
                    )
                    print(f"巴特沃斯滤波参数已更新: 截止频率={params['cutoff_freq']}, 采样率={params['fs']}, 阶数={params['order']}, 类型={params['btype']}")
                elif filter_params['method'] == 'savitzky_golay':
                    self.sg_filter.update_filter_parameters(
                        window_length=params['window_length'],
                        polyorder=params['polyorder']
                    )
                    print(f"Savitzky-Golay滤波参数已更新: 窗口长度={params['window_length']}, 多项式阶数={params['polyorder']}")
                else:
                    print("未知的滤波方法")
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
            
            # 记录采集结束
            self.event_logger.log_acquisition_stop({
                'display_data_count': stats.get('display_data_count', 0),
                'total_data_count': stats.get('total_data_count', 0),
                'raw_data_count': stats.get('raw_data_count', 0),
                'events_count': events_count
            })
            
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
        """处理接收到的传感器数据（集成滤波器和数据增强）"""
        try:
            self.data_count += 1
            filter_params = self.control_panel.get_filter_params()
            enhancement_params = self.control_panel.get_enhancement_params()
            
            # 第一步：滤波处理
            filter_enabled = filter_params['enabled']
            filter_method = filter_params['method']
            filter_params_dict = filter_params['params']
            
            if filter_enabled:
                if filter_method == 'butterworth':
                    filtered_data, raw_data = self.butterworth_filter.filter_data_with_timestamp(data)
                elif filter_method == 'kalman':
                    filtered_data, raw_data = self.kalman_filter.filter_data_with_timestamp(data)
                elif filter_method == 'savitzky_golay':
                    filtered_data, raw_data = self.sg_filter.filter_data_with_timestamp(data)
                else:
                    filtered_data = data
                    raw_data = data
            else:
                filtered_data = data
                raw_data = data
                
            # 保存原始数据
            raw_data_with_flag = raw_data.copy()
            raw_data_with_flag.insert(0, "RAW")
            self.data_manager.add_raw_data_point(raw_data_with_flag)
            
            # 直接使用滤波后的数据
            processed_data = filtered_data
                
            # 保存处理后的数据
            self.data_manager.add_data_point(processed_data)
            # 新增：保存一份带PROCESSED标记的数据到processed缓存
            processed_data_with_flag = processed_data.copy()
            processed_data_with_flag.insert(0, "PROCESSED")
            self.data_manager.add_processed_data_point(processed_data_with_flag)
            
            # 更新事件记录器的数据（同时保存原始数据和处理后数据）
            self.event_recorder.set_current_sensor_data(raw_data[1:] if len(raw_data) > 1 else raw_data, 
                                                        processed_data[1:] if len(processed_data) > 1 else processed_data)
            
            # 更新显示
            display_data = self.data_manager.get_display_data()
            if display_data:
                current_mode = self.control_panel.get_current_mode()
                if current_mode == "doctor":
                    self.plot_widget_tab1.update_plot(display_data)
                    self.plot_widget_tab2.update_plot(display_data)
                    self.blocks_manager.process_sensor_data(processed_data)
                elif current_mode == "patient":
                    self.plot_widget_tab1.update_plot(display_data)
                    self.plot_widget_tab3.update_plot(display_data)
                    if self.patient_blocks_tab:
                        self.patient_blocks_tab.update_sensor_data(processed_data)
                        
            # UDP发送
            if self.spine_data_sender.enable and len(processed_data) > 1:
                sensor_data = processed_data[1:]
                # 获取患者端的归一化值
                if current_mode == "patient" and self.patient_blocks_tab:
                    # 获取患者端的可视化参数
                    visualizer_params = self.patient_blocks_tab.visualizer_params
                    # 发送数据包
                    data_package = {
                        "timestamp": time.time(),
                        "sensor_data": sensor_data,
                        "stage_values": {
                            "gray_rotation": visualizer_params['gray_rotation'],
                            "blue_curvature": visualizer_params['blue_curvature'],
                            "gray_tilt": visualizer_params['gray_tilt'],
                            "green_tilt": visualizer_params['green_tilt']
                        },
                        "stage_error_ranges": {
                            "gray_rotation": 0.1,
                            "blue_curvature": 0.1,
                            "gray_tilt": 0.1,
                            "green_tilt": 0.1
                        },
                        "sensor_count": len(sensor_data),
                        "events_file_loaded": True
                    }
                    # 转换为JSON并发送
                    json_data = json.dumps(data_package, cls=NumpyEncoder)
                    if self.spine_data_sender.socket:
                        self.spine_data_sender.socket.sendto(json_data.encode(), (self.spine_data_sender.host, self.spine_data_sender.port))
                        self.spine_data_sender.sent_count += 1
                else:
                    # 医生端模式下使用原来的发送方式
                    self.spine_data_sender.send_spine_data(sensor_data)

            # 新增：每秒只打印一次所有阶段的归一化/驱动参数
            now = time.time()
            if not hasattr(self, '_last_stage_print_time'):
                self._last_stage_print_time = 0
            if now - self._last_stage_print_time >= 1:
                all_stage_values = self.spine_data_sender._calculate_all_stage_values(processed_data[1:] if len(processed_data) > 1 else processed_data)
                print("【所有阶段归一化/驱动参数】")
                for stage, value in all_stage_values.items():
                    print(f"  阶段 {stage}: {value:.4f}")
                self._last_stage_print_time = now
            
            # 统计信息
            if self.data_count % 1000 == 0:
                stats = {}
                if filter_enabled:
                    if filter_method == 'butterworth':
                        stats['filter'] = self.butterworth_filter.get_filter_stats()
                    elif filter_method == 'kalman':
                        stats['filter'] = self.kalman_filter.get_filter_stats()
                    elif filter_method == 'savitzky_golay':
                        stats['filter'] = self.sg_filter.get_filter_stats()
                    
                print(f"处理统计: {stats}")
                
        except Exception as e:
            print(f"处理传感器数据时出错: {e}")
            import traceback
            traceback.print_exc()

    def handle_serial_error(self, error_msg):
        """处理串口错误"""
        print(f"串口错误: {error_msg}")
        self.event_logger.log_error('serial', error_msg)
        QMessageBox.warning(self, "串口错误", f"串口通信出现错误：\n{error_msg}")
        
    def handle_bluetooth_error(self, error_msg):
        """处理蓝牙错误 - 改进版"""
        print(f"蓝牙错误: {error_msg}")
        self.event_logger.log_error('bluetooth', error_msg)
        
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

    def update_butterworth_filter_sensor_count(self, new_sensor_count):
        """更新Butterworth滤波器的传感器数量"""
        self.butterworth_filter.set_num_sensors(new_sensor_count)
        print(f"Butterworth滤波器的传感器数量已更新为: {new_sensor_count}")

    def update_kalman_filter_sensor_count(self, new_sensor_count):
        """更新Kalman滤波器的传感器数量"""
        self.kalman_filter.set_num_sensors(new_sensor_count)
        print(f"Kalman滤波器的传感器数量已更新为: {new_sensor_count}")

    def update_sg_filter_sensor_count(self, new_sensor_count):
        """更新Savitzky-Golay滤波器的传感器数量"""
        self.sg_filter.set_num_sensors(new_sensor_count)
        print(f"Savitzky-Golay滤波器的传感器数量已更新为: {new_sensor_count}")



    def update_data_processors_sensor_count(self, new_sensor_count):
        """更新所有数据处理器的传感器数量"""
        try:
            # 更新滤波器
            self.butterworth_filter.set_num_sensors(new_sensor_count)
            self.kalman_filter.set_num_sensors(new_sensor_count)
            self.sg_filter.set_num_sensors(new_sensor_count)
            
            print(f"所有数据处理器的传感器数量已更新为: {new_sensor_count}")
            return True
            
        except Exception as e:
            print(f"更新数据处理器传感器数量时出错: {e}")
            return False


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