#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置模块，提供全局配置项
"""

import os
import json
from pathlib import Path


class Config:
    """配置类，处理应用程序配置"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        "baud_rate": 115200,
        "default_num_sensors": 3,

        "default_duration": 0,
        "default_window_size": 10,
        "auto_scroll": True,
        "default_colors": ['r', 'g', 'b', 'c', 'm', 'y', 'k'],
        "last_save_directory": str(Path.home()),
        "window_width": 1200,
        "window_height": 800,
        "splitter_ratio": [30, 70],  # 控制面板和图表的比例
                
        # 新增: 数据管理配置
        "enable_temp_file_storage": True,       # 启用临时文件存储
        "memory_data_limit": 5000,              # 内存数据限制
        "auto_backup_interval": 1000,           # 自动备份间隔
        "temp_file_cleanup_on_exit": True,      # 退出时清理临时文件
                
        # 数据保存策略
        "save_strategy": "complete",            # "complete" | "memory_only"
        "backup_enabled": True,                 # 启用自动备份
        
    }
    
    def __init__(self, config_file="settings.json"):
        """初始化配置
        
        Args:
            config_file: 配置文件名
        """
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self.load_config()
        
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # 更新配置，但保留DEFAULT_CONFIG中的任何缺失项
                    self.config.update(loaded_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                # 使用默认配置
                self.config = self.DEFAULT_CONFIG.copy()
        
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
        
    def get(self, key, default=None):
        """获取配置项
        
        Args:
            key: 配置项键名
            default: 默认值，如果键不存在
            
        Returns:
            配置项值
        """
        return self.config.get(key, default)
        
    def set(self, key, value):
        """设置配置项
        
        Args:
            key: 配置项键名
            value: 配置项值
        """
        self.config[key] = value
        
    def update(self, config_dict):
        """批量更新配置
        
        Args:
            config_dict: 配置字典
        """
        self.config.update(config_dict)
        
    def save_window_state(self, width, height, splitter_sizes):
        """保存窗口状态
        
        Args:
            width: 窗口宽度
            height: 窗口高度
            splitter_sizes: 分割器尺寸列表
        """
        self.config["window_width"] = width
        self.config["window_height"] = height
        
        # 计算比例而不是绝对值
        total_size = sum(splitter_sizes)
        if total_size > 0:
            ratio = [int(100 * size / total_size) for size in splitter_sizes]
            self.config["splitter_ratio"] = ratio
            
        self.save_config()
        
    def update_last_directory(self, directory):
        """更新最后使用的目录
        
        Args:
            directory: 目录路径
        """
        self.config["last_save_directory"] = directory
        self.save_config()