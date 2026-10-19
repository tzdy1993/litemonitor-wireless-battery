# LiteMonitor 2.4G 无线外设电量监控插件 (WirelessPeripheral Battery)

<p align="center">
  <img src="https://img.shields.io/badge/LiteMonitor-Plugin-blue?style=flat-square" alt="LiteMonitor Plugin" />
  <img src="https://img.shields.io/badge/Platform-Windows_10%2F11-0078D6?style=flat-square&logo=windows" alt="Windows" />
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" />
</p>

专为 [LiteMonitor](https://github.com/Diorser/LiteMonitor) 任务栏硬件监控软件打造的 **2.4G 无线外设（鼠标/耳机）实时电量监控插件与超低开销本地桥接服务**。

彻底告别各家外设厂商臃肿的驱动托盘图标或割裂的桌面悬浮窗，将无线外设的电量状态优雅地嵌入在 Windows 任务栏托盘区左侧，享受 LiteMonitor 原生透明无底、动态三色联动、双行靠右排列的极致美观体验。

---

## ✨ 核心特性

- 🎮 **极致性能，游戏 0 卡顿 / 0 抢占保障**
  - **操作系统级防抢占**：后台进程通过 Windows 原生 API 硬性锁定为 `IDLE_PRIORITY_CLASS`（系统最低空闲级别）。前台游戏享有绝对排他优先权，Windows 调度器在物理上严禁后台服务抢占游戏的 CPU 时间片。
  - **内存缓存解耦**：LiteMonitor 请求时直接命中内存字典瞬间返回（< 0.5ms），不触发同步硬件阻塞。
  - **内核挂起等待**：耳机 HID 查询采用内核事件挂起（`WaitForSingleObject`），硬件等待期间 CPU 消耗恒定为 `0.00%`，平均 CPU 占用率低于 `0.005%`，内存占用仅约 `25MB`。
- ⚡ **零 C++ 编译与原生硬件直连**
  - 底层基于 `hid_win.py`（纯 Python ctypes 封装 Windows `setupapi.dll` / `hid.dll` / `kernel32.dll`），无需安装 `hidapi`、`pywinusb` 或配置任何复杂的 Visual Studio C++ 编译环境。
- 🔄 **开机零延迟自启**
  - 配套自动注册 Windows 原生计划任务（`LiteMonitorBatteryBridge`），开机登录立即同步就绪，彻底避免 Windows 开始菜单启动文件夹常有的 1~2 分钟系统滞后延迟。
- 🔋 **多外设支持与智能状态解析**
  - **英菲克无线鼠标 (Inphic IN10R / 8K nano 等)**：自动对接官方服务本地 WebSocket (`127.0.0.1:10085`)，被动接收实时电量与充放电心跳。
  - **漫步者花再无线耳机 (Edifier Halo Space D1 等)**：直接向 2.4G 接收器（`VID_2D99 & PID_E049`）发送底层 HID 64 字节 Output Report，动态异或解密第 6 字节电量。
  - 自动识别设备待机休眠与离线状态，支持三色告警（正常绿色、预警黄色、低电红色）。

---

## 📸 效果展示

```text
任务栏托盘左侧展示（靠右双行紧凑排列）：
  🖱️ 78%
  🎧 100%
或使用紧凑合体项：
  外设: 🖱️78% 🎧100%
```

---

## 🚀 快速上手

### 1. 一键安装
1. 确保电脑已安装 **Python 3.8+**（安装时请勾选 `Add Python to PATH`）。
2. 下载本项目源码解压，双击运行 **`install.bat`**。
3. 脚本会自动安装轻量依赖、将插件文件 `WirelessBattery.json` 部署至 LiteMonitor 的 `resources\plugins\` 目录，并注册开机自启动计划任务。

### 2. 在 LiteMonitor 中启用
1. 打开 LiteMonitor，右键选择 **【设置】** ➡️ 点击 **【插件设置】**（或点击右上角【重载插件】）。
2. 在插件列表中找到 **【无线外设双电量 (鼠标/耳机)】**，点击启用。
3. 切换至 **【任务栏】** 页面，找到新增的指标项并勾选：
   - `🖱️` 鼠标电量 (`mouse`)
   - `🎧` 耳机电量 (`headset`)
   - *(可选)* 外设合体项 (`combined`)
4. 建议将任务栏对齐方式设置为 **【靠右对齐】**、布局设为 **【双行显示】**，即可获得最佳视觉效果！

---

## 🛠️ 架构与二次开发

本项目采用 **本地轻量级桥接架构**：

```mermaid
flowchart LR
    A[无线鼠标 / 耳机] -->|2.4G 接收器 / 驱动| B(本地后台服务 bridge_server.py)
    B -->|GET 127.0.0.1:28888/battery <0.5ms| C(LiteMonitor 插件引擎)
    C -->|原生透明渲染| D[Windows 任务栏]
```

### 本地 API 规范
服务常驻在 `http://127.0.0.1:28888/battery`，返回标准的 JSON 格式：

```json
{
  "mouse_level": "78",
  "mouse_charging": 0,
  "mouse_status": "正常连接",
  "mouse_color": "0",
  "headset_level": "100",
  "headset_charging": 0,
  "headset_status": "正常连接",
  "headset_color": "0",
  "time": "20:45:10"
}
```

### 如何添加新设备？
只需在项目中编写对应的 `xxx_reader.py`（继承或返回 `DeviceReading` 对象），并在 `bridge_server.py` 的 `BatteryDataCache` 中挂载更新，即可无缝扩展罗技、雷蛇、Keychron 等其他外设！

---

## 🗑️ 卸载

双击运行 **`uninstall.bat`**，脚本将立即停止服务并从 Windows 计划任务中完全注销。

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。
