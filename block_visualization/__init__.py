#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
积木可视化模块包初始化文件
========================

此文件定义了积木可视化模块的包结构和对外接口。

模块结构：
blocks_visualization/
├── __init__.py (本文件)
├── blocks_tab_manager.py (管理器主文件)
├── blocks_tab.py (原始积木标签页)
├── patient_blocks_tab.py (患者积木标签页)
├── blocks_visualizer.py (3D可视化)
├── block_control_panel.py (控制面板)
├── sensor_selector.py (传感器选择器)
└── training_recorder.py (训练记录器)

使用方式：
from blocks_visualization import BlocksTabManager
manager = BlocksTabManager(sensor_count=10)
"""

# 导入核心类，使其可以直接从包中导入
from .blocks_tab_manager import BlocksTabManager, create_blocks_visualization_manager, validate_sensor_data
from .patient_blocks_tab import PatientBlocksTab

# 包信息
__version__ = "1.0.0"
__author__ = "Sensor System Team"
__description__ = "智能服装传感器积木可视化模块"

# 对外接口列表
__all__ = [
    'BlocksTabManager',
    'create_blocks_visualization_manager', 
    'validate_sensor_data',
    'PatientBlocksTab'
]