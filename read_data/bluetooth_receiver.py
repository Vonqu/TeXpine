#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
蓝牙串口数据接收模块
"""

import time
import threading
import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np

class BluetoothReceiver(QObject):
    """蓝牙串口数据接收类"""
    
    # 定义信号
    data_received = pyqtSignal(list)  # 接收到数据时发出信号
    error_occurred = pyqtSignal(str)  # 错误信号
    
    def __init__(self, data_manager):
        """初始化蓝牙接收器
        
        Args:
            data_manager: DataManager实例，用于存储接收到的数据
        """
        super().__init__()
        self.data_manager = data_manager
        self.serial_port = None
        self.is_connected = False
        self.is_receiving = False
        self.receiver_thread = None
        self.start_time = 0
        self.port_name = ""
        self.baud_rate = 115200
        self.num_sensors = 7  # 默认传感器数量
        self.duration = None  # 采集时长
        
    def get_available_ports(self):
        """获取可用的串口列表
        
        Returns:
            list: 可用串口名称列表
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def connect(self, port_name, baud_rate=115200):
        """连接到指定串口
        
        Args:
            port_name: 串口名称
            baud_rate: 波特率，默认115200
            
        Returns:
            bool: 是否成功连接
        """
        if self.is_connected:
            self.disconnect()
            
        try:
            self.serial_port = serial.Serial(port_name, baud_rate, timeout=1)
            self.is_connected = True
            self.port_name = port_name
            self.baud_rate = baud_rate
            return True
        except Exception as e:
            self.error_occurred.emit(f"蓝牙连接失败: {str(e)}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.is_receiving:
            self.stop_receiving()
            
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            
        self.is_connected = False
    
    def set_duration(self, duration):
        """设置数据采集持续时间（秒）"""
        self.duration = duration
        
    def set_num_sensors(self, num_sensors):
        """设置传感器数量"""
        self.num_sensors = num_sensors
    
    def start_receiving(self):
        """开始接收数据"""
        if not self.is_connected:
            self.error_occurred.emit("未连接，无法接收数据")
            return False
            
        if self.is_receiving:
            return True
            
        # 清空任何缓冲数据
        self.serial_port.reset_input_buffer()
        
        # 记录开始时间
        self.start_time = time.time()
        self.is_receiving = True
        
        # 启动接收线程
        self.receiver_thread = threading.Thread(target=self._receive_data_thread)
        self.receiver_thread.daemon = True
        self.receiver_thread.start()
        
        return True
    
    def stop(self):
        """停止接收数据"""
        self.stop_receiving()
    
    def stop_receiving(self):
        """停止接收数据"""
        self.is_receiving = False
        if self.receiver_thread:
            self.receiver_thread.join(timeout=1.0)
            self.receiver_thread = None
    
    def _receive_data_thread(self):
        """数据接收线程"""
        while self.is_receiving:
            try:
                # 检查是否超过时间限制
                if self.duration is not None:
                    elapsed_time = time.time() - self.start_time
                    if elapsed_time >= self.duration:
                        self.is_receiving = False
                        break
                
                if self.serial_port.in_waiting > 0:
                    # 读取一行数据
                    line = self.serial_port.readline().decode('utf-8').strip()
                    
                    # 处理数据行
                    if line:
                        try:
                            # 解析逗号分隔的值
                            values = [float(val) for val in line.split(',')]
                            
                            # 如果数据有效（检查是否匹配预期的传感器数量）
                            if len(values) == self.num_sensors:
                                # 计算采样时间（相对于开始时间）
                                timestamp = time.time() - self.start_time
                                values.insert(0, timestamp)
                                # 发出数据接收信号
                                self.data_received.emit(values)
                        except ValueError:
                            # 忽略无法解析的行
                            pass
                else:
                    # 短暂休眠以减少CPU使用率
                    time.sleep(0.001)
            except Exception as e:
                self.error_occurred.emit(f"接收数据时出错: {str(e)}")
                self.is_receiving = False
                break
    
    def isRunning(self):
        """检查是否正在运行"""
        return self.is_receiving
    
    def wait(self):
        """等待线程结束"""
        if self.receiver_thread:
            self.receiver_thread.join(timeout=1.0)