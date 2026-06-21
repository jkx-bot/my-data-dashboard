# app.py
# 无人机智能化应用 - 主程序
# 功能：心跳监测 + 3D地图 + 航线规划 + 飞行监控 + 通信拓扑

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import json
import os
import time
import datetime
import numpy as np

# 导入自定义模块
from coord_transform import wgs84_to_gcj02, SCHOOL_LAT, SCHOOL_LON
from heartbeat import HeartbeatSimulator

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="无人机导航与通信可视化系统",
    page_icon="🚁",
    layout="wide"
)

# ==================== 初始化Session State ====================
if 'heartbeat_sim' not in st.session_state:
    st.session_state.heartbeat_sim = HeartbeatSimulator()
    st.session_state.heartbeat_running = False
    
if 'obstacles' not in st.session_state:
    # 默认障碍物（学校内）
    st.session_state.obstacles = [
        {"lat": SCHOOL_LAT + 0.0003, "lon": SCHOOL_LON + 0.0005, "radius": 50, "height": 30},
        {"lat": SCHOOL_LAT - 0.0004, "lon": SCHOOL_LON + 0.0008, "radius": 40, "height": 25},
        {"lat": SCHOOL_LAT + 0.0005, "lon": SCHOOL_LON - 0.0003, "radius": 60, "height": 35},
        {"lat": SCHOOL_LAT - 0.0002, "lon": SCHOOL_LON - 0.0006, "radius": 45, "height": 20},
    ]
    
if 'point_a' not in st.session_state:
    st.session_state.point_a = {"lat": SCHOOL_LAT + 0.001, "lon": SCHOOL_LON - 0.001}
    
if 'point_b' not in st.session_state:
    st.session_state.point_b = {"lat": SCHOOL_LAT - 0.001, "lon": SCHOOL_LON + 0.001}
    
if 'flight_log' not in st.session_state:
    st.session_state.flight_log = []
    
if 'waypoints' not in st.session_state:
    st.session_state.waypoints = []
    
if 'flight_started' not in st.session_state:
    st.session_state.flight_started = False
    
if 'flight_progress' not in st.session_state:
    st.session_state.flight_progress = 0
    
if 'battery' not in st.session_state:
    st.session_state.battery = 100

# ==================== 侧边栏 ====================
st.sidebar.title("🚁 无人机控制系统")
st.sidebar.markdown("---")

# 坐标系统选择
coord_system = st.sidebar.selectbox(
    "坐标系选择",
    ["WGS-84", "GCJ-02"],
    help="WGS-84为国际标准，GCJ-02为中国加密坐标系"
)

st.sidebar.markdown("---")

# 点A设置
st.sidebar.subheader("📍 航点A")
lat_a = st.sidebar.number_input("纬度A", value=st.session_state.point_a["lat"], format="%.6f")
lon_a = st.sidebar.number_input("经度A", value=st.session_state.point_a["lon"], format="%.6f")

# 点B设置
st.sidebar.subheader("📍 航点B")
lat_b = st.sidebar.number_input("纬度B", value=st.session_state.point_b["lat"], format="%.6f")
lon_b = st.sidebar.number_input("经度B", value=st.session_state.point_b["lon"], format="%.6f")

# 更新点A/B
if st.sidebar.button("更新航点"):
    st.session_state.point_a = {"lat": lat_a, "lon": lon_a}
    st.session_state.point_b = {"lat": lat_b, "lon": lon_b}
    st.sidebar.success("✅ 航点已更新")

st.sidebar.markdown("---")

# 飞行参数设置
st.sidebar.subheader("✈️ 飞行参数")
flight_height = st.sidebar.slider("飞行高度 (米)", 10, 200, 50)
safe_radius = st.sidebar.slider("安全半径 (米)", 5, 100, 30)

# 绕飞模式选择
avoid_mode = st.sidebar.selectbox(
    "绕飞模式",
    ["向左绕飞", "向右绕飞", "最优路径"],
    help="选择障碍物避让策略"
)

st.sidebar.markdown("---")

# 心跳控制
st.sidebar.subheader("💓 心跳监测")
if st.sidebar.button("启动心跳", key="start_heartbeat"):
    if not st.session_state.heartbeat_running:
        st.session_state.heartbeat_sim.start()
        st.session_state.heartbeat_running = True
        st.sidebar.success("✅ 心跳已启动")

if st.sidebar.button("停止心跳", key="stop_heartbeat"):
    st.session_state.heartbeat_sim.stop()
    st.session_state.heartbeat_running = False
    st.sidebar.warning("⏹️ 心跳已停止")

