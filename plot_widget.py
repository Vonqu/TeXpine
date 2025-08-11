#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
绘图部件模块，处理数据可视化
"""

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QSpinBox, QCheckBox, QGroupBox)
from PyQt5.QtCore import Qt
import time


class SensorPlotWidget(QWidget):
    """传感器数据绘图部件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_curves = []  # 存储所有图表曲线
        self.event_markers = []  # 存储事件标记
        self.start_time = None  # 记录开始时间
        self.last_update_time = 0  # 上次更新时间
        self.update_interval = 0.1  # 更新间隔（秒）
        
        # 初始化UI
        self._init_ui()
        
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 绘图控制组
        control_group = QGroupBox("绘图控制")
        control_layout = QHBoxLayout()
        
        # 滑动窗口设置
        self.window_size_label = QLabel("滑动窗口大小 (秒):")
        self.window_size_spin = QSpinBox()
        self.window_size_spin.setRange(5, 300)
        self.window_size_spin.setValue(30)
        self.window_size_spin.setSingleStep(5)
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        
        control_layout.addWidget(self.window_size_label)
        control_layout.addWidget(self.window_size_spin)
        control_layout.addWidget(self.auto_scroll_check)
        control_layout.addStretch()
        
        control_group.setLayout(control_layout)
        
        # 绘图区域
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', "数值")
        self.plot_widget.setLabel('bottom', "时间 (s)")
        
        # 添加图例
        self.plot_legend = self.plot_widget.addLegend()
        
        # 添加到布局
        layout.addWidget(control_group)
        layout.addWidget(self.plot_widget, 1)  # 1表示伸展因子，让图表占用更多空间
        
    def add_event_marker(self, event_type, timestamp, description=""):
        """添加事件标记
        
        Args:
            event_type: 事件类型
            timestamp: 时间戳
            description: 事件描述
        """
        if not self.start_time:
            self.start_time = timestamp
            
        # 计算相对时间
        relative_time = timestamp - self.start_time
        
        # 创建事件标记线
        marker = pg.InfiniteLine(
            pos=relative_time,
            angle=90,
            pen=pg.mkPen(color='r', width=2, style=Qt.DashLine)
        )
        
        # 添加标记到图表
        self.plot_widget.addItem(marker)
        
        # 添加文本标签
        text = pg.TextItem(
            text=description,
            color='r',
            anchor=(0.5, 1.0)
        )
        text.setPos(relative_time, self.plot_widget.getViewBox().state['viewRange'][1][1])
        self.plot_widget.addItem(text)
        
        # 保存标记引用
        self.event_markers.append((marker, text))
        
        # 限制标记数量，保持最新的100个
        if len(self.event_markers) > 100:
            old_marker, old_text = self.event_markers.pop(0)
            self.plot_widget.removeItem(old_marker)
            self.plot_widget.removeItem(old_text)
            
    def force_next_update(self):
        """强制下次更新，忽略更新频率限制"""
        self._force_next_update = True
        print("设置强制更新标志，下次update_plot将立即执行")
            
    def clear_plot(self):
        """清除图表"""
        self.plot_widget.clear()
        self.plot_curves = []
        self.event_markers = []
        self.plot_legend = self.plot_widget.addLegend()
        self.start_time = None
        
    def setup_curves(self, num_sensors, colors, names=None):
        """设置曲线
        
        Args:
            num_sensors: 传感器数量
            colors: 颜色列表或字符串
            names: 名称列表，若为None则使用默认名称
        """
        self.clear_plot()
        
        # 若colors是单个颜色字符串，转为列表
        if isinstance(colors, str):
            colors = [colors] * num_sensors
            
        # 确保颜色列表足够长
        while len(colors) < num_sensors:
            colors.extend(colors[:num_sensors-len(colors)])
            
        # 为每个传感器创建一条曲线
        for i in range(num_sensors):
            name = names[i] if names and i < len(names) else f"sensor {i+1}"
            pen = pg.mkPen(color=colors[i], width=2)
            curve = self.plot_widget.plot([], [], pen=pen, name=name)
            self.plot_curves.append(curve)
            
    def update_plot(self, data, auto_scroll=None, window_size=None):
        """更新图表显示
        
        Args:
            data: 数据数组，第一列为时间戳
            auto_scroll: 是否自动滚动，若为None则使用自身设置
            window_size: 滑动窗口大小，若为None则使用自身设置
        """
        if not data or len(data) == 0:
            print("警告：没有数据可显示")
            return
            
        # 检查是否需要更新（限制更新频率）
        # 注意：在关键事件（如完成阶段）时，应该立即更新，不受频率限制
        current_time = time.time()
        # 如果不是强制更新且未到更新间隔，则跳过
        force_update = getattr(self, '_force_next_update', False)
        if not force_update and current_time - self.last_update_time < self.update_interval:
            return
        self.last_update_time = current_time
        # 重置强制更新标志
        if force_update:
            self._force_next_update = False
            
        # 使用自身设置还是传入参数
        if auto_scroll is None:
            auto_scroll = self.auto_scroll_check.isChecked()
        if window_size is None:
            window_size = self.window_size_spin.value()
        
        try:
            # 准备数据
            data_array = np.array(data)
            times = data_array[:, 0]  # 第一列是时间戳
            
            # 检查数据有效性
            if len(times) == 0:
                print("警告：时间戳数据为空")
                return
                
            if len(self.plot_curves) == 0:
                print("警告：没有配置曲线")
                return
                
            # 应用滑动窗口
            current_time = times[-1] if len(times) > 0 else 0
            
            if auto_scroll and len(times) > 0:
                # 只显示窗口大小范围内的数据
                mask = times >= (current_time - window_size)
                visible_data = data_array[mask]
                
                if len(visible_data) > 0:
                    visible_times = visible_data[:, 0]
                    
                    # 设置x轴范围
                    self.plot_widget.setXRange(current_time - window_size, current_time)
                    
                    # 更新每个传感器的曲线
                    for i, curve in enumerate(self.plot_curves):
                        if i < visible_data.shape[1] - 1:  # -1是因为第一列是时间戳
                            sensor_data = visible_data[:, i + 1]  # +1是因为第一列是时间戳
                            curve.setData(visible_times, sensor_data)
                            # print(f"更新曲线 {i}: {len(visible_times)} 个数据点")
            else:
                # 显示所有数据
                for i, curve in enumerate(self.plot_curves):
                    if i < data_array.shape[1] - 1:  # -1是因为第一列是时间戳
                        sensor_data = data_array[:, i + 1]  # +1是因为第一列是时间戳
                        curve.setData(times, sensor_data)
                        # print(f"更新曲线 {i}: {len(times)} 个数据点")
                        
                # 如果不是自动滚动模式，则适应所有数据
                if len(times) > 0:
                    self.plot_widget.setXRange(times[0], times[-1])
                    
            # 强制重绘
            self.plot_widget.replot()
            
        except Exception as e:
            print(f"更新图表失败: {e}")
            import traceback
            traceback.print_exc()
            
    def set_curve_visibility(self, index, visible):
        """设置曲线可见性
        
        Args:
            index: 曲线索引
            visible: 是否可见
        """
        if 0 <= index < len(self.plot_curves):
            self.plot_curves[index].setVisible(visible)
            
    def set_curve_color(self, index, color):
        """设置曲线颜色
        
        Args:
            index: 曲线索引
            color: 颜色
        """
        if 0 <= index < len(self.plot_curves):
            pen = pg.mkPen(color=color, width=2)
            self.plot_curves[index].setPen(pen)
            
    def set_curve_name(self, index, name):
        """设置曲线名称
        
        Args:
            index: 曲线索引
            name: 名称
        """
        if 0 <= index < len(self.plot_curves):
            # 这里需要更新图例，但pyqtgraph不支持直接更新曲线名称
            # 因此需要重新创建图例
            self.update_legend()
            
    def update_legend(self, curve_data=None):
        """更新图例
        
        Args:
            curve_data: 曲线数据字典列表，包含name, pen, visible等字段
                       若为None则使用当前曲线数据
        """
        # 首先清除图表上的所有项目，这会同时清除图例
        self.plot_widget.clear()
        
        # 如果没有提供curve_data，则从当前曲线获取
        if curve_data is None:
            curve_data = []
            for i, curve in enumerate(self.plot_curves):
                # 获取曲线的数据和属性
                xData, yData = curve.getData()
                pen = curve.opts['pen']
                name = curve.name()
                visible = curve.isVisible()
                
                curve_data.append({
                    'xData': xData,
                    'yData': yData,
                    'pen': pen,
                    'name': name,
                    'visible': visible
                })
        
        # 重新创建图例
        self.plot_legend = self.plot_widget.addLegend()
        
        # 重新创建和配置所有曲线
        self.plot_curves = []
        for data in curve_data:
            curve = self.plot_widget.plot(
                data['xData'], 
                data['yData'], 
                pen=data['pen'], 
                name=data['name']
            )
            curve.setVisible(data['visible'])
            self.plot_curves.append(curve)