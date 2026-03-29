import time
import random
from datetime import datetime, timedelta, timezone

class HeartbeatSimulator:
    def __init__(self, timeout_threshold=3.0):
        self.timeout_threshold = timeout_threshold
        self.start_time = time.time()
        self.seq = 0
        
    def generate_packet(self):
        """
        模拟发送并接收一个心跳包的过程
        返回: (序号, 发送时间, RTT往返时间, 是否超时)
        """
        self.seq += 1
        send_time = time.time()
        
        # 模拟网络波动：90% 正常，10% 延迟或丢包
        rand_val = random.random()
        
        if rand_val < 0.9:
            # 正常情况：RTT 在 10ms 到 50ms 之间
            rtt = random.uniform(0.01, 0.05)
            is_timeout = False
        elif rand_val < 0.95:
            # 网络拥塞：RTT 显著增加
            rtt = random.uniform(0.5, 2.0)
            is_timeout = False
        else:
            # 模拟丢包：RTT 超过阈值
            rtt = self.timeout_threshold + random.uniform(0.1, 1.0)
            is_timeout = True
            
        # 模拟处理耗时
        time.sleep(0.05) 
        
        return {
            "seq": self.seq,
            "send_time": send_time,
            "rtt": rtt,
            "is_timeout": is_timeout,
            "status": "正常" if not is_timeout else "超时警告"
        }

    def get_summary(self, history):
        """
        对历史心跳数据进行统计
        """
        if not history:
            return 0, 0
        total = len(history)
        timeouts = sum(1 for p in history if p['is_timeout'])
        loss_rate = (timeouts / total) * 100
        avg_rtt = sum(p['rtt'] for p in history if not p['is_timeout']) / max(1, (total - timeouts))
        return avg_rtt, loss_rate
    
    def generate_packet(self):
        self.seq += 1
        # 获取当前 UTC 时间并转为北京时间 (UTC+8)
        tz_utc_8 = timezone(timedelta(hours=8))
        now_bj = datetime.now(tz_utc_8)
        time_str = now_bj.strftime("%H:%M:%S") # 格式化为 09:30:01
        
        send_time = time.time()
        # ... 之前的随机 RTT 逻辑 ...

        return {
            "seq": self.seq,
            "time": time_str,      # 新增：北京时间字符串
            "send_time": send_time,
            "rtt": rtt,
            "is_timeout": is_timeout,
            "status": "正常" if not is_timeout else "超时警告"
        }