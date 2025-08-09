#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据增强模块测试脚本
"""

import numpy as np
import matplotlib.pyplot as plt
from V20.data_enhancement import DataEnhancement

def test_data_enhancement():
    """测试数据增强模块"""
    print("开始测试数据增强模块...")
    
    # 创建测试数据
    num_sensors = 6
    num_points = 1000
    
    # 生成模拟传感器数据（包含噪声和趋势）
    np.random.seed(42)
    test_data = []
    
    for i in range(num_points):
        timestamp = i * 0.01  # 10ms间隔
        sensor_values = []
        
        for j in range(num_sensors):
            # 基础信号 + 噪声 + 趋势
            base_signal = 2500 + 100 * np.sin(2 * np.pi * 0.1 * i)  # 基础信号
            noise = np.random.normal(0, 10)  # 噪声
            trend = 5 * np.sin(2 * np.pi * 0.05 * i)  # 慢速趋势
            
            # 添加一些突变
            if i > 500 and i < 600:
                base_signal += 50 * np.sin(2 * np.pi * 0.5 * i)  # 高频成分
                
            sensor_values.append(base_signal + noise + trend)
            
        test_data.append([timestamp] + sensor_values)
    
    # 创建数据增强模块
    enhancement = DataEnhancement(num_sensors=num_sensors)
    
    # 测试不同的增强方法
    methods = ['motion_and_lock', 'trend', 'local_contrast', 'gradient', 'segment']
    
    plt.figure(figsize=(15, 10))
    
    for i, method in enumerate(methods):
        print(f"\n测试方法: {method}")
        
        # 设置增强参数
        enhancement.set_enhancement_enabled(True)
        enhancement.set_enhancement_method(method)
        
        # 应用增强
        enhanced_data = []
        for data_point in test_data:
            enhanced_point = enhancement.enhance_data(data_point)
            enhanced_data.append(enhanced_point)
        
        # 绘制结果
        plt.subplot(2, 3, i + 1)
        
        # 原始数据（第一个传感器）
        original_sensor1 = [point[1] for point in test_data]
        enhanced_sensor1 = [point[1] for point in enhanced_data]
        
        plt.plot(original_sensor1, label='原始数据', alpha=0.7)
        plt.plot(enhanced_sensor1, label='增强数据', linewidth=2)
        plt.title(f'{method}')
        plt.xlabel('数据点')
        plt.ylabel('传感器值')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        print(f"  ✓ {method} 增强完成")
    
    # 测试二次滤波
    plt.subplot(2, 3, 6)
    print("\n测试二次滤波...")
    
    enhancement.set_enhancement_enabled(True)
    enhancement.set_enhancement_method('motion_and_lock')
    enhancement.set_second_filter_enabled(True)
    enhancement.set_second_filter_method('kalman')
    
    enhanced_with_second_filter = []
    for data_point in test_data:
        enhanced_point = enhancement.enhance_data(data_point)
        enhanced_with_second_filter.append(enhanced_point)
    
    enhanced_sensor1_with_filter = [point[1] for point in enhanced_with_second_filter]
    
    plt.plot(original_sensor1, label='原始数据', alpha=0.7)
    plt.plot(enhanced_sensor1_with_filter, label='增强+二次滤波', linewidth=2)
    plt.title('增强+二次滤波')
    plt.xlabel('数据点')
    plt.ylabel('传感器值')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    print("  ✓ 二次滤波测试完成")
    
    plt.tight_layout()
    plt.savefig('enhancement_test_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("\n测试完成！结果已保存为 enhancement_test_results.png")

def test_parameter_control():
    """测试参数控制功能"""
    print("\n开始测试参数控制功能...")
    
    enhancement = DataEnhancement(num_sensors=3)
    
    # 测试获取参数
    params = enhancement.get_enhancement_params()
    print("默认参数:")
    print(f"  启用状态: {params['enabled']}")
    print(f"  方法: {params['method']}")
    print(f"  运动检测参数: {params['motion_and_lock']}")
    print(f"  二次滤波: {params['second_filter']}")
    
    # 测试设置参数
    enhancement.set_enhancement_enabled(True)
    enhancement.set_enhancement_method('motion_and_lock')
    enhancement.set_motion_and_lock_params(
        diff_window=10,
        motion_thresh=0.02,
        motion_gain=3.0,
        lock_smoothing=0.98
    )
    
    params = enhancement.get_enhancement_params()
    print("\n修改后参数:")
    print(f"  启用状态: {params['enabled']}")
    print(f"  方法: {params['method']}")
    print(f"  运动检测参数: {params['motion_and_lock']}")
    
    print("  ✓ 参数控制测试完成")

if __name__ == "__main__":
    test_data_enhancement()
    test_parameter_control()
    print("\n所有测试完成！") 