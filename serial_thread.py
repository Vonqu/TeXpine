#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
串口数据读取线程模块
"""

import time
import serial
from PyQt5.QtCore import QThread, pyqtSignal


class SerialThread(QThread):
    """串口读取线程，负责读取串口数据并发送信号"""
    data_received = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, port, baud_rate, num_sensors):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.num_sensors = num_sensors
        self.running = False
        self.duration = None
        self.start_time = None
        self._ser = None
        
    def set_duration(self, duration):
        """设置数据采集持续时间（秒）"""
        self.duration = duration
        
    def stop(self):
        """停止线程运行"""
        self.running = False
        
    def run(self):
        """线程主函数，读取串口数据"""
        try:
            # 打开串口
            self._ser = serial.Serial(self.port, self.baud_rate, timeout=1)
            self.running = True
            self.start_time = time.time()
            
            while self.running:
                # 检查是否超过时间限制
                if self.duration is not None:
                    elapsed_time = time.time() - self.start_time
                    if elapsed_time >= self.duration:
                        self.running = False
                        break
                
                # 读取串口数据
                if self._ser.in_waiting:
                    line = self._ser.readline().decode('latin-1').strip()
                    try:
                        # 解析数据
                        values = [float(x) for x in line.split(',')]
                        # 确保数据长度与传感器数量一致
                        if len(values) == self.num_sensors:
                            # 添加时间戳
                            timestamp = time.time() - self.start_time
                            values.insert(0, timestamp)
                            self.data_received.emit(values)
                    except ValueError:
                        # 解析错误，忽略这一行
                        pass
                else:
                    # 短暂休眠以避免CPU使用率过高
                    self.msleep(10)
            
            # 关闭串口
            if self._ser and self._ser.is_open:
                self._ser.close()
            
        except Exception as e:
            error_msg = f"串口读取错误: {str(e)}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
            self.running = False
            
    def __del__(self):
        """析构函数，确保串口被正确关闭"""
        if hasattr(self, '_ser') and self._ser and self._ser.is_open:
            self._ser.close()