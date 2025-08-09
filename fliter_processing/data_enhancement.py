#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据增强模块，提供多种传感器数据增强算法
"""

import numpy as np
from scipy.signal import butter, filtfilt, savgol_filter


class DataEnhancement:
    """
    数据增强类，提供多种传感器数据增强算法
    """
    
    def __init__(self, num_sensors=6):
        """
        初始化数据增强模块
        
        Args:
            num_sensors: 传感器数量
        """
        self.num_sensors = num_sensors
        
        # 增强算法参数
        self.enhancement_enabled = False
        self.enhancement_method = 'motion_and_lock'  # 默认方法
        
        # 运动检测和锁定参数
        self.diff_window = 5
        self.motion_thresh = 0.015
        self.motion_gain = 2.5
        self.lock_smoothing = 0.95
        
        # 趋势增强参数
        self.trend_alpha = 0.8
        self.trend_gamma = 3.0
        
        # 局部对比增强参数
        self.local_window_size = 11
        self.local_gain = 2.0
        
        # 梯度加速度增强参数
        self.gradient_alpha = 0.6
        self.gradient_beta = 0.4
        
        # 分段归一化增强参数
        self.segment_threshold = 0.05
        self.segment_scale = 2.0
        
        # 二次滤波参数
        self.second_filter_enabled = True
        self.second_filter_method = 'kalman'  # 默认二次滤波方法
        self.second_filter_params = {
            'kalman': {
                'process_noise': 1e-6,
                'measurement_noise': 1e-1
            },
            'butterworth': {
                'cutoff_freq': 0.5,
                'fs': 125.0,
                'order': 4,
                'btype': 'low'
            },
            'savitzky_golay': {
                'window_size': 21,
                'order': 3
            }
        }
        
        # 历史数据存储（用于滑动窗口计算）
        self.history_data = [[] for _ in range(num_sensors)]
        self.max_history_size = 100
        
    def set_num_sensors(self, num_sensors):
        """设置传感器数量"""
        self.num_sensors = num_sensors
        self.history_data = [[] for _ in range(num_sensors)]
        
    def set_enhancement_enabled(self, enabled):
        """设置是否启用数据增强"""
        self.enhancement_enabled = enabled
        
    def set_enhancement_method(self, method):
        """设置增强方法"""
        self.enhancement_method = method
        
    def set_motion_and_lock_params(self, diff_window=5, motion_thresh=0.015, 
                                  motion_gain=2.5, lock_smoothing=0.95):
        """设置运动检测和锁定参数"""
        self.diff_window = diff_window
        self.motion_thresh = motion_thresh
        self.motion_gain = motion_gain
        self.lock_smoothing = lock_smoothing
        
    def set_trend_enhancement_params(self, alpha=0.8, gamma=3.0):
        """设置趋势增强参数"""
        self.trend_alpha = alpha
        self.trend_gamma = gamma
        
    def set_local_contrast_params(self, window_size=11, gain=2.0):
        """设置局部对比增强参数"""
        self.local_window_size = window_size
        self.local_gain = gain
        
    def set_gradient_enhancement_params(self, alpha=0.6, beta=0.4):
        """设置梯度加速度增强参数"""
        self.gradient_alpha = alpha
        self.gradient_beta = beta
        
    def set_segment_enhancement_params(self, threshold=0.05, scale=2.0):
        """设置分段归一化增强参数"""
        self.segment_threshold = threshold
        self.segment_scale = scale
        
    def set_second_filter_enabled(self, enabled):
        """设置是否启用二次滤波"""
        self.second_filter_enabled = enabled
        
    def set_second_filter_method(self, method):
        """设置二次滤波方法"""
        self.second_filter_method = method
        
    def set_second_filter_params(self, method, params):
        """设置二次滤波参数"""
        if method in self.second_filter_params:
            self.second_filter_params[method].update(params)
            
    def get_enhancement_params(self):
        """获取所有增强参数"""
        return {
            'enabled': self.enhancement_enabled,
            'method': self.enhancement_method,
            'motion_and_lock': {
                'diff_window': self.diff_window,
                'motion_thresh': self.motion_thresh,
                'motion_gain': self.motion_gain,
                'lock_smoothing': self.lock_smoothing
            },
            'trend': {
                'alpha': self.trend_alpha,
                'gamma': self.trend_gamma
            },
            'local_contrast': {
                'window_size': self.local_window_size,
                'gain': self.local_gain
            },
            'gradient': {
                'alpha': self.gradient_alpha,
                'beta': self.gradient_beta
            },
            'segment': {
                'threshold': self.segment_threshold,
                'scale': self.segment_scale
            },
            'second_filter': {
                'enabled': self.second_filter_enabled,
                'method': self.second_filter_method,
                'params': self.second_filter_params
            }
        }
        
    def enhance_data(self, data):
        """
        对传感器数据进行增强处理
        
        Args:
            data: 包含时间戳的传感器数据 [timestamp, sensor1, sensor2, ...]
            
        Returns:
            enhanced_data: 增强后的数据 [timestamp, sensor1, sensor2, ...]
        """
        if not self.enhancement_enabled or len(data) < 2:
            return data
            
        try:
            # 分离时间戳和传感器数据
            timestamp = data[0]
            sensor_data = data[1:1+self.num_sensors]
            
            # 应用增强算法
            enhanced_sensors = []
            for i, sensor_value in enumerate(sensor_data):
                # 更新历史数据
                self._update_history(i, sensor_value)
                
                # 获取历史数据用于增强
                history = self.history_data[i]
                if len(history) < 2:
                    enhanced_sensors.append(sensor_value)
                    continue
                    
                # 应用增强算法
                if self.enhancement_method == 'motion_and_lock':
                    enhanced = self._enhance_motion_and_lock(history)
                elif self.enhancement_method == 'trend':
                    enhanced = self._enhance_trend(history)
                elif self.enhancement_method == 'local_contrast':
                    enhanced = self._local_contrast_enhancement(history)
                elif self.enhancement_method == 'gradient':
                    enhanced = self._gradient_acceleration_enhancement(history)
                elif self.enhancement_method == 'segment':
                    enhanced = self._segmentwise_normalized_enhancement(history)
                else:
                    enhanced = sensor_value
                    
                enhanced_sensors.append(enhanced)
                
            # 应用二次滤波
            if self.second_filter_enabled:
                enhanced_sensors = self._apply_second_filter(enhanced_sensors)
                
            # 重新组合数据
            enhanced_data = [timestamp] + enhanced_sensors
            
            return enhanced_data
            
        except Exception as e:
            print(f"数据增强处理出错: {e}")
            return data
            
    def _update_history(self, sensor_index, value):
        """更新传感器历史数据"""
        if sensor_index < len(self.history_data):
            self.history_data[sensor_index].append(value)
            if len(self.history_data[sensor_index]) > self.max_history_size:
                self.history_data[sensor_index].pop(0)
                
    def _enhance_motion_and_lock(self, data):
        """
        增强动作过程中的幅度变化，在保持阶段锁定数值防止下坠
        """
        if len(data) < 2:
            return data[-1] if data else 0
            
        data_array = np.array(data)
        enhanced = np.copy(data_array)
        
        for i in range(1, len(data_array)):
            # 滑动差分
            diff = np.abs(data_array[i] - data_array[max(i - self.diff_window, 0)])
            if diff > self.motion_thresh:
                # 动作阶段：增强变化
                delta = data_array[i] - data_array[i-1]
                enhanced[i] = enhanced[i-1] + self.motion_gain * delta
            else:
                # 平稳阶段：锁定当前值（或慢速跟随）
                enhanced[i] = self.lock_smoothing * enhanced[i-1] + (1 - self.lock_smoothing) * data_array[i]
                
        return enhanced[-1]
        
    def _enhance_trend(self, data):
        """趋势增强函数"""
        if len(data) < 2:
            return data[-1] if data else 0
            
        data_array = np.array(data)
        delta = np.diff(data_array, prepend=data_array[0])
        enhancement = self.trend_alpha * np.sign(delta) * (np.abs(delta) ** self.trend_gamma)
        enhanced = data_array + enhancement
        
        return enhanced[-1]
        
    def _local_contrast_enhancement(self, data):
        """局部对比增强"""
        if len(data) < 2:
            return data[-1] if data else 0
            
        data_array = np.asarray(data).flatten()
        half = self.local_window_size // 2
        enhanced = np.copy(data_array)
        
        for i in range(len(data_array)):
            start = max(0, i - half)
            end = min(len(data_array), i + half + 1)
            local_mean = np.mean(data_array[start:end])
            enhanced[i] += self.local_gain * (data_array[i] - local_mean)
            
        return enhanced[-1]
        
    def _gradient_acceleration_enhancement(self, data):
        """梯度加速度增强"""
        if len(data) < 3:
            return data[-1] if data else 0
            
        data_array = np.asarray(data).flatten()
        first_diff = np.diff(data_array, prepend=data_array[0])
        second_diff = np.diff(first_diff, prepend=first_diff[0])
        enhanced = data_array + self.gradient_alpha * first_diff + self.gradient_beta * second_diff
        
        return enhanced[-1]
        
    def _segmentwise_normalized_enhancement(self, data):
        """分段归一化增强"""
        if len(data) < 2:
            return data[-1] if data else 0
            
        data_array = np.asarray(data).flatten()
        diff = np.abs(np.diff(data_array, prepend=data_array[0]))
        mask = diff > self.segment_threshold
        enhancement = np.where(mask, self.segment_scale * diff, 0)
        enhanced = data_array + enhancement * np.sign(np.diff(data_array, prepend=data_array[0]))
        
        return enhanced[-1]
        
    def _apply_second_filter(self, sensor_data):
        """应用二次滤波"""
        if not self.second_filter_enabled:
            return sensor_data
            
        try:
            filtered_data = []
            method = self.second_filter_method
            params = self.second_filter_params.get(method, {})
            
            for sensor_value in sensor_data:
                if method == 'kalman':
                    filtered = self._kalman_filter_single([sensor_value], 
                                                        params.get('process_noise', 1e-6),
                                                        params.get('measurement_noise', 1e-1))
                elif method == 'butterworth':
                    filtered = self._butterworth_filter_single([sensor_value],
                                                             params.get('cutoff_freq', 0.5),
                                                             params.get('fs', 125.0),
                                                             params.get('order', 4),
                                                             params.get('btype', 'low'))
                elif method == 'savitzky_golay':
                    filtered = self._savitzky_golay_filter_single([sensor_value],
                                                                params.get('window_size', 21),
                                                                params.get('order', 3))
                else:
                    filtered = sensor_value
                    
                filtered_data.append(filtered)
                
            return filtered_data
            
        except Exception as e:
            print(f"二次滤波出错: {e}")
            return sensor_data
            
    def _kalman_filter_single(self, data, process_noise, measurement_noise):
        """单点卡尔曼滤波"""
        if len(data) < 1:
            return 0
            
        data_array = np.array(data)
        n = len(data_array)
        filtered = np.zeros(n)
        P = np.zeros(n)
        K = np.zeros(n)
        
        filtered[0] = data_array[0]
        P[0] = 1.0
        
        for i in range(1, n):
            predicted = filtered[i-1]
            P_predicted = P[i-1] + process_noise
            K[i] = P_predicted / (P_predicted + measurement_noise)
            filtered[i] = predicted + K[i] * (data_array[i] - predicted)
            P[i] = (1 - K[i]) * P_predicted
            
        return filtered[-1]
        
    def _butterworth_filter_single(self, data, cutoff_freq, fs, order, btype):
        """单点Butterworth滤波"""
        if len(data) < 1:
            return 0
            
        data_array = np.array(data)
        nyquist = 0.5 * fs
        normal_cutoff = cutoff_freq / nyquist
        b, a = butter(order, normal_cutoff, btype=btype, analog=False)
        filtered_data = filtfilt(b, a, data_array)
        
        return filtered_data[-1]
        
    def _savitzky_golay_filter_single(self, data, window_size, order):
        """单点Savitzky-Golay滤波"""
        if len(data) < 1:
            return 0
            
        data_array = np.array(data)
        if window_size % 2 == 0:
            window_size += 1
            
        if len(data_array) < window_size:
            return data_array[-1]
            
        filtered_data = savgol_filter(data_array, window_size, order)
        return filtered_data[-1]
        
    def get_enhancement_stats(self):
        """获取增强统计信息"""
        return {
            'enabled': self.enhancement_enabled,
            'method': self.enhancement_method,
            'num_sensors': self.num_sensors,
            'history_sizes': [len(hist) for hist in self.history_data]
        } 