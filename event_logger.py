#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
事件日志记录器
用于记录用户的所有操作和对应时间戳
"""

import os
import json
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

class EventLogger:
    """事件日志记录器"""
    
    def __init__(self):
        self.log_dir = os.path.join("saving_data", "operation_logs")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # 创建新的日志文件（按日期）
        self.current_date = datetime.now().strftime("%Y%m%d")
        self.log_file = os.path.join(self.log_dir, f"operation_log_{self.current_date}.log")
        
        # 配置日志记录器
        self._setup_logger()
        
    def _setup_logger(self):
        """配置日志记录器"""
        self.logger = logging.getLogger('EventLogger')
        self.logger.setLevel(logging.INFO)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建文件处理器（每个文件最大10MB，保留10个文件）
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        # 清除现有的处理器
        self.logger.handlers = []
        self.logger.addHandler(file_handler)
        
        # 记录启动信息
        self.logger.info("=== 新的操作记录会话开始 ===")
        
    def _check_date(self):
        """检查是否需要创建新的日志文件"""
        current_date = datetime.now().strftime("%Y%m%d")
        if current_date != self.current_date:
            self.current_date = current_date
            self.log_file = os.path.join(self.log_dir, f"operation_log_{self.current_date}.log")
            self._setup_logger()
    
    def log_operation(self, operation_type, details=None, stage=None, sensor_data=None):
        """记录操作
        
        Args:
            operation_type: 操作类型
            details: 操作详情（可选）
            stage: 训练阶段（可选）
            sensor_data: 传感器数据（可选）
        """
        self._check_date()
        
        # 准备日志内容
        log_data = {
            'operation': operation_type,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        }
        
        if stage is not None:
            log_data['stage'] = stage
            
        if details:
            log_data['details'] = details
            
        if sensor_data:
            # 只记录前几个传感器的数据作为示例
            log_data['sensor_data'] = [f"{x:.2f}" for x in sensor_data[:3]]
            if len(sensor_data) > 3:
                log_data['sensor_data'].append("...")
        
        # 记录日志
        self.logger.info(json.dumps(log_data, ensure_ascii=False))
        
    def log_mode_change(self, from_mode, to_mode):
        """记录模式切换"""
        self.log_operation(
            'mode_change',
            {'from': from_mode, 'to': to_mode}
        )
    
    def log_stage_event(self, stage, event_name, sensor_data=None):
        """记录阶段事件"""
        self.log_operation(
            'stage_event',
            {'event': event_name},
            stage=stage,
            sensor_data=sensor_data
        )
    
    def log_acquisition_start(self, source_type, settings):
        """记录采集开始"""
        self.log_operation(
            'acquisition_start',
            {'source': source_type, 'settings': settings}
        )
    
    def log_acquisition_stop(self, stats):
        """记录采集结束"""
        self.log_operation(
            'acquisition_stop',
            {'statistics': stats}
        )
    
    def log_error(self, error_type, error_msg):
        """记录错误"""
        self.logger.error(json.dumps({
            'error_type': error_type,
            'message': error_msg,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        }, ensure_ascii=False)) 