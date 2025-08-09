# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
# """
# 事件记录器模块，专门处理事件数据的记录和保存
# """

# import csv
# import os
# from datetime import datetime
# from PyQt5.QtCore import QObject, pyqtSignal
# from PyQt5.QtWidgets import QMessageBox

# class EventRecorder(QObject):
#     """
#     事件记录器类
#     专门用于记录触发事件时的数据
#     """
    
#     # 信号定义
#     event_recorded = pyqtSignal(str, dict)  # 事件记录信号：事件名称，事件数据
    
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.events_file_path = ""
#         self.current_sensor_data = None
#         self.num_sensors = 7  # 恢复默认值为7
#         self.is_new_acquisition = True
#         self.acquisition_start_time = None  # 采集开始的绝对时间
#         self.acquisition_start_time_str = ""  # 采集开始时间的字符串表示
        
#     def set_events_file_path(self, file_path):
#         """设置事件文件保存路径"""
#         self.events_file_path = file_path
#         self.is_new_acquisition = True  # 新路径时标记为新采集
#         print(f"事件文件路径已设置: {file_path}")
        
#     def set_num_sensors(self, num_sensors):
#         """设置传感器数量"""
#         old_num = self.num_sensors
#         self.num_sensors = num_sensors
#         print(f"事件记录器传感器数量已设置为: {num_sensors} (原来是: {old_num})")
        
#         # 如果传感器数量发生变化且已经开始采集，标记需要重新创建文件头
#         if old_num != num_sensors and hasattr(self, 'acquisition_start_time') and self.acquisition_start_time:
#             print(f"传感器数量变化，下次记录事件时将更新文件格式")
        
#     def set_current_sensor_data(self, sensor_data):
#         """设置当前传感器数据"""
#         self.current_sensor_data = sensor_data
        
#     def start_new_acquisition(self):
#         """开始新的采集周期"""
#         self.is_new_acquisition = True
#         self.acquisition_start_time = datetime.now()
#         self.acquisition_start_time_str = self.acquisition_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
#         print(f"开始新的事件采集周期，开始时间: {self.acquisition_start_time_str}")
        
#     def record_event(self, event_name, stage=None, additional_data=None):
#         """
#         记录事件数据
        
#         Args:
#             event_name: 事件名称
#             stage: 训练阶段（可选）
#             additional_data: 额外数据（可选）
#         """
#         if not self.events_file_path:
#             print("警告：未设置事件文件路径")
#             return False
            
#         # 计算相对时间戳（与数据文件时间戳格式一致）
#         relative_timestamp = 0.0
#         if self.acquisition_start_time:
#             current_time = datetime.now()
#             time_diff = current_time - self.acquisition_start_time
#             relative_timestamp = time_diff.total_seconds()
        
#         # 准备事件数据
#         event_data = {
#             'timestamp': relative_timestamp,  # 使用相对时间戳，与数据文件一致
#             'event_name': event_name,
#             'stage': stage or "",
#             'sensor_data': self.current_sensor_data or []
#         }
        
#         # 添加额外数据
#         if additional_data:
#             event_data.update(additional_data)
        
#         # 写入CSV文件
#         success = self._write_to_csv(event_data)
        
#         if success:
#             # 发送事件记录信号
#             self.event_recorded.emit(event_name, event_data)
#             print(f"事件已记录: {event_name} - 相对时间: {relative_timestamp}s")
            
#         return success
        
#     def _write_to_csv(self, event_data):
#         """写入CSV文件"""
#         try:
#             # 检查文件是否存在
#             file_exists = os.path.exists(self.events_file_path)
            
#             # 对于新的采集周期，强制覆盖文件
#             if self.is_new_acquisition:
#                 mode = 'w'  # 强制覆盖模式
#                 write_header = True
#                 print(f"新采集周期，{'覆盖' if file_exists else '创建'}事件文件: {self.events_file_path}")
#             else:
#                 mode = 'a'  # 追加模式
#                 write_header = False
            
#             with open(self.events_file_path, mode, newline='', encoding='utf-8') as csvfile:
#                 # 准备列名（与数据文件格式一致）
#                 fieldnames = ['time(s)', 'event_name', 'stage']
                
