#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多传感器Butterworth滤波器模块
============================

用于对多个传感器数据进行Butterworth滤波处理，减少噪声和提高数据质量。

主要功能：
1. 对每个传感器独立进行Butterworth滤波
2. 支持动态调整滤波参数（截止频率、阶数、滤波器类型）
3. 提供滤波统计信息
4. 保持时间戳信息
5. 支持低通、高通、带通滤波器
"""

import numpy as np
import time
from typing import List, Tuple, Dict, Optional
from scipy import signal
from collections import deque


class ButterworthFilter:
    """单传感器Butterworth滤波器"""
    
    def __init__(self, cutoff_freq: float = 2.0, fs: float = 100.0, 
                 order: int = 4, btype: str = 'low'):
        """
        初始化Butterworth滤波器
        
        Args:
            cutoff_freq: 截止频率 (Hz)
            fs: 采样频率 (Hz)
            order: 滤波器阶数
            btype: 滤波器类型 ('low', 'high', 'band')
        """
        self.cutoff_freq = cutoff_freq
        self.fs = fs
        self.order = order
        self.btype = btype
        
        # 数据缓冲区（用于实时滤波）
        self.data_buffer = deque(maxlen=order * 10)  # 缓冲区大小至少为阶数的10倍
        
        # 滤波器系数
        self.b = None
        self.a = None
        
        # 状态变量（用于filtfilt）
        self.zi = None
        
        # 统计信息
        self.filtered_count = 0
        self.last_measurement = None
        self.last_filtered_value = None
        
        # 初始化滤波器
        self._update_filter_coefficients()
        
    def _update_filter_coefficients(self):
        """更新滤波器系数"""
        try:
            # 计算归一化截止频率
            nyquist = self.fs / 2.0
            if self.cutoff_freq >= nyquist:
                print(f"警告：截止频率 {self.cutoff_freq} Hz 超过奈奎斯特频率 {nyquist} Hz，已调整为 {nyquist * 0.9} Hz")
                self.cutoff_freq = nyquist * 0.9
            
            normalized_cutoff = self.cutoff_freq / nyquist
            
            # 设计Butterworth滤波器
            self.b, self.a = signal.butter(self.order, normalized_cutoff, btype=self.btype)
            
            # 初始化状态变量
            self.zi = signal.lfilter_zi(self.b, self.a)
            
            # print(f"Butterworth滤波器已更新: 截止频率={self.cutoff_freq}Hz, 阶数={self.order}, 类型={self.btype}")
            
        except Exception as e:
            print(f"更新滤波器系数失败: {e}")
            # 使用默认系数
            self.b = np.array([1.0])
            self.a = np.array([1.0])
            self.zi = np.array([0.0])
    
    def filter_value(self, measurement: float) -> float:
        """
        对单个值进行滤波（实时处理）
        
        Args:
            measurement: 测量值
            
        Returns:
            float: 滤波后的值
        """
        try:
            # 将新数据添加到缓冲区
            self.data_buffer.append(measurement)
            
            # 如果缓冲区数据不足，返回原始值
            if len(self.data_buffer) < self.order * 2:
                self.last_filtered_value = measurement
                self.last_measurement = measurement
                self.filtered_count += 1
                return measurement
            
            # 将缓冲区转换为数组
            data_array = np.array(list(self.data_buffer))
            
            # 使用filtfilt进行零相位滤波
            filtered_data = signal.filtfilt(self.b, self.a, data_array)
            
            # 返回最新的滤波值
            filtered_value = float(filtered_data[-1])
            
            # 更新统计信息
            self.filtered_count += 1
            self.last_measurement = measurement
            self.last_filtered_value = filtered_value
            
            return filtered_value
            
        except Exception as e:
            # print(f"Butterworth滤波失败: {e}")
            # 返回原始值作为备用
            return measurement
    
    def update_parameters(self, cutoff_freq: Optional[float] = None, 
                         fs: Optional[float] = None, 
                         order: Optional[int] = None, 
                         btype: Optional[str] = None):
        """
        更新滤波器参数
        
        Args:
            cutoff_freq: 新的截止频率
            fs: 新的采样频率
            order: 新的滤波器阶数
            btype: 新的滤波器类型
        """
        if cutoff_freq is not None:
            self.cutoff_freq = cutoff_freq
        if fs is not None:
            self.fs = fs
        if order is not None:
            self.order = order
        if btype is not None:
            self.btype = btype
            
        # 更新滤波器系数
        self._update_filter_coefficients()
        
        # 清空缓冲区，重新开始
        self.data_buffer.clear()
        self.zi = signal.lfilter_zi(self.b, self.a) if self.b is not None else np.array([0.0])
    
    def reset(self):
        """重置滤波器状态"""
        self.data_buffer.clear()
        self.zi = signal.lfilter_zi(self.b, self.a) if self.b is not None else np.array([0.0])
        self.filtered_count = 0
        self.last_measurement = None
        self.last_filtered_value = None
    
    def get_stats(self) -> Dict:
        """获取滤波器统计信息"""
        return {
            'filtered_count': self.filtered_count,
            'last_measurement': self.last_measurement,
            'last_filtered_value': self.last_filtered_value,
            'cutoff_freq': self.cutoff_freq,
            'fs': self.fs,
            'order': self.order,
            'btype': self.btype,
            'buffer_size': len(self.data_buffer)
        }


class MultiSensorButterworthFilter:
    """多传感器Butterworth滤波器"""
    
    def __init__(self, num_sensors: int = 7, cutoff_freq: float = 2.0, 
                 fs: float = 100.0, order: int = 4, btype: str = 'low'):
        """
        初始化多传感器Butterworth滤波器
        
        Args:
            num_sensors: 传感器数量
            cutoff_freq: 截止频率 (Hz)
            fs: 采样频率 (Hz)
            order: 滤波器阶数
            btype: 滤波器类型 ('low', 'high', 'band')
        """
        self.num_sensors = num_sensors
        self.cutoff_freq = cutoff_freq
        self.fs = fs
        self.order = order
        self.btype = btype
        
        # 为每个传感器创建独立的Butterworth滤波器
        self.filters = [ButterworthFilter(cutoff_freq, fs, order, btype) 
                       for _ in range(num_sensors)]
        
        # 统计信息
        self.total_filtered_count = 0
        self.start_time = time.time()
        
        # print(f"多传感器Butterworth滤波器初始化完成: {num_sensors} 个传感器")
        # print(f"参数: 截止频率={cutoff_freq}Hz, 采样频率={fs}Hz, 阶数={order}, 类型={btype}")
    
    def filter_sensor_data(self, sensor_data: List[float]) -> List[float]:
        """
        对传感器数据进行滤波
        
        Args:
            sensor_data: 传感器数据列表 [sensor1, sensor2, ..., sensorN]
            
        Returns:
            List[float]: 滤波后的传感器数据
        """
        if len(sensor_data) != self.num_sensors:
            # print(f"警告：传感器数据长度 {len(sensor_data)} 与预期 {self.num_sensors} 不匹配")
            # 调整数据长度
            if len(sensor_data) < self.num_sensors:
                # 数据不足，用最后一个值填充
                sensor_data = sensor_data + [sensor_data[-1]] * (self.num_sensors - len(sensor_data))
            else:
                # 数据过多，截取前num_sensors个
                sensor_data = sensor_data[:self.num_sensors]
        
        # 对每个传感器进行滤波
        filtered_data = []
        for i, (filter_bw, measurement) in enumerate(zip(self.filters, sensor_data)):
            try:
                filtered_value = filter_bw.filter_value(measurement)
                filtered_data.append(filtered_value)
            except Exception as e:
                print(f"传感器 {i+1} 滤波失败: {e}")
                # 使用原始值作为备用
                filtered_data.append(measurement)
        
        self.total_filtered_count += 1
        return filtered_data
    
    def filter_data_with_timestamp(self, data: List[float]) -> Tuple[List[float], List[float]]:
        """
        对包含时间戳的数据进行滤波
        
        Args:
            data: 数据列表 [timestamp, sensor1, sensor2, ..., sensorN]
            
        Returns:
            Tuple[List[float], List[float]]: (滤波后数据, 原始数据)
        """
        if len(data) < 2:
            # print("警告：数据长度不足，无法进行滤波")
            return data, data
        
        # 分离时间戳和传感器数据
        timestamp = data[0]
        sensor_data = data[1:]
        
        # 对传感器数据进行滤波
        filtered_sensor_data = self.filter_sensor_data(sensor_data)
        
        # 重新组合数据
        filtered_data = [timestamp] + filtered_sensor_data
        raw_data = data.copy()
        
        return filtered_data, raw_data
    
    def update_filter_parameters(self, cutoff_freq: Optional[float] = None, 
                                fs: Optional[float] = None,
                                order: Optional[int] = None, 
                                btype: Optional[str] = None):
        """
        更新滤波器参数
        
        Args:
            cutoff_freq: 新的截止频率
            fs: 新的采样频率
            order: 新的滤波器阶数
            btype: 新的滤波器类型
        """
        if cutoff_freq is not None:
            self.cutoff_freq = cutoff_freq
        if fs is not None:
            self.fs = fs
        if order is not None:
            self.order = order
        if btype is not None:
            self.btype = btype
        
        # 更新所有滤波器的参数
        for filter_bw in self.filters:
            filter_bw.update_parameters(cutoff_freq, fs, order, btype)
        
        # print(f"Butterworth滤波器参数已更新: 截止频率={self.cutoff_freq}Hz, "
            #   f"采样频率={self.fs}Hz, 阶数={self.order}, 类型={self.btype}")
    
    def reset_filters(self):
        """重置所有滤波器"""
        for filter_bw in self.filters:
            filter_bw.reset()
        
        self.total_filtered_count = 0
        self.start_time = time.time()
        print("所有Butterworth滤波器已重置")
    
    def get_filter_stats(self) -> Dict:
        """获取滤波器统计信息"""
        # 计算平均滤波统计
        avg_stats = {
            'filtered_count': 0,
            'last_measurement': None,
            'last_filtered_value': None,
            'cutoff_freq': self.cutoff_freq,
            'fs': self.fs,
            'order': self.order,
            'btype': self.btype
        }
        
        total_filtered = 0
        for i, filter_bw in enumerate(self.filters):
            stats = filter_bw.get_stats()
            total_filtered += stats['filtered_count']
            
            # 记录最后一个滤波值（用于调试）
            if stats['last_filtered_value'] is not None:
                avg_stats['last_filtered_value'] = stats['last_filtered_value']
        
        avg_stats['filtered_count'] = total_filtered
        avg_stats['num_sensors'] = self.num_sensors
        avg_stats['total_filtered_count'] = self.total_filtered_count
        
        # 计算运行时间
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            avg_stats['filtering_rate'] = self.total_filtered_count / elapsed_time
        else:
            avg_stats['filtering_rate'] = 0
        
        return avg_stats
    
    def get_sensor_filter_stats(self, sensor_index: int) -> Dict:
        """
        获取特定传感器的滤波器统计信息
        
        Args:
            sensor_index: 传感器索引 (0-based)
            
        Returns:
            Dict: 该传感器的滤波器统计信息
        """
        if 0 <= sensor_index < len(self.filters):
            return self.filters[sensor_index].get_stats()
        else:
            return {}
    
    def set_num_sensors(self, num_sensors: int):
        """
        设置传感器数量（会重新创建滤波器）
        
        Args:
            num_sensors: 新的传感器数量
        """
        if num_sensors != self.num_sensors:
            self.num_sensors = num_sensors
            self.filters = [ButterworthFilter(self.cutoff_freq, self.fs, self.order, self.btype) 
                           for _ in range(num_sensors)]
            # print(f"传感器数量已更新为: {num_sensors}")
    
    def get_filter_quality_metrics(self) -> Dict:
        """
        获取滤波质量指标
        
        Returns:
            Dict: 包含各种质量指标的字典
        """
        if self.total_filtered_count == 0:
            return {'status': 'no_data'}
        
        # 计算每个传感器的滤波质量指标
        quality_metrics = {
            'total_samples': self.total_filtered_count,
            'sensor_quality': []
        }
        
        for i, filter_bw in enumerate(self.filters):
            # 计算滤波质量指标
            sensor_quality = {
                'sensor_index': i,
                'filtered_count': filter_bw.filtered_count,
                'last_value': filter_bw.last_filtered_value,
                'cutoff_freq': filter_bw.cutoff_freq,
                'fs': filter_bw.fs,
                'order': filter_bw.order,
                'btype': filter_bw.btype,
                'buffer_size': len(filter_bw.data_buffer)
            }
            quality_metrics['sensor_quality'].append(sensor_quality)
        
        return quality_metrics


# # 测试函数
# def test_butterworth_filter():
#     """测试Butterworth滤波器功能"""
#     print("开始测试Butterworth滤波器...")
    
#     # 创建多传感器滤波器
#     filter_bw = MultiSensorButterworthFilter(
#         num_sensors=3, 
#         cutoff_freq=2.0, 
#         fs=100.0, 
#         order=4, 
#         btype='low'
#     )
    
#     # 模拟带噪声的传感器数据
#     import random
    
#     # 生成测试数据
#     test_data = []
#     for i in range(20):  # 增加测试数据点数量
#         # 模拟时间戳和3个传感器数据
#         timestamp = i * 0.01  # 10ms采样间隔
#         sensor1 = 2500 + 50 * np.sin(i * 0.5) + random.gauss(0, 10)  # 正弦波 + 噪声
#         sensor2 = 2600 + 30 * np.cos(i * 0.3) + random.gauss(0, 8)   # 余弦波 + 噪声
#         sensor3 = 2700 + 20 * np.sin(i * 0.7) + random.gauss(0, 12)  # 另一个正弦波 + 噪声
        
#         data_point = [timestamp, sensor1, sensor2, sensor3]
#         test_data.append(data_point)
    
#     print("原始数据:")
#     for i, data in enumerate(test_data[:5]):  # 只显示前5个
#         print(f"  数据点 {i+1}: {data}")
    
#     print("\n滤波后数据:")
#     for i, data in enumerate(test_data):
#         filtered_data, raw_data = filter_bw.filter_data_with_timestamp(data)
#         if i < 5:  # 只显示前5个
#             print(f"  数据点 {i+1}: {filtered_data}")
    
#     # 显示统计信息
#     stats = filter_bw.get_filter_stats()
#     print(f"\n滤波统计信息:")
#     for key, value in stats.items():
#         print(f"  {key}: {value}")
    
#     print("Butterworth滤波器测试完成!")


# if __name__ == "__main__":
#     test_butterworth_filter() 