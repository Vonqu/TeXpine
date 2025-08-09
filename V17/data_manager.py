"""
数据管理模块（内存优化版），处理数据保存和加载

核心优化思路：
1. 内存中只保留用于实时显示的数据（固定窗口大小，防止内存无限增长）
2. 所有原始数据实时写入临时文件（确保数据完整性）
3. 绘图使用固定大小的滚动窗口（例如最近5000个点）
4. 自动清理过期数据，防止内存泄漏
5. 分层数据管理：显示层、缓存层、存储层
6. 支持患者端模式的扩展数据格式

优势：
- 内存使用可控且固定
- 绘图性能稳定，不随数据量增长而变慢
- 数据完整性保证
- 支持超大数据量（GB级别）
- 系统崩溃也不会丢失数据
- 患者端模式支持0-1映射值输出
"""

import os
import csv
import tempfile
import numpy as np
from collections import deque
from PyQt5.QtWidgets import QMessageBox
import datetime
import threading
import gc  # 垃圾回收


class DataManager:
    """
    内存优化版数据管理类
    ===================
    
    三层数据管理：
    1. 显示层：固定大小的deque，用于实时绘图（5000点）
    2. 缓存层：中等大小的缓存，用于快速访问（50000点）
    3. 存储层：临时文件，存储所有数据
    4. 患者端支持：自动添加0-1映射值列
    """
    
    def __init__(self):
        # ====== 原有属性（保持兼容） ======
        self.data = []  # 保留原有属性名，但改为内存显示数据
        self.save_path = ""
        
        # ====== 新增优化属性 ======
        self.display_data = deque(maxlen=5000)  # 实际的内存显示数据
        self.cache_data = deque(maxlen=50000)   # 【新增】缓存数据（更大的历史窗口）
        self.temp_file_path = None  # 临时文件路径
        self.temp_file_handle = None  # 临时文件句柄
        self.temp_writer = None  # CSV写入器
        self.data_count = 0  # 数据点计数
        self.total_data_points = 0  # 【新增】总数据点计数
        self.file_lock = threading.Lock()  # 文件操作锁
        self.data_lock = threading.Lock()  # 数据操作锁
        
        # ====== 【新增】原始数据存储 ======
        self.raw_data = deque(maxlen=5000)  # 原始数据存储（滤波前）
        self.raw_temp_file_path = None  # 原始数据临时文件路径
        self.raw_temp_file_handle = None  # 原始数据临时文件句柄
        self.raw_temp_writer = None  # 原始数据CSV写入器
        self.raw_data_count = 0  # 原始数据点计数
        
        # ====== 新增：处理后数据缓存 ======
        self.processed_data = deque(maxlen=5000)  # 处理后数据缓存
        self.processed_temp_file_path = None  # 处理后数据临时文件路径
        self.processed_temp_file_handle = None  # 处理后数据临时文件句柄
        self.processed_temp_writer = None  # 处理后数据CSV写入器
        self.processed_data_count = 0  # 处理后数据计数
        
        # ====== 配置参数 ======
        self.enable_temp_file = True  # 是否启用临时文件存储
        self.memory_limit = 5000  # 内存中保留的数据点数
        self.cache_window_size = 50000  # 【新增】缓存窗口大小
        self.display_window_size = 5000  # 【新增】显示窗口大小
        self.auto_backup_interval = 1000  # 自动备份间隔
        self.last_cleanup_count = 0  # 【新增】上次清理计数
        
        # ====== 患者端模式相关属性 ======
        self.is_patient_mode = False
        self.patient_mapping_data = None  # 存储映射数据的引用
        
        # 初始化临时文件
        self.init_temp_file()
        self.init_raw_temp_file()
        self.init_processed_temp_file() # 初始化处理后数据临时文件
        
    def init_temp_file(self):
        """初始化临时文件存储"""
        try:
            # 创建临时目录
            temp_dir = os.path.join(tempfile.gettempdir(), "sensor_data_optimized")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            # 创建临时文件
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_file_path = os.path.join(temp_dir, f"sensor_data_{timestamp}.csv")
            
            # 打开文件准备写入
            self.temp_file_handle = open(self.temp_file_path, 'w', newline='', encoding='utf-8')
            self.temp_writer = csv.writer(self.temp_file_handle)
            
            print(f"✓ 临时数据文件已创建: {self.temp_file_path}")
            
        except Exception as e:
            print(f"✗ 创建临时文件失败: {e}")
    
    def init_raw_temp_file(self):
        """初始化原始数据临时文件存储"""
        try:
            # 创建临时目录
            temp_dir = os.path.join(tempfile.gettempdir(), "sensor_data_optimized")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            # 创建原始数据临时文件
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.raw_temp_file_path = os.path.join(temp_dir, f"raw_sensor_data_{timestamp}.csv")
            
            # 打开文件准备写入
            self.raw_temp_file_handle = open(self.raw_temp_file_path, 'w', newline='', encoding='utf-8')
            self.raw_temp_writer = csv.writer(self.raw_temp_file_handle)
            
            print(f"✓ 原始数据临时文件已创建: {self.raw_temp_file_path}")
            
        except Exception as e:
            print(f"✗ 创建原始数据临时文件失败: {e}")
            
    def init_processed_temp_file(self):
        """
        初始化处理后数据临时文件存储
        """
        try:
            temp_dir = os.path.join(tempfile.gettempdir(), "sensor_data_optimized")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.processed_temp_file_path = os.path.join(temp_dir, f"processed_sensor_data_{timestamp}.csv")
            self.processed_temp_file_handle = open(self.processed_temp_file_path, 'w', newline='', encoding='utf-8')
            self.processed_temp_writer = csv.writer(self.processed_temp_file_handle)
            print(f"✓ 处理后数据临时文件已创建: {self.processed_temp_file_path}")
        except Exception as e:
            print(f"✗ 创建处理后数据临时文件失败: {e}")
    
    def init_performance_monitoring(self):
        """初始化性能监控"""
        self.performance_stats['start_time'] = datetime.datetime.now()
        print("✓ 性能监控已启动")
        
    def clear_data(self):
        """清空所有数据"""
        with self.data_lock:
            self.display_data.clear()
            self.cache_data.clear()
            self.data = []  # 保持兼容性
            # 【新增】清空原始数据
            self.raw_data.clear()
            # 新增：清空处理后数据
            self.processed_data.clear()
        
        # 重新初始化临时文件
        self.cleanup_temp_file()
        self.init_temp_file()
        
        # 【新增】重新初始化原始数据临时文件
        self.cleanup_raw_temp_file()
        self.init_raw_temp_file()
        
        # 重置计数器
        self.data_count = 0
        self.total_data_points = 0
        self.last_cleanup_count = 0
        # 【新增】重置原始数据计数器
        self.raw_data_count = 0
        # 新增：重置处理后数据计数器
        self.processed_data_count = 0
        
        # 强制垃圾回收
        gc.collect()
        
        print("✓ 所有数据已清空，内存已释放")
        
    def add_data_point(self, values):
        """
        添加一个数据点（支持患者端扩展格式）
        =============
        
        Args:
            values: 数据值列表 [timestamp, sensor1, sensor2, ..., sensorN]
        """
        try:
            # 如果是患者端模式且有映射数据，需要计算并添加映射值
            if getattr(self, 'is_patient_mode', False) and hasattr(self, 'patient_mapping_data'):
                extended_values = self._create_extended_data_point(values)
            else:
                extended_values = values
            
            with self.data_lock:
                # 添加到显示缓存
                self.display_data.append(extended_values)
                
                # 保持兼容性：data属性指向显示数据
                if getattr(self, 'is_patient_mode', False) and len(extended_values) > len(values):
                    # 患者端模式：只显示原始数据部分给绘图组件
                    self.data = [row[:len(values)] for row in list(self.display_data)]
                else:
                    self.data = list(self.display_data)
                
                # 更新数据计数
                self.data_count += 1
                
                # 写入临时文件
                if self.enable_temp_file and self.temp_writer:
                    with self.file_lock:
                        self.temp_writer.writerow(extended_values)
                        self.temp_file_handle.flush()
                        
                # 自动备份检查
                if self.data_count % self.auto_backup_interval == 0:
                    self._backup_temp_file()
                    
        except Exception as e:
            print(f"添加数据点时出错: {e}")
            import traceback
            traceback.print_exc()

    def add_raw_data_point(self, values):
        """
        添加一个原始数据点（滤波前的数据）
        =============
        
        Args:
            values: 原始数据值列表 [RAW, timestamp, sensor1, sensor2, ..., sensorN]
        """
        try:
            with self.data_lock:
                # 添加到原始数据缓存
                self.raw_data.append(values)
                
                # 更新原始数据计数
                self.raw_data_count += 1
                
                # 写入原始数据临时文件
                if self.enable_temp_file and self.raw_temp_writer:
                    with self.file_lock:
                        self.raw_temp_writer.writerow(values)
                        self.raw_temp_file_handle.flush()
                        
        except Exception as e:
            print(f"添加原始数据点时出错: {e}")
            import traceback
            traceback.print_exc()

    def add_processed_data_point(self, values):
        """
        添加一个处理后数据点（滤波+增强+二次滤波后）
        =============
        Args:
            values: 处理后数据值列表 [PROCESSED, timestamp, sensor1, sensor2, ..., sensorN]
        """
        try:
            with self.data_lock:
                self.processed_data.append(values)
                self.processed_data_count += 1
                if self.enable_temp_file and self.processed_temp_writer:
                    with self.file_lock:
                        self.processed_temp_writer.writerow(values)
                        self.processed_temp_file_handle.flush()
        except Exception as e:
            print(f"添加处理后数据点时出错: {e}")
            import traceback
            traceback.print_exc()

    def _create_extended_data_point(self, values):
        """为患者端模式创建包含映射值的扩展数据点"""
        if not self.patient_mapping_data or not values or len(values) < 2:
            return values
        
        try:
            # 提取传感器数据（跳过时间戳）
            sensor_data = values[1:]
            
            # 计算映射值
            mapped_values = self._calculate_mapping_values(sensor_data)
            
            # 构造扩展数据：[时间戳, 原始传感器1-N, 映射传感器1-N]
            extended_values = [values[0]]  # 时间戳
            extended_values.extend(sensor_data)  # 原始传感器数据
            extended_values.extend(mapped_values)  # 映射传感器数据
            
            return extended_values
            
        except Exception as e:
            print(f"创建扩展数据点失败: {e}")
            return values
    
    def _calculate_mapping_values(self, sensor_data):
        """计算传感器数据的0-1映射值"""
        if not self.patient_mapping_data or not self.patient_mapping_data.get('loaded', False):
            return [0.5] * len(sensor_data)
        
        # 获取当前阶段
        current_stage = self.patient_mapping_data.get('current_stage', 1)
        
        # 获取该阶段的原始值和目标值
        original_values = self.patient_mapping_data.get('original_values', {}).get(current_stage, [])
        target_values = self.patient_mapping_data.get('target_values', {}).get(current_stage, [])

        if not original_values or not target_values:
            # 如果当前阶段没有数据，尝试使用阶段1的数据作为默认
            if current_stage != 1:
                original_values = self.patient_mapping_data.get('original_values', {}).get(1, [])
                target_values = self.patient_mapping_data.get('target_values', {}).get(1, [])
            
            if not original_values or not target_values:
                print(f"阶段{current_stage}的映射数据不完整，使用默认值0.5")
                return [0.5] * len(sensor_data)
        
        mapped_values = []
        for i, sensor_val in enumerate(sensor_data):
            if i < len(original_values) and i < len(target_values):
                original_val = original_values[i]  # 原始值 -> 映射为1
                target_val = target_values[i]      # 最佳值 -> 映射为0
                
                # 计算0-1映射（原始值=1，最佳值=0）
                if abs(original_val - target_val) > 1e-6:  # 避免除零
                    # 计算比例：(sensor_val - target_val) / (original_val - target_val)
                    # 当sensor_val = original_val时，结果为1
                    # 当sensor_val = target_val时，结果为0
                    mapped_val = (sensor_val - target_val) / (original_val - target_val)
                    
                    # 限制在0-1范围内（超出范围直接算作0或1）
                    if mapped_val > 1.0:
                        mapped_val = 1.0
                    elif mapped_val < 0.0:
                        mapped_val = 0.0
                else:
                    mapped_val = 0.5  # 原始值等于最佳值的情况
                
                mapped_values.append(mapped_val)
            else:
                mapped_values.append(0.5)  # 默认值
        
        return mapped_values
            
    def get_display_data(self):
        """
        获取用于显示的数据（固定窗口大小）
        ===============================
        
        Returns:
            list: 用于显示的数据列表（最多5000个点）
        """
        with self.data_lock:
            display_data = list(self.display_data)
            return display_data
    
    def get_recent_data(self, count=None):
        """
        获取最近的N个数据点
        ==================
        
        Args:
            count: 要获取的数据点数量，None表示获取所有显示数据
            
        Returns:
            list: 最近的数据点
        """
        with self.data_lock:
            if count is None:
                return list(self.display_data)
            else:
                recent_data = list(self.display_data)
                return recent_data[-count:] if len(recent_data) > count else recent_data
    
    def get_cache_data(self, start_index=None, end_index=None):
        """
        获取缓存数据（更大的历史窗口）
        =============================
        
        Args:
            start_index: 开始索引
            end_index: 结束索引
            
        Returns:
            list: 缓存数据
        """
        with self.data_lock:
            cache_list = list(self.cache_data)
            if start_index is None and end_index is None:
                return cache_list
            elif start_index is None:
                return cache_list[:end_index]
            elif end_index is None:
                return cache_list[start_index:]
            else:
                return cache_list[start_index:end_index]
    
    def get_complete_data(self):
        """
        获取完整数据（从临时文件读取）
        =============================
        
        Returns:
            list: 完整的数据列表
        """
        if not self.temp_file_path or not os.path.exists(self.temp_file_path):
            return self.get_cache_data()
        
        complete_data = []
        
        try:
            # 刷新当前写入缓冲区
            if self.temp_file_handle:
                with self.file_lock:
                    self.temp_file_handle.flush()
            
            # 分块读取临时文件，避免内存爆炸
            with open(self.temp_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                chunk_size = 10000  # 每次读取10000行
                chunk = []
                
                for row in reader:
                    try:
                        # 转换为浮点数
                        data_row = [float(val) for val in row]
                        chunk.append(data_row)
                        
                        # 达到块大小时处理一批
                        if len(chunk) >= chunk_size:
                            complete_data.extend(chunk)
                            chunk = []
                            
                    except ValueError:
                        # 跳过无效行
                        continue
                
                # 处理最后一批数据
                if chunk:
                    complete_data.extend(chunk)
            
            print(f"✓ 从临时文件读取了 {len(complete_data)} 个数据点")
            return complete_data
            
        except Exception as e:
            print(f"✗ 读取临时文件失败: {e}")
            # 降级到缓存数据
            return self.get_cache_data()
    
    def _auto_cleanup(self):
        """自动清理内存（简化版本）"""
        try:
            # 强制垃圾回收
            gc.collect()
            
            # 更新清理计数
            self.last_cleanup_count = getattr(self, 'data_count', 0)
            
            # 获取当前内存使用情况
            memory_usage = self._get_memory_usage()
            if hasattr(self, 'performance_stats'):
                self.performance_stats['memory_usage_mb'] = memory_usage
            
            total_points = getattr(self, 'total_data_points', getattr(self, 'data_count', 0))
            print(f"✓ 自动清理完成，当前内存使用: {memory_usage:.1f}MB，数据点: {total_points}")
            
        except Exception as e:
            print(f"✗ 自动清理失败: {e}")
    
    def _get_memory_usage(self):
        """获取当前内存使用情况（MB）"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # 如果没有psutil，使用近似估算
            display_size = len(self.display_data) * 8 * 10  # 假设每个数据点10个浮点数
            cache_size = len(self.cache_data) * 8 * 10
            return (display_size + cache_size) / 1024 / 1024
    
    def _update_performance_stats(self):
        """更新性能统计"""
        try:
            current_time = datetime.datetime.now()
            time_diff = (current_time - self.performance_stats['last_update_time']).total_seconds()
            
            if time_diff >= 1.0:  # 每秒更新一次
                # 计算数据处理速率
                points_per_sec = self.data_count / time_diff if time_diff > 0 else 0
                self.performance_stats['data_points_per_sec'] = points_per_sec
                self.performance_stats['last_update_time'] = current_time
                
                # 每10秒打印一次统计信息
                if self.data_count % 1000 == 0:
                    print(f"📊 性能统计: {points_per_sec:.1f} 点/秒, "
                          f"内存: {self.performance_stats['memory_usage_mb']:.1f}MB, "
                          f"总数据: {self.total_data_points}")
                
        except Exception as e:
            print(f"✗ 更新性能统计失败: {e}")
    
    def get_optimized_plot_data(self, max_points=None):
        """
        获取优化的绘图数据
        ==================
        
        Args:
            max_points: 最大点数，None表示使用默认显示窗口大小
            
        Returns:
            list: 优化的绘图数据
        """
        if max_points is None:
            max_points = self.display_window_size
            
        display_data = self.get_display_data()
        
        # 如果数据量大于最大点数，进行抽样
        if len(display_data) > max_points:
            # 使用均匀抽样保持数据分布
            step = len(display_data) // max_points
            sampled_data = display_data[::step][:max_points]
            print(f"📈 绘图数据已抽样: {len(display_data)} -> {len(sampled_data)} 点")
            return sampled_data
        else:
            return display_data
    
    def set_display_window_size(self, size):
        """
        设置显示窗口大小
        ================
        
        Args:
            size: 新的窗口大小
        """
        old_size = self.display_window_size
        self.display_window_size = size
        
        # 重新创建显示数据deque
        with self.data_lock:
            current_data = list(self.display_data)
            self.display_data = deque(current_data[-size:], maxlen=size)
            self.data = list(self.display_data)
            
        print(f"✓ 显示窗口大小已更新: {old_size} -> {size}")
    
    def set_cache_window_size(self, size):
        """
        设置缓存窗口大小
        ================
        
        Args:
            size: 新的缓存窗口大小
        """
        old_size = self.cache_window_size
        self.cache_window_size = size
        
        # 重新创建缓存数据deque
        with self.data_lock:
            current_cache = list(self.cache_data)
            self.cache_data = deque(current_cache[-size:], maxlen=size)
            
        print(f"✓ 缓存窗口大小已更新: {old_size} -> {size}")
    
    # ================================================================
    # 保持原有接口兼容性
    # ================================================================
    
    def set_save_path(self, path):
        """设置保存路径"""
        self.save_path = path
        
    def get_save_path(self):
        """获取保存路径"""
        return self.save_path
    
    def start_acquisition(self):
        """开始新的数据采集会话"""
        self.clear_data()
        # 记录绝对开始时间
        self.acquisition_start_time = datetime.datetime.now()
        self.acquisition_start_time_str = self.acquisition_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        print("✓ 数据采集开始，优化存储系统已就绪")
        
    def save_data(self, parent_widget=None, num_sensors=None, sensor_names=None):
        """
        保存数据到CSV文件（修改版：支持患者端扩展数据格式）
        """
        if not self.save_path:
            if parent_widget:
                QMessageBox.warning(parent_widget, "错误", "未指定保存路径")
            return False
        
        # 优先使用完整数据
        try:
            print("📁 开始保存完整数据...")
            data_to_save = self.get_complete_data()
            data_source = "完整数据（临时文件）"
        except Exception as e:
            print(f"⚠️ 无法获取完整数据，使用缓存数据: {e}")
            data_to_save = self.get_cache_data()
            data_source = "缓存数据"
        
        if not data_to_save:
            if parent_widget:
                QMessageBox.information(parent_widget, "提示", "没有数据可保存")
            return False
            
        try:
            # 检测数据格式（患者端扩展格式 vs 普通格式）
            is_extended_format = False
            if data_to_save and len(data_to_save[0]) > 1:
                # 通过数据长度判断是否为扩展格式
                first_row_length = len(data_to_save[0])
                if num_sensors:
                    expected_normal_length = num_sensors + 1  # 时间戳 + 传感器数据
                    expected_extended_length = num_sensors * 2 + 1  # 时间戳 + 原始 + 映射
                    
                    if first_row_length == expected_extended_length:
                        is_extended_format = True
                        print(f"检测到患者端扩展数据格式: {first_row_length} 列")
                    elif first_row_length == expected_normal_length:
                        is_extended_format = False
                        print(f"检测到普通数据格式: {first_row_length} 列")
                    else:
                        # 自动推断传感器数量
                        if first_row_length % 2 == 1 and first_row_length > 3:
                            # 奇数列且大于3，可能是扩展格式
                            inferred_sensors = (first_row_length - 1) // 2
                            if inferred_sensors > 0:
                                is_extended_format = True
                                num_sensors = inferred_sensors
                                print(f"自动推断：患者端扩展格式，传感器数量: {num_sensors}")
            
            # 自动推断传感器数量
            if num_sensors is None and data_to_save:
                if is_extended_format:
                    num_sensors = (len(data_to_save[0]) - 1) // 2
                else:
                    num_sensors = len(data_to_save[0]) - 1
            
            # 检查文件是否存在
            file_exists = os.path.exists(self.save_path)
            if file_exists:
                print(f"📄 文件已存在，将覆盖: {self.save_path}")
                
            # 分批写入大文件，避免内存问题
            with open(self.save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # 写入元数据
                if hasattr(self, 'acquisition_start_time_str'):
                    writer.writerow(["# Acquisition Start Time: " + self.acquisition_start_time_str])
                    writer.writerow(["# Total data points: " + str(len(data_to_save))])
                    writer.writerow(["# Data source: " + data_source])
                    writer.writerow(["# Memory optimized: True"])
                    if is_extended_format:
                        writer.writerow(["# Data format: Patient mode (original + mapped values)"])
                        writer.writerow(["# Mapping: original=1, target=0, intermediate=proportional"])
                    else:
                        writer.writerow(["# Data format: Doctor mode (original values only)"])
                    writer.writerow([])
                
                # 写入标题行
                header = ["time(s)"]
                
                if is_extended_format:
                    # 患者端扩展格式：原始值 + 映射值
                    for i in range(num_sensors):
                        if sensor_names and i < len(sensor_names):
                            header.append(f"{sensor_names[i]}_original")
                        else:
                            header.append(f"sensor{i+1}_original")
                    
                    for i in range(num_sensors):
                        if sensor_names and i < len(sensor_names):
                            header.append(f"{sensor_names[i]}_mapped")
                        else:
                            header.append(f"sensor{i+1}_mapped")
                else:
                    # 普通格式：只有原始值
                    for i in range(num_sensors):
                        if sensor_names and i < len(sensor_names):
                            header.append(sensor_names[i])
                        else:
                            header.append(f"sensor{i+1}")
                
                writer.writerow(header)
                
                # 分批写入数据
                batch_size = 10000
                for i in range(0, len(data_to_save), batch_size):
                    batch = data_to_save[i:i+batch_size]
                    for row in batch:
                        writer.writerow(row)
                    
                    # 显示进度
                    progress = min(100, (i + batch_size) * 100 // len(data_to_save))
                    print(f"💾 保存进度: {progress}%")
                    
            if parent_widget:
                format_info = "患者端扩展格式（原始值+0-1映射值）" if is_extended_format else "普通格式（原始值）"
                message = (f"数据已保存至：\n{self.save_path}\n"
                          f"共保存 {len(data_to_save)} 个数据点\n"
                          f"数据源：{data_source}\n"
                          f"数据格式：{format_info}\n"
                          f"内存优化：已启用")
                if file_exists:
                    message += "\n注意：原文件已被覆盖"
                if is_extended_format:
                    message += f"\n\n数据列格式："
                    message += f"\n- 时间戳列: time(s)"
                    message += f"\n- 原始数据列: sensor1_original ~ sensor{num_sensors}_original"
                    message += f"\n- 映射数据列: sensor1_mapped ~ sensor{num_sensors}_mapped"
                    message += f"\n- 映射规则: 原始值=1, 最佳值=0, 中间值按比例计算"
                QMessageBox.information(parent_widget, "成功", message)
            
            print(f"✓ 数据保存成功: {len(data_to_save)} 个数据点 -> {self.save_path}")
            if is_extended_format:
                print(f"✓ 保存格式: 患者端扩展格式（{num_sensors}个传感器，原始值+0-1映射值）")
            else:
                print(f"✓ 保存格式: 普通格式（{num_sensors}个传感器，原始值）")
            
            # 【新增】保存原始数据（滤波前的数据）
            self._save_raw_data(parent_widget, num_sensors, sensor_names)
            
            # 【新增】保存处理后数据（滤波+增强+二次滤波后）
            self._save_processed_data(parent_widget, num_sensors, sensor_names)
            
            return True
            
        except Exception as e:
            error_msg = f"保存数据失败: {str(e)}"
            print(f"✗ {error_msg}")
            if parent_widget:
                QMessageBox.critical(parent_widget, "错误", error_msg)
            return False
    
    def _save_raw_data(self, parent_widget=None, num_sensors=None, sensor_names=None):
        """
        保存原始数据（滤波前的数据）
        """
        try:
            # 构造原始数据保存路径
            if not self.save_path:
                return False
            
            # 在原始文件名基础上添加"_raw"后缀
            base_path = os.path.splitext(self.save_path)[0]
            extension = os.path.splitext(self.save_path)[1]
            raw_save_path = f"{base_path}_raw{extension}"
            
            # 获取原始数据
            raw_data_to_save = []
            if self.raw_temp_file_path and os.path.exists(self.raw_temp_file_path):
                # 从临时文件读取原始数据
                with open(self.raw_temp_file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and len(row) > 1:  # 跳过空行
                            # 移除RAW标识，保留时间戳和传感器数据
                            if row[0] == "RAW":
                                raw_data_to_save.append(row[1:])  # 跳过RAW标识
                            else:
                                raw_data_to_save.append(row)
            else:
                # 从内存中获取原始数据
                with self.data_lock:
                    raw_data_to_save = [row[1:] for row in list(self.raw_data) if len(row) > 1]
            
            if not raw_data_to_save:
                print("⚠️ 没有原始数据可保存")
                return False
            
            # 自动推断传感器数量
            if num_sensors is None and raw_data_to_save:
                num_sensors = len(raw_data_to_save[0]) - 1  # 减去时间戳
            
            # 保存原始数据
            with open(raw_save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入元数据
                if hasattr(self, 'acquisition_start_time_str'):
                    writer.writerow(["# Acquisition Start Time: " + self.acquisition_start_time_str])
                    writer.writerow(["# Total raw data points: " + str(len(raw_data_to_save))])
                    writer.writerow(["# Data source: Raw sensor data (before Kalman filtering)"])
                    writer.writerow(["# Memory optimized: True"])
                    writer.writerow([])
                
                # 写入标题行
                header = ["time(s)"]
                for i in range(num_sensors):
                    if sensor_names and i < len(sensor_names):
                        header.append(f"{sensor_names[i]}_raw")
                    else:
                        header.append(f"sensor{i+1}_raw")
                
                writer.writerow(header)
                
                # 写入数据
                for row in raw_data_to_save:
                    writer.writerow(row)
            
            print(f"✓ 原始数据保存成功: {len(raw_data_to_save)} 个数据点 -> {raw_save_path}")
            
            if parent_widget:
                QMessageBox.information(parent_widget, "原始数据保存成功", 
                    f"原始数据（滤波前）已保存至：\n{raw_save_path}\n"
                    f"共保存 {len(raw_data_to_save)} 个原始数据点")
            
            return True
            
        except Exception as e:
            print(f"✗ 保存原始数据失败: {e}")
            return False
    
    def _save_processed_data(self, parent_widget=None, num_sensors=None, sensor_names=None):
        """
        保存处理后数据（滤波+增强+二次滤波后）
        """
        try:
            if not self.save_path:
                return False
            base_path = os.path.splitext(self.save_path)[0]
            extension = os.path.splitext(self.save_path)[1]
            processed_save_path = f"{base_path}_processed{extension}"
            # 获取处理后数据
            processed_data_to_save = []
            if self.processed_temp_file_path and os.path.exists(self.processed_temp_file_path):
                with open(self.processed_temp_file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and len(row) > 1:
                            if row[0] == "PROCESSED":
                                processed_data_to_save.append(row[1:])
                            else:
                                processed_data_to_save.append(row)
            else:
                with self.data_lock:
                    processed_data_to_save = [row[1:] for row in list(self.processed_data) if len(row) > 1]
            if not processed_data_to_save:
                print("⚠️ 没有处理后数据可保存")
                return False
            # 自动推断传感器数量
            if num_sensors is None and processed_data_to_save:
                num_sensors = len(processed_data_to_save[0]) - 1
            with open(processed_save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if hasattr(self, 'acquisition_start_time_str'):
                    writer.writerow(["# Acquisition Start Time: " + self.acquisition_start_time_str])
                    writer.writerow(["# Total processed data points: " + str(len(processed_data_to_save))])
                    writer.writerow(["# Data source: Processed sensor data (after all filters)"])
                # 写入标题行
                header = ["time(s)"]
                for i in range(num_sensors):
                    if sensor_names and i < len(sensor_names):
                        header.append(sensor_names[i])
                    else:
                        header.append(f"sensor{i+1}")
                writer.writerow(header)
                batch_size = 10000
                for i in range(0, len(processed_data_to_save), batch_size):
                    batch = processed_data_to_save[i:i+batch_size]
                    for row in batch:
                        writer.writerow(row)
            print(f"✓ 处理后数据已保存: {len(processed_data_to_save)} 个数据点 -> {processed_save_path}")
            return True
        except Exception as e:
            print(f"✗ 保存处理后数据失败: {e}")
            return False
    
    def load_data(self, file_path=None, parent_widget=None):
        """从CSV文件加载数据"""
        path = file_path if file_path else self.save_path
        
        if not path or not os.path.exists(path):
            if parent_widget:
                QMessageBox.warning(parent_widget, "错误", "文件不存在")
            return False, [], []
            
        try:
            loaded_data = []
            sensor_names = []
            
            print(f"📂 开始加载数据文件: {path}")
            
            with open(path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                # 跳过注释行
                for row in reader:
                    if not row or row[0].startswith('#'):
                        continue
                    
                    # 第一个非注释行是标题行
                    if not sensor_names:
                        sensor_names = row[1:]  # 跳过时间列
                        continue
                    
                    # 数据行
                    try:
                        data_row = [float(val) for val in row]
                        loaded_data.append(data_row)
                        
                        # 显示加载进度
                        if len(loaded_data) % 10000 == 0:
                            print(f"📈 已加载 {len(loaded_data)} 行数据...")
                            
                    except ValueError:
                        continue
                        
            # 更新内部数据结构
            with self.data_lock:
                # 如果加载的数据太大，只保留最近的部分
                if len(loaded_data) > self.cache_window_size:
                    print(f"⚠️ 数据量过大，只保留最近 {self.cache_window_size} 个数据点")
                    loaded_data = loaded_data[-self.cache_window_size:]
                
                self.cache_data = deque(loaded_data, maxlen=self.cache_window_size)
                self.display_data = deque(loaded_data[-self.display_window_size:], 
                                        maxlen=self.display_window_size)
                self.data = list(self.display_data)
                
            self.save_path = path
            self.total_data_points = len(loaded_data)
            
            if parent_widget:
                QMessageBox.information(parent_widget, "成功", 
                                      f"已加载数据，共{len(loaded_data)}行\n"
                                      f"显示窗口：{len(self.display_data)}行\n"
                                      f"缓存窗口：{len(self.cache_data)}行")
                
            print(f"✓ 数据加载完成: {len(loaded_data)} 行")
            return True, loaded_data, sensor_names
            
        except Exception as e:
            if parent_widget:
                QMessageBox.critical(parent_widget, "错误", f"加载数据时发生错误：\n{str(e)}")
            print(f"✗ 加载数据失败: {e}")
            return False, [], []
    
    def _backup_temp_file(self):
        """备份临时文件的简单实现"""
        if not self.enable_temp_file or not self.temp_file_path:
            return
        
        try:
            if self.temp_file_handle:
                self.temp_file_handle.flush()
            print(f"自动备份检查: {self.data_count} 个数据点")
        except Exception as e:
            print(f"备份检查失败: {e}")

    def get_data_stats(self):
        """
        获取数据统计信息（兼容新旧版本）
        ===========================
        
        Returns:
            dict: 数据统计信息
        """
        with self.data_lock:
            # 兼容新旧版本的属性名
            display_count = len(self.display_data) if hasattr(self, 'display_data') else len(self.data)
            total_count = getattr(self, 'data_count', len(self.data))
            
            # 【新增】原始数据统计
            raw_count = getattr(self, 'raw_data_count', 0)
            
            # 【新增】处理后数据统计
            processed_count = getattr(self, 'processed_data_count', 0)
            
            return {
                'display_data_count': display_count,
                'total_data_count': total_count,
                'raw_data_count': raw_count,  # 【新增】原始数据计数
                'processed_data_count': processed_count, # 【新增】处理后数据计数
                'memory_data_count': display_count,  # 兼容旧版本
                'temp_file_enabled': self.enable_temp_file,
                'temp_file_path': self.temp_file_path,
                'raw_temp_file_path': getattr(self, 'raw_temp_file_path', None),  # 【新增】原始数据临时文件路径
                'processed_temp_file_path': getattr(self, 'processed_temp_file_path', None), # 【新增】处理后数据临时文件路径
                'memory_limit': self.memory_limit,
                'save_path': self.save_path
            }
    
    def cleanup_temp_file(self):
        """清理临时文件"""
        try:
            if self.temp_file_handle:
                self.temp_file_handle.close()
                self.temp_file_handle = None
                self.temp_writer = None
            
            if self.temp_file_path and os.path.exists(self.temp_file_path):
                os.remove(self.temp_file_path)
                print(f"✓ 临时文件已清理: {self.temp_file_path}")
                
        except Exception as e:
            print(f"✗ 清理临时文件失败: {e}")
    
    def cleanup_raw_temp_file(self):
        """清理原始数据临时文件"""
        try:
            if self.raw_temp_file_handle:
                self.raw_temp_file_handle.close()
                self.raw_temp_file_handle = None
                self.raw_temp_writer = None
            
            if self.raw_temp_file_path and os.path.exists(self.raw_temp_file_path):
                os.remove(self.raw_temp_file_path)
                print(f"✓ 原始数据临时文件已清理: {self.raw_temp_file_path}")
                
        except Exception as e:
            print(f"✗ 清理原始数据临时文件失败: {e}")
    
    def cleanup_processed_temp_file(self):
        """
        清理处理后数据临时文件
        """
        try:
            if self.processed_temp_file_handle:
                self.processed_temp_file_handle.close()
                self.processed_temp_file_handle = None
                self.processed_temp_writer = None
        except Exception as e:
            print(f"✗ 清理处理后数据临时文件失败: {e}")
    
    def set_patient_mode(self, is_patient_mode):
        """设置是否为患者端模式"""
        self.is_patient_mode = is_patient_mode
        print(f"数据管理器设置为{'患者端' if is_patient_mode else '医生端'}模式")
    
    def set_patient_mapping_data(self, mapping_data):
        """设置患者端映射数据"""
        self.patient_mapping_data = mapping_data
        print("患者端映射数据已设置到数据管理器")

    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            self.cleanup_temp_file()
            # 【新增】清理原始数据临时文件
            self.cleanup_raw_temp_file()
            # 【新增】清理处理后数据临时文件
            self.cleanup_processed_temp_file()
        except:
            pass