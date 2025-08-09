# 智能服装传感器监测系统 - 模块化结构分析

## 系统整体架构

这是一个基于PyQt5的智能服装传感器监测与可视化系统，采用模块化设计，主要用于实时监测传感器数据并提供积木可视化训练功能。

### 核心架构图
```
main_window.py (主窗口/系统集成)
├── 数据采集层
│   ├── serial_thread.py (串口数据采集)
│   └── bluetooth_receiver.py (蓝牙数据采集)
├── 数据处理层
│   ├── data_manager.py (数据存储管理)
│   └── utils.py (工具函数)
├── 界面控制层
│   ├── control_panel.py (主控制面板)
│   ├── plot_widget.py (数据图表显示)
│   └── config.py (配置管理)
└── 功能模块层
    ├── 积木可视化模块
    │   ├── blocks_tab.py (积木标签页)
    │   ├── blocks_visualizer.py (积木可视化)
    │   ├── block_control_panel.py (积木控制面板)
    │   └── sensor_selector.py (传感器选择器)
    └── 训练记录模块
        ├── training_recorder.py (训练记录器)
        └── training_report_tab.py (训练报告)
```

---

## 模块详细分析

### 1. 主入口模块

#### main_window.py - 系统主窗口
**功能职责：**
- 系统总入口，负责整体架构搭建和模块集成
- 管理三个主要标签页：监测、积木可视化、报告
- 协调数据采集、处理和显示的整体流程
- 处理应用程序生命周期

**核心方法：**
- `__init__()`: 初始化所有组件并建立连接
- `start_acquisition()`: 启动数据采集
- `stop_acquisition()`: 停止采集并保存数据
- `process_data()`: 处理接收到的传感器数据
- `_handle_training_record()`: 处理训练记录事件

**调用关系：**
- 创建：`ControlPanel`, `SensorPlotWidget`, `DataManager`, `BlocksTab`, `TrainingReportTab`
- 使用：`SerialThread`, `BluetoothReceiver`
- 信号连接：与所有子组件建立信号槽连接

---

### 2. 数据采集层

#### serial_thread.py - 串口数据采集线程
**功能职责：**
- 独立线程处理串口数据读取，避免阻塞UI
- 支持设定采集时长和传感器数量
- 实时解析CSV格式的传感器数据

**核心方法：**
- `run()`: 线程主循环，读取串口数据
- `set_duration()`: 设置采集时长
- `stop()`: 停止数据采集

**数据流向：**
```
串口设备 → SerialThread.run() → data_received信号 → MainWindow.process_data()
```

**被调用者：** `main_window.py`

#### bluetooth_receiver.py - 蓝牙数据接收器
**功能职责：**
- 通过蓝牙串口接收传感器数据
- 支持自动连接和断开重连
- 数据格式验证和错误处理

**核心方法：**
- `connect()`: 连接蓝牙设备
- `start_receiving()`: 开始数据接收
- `_receive_data_thread()`: 数据接收线程

**数据流向：**
```
蓝牙设备 → BluetoothReceiver → data_received信号 → MainWindow.process_data()
```

**被调用者：** `main_window.py`

---

### 3. 数据处理层

#### data_manager.py - 数据存储管理
**功能职责：**
- 内存中存储实时传感器数据
- 数据持久化：保存为CSV格式
- 数据加载和导入功能

**核心方法：**
- `add_data_point()`: 添加单个数据点
- `save_data()`: 保存数据到CSV文件
- `load_data()`: 从CSV文件加载数据
- `start_acquisition()`: 开始新的采集会话

**数据格式：**
```python
# 数据结构：[timestamp, sensor1, sensor2, ..., sensorN]
data_point = [1.234, 2500, 2600, 2700, ...]
```

**被调用者：** `main_window.py`, `control_panel.py`

#### config.py - 配置管理
**功能职责：**
- 管理应用程序配置参数
- 配置文件的读取和保存
- 提供默认配置和配置验证

**配置项：**
- 串口参数：波特率、默认传感器数量
- UI参数：窗口大小、分割比例
- 数据参数：默认保存路径、颜色设置

**被调用者：** 可被任何需要配置的模块调用

---

### 4. 界面控制层

#### control_panel.py - 主控制面板
**功能职责：**
- 串口/蓝牙连接配置界面
- 数据采集参数设置（传感器数量、采集时长）
- 文件保存路径设置
- 曲线显示控制（颜色、可见性、名称）

**核心功能区域：**
1. **串口设置组**：数据源选择、端口配置、波特率设置
2. **文件保存设置组**：保存路径选择
3. **曲线可见性控制组**：动态生成的传感器曲线控制
4. **控制按钮组**：开始/停止采集

**信号发送：**
- `acquisition_started/stopped`: 采集控制信号
- `path_changed`: 保存路径变更
- `curve_visibility/color/name_changed`: 曲线显示控制

**被调用者：** `main_window.py`

#### plot_widget.py - 数据图表显示
**功能职责：**
- 实时显示多路传感器数据曲线
- 支持滑动窗口和自动滚动
- 曲线样式自定义（颜色、可见性、名称）

**核心方法：**
- `setup_curves()`: 初始化多条曲线
- `update_plot()`: 更新图表数据
- `set_curve_visibility/color/name()`: 曲线样式控制

**显示特性：**
- 使用pyqtgraph实现高性能实时绘图
- 支持大数据量显示（滑动窗口机制）
- 图例和网格显示

**被调用者：** `main_window.py`

---

### 5. 积木可视化模块

#### blocks_tab.py - 积木可视化标签页
**功能职责：**
- 整合积木可视化的所有组件
- 管理三个训练阶段的切换
- 协调传感器数据到可视化的映射

