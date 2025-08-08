#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
脊柱监测系统UDP数据接收器
========================

接收并显示脊柱监测系统发送的四个阶段数据：
1. 阶段1：骨盆前后翻转 (gray_rotation)
2. 阶段2：脊柱曲率矫正 (blue_curvature)  
3. 阶段3：骨盆左右倾斜 (gray_tilt)
4. 阶段3：肩部左右倾斜 (green_tilt)

每个阶段包含：
- 加权归一化值 (0-1)
- 误差范围值 (error_range)

使用方法:
python spine_udp_receiver.py --verbose
"""

import socket
import json
import time
import argparse
from datetime import datetime

class SpineDataReceiver:
    def __init__(self, host='127.0.0.1', port=6667, buffer_size=65535, verbose=False):
        """初始化脊柱数据UDP接收器"""
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.verbose = verbose
        self.socket = None
        self.running = False
        self.packet_count = 0
        self.start_time = None
        self.last_status_time = 0
        
        # 阶段名称映射
        self.stage_names = {
            'gray_rotation': '阶段1-骨盆前后翻转',
            'blue_curvature': '阶段2-脊柱曲率矫正',
            'gray_tilt': '阶段3-骨盆左右倾斜',
            'green_tilt': '阶段3-肩部左右倾斜'
        }
    
    def initialize_socket(self):
        """初始化UDP socket进行监听"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(1.0)
            print(f"脊柱数据接收器已初始化，正在监听 {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Socket初始化失败: {e}")
            self.socket = None
            return False
    
    def start(self):
        """开始监听传入数据"""
        if not self.initialize_socket():
            print("无法初始化socket，退出。")
            return False
        
        self.running = True
        self.packet_count = 0
        self.start_time = time.time()
        self.last_status_time = time.time()
        print(f"开始脊柱数据接收，时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("按Ctrl+C停止...\n")
        
        try:
            while self.running:
                try:
                    data, addr = self.socket.recvfrom(self.buffer_size)
                    self.packet_count += 1
                    self.process_data(data, addr)
                    self.last_status_time = time.time()
                except socket.timeout:
                    current_time = time.time()
                    elapsed = current_time - self.start_time
                    status_elapsed = current_time - self.last_status_time
                    
                    # 每5秒打印一次状态
                    if status_elapsed >= 5:
                        if self.packet_count == 0:
                            print(f"尚未收到脊柱数据... 已等待 {elapsed:.1f} 秒。确保发送端正在运行。")
                        else:
                            print(f"最近5秒没有收到新数据。总计收到 {self.packet_count} 个数据包。")
                        self.last_status_time = current_time
                except Exception as e:
                    print(f"接收数据时出错: {e}")
        except KeyboardInterrupt:
            print("\n用户停止了接收器。")
        finally:
            self.stop()
        
        return True
    
    def process_data(self, data, addr):
        """处理接收到的脊柱数据"""
        try:
            json_data = json.loads(data.decode())
            
            # 基本统计信息
            elapsed = time.time() - self.start_time
            rate = self.packet_count / elapsed if elapsed > 0 else 0
            
            print(f"\n=== 脊柱数据包 #{self.packet_count} === 来自 {addr[0]}:{addr[1]} === {datetime.now().strftime('%H:%M:%S')} === {rate:.2f} 包/秒 ===")
            
            # 获取基本信息
            timestamp = json_data.get('timestamp', 'N/A')
            sensor_count = json_data.get('sensor_count', 'N/A')
            events_file_loaded = json_data.get('events_file_loaded', False)
            
            print(f"时间戳: {timestamp}")
            print(f"传感器数量: {sensor_count}")
            print(f"事件文件加载: {'是' if events_file_loaded else '否'}")
            
            # 显示四个阶段的核心数据
            stage_values = json_data.get('stage_values', {})
            stage_error_ranges = json_data.get('stage_error_ranges', {})
            
            # print(f"\n{'阶段':<25} {'加权归一化值':<15} {'误差范围':<10} {'状态评估'}")
            print(f"\n{'阶段':<25} {'加权归一化值':<15} {'误差范围':<10}")
            print("-" * 70)
            
            for stage_code, stage_name in self.stage_names.items():
                value = stage_values.get(stage_code, 'N/A')
                error_range = stage_error_ranges.get(stage_code, 'N/A')
                
                # # 状态评估
                # if isinstance(value, (int, float)):
                #     if 0.4 <= value <= 0.6:
                #         status = "理想"
                #         status_color = "🟢"
                #     elif 0.2 <= value <= 0.8:
                #         status = "良好"
                #         status_color = "🟡"
                #     else:
                #         status = "需调整"
                #         status_color = "🔴"
                #     value_str = f"{value:.3f}"
                # else:
                #     status = "未知"
                #     status_color = "⚪"
                #     value_str = str(value)
                
                error_str = f"{error_range:.3f}" if isinstance(error_range, (int, float)) else str(error_range)
                
                # print(f"{stage_name:<25} {value_str:<15} {error_str:<10} {status_color} {status}")
                value_str = f"{value:.3f}"
                print(f"{stage_name:<25} {value_str:<15} {error_str:<10}")
            
            print("-" * 70)
            
            # 详细数据显示（仅在verbose模式下）
            if self.verbose:
                print(f"\n详细传感器数据:")
                sensor_data = json_data.get('sensor_data', [])
                if sensor_data:
                    print(f"  传感器值: {[f'{val:.2f}' for val in sensor_data[:8]]}...")  # 只显示前8个
                    if len(sensor_data) > 8:
                        print(f"  (还有 {len(sensor_data) - 8} 个传感器值未显示)")
                
                print(f"\n阶段详细信息:")
                for stage_code, stage_name in self.stage_names.items():
                    value = stage_values.get(stage_code, 'N/A')
                    error_range = stage_error_ranges.get(stage_code, 'N/A')
                    print(f"  {stage_name}:")
                    print(f"    加权归一化值: {value}")
                    print(f"    误差范围: {error_range}")
                    
                    # 如果有详细的计算信息，可以在这里显示
                    
            print("=" * 80)
            
        except json.JSONDecodeError:
            print(f"错误: 接收到非JSON数据: {data[:100]}...")
        except Exception as e:
            print(f"处理脊柱数据时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """停止监听并清理"""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
        
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"\n脊柱数据接收器在 {elapsed:.1f} 秒后停止。")
        print(f"总计接收到的数据包: {self.packet_count}")
        if elapsed > 0:
            print(f"平均速率: {self.packet_count / elapsed:.2f} 包/秒")

def main():
    parser = argparse.ArgumentParser(description="脊柱监测系统UDP数据接收器")
    parser.add_argument("--host", default="127.0.0.1", help="监听的主机地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=6667, help="监听的端口 (默认: 6667)")
    parser.add_argument("--buffer", type=int, default=65535, help="UDP缓冲区大小 (默认: 65535)")
    parser.add_argument("--verbose", "-v", action="store_true", help="启用详细输出")
    
    args = parser.parse_args()
    
    print("脊柱监测系统UDP数据接收器")
    print("=" * 50)
    print(f"监听地址: {args.host}:{args.port}")
    print(f"详细模式: {'开启' if args.verbose else '关闭'}")
    print(f"缓冲区大小: {args.buffer} 字节")
    print("=" * 50)
    print("\n期待接收以下8个核心数据值:")
    print("1. 阶段1-骨盆前后翻转: 加权归一化值 + 误差范围")
    print("2. 阶段2-脊柱曲率矫正: 加权归一化值 + 误差范围")
    print("3. 阶段3-骨盆左右倾斜: 加权归一化值 + 误差范围")
    print("4. 阶段3-肩部左右倾斜: 加权归一化值 + 误差范围")
    print("=" * 50)
    
    receiver = SpineDataReceiver(
        host=args.host,
        port=args.port,
        buffer_size=args.buffer,
        verbose=args.verbose
    )
    
    receiver.start()

if __name__ == "__main__":
    main()