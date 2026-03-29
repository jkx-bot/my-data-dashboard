import streamlit as st
import pandas as pd
import pydeck as pdk
import time
from datetime import datetime
from utils import wgs84_to_gcj02
from heartbeat_sim import HeartbeatSimulator

# 1. 页面基础配置
st.set_page_config(page_title="无人机地面站监控系统", layout="wide")

# 2. 侧边栏导航与设置
st.sidebar.title("🧭 导航控制")
page = st.sidebar.radio("请选择功能页面", ["航线规划", "飞行监控"])

st.sidebar.divider()
coord_mode = st.sidebar.radio("输入坐标系设置", ["WGS-84 (原始)", "GCJ-02 (高德/百度)"])
st.sidebar.info("提示：若地图点位偏移，请切换至 GCJ-02 进行纠偏。")

# 3. 页面逻辑：航线规划
if page == "航线规划":
    st.header("🗺️ 航线规划 (3D 视图)")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📍 坐标输入")
        # 默认值参考作业 Demo
        lat_a = st.number_input("起点 A 纬度", value=32.2322, format="%.6f")
        lon_a = st.number_input("起点 A 经度", value=118.7490, format="%.6f")
        lat_b = st.number_input("终点 B 纬度", value=32.2343, format="%.6f")
        lon_b = st.number_input("终点 B 经度", value=118.7495, format="%.6f")
        
        height = st.slider("设定飞行高度 (m)", 0, 100, 50)
        
        # 坐标纠偏处理
        if coord_mode == "GCJ-02":
            lon_a, lat_a = wgs84_to_gcj02(lon_a, lat_a)
            lon_b, lat_b = wgs84_to_gcj02(lon_b, lat_b)
            st.caption("✅ 已应用 GCJ-02 坐标纠偏")

    with col2:
        # 准备地图数据
        map_data = pd.DataFrame({
            'lat': [lat_a, lat_b],
            'lon': [lon_a, lon_b],
            'name': ['起点 A', '终点 B']
        })
        
        # 定义 3D 地图层：使用 ColumnLayer 体现高度
        view_state = pdk.ViewState(latitude=lat_a, longitude=lon_a, zoom=16, pitch=45)
        
        layer = pdk.Layer(
            "ColumnLayer",
            map_data,
            get_position="[lon, lat]",
            get_elevation=height, 
            elevation_scale=1,
            radius=15,
            get_fill_color=[245, 166, 35, 200],
            pickable=True,
        )
        
        # 增加连线层
        line_layer = pdk.Layer(
            "LineLayer",
            pd.DataFrame({"start": [[lon_a, lat_a]], "end": [[lon_b, lat_b]]}),
            get_source_position="start",
            get_target_position="end",
            get_color=[255, 255, 255, 150],
            get_width=3,
        )
        
        st.pydeck_chart(pdk.Deck(
            layers=[line_layer, layer], 
            initial_view_state=view_state,
            map_style='mapbox://styles/mapbox/satellite-v9' # 卫星地图模式
        ))

# 4. 页面逻辑：飞行监控
elif page == "飞行监控":
    st.header("✈️ 飞行监控 (心跳包实时状态)")
    
    # 初始化模拟器和历史记录到 session_state，防止刷新丢失
    if "sim" not in st.session_state:
        st.session_state.sim = HeartbeatSimulator()
    if "history" not in st.session_state:
        st.session_state.history = []

    # 动态显示容器
    placeholder = st.empty()
    
    # 修复关键：添加唯一的 key 解决 StreamlitDuplicateElementId 报错
    if st.button("开始接收实时数据", key="btn_monitor_start"):
        for _ in range(50): 
            packet = st.session_state.sim.generate_packet()
            st.session_state.history.append(packet)
            
            # 仅取最近 20 条数据用于绘图，保持横轴整洁
            plot_df = pd.DataFrame(st.session_state.history[-20:])
            
            with placeholder.container():
                # 仪表盘指标
                m1, m2, m3 = st.columns(3)
                avg_rtt, loss_rate = st.session_state.sim.get_summary(st.session_state.history)
                
                # 指标显示：包含实时状态标签
                m1.metric("实时 RTT", f"{packet['rtt']:.3f}s", delta=packet['status'], delta_color="inverse")
                m2.metric("平均往返时间", f"{avg_rtt:.3f}s")
                m3.metric("累计丢包率", f"{loss_rate:.1f}%")
                
                # 动态图表：使用北京时间 time 作为索引（横轴）
                st.subheader("通讯延迟 (RTT) 变化曲线")
                st.line_chart(plot_df.set_index("time")["rtt"])
                
                # 实时日志显示
                if packet['is_timeout']:
                    st.error(f"🔴 警报：北京时间 {packet['time']} 发生通讯超时！")
            
            time.sleep(0.5) 
    else:
        st.info("💡 点击上方按钮开始模拟心跳包接收过程。")