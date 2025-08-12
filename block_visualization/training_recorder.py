# -*- coding: utf-8 -*-
"""
训练记录器模块
用于记录和管理训练过程中的数据
"""

import os
import json
import pandas as pd
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QGroupBox
from PyQt5.QtCore import pyqtSignal

class TrainingRecorder(QWidget):
    """训练记录器类"""
    
    # 信号定义
    record_updated = pyqtSignal(str)  # 记录更新信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 数据存储
        self.records = {}  # 存储所有训练记录
        self.current_session = None  # 当前训练会话
        self.current_stage = None
        self.spine_type = 'C'  # 默认C型
        self.spine_direction = 'left'  # 默认左凸
        self.save_directory = "saving_data/training_records"  # 保存目录
        
        # 确保保存目录存在
        os.makedirs(self.save_directory, exist_ok=True)
        
        # 初始化UI
        self.setup_ui()
        
        print("TrainingRecorder: 初始化完成")
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("训练记录详情")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 记录显示区域
        self.record_display = QTextEdit()
        self.record_display.setMaximumHeight(500)
        self.record_display.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.record_display)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 保存记录按钮
        self.save_button = QPushButton("保存记录")
        self.save_button.clicked.connect(self.save_records)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.save_button)
        
        # 清空记录按钮
        self.clear_button = QPushButton("清空记录")
        self.clear_button.clicked.connect(self.clear_records)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        button_layout.addWidget(self.clear_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 统计信息
        self.stats_label = QLabel("记录数量: 0")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.stats_label)
    
    def add_record_data(self, record_key, data):
        """添加记录数据"""
        try:
            # 确保数据包含必要字段
            if not isinstance(data, dict):
                print(f"警告: 记录数据必须是字典格式")
                return
            
            # 添加时间戳
            data['recorded_at'] = datetime.now().isoformat()
            
            # 存储记录
            self.records[record_key] = data
            
            # 实时更新UI显示
            self._update_record_display()
            
            # 自动保存标准文件功能已禁用
            # if 'event_name' in data and '完成' in data.get('event_name', ''):
            #     self._save_standard_file(data)
            
            print(f"TrainingRecorder: 已添加记录 {record_key}")
            
            # 发送更新信号
            self.record_updated.emit(record_key)
            
        except Exception as e:
            print(f"TrainingRecorder: 添加记录时出错 - {e}")
    
    def _update_record_display(self):
        """更新记录显示（增强版：显示校准过程和计算结果）"""
        try:
            display_text = f"脊柱类型: {getattr(self, 'spine_type', 'C')}型\n"
            display_text += f"方向: {getattr(self, 'spine_direction', 'left')}凸\n"
            display_text += f"当前阶段: {self.current_stage or '未设置'}\n\n"
            
            # 按时间排序显示记录
            sorted_records = sorted(
                self.records.items(),
                key=lambda x: x[1].get('recorded_at', ''),
                reverse=True
            )
            
            for record_key, data in sorted_records[-10:]:  # 只显示最近10条
                stage = data.get('stage', 'N/A')
                event_name = data.get('event_name', 'N/A')
                timestamp = data.get('timestamp', 0)
                
                if isinstance(timestamp, str):
                    display_text += f"[{timestamp}] 阶段{stage} - {event_name}\n"
                else:
                    display_text += f"[{timestamp:.1f}s] 阶段{stage} - {event_name}\n"
                
                # 显示原始传感器数据
                if 'raw_sensor_data' in data and data['raw_sensor_data']:
                    sensor_data = self._strip_timestamp_if_present(data['raw_sensor_data'])
                    display_text += f"  📊 原始数据: {[f'{x:.0f}' for x in sensor_data]}\n"
                
                # 显示权重信息
                if 'sensor_weights' in data:
                    weights = data['sensor_weights']
                    display_text += f"  ⚖️ 传感器权重: {[f'{w:.1f}' for w in weights]}\n"
                
                # 显示误差范围
                if 'error_range' in data:
                    error_range = data['error_range']
                    display_text += f"  🎯 误差范围: {error_range:.2f}\n"
                
                # 显示校准计算结果（增强功能）
                calibration_result = self._calculate_calibration_display(data)
                if calibration_result:
                    display_text += calibration_result
                
                # 显示归一化和加权组合结果
                normalized_result = self._calculate_normalized_display(data)
                if normalized_result:
                    display_text += normalized_result

                display_text += "─" * 50 + "\n"
            
            self.record_display.setPlainText(display_text)
            
            # 滚动到底部
            scrollbar = self.record_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            # 更新统计信息
            self.stats_label.setText(f"记录数量: {len(self.records)}")
            
        except Exception as e:
            print(f"TrainingRecorder: 更新显示时出错 - {e}")
    
    def _calculate_calibration_display(self, data):
        """计算并显示校准过程信息"""
        try:
            result_text = ""
            
            # 获取校准相关数据
            visualization_state = data.get('visualization_state', {})
            sensor_values = visualization_state.get('sensor_values', {})
            event_name = data.get('event_name', '')
            
            # 如果是校准相关事件，显示OV/BV信息
            if any(keyword in event_name for keyword in ['开始', '完成']):
                if '开始' in event_name:
                    result_text += f"  🔧 校准开始 - 记录原始值(OV)\n"
                elif '完成' in event_name:
                    result_text += f"  ✅ 校准完成 - 更新最佳值(BV)\n"
                    
            
            return result_text
            
        except Exception as e:
            print(f"计算校准显示信息时出错: {e}")
            return ""
    
    def _calculate_normalized_display(self, data):
        """计算并显示归一化和加权组合结果（使用真实校准数据）"""
        try:
            result_text = ""
            
            # 获取数据
            raw_sensor_data = data.get('raw_sensor_data', [])
            sensor_weights = data.get('sensor_weights', [])
            calibration_data = data.get('calibration_data', {})
            
            if not raw_sensor_data or not sensor_weights:
                return result_text
                
            sensor_data = self._strip_timestamp_if_present(raw_sensor_data)
            
            # 使用真实的校准数据计算归一化值
            if calibration_data and 'normalized_values' in calibration_data:
                # 使用已计算的真实归一化值
                normalized_values = calibration_data['normalized_values']
                result_text += f"  📐 归一化值: {[f'{n:.3f}' for n in normalized_values]}\n"
                
                # 使用真实的加权组合值
                if 'combined_value' in calibration_data:
                    combined_value = calibration_data['combined_value']
                    result_text += f"  🎯 加权组合值: {combined_value:.3f}\n"
                else:
                    # 如果没有预计算的组合值，则计算
                    weighted_sum = sum(w * n for w, n in zip(sensor_weights, normalized_values) if w > 0)
                    total_weight = sum(w for w in sensor_weights if w > 0)
                    if total_weight > 0:
                        combined_value = weighted_sum / total_weight
                        result_text += f"  🎯 加权组合值: {combined_value:.3f}\n"
            
            else:
                # 如果没有校准数据，显示提示信息
                result_text += f"  ℹ️ 等待校准数据更新...\n"
            
            return result_text
            
        except Exception as e:
            print(f"计算归一化显示信息时出错: {e}")
            return ""
    
    
    # def _save_standard_file(self, data):
    #     """保存标准文件（已禁用）"""
    #     print("TrainingRecorder: 标准文件保存功能已禁用")
    #     pass
    
    def save_records(self, export_path=None):
        """保存所有记录到Excel文件，可选自定义导出路径"""
        try:
            if not self.records:
                print("TrainingRecorder: 没有记录可保存")
                return
            
            if export_path:
                filepath = export_path
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"training_records_{timestamp}.xlsx"
                filepath = os.path.join(self.save_directory, filename)
            
            # 准备数据
            records_data = []
            for record_key, data in self.records.items():
                record_row = {
                    'record_key': record_key,
                    'stage': data.get('stage', ''),
                    'event_name': data.get('event_name', ''),
                    'event_code': data.get('event_code', ''),
                    'timestamp': data.get('timestamp', 0),
                    'recorded_at': data.get('recorded_at', ''),
                    'error_range': data.get('error_range', 0)
                }
                
                # 添加传感器数据
                sensor_data = self._strip_timestamp_if_present(data.get('raw_sensor_data', []))
                if sensor_data:
                    for i, value in enumerate(sensor_data, 1):
                        record_row[f'sensor_{i}'] = value
                
                # 添加权重数据
                weights = data.get('sensor_weights', [])
                for i, weight in enumerate(weights, 1):
                    record_row[f'weight_{i}'] = weight
                
                records_data.append(record_row)
            
            # 创建DataFrame并保存
            df = pd.DataFrame(records_data)
            
            # 按阶段分别保存到不同的工作表
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 保存所有记录
                df.to_excel(writer, sheet_name='所有记录', index=False)
                
                # 按阶段分别保存
                for stage in df['stage'].unique():
                    stage_df = df[df['stage'] == stage]
                    sheet_name = f'阶段{stage}'
                    stage_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            print(f"TrainingRecorder: 已保存记录到 {filepath}")
            print(f"TrainingRecorder: 共保存 {len(records_data)} 条记录")
            return filepath
            
        except Exception as e:
            print(f"TrainingRecorder: 保存记录时出错 - {e}")
            return None
    
    def clear_records(self):
        """清空所有记录"""
        self.records.clear()
        self._update_record_display()
        print("TrainingRecorder: 已清空所有记录")
    
    def get_latest_standard_file(self, stage):
        """获取指定阶段的最新标准文件"""
        try:
            pattern = f"standard_stage{stage}_"
            files = [f for f in os.listdir(self.save_directory) if f.startswith(pattern) and f.endswith('.json')]
            
            if not files:
                return None
            
            # 按时间排序，返回最新的
            files.sort(reverse=True)
            latest_file = os.path.join(self.save_directory, files[0])
            
            # with open(latest_file, 'r', encoding='utf-8') as f: # 已移除，不再使用JSON文件保存功能
            #     return json.load(f) # 已移除，不再使用JSON文件保存功能
            return None # 已移除，不再使用JSON文件保存功能
                
        except Exception as e:
            print(f"TrainingRecorder: 获取标准文件时出错 - {e}")
            return None
    
    def get_record_count(self):
        """获取记录数量"""
        return len(self.records)
    
    def set_stage(self, stage):
        """设置当前阶段"""
        self.current_stage = stage
        print(f"TrainingRecorder: 设置阶段为 {stage}")
        try:
            self._update_record_display()
        except Exception as _e:
            print('record display refresh failed:', _e)
    
    def set_spine_type(self, spine_type):
        """设置脊柱类型"""
        self.spine_type = spine_type
        print(f"TrainingRecorder: 设置脊柱类型为 {spine_type}")
        # 更新显示
        self._update_record_display()
    
    def set_spine_direction(self, spine_direction):
        """设置脊柱方向"""
        self.spine_direction = spine_direction
        print(f"TrainingRecorder: 设置脊柱方向为 {spine_direction}")
        # 更新显示
        self._update_record_display()
    
    def start_stage(self, stage):
        """开始阶段"""
        self.current_stage = stage
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        record_key = f"start_stage_{stage}_{datetime.now().timestamp()}"
        record = {
            'timestamp': timestamp,
            'stage': stage,
            'action': 'start',
            'spine_type': getattr(self, 'spine_type', 'C'),
            'spine_direction': getattr(self, 'spine_direction', 'left'),
            'event_name': f'开始阶段{stage}',
            'recorded_at': datetime.now().isoformat()
        }
        self.records[record_key] = record
        print(f"TrainingRecorder: 开始阶段 {stage}")
        self._update_record_display()
        self.record_updated.emit(record_key)
    
    def complete_stage(self, stage, sensor_data=None):
        """完成阶段"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        record_key = f"complete_stage_{stage}_{datetime.now().timestamp()}"
        record = {
            'timestamp': timestamp,
            'stage': stage,
            'action': 'complete',
            'spine_type': getattr(self, 'spine_type', 'C'),
            'spine_direction': getattr(self, 'spine_direction', 'left'),
            'event_name': f'完成阶段{stage}',
            'recorded_at': datetime.now().isoformat(),
            'sensor_data': sensor_data if sensor_data else [],
            'sequence_number': len([k for k in self.records.keys() if k.startswith(f'complete_stage_{stage}_')]) + 1
        }
        
        # 保存每次完成阶段的记录（用于导出）
        self.records[record_key] = record
        
        # 更新标准文件（仅保留最后一次，用于第三个tab调用）
        standard_key = f"standard_stage_{stage}"
        self.records[standard_key] = record.copy()
        self.records[standard_key]['is_standard'] = True
        
        print(f"TrainingRecorder: 完成阶段 {stage}，序号: {record['sequence_number']}")
        self._update_record_display()
        self.record_updated.emit(record_key)
        
        # 校准数据保存功能已禁用
        # self._save_calibration_data(record)
    
    # def _save_calibration_data(self, record):
    #     """校准数据保存功能已禁用"""
    #     print("TrainingRecorder: 校准数据保存功能已禁用")
    #     pass
    
    def get_records_by_stage(self, stage):
        """获取指定阶段的所有记录"""
        return {k: v for k, v in self.records.items() if v.get('stage') == stage}
    
    def get_standard_record(self, stage):
        """获取指定阶段的标准记录（最后一次完成的记录）"""
        standard_key = f"standard_stage_{stage}"
        return self.records.get(standard_key, None)
    
    def get_all_standard_records(self):
        """获取所有标准记录（用于第三个tab调用）"""
        return {k: v for k, v in self.records.items() if v.get('is_standard', False)}
    
    def export_all_records(self, export_path=None):
        """导出所有记录（包括每次完成阶段的数据）"""
        try:
            if not export_path:
                export_dir = os.path.join(os.path.dirname(__file__), '..', 'saving_data', 'exports')
                os.makedirs(export_dir, exist_ok=True)
                export_path = os.path.join(export_dir, f"training_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
            # 过滤掉标准记录，只导出原始完成记录
            export_records = {k: v for k, v in self.records.items() if not v.get('is_standard', False)}
            
            # with open(export_path, 'w', encoding='utf-8') as f: # 已移除，不再使用JSON文件保存功能
            #     json.dump(export_records, f, ensure_ascii=False, indent=2) # 已移除，不再使用JSON文件保存功能
            # print(f"训练记录已导出: {export_path}") # 已移除，不再使用JSON文件保存功能
            return export_path
        except Exception as e:
            print(f"导出训练记录失败: {e}")
            return None

    def _strip_timestamp_if_present(self, data):
        """如果首元素像时间戳则去除，否则原样返回"""
        try:
            if isinstance(data, (list, tuple)) and len(data) > 0:
                first = data[0]
                if isinstance(first, (int, float)) and first > 1e8:
                    return list(data[1:])
            return list(data) if isinstance(data, (list, tuple)) else data
        except Exception:
            return data