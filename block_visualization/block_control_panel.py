#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BlockControlPanel
-----------------
医生端右侧“控制面板”组件。此版本在 C / S 型之间切换时：
- C 型：显示 4 张卡片（单段曲率 blue_curvature）
- S 型：显示 5 张卡片（胸段 blue_curvature_up、腰段 blue_curvature_down）

提供 API：
- set_spine_type(spine_type): "C" 或 "S"，切换显示的卡片
- highlight_stage(stage: int): 根据当前阶段高亮相应卡片
- get_controller_for_stage(stage: int) -> SensorSelector: 返回该阶段对应控件（便于权重/阈值读取）
- error_range_changed(str, float): 任一控件误差范围变化时发出（名称, 值）
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout

# 说明：SensorSelector 由你的工程中其他文件提供，这里只引用其公开接口：
# - set_highlighted(bool)
# - get_error_range() -> float
# - error_range_changed: pyqtSignal(float)
# - original_value_spins / best_value_spins 等属性，被外部写入时需存在
try:
    from .sensor_selector import SensorSelector   # 你的项目里若有独立文件
except Exception:
    # 如果你的项目里 SensorSelector 是在同目录其他文件中定义的，保持导入路径统一；
    # 此处兜底从全局导入（按你的项目结构无需改动）
    from sensor_selector import SensorSelector    # type: ignore


