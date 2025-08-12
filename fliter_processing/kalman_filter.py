#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多传感器卡尔曼滤波器模块
========================

用于对多个传感器数据进行卡尔曼滤波处理，减少噪声和提高数据质量。

主要功能：
1. 对每个传感器独立进行卡尔曼滤波
2. 支持动态调整滤波参数
3. 提供滤波统计信息
4. 保持时间戳信息
"""

import numpy as np
import time
from typing import List, Tuple, Dict, Optional


class KalmanFilter:
    """单传感器卡尔曼滤波器"""
    
    def __init__(self, process_noise: float = 0.01, measurement_noise: float = 0.1):
        """
        初始化卡尔曼滤波器
        
        Args:
            process_noise: 过程噪声协方差
            measurement_noise: 测量噪声协方差
        """
        # 状态变量 [位置, 速度]
        self.x = np.array([[0.0], [0.0]])  # 初始状态
        
        # 状态转移矩阵
        self.F = np.array([[1.0, 1.0], [0.0, 1.0]])
        
        # 测量矩阵 (只测量位置)
        self.H = np.array([[1.0, 0.0]])
        
        # 过程噪声协方差矩阵
        self.Q = np.array([[process_noise, 0.0], [0.0, process_noise]])
        
        # 测量噪声协方差
        self.R = np.array([[measurement_noise]])
        
        # 误差协方差矩阵
        self.P = np.array([[1.0, 0.0], [0.0, 1.0]])
        
        # 统计信息
        self.filtered_count = 0
        self.last_measurement = None
        self.last_filtered_value = None
        
    def predict(self):
        """预测步骤"""
        # 状态预测
        self.x = self.F @ self.x
        
        # 误差协方差预测
        self.P = self.F @ self.P @ self.F.T + self.Q
        
    def update(self, measurement: float) -> float:
        """
        更新步骤
        
        Args:
            measurement: 测量值
            
        Returns:
            float: 滤波后的值
        """
        # 计算卡尔曼增益
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # 状态更新
        y = measurement - self.H @ self.x  # 残差
        self.x = self.x + K @ y
        
        # 误差协方差更新
        I = np.eye(2)
        self.P = (I - K @ self.H) @ self.P
        
        # 更新统计信息
        self.filtered_count += 1
        self.last_measurement = measurement
        self.last_filtered_value = float(self.x[0, 0])
        
        return self.last_filtered_value
    
    def filter_value(self, measurement: float) -> float:
        """
        对单个值进行滤波
        
        Args:
            measurement: 测量值
            
        Returns:
            float: 滤波后的值
        """
        self.predict()
        return self.update(measurement)
    
    def reset(self):
        """重置滤波器状态"""
        self.x = np.array([[0.0], [0.0]])
        self.P = np.array([[1.0, 0.0], [0.0, 1.0]])
        self.filtered_count = 0
        self.last_measurement = None
        self.last_filtered_value = None
    
    def get_stats(self) -> Dict:
        """获取滤波器统计信息"""
        return {
            'filtered_count': self.filtered_count,
            'last_measurement': self.last_measurement,
            'last_filtered_value': self.last_filtered_value,
            'process_noise': float(self.Q[0, 0]),
            'measurement_noise': float(self.R[0, 0])
        }


class MultiSensorKalmanFilter:
    """多传感器卡尔曼滤波器"""
    
    def __init__(self, num_sensors: int = 7, process_noise: float = 0.01, 
                 measurement_noise: float = 0.1):
        """
        初始化多传感器卡尔曼滤波器
        
        Args:
            num_sensors: 传感器数量
            process_noise: 过程噪声协方差
            measurement_noise: 测量噪声协方差
        """
        self.num_sensors = num_sensors
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        
        # 为每个传感器创建独立的卡尔曼滤波器
        self.filters = [KalmanFilter(process_noise, measurement_noise) 
                       for _ in range(num_sensors)]
        
        # 统计信息
        self.total_filtered_count = 0
        self.start_time = time.time()
        
        # print(f"多传感器卡尔曼滤波器初始化完成: {num_sensors} 个传感器")
    
    def filter_sensor_data(self, sensor_data: List[float]) -> List[float]:
        """
        对传感器数据进行滤波
        
        Args:
            sensor_data: 传感器数据列表 [sensor1, sensor2, ..., sensorN]
            
        Returns:
            List[float]: 滤波后的传感器数据
        """
        if len(sensor_data) != self.num_sensors:
            print(f"警告：传感器数据长度 {len(sensor_data)} 与预期 {self.num_sensors} 不匹配")
            # 调整数据长度
            if len(sensor_data) < self.num_sensors:
                # 数据不足，用最后一个值填充
                sensor_data = sensor_data + [sensor_data[-1]] * (self.num_sensors - len(sensor_data))
            else:
                # 数据过多，截取前num_sensors个
                sensor_data = sensor_data[:self.num_sensors]
        
        # 对每个传感器进行滤波
        filtered_data = []
        for i, (filter_kf, measurement) in enumerate(zip(self.filters, sensor_data)):
            try:
                filtered_value = filter_kf.filter_value(measurement)
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
            print("警告：数据长度不足，无法进行滤波")
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
    
    def update_filter_parameters(self, process_noise: Optional[float] = None, 
                                measurement_noise: Optional[float] = None):
        """
        更新滤波器参数
        
        Args:
            process_noise: 新的过程噪声协方差
            measurement_noise: 新的测量噪声协方差
        """
        if process_noise is not None:
            self.process_noise = process_noise
            for filter_kf in self.filters:
                filter_kf.Q = np.array([[process_noise, 0.0], [0.0, process_noise]])
        
        if measurement_noise is not None:
            self.measurement_noise = measurement_noise
            for filter_kf in self.filters:
                filter_kf.R = np.array([[measurement_noise]])
        
        print(f"滤波器参数已更新: 过程噪声={self.process_noise}, 测量噪声={self.measurement_noise}")
    
    def reset_filters(self):
        """重置所有滤波器"""
        for filter_kf in self.filters:
            filter_kf.reset()
        
        self.total_filtered_count = 0
        self.start_time = time.time()
        print("所有滤波器已重置")
    
    def get_filter_stats(self) -> Dict:
        """获取滤波器统计信息"""
        # 计算平均滤波统计
        avg_stats = {
            'filtered_count': 0,
            'last_measurement': None,
            'last_filtered_value': None,
            'process_noise': self.process_noise,
            'measurement_noise': self.measurement_noise
        }
        
        total_filtered = 0
        for i, filter_kf in enumerate(self.filters):
            stats = filter_kf.get_stats()
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
            self.filters = [KalmanFilter(self.process_noise, self.measurement_noise) 
                           for _ in range(num_sensors)]
            print(f"传感器数量已更新为: {num_sensors}")
    
    def get_filter_quality_metrics(self) -> Dict:
        """
        获取滤波质量指标
        
        Returns:
            Dict: 包含各种质量指标的字典
        """
        if self.total_filtered_count == 0:
            return {'status': 'no_data'}
        
        # 计算每个传感器的方差变化（简单质量指标）
        quality_metrics = {
            'total_samples': self.total_filtered_count,
            'sensor_quality': []
        }
        
        for i, filter_kf in enumerate(self.filters):
            # 这里可以添加更复杂的质量评估逻辑
            # 目前只是简单的统计信息
            sensor_quality = {
                'sensor_index': i,
                'filtered_count': filter_kf.filtered_count,
                'last_value': filter_kf.last_filtered_value,
                'process_noise': float(filter_kf.Q[0, 0]),
                'measurement_noise': float(filter_kf.R[0, 0])
            }
            quality_metrics['sensor_quality'].append(sensor_quality)
        
        return quality_metrics


# # 测试函数
# def test_kalman_filter():
#     """测试卡尔曼滤波器功能"""
#     print("开始测试卡尔曼滤波器...")
    
#     # 创建多传感器滤波器
#     filter_kf = MultiSensorKalmanFilter(num_sensors=3, process_noise=0.01, measurement_noise=0.1)
    
#     # 模拟带噪声的传感器数据
#     import random
    
#     # 生成测试数据
#     test_data = []
#     for i in range(10):
#         # 模拟时间戳和3个传感器数据
#         timestamp = i * 0.1
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
#         filtered_data, raw_data = filter_kf.filter_data_with_timestamp(data)
#         if i < 5:  # 只显示前5个
#             print(f"  数据点 {i+1}: {filtered_data}")
    
#     # 显示统计信息
#     stats = filter_kf.get_filter_stats()
#     print(f"\n滤波统计信息:")
#     for key, value in stats.items():
#         print(f"  {key}: {value}")
    
#     print("卡尔曼滤波器测试完成!")


# if __name__ == "__main__":
#     test_kalman_filter() 