# ==================== 主界面 ====================
st.title("🚁 无人机导航与通信可视化系统")
st.caption(f"南京科技职业学院 | 坐标系: {coord_system} | 当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==================== Tab布局 ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📡 心跳监测", 
    "🗺️ 3D地图", 
    "✈️ 航线规划", 
    "📊 飞行监控",
    "📡 通信拓扑"
])

# ==================== Tab1: 心跳监测 ====================
with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📡 实时心跳数据")
        # 检查超时
        if st.session_state.heartbeat_running:
            timeout = st.session_state.heartbeat_sim.check_timeout()
            if timeout:
                st.error("🚨 连接超时！3秒未收到心跳包")
            else:
                st.success("✅ 连接正常")
        else:
            st.info("⏸️ 心跳未启动，请点击侧边栏启动")
            
        # 显示心跳数据表格
        heartbeats = st.session_state.heartbeat_sim.get_heartbeats()
        if heartbeats:
            df = pd.DataFrame(heartbeats[-20:])  # 显示最近20条
            if 'time' in df.columns:
                df = df.drop('time', axis=1)
            st.dataframe(df, use_container_width=True)
            
    with col2:
        st.subheader("📈 心跳序号趋势")
        if len(heartbeats) > 1:
            df_plot = pd.DataFrame(heartbeats)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(df_plot))),
                y=df_plot['seq'],
                mode='lines+markers',
                name='心跳序号',
                line=dict(color='#00ff00', width=2)
            ))
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_title="包序号",
                yaxis_title="序号值",
                template="plotly_dark"
            )
            st.plotly_chart(fig, use_container_width=True)
            
        # 统计信息
        if heartbeats:
            st.metric("总心跳包数", len(heartbeats))
            st.metric("最新序号", heartbeats[-1]['seq'] if heartbeats else 0)

# ==================== Tab2: 3D地图 ====================
with tab2:
    st.subheader("🗺️ 3D地图与障碍物显示")
    
    # 坐标转换显示
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📍 航点A: ({st.session_state.point_a['lat']:.6f}, {st.session_state.point_a['lon']:.6f})")
        # 显示转换后的坐标
        if coord_system == "GCJ-02":
            gcj_a = wgs84_to_gcj02(st.session_state.point_a['lat'], st.session_state.point_a['lon'])
            st.caption(f"   → GCJ-02: ({gcj_a[0]:.6f}, {gcj_a[1]:.6f})")
            
    with col2:
        st.info(f"📍 航点B: ({st.session_state.point_b['lat']:.6f}, {st.session_state.point_b['lon']:.6f})")
        if coord_system == "GCJ-02":
            gcj_b = wgs84_to_gcj02(st.session_state.point_b['lat'], st.session_state.point_b['lon'])
            st.caption(f"   → GCJ-02: ({gcj_b[0]:.6f}, {gcj_b[1]:.6f})")
    
    # 创建Folium地图
    map_center = [SCHOOL_LAT, SCHOOL_LON]
    m = folium.Map(
        location=map_center,
        zoom_start=16,
        tiles='OpenStreetMap'
    )
    
    # 添加航点A
    folium.Marker(
        [st.session_state.point_a['lat'], st.session_state.point_a['lon']],
        popup='航点A (起点)',
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)
    
    # 添加航点B
    folium.Marker(
        [st.session_state.point_b['lat'], st.session_state.point_b['lon']],
        popup='航点B (终点)',
        icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa')
    ).add_to(m)
    
    # 添加障碍物（圆形）
    for i, obs in enumerate(st.session_state.obstacles):
        folium.Circle(
            [obs['lat'], obs['lon']],
            radius=obs.get('radius', 50),
            color='red',
            fill=True,
            fillOpacity=0.3,
            popup=f"障碍物 {i+1}: 高{obs.get('height', 0)}m"
        ).add_to(m)
        folium.Marker(
            [obs['lat'], obs['lon']],
            icon=folium.Icon(color='orange', icon='warning', prefix='fa'),
            popup=f"障碍物 {i+1}"
        ).add_to(m)
    
    # 添加A到B的连线（路径示意）
    folium.PolyLine(
        [[st.session_state.point_a['lat'], st.session_state.point_a['lon']],
         [st.session_state.point_b['lat'], st.session_state.point_b['lon']]],
        color='blue',
        weight=2,
        opacity=0.8,
        popup='规划路径'
    ).add_to(m)
    
    # 添加学校标记
    folium.Marker(
        [SCHOOL_LAT, SCHOOL_LON],
        popup='🏫 南京科技职业学院',
        icon=folium.Icon(color='blue', icon='university', prefix='fa')
    ).add_to(m)
    
    # 显示地图
    st_data = st_folium(m, width=800, height=500)
    
    # 障碍物管理
    with st.expander("🔄 障碍物管理"):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.write("当前障碍物列表:")
            for i, obs in enumerate(st.session_state.obstacles):
                st.write(f"{i+1}. 位置: ({obs['lat']:.6f}, {obs['lon']:.6f}) | 半径: {obs.get('radius', 50)}m | 高度: {obs.get('height', 0)}m")
        
        with col2:
            # 添加障碍物
            st.subheader("添加障碍物")
            new_lat = st.number_input("纬度", value=SCHOOL_LAT + 0.0001, format="%.6f")
            new_lon = st.number_input("经度", value=SCHOOL_LON + 0.0001, format="%.6f")
            new_radius = st.number_input("半径 (米)", value=50)
            new_height = st.number_input("高度 (米)", value=30)
            if st.button("添加障碍物"):
                st.session_state.obstacles.append({
                    "lat": new_lat,
                    "lon": new_lon,
                    "radius": new_radius,
                    "height": new_height
                })
                st.success("✅ 障碍物已添加")
                st.rerun()
            
            if st.button("重置障碍物"):
                st.session_state.obstacles = []
                st.success("✅ 障碍物已清空")
                st.rerun()

