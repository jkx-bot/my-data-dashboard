import socket
import threading
import time
from datetime import datetime
import matplotlib.pyplot as plt

# 无人机心跳监控类（自发自收、超时检测、数据记录、可视化）
class DroneHeartbeat:
    def __init__(self, local_ip="127.0.0.1", port=5006, timeout=3):
        self.local_ip = local_ip
        self.port = port
        self.timeout_threshold = timeout  # 3秒超时
        self.seq = 0                      # 心跳序号
        self.running = True               # 运行标志
        
        # 数据存储：序号、发送时间、接收时间、是否超时
        self.heartbeat_data = []
        self.last_recv_time = time.time()
        
        # UDP套接字（自发自收）
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.2)
        self.sock.bind((local_ip, port))
        
        # 线程锁
        self.lock = threading.Lock()

    # 发送线程：每秒发送一次心跳
    def send_heartbeat(self):
        while self.running:
            start = time.time()
            self.seq += 1
            send_time = time.time()
            msg = f"{self.seq},{send_time}"
            
            try:
                self.sock.sendto(msg.encode(), (self.local_ip, self.port))
                print(f"[发送] 序号:{self.seq}  | 时间:{datetime.fromtimestamp(send_time).strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"发送失败: {e}")
            
            # 精确1秒周期
            cost = time.time() - start
            time.sleep(max(0, 1 - cost))

    # 接收 + 超时检测 线程（合并，更简洁）
    def recv_and_check(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(1024)
                recv_time = time.time()
                msg = data.decode().split(",")
                
                if len(msg) == 2:
                    seq = int(msg[0])
                    send_time = float(msg[1])
                    rtt = recv_time - send_time

                    with self.lock:
                        self.last_recv_time = recv_time
                        self.heartbeat_data.append({
                            "seq": seq,
                            "send_time": send_time,
                            "recv_time": recv_time,
                            "rtt": rtt,
                            "timeout": False
                        })
                    print(f"[正常] 序号:{seq}  | RTT:{rtt:.3f}s")

            except socket.timeout:
                # 超时检测
                now = time.time()
                with self.lock:
                    if now - self.last_recv_time > self.timeout_threshold:
                        print(f"[警告] 连接超时！{self.timeout_threshold}秒未收到心跳")
                        self.heartbeat_data.append({
                            "seq": self.seq,
                            "send_time": now - self.timeout_threshold,
                            "recv_time": None,
                            "rtt": None,
                            "timeout": True
                        })
                        self.last_recv_time = now  # 避免重复报警
            except Exception as e:
                if self.running:
                    print(f"接收异常: {e}")

    # 启动程序
    def start(self):
        print("=== 无人机心跳模拟器启动 ===")
        print(f"本地IP:{self.local_ip}  端口:{self.port}  超时:{self.timeout_threshold}s\n")
        
        threading.Thread(target=self.send_heartbeat, daemon=True).start()
        threading.Thread(target=self.recv_and_check, daemon=True).start()

    # 停止并绘图
    def stop_and_plot(self):
        self.running = False
        time.sleep(0.5)
        try:
            self.sock.close()
        except:
            pass
        print("\n=== 模拟器已停止，生成图表 ===")
        
        # 绘图：修复字体和负号问题
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]  # 用微软雅黑替代SimHei，支持完整符号
        plt.rcParams["axes.unicode_minus"] = False             # 正常显示负号，避免Glyph 8722警告
        plt.figure(figsize=(10, 6))

        # 子图1：RTT变化
        plt.subplot(2,1,1)
        seqs = [d["seq"] for d in self.heartbeat_data]
        rtts = [d["rtt"] if d["rtt"] is not None else 0 for d in self.heartbeat_data]
        plt.plot(seqs, rtts, "b-o", linewidth=1, markersize=3, label="RTT(秒)")
        plt.title("心跳RTT变化曲线")
        plt.ylabel("往返时间")
        plt.grid(True)
        plt.legend()

        # 子图2：超时统计
        plt.subplot(2,1,2)
        timeouts = [1 if d["timeout"] else 0 for d in self.heartbeat_data]
        ok_cnt = len(timeouts) - sum(timeouts)
        timeout_cnt = sum(timeouts)
        plt.pie([ok_cnt, timeout_cnt], labels=["正常", "超时"], colors=["green","red"], autopct="%1.1f%%")
        plt.title(f"心跳统计  总计:{len(seqs)}个")

        plt.tight_layout()
        plt.show()

# ==================== 主程序 ====================
if __name__ == "__main__":
    # 创建实例：3秒超时
    heartbeat = DroneHeartbeat(timeout=3)
    
    try:
        heartbeat.start()
        # 运行30秒自动停止
        time.sleep(30)
    except KeyboardInterrupt:
        print("\n用户手动停止")
    finally:
        heartbeat.stop_and_plot()
        
