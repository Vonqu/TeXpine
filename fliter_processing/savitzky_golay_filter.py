#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多传感器Savitzky-Golay滤波器模块
===============================

用于对多个传感器数据进行Savitzky-Golay滤波处理，减少噪声和提高数据质量。

主要功能：
1. 对每个传感器独立进行Savitzky-Golay滤波
2. 支持动态调整滤波参数（窗口长度、多项式阶数）
3. 提供滤波统计信息
4. 保持时间戳信息
"""

import numpy as np
import time
from typing import List, Tuple, Dict, Optional
from scipy.signal import savgol_filter
from collections import deque

class SavitzkyGolayFilter:
    """单传感器Savitzky-Golay滤波器"""
    def __init__(self, window_length: int = 11, polyorder: int = 3):
        self.window_length = window_length if window_length % 2 == 1 else window_length + 1
        self.polyorder = polyorder
        self.data_buffer = deque(maxlen=100)
        self.filtered_count = 0
        self.last_measurement = None
        self.last_filtered_value = None

    def filter_value(self, measurement: float) -> float:
        self.data_buffer.append(measurement)
        if len(self.data_buffer) < self.window_length:
            self.filtered_count += 1
            self.last_measurement = measurement
            self.last_filtered_value = measurement
            return measurement
        try:
            data_array = np.array(self.data_buffer)
            filtered_data = savgol_filter(data_array, self.window_length, self.polyorder)
            filtered_value = float(filtered_data[-1])
            self.filtered_count += 1
            self.last_measurement = measurement
            self.last_filtered_value = filtered_value
            return filtered_value
        except Exception as e:
            # print(f"Savitzky-Golay滤波失败: {e}")
            return measurement

    def update_parameters(self, window_length: Optional[int] = None, polyorder: Optional[int] = None):
        if window_length is not None:
            self.window_length = window_length if window_length % 2 == 1 else window_length + 1
        if polyorder is not None:
            self.polyorder = polyorder
        self.data_buffer.clear()

    def reset(self):
        self.data_buffer.clear()
        self.filtered_count = 0
        self.last_measurement = None
        self.last_filtered_value = None

    def get_stats(self) -> Dict:
        return {
            'filtered_count': self.filtered_count,
            'last_measurement': self.last_measurement,
            'last_filtered_value': self.last_filtered_value,
            'window_length': self.window_length,
            'polyorder': self.polyorder,
            'buffer_size': len(self.data_buffer)
        }

class MultiSensorSavitzkyGolayFilter:
    """多传感器Savitzky-Golay滤波器"""
    def __init__(self, num_sensors: int = 7, window_length: int = 11, polyorder: int = 3):
        self.num_sensors = num_sensors
        self.window_length = window_length
        self.polyorder = polyorder
        self.filters = [SavitzkyGolayFilter(window_length, polyorder) for _ in range(num_sensors)]
        self.total_filtered_count = 0
        self.start_time = time.time()
        # print(f"多传感器Savitzky-Golay滤波器初始化完成: {num_sensors} 个传感器")
        # print(f"参数: window_length={window_length}, polyorder={polyorder}")

    def filter_sensor_data(self, sensor_data: List[float]) -> List[float]:
        if len(sensor_data) != self.num_sensors:
            print(f"警告：传感器数据长度 {len(sensor_data)} 与预期 {self.num_sensors} 不匹配")
            if len(sensor_data) < self.num_sensors:
                sensor_data = sensor_data + [sensor_data[-1]] * (self.num_sensors - len(sensor_data))
            else:
                sensor_data = sensor_data[:self.num_sensors]
        filtered_data = []
        for i, (filter_sg, measurement) in enumerate(zip(self.filters, sensor_data)):
            try:
                filtered_value = filter_sg.filter_value(measurement)
                filtered_data.append(filtered_value)
            except Exception as e:
                print(f"传感器 {i+1} 滤波失败: {e}")
                filtered_data.append(measurement)
        self.total_filtered_count += 1
        return filtered_data

    def filter_data_with_timestamp(self, data: List[float]) -> Tuple[List[float], List[float]]:
        if len(data) < 2:
            print("警告：数据长度不足，无法进行滤波")
            return data, data
        timestamp = data[0]
        sensor_data = data[1:]
        filtered_sensor_data = self.filter_sensor_data(sensor_data)
        filtered_data = [timestamp] + filtered_sensor_data
        raw_data = data.copy()
        return filtered_data, raw_data

    def update_filter_parameters(self, window_length: Optional[int] = None, polyorder: Optional[int] = None):
        if window_length is not None:
            self.window_length = window_length
        if polyorder is not None:
            self.polyorder = polyorder
        for filter_sg in self.filters:
            filter_sg.update_parameters(window_length, polyorder)
        print(f"Savitzky-Golay滤波器参数已更新: window_length={self.window_length}, polyorder={self.polyorder}")

    def reset_filters(self):
        for filter_sg in self.filters:
            filter_sg.reset()
        self.total_filtered_count = 0
        self.start_time = time.time()
        print("所有Savitzky-Golay滤波器已重置")

    def get_filter_stats(self) -> Dict:
        avg_stats = {
            'filtered_count': 0,
            'last_measurement': None,
            'last_filtered_value': None,
            'window_length': self.window_length,
            'polyorder': self.polyorder
        }
        total_filtered = 0
        for i, filter_sg in enumerate(self.filters):
            stats = filter_sg.get_stats()
            total_filtered += stats['filtered_count']
            if stats['last_filtered_value'] is not None:
                avg_stats['last_filtered_value'] = stats['last_filtered_value']
        avg_stats['filtered_count'] = total_filtered
        avg_stats['num_sensors'] = self.num_sensors
        avg_stats['total_filtered_count'] = self.total_filtered_count
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            avg_stats['filtering_rate'] = self.total_filtered_count / elapsed_time
        else:
            avg_stats['filtering_rate'] = 0
        return avg_stats

    def get_sensor_filter_stats(self, sensor_index: int) -> Dict:
        if 0 <= sensor_index < len(self.filters):
            return self.filters[sensor_index].get_stats()
        else:
            return {}

    def set_num_sensors(self, num_sensors: int):
        if num_sensors != self.num_sensors:
            self.num_sensors = num_sensors
            self.filters = [SavitzkyGolayFilter(self.window_length, self.polyorder) for _ in range(num_sensors)]
            print(f"传感器数量已更新为: {num_sensors}")

    def get_filter_quality_metrics(self) -> Dict:
        if self.total_filtered_count == 0:
            return {'status': 'no_data'}
        quality_metrics = {
            'total_samples': self.total_filtered_count,
            'sensor_quality': []
        }
        for i, filter_sg in enumerate(self.filters):
            sensor_quality = {
                'sensor_index': i,
                'filtered_count': filter_sg.filtered_count,
                'last_value': filter_sg.last_filtered_value,
                'window_length': filter_sg.window_length,
                'polyorder': filter_sg.polyorder,
                'buffer_size': len(filter_sg.data_buffer)
            }
            quality_metrics['sensor_quality'].append(sensor_quality)
        return quality_metrics

# # 测试函数
# def test_sg_filter():
#     print("开始测试Savitzky-Golay滤波器...")
#     filter_sg = MultiSensorSavitzkyGolayFilter(num_sensors=3, window_length=11, polyorder=3)
#     import random
#     test_data = []
#     for i in range(20):
#         timestamp = i * 0.01
#         sensor1 = 2500 + 50 * np.sin(i * 0.5) + random.gauss(0, 10)
#         sensor2 = 2600 + 30 * np.cos(i * 0.3) + random.gauss(0, 8)
#         sensor3 = 2700 + 20 * np.sin(i * 0.7) + random.gauss(0, 12)
#         data_point = [timestamp, sensor1, sensor2, sensor3]
#         test_data.append(data_point)
#     print("原始数据:")
#     for i, data in enumerate(test_data[:5]):
#         print(f"  数据点 {i+1}: {data}")
#     print("\n滤波后数据:")
#     for i, data in enumerate(test_data):
#         filtered_data, raw_data = filter_sg.filter_data_with_timestamp(data)
#         if i < 5:
#             print(f"  数据点 {i+1}: {filtered_data}")
#     stats = filter_sg.get_filter_stats()
#     print(f"\n滤波统计信息:")
#     for key, value in stats.items():
#         print(f"  {key}: {value}")
#     print("Savitzky-Golay滤波器测试完成!")

# if __name__ == "__main__":
#     test_sg_filter() 