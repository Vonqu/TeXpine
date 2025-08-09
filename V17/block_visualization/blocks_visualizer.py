import numpy as np
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor

class BlocksVisualizer(QWidget):
    """积木可视化控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.gray_block_rotation = 0
        self.gray_block_tilt = 0
        self.blue_blocks_curvature = 0
        self.green_block_tilt = 0
        self.gray_rotation_alert = False
        self.gray_tilt_alert = False
        self.blue_curvature_alert = False
        self.green_tilt_alert = False

        self.current_stage = 1
        
        # 新增：脊柱配置
        self.spine_type = "C"  # "C" 或 "S"
        self.spine_direction = "left"  # C型："left"/"right", S型："lumbar_left_thoracic_right"/"lumbar_right_thoracic_left"
        
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(50, 50, 50))
        self.setPalette(palette)

    def set_spine_config(self, spine_type, spine_direction):
        """设置脊柱配置"""
        self.spine_type = spine_type
        self.spine_direction = spine_direction
        print(f"可视化器脊柱配置已更新：{spine_type}型，方向={spine_direction}")

    def set_current_stage(self, stage):
        """设置当前阶段"""
        self.current_stage = stage
        print(f"可视化器当前阶段已更新：{stage}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        height = self.height()
        
        # 绘制灰色方块（保持不变）
        self._draw_gray_block(painter, width, height)
        
        # 绘制绿色方块（保持不变）
        self._draw_green_block(painter, width, height)
        
        # 根据脊柱类型绘制蓝色方块
        if self.spine_type == "C":
            self._draw_blue_blocks_c_type(painter, width, height)
        else:  # S型
            self._draw_blue_blocks_s_type(painter, width, height)

    def _draw_gray_block(self, painter, width, height):
        """绘制灰色方块（保持原有逻辑）"""
        norm = self.gray_block_rotation
        norm = max(0.0, min(1.0, norm))
        
        base_gray_width = width * 0.4
        gray_width = base_gray_width * (1 - 0.5 * norm)
        gray_height = height * 0.08
        gray_x = (width - gray_width) / 2
        gray_y = height - gray_height - 20
        
        painter.save()
        painter.translate(width/2, gray_y + gray_height/2)
        painter.rotate(self.gray_block_tilt)
        adjusted_width = int(gray_width * np.cos(np.radians(self.gray_block_rotation)))
        painter.translate(-adjusted_width/2, -gray_height/2)
        
        if self.gray_rotation_alert or self.gray_tilt_alert:
            painter.setBrush(QColor(255, 100, 100))
        else:
            c = int(255 * (1-norm))
            painter.setBrush(QColor(c, c, c))
        
        painter.drawRect(0, 0, adjusted_width, int(gray_height))
        painter.restore()

    def _draw_green_block(self, painter, width, height):
        """绘制绿色方块（保持原有逻辑）"""
        green_width = width * 0.4
        green_height = height * 0.06
        green_x = (width - green_width) / 2
        green_y = height * 0.1
        
        painter.save()
        painter.translate(width/2, green_y + green_height/2)
        painter.rotate(self.green_block_tilt)
        
        if self.green_tilt_alert:
            painter.setBrush(QColor(255, 100, 100))
        else:
            painter.setBrush(QColor(0, 240, 0))
        
        painter.drawRect(-int(green_width/2), -int(green_height/2), int(green_width), int(green_height))
        painter.restore()

    def _draw_blue_blocks_c_type(self, painter, width, height):
        """绘制C型脊柱的蓝色方块"""
        num_blocks = 7
        blue_height = height * 0.04
        blue_width = width * 0.15
        
        # 起点P0（灰色方块中心）
        gray_y = height - height * 0.08 - 20
        P0 = np.array([width/2, gray_y + height * 0.08/2])
        
        # 终点P2（绿色方块中心）
        green_y = height * 0.1
        P2 = np.array([width/2, green_y + height * 0.06/2])
        
        # 控制点P1：根据侧弯方向调整
        mid = (P0 + P2) / 2
        direction = P2 - P0
        normal = np.array([direction[1], -direction[0]])
        normal = normal / (np.linalg.norm(normal) + 1e-6)
        
        # 根据侧弯方向调整控制点
        t = self.blue_blocks_curvature
        if self.spine_direction == "right":
            # 右凸：控制点向左偏移（相对于默认的右偏移）
            P1 = mid - normal * t * (height * 0.25)
        else:  # left
            # 左凸：控制点向右偏移（原来的逻辑）
            P1 = mid + normal * t * (height * 0.25)
        
        # 绘制蓝色方块
        for i in range(num_blocks):
            painter.save()
            s = (i+1)/(num_blocks+1)
            pos = (1-s)**2 * P0 + 2*(1-s)*s*P1 + s**2*P2
            painter.translate(pos[0], pos[1])
            
            if self.blue_curvature_alert:
                painter.setBrush(QColor(255, 100, 100))
            else:
                painter.setBrush(QColor(50, 100, 240))
            
            painter.drawRect(-int(blue_width/2), -int(blue_height/2), int(blue_width), int(blue_height))
            painter.restore()

    def _draw_blue_blocks_s_type(self, painter, width, height):
        """绘制S型脊柱的蓝色方块（分阶段控制，修复版）"""
        num_blocks = 7
        blue_height = height * 0.04
        blue_width = width * 0.15
        
        # 起点P0（灰色方块中心）
        gray_y = height - height * 0.08 - 20
        P0 = np.array([width/2, gray_y + height * 0.08/2])
        
        # 终点P3（绿色方块中心）
        green_y = height * 0.1
        P3 = np.array([width/2, green_y + height * 0.06/2])
        
        # 中点（胸椎和腰椎的分界点）
        total_height = P0[1] - P3[1]
        mid_point = np.array([width/2, P0[1] - total_height * 0.5])
        
        # 获取当前阶段信息
        current_stage = getattr(self, 'current_stage', 1)
        
        # 计算偏移量
        offset_magnitude = self.blue_blocks_curvature * (width * 0.2)
        
        # 根据当前阶段和脊柱方向确定弯曲参数
        lumbar_curve = 0.0  # 腰椎弯曲程度
        thoracic_curve = 0.0  # 胸椎弯曲程度
        
        if current_stage == 2:
            # 阶段2：腰椎曲率矫正 - 只有腰椎变化
            lumbar_curve = self.blue_blocks_curvature
            thoracic_curve = 0.0
        elif current_stage == 3:
            # 阶段3：胸椎曲率矫正 - 只有胸椎变化
            lumbar_curve = 0.0
            thoracic_curve = self.blue_blocks_curvature
        else:
            # 阶段1和4：保持直线
            lumbar_curve = 0.0
            thoracic_curve = 0.0
        
        # 根据S型方向和弯曲程度定义控制点
        if self.spine_direction == "lumbar_left_thoracic_right":
            # 腰椎左凸胸椎右凸
            lumbar_control = np.array([
                width/2 - lumbar_curve * (width * 0.2),  # 腰椎向右弯曲
                P0[1] - total_height * 0.25
            ])
            thoracic_control = np.array([
                width/2 + thoracic_curve * (width * 0.2),  # 胸椎向左弯曲
                P0[1] - total_height * 0.75
            ])
        else:  # lumbar_right_thoracic_left
            # 腰椎右凸胸椎左凸
            lumbar_control = np.array([
                width/2 + lumbar_curve * (width * 0.2),  # 腰椎向左弯曲
                P0[1] - total_height * 0.25
            ])
            thoracic_control = np.array([
                width/2 - thoracic_curve * (width * 0.2),  # 胸椎向右弯曲
                P0[1] - total_height * 0.75
            ])
        
        # 绘制蓝色方块
        for i in range(num_blocks):
            painter.save()
            t_global = (i+1)/(num_blocks+1)  # 全局参数t，从1/8到7/8
            
            # 计算当前方块的位置
            if t_global <= 0.5:
                # 腰椎段：从P0到mid_point
                t_local = t_global * 2  # 归一化到0-1
                # 二次贝塞尔曲线：腰椎段
                pos = (1-t_local)**2 * P0 + 2*(1-t_local)*t_local * lumbar_control + t_local**2 * mid_point
            else:
                # 胸椎段：从mid_point到P3
                t_local = (t_global - 0.5) * 2  # 归一化到0-1
                # 二次贝塞尔曲线：胸椎段
                pos = (1-t_local)**2 * mid_point + 2*(1-t_local)*t_local * thoracic_control + t_local**2 * P3
            
            painter.translate(pos[0], pos[1])
            
            if self.blue_curvature_alert:
                painter.setBrush(QColor(255, 100, 100))
            else:
                painter.setBrush(QColor(50, 100, 240))
            
            painter.drawRect(-int(blue_width/2), -int(blue_height/2), int(blue_width), int(blue_height))
            painter.restore()