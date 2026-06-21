# heartbeat.py
# 无人机心跳包模拟模块
# 每秒发送一个心跳包，包含序号和时间戳

import time
import datetime
import threading
import streamlit as st

class HeartbeatSimulator:
    def __init__(self):
        self.heartbeats = []  # 存储所有心跳包
        self.seq = 0
        self.is_running = False
        self.last_receive_time = None
        self.is_timeout = False
        self.lock = threading.Lock()
        
    def start(self):
        """启动心跳模拟"""
        if not self.is_running:
            self.is_running = True
            self.seq = 0
            self.heartbeats = []
            self.is_timeout = False
            self.last_receive_time = time.time()
            thread = threading.Thread(target=self._send_heartbeat, daemon=True)
            thread.start()
            
    def stop(self):
        """停止心跳模拟"""
        self.is_running = False
        
    def _send_heartbeat(self):
        """后台线程：每秒发送一个心跳包"""
        while self.is_running:
            self.seq += 1
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            heartbeat = {
                "seq": self.seq,
                "timestamp": timestamp,
                "time": time.time()
            }
            with self.lock:
                self.heartbeats.append(heartbeat)
                self.last_receive_time = time.time()
                self.is_timeout = False
            time.sleep(1)
            
    def check_timeout(self):
        """检查是否超时（3秒未收到心跳）"""
        with self.lock:
            if self.last_receive_time is not None:
                if time.time() - self.last_receive_time > 3:
                    self.is_timeout = True
                    return True
            return False
            
    def get_heartbeats(self):
        """获取所有心跳包数据"""
        with self.lock:
            return self.heartbeats.copy()
            
    def get_latest_seq(self):
        """获取最新序号"""
        with self.lock:
            if self.heartbeats:
                return self.heartbeats[-1]["seq"]
            return 0