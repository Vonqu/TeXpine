
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
积木可视化模块管理器（修改版）
==============================

修改内容：
1. 添加父窗口引用传递机制
2. 支持根据模式控制事件记录功能

功能职责：
1. 统一管理积木可视化相关的所有组件
2. 提供标准化的接口供主窗口调用
3. 封装积木可视化的内部逻辑和状态管理
4. 处理积木可视化模块内部的信号传递
"""

import sys
import os
from PyQt5.QtCore import QObject, pyqtSignal

# 确保能导入积木可视化相关模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# 导入积木可视化核心组件
from block_visualization.blocks_tab import BlocksTab

class BlocksTabManager(QObject):
    """
    积木可视化模块管理器（修改版）
    =============================
    
    新增功能：
    - 支持父窗口引用传递
    - 支持根据模式控制事件记录
    """
    
    # ====== 对外信号 ======
    alert_signal = pyqtSignal(str)  # 阈值警报信号
    stage_changed = pyqtSignal(int)  # 训练阶段变更信号
    
    def __init__(self, sensor_count=6, parent=None):
        """
        初始化积木可视化管理器
        ======================
        
        Args:
            sensor_count: 传感器数量，默认6个
            parent: 父对象
        """
        super().__init__(parent)
        
        # ====== 配置参数 ======
        self.sensor_count = sensor_count
        self.parent_window = None  # 用于存储主窗口引用
        
        # ====== 创建核心组件 ======
        print("BlocksTabManager: 开始初始化积木可视化组件...")
        self._create_components()
        print("BlocksTabManager: 积木可视化组件初始化完成")
        
        # ====== 建立内部信号连接 ======
        self._connect_internal_signals()
        print("BlocksTabManager: 内部信号连接完成")
        
    def _create_components(self):
        """
        创建积木可视化相关组件
        ======================
        """
        try:
            # 创建积木可视化主标签页
            self.blocks_tab = BlocksTab(sensor_count=self.sensor_count)
            print("BlocksTabManager: BlocksTab 创建成功")
            
        except Exception as e:
            print(f"BlocksTabManager: 创建组件时发生错误: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _connect_internal_signals(self):
        """
        建立组件间的内部信号连接
        ========================
        """
        # 连接警报信号（传递给主窗口）
        if hasattr(self.blocks_tab, 'alert_signal'):
            self.blocks_tab.alert_signal.connect(self.alert_signal.emit)
            
        # 连接阶段变更信号
        training_recorder = self.get_training_recorder()
        if training_recorder and hasattr(training_recorder, 'stage_changed'):
            training_recorder.stage_changed.connect(self.stage_changed.emit)
    
    def set_parent_window(self, parent_window):
        """
        设置父窗口引用
        ==============
        
        Args:
            parent_window: 主窗口实例，用于获取当前模式等信息
        """
        self.parent_window = parent_window
        # 传递给积木标签页
        if hasattr(self.blocks_tab, 'set_parent_window'):
            self.blocks_tab.set_parent_window(parent_window)
            print("BlocksTabManager: 父窗口引用已设置")
    
    # ================================================================
    # 对外接口方法 - 供主窗口调用
    # ================================================================
    
    def get_tab_widget(self):
        """
        获取积木可视化标签页部件
        ========================
        
        Returns:
            QWidget: 积木可视化标签页部件，可直接添加到主窗口的标签容器中
        """
        return self.blocks_tab
    
    def get_training_recorder(self):
        """
        获取训练记录器实例
        ==================
        
        Returns:
            TrainingRecorder: 训练记录器实例，用于记录训练数据和事件
        """
        if hasattr(self.blocks_tab, 'training_recorder'):
            return self.blocks_tab.training_recorder
        else:
            print("警告: training_recorder 属性不存在")
            return None
    
    def process_sensor_data(self, data_values):
        """
        处理传感器数据
        ==============
        
        将从主窗口接收到的传感器数据分发给积木可视化相关组件
        
        Args:
            data_values: 传感器数据列表 [timestamp, sensor1, sensor2, ..., sensorN]
        """
        try:
            if self.blocks_tab:
                self.blocks_tab.process_sensor_data(data_values)
        except Exception as e:
            print(f"BlocksTabManager: 处理传感器数据时发生错误: {e}")
    
    def set_stage(self, stage):
        """
        设置训练阶段
        ============
        
        Args:
            stage: 训练阶段编号 (1, 2, 3)
        """
        try:
            if hasattr(self.blocks_tab, 'stage'):
                self.blocks_tab.stage = stage
                self.blocks_tab.update_stage_ui()
                
            # 同步到训练记录器
            training_recorder = self.get_training_recorder()
            if training_recorder:
                training_recorder.set_stage(stage)
                
        except Exception as e:
            print(f"BlocksTabManager: 设置训练阶段时发生错误: {e}")
    
    def get_current_stage(self):
        """
        获取当前训练阶段
        ================
        
        Returns:
            int: 当前训练阶段编号
        """
        if hasattr(self.blocks_tab, 'stage'):
            return self.blocks_tab.stage
        return 1
    
    # ================================================================
    # 积木可视化参数控制方法
    # ================================================================
    
    def get_control_panel(self):
        """
        获取积木控制面板
        ================
        
        Returns:
            BlockControlPanel: 积木控制面板实例
        """
        if hasattr(self.blocks_tab, 'control_panel'):
            return self.blocks_tab.control_panel
        return None
    
    def get_visualizer(self):
        """
        获取积木可视化器
        ================
        
        Returns:
            BlocksVisualizer: 积木可视化器实例
        """
        if hasattr(self.blocks_tab, 'visualizer'):
            return self.blocks_tab.visualizer
        return None
    
    def set_sensor_threshold(self, sensor_index, min_val, max_val):
        """
        设置传感器阈值
        ==============
        
        Args:
            sensor_index: 传感器索引
            min_val: 最小阈值
            max_val: 最大阈值
        """
        control_panel = self.get_control_panel()
        if control_panel:
            # 这里可以扩展阈值设置功能
            pass
    
    def get_visualization_state(self):
        """
        获取可视化状态信息
        ==================
        
        Returns:
            dict: 包含当前可视化状态的字典
        """
        state = {
            'current_stage': self.get_current_stage(),
            'sensor_count': self.sensor_count,
            'alert_active': False
        }
        
        # 获取可视化器状态
        visualizer = self.get_visualizer()
        if visualizer:
            state.update({
                'gray_rotation': getattr(visualizer, 'gray_block_rotation', 0),
                'gray_tilt': getattr(visualizer, 'gray_block_tilt', 0),
                'blue_curvature': getattr(visualizer, 'blue_blocks_curvature', 0),
                'green_tilt': getattr(visualizer, 'green_block_tilt', 0),
                'alerts': {
                    'gray_rotation': getattr(visualizer, 'gray_rotation_alert', False),
                    'gray_tilt': getattr(visualizer, 'gray_tilt_alert', False),
                    'blue_curvature': getattr(visualizer, 'blue_curvature_alert', False),
                    'green_tilt': getattr(visualizer, 'green_tilt_alert', False)
                }
            })
        
        return state
    
    # ================================================================
    # 训练数据管理方法
    # ================================================================
    
    def get_training_data(self):
        """
        获取训练记录数据
        ================
        
        Returns:
            dict: 训练记录数据字典
        """
        training_recorder = self.get_training_recorder()
        if training_recorder:
            return getattr(training_recorder, 'recording_data', {})
        return {}
    
    def export_training_data(self, file_path):
        """
        导出训练数据
        ============
        
        Args:
            file_path: 导出文件路径
            
        Returns:
            bool: 是否导出成功
        """
        training_recorder = self.get_training_recorder()
        if training_recorder:
            try:
                training_recorder.save_records(file_path)
                return True
            except Exception as e:
                print(f"BlocksTabManager: 导出训练数据失败: {e}")
                return False
        return False
    
    def clear_training_data(self):
        """
        清空训练记录数据
        ================
        """
        training_recorder = self.get_training_recorder()
        if training_recorder:
            training_recorder.recording_data = {}
    
    # ================================================================
    # 扩展接口方法
    # ================================================================
    
    def get_current_mode(self):
        """
        获取当前操作模式
        ================
        
        Returns:
            str: "doctor" 或 "patient"，如果无法获取则返回 "doctor"
        """
        if self.parent_window and hasattr(self.parent_window, 'current_mode'):
            return self.parent_window.current_mode
        return "doctor"  # 默认医生端模式
    
    def is_doctor_mode(self):
        """
        判断是否为医生端模式
        ====================
        
        Returns:
            bool: 是否为医生端模式
        """
        return self.get_current_mode() == "doctor"
    
    def is_patient_mode(self):
        """
        判断是否为患者端模式
        ====================
        
        Returns:
            bool: 是否为患者端模式
        """
        return self.get_current_mode() == "patient"
    
    def get_component_status(self):
        """
        获取组件状态信息
        ================
        
        用于调试和监控，返回各组件的状态信息
        
        Returns:
            dict: 组件状态信息字典
        """
        status = {
            'blocks_tab': self.blocks_tab is not None,
            'control_panel': self.get_control_panel() is not None,
            'visualizer': self.get_visualizer() is not None,
            'training_recorder': self.get_training_recorder() is not None,
            'sensor_count': self.sensor_count,
            'current_stage': self.get_current_stage(),
            'current_mode': self.get_current_mode(),
            'parent_window_set': self.parent_window is not None
        }
        
        return status
    
    def reset_to_defaults(self):
        """
        重置到默认状态
        ==============
        
        将所有组件重置到初始默认状态
        """
        try:
            # 重置到第一阶段
            self.set_stage(1)
            
            # 清空训练数据
            self.clear_training_data()
            
            # 重置可视化器状态
            visualizer = self.get_visualizer()
            if visualizer:
                visualizer.gray_block_rotation = 0
                visualizer.gray_block_tilt = 0
                visualizer.blue_blocks_curvature = 0
                visualizer.green_block_tilt = 0
                visualizer.gray_rotation_alert = False
                visualizer.gray_tilt_alert = False
                visualizer.blue_curvature_alert = False
                visualizer.green_tilt_alert = False
                visualizer.update()
                
            print("BlocksTabManager: 重置到默认状态完成")
            
        except Exception as e:
            print(f"BlocksTabManager: 重置失败: {e}")


# ================================================================
# 积木可视化工具函数
# ================================================================

def create_blocks_visualization_manager(sensor_count=6):
    """
    创建积木可视化管理器的工厂函数
    ==============================
    
    Args:
        sensor_count: 传感器数量
        
    Returns:
        BlocksTabManager: 积木可视化管理器实例
    """
    try:
        manager = BlocksTabManager(sensor_count=sensor_count)
        print(f"成功创建积木可视化管理器，传感器数量: {sensor_count}")
        return manager
    except Exception as e:
        print(f"创建积木可视化管理器失败: {e}")
        return None

def validate_sensor_data(data_values):
    """
    验证传感器数据格式
    ==================
    
    Args:
        data_values: 传感器数据
        
    Returns:
        bool: 数据格式是否正确
    """
    if not isinstance(data_values, (list, tuple)):
        return False
    
    if len(data_values) < 2:  # 至少包含时间戳和一个传感器值
        return False
    
    try:
        # 检查是否都是数值
        for value in data_values:
            float(value)
        return True
    except (ValueError, TypeError):
        return False
    
