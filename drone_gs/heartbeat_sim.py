import time
import random
from datetime import datetime, timedelta, timezone

class HeartbeatSimulator:
    def __init__(self, timeout_threshold=3.0):
        """
        初始化心跳模拟器
        :param timeout_threshold: 超时阈值（秒）
        """
        self.timeout_threshold = timeout_threshold
        self.seq = 0
        
    def generate_packet(self):
        """
        生成单次心跳数据包
        """
        self.seq += 1
        
        # 1. 获取北京时间 (UTC+8)
        # 无论在本地还是 Streamlit Cloud (通常是UTC时间) 运行，都能正确显示北京时间
        tz_utc_8 = timezone(timedelta(hours=8))
        time_str = datetime.now(tz_utc_8).strftime("%H:%M:%S")
        
        # 2. 模拟网络往返时间 (RTT) 
        # [核心修复] 在逻辑分支前预定义变量，防止出现 NameError
        rtt = 0.0
        is_timeout = False
        rand_val = random.random()
        
        if rand_val < 0.8:
            # 80% 概率：连接状况良好
            rtt = random.uniform(0.01, 0.05)
            is_timeout = False
        elif rand_val < 0.95:
            # 15% 概率：网络出现波动（抖动）
            rtt = random.uniform(0.1, 0.6)
            is_timeout = False
        else:
            # 5% 概率：模拟丢包或严重超时
            rtt = self.timeout_threshold + random.uniform(0.1, 0.5)
            is_timeout = True
            
        return {
            "seq": self.seq,
            "time": time_str,     # 用于横坐标的北京时间字符串
            "rtt": rtt,
            "is_timeout": is_timeout,
            "status": "正常" if not is_timeout else "超时警告"
        }

    def get_summary(self, history):
        """
        对历史数据进行统计分析
        """
        if not history:
            return 0.0, 0.0
            
        total = len(history)
        timeouts = sum(1 for p in history if p['is_timeout'])
        loss_rate = (timeouts / total) * 100
        
        # 仅对未超时的包计算平均 RTT
        valid_rtts = [p['rtt'] for p in history if not p['is_timeout']]
        avg_rtt = sum(valid_rtts) / len(valid_rtts) if valid_rtts else 0.0
        
        return avg_rtt, loss_rate