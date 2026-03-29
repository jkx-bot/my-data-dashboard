import time
import random
from datetime import datetime, timedelta, timezone

class HeartbeatSimulator:
    def __init__(self, timeout_threshold=3.0):
        """
        初始化心跳模拟器
        :param timeout_threshold: 超时阈值（秒），超过此值认为丢包
        """
        self.timeout_threshold = timeout_threshold
        self.seq = 0
        
    def generate_packet(self):
        """
        生成单次心跳数据包，包含时间戳、RTT模拟和状态判定
        """
        self.seq += 1
        
        # 1. 获取北京时间 (UTC+8) 用于横坐标显示
        tz_utc_8 = timezone(timedelta(hours=8))
        time_str = datetime.now(tz_utc_8).strftime("%H:%M:%S")
        
        # 2. 模拟网络往返时间 (RTT)
        send_time = time.time()
        rand_val = random.random()
        
        # 初始化变量，确保不会出现 NameError
        rtt = 0.0
        is_timeout = False
        
        if rand_val < 0.8:
            # 80% 概率：网络正常，低延迟
            rtt = random.uniform(0.015, 0.045)
            is_timeout = False
        elif rand_val < 0.95:
            # 15% 概率：网络波动，中等延迟
            rtt = random.uniform(0.1, 0.8)
            is_timeout = False
        else:
            # 5% 概率：模拟丢包或极高延迟（超过阈值）
            rtt = self.timeout_threshold + random.uniform(0.1, 0.5)
            is_timeout = True
            
        # 3. 返回封装好的数据字典
        return {
            "seq": self.seq,               # 序号
            "time": time_str,              # 北京时间字符串 (HH:MM:SS)
            "send_time": send_time,        # 发送时间戳
            "rtt": rtt,                    # 往返时间
            "is_timeout": is_timeout,      # 是否超时标志
            "status": "正常" if not is_timeout else "超时/丢包"
        }

    def get_summary(self, history):
        """
        根据历史记录计算统计信息
        :param history: 存储 packet 字典的列表
        :return: (平均RTT, 丢包率)
        """
        if not history:
            return 0.0, 0.0
            
        total = len(history)
        # 统计超时个数
        timeouts = sum(1 for p in history if p.get('is_timeout', False))
        loss_rate = (timeouts / total) * 100
        
        # 计算非超时包的平均 RTT
        valid_rtts = [p['rtt'] for p in history if not p.get('is_timeout', False)]
        avg_rtt = sum(valid_rtts) / len(valid_rtts) if valid_rtts else 0.0
        
        return avg_rtt, loss_rate