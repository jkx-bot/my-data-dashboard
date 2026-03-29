import streamlit as st
import pandas as pd
import pydeck as pdk
import time
from utils import wgs84_to_gcj02
from heartbeat_sim import HeartbeatSimulator

# 页面基础配置
st.set_page_config(page_title="无人机地面站监控系统", layout="wide")

# --- 侧边栏导航 ---
st.sidebar.title("🧭 导航控制")
page = st.sidebar.radio("请选择功能页面", ["航线规划", "飞行监控"])

st.sidebar.divider()
coord_mode = st.sidebar.radio("坐标系设置", ["WGS-84 (原始)", "GCJ-02 (纠偏)"])
st.sidebar.info("提示：若地图点位偏移，请切换至 GCJ-02")

# --- 逻辑处理：航线规划 ---
if page == "航线规划":
    st.header("🗺️ 航线规划 (3D 视图)")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📍 坐标输入")
        lat_a = st.number_input("起点 A 纬度", value=32.2322, format="%.6f")
        lon_a = st.number_input("起点 A 经度", value=118.7490, format="%.6f")
        lat_b = st.number_input("终点 B 纬度", value=32.2343, format="%.6f")
        lon_b = st.number_input("终点 B 经度", value=118.7495, format="%.6f")
        
        height = st.slider("设定飞行高度 (m)", 0, 100, 50)
        
        # 坐标纠偏处理
        if coord_mode == "GCJ-02":
            lon_a, lat_a = wgs84_to_gcj02(lon_a, lat_a)
            lon_b, lat_b = wgs84_to_gcj02(lon_b, lat_b)
            st.caption("已自动应用坐标偏移修正")

    with col2:
        # 准备地图数据
        map_data = pd.DataFrame({
            'lat': [lat_a, lat_b],
            'lon': [lon_a, lon_b],
            'name': ['起点 A', '终点 B']
        })
        
        # 定义 3D 地图层
        view_state = pdk.ViewState(latitude=lat_a, longitude=lon_a, zoom=16, pitch=45)
        
        layer = pdk.Layer(
            "ColumnLayer",
            map_data,
            get_position="[lon, lat]",
            get_elevation=height, # 柱状图高度对应飞行高度
            elevation_scale=1,
            radius=15,
            get_fill_color=[245, 166, 35, 200],
            pickable=True,
        )
        
        st.pydeck_chart(pdk.Deck(
            layers=[layer], 
            initial_view_state=view_state,
            # 常用样式：
            # 'mapbox://styles/mapbox/satellite-v9' (卫星图，作业 Demo 效果)
            #   'mapbox://styles/mapbox/light-v9' (简洁白)
            # 'mapbox://styles/mapbox/dark-v9' (科技黑)
            map_style='mapbox://styles/mapbox/satellite-v9', 
            tooltip={
                "html": "<b>位置:</b> {name}",
                "style": {"color": "white"}
            }
        ))
# --- 逻辑处理：飞行监控 ---
elif page == "飞行监控":
    st.header("✈️ 飞行监控 (心跳包实时状态)")
    
    # 初始化模拟器和历史记录到 session_state
    if "sim" not in st.session_state:
        st.session_state.sim = HeartbeatSimulator()
    if "history" not in st.session_state:
        st.session_state.history = []

    # 实时显示容器
    placeholder = st.empty()
    
    if st.button("开始接收实时数据"):
        for _ in range(30): # 模拟运行30个心跳周期
            packet = st.session_state.sim.generate_packet()
            st.session_state.history.append(packet)
            
            # 仅取最近 30 条数据用于绘图
            plot_df = pd.DataFrame(st.session_state.history[-30:])
            
            with placeholder.container():
                # 仪表盘指标
                m1, m2, m3 = st.columns(3)
                avg_rtt, loss_rate = st.session_state.sim.get_summary(st.session_state.history)
                
                m1.metric("实时 RTT", f"{packet['rtt']:.3f}s", delta=packet['status'], delta_color="inverse")
                m2.metric("平均往返时间", f"{avg_rtt:.3f}s")
                m3.metric("当前丢包率", f"{loss_rate:.1f}%")
                
                # 动态折线图
                st.subheader("通讯延迟 (RTT) 变化曲线")
                st.line_chart(plot_df.set_index("seq")["rtt"])
                
                # 状态列表
                if packet['is_timeout']:
                    st.error(f"警告：序号 {packet['seq']} 丢包或超时！")
            
            time.sleep(0.4) # 模拟真实频率
    else:
        st.info("请点击上方按钮启动监控模拟器")