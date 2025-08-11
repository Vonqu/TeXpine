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
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(50, 50, 50))
        self.setPalette(palette)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        height = self.height()
        # 灰色方块归一化参数（0=标准，1=最远）
        norm = self.gray_block_rotation
        norm = max(0.0, min(1.0, norm))
        # 绘制底部灰色方块
        base_gray_width = width * 0.4
        gray_width = base_gray_width * (1 - 0.5 * norm)  # 0时为100%，1时为50%
        gray_height = height * 0.08
        gray_x = (width - gray_width) / 2
        gray_y = height - gray_height - 20
        painter.save()
        painter.translate(width/2, gray_y + gray_height/2)
        painter.rotate(self.gray_block_tilt)
        adjusted_width = int(gray_width * np.cos(np.radians(self.gray_block_rotation)))
        painter.translate(-adjusted_width/2, -gray_height/2)
        # 颜色渐变：0为白色，1为黑色
        if self.gray_rotation_alert or self.gray_tilt_alert:
            painter.setBrush(QColor(255, 100, 100))
        else:
            c = int(255 * (1-norm))
            painter.setBrush(QColor(c, c, c))
        painter.drawRect(0, 0, adjusted_width, int(gray_height))
        painter.restore()
        # 绘制顶部绿色方块
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
        # 贝塞尔曲线分布蓝色方块
        num_blocks = 7
        blue_height = height * 0.04
        blue_width = width * 0.15
        # 起点P0（灰色方块中心）
        P0 = np.array([width/2, gray_y + gray_height/2])
        # 终点P2（绿色方块中心）
        P2 = np.array([width/2, green_y + green_height/2])
        # 控制点P1：P0和P2中点加法向量，t控制弯曲
        mid = (P0 + P2) / 2
        # 法向量（垂直于P2-P0，向右）
        direction = P2 - P0
        normal = np.array([direction[1], -direction[0]])
        normal = normal / (np.linalg.norm(normal) + 1e-6)
        t = self.blue_blocks_curvature  # 0~1
        P1 = mid + normal * t * (height * 0.25)  # 弯曲幅度
        for i in range(num_blocks):
            painter.save()
            s = (i+1)/(num_blocks+1)  # 均匀分布
            # 二次贝塞尔插值
            pos = (1-s)**2 * P0 + 2*(1-s)*s*P1 + s**2*P2
            painter.translate(pos[0], pos[1])
            if self.blue_curvature_alert:
                painter.setBrush(QColor(255, 100, 100))
            else:
                painter.setBrush(QColor(50, 100, 240))
            painter.drawRect(-int(blue_width/2), -int(blue_height/2), int(blue_width), int(blue_height))
            painter.restore()

    def update_blue_blocks_curvature(self, t):
        """根据t值更新蓝色方块的曲率，t由第二阶段的加权结果控制"""
        # 二次贝塞尔曲线参数
        p0 = (self.gray_block_x, self.gray_block_y)  # 起点（灰色方块）
        p2 = (self.green_block_x, self.green_block_y)  # 终点（绿色方块）
        p1 = ((p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2 + 50)  # 控制点
        # 计算蓝色方块的位置
        for i in range(len(self.blue_blocks)):
            t_i = t * (i + 1) / (len(self.blue_blocks) + 1)
            x = (1 - t_i) ** 2 * p0[0] + 2 * (1 - t_i) * t_i * p1[0] + t_i ** 2 * p2[0]
            y = (1 - t_i) ** 2 * p0[1] + 2 * (1 - t_i) * t_i * p1[1] + t_i ** 2 * p2[1]
            self.blue_blocks[i] = (x, y)
        self.update()
        # 更新提示栏
        if t <= 0.1:  # 假设t接近0时动作达标
            self.correct_label.setText("当前动作：达标")
            self.correct_label.setStyleSheet("font-size: 18px; color: green; font-weight: bold;")
        else:
            self.correct_label.setText("当前动作：不正确")
            self.correct_label.setStyleSheet("font-size: 18px; color: red; font-weight: bold;") 