# ==================== Tab3: 航线规划 ====================
with tab3:
    st.subheader("✈️ 航线规划")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.info(f"**飞行参数**")
        st.write(f"🛫 飞行高度: {flight_height} 米")
        st.write(f"🛡️ 安全半径: {safe_radius} 米")
        st.write(f"🔄 绕飞模式: {avoid_mode}")
        st.write(f"📍 航点A → 航点B: {st.session_state.point_a} → {st.session_state.point_b}")
        
        # 生成航点
        if st.button("🚀 生成航线", type="primary"):
            # 模拟生成航点（实际应该使用路径规划算法）
            waypoints = []
            # 计算A到B的方向
            lat_diff = st.session_state.point_b['lat'] - st.session_state.point_a['lat']
            lon_diff = st.session_state.point_b['lon'] - st.session_state.point_a['lon']
            
            # 生成10个航点（包含起点和终点）
            for i in range(10):
                t = i / 9  # 0到1
                lat = st.session_state.point_a['lat'] + lat_diff * t
                lon = st.session_state.point_a['lon'] + lon_diff * t
                
                # 根据绕飞模式添加偏移
                if avoid_mode == "向左绕飞":
                    offset = -0.0002 * np.sin(t * np.pi) * (safe_radius / 50)
                elif avoid_mode == "向右绕飞":
                    offset = 0.0002 * np.sin(t * np.pi) * (safe_radius / 50)
                else:  # 最优路径
                    offset = 0
                    
                # 添加障碍物避让（简单模拟）
                for obs in st.session_state.obstacles:
                    dist = ((lat - obs['lat'])**2 + (lon - obs['lon'])**2)**0.5
                    if dist < 0.0005:  # 如果靠近障碍物
                        if avoid_mode == "向左绕飞":
                            lat += 0.0001
                        elif avoid_mode == "向右绕飞":
                            lat -= 0.0001
                        else:
                            # 最优路径：直接绕开
                            lat += 0.0001 * np.sign(lat - obs['lat'])
                            lon += 0.0001 * np.sign(lon - obs['lon'])
                
                waypoints.append({
                    "seq": i + 1,
                    "lat": lat,
                    "lon": lon,
                    "height": flight_height
                })
            
            st.session_state.waypoints = waypoints
            st.success(f"✅ 已生成 {len(waypoints)} 个航点")
            
    with col2:
        st.subheader("🗺️ 航线预览")
        if st.session_state.waypoints:
            # 在Folium地图上显示航线
            m_route = folium.Map(location=[SCHOOL_LAT, SCHOOL_LON], zoom_start=16, tiles='OpenStreetMap')
            
            # 绘制航点
            for wp in st.session_state.waypoints:
                folium.CircleMarker(
                    [wp['lat'], wp['lon']],
                    radius=5,
                    color='blue',
                    fill=True,
                    popup=f"航点{wp['seq']}"
                ).add_to(m_route)
            
            # 绘制航线
            route_points = [[wp['lat'], wp['lon']] for wp in st.session_state.waypoints]
            folium.PolyLine(
                route_points,
                color='red',
                weight=3,
                opacity=0.8
            ).add_to(m_route)
            
            # 添加障碍物
            for obs in st.session_state.obstacles:
                folium.Circle(
                    [obs['lat'], obs['lon']],
                    radius=obs.get('radius', 50),
                    color='red',
                    fill=True,
                    fillOpacity=0.2
                ).add_to(m_route)
            
            st_folium(m_route, width=500, height=400)
            
            # 显示航点表格
            df_wp = pd.DataFrame(st.session_state.waypoints)
            st.dataframe(df_wp, use_container_width=True)

