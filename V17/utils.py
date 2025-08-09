#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
工具模块，提供各种辅助函数
"""

import os
import pyqtgraph as pg
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtGui import QColor


def get_color_map():
    """获取颜色映射字典
    
    Returns:
        dict: 颜色映射字典
    """
    return {
        'r': 'red',
        'g': 'green',
        'b': 'blue',
        'c': 'cyan',
        'm': 'magenta',
        'y': 'yellow',
        'k': 'black',
        'w': 'white'
    }
    
def color_to_css(color):
    """将pyqtgraph颜色转换为CSS颜色
    
    Args:
        color: 颜色值(字符串或QColor对象)
        
    Returns:
        str: CSS颜色字符串
    """
    if isinstance(color, QColor):
        return color.name()
        
    color_map = get_color_map()
    return color_map.get(color, color)
    
def create_pen(color, width=2):
    """创建pyqtgraph画笔
    
    Args:
        color: 颜色值
        width: 线宽
        
    Returns:
        pg.mkPen: pyqtgraph画笔
    """
    return pg.mkPen(color=color, width=width)
    
def ensure_directory(path):
    """确保目录存在，不存在则创建
    
    Args:
        path: 目录路径
        
    Returns:
        bool: 是否成功确保目录存在
    """
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        return True
    except Exception as e:
        print(f"创建目录失败: {e}")
        return False


class WorkerSignals(QObject):
    """工作线程信号类"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    

class Worker(QThread):
    """通用工作线程类
    
    用于执行耗时操作而不阻塞主线程
    """
    
    def __init__(self, fn, *args, **kwargs):
        """初始化工作线程
        
        Args:
            fn: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
        """
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        
    def run(self):
        """线程运行函数"""
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()