#                 # 为每个传感器添加一列
#                 sensor_data = event_data.get('sensor_data', [])
#                 if sensor_data and len(sensor_data) > 1:  # 第一个是时间戳，后面是传感器数据
#                     for i in range(len(sensor_data) - 1):  # 减去时间戳
#                         fieldnames.append(f'sensor{i+1}')
#                 else:
#                     # 如果没有传感器数据，使用默认数量
#                     for i in range(self.num_sensors):
#                         fieldnames.append(f'sensor{i+1}')
                
#                 # 添加权重列
#                 for i in range(self.num_sensors):
#                     fieldnames.append(f'weight{i+1}')
                
#                 writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
#                 # 写入表头（新文件或新采集周期）
#                 if write_header:
#                     # 写入采集开始时间信息作为注释（与数据文件格式一致）
#                     csvfile.write(f"# Acquisition Start Time: {self.acquisition_start_time_str}\n")
#                     csvfile.write(f"# Event recording for acquisition session\n")
#                     csvfile.write(f"# Data source: 事件数据\n")
#                     csvfile.write("\n")  # 空行
#                     writer.writeheader()
#                     self.is_new_acquisition = False  # 标记已写入表头
                
#                 # 准备CSV行数据（与数据文件格式一致）
#                 csv_row = {
#                     'time(s)': event_data['timestamp'],  # 不进行格式化，保持原始精度
#                     'event_name': event_data['event_name'],
#                     'stage': event_data.get('stage', '')
#                 }
                
#                 # 添加传感器数据到单独的列
#                 if sensor_data and len(sensor_data) > 1:
#                     for i, value in enumerate(sensor_data[1:], 1):  # 从1开始，跳过时间戳
#                         if i <= self.num_sensors:
#                             csv_row[f'sensor{i}'] = value
#                 else:
#                     # 如果没有传感器数据，填充空值
#                     for i in range(1, self.num_sensors + 1):
#                         csv_row[f'sensor{i}'] = ""
                
#                 # 添加权重数据到单独的列
#                 weights = event_data.get('sensor_weights', [0] * self.num_sensors)
#                 for i in range(self.num_sensors):
#                     csv_row[f'weight{i+1}'] = weights[i] if i < len(weights) else 0
                
#                 writer.writerow(csv_row)
                
#             return True
            
#         except Exception as e:
#             print(f"写入事件CSV文件时发生错误: {e}")
#             return False
            
#     def get_events_count(self):
#         """获取已记录的事件数量"""
#         if not os.path.exists(self.events_file_path):
#             return 0
            
#         try:
#             with open(self.events_file_path, 'r', encoding='utf-8') as f:
#                 reader = csv.reader(f)
#                 # 跳过表头
#                 next(reader, None)
#                 return sum(1 for _ in reader)
#         except Exception as e:
#             print(f"读取事件文件时发生错误: {e}")
#             return 0
            
#     def validate_events_file(self):
#         """验证事件文件的有效性"""
#         if not self.events_file_path:
#             return False, "未设置事件文件路径"
            
#         # 检查目录是否存在
#         directory = os.path.dirname(self.events_file_path)
#         if directory and not os.path.exists(directory):
#             try:
#                 os.makedirs(directory)
#             except Exception as e:
#                 return False, f"无法创建目录: {e}"
                
