# -*- coding: utf-8 -*-
"""edifier_reader.py —— 漫步者花再 (Halo Space D1) 2.4G 无线耳机电量读取器

硬件信息：
  - 接收器硬件 ID: VID_2D99 & PID_E049
  - 通信接口: UsagePage 0xFF14, Usage 0x0001, in=64, out=64
协议说明：
  - 发送 64 字节 Output Report:
      2E AA EC D0 00 00 66 + 57 个 0x00
  - 接收 64 字节 Input Report:
      首部为 2F BB EC D0 00 01
      第 6 字节为加密电量: battery = resp[6] ^ 0xA5
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

try:
    from . import hid_win as hw
except ImportError:
    import hid_win as hw


@dataclass
class DeviceReading:
    name: str
    level: Optional[int] = None
    status: str = "未初始化"
    charging: bool = False
    online: bool = False
    update_time: float = 0.0

    @property
    def level_str(self) -> str:
        return f"{self.level}%" if self.level is not None else "--"

    @property
    def time_str(self) -> str:
        if not self.update_time:
            return "未更新"
        return time.strftime("%H:%M:%S", time.localtime(self.update_time))


EDIFIER_VID = 0x2D99
EDIFIER_PID = 0xE049
EDIFIER_USAGE_PAGE = 0xFF14


_cached_iface: Optional[hw.HidInterface] = None


def find_edifier_interface() -> Optional[hw.HidInterface]:
    """枚举系统中的 HID 接口，找到漫步者的通信接口（带缓存加速，消除重复枚举）。"""
    global _cached_iface
    if _cached_iface is not None:
        return _cached_iface
    for d in hw.enumerate_hid():
        if d.vid == EDIFIER_VID and d.usage_page == EDIFIER_USAGE_PAGE:
            _cached_iface = d
            return d
    return None


def read_edifier(timeout: float = 0.5) -> DeviceReading:
    """读取漫步者花再耳机当前电量。"""
    global _cached_iface
    r = DeviceReading(name="漫步者花再耳机")

    iface = find_edifier_interface()
    if iface is None:
        r.status = "未找到 2.4G 接收器"
        r.online = False
        r.update_time = time.time()
        return r

    dev = None
    try:
        dev = hw.HidDevice(iface.path, write=True)
        # 构造电量查询帧
        out_len = iface.output_len or 64
        pkt = [0x2E, 0xAA, 0xEC, 0xD0, 0x00, 0x00, 0x66] + [0] * (out_len - 7)
        dev.write_output(bytes(pkt))

        # 读取回包
        timeout_ms = int(timeout * 1000)
        resp = dev.read_input(timeout_ms=timeout_ms)
        now = time.time()
        r.update_time = now

        if not resp:
            r.status = "耳机未开机 / 待机休眠"
            r.online = False
            return r

        if len(resp) >= 7 and resp[0] == 0x2F and resp[1] == 0xBB and resp[2] == 0xEC and resp[3] == 0xD0:
            # 第 6 字节异或 0xA5 解密出电量
            battery = resp[6] ^ 0xA5
            if 0 <= battery <= 100:
                r.level = battery
                r.online = True
                r.status = "正常连接"
                # 检查是否充电状态 (回包中如果有充电标识)
                r.charging = False
                return r

        r.status = f"数据解析异常 ({resp[:8].hex()})"
        r.online = False
        return r

    except Exception as e:
        r.status = f"通信失败: {e}"
        r.online = False
        r.update_time = time.time()
        return r
    finally:
        if dev:
            try:
                dev.close()
            except Exception:
                pass


if __name__ == "__main__":
    reading = read_edifier()
    print(f"[{reading.name}] 电量: {reading.level_str}, 状态: {reading.status}, 时间: {reading.time_str}")
