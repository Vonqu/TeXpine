
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
事件记录器模块（修改版）
======================

修改内容：
1. 支持误差范围记录到事件数据
2. 保持原有所有功能不变
"""

import csv
import os
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

class EventRecorder(QObject):
    """
    事件记录器类（修改版）
    ====================
    
    新增功能：
    - 支持误差范围记录
    """
    
    # 信号定义
    event_recorded = pyqtSignal(str, dict)  # 事件记录信号：事件名称，事件数据
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.events_file_path = ""
        self.current_sensor_data = None
        self.current_processed_data = None  # 新增：存储处理后的数据
        self.num_sensors = 7  # 恢复默认值为7
        self.is_new_acquisition = True
        self.acquisition_start_time = None  # 采集开始的绝对时间
        self.acquisition_start_time_str = ""  # 采集开始时间的字符串表示
        self.event_count = 0  # 新增：事件计数器
        self.event_history = []  # 新增：事件历史记录
        
    def set_events_file_path(self, file_path):
        """设置事件文件保存路径"""
        self.events_file_path = file_path
        self.is_new_acquisition = True  # 新路径时标记为新采集
        # 确保目录存在
        try:
            directory = os.path.dirname(self.events_file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
        except Exception as _e:
            print(f"创建事件文件目录失败: {self.events_file_path}, 错误: {_e}")
        print(f"事件文件路径已设置: {file_path}")
        
    def set_num_sensors(self, num_sensors):
        """设置传感器数量"""
        # old_num = self.num_sensors
        self.num_sensors = num_sensors
        # print(f"事件记录器传感器数量已设置为: {num_sensors} (原来是: {old_num})")
        
        # # 如果传感器数量发生变化且已经开始采集，标记需要重新创建文件头
        # if old_num != num_sensors and hasattr(self, 'acquisition_start_time') and self.acquisition_start_time:
        #     print(f"传感器数量变化，下次记录事件时将更新文件格式")
        
    def set_current_sensor_data(self, sensor_data, processed_data=None):
        """设置当前传感器数据（同时保存原始数据和处理后数据）"""
        # 检查数据是否包含时间戳
        if isinstance(sensor_data, (list, tuple)) and len(sensor_data) > 0:
            # 如果第一个元素是时间戳（通常为 epoch 秒，远大于 1e8），则移除它
            try:
                first = sensor_data[0]
                if isinstance(first, (int, float)) and (
                    first > 1e8 or len(sensor_data) == self.num_sensors + 1
                ):
                    sensor_data = sensor_data[1:]
                    if processed_data is not None and isinstance(processed_data, (list, tuple)) and len(processed_data) > 0:
                        # 若处理后数据同样包含时间戳，保持一致去除
                        p_first = processed_data[0]
                        if isinstance(p_first, (int, float)) and (
                            p_first > 1e8 or len(processed_data) == self.num_sensors + 1
                        ):
                            processed_data = processed_data[1:]
            except Exception:
                pass

        self.current_sensor_data = sensor_data
        if processed_data is not None:
            self.current_processed_data = processed_data
    
    def get_latest_sensor_data(self):
        """获取最新的传感器数据（包含时间戳）"""
        if self.current_sensor_data is not None:
            # 添加当前时间戳
            import time
            timestamp = time.time()
            return [timestamp] + list(self.current_sensor_data)
        return None
        
    def start_new_acquisition(self):
        """开始新的采集周期"""
        self.is_new_acquisition = True
        self.acquisition_start_time = datetime.now()
        self.acquisition_start_time_str = self.acquisition_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"开始新的事件采集周期，开始时间: {self.acquisition_start_time_str}")
        
    def record_event(self, event_name, stage=None, additional_data=None):
        """
        记录事件数据（增强版）
        
        Args:
            event_name: 事件名称
            stage: 训练阶段（可选）
            additional_data: 额外数据（可选）
        """
        if not self.events_file_path:
            print("警告：未设置事件文件路径")
            return False
            
        try:
            # 获取当前时间和计算相对时间戳
            current_time = datetime.now()
            relative_timestamp = 0.0
            if self.acquisition_start_time:
                time_diff = current_time - self.acquisition_start_time
                relative_timestamp = time_diff.total_seconds()
            
            # 检查是否为重复事件（在3秒内的相同事件名称和阶段）
            if self._is_duplicate_event(event_name, stage, relative_timestamp):
                print(f"跳过重复事件: {event_name} (阶段: {stage})")
                return False
            
            # 准备详细的时间信息
            time_info = {
                'absolute_time': current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                'relative_timestamp': relative_timestamp,
                'acquisition_start': self.acquisition_start_time_str,
                'elapsed_minutes': relative_timestamp / 60.0
            }
            
            # 准备事件数据
            event_data = {
                'event_id': self.event_count + 1,
                'timestamp': relative_timestamp,
                'time_info': time_info,
                'event_name': event_name,
                'stage': stage or "",
                'raw_sensor_data': self.current_sensor_data or [],
                'processed_sensor_data': self.current_processed_data or self.current_sensor_data or []
            }
            
            # 添加额外数据
            if additional_data:
                event_data.update(additional_data)
            
            # 写入CSV文件
            success = self._write_to_csv(event_data)
            
            if success:
                self.event_count += 1
                # 保存到事件历史
                self.event_history.append(event_data)
                # 发送事件记录信号
                self.event_recorded.emit(event_name, event_data)
                print(f"\n=== 事件记录成功 ===")
                print(f"事件ID: {event_data['event_id']}")
                print(f"事件名称: {event_name}")
                print(f"阶段: {stage}")
                print(f"记录时间: {time_info['absolute_time']}")
                print(f"相对时间: {time_info['relative_timestamp']:.2f}秒")
                print(f"训练时长: {time_info['elapsed_minutes']:.2f}分钟")
                # print(f"传感器数据:")
                sensor_data = event_data.get('processed_sensor_data', event_data.get('raw_sensor_data', []))
                # for i, value in enumerate(sensor_data[:10], 1):  # 只显示前10个传感器
                #     print(f"  传感器{i}: {value:.2f}")
                if additional_data:
                    print("附加数据:")
                    for key, value in additional_data.items():
                        if isinstance(value, list):
                            print(f"  {key}: [{', '.join(f'{v:.3f}' for v in value[:3])}...]")
                        else:
                            print(f"  {key}: {value}")
                print("===================\n")
            
            return success
            
        except Exception as e:
            print(f"记录事件时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _is_duplicate_event(self, event_name, stage, current_timestamp, time_threshold=1.0):
        """
        检查是否为重复事件（改进版：更严格的重复检测）
        
        Args:
            event_name: 事件名称
            stage: 训练阶段
            current_timestamp: 当前时间戳
            time_threshold: 时间阈值（秒），调整为1秒以更好检测重复
        
        Returns:
            bool: 如果是重复事件返回True，否则返回False
        """
        try:
            # 检查最近的事件历史
            for event in reversed(self.event_history[-5:]):  # 只检查最近5个事件，减少检查范围
                # 检查事件名称和阶段是否相同
                if (event.get('event_name') == event_name and 
                    event.get('stage') == stage):
                    
                    # 检查时间间隔（更严格的检测）
                    time_diff = abs(current_timestamp - event.get('timestamp', 0))
                    if time_diff < time_threshold:
                        print(f"检测到重复事件: {event_name} (阶段: {stage}), 时间间隔: {time_diff:.3f}秒")
                        return True
            
            return False
            
        except Exception as e:
            print(f"检查重复事件时出错: {e}")
            return False
        
    def _write_to_csv(self, event_data):
        """写入CSV文件（支持误差范围）"""
        try:
            # 确保目录存在
            directory = os.path.dirname(self.events_file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # 检查文件是否存在
            file_exists = os.path.exists(self.events_file_path)
            
            # 对于新的采集周期，强制覆盖文件
            if self.is_new_acquisition:
                mode = 'w'  # 强制覆盖模式
                write_header = True
                print(f"新采集周期，{'覆盖' if file_exists else '创建'}事件文件: {self.events_file_path}")
            else:
                mode = 'a'  # 追加模式
                write_header = False
            
            with open(self.events_file_path, mode, newline='', encoding='utf-8') as csvfile:
                # 准备列名（与数据文件格式一致，新增误差范围列）
                fieldnames = ['time(s)', 'event_name', 'event_code', 'stage']
                
                # 为每个传感器添加一列
                # 添加传感器数据列（从1开始编号）
                for i in range(1, self.num_sensors + 1):
                    fieldnames.append(f'sensor{i}')
                
                # 添加权重列
                for i in range(1, self.num_sensors + 1):
                    fieldnames.append(f'weight{i}')
                
                # 新增：添加误差范围列
                fieldnames.append('error_range')
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # 写入表头（新文件或新采集周期）
                if write_header:
                    # 写入采集开始时间信息作为注释（与数据文件格式一致）
                    csvfile.write(f"# Acquisition Start Time: {self.acquisition_start_time_str}\n")
                    csvfile.write(f"# Event recording for acquisition session\n")
                    csvfile.write(f"# Data source: 事件数据\n")
                    csvfile.write(f"# Contains error_range for patient training\n")
                    csvfile.write("\n")  # 空行
                    writer.writeheader()
                    self.is_new_acquisition = False  # 标记已写入表头
                
                # 准备CSV行数据（与数据文件格式一致）
                csv_row = {
                    'time(s)': event_data['timestamp'],  # 不进行格式化，保持原始精度
                    'event_name': event_data['event_name'],
                    'event_code': event_data.get('event_code', ''),
                    'stage': event_data.get('stage', '')
                }
                
                # 添加传感器数据到单独的列
                # 优先使用处理后的数据，如果没有则使用原始数据
                sensor_data = event_data.get('processed_sensor_data', event_data.get('raw_sensor_data', []))
                
                # 写入传感器数据
                for i in range(1, self.num_sensors + 1):
                    idx = i - 1  # 数组索引从0开始
                    if idx < len(sensor_data):
                        csv_row[f'sensor{i}'] = sensor_data[idx]
                    else:
                        csv_row[f'sensor{i}'] = ""
                
                # 添加权重数据到单独的列
                weights = event_data.get('sensor_weights', [0] * self.num_sensors)
                for i in range(1, self.num_sensors + 1):
                    idx = i - 1  # 数组索引从0开始
                    csv_row[f'weight{i}'] = weights[idx] if idx < len(weights) else 0
                
                # 新增：添加误差范围数据
                csv_row['error_range'] = event_data.get('error_range', 0.1)  # 默认误差范围10%
                
                writer.writerow(csv_row)
                
            return True
            
        except Exception as e:
            print(f"写入事件CSV文件时发生错误: {e}")
            return False
            
    def get_events_count(self):
        """获取已记录的事件数量"""
        if not os.path.exists(self.events_file_path):
            return 0
            
        try:
            with open(self.events_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                # 跳过注释行和表头
                event_count = 0
                for row in reader:
                    if row and not row[0].startswith('#') and row[0] != 'time(s)':
                        event_count += 1
                return event_count
        except Exception as e:
            print(f"读取事件文件时发生错误: {e}")
            return 0
            
    def validate_events_file(self):
        """验证事件文件的有效性"""
        if not self.events_file_path:
            return False, "未设置事件文件路径"
            
        # 检查目录是否存在
        directory = os.path.dirname(self.events_file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                return False, f"无法创建目录: {e}"
                
        # 检查文件是否可写
        try:
            # 尝试打开文件进行写入测试
            with open(self.events_file_path, 'a', encoding='utf-8') as f:
                pass
            return True, "事件文件路径有效"
        except Exception as e:
            return False, f"文件不可写: {e}"
            
    def read_events_with_error_range(self):
        """
        读取事件文件，包含误差范围信息（新增方法）
        
        Returns:
            list: 事件数据列表，每个事件包含误差范围信息
        """
        if not os.path.exists(self.events_file_path):
            return []
            
        events = []
        try:
            with open(self.events_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 跳过注释行
                    if any(key.startswith('#') for key in row.keys()):
                        continue
                    events.append(row)
        except Exception as e:
            print(f"读取事件文件时出错: {e}")
        
        return events
        
    def get_stage_error_ranges(self):
        """
        从事件文件中获取各阶段的误差范围（新增方法）
        
        Returns:
            dict: {stage_number: error_range} 映射
        """
        events = self.read_events_with_error_range()
        stage_error_ranges = {}
        
        for event in events:
            stage = event.get('stage', '')
            error_range = event.get('error_range', '')
            
            # 提取阶段编号
            stage_num = None
            if '阶段1' in stage:
                stage_num = 1
            elif '阶段2' in stage:
                stage_num = 2
            elif '阶段3' in stage:
                stage_num = 3
            elif '阶段4' in stage:
                stage_num = 4
            
            if stage_num and error_range:
                try:
                    stage_error_ranges[stage_num] = float(error_range)
                except ValueError:
                    pass
        
        return stage_error_ranges

    def get_event_history(self):
        """获取事件历史记录"""
        return self.event_history

    def get_latest_event(self):
        """获取最近一次记录的事件"""
        return self.event_history[-1] if self.event_history else None

    def get_stage_events(self, stage):
        """获取指定阶段的所有事件"""
        return [event for event in self.event_history if event.get('stage') == stage]

    def get_event_summary(self):
        """获取事件记录摘要"""
        if not self.event_history:
            return "暂无事件记录"
            
        summary = []
        summary.append(f"总事件数: {self.event_count}")
        if self.acquisition_start_time:
            total_time = (datetime.now() - self.acquisition_start_time).total_seconds()
            summary.append(f"总训练时长: {total_time/60:.2f}分钟")
            
        # 按阶段统计
        stage_counts = {}
        for event in self.event_history:
            stage = event.get('stage', '未分类')
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
        summary.append("\n各阶段事件统计:")
        for stage, count in stage_counts.items():
            summary.append(f"  {stage}: {count}个事件")
            
        return "\n".join(summary)


    def get_current_sensor_data(self):
        return self.current_sensor_data
