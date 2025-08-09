#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
训练记录器模块，用于记录不同训练阶段的数据
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QGroupBox, QComboBox, QSpinBox, QFileDialog,
                           QTextEdit, QScrollArea)
from PyQt5.QtCore import pyqtSignal
import pandas as pd
import json
from datetime import datetime
import os

class TrainingRecorder(QWidget):
    """训练记录器组件"""
    
    record_signal = pyqtSignal(str, list)  # 记录信号：阶段名称，数据列表
    stage_changed = pyqtSignal(int)  # 阶段切换信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_stage = 1
        self.recording_data = {}
        self.save_path = os.path.join("saving_data", "training_records")
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        self._init_ui()
        
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 阶段选择
        stage_group = QGroupBox("训练阶段")
        stage_layout = QHBoxLayout()
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(["第一阶段：骨盆前滚", "第二阶段：曲率矫正", "第三阶段：关节平衡"])
        self.stage_combo.currentIndexChanged.connect(self._on_stage_changed)
        stage_layout.addWidget(QLabel("当前阶段："))
        stage_layout.addWidget(self.stage_combo)
        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group)
        
        # 保存路径设置
        path_group = QGroupBox("数据保存设置")
        path_layout = QHBoxLayout()
        self.path_label = QLabel(self.save_path)
        self.change_path_btn = QPushButton("更改路径")
        self.change_path_btn.clicked.connect(self._change_save_path)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.change_path_btn)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # 第一阶段控制
        self.stage1_group = QGroupBox("骨盆前滚记录")
        stage1_layout = QVBoxLayout()
        self.record_original_btn = QPushButton("记录原始值")
        self.record_trained_btn = QPushButton("记录训练后值")
        stage1_layout.addWidget(self.record_original_btn)
        stage1_layout.addWidget(self.record_trained_btn)
        self.stage1_group.setLayout(stage1_layout)
        layout.addWidget(self.stage1_group)
        
        # 第二阶段控制
        self.stage2_group = QGroupBox("曲率矫正记录")
        stage2_layout = QVBoxLayout()
        self.start_force_btn = QPushButton("开始发力")
        self.end_force_btn = QPushButton("完成发力")
        stage2_layout.addWidget(self.start_force_btn)
        stage2_layout.addWidget(self.end_force_btn)
        self.stage2_group.setLayout(stage2_layout)
        layout.addWidget(self.stage2_group)
        
        # 第三阶段控制
        self.stage3_group = QGroupBox("关节平衡记录")
        stage3_layout = QVBoxLayout()
        self.record_force_btn = QPushButton("记录发力值")
        self.start_shoulder_btn = QPushButton("开始沉肩")
        self.end_shoulder_btn = QPushButton("完成沉肩")
        self.start_hip_btn = QPushButton("开始沉髋")
        self.end_hip_btn = QPushButton("完成沉髋")
        stage3_layout.addWidget(self.record_force_btn)
        stage3_layout.addWidget(self.start_shoulder_btn)
        stage3_layout.addWidget(self.end_shoulder_btn)
        stage3_layout.addWidget(self.start_hip_btn)
        stage3_layout.addWidget(self.end_hip_btn)
        self.stage3_group.setLayout(stage3_layout)
        layout.addWidget(self.stage3_group)
        
        # 训练记录显示区域
        record_group = QGroupBox("训练记录详情")
        record_layout = QVBoxLayout()
        self.record_display = QTextEdit()
        self.record_display.setReadOnly(True)
        self.record_display.setMaximumHeight(200)
        self.record_display.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                font-family: 'Courier New', monospace;
                font-size: 9pt;
            }
        """)
        record_layout.addWidget(self.record_display)
        record_group.setLayout(record_layout)
        layout.addWidget(record_group)
        
        # 连接信号
        self._connect_signals()
        
        # 初始显示第一阶段
        self._show_stage(1)
        
    def _connect_signals(self):
        """连接信号与槽"""
        self.record_original_btn.clicked.connect(lambda: self._record_data("original"))
        self.record_trained_btn.clicked.connect(lambda: self._record_data("trained"))
        self.start_force_btn.clicked.connect(lambda: self._record_data("force_start"))
        self.end_force_btn.clicked.connect(lambda: self._record_data("force_end"))
        self.record_force_btn.clicked.connect(lambda: self._record_data("force_value"))
        self.start_shoulder_btn.clicked.connect(lambda: self._record_data("shoulder_start"))
        self.end_shoulder_btn.clicked.connect(lambda: self._record_data("shoulder_end"))
        self.start_hip_btn.clicked.connect(lambda: self._record_data("hip_start"))
        self.end_hip_btn.clicked.connect(lambda: self._record_data("hip_end"))
        
    def _on_stage_changed(self, index):
        """处理阶段切换"""
        new_stage = index + 1
        self._show_stage(new_stage)
        self.stage_changed.emit(new_stage)
        
    def _show_stage(self, stage):
        """显示指定阶段的控制面板"""
        self.stage1_group.setVisible(stage == 1)
        self.stage2_group.setVisible(stage == 2)
        self.stage3_group.setVisible(stage == 3)
        self.current_stage = stage
        
    def _record_data(self, record_type):
        """记录数据
        
        Args:
            record_type: 记录类型
        """
        # 发送记录信号
        self.record_signal.emit(f"stage{self.current_stage}_{record_type}", [])
        
        # 记录事件数据
        if f"stage{self.current_stage}" not in self.recording_data:
            self.recording_data[f"stage{self.current_stage}"] = {}
            
        self.recording_data[f"stage{self.current_stage}"][record_type] = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sensor_data": []
        }
        
    def _change_save_path(self):
        """更改保存路径"""
        new_path = QFileDialog.getExistingDirectory(
            self, "选择保存目录", self.save_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if new_path:
            self.save_path = new_path
            self.path_label.setText(self.save_path)
        
    def save_records(self, file_name=None):
        """保存记录数据（修复版：保存所有记录，不覆盖）
        
        Args:
            file_name: 文件名（可选）
        """
        if not file_name:
            file_name = f"training_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        file_path = os.path.join(self.save_path, file_name)
        
        # 创建详细的DataFrame
        records = []
        for stage in range(1, 5):  # 支持4个阶段
            stage_data = self.recording_data.get(f"stage{stage}", {})
            for unique_key, data in stage_data.items():
                # 解析记录类型
                record_type = data.get("record_type", unique_key.split("_")[0])
                
                # 基本记录信息
                record = {
                    "阶段": stage,
                    "记录唯一键": unique_key,
                    "记录类型": record_type,
                    "时间戳": data.get("timestamp", ""),
                    "传感器数据": json.dumps(data.get("sensor_data", [])),
                    "数据点数量": len(data.get("sensor_data", []))
                }
                
                # 添加额外数据
                additional_data = data.get("additional_data", {})
                for key, value in additional_data.items():
                    if isinstance(value, (list, dict)):
                        record[f"额外_{key}"] = json.dumps(value)
                    else:
                        record[f"额外_{key}"] = str(value)
                
                records.append(record)
        
        # 按时间戳排序
        records.sort(key=lambda x: x["时间戳"])
        
        df = pd.DataFrame(records)
        
        # 创建多个工作表
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # 主记录表
            df.to_excel(writer, sheet_name='训练记录总览', index=False)
            
            # 按阶段分别保存
            for stage in range(1, 5):
                stage_records = [r for r in records if r["阶段"] == stage]
                if stage_records:
                    stage_df = pd.DataFrame(stage_records)
                    stage_df.to_excel(writer, sheet_name=f'阶段{stage}详情', index=False)
        
        print(f"训练记录已保存到: {file_path}")
        print(f"总计记录数: {len(records)}")
        return file_path
        
    def add_record_data(self, record_type, sensor_data):
        """添加记录数据（修复版：支持多次记录，避免覆盖）
        
        Args:
            record_type: 记录类型
            sensor_data: 传感器数据
        """
        if f"stage{self.current_stage}" not in self.recording_data:
            self.recording_data[f"stage{self.current_stage}"] = {}
        
        # 修复：为每次记录创建唯一的键，避免覆盖
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 精确到毫秒
        unique_record_key = f"{record_type}_{timestamp}"
        
        # 创建新的记录条目
        self.recording_data[f"stage{self.current_stage}"][unique_record_key] = {
            "record_type": record_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "sensor_data": [],
            "additional_data": {}
        }
        
        # 处理传感器数据
        if isinstance(sensor_data, dict):
            # 如果是字典格式（包含额外信息）
            raw_data = sensor_data.get('raw_sensor_data', [])
            self.recording_data[f"stage{self.current_stage}"][unique_record_key]["sensor_data"] = raw_data
            self.recording_data[f"stage{self.current_stage}"][unique_record_key]["additional_data"] = {
                k: v for k, v in sensor_data.items() if k != 'raw_sensor_data'
            }
        elif isinstance(sensor_data, (list, tuple)):
            # 如果是列表格式
            self.recording_data[f"stage{self.current_stage}"][unique_record_key]["sensor_data"] = list(sensor_data)
        else:
            # 尝试转换其他格式
            try:
                self.recording_data[f"stage{self.current_stage}"][unique_record_key]["sensor_data"] = list(sensor_data)
            except Exception as e:
                print(f"无法添加传感器数据: {e}")
                return
        
        # 实时更新UI显示
        self._update_record_display(unique_record_key)
        
        # 自动保存标准文件（如果是完成阶段事件）
        if "完成阶段" in record_type or "矫正完成" in record_type:
            self._save_standard_file(unique_record_key)
        
        print(f"已添加记录: {unique_record_key} (阶段{self.current_stage})")
        
    def set_stage(self, stage):
        """设置当前阶段
        
        Args:
            stage: 阶段编号
        """
        self.current_stage = stage
        self.stage_combo.setCurrentIndex(stage - 1)  # 更新下拉菜单
        self._show_stage(stage)
    
    def _update_record_display(self, unique_record_key):
        """实时更新记录显示
        
        Args:
            unique_record_key: 唯一记录键
        """
        try:
            stage_data = self.recording_data.get(f"stage{self.current_stage}", {})
            record_data = stage_data.get(unique_record_key, {})
            
            if not record_data:
                return
            
            # 格式化显示文本
            record_type = record_data.get("record_type", "未知")
            timestamp = record_data.get("timestamp", "")
            sensor_data = record_data.get("sensor_data", [])
            additional_data = record_data.get("additional_data", {})
            
            display_text = f"[{timestamp}] 阶段{self.current_stage} - {record_type}\n"
            
            if sensor_data:
                if len(sensor_data) > 6:
                    display_text += f"  传感器数据: {sensor_data[:6]}...\n"
                else:
                    display_text += f"  传感器数据: {sensor_data}\n"
            
            # 显示额外数据
            for key, value in additional_data.items():
                if key in ['sensor_weights', 'error_range', 'spine_type']:
                    display_text += f"  {key}: {value}\n"
            
            display_text += "─" * 50 + "\n"
            
            # 添加到显示区域
            self.record_display.append(display_text)
            
            # 自动滚动到底部
            self.record_display.verticalScrollBar().setValue(
                self.record_display.verticalScrollBar().maximum()
            )
            
        except Exception as e:
            print(f"更新记录显示失败: {e}")
    
    def _save_standard_file(self, unique_record_key):
        """自动保存标准文件（用于第三个tab页的病人训练）
        
        Args:
            unique_record_key: 唯一记录键
        """
        try:
            stage_data = self.recording_data.get(f"stage{self.current_stage}", {})
            record_data = stage_data.get(unique_record_key, {})
            
            if not record_data:
                return
            
            # 创建标准文件目录
            standard_path = os.path.join(self.save_path, "standard_files")
            if not os.path.exists(standard_path):
                os.makedirs(standard_path)
            
            # 生成标准文件名（包含时间戳避免覆盖）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            standard_file = os.path.join(standard_path, f"standard_stage{self.current_stage}_{timestamp}.json")
            
            # 准备标准数据
            standard_data = {
                "stage": self.current_stage,
                "record_type": record_data.get("record_type", ""),
                "timestamp": record_data.get("timestamp", ""),
                "sensor_data": record_data.get("sensor_data", []),
                "additional_data": record_data.get("additional_data", {}),
                "file_version": "1.0",
                "created_for_patient_training": True
            }
            
            # 保存标准文件
            with open(standard_file, 'w', encoding='utf-8') as f:
                json.dump(standard_data, f, ensure_ascii=False, indent=2)
            
            print(f"标准文件已保存: {standard_file}")
            
            # 同时保存最新的标准文件（用于第三个tab页调用）
            latest_standard_file = os.path.join(standard_path, f"latest_standard_stage{self.current_stage}.json")
            with open(latest_standard_file, 'w', encoding='utf-8') as f:
                json.dump(standard_data, f, ensure_ascii=False, indent=2)
            
            print(f"最新标准文件已更新: {latest_standard_file}")
            
        except Exception as e:
            print(f"保存标准文件失败: {e}")
    
    def get_latest_standard_file(self, stage):
        """获取指定阶段的最新标准文件路径
        
        Args:
            stage: 阶段编号
            
        Returns:
            str: 标准文件路径，如果不存在则返回None
        """
        try:
            standard_path = os.path.join(self.save_path, "standard_files")
            latest_file = os.path.join(standard_path, f"latest_standard_stage{stage}.json")
            
            if os.path.exists(latest_file):
                return latest_file
            else:
                return None
                
        except Exception as e:
            print(f"获取最新标准文件失败: {e}")
            return None
    
    def clear_records(self):
        """清空所有记录"""
        self.recording_data = {}
        self.record_display.clear()
        print("所有训练记录已清空")
    
    def get_record_count(self):
        """获取记录总数"""
        total_count = 0
        for stage_data in self.recording_data.values():
            total_count += len(stage_data)
        return total_count