**三个训练阶段：**
1. **阶段1**：骨盆前后旋转（只调整骨盆前后翻转）
2. **阶段2**：发力阶段（只调整脊柱曲率矫正）
3. **阶段3**：平衡阶段（调整骨盆和肩部左右倾斜）

**核心组件集成：**
- `BlockControlPanel`: 参数控制面板
- `BlocksVisualizer`: 3D积木可视化
- `SensorPlotWidget`: 传感器曲线
- `TrainingRecorder`: 训练记录器

**被调用者：** `main_window.py`

#### blocks_visualizer.py - 积木3D可视化控件
**功能职责：**
- 实时3D积木动画显示
- 根据传感器数据计算积木位置和形态
- 阈值警报的视觉反馈

**可视化元素：**
1. **灰色方块**：骨盆，支持前后旋转和左右倾斜
2. **蓝色方块链**：脊柱，使用贝塞尔曲线显示曲率
3. **绿色方块**：肩部，支持左右倾斜

**数学模型：**
```python
# 贝塞尔曲线计算脊柱弯曲
pos = (1-s)**2 * P0 + 2*(1-s)*s*P1 + s**2*P2
```

**被调用者：** `blocks_tab.py`

#### block_control_panel.py - 积木控制面板
**功能职责：**
- 整合4个传感器选择器组件
- 管理不同阶段的高亮显示
- 设置各阶段的默认参数值

**4个控制组件：**
- `gray_rotation`: 骨盆前后翻转
- `blue_curvature`: 脊柱曲率矫正  
- `gray_tilt`: 骨盆左右倾斜
- `green_tilt`: 肩部左右倾斜

**阶段管理：**
- `highlight_stage()`: 高亮当前阶段控件
- `set_stage_defaults()`: 设置阶段默认值

**被调用者：** `blocks_tab.py`

#### sensor_selector.py - 传感器选择器
**功能职责：**
- 多传感器线性组合配置
- 传感器权重设置和归一化计算
- 阈值监控和警报触发

**核心算法：**
```python
# 归一化计算
norm = (sensor_val - rbv) / (ov - rbv)
# 加权组合
combined_value = weighted_sum / total_weight
```

**界面组件：**
- 传感器选择复选框
- 权重调节旋钮
- 原始值/最佳值设置
- 手动测试滑块

**被调用者：** `block_control_panel.py`

---

### 6. 训练记录模块

#### training_recorder.py - 训练记录器
**功能职责：**
- 记录不同训练阶段的关键事件
- 数据标注和时间戳记录
- 训练数据导出功能

**记录事件类型：**
- **阶段1**：记录原始值、记录训练后值
- **阶段2**：开始发力、完成发力
- **阶段3**：记录发力值、开始/完成沉肩、开始/完成沉髋

**数据结构：**
```python
recording_data = {
    "stage1": {
        "original": {"timestamp": "...", "sensor_data": [...]},
        "trained": {"timestamp": "...", "sensor_data": [...]}
    }
}
```

**被调用者：** `blocks_tab.py`

#### training_report_tab.py - 训练报告标签页
**功能职责：**
- 显示训练记录的统计分析
- 提供数据可视化图表
- 导出训练报告功能

**显示组件：**
- 训练阶段记录表格
- 传感器数据曲线图
- 事件标记和时间轴
- 导出按钮

**被调用者：** `main_window.py`

---

## 数据流图

### 主要数据流向：
```
传感器设备
    ↓
[串口/蓝牙采集层]
    ↓ data_received信号
MainWindow.process_data()
    ↓ 数据分发
├── DataManager.add_data_point() → 数据存储
├── PlotWidget.update_plot() → 实时曲线显示  
├── BlocksTab.process_sensor_data() → 积木可视化
└── TrainingRecorder → 训练记录

积木可视化数据流：
传感器数据 → SensorSelector.set_sensor_value() 
    → 归一化计算 → BlocksVisualizer.update() → 3D显示
```

---

## 信号槽连接图

### 主要信号连接：
```
ControlPanel:
├── acquisition_started → MainWindow.start_acquisition()
├── acquisition_stopped → MainWindow.stop_acquisition()
├── path_changed → DataManager.set_save_path()
└── curve_*_changed → PlotWidget.set_curve_*()

DataCollectors:
├── SerialThread.data_received → MainWindow.process_data()
├── BluetoothReceiver.data_received → MainWindow.process_data()
└── *.error_occurred → MainWindow.handle_serial_error()

BlocksTab:
├── alert_signal → MainWindow.show_alert()
└── TrainingRecorder.record_signal → MainWindow._handle_training_record()
```

---

## 扩展指南

### 添加新的传感器类型：
1. 在`sensor_selector.py`中扩展传感器选择逻辑
2. 在`blocks_visualizer.py`中添加新的可视化元素
3. 在`block_control_panel.py`中集成新的控制组件

### 添加新的训练阶段：
1. 在`training_recorder.py`中添加新阶段的记录逻辑
2. 在`blocks_tab.py`中扩展阶段切换逻辑
3. 在`block_control_panel.py`中添加阶段默认值设置

### 添加新的数据源：
1. 创建新的数据采集类（参考`serial_thread.py`）
2. 在`main_window.py`中集成新的数据源
3. 在`control_panel.py`中添加相应的配置选项

### 优化建议：
1. **性能优化**：大数据量时考虑数据采样和缓存策略
2. **错误处理**：加强异常处理和用户反馈
3. **配置管理**：扩展配置系统支持更多自定义选项
4. **测试覆盖**：添加单元测试和集成测试
5. **文档完善**：添加API文档和用户手册