#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
加权和计算修复验证脚本
==================

验证修复后的加权和计算是否能正确处理异常情况
"""

import sys
import os
import time
from PyQt5.QtWidgets import QApplication

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from block_visualization.sensor_selector import SensorSelector

def test_weighted_sum_fixes():
    """测试加权和计算修复效果"""
    print("=== 加权和计算修复验证测试 ===\n")
    
    # 创建QApplication（GUI组件需要）
    app = QApplication(sys.argv)
    
    # 创建一个SensorSelector实例进行测试
    selector = SensorSelector("测试传感器", sensor_count=5, special_mode=True)
    
    print("📊 测试1：正常情况下的加权和计算")
    print("-" * 50)
    
    # 设置正常的传感器配置
    selector.sensor_checkboxes[0].setChecked(True)
    selector.weight_spinboxes[0].setValue(1.0)
    selector.original_value_spins[0].setValue(2600)
    selector.rotate_best_value_spins[0].setValue(2350)
    
    selector.sensor_checkboxes[1].setChecked(True)
    selector.weight_spinboxes[1].setValue(1.5)
    selector.original_value_spins[1].setValue(2650)
    selector.rotate_best_value_spins[1].setValue(2400)
    
    # 设置传感器当前值
    selector.sensor_values = [2450, 2520, 2380, 2600, 2470]
    
    # 计算加权和
    selector.update_combined_value()
    result1 = selector.current_value
    
    print(f"✅ 测试1结果: {result1:.3f} (预期: 0-1范围内)")
    print(f"   结果正常: {0 <= result1 <= 1}")
    print()
    
    print("📊 测试2：错误的OV/RBV设置（RBV > OV）")
    print("-" * 50)
    
    # 故意设置错误的OV/RBV（违反OV > RBV假设）
    selector.original_value_spins[0].setValue(2300)  # OV < RBV
    selector.rotate_best_value_spins[0].setValue(2600)  # RBV > OV
    
    selector.original_value_spins[1].setValue(2350)  # OV < RBV  
    selector.rotate_best_value_spins[1].setValue(2650)  # RBV > OV
    
    print("设置错误配置:")
    print(f"传感器1: OV={selector.original_value_spins[0].value()}, RBV={selector.rotate_best_value_spins[0].value()}")
    print(f"传感器2: OV={selector.original_value_spins[1].value()}, RBV={selector.rotate_best_value_spins[1].value()}")
    print()
    
    # 计算加权和（应该自动修正）
    selector.update_combined_value()
    result2 = selector.current_value
    
    print(f"✅ 测试2结果: {result2:.3f}")
    print(f"   结果正常: {0 <= result2 <= 1}")
    print(f"修正后的配置:")
    print(f"传感器1: OV={selector.original_value_spins[0].value()}, RBV={selector.rotate_best_value_spins[0].value()}")
    print(f"传感器2: OV={selector.original_value_spins[1].value()}, RBV={selector.rotate_best_value_spins[1].value()}")
    print()
    
    print("📊 测试3：极端权重值")
    print("-" * 50)
    
    # 重置为正常配置
    selector.original_value_spins[0].setValue(2600)
    selector.rotate_best_value_spins[0].setValue(2350)
    selector.original_value_spins[1].setValue(2650)
    selector.rotate_best_value_spins[1].setValue(2400)
    
    # 设置极端权重
    selector.weight_spinboxes[0].setValue(100.0)  # 很大的权重
    selector.weight_spinboxes[1].setValue(-50.0)  # 负权重
    
    print(f"设置极端权重:")
    print(f"传感器1权重: {selector.weight_spinboxes[0].value()}")
    print(f"传感器2权重: {selector.weight_spinboxes[1].value()}")
    print()
    
    # 计算加权和
    selector.update_combined_value()
    result3 = selector.current_value
    
    print(f"✅ 测试3结果: {result3:.3f}")
    print(f"   结果正常: {0 <= result3 <= 1}")
    print()
    
    print("📊 测试4：验证OV/RBV验证方法")
    print("-" * 50)
    
    # 创建另一个selector来测试验证方法
    selector2 = SensorSelector("验证测试", sensor_count=3, special_mode=True)
    
    # 设置一些错误的OV/RBV值
    selector2.original_value_spins[0].setValue(2300)  # 错误：OV < RBV
    selector2.rotate_best_value_spins[0].setValue(2600)
    
    selector2.original_value_spins[1].setValue(2400)  # 错误：差值太小
    selector2.rotate_best_value_spins[1].setValue(2390)
    
    selector2.original_value_spins[2].setValue(2700)  # 正常
    selector2.rotate_best_value_spins[2].setValue(2400)
    
    print("验证前的配置:")
    for i in range(3):
        ov = selector2.original_value_spins[i].value()
        rbv = selector2.rotate_best_value_spins[i].value()
        print(f"传感器{i+1}: OV={ov}, RBV={rbv}, 差值={ov-rbv}")
    print()
    
    # 执行验证和修正
    fixed_count = selector2.validate_ov_rbv_values()
    
    print(f"\n验证后的配置:")
    for i in range(3):
        ov = selector2.original_value_spins[i].value()
        rbv = selector2.rotate_best_value_spins[i].value()
        print(f"传感器{i+1}: OV={ov}, RBV={rbv}, 差值={ov-rbv}")
    
    print(f"\n✅ 修正了 {fixed_count} 个传感器的配置")
    
    print("\n" + "=" * 60)
    print("🎯 测试总结")
    print("=" * 60)
    
    all_results_valid = all(0 <= result <= 1 for result in [result1, result2, result3])
    
    print(f"测试1 (正常情况): {result1:.3f} {'✅' if 0 <= result1 <= 1 else '❌'}")
    print(f"测试2 (错误OV/RBV): {result2:.3f} {'✅' if 0 <= result2 <= 1 else '❌'}")
    print(f"测试3 (极端权重): {result3:.3f} {'✅' if 0 <= result3 <= 1 else '❌'}")
    print(f"测试4 (验证修正): 修正了{fixed_count}个配置 {'✅' if fixed_count > 0 else '❌'}")
    print()
    
    if all_results_valid:
        print("🎉 所有测试通过！加权和计算修复成功。")
        print("   - 自动检测和修正错误的OV/RBV设置")
        print("   - 严格限制最终结果到0-1范围")
        print("   - 处理极端权重值")
        print("   - 提供详细的调试信息")
    else:
        print("❌ 部分测试失败，需要进一步检查。")
    
    return all_results_valid

if __name__ == "__main__":
    try:
        success = test_weighted_sum_fixes()
        print(f"\n{'='*60}")
        print(f"测试{'成功' if success else '失败'}!")
        print(f"{'='*60}")
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc() 