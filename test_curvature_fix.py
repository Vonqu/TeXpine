#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
脊柱曲率矫正阶段数据传输修复验证脚本
===================================

用于验证 sensor_selector 计算的加权和是否正确控制 blue curvature 的可视化
"""

import sys
import time
import random
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QTimer, pyqtSlot

# 导入项目模块
from block_visualization.blocks_tab import BlocksTab

class CurvatureTestWidget(QWidget):
    """脊柱曲率矫正测试界面"""
    
    def __init__(self):
        super().__init__()
        self.blocks_tab = None
        self.data_timer = QTimer()
        self.test_data_counter = 0
        self.init_ui()
        self.setup_test()
        
    def init_ui(self):
        """初始化测试界面"""
        self.setWindowTitle("脊柱曲率矫正阶段数据传输测试")
        self.setGeometry(100, 100, 1200, 800)
        
        layout = QVBoxLayout()
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始测试")
        self.start_btn.clicked.connect(self.start_test)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止测试")
        self.stop_btn.clicked.connect(self.stop_test)
        control_layout.addWidget(self.stop_btn)
        
        self.switch_c_btn = QPushButton("切换到C型脊柱")
        self.switch_c_btn.clicked.connect(lambda: self.switch_spine_type('C'))
        control_layout.addWidget(self.switch_c_btn)
        
        self.switch_s_btn = QPushButton("切换到S型脊柱")
        self.switch_s_btn.clicked.connect(lambda: self.switch_spine_type('S'))
        control_layout.addWidget(self.switch_s_btn)
        
        self.stage2_btn = QPushButton("切换到阶段2")
        self.stage2_btn.clicked.connect(lambda: self.switch_stage(2))
        control_layout.addWidget(self.stage2_btn)
        
        layout.addLayout(control_layout)
        
        # 状态显示
        self.status_label = QLabel("测试状态: 未开始")
        layout.addWidget(self.status_label)
        
        # 积木可视化标签页
        self.blocks_tab = BlocksTab(sensor_count=10)
        layout.addWidget(self.blocks_tab)
        
        self.setLayout(layout)
        
    def setup_test(self):
        """设置测试环境"""
        # 设置定时器
        self.data_timer.timeout.connect(self.send_test_data)
        
        # 初始化为阶段2（脊柱曲率矫正阶段）
        self.blocks_tab.set_stage(2)
        
        print("测试环境设置完成")
        
    def start_test(self):
        """开始测试"""
        print("\n=== 开始脊柱曲率矫正数据传输测试 ===")
        
        # 重置计数器
        self.test_data_counter = 0
        
        # 开始发送模拟数据
        self.data_timer.start(100)  # 每100ms发送一次数据
        
        self.status_label.setText("测试状态: 运行中...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
    def stop_test(self):
        """停止测试"""
        print("\n=== 停止脊柱曲率矫正数据传输测试 ===")
        
        self.data_timer.stop()
        
        self.status_label.setText("测试状态: 已停止")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
    def switch_spine_type(self, spine_type):
        """切换脊柱类型"""
        print(f"\n=== 切换脊柱类型到 {spine_type} 型 ===")
        self.blocks_tab.update_spine_type(spine_type)
        self.status_label.setText(f"测试状态: 已切换到{spine_type}型脊柱")
        
    def switch_stage(self, stage):
        """切换阶段"""
        print(f"\n=== 切换到阶段 {stage} ===")
        self.blocks_tab.set_stage(stage)
        self.status_label.setText(f"测试状态: 已切换到阶段{stage}")
        
    def send_test_data(self):
        """发送测试数据"""
        self.test_data_counter += 1
        
        # 生成模拟传感器数据
        timestamp = time.time()
        
        # 生成10个传感器的模拟数据
        # 为了测试脊柱曲率，让某些传感器有明显变化
        sensor_data = []
        for i in range(10):
            if i in [2, 3, 4]:  # 假设这些是脊柱曲率相关的传感器
                # 生成有规律变化的数据来测试曲率计算
                base_value = 2500 + 200 * (i - 2)
                variation = 100 * math.sin(self.test_data_counter * 0.1) * (i - 1)
                sensor_data.append(base_value + variation)
            else:
                # 其他传感器使用相对稳定的随机数据
                sensor_data.append(2500 + random.randint(-50, 50))
        
        # 构造完整的数据包（时间戳 + 传感器数据）
        full_data = [timestamp] + sensor_data
        
        # 发送数据到积木标签页
        self.blocks_tab.process_sensor_data(full_data)
        
        # 每50次打印一次状态
        if self.test_data_counter % 50 == 0:
            spine_type = getattr(self.blocks_tab, 'spine_type', 'C')
            stage = getattr(self.blocks_tab, 'stage', 1)
            print(f"测试进度: 已发送 {self.test_data_counter} 次数据 (脊柱类型: {spine_type}, 阶段: {stage})")
            
            # 获取当前可视化状态
            if hasattr(self.blocks_tab, 'visualizer'):
                blue_curvature = getattr(self.blocks_tab.visualizer, 'blue_blocks_curvature', 0)
                print(f"  当前蓝色积木曲率值: {blue_curvature:.3f}")

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 导入数学模块
    import math
    globals()['math'] = math
    
    # 创建测试窗口
    test_widget = CurvatureTestWidget()
    test_widget.show()
    
    print("脊柱曲率矫正数据传输测试程序启动")
    print("使用说明:")
    print("1. 点击'开始测试'开始发送模拟传感器数据")
    print("2. 点击'切换到C型脊柱'或'切换到S型脊柱'测试不同脊柱类型")
    print("3. 点击'切换到阶段2'确保在脊柱曲率矫正阶段")
    print("4. 观察控制台输出，检查数据传输和信号连接是否正常")
    print("5. 观察积木可视化器中的蓝色积木是否有相应变化")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 