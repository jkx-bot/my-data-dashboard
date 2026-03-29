import streamlit as st
import pandas as pd
import pydeck as pdk # 用于 3D 地图
import time

# 设置页面配置
st.set_page_config(page_title="无人机地面站监控", layout="wide")

# --- 侧边栏：导航与坐标系设置 ---
st.sidebar.title("🧭 导航")
page = st.sidebar.radio("功能页面", ["🗺️ 航线规划", "✈️ 飞行监控"])

st.sidebar.divider()
st.sidebar.title("⚙️ 坐标系设置")
coord_system = st.sidebar.radio("输入坐标系", ["WGS-84", "GCJ-02(高德/百度)"])

# --- 页面 1：航线规划 ---
if page == "🗺️ 航线规划":
    st.title("航线规划")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📍 控制面板")
        st.write("**起点 A**")
        lat_a = st.number_input("纬度 (A)", value=32.2322, format="%.4f")
        lon_a = st.number_input("经度 (A)", value=118.7490, format="%.4f")
        st.button("设置 A 点")
        
        st.write("**终点 B**")
        lat_b = st.number_input("纬度 (B)", value=32.2343, format="%.4f")
        lon_b = st.number_input("经度 (B)", value=118.7490, format="%.4f")
        st.button("设置 B 点")
        
        st.divider()
        st.subheader("✈️ 飞行参数")
        height = st.slider("设定飞行高度 (m)", 0, 100, 50)

    with col2:
        st.subheader("🗺️ 地图显示")
        # 使用 Pydeck 实现 3D 效果图
        view_state = pdk.ViewState(latitude=lat_a, longitude=lon_a, zoom=15, pitch=45)
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=[{"lat": lat_a, "lon": lon_a}, {"lat": lat_b, "lon": lon_b}],
            get_position="[lon, lat]",
            get_color="[200, 30, 0, 160]",
            get_radius=30,
        )
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))

# --- 页面 2：飞行监控 ---
elif page == "✈️ 飞行监控":
    st.title("飞行监控")
    st.subheader("💓 心跳包实时监控")
    
    # 这里可以集成你 heartbeat.py 中的数据逻辑
    # 模拟实时数据流
    chart_data = pd.DataFrame({"RTT": [0.01, 0.02, 0.015, 0.03]}) 
    st.line_chart(chart_data)
    
    if st.button("开始心跳监控"):
        st.success("监控已启动...")
        # 调用你的 DroneHeartbeat 类逻辑...