#         # 检查文件是否可写
#         try:
#             # 尝试打开文件进行写入测试
#             with open(self.events_file_path, 'a', encoding='utf-8') as f:
#                 pass
#             return True, "事件文件路径有效"
#         except Exception as e:
#             return False, f"文件不可写: {e}"




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
        self.num_sensors = 7  # 恢复默认值为7
        self.is_new_acquisition = True
        self.acquisition_start_time = None  # 采集开始的绝对时间
        self.acquisition_start_time_str = ""  # 采集开始时间的字符串表示
        
    def set_events_file_path(self, file_path):
        """设置事件文件保存路径"""
        self.events_file_path = file_path
        self.is_new_acquisition = True  # 新路径时标记为新采集
        print(f"事件文件路径已设置: {file_path}")
        
    def set_num_sensors(self, num_sensors):
        """设置传感器数量"""
        old_num = self.num_sensors
        self.num_sensors = num_sensors
        print(f"事件记录器传感器数量已设置为: {num_sensors} (原来是: {old_num})")
        
        # 如果传感器数量发生变化且已经开始采集，标记需要重新创建文件头
        if old_num != num_sensors and hasattr(self, 'acquisition_start_time') and self.acquisition_start_time:
            print(f"传感器数量变化，下次记录事件时将更新文件格式")
        
    def set_current_sensor_data(self, sensor_data):
        """设置当前传感器数据"""
        self.current_sensor_data = sensor_data
        
    def start_new_acquisition(self):
        """开始新的采集周期"""
        self.is_new_acquisition = True
        self.acquisition_start_time = datetime.now()
        self.acquisition_start_time_str = self.acquisition_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"开始新的事件采集周期，开始时间: {self.acquisition_start_time_str}")
        
    def record_event(self, event_name, stage=None, additional_data=None):
        """
        记录事件数据（支持误差范围）
        
        Args:
            event_name: 事件名称
            stage: 训练阶段（可选）
            additional_data: 额外数据（可选，现在可以包含error_range）
        """
        if not self.events_file_path:
            print("警告：未设置事件文件路径")
            return False
            
        # 计算相对时间戳（与数据文件时间戳格式一致）
        relative_timestamp = 0.0
        if self.acquisition_start_time:
            current_time = datetime.now()
            time_diff = current_time - self.acquisition_start_time
            relative_timestamp = time_diff.total_seconds()
        
        # 准备事件数据
        event_data = {
            'timestamp': relative_timestamp,  # 使用相对时间戳，与数据文件一致
            'event_name': event_name,
            'stage': stage or "",
            'sensor_data': self.current_sensor_data or []
        }
        
        # 添加额外数据
        if additional_data:
            event_data.update(additional_data)
        
        # 写入CSV文件
        success = self._write_to_csv(event_data)
        
        if success:
            # 发送事件记录信号
            self.event_recorded.emit(event_name, event_data)
            error_range = additional_data.get('error_range', 'N/A') if additional_data else 'N/A'
            print(f"事件已记录: {event_name} - 相对时间: {relative_timestamp}s, 误差范围: {error_range}")
            
        return success
        
    def _write_to_csv(self, event_data):
        """写入CSV文件（支持误差范围）"""
        try:
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
                fieldnames = ['time(s)', 'event_name', 'stage']
                
                # 为每个传感器添加一列
                sensor_data = event_data.get('sensor_data', [])
                if sensor_data and len(sensor_data) > 1:  # 第一个是时间戳，后面是传感器数据
                    for i in range(len(sensor_data) - 1):  # 减去时间戳
                        fieldnames.append(f'sensor{i+1}')
                else:
                    # 如果没有传感器数据，使用默认数量
                    for i in range(self.num_sensors):
                        fieldnames.append(f'sensor{i+1}')
                
                # 添加权重列
                for i in range(self.num_sensors):
                    fieldnames.append(f'weight{i+1}')
                
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
                    'stage': event_data.get('stage', '')
                }
                
                # 添加传感器数据到单独的列
                if sensor_data and len(sensor_data) > 1:
                    for i, value in enumerate(sensor_data[1:], 1):  # 从1开始，跳过时间戳
                        if i <= self.num_sensors:
                            csv_row[f'sensor{i}'] = value
                else:
                    # 如果没有传感器数据，填充空值
                    for i in range(1, self.num_sensors + 1):
                        csv_row[f'sensor{i}'] = ""
                
                # 添加权重数据到单独的列
                weights = event_data.get('sensor_weights', [0] * self.num_sensors)
                for i in range(self.num_sensors):
                    csv_row[f'weight{i+1}'] = weights[i] if i < len(weights) else 0
                
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
            
            if stage_num and error_range:
                try:
                    stage_error_ranges[stage_num] = float(error_range)
                except ValueError:
                    pass
        
        return stage_error_ranges