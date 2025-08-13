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
        # C 型：单段曲率；S 型：分段曲率（上/下）
        self.blue_blocks_curvature = 0
        self.blue_blocks_curvature_up = 0
        self.blue_blocks_curvature_down = 0
        self.green_block_tilt = 0
        self.gray_rotation_alert = False
        self.gray_tilt_alert = False
        self.blue_curvature_alert = False
        self.green_tilt_alert = False
        # C 或 S（默认 C）
        self.spine_type = 'C'
        # 方向：C型使用 'left'/'right'，S型使用 'lumbar_left'/'lumbar_right'
        self.spine_direction = 'left'
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
        # 贝塞尔曲线分布蓝色方块（C: 单段；S: 两段反向拼接）
        num_blocks = 10
        blue_height = height * 0.04
        blue_width = width * 0.15
        P0 = np.array([width/2, gray_y + gray_height/2])
        P2 = np.array([width/2, green_y + green_height/2])
        direction = P2 - P0
        normal = np.array([direction[1], -direction[0]])
        normal = normal / (np.linalg.norm(normal) + 1e-6)

        # 根据选择的方向翻转法向量
        dir_key = str(getattr(self, 'spine_direction', 'left'))
        s_type = str(getattr(self, 'spine_type', 'C')).upper()
        # C型: left=默认(不翻转), right=翻转
        # S型: lumbar_left=下段向左(默认), 上段向右；lumbar_right=下段向右(翻转), 上段向左
        flip_for_c = (s_type != 'S') and (dir_key == 'right')
        flip_for_s_down = (s_type == 'S') and (dir_key == 'lumbar_right')
        flip_for_s_up = (s_type == 'S') and (dir_key == 'lumbar_left')  # 上段与下段相反

        amplitude = height * 0.25

        if str(getattr(self, 'spine_type', 'C')).upper() == 'S':
            # S 型：两段反向 C 曲线
            Pm = (P0 + P2) / 2
            # 为每个半段使用自身中点，曲率方向相反
            mid_lower = (P0 + Pm) / 2
            mid_upper = (Pm + P2) / 2
            t_down = max(0.0, min(1.0, float(self.blue_blocks_curvature_down)))
            t_up = max(0.0, min(1.0, float(self.blue_blocks_curvature_up)))
            # 下半段/上半段根据方向设置法向量（lumbar_left: 下左上右；lumbar_right: 下右上左）
            if dir_key == 'lumbar_left':
                effective_normal_down = normal
                effective_normal_up = -normal
            else:
                effective_normal_down = -normal
                effective_normal_up = normal
            L1 = mid_lower + effective_normal_down * t_down * amplitude
            U1 = mid_upper + effective_normal_up * t_up * amplitude
            lower_count, upper_count = 5, 5

            # 下半段 P0 -> Pm
            for i in range(lower_count):
                painter.save()
                s = (i + 1) / (lower_count + 1)
                pos = (1 - s) ** 2 * P0 + 2 * (1 - s) * s * L1 + s ** 2 * Pm
                painter.translate(pos[0], pos[1])
                painter.setBrush(QColor(255, 100, 100) if self.blue_curvature_alert else QColor(50, 100, 240))
                painter.drawRect(-int(blue_width/2), -int(blue_height/2), int(blue_width), int(blue_height))
                painter.restore()

            # 上半段 Pm -> P2
            for i in range(upper_count):
                painter.save()
                s = (i + 1) / (upper_count + 1)
                pos = (1 - s) ** 2 * Pm + 2 * (1 - s) * s * U1 + s ** 2 * P2
                painter.translate(pos[0], pos[1])
                painter.setBrush(QColor(255, 100, 100) if self.blue_curvature_alert else QColor(50, 100, 240))
                painter.drawRect(-int(blue_width/2), -int(blue_height/2), int(blue_width), int(blue_height))
                painter.restore()
        else:
            # C 型：单段二次贝塞尔
            mid = (P0 + P2) / 2
            t = max(0.0, min(1.0, float(self.blue_blocks_curvature)))
            # C型方向翻转
            effective_normal = (-normal if flip_for_c else normal)
            P1 = mid + effective_normal * t * amplitude
            for i in range(num_blocks):
                painter.save()
                s = (i+1)/(num_blocks+1)
                pos = (1-s)**2 * P0 + 2*(1-s)*s*P1 + s**2*P2
                painter.translate(pos[0], pos[1])
                painter.setBrush(QColor(255, 100, 100) if self.blue_curvature_alert else QColor(50, 100, 240))
                painter.drawRect(-int(blue_width/2), -int(blue_height/2), int(blue_width), int(blue_height))
                painter.restore()

    def update_visualization(self, gray_rotation=0, blue_curvature=0, blue_curvature_up=0, blue_curvature_down=0, gray_tilt=0, green_tilt=0):
        """更新可视化参数并重绘"""
        try:
            # 更新灰色方块参数
            self.gray_block_rotation = float(gray_rotation)
            self.gray_block_tilt = float(gray_tilt) * 30.0  # 转换为角度
            
            # 更新绿色方块参数
            self.green_block_tilt = float(green_tilt) * 30.0  # 转换为角度
            
            # 更新蓝色方块参数（根据脊柱类型）
            if str(getattr(self, 'spine_type', 'C')).upper() == 'S':
                # S型脊柱：使用分段参数
                self.blue_blocks_curvature_up = float(blue_curvature_up)
                self.blue_blocks_curvature_down = float(blue_curvature_down)
                # 为兼容性也设置单一参数（使用最大值）
                self.blue_blocks_curvature = float(max(blue_curvature_up, blue_curvature_down))
            else:
                # C型脊柱：使用单一参数
                self.blue_blocks_curvature = float(blue_curvature)
            
            # 触发重绘
            self.update()
            
        except Exception as e:
            print(f"更新可视化参数失败: {e}")
    
    def set_spine_config(self, spine_type, spine_direction):
        """设置脊柱配置"""
        self.spine_type = spine_type
        self.spine_direction = spine_direction
        # 触发重绘以应用新配置
        self.update()

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