class BlockControlPanel(QWidget):
    """医生端控制面板：卡片容器 + C/S 显示切换 + 阶段高亮"""
    error_range_changed = pyqtSignal(str, float)  # 控制器名称, 误差范围

    def __init__(self, sensor_count: int = 6, parent=None):
        super().__init__(parent)
        self.sensor_count = sensor_count
        self._is_s_flag = False  # 默认 C 型
        self._build_ui()
        self._connect_error_range_signals()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(10)

        # 基础四张卡片（C/S 共用）
        self.gray_rotation = SensorSelector("骨盆前后翻转", self.sensor_count, special_mode=True)
        self.blue_curvature = SensorSelector("脊柱曲率矫正", self.sensor_count, special_mode=True)
        self.gray_tilt = SensorSelector("骨盆左右倾斜", self.sensor_count, special_mode=True)
        self.green_tilt = SensorSelector("肩部左右倾斜", self.sensor_count, special_mode=True)

        # S 型专用：胸/腰两段曲率
        self.blue_curvature_up = SensorSelector("脊柱曲率矫正·胸段", self.sensor_count, special_mode=True)
        self.blue_curvature_down = SensorSelector("脊柱曲率矫正·腰段", self.sensor_count, special_mode=True)

        # 统一尺寸（可按需调整）
        for ctrl in [
            self.gray_rotation, self.blue_curvature,
            self.blue_curvature_up, self.blue_curvature_down,
            self.gray_tilt, self.green_tilt
        ]:
            try:
                ctrl.setMinimumHeight(420)
                ctrl.setFixedWidth(250)
            except Exception:
                pass

        # 添加到布局：顺序 = 骨盆前后 → 曲率(单/胸/腰) → 骨盆倾 → 肩部倾
        layout.addWidget(self.gray_rotation)
        layout.addWidget(self.blue_curvature)
        layout.addWidget(self.blue_curvature_up)
        layout.addWidget(self.blue_curvature_down)
        layout.addWidget(self.gray_tilt)
        layout.addWidget(self.green_tilt)

        # 默认 C 型：隐藏胸/腰两段
        self.blue_curvature_up.hide()
        self.blue_curvature_down.hide()

    def _connect_error_range_signals(self):
        """把每张卡片的误差范围变更汇总抛出（名称, 值）"""
        self.gray_rotation.error_range_changed.connect(
            lambda v: self.error_range_changed.emit("gray_rotation", v)
        )
        self.blue_curvature.error_range_changed.connect(
            lambda v: self.error_range_changed.emit("blue_curvature", v)
        )
        self.gray_tilt.error_range_changed.connect(
            lambda v: self.error_range_changed.emit("gray_tilt", v)
        )
        self.green_tilt.error_range_changed.connect(
            lambda v: self.error_range_changed.emit("green_tilt", v)
        )
        # S 型胸/腰段
        self.blue_curvature_up.error_range_changed.connect(
            lambda v: self.error_range_changed.emit("blue_curvature_up", v)
        )
        self.blue_curvature_down.error_range_changed.connect(
            lambda v: self.error_range_changed.emit("blue_curvature_down", v)
        )

    # ---------- 公共接口 ----------
    def set_spine_type(self, spine_type: str):
        """
        切换 C/S：
        - C：显示单段曲率（blue_curvature），隐藏胸/腰段
        - S：隐藏单段曲率，显示胸/腰段
        """
        self._is_s_flag = (str(spine_type).upper() == "S")
        is_s = self._is_s_flag

        self.blue_curvature.setVisible(not is_s)
        self.blue_curvature_up.setVisible(is_s)
        self.blue_curvature_down.setVisible(is_s)

        # 切换后可以重置一次高亮到当前阶段（由外部再调用 highlight_stage）

    def highlight_stage(self, stage: int):
        """根据阶段高亮某张卡片（C：4 阶段；S：5 阶段）"""
        # 先全部取消
        for w in [
            getattr(self, "gray_rotation", None),
            getattr(self, "blue_curvature", None),
            getattr(self, "blue_curvature_up", None),
            getattr(self, "blue_curvature_down", None),
            getattr(self, "gray_tilt", None),
            getattr(self, "green_tilt", None),
        ]:
            try:
                if w is not None and hasattr(w, "set_highlighted"):
                    w.set_highlighted(False)
            except Exception:
                pass

        is_s = self._is_s_flag
        try:
            if stage == 1:
                self.gray_rotation.set_highlighted(True)
            elif stage == 2:
                # C: 单段曲率；S: 胸段
                (self.blue_curvature_up if is_s else self.blue_curvature).set_highlighted(True)
            elif stage == 3:
                # C: 骨盆左右倾斜；S: 腰段
                (self.blue_curvature_down if is_s else self.gray_tilt).set_highlighted(True)
            elif stage == 4:
                # C: 肩部左右倾斜；S: 骨盆左右倾斜
                (self.gray_tilt if is_s else self.green_tilt).set_highlighted(True)
            elif stage == 5 and is_s:
                # S: 第 5 阶段肩部左右倾斜
                self.green_tilt.set_highlighted(True)
        except Exception:
            # 某控件缺少 set_highlighted 不致命，忽略
            pass

    def get_controller_for_stage(self, stage: int) -> "SensorSelector":
        """
        返回当前阶段对应的控件，便于外部统一读取权重/误差等。
        """
        is_s = self._is_s_flag
        if is_s:
            mapping = {
                1: self.gray_rotation,
                2: self.blue_curvature_up,
                3: self.blue_curvature_down,
                4: self.gray_tilt,
                5: self.green_tilt,
            }
        else:
            mapping = {
                1: self.gray_rotation,
                2: self.blue_curvature,
                3: self.gray_tilt,
                4: self.green_tilt,
            }
        # 默认返回第一阶段以避免 None
        return mapping.get(stage, self.gray_rotation)
    
    def set_stage_defaults(self, stage: int):
        """设置指定阶段的默认参数值"""
        try:
            controller = self.get_controller_for_stage(stage)
            if controller and hasattr(controller, 'reset_to_defaults'):
                controller.reset_to_defaults()
            
            # 可以在这里添加更多针对特定阶段的默认设置
            print(f"BlockControlPanel: 设置阶段{stage}默认参数")
        except Exception as e:
            print(f"BlockControlPanel: 设置阶段{stage}默认参数失败: {e}")

    def process_sensor_data(self, data_values):
        """处理传感器数据，更新所有控制器"""
        try:
            for controller_name in ['gray_rotation', 'blue_curvature', 'blue_curvature_up', 
                                  'blue_curvature_down', 'gray_tilt', 'green_tilt']:
                controller = getattr(self, controller_name, None)
                if controller and hasattr(controller, 'process_sensor_data'):
                    controller.process_sensor_data(data_values)
        except Exception as e:
            print(f"BlockControlPanel: 处理传感器数据失败: {e}")
