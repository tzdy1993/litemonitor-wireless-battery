# -*- coding: utf-8 -*-
"""inphic_reader.py —— 英菲克 (IN10R 8K / 其它型号) 2.4G 无线鼠标电量读取器

硬件信息：
  - 接收器硬件 ID: VID_1D57 & PID_FA65 (8K nano 接收器)
通信机制：
  - 英菲克官方配套微型服务位于：C:\\Program Files (x86)\\Inphic\\Inphic.exe
  - 服务常驻监听本地 WebSocket 端口：ws://127.0.0.1:10085
  - 连入后驱动会自动下发电量心跳帧（十六进制文本格式）：
      例如 "8201039840015a"
      - 0x82 (130): 2.4G 无线连接
      - 0x98 (152): 设备 ID (IN10R)
      - 0x01: 电池工作状态 (1 为放电使用中，2 为充电中)
      - 0x5a (90): 电池电量百分比 90%
"""

from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from typing import Optional

try:
    from .edifier_reader import DeviceReading
except ImportError:
    from edifier_reader import DeviceReading

try:
    import websocket
except ImportError:
    websocket = None


DEFAULT_INPHIC_PATHS = [
    r"C:\Program Files (x86)\Inphic\Inphic.exe",
    r"C:\Program Files\Inphic\Inphic.exe",
]


class InphicReader:
    _instance: Optional["InphicReader"] = None
    _lock = threading.Lock()

    def __init__(self, inphic_path: Optional[str] = None):
        self.inphic_path = inphic_path or self._find_inphic_exe()
        self.reading = DeviceReading(name="英菲克无线鼠标")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._ws = None
        self._child_proc: Optional[subprocess.Popen] = None
        self._last_rx_time = 0.0
        self._listeners: list = []

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    @classmethod
    def get_instance(cls) -> "InphicReader":
        with cls._lock:
            if cls._instance is None:
                cls._instance = InphicReader()
                cls._instance.start()
            return cls._instance

    def _find_inphic_exe(self) -> Optional[str]:
        for p in DEFAULT_INPHIC_PATHS:
            if os.path.isfile(p):
                return p
        return None

    def _is_service_listening(self) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            s.connect(("127.0.0.1", 10085))
            s.close()
            return True
        except Exception:
            return False

    def _ensure_service_running(self):
        if self._is_service_listening():
            return True
        if not self.inphic_path or not os.path.isfile(self.inphic_path):
            return False
        try:
            # 零黑窗启动 Inphic.exe
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
            self._child_proc = subprocess.Popen(
                [self.inphic_path],
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.2)
            return self._is_service_listening()
        except Exception:
            return False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="InphicWSClient")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _parse_packet(self, data_str: str):
        try:
            raw = bytes.fromhex(data_str.strip())
        except Exception:
            return

        n = list(raw)
        # 匹配长度为 7 或 6 的心跳帧
        if (len(n) == 7 or len(n) == 6) and (128 <= n[0] <= 133):
            # 7 字节帧格式:
            # n[0]: 连接方式 (130 = 2.4G)
            # n[3]: deviceId (152 为 IN10R)
            # n[4]: 状态标记 (64 或 65)
            # n[5]: 电池状态 (1 为放电, 2 为充电)
            # n[6]: 电池电量 (0~100)
            if len(n) == 7:
                dev_id = n[3]
                b_status = n[5]
                b_level = n[6]
            else:
                dev_id = n[2]
                b_status = n[4]
                b_level = n[5]

            if 0 <= b_level <= 100:
                self.reading.level = b_level
                self.reading.online = True
                self.reading.charging = (b_status == 2)
                self.reading.status = "正在充电" if self.reading.charging else "正常连接"
                self.reading.update_time = time.time()
                self._last_rx_time = time.time()

                for cb in list(self._listeners):
                    try:
                        cb(self.reading)
                    except Exception:
                        pass

    def _worker_loop(self):
        if websocket is None:
            self.reading.status = "缺少 websocket-client 库"
            self.reading.online = False
            return

        while self._running:
            if not self._ensure_service_running():
                self.reading.status = "未找到驱动服务 Inphic.exe"
                self.reading.online = False
                time.sleep(3)
                continue

            try:
                ws = websocket.create_connection("ws://127.0.0.1:10085", timeout=3)
                self._ws = ws
                while self._running:
                    try:
                        msg = ws.recv()
                        if not msg:
                            break
                        self._parse_packet(msg)
                    except websocket.WebSocketTimeoutException:
                        # 检查超时，若长时间无心跳则标为休眠
                        if time.time() - self._last_rx_time > 30 and self.reading.level is not None:
                            self.reading.status = "鼠标休眠中"
                        continue
                    except Exception:
                        break
            except Exception:
                pass
            finally:
                if self._ws:
                    try:
                        self._ws.close()
                    except Exception:
                        pass
                    self._ws = None

            # 若断开，短暂停顿后重试
            time.sleep(2)

    def get_reading(self, wait_initial: float = 2.5) -> DeviceReading:
        if not self._running:
            self.start()

        # 初次调用若暂无电量，等待片刻接收首帧
        if self.reading.level is None and wait_initial > 0:
            start_t = time.time()
            while time.time() - start_t < wait_initial:
                if self.reading.level is not None:
                    break
                time.sleep(0.1)

        return self.reading


def read_inphic(wait_initial: float = 2.5) -> DeviceReading:
    return InphicReader.get_instance().get_reading(wait_initial=wait_initial)


if __name__ == "__main__":
    reader = InphicReader.get_instance()
    r = reader.get_reading(wait_initial=2.0)
    print(f"[{r.name}] 电量: {r.level_str}, 状态: {r.status}, 充电: {r.charging}, 时间: {r.time_str}")
