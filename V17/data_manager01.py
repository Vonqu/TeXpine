#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据管理模块，处理数据保存和加载

核心思路：
1. 内存中只保留用于实时显示的数据（控制内存使用）
2. 所有原始数据实时写入临时文件（确保数据完整性）
3. 保存时从临时文件读取完整数据（保证数据不丢失）
4. 提供多种保存策略（内存+文件、仅文件等）

优势：
- 内存使用可控
- 数据完整性保证
- 支持超大数据量
- 系统崩溃也不会丢失数据
"""

import os
import csv
import tempfile
import numpy as np
from collections import deque
from PyQt5.QtWidgets import QMessageBox
import datetime
import threading


class DataManager:
    """数据管理类，负责保存和加载数据
        ====================================================
    
    双重存储策略：
    1. 内存缓存：用于实时显示，数量有限
    2. 临时文件：存储所有原始数据，保证完整性
    """
    
    def __init__(self):
        # ====== 原有属性（保持兼容） ======
        self.data = []  # 保留原有属性名，但改为内存显示数据
        self.save_path = ""
        
        # ====== 新增优化属性 ======
        self.display_data = deque(maxlen=5000)  # 实际的内存显示数据
        self.temp_file_path = None  # 临时文件路径
        self.temp_file_handle = None  # 临时文件句柄
        self.temp_writer = None  # CSV写入器
        self.data_count = 0  # 数据点计数
        self.file_lock = threading.Lock()  # 文件操作锁
        
        # ====== 配置参数 ======
        self.enable_temp_file = True  # 是否启用临时文件存储
        self.memory_limit = 5000  # 内存中保留的数据点数
        self.auto_backup_interval = 1000  # 自动备份间隔
        
        # 初始化临时文件
        self.init_temp_file()

            
    def init_temp_file(self):
        """
        初始化临时文件
        ==============
        
        创建临时文件用于存储所有原始数据，确保数据不丢失
        """
        if not self.enable_temp_file:
            return
            
        try:
            # 创建临时目录
            temp_dir = os.path.join(tempfile.gettempdir(), "sensor_data_temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            # 创建临时文件
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_file_path = os.path.join(temp_dir, f"sensor_data_{timestamp}.csv")
            
            # 打开文件准备写入
            self.temp_file_handle = open(self.temp_file_path, 'w', newline='', encoding='utf-8')
            self.temp_writer = csv.writer(self.temp_file_handle)
            
            print(f"临时数据文件已创建: {self.temp_file_path}")
            
        except Exception as e:
            print(f"创建临时文件失败: {e}")
            self.enable_temp_file = False
        
    def clear_data(self):
        """清空数据 - 保持原有接口"""
        self.display_data.clear()
        self.data = []  # 保持兼容性
        
        # 重新初始化临时文件
        self.cleanup_temp_file()
        self.init_temp_file()
        self.data_count = 0    
         
    def add_data_point(self, values):
        """
        添加数据点 - 双重存储策略
        ==========================
        
        Args:
            values: 数据值列表，包含时间戳和传感器数据
        """
        # 1. 添加到内存缓存（用于实时显示）
        self.display_data.append(values)
        
        # 2. 写入临时文件（保证数据完整性）
        if self.enable_temp_file and self.temp_writer:
            with self.file_lock:
                try:
                    self.temp_writer.writerow(values)
                    self.data_count += 1
                    
                    # 定期刷新文件缓冲区
                    if self.data_count % 100 == 0:
                        self.temp_file_handle.flush()
                    
                    # 定期自动备份
                    if self.data_count % self.auto_backup_interval == 0:
                        self.auto_backup()
                        
                except Exception as e:
                    print(f"写入临时文件失败: {e}")
    
    def get_complete_data(self):
        """
        获取完整数据（新增方法）
        =======================
        
        Returns:
            list: 从临时文件读取的完整数据
        """
        if not self.enable_temp_file or not self.temp_file_path:
            return self.data
        
        complete_data = []
        
        try:
            # 刷新当前写入缓冲区
            if self.temp_file_handle:
                self.temp_file_handle.flush()
            
            # 读取临时文件
            with open(self.temp_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    try:
                        # 转换为浮点数
                        data_row = [float(val) for val in row]
                        complete_data.append(data_row)
                    except ValueError:
                        # 跳过无效行
                        continue
            
            print(f"从临时文件读取了 {len(complete_data)} 个数据点")
            return complete_data
            
        except Exception as e:
            print(f"读取临时文件失败: {e}")
            # 降级到显示数据
            return self.data
    
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化版数据管理模块 - 完全兼容现有接口
===================================

保持所有原有方法和接口不变，只在内部添加性能优化
"""

