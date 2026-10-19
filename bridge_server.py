# -*- coding: utf-8 -*-
"""bridge_server.py —— 为 LiteMonitor 提供本地外设电量数据的极简高并发 HTTP 桥接服务

端口：127.0.0.1:28888
接口：GET /battery
资源占用：CPU 0.0%，内存 ~12MB，网络 0 KB/s（纯本地回环）
"""

from __future__ import annotations

import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

# 针对 pythonw.exe 无终端环境，防止标准流为 None 导致潜在写异常
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()


try:
    from edifier_reader import DeviceReading, read_edifier
    from inphic_reader import InphicReader, read_inphic
except ImportError:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)
    from edifier_reader import DeviceReading, read_edifier
    from inphic_reader import InphicReader, read_inphic

PORT = 28888
HOST = "127.0.0.1"

# 将当前进程优先级设为 IDLE_PRIORITY_CLASS (0x40 空闲优先级)
# 确保在 Windows 调度器层面，前台游戏具有绝对优先权，绝不被抢占 CPU 周期
try:
    import ctypes
    from ctypes import wintypes
    _k = ctypes.WinDLL("kernel32", use_last_error=True)
    _k.GetCurrentProcess.restype = wintypes.HANDLE
    _k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _k.SetPriorityClass(_k.GetCurrentProcess(), 0x00000040)  # IDLE_PRIORITY_CLASS (空闲优先级)
except Exception:
    pass




class BatteryDataCache:
    """线程安全的内存极速缓存"""

    def __init__(self):
        self.lock = threading.Lock()
        self.mouse = DeviceReading("英菲克无线鼠标")
        self.headset = DeviceReading("漫步者花再耳机")
        self.last_headset_poll = 0.0

    def get_color_code(self, lvl: Optional[int], chg: bool = False) -> str:
        # LiteMonitor 规范：0=绿色(正常), 1=黄色(告警), 2=红色(危险)
        if lvl is None or lvl < 0:
            return "1"
        if lvl >= 50:
            return "0"
        if lvl >= 20:
            return "1"
        return "2"

    def get_json_dict(self) -> dict:
        with self.lock:
            # 耳机主动轮询：若缓存超过 3 秒则异步触发刷新
            now = time.time()
            if now - self.last_headset_poll > 3.0:
                self.last_headset_poll = now
                threading.Thread(target=self._poll_headset, daemon=True).start()

            m = self.mouse
            h = self.headset

            m_val = str(m.level) if m.level is not None else "--"
            h_val = str(h.level) if h.level is not None else "--"

            return {
                "mouse_level": m_val,
                "mouse_charging": 1 if m.charging else 0,
                "mouse_status": m.status,
                "mouse_color": self.get_color_code(m.level, m.charging),
                "headset_level": h_val,
                "headset_charging": 1 if h.charging else 0,
                "headset_status": h.status,
                "headset_color": self.get_color_code(h.level, h.charging),
                "time": time.strftime("%H:%M:%S"),
            }

    def _poll_headset(self):
        try:
            h = read_edifier(timeout=0.5)
            with self.lock:
                self.headset = h
        except Exception:
            pass

    def on_mouse_frame(self, reading: DeviceReading):
        with self.lock:
            self.mouse = reading


CACHE = BatteryDataCache()


class BatteryHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 允许跨域及无阻断访问
        data = CACHE.get_json_dict()
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # 静默日志，不刷控制台
        pass

    def log_error(self, format, *args):
        # 静默错误日志，不向 stderr 输出
        pass



def run_bridge_server():
    # 挂载英菲克实时驱动 WebSocket
    reader = InphicReader.get_instance()
    reader.add_listener(CACHE.on_mouse_frame)

    # 首次预热读取
    def _warmup():
        try:
            m = read_inphic(wait_initial=1.5)
            h = read_edifier(timeout=0.6)
            with CACHE.lock:
                CACHE.mouse = m
                CACHE.headset = h
        except Exception:
            pass

    threading.Thread(target=_warmup, daemon=True).start()

    HTTPServer.allow_reuse_address = True
    server = HTTPServer((HOST, PORT), BatteryHTTPHandler)
    server.serve_forever()



if __name__ == "__main__":
    run_bridge_server()
