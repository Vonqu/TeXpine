#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
训练报告标签页模块
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTableWidget, QTableWidgetItem,
                            QHeaderView, QMessageBox, QSplitter, QGroupBox,
                            QProgressBar)
from PyQt5.QtCore import Qt
import pandas as pd
import os
import pyqtgraph as pg
import numpy as np

class TrainingReportTab(QWidget):
    """训练报告标签页类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recording_data = {}  # 训练记录数据字典
        self.plot_curves = {}  # 存储每个阶段的曲线
        self.event_markers = {}  # 存储事件标记
        self._init_ui()
        
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 创建上半部分：数据表格和积木可视化
        top_layout = QHBoxLayout()
        
        # 左侧：数据表格
        table_group = QGroupBox("训练阶段记录")
        table_layout = QVBoxLayout()
        
        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)  # 增加一列用于显示阈值
        self.table.setHorizontalHeaderLabels(["训练阶段", "开始时间", "结束时间", "持续时间", "事件记录"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        
        # 右侧：积木可视化
        visualizer_group = QGroupBox("脊柱积木图形示例")
        visualizer_layout = QVBoxLayout()
        
        # 创建积木可视化器
        self.visualizer = BlocksVisualizer()
        self.visualizer.setMinimumSize(250, 200)
        visualizer_layout.addWidget(self.visualizer)
        
        visualizer_group.setLayout(visualizer_layout)
        
        # 添加到上半部分布局
        top_layout.addWidget(table_group, 2)
        top_layout.addWidget(visualizer_group, 1)
        
        # 创建上半部分容器
        top_widget = QWidget()
        top_widget.setLayout(top_layout)
        
        # 创建下半部分：图表显示
        plot_group = QGroupBox("传感器数据曲线")
        plot_layout = QVBoxLayout()
        
        # 创建图表
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')  # 白色背景
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', '传感器值')
        self.plot_widget.setLabel('bottom', '时间 (秒)')
        
        # 添加图例
        self.plot_widget.addLegend()
        
        # 添加点击事件处理
        self.plot_widget.scene().sigMouseClicked.connect(self._handle_plot_click)
        
        plot_layout.addWidget(self.plot_widget)
        plot_group.setLayout(plot_layout)
        
        # 添加到分割器
        splitter.addWidget(top_widget)
        splitter.addWidget(plot_group)
        
        # 创建按钮
        button_layout = QHBoxLayout()
        self.export_btn = QPushButton("导出报告")
        self.export_btn.clicked.connect(self.export_report)
        self.export_btn.setEnabled(False)  # 初始禁用导出按钮
        
        button_layout.addStretch()
        button_layout.addWidget(self.export_btn)
        
        # 创建当前动作信息区域
        current_action_layout = QHBoxLayout()
        self.current_action_label = QLabel("当前动作：无")
        self.duration_label = QLabel("持续时间：0秒")
        current_action_layout.addWidget(self.current_action_label)
        current_action_layout.addWidget(self.duration_label)
        
        # 创建动作得分表格
        self.score_table = QTableWidget()
        self.score_table.setColumnCount(3)
        self.score_table.setHorizontalHeaderLabels(["动作", "得分", "完成度"])
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        
        # 添加到主布局
        layout.addWidget(splitter)
        layout.addLayout(button_layout)
        layout.addLayout(current_action_layout)
        layout.addWidget(self.score_table)
        layout.addWidget(self.progress_bar)
        
    def _handle_plot_click(self, event):
        """处理图表点击事件
        
        Args:
            event: 点击事件对象
        """
        if event.button() == Qt.LeftButton:
            # 获取点击位置的时间戳
            pos = event.pos()
            timestamp = self.plot_widget.getViewBox().mapSceneToView(pos).x()
            
            # 在点击位置添加事件标记
            self._add_event_marker(timestamp, "用户标记")
        
    def _add_event_marker(self, timestamp, event_name):
        """添加事件标记
        
        Args:
            timestamp: 时间戳
            event_name: 事件名称
        """
        # 创建垂直标记线
        marker = pg.InfiniteLine(
            pos=timestamp,
            angle=90,
            pen=pg.mkPen(color='r', style=Qt.DashLine)
        )
        self.plot_widget.addItem(marker)
        
        # 添加事件标签
        text = pg.TextItem(
            text=event_name,
            color='r',
            anchor=(0, 0)
        )
        text.setPos(timestamp, self.plot_widget.getViewBox().state['viewRange'][1][1])
        self.plot_widget.addItem(text)
        
        # 存储标记引用
        if timestamp not in self.event_markers:
            self.event_markers[timestamp] = []
        self.event_markers[timestamp].extend([marker, text])
        
    def update_data(self, recording_data):
        """更新训练数据
        
        Args:
            recording_data: 训练记录数据字典
        """
        if recording_data:
            self.recording_data = recording_data
            self._update_table()
            self._update_plot()
            self._update_visualizer()
            self.export_btn.setEnabled(True)  # 启用导出按钮
            
            # 添加事件标记
            for phase_name, phase_data in recording_data.items():
                for event_type, event_data in phase_data.items():
                    if isinstance(event_data, dict) and 'timestamp' in event_data:
                        timestamp = event_data['timestamp']
                        if isinstance(timestamp, str):
                            # 将字符串时间戳转换为数值
                            from datetime import datetime
                            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").timestamp()
                        self._add_event_marker(timestamp, f"{phase_name}-{event_type}")
        
    def _update_table(self):
        """更新表格显示"""
        if not self.recording_data:
            return
            
        self.table.setRowCount(0)  # 清空表格
        
        # 遍历所有训练阶段
        for phase_name, phase_data in self.recording_data.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 添加训练阶段
            self.table.setItem(row, 0, QTableWidgetItem(phase_name))
            
            # 添加开始时间
            start_time = phase_data.get('start_time', '')
            self.table.setItem(row, 1, QTableWidgetItem(str(start_time)))
            
            # 添加结束时间
            end_time = phase_data.get('end_time', '')
            self.table.setItem(row, 2, QTableWidgetItem(str(end_time)))
            
            # 计算并添加持续时间
            if start_time and end_time:
                duration = end_time - start_time
                duration_str = f"{duration:.2f}秒"
            else:
                duration_str = "未完成"
            self.table.setItem(row, 3, QTableWidgetItem(duration_str))
            
            # 添加事件记录
            events = []
            for event_type, event_data in phase_data.items():
                if isinstance(event_data, dict) and 'timestamp' in event_data:
                    events.append(f"{event_type}: {event_data['timestamp']}")
            event_str = "\n".join(events) if events else "无事件记录"
            self.table.setItem(row, 4, QTableWidgetItem(event_str))
            
    def _update_plot(self):
        """更新图表显示"""
        self.plot_widget.clear()
        self.event_markers.clear()  # 清除事件标记
        
        # 为每个阶段创建不同颜色的曲线
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
        
        for i, (phase_name, phase_data) in enumerate(self.recording_data.items()):
            if not isinstance(phase_data, dict):
                continue
                
            # 获取传感器数据
            sensor_data = []
            for event_type, event_data in phase_data.items():
                if isinstance(event_data, dict) and 'sensor_data' in event_data:
                    sensor_data.extend(event_data['sensor_data'])
            
            if not sensor_data:
                continue
                
            # 提取时间戳和传感器数据
            timestamps = [data[0] for data in sensor_data]
            sensor_values = np.array([data[1:] for data in sensor_data])
            
            # 为每个传感器创建曲线
            for sensor_idx in range(sensor_values.shape[1]):
                color = colors[(i + sensor_idx) % len(colors)]
                # 确保数据形状正确
                sensor_data = sensor_values[:, sensor_idx]
                if len(sensor_data) > 0:
                    curve = self.plot_widget.plot(
                        x=timestamps,
                        y=sensor_data,
                        name=f"{phase_name}-传感器{sensor_idx+1}",
                        pen=color
                    )
                    
                    # 存储曲线引用
                    if phase_name not in self.plot_curves:
                        self.plot_curves[phase_name] = []
                    self.plot_curves[phase_name].append(curve)
                
            # 添加事件标记
            for event_type, event_data in phase_data.items():
                if isinstance(event_data, dict) and 'timestamp' in event_data:
                    timestamp = event_data['timestamp']
                    if isinstance(timestamp, str):
                        # 将字符串时间戳转换为数值
                        from datetime import datetime
                        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").timestamp()
                    self._add_event_marker(timestamp, f"{phase_name}-{event_type}")
        
    def _update_visualizer(self):
        """更新积木可视化效果"""
        if not self.recording_data:
            return
            
        # 遍历所有训练阶段
        for phase_name, phase_data in self.recording_data.items():
            if not isinstance(phase_data, dict):
                continue
                
            # 根据阶段名称和事件类型更新可视化效果
            if phase_name == "阶段1":  # 骨盆前后翻转
                # 获取开始训练和完成阶段的事件数据
                start_data = phase_data.get("开始训练", {})
                end_data = phase_data.get("完成阶段", {})
                
                if start_data and end_data:
                    # 获取传感器数据
                    start_sensor_data = start_data.get("sensor_data", [0])[0]
                    end_sensor_data = end_data.get("sensor_data", [0])[0]
                    current_sensor_data = phase_data.get("current_sensor_data", start_sensor_data)
                    
                    # 计算当前值与目标值的比例
                    if end_sensor_data != start_sensor_data:
                        progress = (current_sensor_data - start_sensor_data) / (end_sensor_data - start_sensor_data)
                        progress = max(0.0, min(1.0, progress))  # 限制在0-1范围内
                        self.visualizer.gray_block_rotation = progress
                    
            elif phase_name == "阶段2":  # 脊柱曲率矫正
                # 获取开始矫正和矫正完成的事件数据
                start_data = phase_data.get("开始矫正", {})
                end_data = phase_data.get("矫正完成", {})
                
                if start_data and end_data:
                    # 获取传感器数据
                    start_sensor_data = start_data.get("sensor_data", [0])[0]
                    end_sensor_data = end_data.get("sensor_data", [0])[0]
                    current_sensor_data = phase_data.get("current_sensor_data", start_sensor_data)
                    
                    # 计算当前值与目标值的比例
                    if end_sensor_data != start_sensor_data:
                        progress = (current_sensor_data - start_sensor_data) / (end_sensor_data - start_sensor_data)
                        progress = max(0.0, min(1.0, progress))  # 限制在0-1范围内
                        self.visualizer.blue_blocks_curvature = progress
                    
            elif phase_name == "阶段3":  # 骨盆和肩部倾斜
                # 获取沉髋相关事件数据
                hip_start_data = phase_data.get("开始沉髋", {})
                hip_end_data = phase_data.get("沉髋结束", {})
                
                # 获取沉肩相关事件数据
                shoulder_start_data = phase_data.get("开始沉肩", {})
                shoulder_end_data = phase_data.get("沉肩结束", {})
                
                if hip_start_data and hip_end_data:
                    # 获取传感器数据
                    start_sensor_data = hip_start_data.get("sensor_data", [0])[0]
                    end_sensor_data = hip_end_data.get("sensor_data", [0])[0]
                    current_sensor_data = phase_data.get("current_sensor_data", start_sensor_data)
                    
                    # 计算当前值与目标值的比例
                    if end_sensor_data != start_sensor_data:
                        progress = (current_sensor_data - start_sensor_data) / (end_sensor_data - start_sensor_data)
                        progress = max(0.0, min(1.0, progress))  # 限制在0-1范围内
                        self.visualizer.gray_block_tilt = progress
                    
                if shoulder_start_data and shoulder_end_data:
                    # 获取传感器数据
                    start_sensor_data = shoulder_start_data.get("sensor_data", [0])[0]
                    end_sensor_data = shoulder_end_data.get("sensor_data", [0])[0]
                    current_sensor_data = phase_data.get("current_sensor_data", start_sensor_data)
                    
                    # 计算当前值与目标值的比例
                    if end_sensor_data != start_sensor_data:
                        progress = (current_sensor_data - start_sensor_data) / (end_sensor_data - start_sensor_data)
                        progress = max(0.0, min(1.0, progress))  # 限制在0-1范围内
                        self.visualizer.green_block_tilt = progress
        
        # 更新可视化效果
        self.visualizer.update()
        
    def export_report(self):
        """导出训练报告"""
        if not self.recording_data:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return
            
        # 获取程序根目录
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 创建 reports 目录（如果不存在）
        reports_dir = os.path.join(app_root, "reports")
        if not os.path.exists(reports_dir):
            try:
                os.makedirs(reports_dir)
            except OSError:
                reports_dir = os.path.expanduser("~")
        
        # 创建DataFrame
        data = []
        for phase_name, phase_data in self.recording_data.items():
            start_time = phase_data.get('start_time', '')
            end_time = phase_data.get('end_time', '')
            duration = end_time - start_time if start_time and end_time else None
            
            # 格式化阈值数据
            threshold_data = phase_data.get('threshold_data', {})
            threshold_str = self._format_threshold_data(threshold_data)
            
            data.append({
                '训练阶段': phase_name,
                '开始时间': start_time,
                '结束时间': end_time,
                '持续时间(秒)': f"{duration:.2f}" if duration else "未完成",
                '阈值记录': threshold_str
            })
            
        df = pd.DataFrame(data)
        
        # 导出到Excel
        try:
            file_path = os.path.join(reports_dir, "训练报告.xlsx")
            df.to_excel(file_path, index=False, engine='openpyxl')
            QMessageBox.information(self, "成功", f"报告已导出到：{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出报告失败：{str(e)}") 