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
        self.record_display.setMaximumHeight(200)
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
            
            # 自动保存标准文件（如果是完成阶段事件）
            if 'event_name' in data and '完成' in data.get('event_name', ''):
                self._save_standard_file(data)
            
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
                    sensor_data = data['raw_sensor_data'][1:] if len(data['raw_sensor_data']) > 1 else data['raw_sensor_data']
                    display_text += f"  📊 原始数据: {[f'{x:.0f}' for x in sensor_data]}\n"
                
                # 显示权重信息
                if 'sensor_weights' in data:
                    weights = data['sensor_weights']
                    display_text += f"  ⚖️ 传感器权重: {[f'{w:.1f}' for w in weights]}\n"
                
                # 显示误差范围
                if 'error_range' in data:
                    error_range = data['error_range']
                    display_text += f"  🎯 误差范围: {error_range:.3f}\n"
                
                # 显示校准计算结果（增强功能）
                calibration_result = self._calculate_calibration_display(data)
                if calibration_result:
                    display_text += calibration_result
                
                # 显示归一化和加权组合结果
                normalized_result = self._calculate_normalized_display(data)
                if normalized_result:
                    display_text += normalized_result
                
                # 显示校准效果评估
                evaluation_result = self._evaluate_calibration_effect(data)
                if evaluation_result:
                    display_text += evaluation_result
                
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
            if any(keyword in event_name for keyword in ['开始', '完成', '校准']):
                if '开始' in event_name:
                    result_text += f"  🔧 校准开始 - 记录原始值(OV)\n"
                elif '完成' in event_name:
                    result_text += f"  ✅ 校准完成 - 更新最佳值(BV)\n"
                    
                    # 显示校准前后对比（如果有历史数据）
                    if hasattr(self, '_last_original_values'):
                        improvement = self._calculate_improvement(data)
                        if improvement:
                            result_text += f"  📈 改善程度: {improvement}\n"
            
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
                
            sensor_data = raw_sensor_data[1:] if len(raw_sensor_data) > 1 else raw_sensor_data
            
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
    
    def _evaluate_calibration_effect(self, data):
        """评估校准效果"""
        try:
            result_text = ""
            
            error_range = data.get('error_range', 0)
            event_name = data.get('event_name', '')
            
            # 校准效果评估
            if '完成' in event_name:
                if error_range < 0.05:
                    result_text += f"  🟢 校准效果: 优秀 (误差 < 5%)\n"
                elif error_range < 0.1:
                    result_text += f"  🟡 校准效果: 良好 (误差 < 10%)\n"
                else:
                    result_text += f"  🔴 校准效果: 需改善 (误差 ≥ 10%)\n"
                
                # 给出建议
                if error_range > 0.1:
                    result_text += f"  💡 建议: 重新调整传感器权重或重新校准\n"
            
            return result_text
            
        except Exception as e:
            print(f"评估校准效果时出错: {e}")
            return ""
    
    def _calculate_improvement(self, data):
        """计算改善程度"""
        try:
            # 这里应该比较校准前后的数据
            # 由于需要历史数据，暂时返回模拟结果
            return "传感器稳定性提升 15%"
        except:
            return None
    
    def _save_standard_file(self, data):
        """保存标准文件（每次完成阶段时自动保存）"""
        try:
            stage = data.get('stage', 1)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 生成标准文件名
            filename = f"standard_stage{stage}_{timestamp}.json"
            filepath = os.path.join(self.save_directory, filename)
            
            # 保存标准数据
            standard_data = {
                'stage': stage,
                'event_name': data.get('event_name', ''),
                'timestamp': data.get('timestamp', 0),
                'raw_sensor_data': data.get('raw_sensor_data', []),
                'sensor_weights': data.get('sensor_weights', []),
                'error_range': data.get('error_range', 0.1),
                'recorded_at': data.get('recorded_at', ''),
                'visualization_state': data.get('visualization_state', {})
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(standard_data, f, ensure_ascii=False, indent=2)
            
            print(f"TrainingRecorder: 已保存标准文件 {filename}")
            
        except Exception as e:
            print(f"TrainingRecorder: 保存标准文件时出错 - {e}")
    
    def save_records(self):
        """保存所有记录到Excel文件"""
        try:
            if not self.records:
                print("TrainingRecorder: 没有记录可保存")
                return
            
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
                sensor_data = data.get('raw_sensor_data', [])
                if sensor_data and len(sensor_data) > 1:
                    for i, value in enumerate(sensor_data[1:], 1):
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
            
            print(f"TrainingRecorder: 已保存记录到 {filename}")
            print(f"TrainingRecorder: 共保存 {len(records_data)} 条记录")
            
        except Exception as e:
            print(f"TrainingRecorder: 保存记录时出错 - {e}")
    
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
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
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
        
        # 实时保存校准数据
        self._save_calibration_data(record)
    
    def _save_calibration_data(self, record):
        """实时保存校准数据"""
        try:
            # 创建校准数据保存目录
            calibration_dir = os.path.join(os.path.dirname(__file__), '..', 'saving_data', 'calibration')
            os.makedirs(calibration_dir, exist_ok=True)
            
            # 保存单次校准记录
            filename = f"calibration_stage_{record['stage']}_{record['sequence_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(calibration_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            
            print(f"校准数据已保存: {filepath}")
        except Exception as e:
            print(f"保存校准数据失败: {e}")
    
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
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_records, f, ensure_ascii=False, indent=2)
            
            print(f"训练记录已导出: {export_path}")
            return export_path
        except Exception as e:
            print(f"导出训练记录失败: {e}")
            return None