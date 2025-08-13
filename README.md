# 智能服装传感器监测与可视化系统（TeXpine-main）

## 概览
- 基于 PyQt5 的多传感器实时监测、校准（医生端）与训练（患者端）系统
- 积木式训练可视化，事件记录与数据导出
- 实时 UDP 向 Unity/外部系统发送归一化训练指标
- 三类滤波（Butterworth / Kalman / Savitzky–Golay）与数据增强
- 已内置性能优化：UI 限频刷新与 UDP 限频发送，蓝牙轮询日志降噪

## 快速开始
- 环境需求：Python 3.8+（Windows 推荐）
- 依赖（常用）：
  - PyQt5, pyqtgraph, numpy, scipy, pandas, openpyxl
- 安装示例：
  ```bash
  pip install PyQt5 pyqtgraph numpy scipy pandas openpyxl
  ```
- 运行：
  ```bash
  cd TeXpine/TeXpine-main
  python main_window.py
  ```

## 目录结构与脚本职责
```
TeXpine-main/
├── main_window.py                  # 应用主入口/系统编排（医生/患者模式、UDP、限频刷新）
├── control_panel.py                # 主控制面板（串口/蓝牙/保存/滤波/脊柱类型与方向/UDP设置）
├── data_manager.py                 # 数据内存/缓存/保存（RAW 与 PROCESSED 缓存、滑动窗口显示）
├── serial_thread.py                # 串口采集线程（QThread）
├── bluetooth_receiver.py           # 蓝牙采集（连接、接收、轮询备选）
├── plot_widget.py                  # 实时曲线显示（pyqtgraph）
├── event_recorder.py               # 事件记录（阶段原始/目标/权重/误差范围）
├── event_logger.py                 # 操作日志（启动/停止/错误/模式切换）
├── fliter_processing/              # 三类滤波与增强
│   ├── butterworth_filter.py
│   ├── kalman_filter.py
│   ├── savitzky_golay_filter.py
│   └── data_enhancement.py
└── block_visualization/            # 积木可视化与训练记录
    ├── blocks_tab_manager.py
    ├── blocks_tab.py               # 医生端（校准）标签页
    ├── patient_blocks_tab.py       # 患者端（训练）标签页
    ├── block_control_panel.py
    ├── blocks_visualizer.py
    ├── sensor_selector.py          # 传感器选择/权重/阈值/误差配置
    ├── spine_type_selector.py      # C/S 型，左右方向选择与广播
    └── training_recorder.py        # 训练记录导出（xlsx）
```

## 模式与标签页
- 医生端模式（doctor）：
  - Tab1 监测（曲线） + Tab2 积木可视化（校准）
  - 用于设置原始/目标值、权重与误差范围
- 患者端模式（patient）：
  - Tab1 监测（曲线） + Tab3 患者训练
  - 读取事件文件的原始/目标与权重，实时给出训练进度

在 `control_panel.py` 切换模式/数据源/滤波/UDP 等；`main_window.py` 负责同步到 Blocks 与 Patient 标签页。

## 核心数据流
```
硬件(串口/蓝牙)
  → serial_thread.py / bluetooth_receiver.py (data_received 信号)
  → main_window.py:process_sensor_data
    → fliter_processing/*_filter.py (按设置滤波)
    → data_manager.py.add_raw_data_point / add_data_point / add_processed_data_point
    → event_recorder.py.set_current_sensor_data (RAW 与 PROCESSED)
    → 定时器限频刷新 _refresh_realtime_ui()
        ↳ plot_widget.py.update_plot (Tab1 + Tab2/Tab3)
        ↳ block_visualization.blocks_tab_manager.process_sensor_data 或 patient_blocks_tab.update_sensor_data
    → UDP 限频发送（SpineDataSender 或患者端数据包）
```