import os
import csv
import tempfile
import numpy as np
from collections import deque
from PyQt5.QtWidgets import QMessageBox
import datetime
import threading

class DataManager:
    """
    优化版数据管理类 - 兼容原有接口
    ===============================
    
    新增功能：
    - 双重存储策略（内存+临时文件）
    - 自动数据清理
    - 完整数据保存
    
    保持兼容：
    - 所有原有方法都保留
    - 接口调用方式不变
    - 外部代码无需修改
    """
    
    def __init__(self):
        # ====== 原有属性（保持兼容） ======
        self.data = []  # 保留原有属性名，但改为内存显示数据
        self.save_path = ""
        
        # ====== 新增优化属性 ======
        self.display_data = deque(maxlen=5000)  # 实际的内存显示数据
        self.temp_file_path = None  # 临时文件路径
        self.temp_file_handle = None  # 临时文件句柄
        self.temp_writer = None  # CSV写入器
        self.data_count = 0  # 数据点计数
        self.file_lock = threading.Lock()  # 文件操作锁
        
        # ====== 配置参数 ======
        self.enable_temp_file = True  # 是否启用临时文件存储
        self.memory_limit = 5000  # 内存中保留的数据点数
        self.auto_backup_interval = 1000  # 自动备份间隔
        
        # 初始化临时文件
        self.init_temp_file()
        
    def init_temp_file(self):
        """初始化临时文件"""
        if not self.enable_temp_file:
            return
            
        try:
            # 创建临时目录
            temp_dir = os.path.join(tempfile.gettempdir(), "sensor_data_temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            # 创建临时文件
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_file_path = os.path.join(temp_dir, f"sensor_data_{timestamp}.csv")
            
            # 打开文件准备写入
            self.temp_file_handle = open(self.temp_file_path, 'w', newline='', encoding='utf-8')
            self.temp_writer = csv.writer(self.temp_file_handle)
            
            print(f"临时数据文件已创建: {self.temp_file_path}")
            
        except Exception as e:
            print(f"创建临时文件失败: {e}")
            self.enable_temp_file = False
    
    def clear_data(self):
        """清空数据 - 保持原有接口"""
        self.display_data.clear()
        self.data = []  # 保持兼容性
        
        # 重新初始化临时文件
        self.cleanup_temp_file()
        self.init_temp_file()
        self.data_count = 0
        
    def add_data_point(self, values):
        """
        添加一个数据点 - 保持原有接口，内部优化
        =======================================
        
        Args:
            values: 数据值列表，包含时间戳和传感器数据
        """
        # 添加到显示数据（有限制的内存缓存）
        self.display_data.append(values)
        
        # 保持原有接口兼容性（self.data 指向显示数据）
        # 注意：这里我们让 self.data 始终反映最新的显示数据
        self.data = list(self.display_data)
        
        # 写入临时文件（完整数据保存）
        if self.enable_temp_file and self.temp_writer:
            with self.file_lock:
                try:
                    self.temp_writer.writerow(values)
                    self.data_count += 1
                    
                    # 定期刷新文件缓冲区
                    if self.data_count % 100 == 0:
                        self.temp_file_handle.flush()
                    
                    # 定期自动备份
                    if self.data_count % self.auto_backup_interval == 0:
                        self.auto_backup()
                        
                except Exception as e:
                    print(f"写入临时文件失败: {e}")
        
    def get_data(self):
        """
        获取所有数据 - 保持原有接口
        ===========================
        
        Returns:
            list: 所有数据点的列表
        """
        # 为了保持兼容性，这里返回显示数据
        # 如果需要完整数据，请使用 get_complete_data()
        return self.data
    
    def get_complete_data(self):
        """
        获取完整数据（新增方法）
        =======================
        
        Returns:
            list: 从临时文件读取的完整数据
        """
        if not self.enable_temp_file or not self.temp_file_path:
            return self.data
        
        complete_data = []
        
        try:
            # 刷新当前写入缓冲区
            if self.temp_file_handle:
                self.temp_file_handle.flush()
            
            # 读取临时文件
            with open(self.temp_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    try:
                        # 转换为浮点数
                        data_row = [float(val) for val in row]
                        complete_data.append(data_row)
                    except ValueError:
                        # 跳过无效行
                        continue
            
            print(f"从临时文件读取了 {len(complete_data)} 个数据点")
            return complete_data
            
        except Exception as e:
            print(f"读取临时文件失败: {e}")
            # 降级到显示数据
            return self.data
        
    def set_save_path(self, path):
        """
        设置保存路径 - 保持原有接口
        ===========================
        
        Args:
            path: 数据保存路径
        """
        self.save_path = path
        
    def get_save_path(self):
        """
        获取保存路径 - 保持原有接口
        ===========================
        
        Returns:
            str: 保存路径
        """
        return self.save_path
        
    def get_display_data(self):
        """
        获取用于显示的数据
        ==================
        
        Returns:
            list: 内存中的显示数据
        """
        return list(self.display_data)
    
        
    def get_complete_data_from_file(self):
        """
        从临时文件读取完整数据
        ======================
        
        Returns:
            list: 完整的原始数据
        """
        if not self.enable_temp_file or not self.temp_file_path:
            return list(self.display_data)
        
        complete_data = []
        
        try:
            # 刷新当前写入缓冲区
            if self.temp_file_handle:
                self.temp_file_handle.flush()
            
            # 读取临时文件
            with open(self.temp_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    try:
                        # 转换为浮点数
                        data_row = [float(val) for val in row]
                        complete_data.append(data_row)
                    except ValueError:
                        # 跳过无效行
                        continue
            
            print(f"从临时文件读取了 {len(complete_data)} 个数据点")
            return complete_data
            
        except Exception as e:
            print(f"读取临时文件失败: {e}")
            # 降级到内存数据
            return list(self.display_data)
        
        
    def start_acquisition(self):
        """开始新的数据采集会话"""
        # 清空内存数据
        self.display_data.clear()
        
        # 重新初始化临时文件
        self.cleanup_temp_file()
        self.init_temp_file()
        
        # 记录开始时间
        self.acquisition_start_time = datetime.datetime.now()
        self.acquisition_start_time_str = self.acquisition_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        self.data_count = 0
        
        print("数据采集开始，临时文件已重置")


    def clear_data(self):
        """清空数据"""
        self.data = []
        
        
    def save_data(self, parent_widget=None, num_sensors=None, sensor_names=None):
        """
        保存数据到CSV文件 - 支持完整数据保存
        ===================================
        
        Args:
            parent_widget: 父部件，用于显示消息框
            num_sensors: 传感器数量
            sensor_names: 传感器名称列表
            
        Returns:
            bool: 是否成功保存
        """
        if not self.save_path:
            if parent_widget:
                QMessageBox.warning(parent_widget, "错误", "未指定保存路径")
            return False
        
        # 获取完整数据
        complete_data = self.get_complete_data_from_file()
        
        if not complete_data:
            if parent_widget:
                QMessageBox.information(parent_widget, "提示", "没有数据可保存")
            return False
        
        try:
            # 推断传感器数量
            if num_sensors is None and complete_data:
                num_sensors = len(complete_data[0]) - 1
            
            with open(self.save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入元数据
                if hasattr(self, 'acquisition_start_time_str'):
                    writer.writerow(["# start time: " + self.acquisition_start_time_str])
                    writer.writerow(["# total data points: " + str(len(complete_data))])
                    writer.writerow([])
                
                # 写入标题行
                header = ["time(s)"]
                for i in range(num_sensors):
                    if sensor_names and i < len(sensor_names):
                        header.append(sensor_names[i])
                    else:
                        header.append(f"sensor{i+1}")
                writer.writerow(header)
                
                # 写入所有数据
                for row in complete_data:
                    writer.writerow(row)
            
            if parent_widget:
                QMessageBox.information(
                    parent_widget, "成功", 
                    f"数据已保存至：\n{self.save_path}\n"
                    f"共保存 {len(complete_data)} 个数据点"
                )
            
            print(f"数据保存成功: {len(complete_data)} 个数据点 -> {self.save_path}")
            return True
            
        except Exception as e:
            if parent_widget:
                QMessageBox.critical(parent_widget, "错误", f"保存数据时发生错误：\n{str(e)}")
            print(f"保存数据失败: {e}")
            return False
        
    def auto_backup(self):
        """
        自动备份机制
        ============
        
        定期创建数据备份，防止数据丢失
        """
        if not self.enable_temp_file or not self.temp_file_path:
            return
        
        try:
            backup_dir = os.path.join(os.path.dirname(self.temp_file_path), "backups")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            backup_path = os.path.join(backup_dir, f"backup_{timestamp}.csv")
            
            # 刷新当前文件
            if self.temp_file_handle:
                self.temp_file_handle.flush()
            
            # 复制文件
            import shutil
            shutil.copy2(self.temp_file_path, backup_path)
            
            print(f"自动备份完成: {backup_path} ({self.data_count} 个数据点)")
            
        except Exception as e:
            print(f"自动备份失败: {e}")

        
    def cleanup_temp_file(self):
        """
        清理临时文件
        ============
        """
        try:
            if self.temp_file_handle:
                self.temp_file_handle.close()
                self.temp_file_handle = None
                self.temp_writer = None
            
            if self.temp_file_path and os.path.exists(self.temp_file_path):
                os.remove(self.temp_file_path)
                print(f"临时文件已清理: {self.temp_file_path}")
                
        except Exception as e:
            print(f"清理临时文件失败: {e}")
    
    def get_data_stats(self):
        """
        获取数据统计信息
        ================
        
        Returns:
            dict: 数据统计信息
        """
        return {
            'memory_data_count': len(self.display_data),
            'total_data_count': self.data_count,
            'temp_file_enabled': self.enable_temp_file,
            'temp_file_path': self.temp_file_path,
            'memory_limit': self.memory_limit
        }
    
    def set_memory_limit(self, limit):
        """
        设置内存数据限制
        ================
        
        Args:
            limit: 内存中保留的最大数据点数
        """
        self.memory_limit = limit
        # 重新创建deque以应用新限制
        current_data = list(self.display_data)
        self.display_data = deque(current_data[-limit:], maxlen=limit)
        print(f"内存限制已更新为: {limit} 个数据点")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        self.cleanup_temp_file()

    def get_save_path(self):
        """获取保存路径
        
        Returns:
            str: 保存路径
        """
        return self.save_path
    
    def start_acquisition(self):
        """开始新的数据采集会话，记录开始时间"""
        self.clear_data()
        # 记录绝对开始时间
        self.acquisition_start_time = datetime.datetime.now()
        self.acquisition_start_time_str = self.acquisition_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    
        
    def save_data(self, parent_widget=None, num_sensors=None, sensor_names=None):
        """保存数据到CSV文件
        
        Args:
            parent_widget: 父部件，用于显示消息框
            num_sensors: 传感器数量，如果为None则从数据推断
            sensor_names: 传感器名称列表，如果为None则使用默认名称
            
        Returns:
            bool: 是否成功保存
        """
        if not self.data:
            if parent_widget:
                QMessageBox.information(parent_widget, "提示", "没有数据可保存")
            return False
            
        if not self.save_path:
            if parent_widget:
                QMessageBox.warning(parent_widget, "错误", "未指定保存路径")
            return False
            
        try:
            # 如果未指定传感器数量，从数据推断
            if num_sensors is None and self.data:
                # 第一列是时间戳，所以传感器数量是总列数减1
                num_sensors = len(self.data[0]) - 1
                
            with open(self.save_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # 写入采集开始时间信息（作为注释）
                if hasattr(self, 'acquisition_start_time_str'):
                    writer.writerow(["# start time: " + self.acquisition_start_time_str])
                    writer.writerow([])  # 空行
                
                # 写入标题行
                header = ["time(s)"]
                for i in range(num_sensors):
                    if sensor_names and i < len(sensor_names):
                        header.append(sensor_names[i])
                    else:
                        header.append(f"sensor{i+1}")
                writer.writerow(header)
                
                # 写入数据
                for row in self.data:
                    writer.writerow(row)
                    
            if parent_widget:
                QMessageBox.information(parent_widget, "成功", f"数据已保存至：\n{self.save_path}")
            return True
            
        except Exception as e:
            if parent_widget:
                QMessageBox.critical(parent_widget, "错误", f"保存数据时发生错误：\n{str(e)}")
            return False
            
    def load_data(self, file_path=None, parent_widget=None):
        """从CSV文件加载数据
        
        Args:
            file_path: 文件路径，如果为None则使用当前保存路径
            parent_widget: 父部件，用于显示消息框
            
        Returns:
            tuple: (是否成功, 数据数组, 传感器名称列表)
        """
        path = file_path if file_path else self.save_path
        
        if not path or not os.path.exists(path):
            if parent_widget:
                QMessageBox.warning(parent_widget, "错误", "文件不存在")
            return False, [], []
            
        try:
            with open(path, 'r', newline='') as f:
                reader = csv.reader(f)
                
                # 读取标题行
                header = next(reader)
                sensor_names = header[1:]  # 第一列是时间，剩下的是传感器名称
                
                # 读取数据行
                data = []
                for row in reader:
                    # 转换为浮点数
                    try:
                        data.append([float(val) for val in row])
                    except ValueError:
                        # 忽略无法转换的行
                        continue
                        
            self.data = data
            self.save_path = path
            
            if parent_widget:
                QMessageBox.information(parent_widget, "成功", f"已加载数据，共{len(data)}行")
                
            return True, data, sensor_names
            
        except Exception as e:
            if parent_widget:
                QMessageBox.critical(parent_widget, "错误", f"加载数据时发生错误：\n{str(e)}")
            return False, [], []