# ==================== Tab4: 飞行监控 ====================
with tab4:
    st.subheader("📊 飞行监控面板")
    
    col1, col2, col3 = st.columns(3)
    
    # 模拟飞行数据
    if st.session_state.waypoints and st.button("🛫 开始飞行", type="primary"):
        st.session_state.flight_started = True
        st.session_state.flight_progress = 0
        st.session_state.battery = 100
    
    if st.session_state.flight_started and st.session_state.waypoints:
        # 模拟进度更新
        if st.session_state.flight_progress < len(st.session_state.waypoints) - 1:
            st.session_state.flight_progress += 1
            st.session_state.battery = max(0, st.session_state.battery - 2)
    
    # 显示当前状态
    with col1:
        st.metric("🎯 当前航点", f"{st.session_state.flight_progress + 1} / {len(st.session_state.waypoints) if st.session_state.waypoints else 0}")
        if st.session_state.waypoints and st.session_state.flight_progress < len(st.session_state.waypoints):
            wp = st.session_state.waypoints[st.session_state.flight_progress]
            st.caption(f"经纬度: ({wp['lat']:.6f}, {wp['lon']:.6f})")
            st.caption(f"高度: {wp['height']}m")
    
    with col2:
        # 模拟速度（随时间变化）
        speed = 5 + 3 * np.sin(time.time() / 5)
        st.metric("🚀 飞行速度", f"{speed:.1f} m/s")
        
        elapsed = st.session_state.flight_progress * 2  # 每个航点2秒
        st.metric("⏱️ 已用时间", f"{elapsed}s")
    
    with col3:
        st.metric("🔋 模拟电量", f"{st.session_state.battery}%")
        # 电量进度条
        st.progress(st.session_state.battery / 100)
        
        if st.session_state.waypoints:
            total_dist = len(st.session_state.waypoints) * 50  # 模拟距离
            remain_dist = (len(st.session_state.waypoints) - st.session_state.flight_progress) * 50
            st.metric("📏 剩余距离", f"{remain_dist}m")
            eta = remain_dist / speed if speed > 0 else 0
            st.metric("⏰ 预计到达", f"{eta:.0f}s")
    
    # 飞行轨迹图
    if st.session_state.waypoints:
        st.subheader("🛤️ 飞行轨迹")
        # 创建3D轨迹图
        fig = go.Figure()
        
        # 绘制已飞路径
        if st.session_state.flight_progress > 0:
            flown = st.session_state.waypoints[:st.session_state.flight_progress + 1]
            fig.add_trace(go.Scatter3d(
                x=[wp['lon'] for wp in flown],
                y=[wp['lat'] for wp in flown],
                z=[wp['height'] for wp in flown],
                mode='lines+markers',
                name='已飞路径',
                line=dict(color='green', width=4),
                marker=dict(size=6, color='green')
            ))
        
        # 绘制未飞路径
        if st.session_state.flight_progress < len(st.session_state.waypoints) - 1:
            remaining = st.session_state.waypoints[st.session_state.flight_progress:]
            fig.add_trace(go.Scatter3d(
                x=[wp['lon'] for wp in remaining],
                y=[wp['lat'] for wp in remaining],
                z=[wp['height'] for wp in remaining],
                mode='lines+markers',
                name='剩余路径',
                line=dict(color='gray', width=3, dash='dash'),
                marker=dict(size=4, color='gray')
            ))
        
        # 添加障碍物
        for obs in st.session_state.obstacles:
            fig.add_trace(go.Scatter3d(
                x=[obs['lon']],
                y=[obs['lat']],
                z=[obs.get('height', 30) / 2],
                mode='markers',
                name='障碍物',
                marker=dict(size=15, color='red', symbol='x')
            ))
        
        fig.update_layout(
            height=500,
            scene=dict(
                xaxis_title='经度',
                yaxis_title='纬度',
                zaxis_title='高度 (m)',
                aspectmode='manual',
                aspectratio=dict(x=1, y=1, z=0.3)
            ),
            template='plotly_dark'
        )
        st.plotly_chart(fig, use_container_width=True)

# ==================== Tab5: 通信拓扑 ====================
with tab5:
    st.subheader("📡 通信链路拓扑结构")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🏗️ GCS - OBC - FCU 三层通信架构
        