## 模块调用与信号/槽规则
- main_window.py（主编排）
  - 创建与持有：`ControlPanel`, `SensorPlotWidget(×3)`, `DataManager`, 过滤器组, `BlocksTabManager`, `PatientBlocksTab`, `EventRecorder`, `EventLogger`
  - 连接：
    - `control_panel.acquisition_started → start_acquisition()`
    - `control_panel.acquisition_stopped → stop_acquisition()`
    - `serial_thread.data_received → process_sensor_data()`
    - `bluetooth_receiver.data_received → process_sensor_data()`
    - `blocks_manager.alert_signal → show_alert()`
    - `control_panel.events_path_changed → event_recorder.set_events_file_path()` 与同步到 Patient / Blocks
    - `control_panel.sensor_count_changed → 过滤器/可视化/事件记录器 同步
    - 脊柱类型/方向变化：同步到 `SpineDataSender` 与两个标签页
- 数据采集层
  - `serial_thread.py`：`start()` 后在线程中读取串口数据，周期性发射 `data_received(list)`
  - `bluetooth_receiver.py`：`connect()` + `start_receiving()`，或轮询 `_poll_bluetooth_data()` 兜底
- 可视化与训练
  - 医生端：`blocks_tab.py` 内部组合 `block_control_panel.py` 与 `sensor_selector.py` 管理阶段参数；`blocks_visualizer.py` 负责3D积木显示
  - 患者端：`patient_blocks_tab.py` 读取事件文件映射数据，给出阶段驱动与反馈
- 过滤与增强
  - 三类滤波器均提供 `filter_data_with_timestamp(data)` 与统计接口；在采集开始时按控制面板参数重置与更新

## 阶段与事件（医生端/文件映射）
- 阶段与事件名（用于事件文件与 UDP 映射）：
  - 阶段1：骨盆前后翻转（开始训练 / 完成阶段）
  - 阶段2：脊柱曲率矫正（开始矫正 / 矫正完成）
  - 阶段3a：骨盆左右倾斜（开始沉髋 / 沉髋结束）
  - 阶段3b：肩部左右倾斜（开始沉肩 / 沉肩结束）
- `event_recorder.py` 记录字段包括：时间、stage、各 `sensorN` 值、各 `weightN` 权重、`error_range` 等
- `SpineDataSender.load_events_file()` 会读取事件文件，按上述事件名填充每阶段的 `original_values / target_values / weights / error_range`

## UDP 发送（Unity 等外部系统）
- 网络设置在控制面板里配置：启用、主机、端口；`main_window.py` 驱动 `SpineDataSender`
- 发送频率限为约 50Hz（可在主窗口 `_udp_send_hz` 调整）
- **根据脊柱类型发送不同数量的控制器参数**：
  - **C型脊柱**：4个控制器参数 (gray_rotation, blue_curvature, gray_tilt, green_tilt)
  - **S型脊柱**：5个控制器参数 (gray_rotation, blue_curvature_up, blue_curvature_down, gray_tilt, green_tilt)
- 字段与示例
  - 医生端C型脊柱（`SpineDataSender.send_spine_data`）：
    ```json
    {
      "timestamp": 1731122334.123,
      "sensor_data": [2500, 2510, ...],
      "stage_values": {
        "gray_rotation": 0.42,
        "blue_curvature": 0.31,
        "gray_tilt": 0.55,
        "green_tilt": 0.20
      },
      "stage_error_ranges": {
        "gray_rotation": 0.1,
        "blue_curvature": 0.1,
        "gray_tilt": 0.1,
        "green_tilt": 0.1
      },
      "spine_curve": 0.31,               // C型：blue_curvature值
      "sensor_count": 10,
      "events_file_loaded": true,
      "spine_type": "C",
      "spine_direction": "left"
    }
    ```
  - 医生端S型脊柱（`SpineDataSender.send_spine_data`）：
    ```json
    {
      "timestamp": 1731122334.123,
      "sensor_data": [2500, 2510, ...],
      "stage_values": {
        "gray_rotation": 0.42,
        "blue_curvature_up": 0.31,
        "blue_curvature_down": 0.28,
        "gray_tilt": 0.55,
        "green_tilt": 0.20
      },
      "stage_error_ranges": {
        "gray_rotation": 0.1,
        "blue_curvature_up": 0.1,
        "blue_curvature_down": 0.1,
        "gray_tilt": 0.1,
        "green_tilt": 0.1
      },
      "spine_curve": 0.31,               // S型：max(blue_curvature_up, blue_curvature_down)
      "sensor_count": 10,
      "events_file_loaded": true,
      "spine_type": "S",
      "spine_direction": "lumbar_left"
    }
    ```
  - 患者端（根据脊柱类型自动适配）：
    ```json
    {
      "timestamp": 1731122334.567,
      "sensor_data": [2500, 2510, ...],
      "stage_values": {
        // C型：4个参数或S型：5个参数
      },
      "stage_error_ranges": {
        // 对应的误差范围
      },
      "sensor_count": 10,
      "events_file_loaded": true,
      "spine_type": "C" // 或 "S"
    }
    ```
- 脊柱类型/方向：由控制面板广播同步到所有组件，影响UDP数据包的结构和 `spine_curve` 的计算

## 性能与稳定性
- UI 限频刷新：约 30Hz（`_ui_refresh_hz`），由 `_ui_refresh_timer` 统一驱动三个图表与 Blocks/Patient 更新
- UDP 限频发送：约 50Hz（`_udp_send_hz`），避免对外部系统与本机网络造成压力
- 蓝牙轮询日志降噪：最多每 5 秒打印一次，避免控制台刷屏带来的卡顿

## 运行与保存
- 采集开始：在控制面板设置端口/波特率/传感器数量/保存路径/事件路径，点击“开始采集”
- 采集中：
  - 医生端可在 Tab2 设置各阶段 `original/target` 与 `weights`、`error_range`
  - 患者端会读取事件文件，按阶段指导训练
- 采集停止：自动保存 RAW 与 PROCESSED 数据到 CSV；训练记录（如启用）保存为 xlsx

## 核心逻辑梳理（调用规则）
- 开始采集
  1) ControlPanel → `acquisition_started`
  2) MainWindow → `start_acquisition()`：创建/启动 Serial 或 Bluetooth；重置/更新滤波器；设置三页曲线；Blocks/Patient 进入采集/训练模式
- 数据到达
  1) Serial/Bluetooth → `data_received(list)`
  2) MainWindow → `process_sensor_data()`：滤波→保存 RAW/PROCESSED→更新 EventRecorder 当前值→缓存 `_last_processed_data`→按限频 UDP 发送→按秒打印阶段指标
  3) 定时器 → `_refresh_realtime_ui()`：按模式刷新图表与 Blocks/Patient
- 停止采集
  1) ControlPanel → `acquisition_stopped`
  2) MainWindow → `stop_acquisition()`：停止线程/轮询→汇总统计→保存数据与训练记录→停止 Blocks/Patient

## 扩展指引
- 新增传感器/阶段：补充 `sensor_selector.py` 与事件文件映射；更新 `blocks_tab.py`/`patient_blocks_tab.py`
- 新增滤波方法：在 `fliter_processing/` 中新增实现，并在 `control_panel.py` + `main_window.py` 接入
- 对接外部系统：修改 `SpineDataSender` 主机/端口或扩展字段；如需更高/低频，调整 `_udp_send_hz`

## 备注
- 仓库包含多个历史版本目录（如 `V22wyw/` 等），当前维护版本为 `TeXpine/TeXpine-main/`。
- 若运行缺少依赖，请按报错信息补充安装（如 `pyqtgraph`, `scipy`, `pandas`, `openpyxl`）。