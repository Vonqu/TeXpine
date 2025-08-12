#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
脊柱曲率控件显示和信号连接测试
===============================

验证blue_curvature控件是否正确显示和连接信号
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt5.QtCore import pyqtSlot

# 导入相关模块
from block_visualization.block_control_panel import BlockControlPanel
from block_visualization.blocks_visualizer import BlocksVisualizer

class TestWindow(QMainWindow):
    """测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("脊柱曲率控件测试")
        self.setGeometry(100, 100, 1200, 700)
        
        # 创建中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 状态标签
        self.status_label = QLabel("状态：等待测试...")
        layout.addWidget(self.status_label)
        
        # 创建控制面板
        self.control_panel = BlockControlPanel(sensor_count=5)
        layout.addWidget(self.control_panel)
        
        # 创建积木可视化器
        self.visualizer = BlocksVisualizer()
        layout.addWidget(self.visualizer)
        
        # 连接信号
        self.connect_signals()
        
        # 添加测试按钮
        test_button = QPushButton("手动设置脊柱曲率值")
        test_button.clicked.connect(self.test_manual_value)
        layout.addWidget(test_button)
        
        print("测试窗口初始化完成")
        print(f"blue_curvature控件是否可见: {self.control_panel.blue_curvature.isVisible()}")
    
    def connect_signals(self):
        """连接信号"""
        # 连接脊柱曲率信号
        self.control_panel.blue_curvature.value_changed.connect(self.on_blue_curvature_changed)
        print("已连接blue_curvature.value_changed信号")
    
    @pyqtSlot(float)
    def on_blue_curvature_changed(self, value):
        """响应脊柱曲率变更"""
        self.visualizer.blue_blocks_curvature = value
        self.visualizer.update()
        
        self.status_label.setText(f"脊柱曲率更新: {value:.3f}")
        print(f"收到脊柱曲率信号: {value:.3f}")
    
    def test_manual_value(self):
        """手动测试设置值"""
        # 手动设置一些传感器数据
        controller = self.control_panel.blue_curvature
        
        # 模拟选中第一个传感器
        if hasattr(controller, 'sensor_checkboxes') and len(controller.sensor_checkboxes) > 0:
            controller.sensor_checkboxes[0].setChecked(True)
            controller.weight_spinboxes[0].setValue(1.0)
            controller.original_value_spins[0].setValue(10.0)
            controller.rotate_best_value_spins[0].setValue(0.0)
            
            # 模拟传感器数据
            test_sensor_data = [0, 5.0, 0, 0, 0, 0]  # 第一个传感器值为5.0
            controller.process_sensor_data(test_sensor_data)
            
            print("已设置测试数据")
        else:
            print("控件属性不存在，无法设置测试数据")

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    try:
        window = TestWindow()
        window.show()
        
        print("=" * 50)
        print("脊柱曲率控件测试")
        print("=" * 50)
        print("1. 检查blue_curvature控件是否显示")
        print("2. 点击'手动设置脊柱曲率值'按钮进行测试")
        print("3. 观察积木可视化器中的蓝色积木弯曲变化")
        print("4. 控制台会输出信号传递过程")
        print("=" * 50)
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"测试程序启动失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 