"""
无人机通信与飞行监控系统 — UAV Communication & Flight Monitoring System
南京科技职业学院 campus
"""

import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json
import time
import os
from datetime import datetime

from utils.coordinate import wgs84_to_gcj02, gcj02_to_wgs84
from utils.heartbeat import HeartbeatState
from utils.route import Point, Obstacle, plan_route, calculate_route_stats
from utils.flight import FlightState
from utils.topology import TopologyState

# ---- Page config ----
st.set_page_config(
    page_title="无人机通信与飞行监控系统",
    page_icon="🛸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Constants ----
CAMPUS_CENTER = (32.2333, 118.749)  # 南京科技职业学院
DEFAULT_POINT_A = (32.2322, 118.749)
DEFAULT_POINT_B = (32.2343, 118.749)
OBSTACLES_FILE = os.path.join(os.path.dirname(__file__), "obstacles.json")

# ---- Session state initialization ----
if "heartbeat" not in st.session_state:
    st.session_state.heartbeat = HeartbeatState()
if "flight" not in st.session_state:
    st.session_state.flight = FlightState()
if "topology" not in st.session_state:
    st.session_state.topology = TopologyState()
if "obstacles" not in st.session_state:
    st.session_state.obstacles = []
if "point_a" not in st.session_state:
    st.session_state.point_a = DEFAULT_POINT_A
if "point_b" not in st.session_state:
    st.session_state.point_b = DEFAULT_POINT_B
if "flight_height" not in st.session_state:
    st.session_state.flight_height = 50
if "safety_radius" not in st.session_state:
    st.session_state.safety_radius = 10
if "route_strategy" not in st.session_state:
    st.session_state.route_strategy = "最优路径"
if "planned_route" not in st.session_state:
    st.session_state.planned_route = None
if "coord_system" not in st.session_state:
    st.session_state.coord_system = "WGS-84"
if "flight_started" not in st.session_state:
    st.session_state.flight_started = False

# ---- Handle map right-click context menu actions ----
params = st.query_params
if "set_a" in params:
    try:
        vals = params["set_a"].split(",")
        st.session_state.point_a = (float(vals[0]), float(vals[1]))
        del st.query_params["set_a"]
        st.rerun()
    except (ValueError, IndexError):
        pass
if "set_b" in params:
    try:
        vals = params["set_b"].split(",")
        st.session_state.point_b = (float(vals[0]), float(vals[1]))
        del st.query_params["set_b"]
        st.rerun()
    except (ValueError, IndexError):
        pass


def load_obstacles():
    if os.path.exists(OBSTACLES_FILE):
        try:
            with open(OBSTACLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for o in data:
                if "height" not in o:
                    o["height"] = 50.0
            return [Obstacle(**o) for o in data]
        except Exception:
            return []
    return []


def save_obstacles(obs_list: list[Obstacle]):
    data = [{"lng": o.lng, "lat": o.lat, "radius": o.radius, "height": o.height}
            for o in obs_list]
    with open(OBSTACLES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if "obstacles_loaded" not in st.session_state:
    st.session_state.obstacles = load_obstacles()
    st.session_state.obstacles_loaded = True


def create_map(lat: float, lng: float, zoom: int = 17, height: int = 500) -> folium.Map:
    """Create a folium map with Gaode tiles (fast in China, no API key)."""
    m = folium.Map(location=[lat, lng], zoom_start=zoom,
                   tiles=None, height=height, control_scale=True)
    folium.TileLayer(
        tiles="https://webrd01.is.autonavi.com/appmaptile?"
              "lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        attr="高德地图",
        name="高德地图",
        overlay=False,
        control=False,
    ).add_to(m)
    return m


def add_context_menu(folium_map: folium.Map):
    """Inject a right-click context menu via onerror trick (bypasses script sanitization)."""
    map_name = folium_map.get_name()

    # JS code that creates context menu on right-click
    js_code = (
        'var _m = window["' + map_name + '"];'
        'if(_m){'
        'var _d=document.createElement("div");'
        '_d.id="cm-' + map_name + '";'
        '_d.style.cssText="display:none;position:absolute;z-index:9999;'
        "background:#2d2d2d;border:1px solid #666;border-radius:6px;"
        'min-width:140px;box-shadow:0 4px 14px rgba(0,0,0,0.6);font-family:sans-serif;";'
        '_d.innerHTML=\'<div style="padding:8px 14px;cursor:pointer;color:#00ff88;font-size:14px;" '
        'onmouseover="this.style.background=\\\'#3a3a3a\\\'" '
        'onmouseout="this.style.background=\\\'transparent\\\'" '
        'id="cma-' + map_name + '">📍 设为 A 点</div>'
        '<div style="padding:8px 14px;cursor:pointer;color:#00aaff;font-size:14px;" '
        'onmouseover="this.style.background=\\\'#3a3a3a\\\'" '
        'onmouseout="this.style.background=\\\'transparent\\\'" '
        'id="cmb-' + map_name + '">📍 设为 B 点</div>\';'
        'document.body.appendChild(_d);'
        'var _la=0,_lo=0;'
        '_m.on("contextmenu",function(e){'
        'L.DomEvent.preventDefault(e);'
        '_la=e.latlng.lat;_lo=e.latlng.lng;'
        'var c=_m.getContainer().getBoundingClientRect();'
        'var p=_m.latLngToContainerPoint(e.latlng);'
        '_d.style.display="block";'
        '_d.style.left=(c.left+p.x)+"px";'
        '_d.style.top=(c.top+p.y)+"px";'
        '});'
        'document.addEventListener("click",function(e){'
        'if(e.target!==_d&&!_d.contains(e.target))_d.style.display="none";'
        '});'
        'document.getElementById("cma-' + map_name + '").onclick=function(){'
        '_d.style.display="none";'
        'window.location.href=window.location.origin+window.location.pathname'
        '+"?set_a="+_la.toFixed(7)+","+_lo.toFixed(7);'
        '};'
        'document.getElementById("cmb-' + map_name + '").onclick=function(){'
        '_d.style.display="none";'
        'window.location.href=window.location.origin+window.location.pathname'
        '+"?set_b="+_la.toFixed(7)+","+_lo.toFixed(7);'
        '};'
        '}'
    )

    # Use onerror trick to bypass script stripping
    bypass = folium.Element(
        '<img src="x" style="display:none" '
        'onerror="' + js_code.replace('"', '&quot;') + '">'
    )
    folium_map.get_root().html.add_child(bypass)


def add_draw_plugin(m: folium.Map):
    """Add rectangle/circle drawing tools for obstacle selection."""
    plugins.Draw(
        export=False,
        position='topleft',
        draw_options={
            'polyline': False,
            'polygon': False,
            'rectangle': {'shapeOptions': {'color': '#ff3333', 'weight': 2, 'fillOpacity': 0.2}},
            'circle': {'shapeOptions': {'color': '#ff3333', 'weight': 2, 'fillOpacity': 0.2}},
            'marker': False,
            'circlemarker': False,
        },
        edit_options={'edit': False, 'remove': True},
    ).add_to(m)


def parse_drawings_to_obstacles(drawings: list) -> list[Obstacle]:
    """Convert GeoJSON drawings from folium Draw plugin to Obstacle objects."""
    obstacles = []
    for feature in drawings:
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})
        geom_type = geom.get("type")

        if geom_type == "Polygon":
            coords = geom["coordinates"][0]
            lngs = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            center_lng = (min(lngs) + max(lngs)) / 2
            center_lat = (min(lats) + max(lats)) / 2
            corner = Point(min(lngs), min(lats))
            center = Point(center_lng, center_lat)
            radius = center.distance_to(corner)
            obstacles.append(Obstacle(lng=center_lng, lat=center_lat,
                                      radius=max(radius, 5), height=50.0))

        elif geom_type == "Point":
            coords = geom["coordinates"]
            radius = props.get("radius", 30)
            obstacles.append(Obstacle(lng=coords[0], lat=coords[1],
                                      radius=radius, height=50.0))

    return obstacles


# ---- Sidebar Navigation ----
st.sidebar.title("🛸 无人机监控系统")
st.sidebar.markdown("南京科技职业学院")
tab = st.sidebar.radio(
    "导航菜单",
    ["💓 心跳监测", "🗺️ 3D地图与坐标", "🛫 航线规划", "📡 飞行监控", "🔗 通信拓扑"],
)

# ===================================================================
# Tab 1: Heartbeat Monitor
# ===================================================================
if tab == "💓 心跳监测":
    st.title("💓 基础心跳监测系统")
    st.markdown("模拟无人机心跳包自发自收，地面站监控连接状态")

    hb = st.session_state.heartbeat

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if not hb.running:
            if st.button("▶️ 启动心跳", use_container_width=True):
                hb.start()
                st.rerun()
        else:
            if st.button("⏹️ 停止心跳", use_container_width=True):
                hb.stop()
                st.rerun()

    with col2:
        if st.button("⚠️ 模拟超时", use_container_width=True, disabled=not hb.running):
            hb.trigger_timeout()
            st.rerun()

    with col3:
        if st.button("🔄 重置", use_container_width=True):
            hb.reset()
            st.rerun()

    with col4:
        timeout = hb.check_timeout()
        if timeout:
            st.error("🚨 连接超时!")
        elif hb.running:
            st.success("✅ 连接正常")
        else:
            st.info("⏸️ 已停止")

    st.subheader("心跳包时序图")
    if hb.packets:
        df = pd.DataFrame([{"seq": p.seq, "time": datetime.fromtimestamp(p.timestamp).strftime("%H:%M:%S"),
                            "timestamp": p.timestamp} for p in hb.packets])
        fig = px.line(df, x="seq", y="timestamp", markers=True,
                      labels={"seq": "心跳包序号", "timestamp": "时间戳"},
                      title="心跳包接收记录")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"共收到 {len(hb.packets)} 个心跳包，最新序号: {hb.packets[-1].seq}")
    else:
        st.info("尚未收到任何心跳包，请点击「启动心跳」")

    st.subheader("数据导出")
    if hb.packets:
        data_json = json.dumps([{"seq": p.seq, "timestamp": p.timestamp} for p in hb.packets],
                               ensure_ascii=False, indent=2)
        st.download_button("📥 下载心跳数据 (JSON)", data_json,
                           file_name="heartbeat_data.json", mime="application/json")

# ===================================================================
# Tab 2: 3D Map & Coordinates (Folium)
# ===================================================================
elif tab == "🗺️ 3D地图与坐标":
    st.title("🗺️ 3D地图显示与坐标管理")
    st.markdown("校园坐标点设置、障碍物管理、坐标系转换")

    coord_sys = st.radio("坐标系", ["WGS-84", "GCJ-02"], horizontal=True,
                         key="coord_sys_selector")
    st.session_state.coord_system = coord_sys

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📍 坐标点 A")
        a_lat = st.number_input("纬度 A", value=st.session_state.point_a[0],
                                format="%.6f", key="a_lat")
        a_lng = st.number_input("经度 A", value=st.session_state.point_a[1],
                                format="%.6f", key="a_lng")
        st.session_state.point_a = (a_lat, a_lng)

    with col_b:
        st.subheader("📍 坐标点 B")
        b_lat = st.number_input("纬度 B", value=st.session_state.point_b[0],
                                format="%.6f", key="b_lat")
        b_lng = st.number_input("经度 B", value=st.session_state.point_b[1],
                                format="%.6f", key="b_lng")
        st.session_state.point_b = (b_lat, b_lng)

    st.subheader("🔄 坐标系转换")
    col_wgs, col_gcj = st.columns(2)
    with col_wgs:
        st.markdown("**WGS-84**")
        st.text(f"A: ({a_lat:.6f}, {a_lng:.6f})")
        st.text(f"B: ({b_lat:.6f}, {b_lng:.6f})")
    with col_gcj:
        st.markdown("**GCJ-02 (火星坐标系)**")
        gcj_a = wgs84_to_gcj02(a_lng, a_lat)
        gcj_b = wgs84_to_gcj02(b_lng, b_lat)
        st.text(f"A: ({gcj_a[1]:.6f}, {gcj_a[0]:.6f})")
        st.text(f"B: ({gcj_b[1]:.6f}, {gcj_b[0]:.6f})")

    st.subheader("🚧 障碍物管理")
    st.caption("障碍物数据自动保存，刷新后仍保留")

    col_obs, col_obs_list = st.columns([1, 1])

    with col_obs:
        obs_lat = st.number_input("障碍物纬度", value=CAMPUS_CENTER[0], format="%.6f", key="obs_lat")
        obs_lng = st.number_input("障碍物经度", value=CAMPUS_CENTER[1], format="%.6f", key="obs_lng")
        obs_radius = st.slider("障碍物半径 (米)", 5, 200, 30, key="obs_radius")
        obs_height = st.slider("障碍物高度 (米)", 5, 500, 50, key="obs_height",
                               help="飞行高度高于此障碍物时无需绕行")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ 添加障碍物", use_container_width=True):
                st.session_state.obstacles.append(
                    Obstacle(lng=obs_lng, lat=obs_lat, radius=obs_radius, height=obs_height))
                save_obstacles(st.session_state.obstacles)
                st.rerun()
        with c2:
            if st.button("🗑️ 清除全部", use_container_width=True):
                st.session_state.obstacles = []
                save_obstacles([])
                st.rerun()

    with col_obs_list:
        st.markdown("**已有障碍物列表**")
        if st.session_state.obstacles:
            for i, obs in enumerate(st.session_state.obstacles):
                cols = st.columns([3, 1])
                with cols[0]:
                    st.text(f"#{i+1}: ({obs.lat:.5f}, {obs.lng:.5f}) r={obs.radius:.0f}m h={obs.height:.0f}m")
                with cols[1]:
                    if st.button(f"✕", key=f"del_obs_{i}"):
                        st.session_state.obstacles.pop(i)
                        save_obstacles(st.session_state.obstacles)
                        st.rerun()
        else:
            st.info("暂无障碍物")

    # ---- Folium Map ----
    st.subheader("🗺️ 地图视图")
    st.info("💡 使用地图左侧工具栏绘制矩形或圆形框选障碍物，绘制完成后点击下方按钮确认添加")
    st.caption("高德地图瓦片 — 国内高速加载，无需 API Key")

    center_lat = (a_lat + b_lat) / 2
    center_lng = (a_lng + b_lng) / 2
    m = create_map(center_lat, center_lng, zoom=17, height=500)

    plugins.Fullscreen().add_to(m)
    add_context_menu(m)
    add_draw_plugin(m)

    # Point A — green marker
    folium.CircleMarker(
        location=[a_lat, a_lng], radius=14,
        color="#00ff00", fill=True, fill_color="#00ff00", fill_opacity=0.7,
        popup=folium.Popup(f"<b>坐标点 A</b><br>({a_lat:.6f}, {a_lng:.6f})", max_width=200),
    ).add_to(m)
    folium.Marker(
        location=[a_lat, a_lng],
        icon=folium.DivIcon(html='<div style="font-size:14px;font-weight:bold;color:#00ff00;'
                            'text-shadow:0 0 4px black;">A</div>'),
    ).add_to(m)

    # Point B — blue marker
    folium.CircleMarker(
        location=[b_lat, b_lng], radius=14,
        color="#0066ff", fill=True, fill_color="#0066ff", fill_opacity=0.7,
        popup=folium.Popup(f"<b>坐标点 B</b><br>({b_lat:.6f}, {b_lng:.6f})", max_width=200),
    ).add_to(m)
    folium.Marker(
        location=[b_lat, b_lng],
        icon=folium.DivIcon(html='<div style="font-size:14px;font-weight:bold;color:#0066ff;'
                            'text-shadow:0 0 4px black;">B</div>'),
    ).add_to(m)

    # Direct line A → B
    folium.PolyLine(
        locations=[[a_lat, a_lng], [b_lat, b_lng]],
        color="#ffcc00", weight=3, dash_array="8 4",
        popup="A→B 直线距离",
    ).add_to(m)

    # Obstacles
    for obs in st.session_state.obstacles:
        folium.Circle(
            location=[obs.lat, obs.lng], radius=obs.radius,
            color="#ff3333", weight=2, fill=True, fill_color="#ff3333", fill_opacity=0.3,
            popup=f"<b>障碍物</b><br>半径: {obs.radius:.0f}m<br>高度: {obs.height:.0f}m",
        ).add_to(m)
        folium.CircleMarker(
            location=[obs.lat, obs.lng], radius=4,
            color="#cc0000", fill=True, fill_color="#cc0000",
        ).add_to(m)

    # Planned route overlay
    if st.session_state.planned_route:
        route = st.session_state.planned_route
        route_coords = [[p.lat, p.lng] for p in route]
        folium.PolyLine(
            locations=route_coords, color="#00ff88", weight=5,
            popup="规划航线",
        ).add_to(m)
        # Waypoint dots (excluding first and last)
        for wp in route[1:-1]:
            folium.CircleMarker(
                location=[wp.lat, wp.lng], radius=5,
                color="#ffaa00", fill=True, fill_color="#ffaa00",
                popup=f"航点 ({wp.lat:.5f}, {wp.lng:.5f})",
            ).add_to(m)

    # Click-to-set-coordinate mode selector
    click_mode = st.radio(
        "🖱️ 左键点击设置坐标",
        ["关闭", "设为 A 点", "设为 B 点"],
        horizontal=True, key="click_mode_tab2",
    )

    map_data = st_folium(m, width=1200, height=500, key="map_tab2")

    # Handle left-click for setting coordinates
    if click_mode != "关闭" and map_data and map_data.get("last_clicked"):
        lc = map_data["last_clicked"]
        if lc and lc.get("lat") is not None:
            if click_mode == "设为 A 点":
                st.session_state.point_a = (lc["lat"], lc["lng"])
                st.success(f"A点已设为 ({lc['lat']:.6f}, {lc['lng']:.6f})")
                st.rerun()
            elif click_mode == "设为 B 点":
                st.session_state.point_b = (lc["lat"], lc["lng"])
                st.success(f"B点已设为 ({lc['lat']:.6f}, {lc['lng']:.6f})")
                st.rerun()

    # Confirm button for drawing obstacles
    if st.button("📐 确认框选障碍物", key="confirm_draw_tab2", use_container_width=True):
        if map_data and map_data.get("all_drawings"):
            new_obs = parse_drawings_to_obstacles(map_data["all_drawings"])
            if new_obs:
                st.session_state.obstacles.extend(new_obs)
                save_obstacles(st.session_state.obstacles)
                st.success(f"已从地图框选添加 {len(new_obs)} 个障碍物")
                st.rerun()
        else:
            st.info("未检测到框选形状，请先在地图上使用左侧工具栏绘制矩形或圆形")

    st.caption("🟢 A点 | 🔵 B点 | 🔴 障碍物(红圈) | 🟡 A-B虚线 | 🟢 规划航线(绿线) | 🟠 航点")

# ===================================================================
# Tab 3: Route Planning (Folium)
# ===================================================================
elif tab == "🛫 航线规划":
    st.title("🛫 航线规划与飞行参数")
    st.markdown("设置飞行参数并规划绕飞航线")

    col_params, col_preview = st.columns([1, 2])

    with col_params:
        st.subheader("飞行参数")

        flight_height = st.slider("飞行高度 (米)", 10, 500, st.session_state.flight_height, 5,
                                  key="fh")
        st.session_state.flight_height = flight_height

        safety_radius = st.slider("安全半径 (米)", 5, 200, st.session_state.safety_radius, 5,
                                  key="sr")
        st.session_state.safety_radius = safety_radius

        strategy_map = {"向左绕飞": "left", "向右绕飞": "right", "最优路径": "optimal"}
        strategy = st.radio("绕飞策略", ["向左绕飞", "向右绕飞", "最优路径"], key="strategy")
        st.session_state.route_strategy = strategy

        # Show obstacle height summary
        obs_list = st.session_state.obstacles
        if obs_list:
            blocking = [o for o in obs_list if o.height >= flight_height]
            clear = [o for o in obs_list if o.height < flight_height]
            st.caption(f"🚫 {len(blocking)} 个障碍物高于飞行高度(需绕行) | ✅ {len(clear)} 个低于飞行高度(可飞越)")

        st.divider()

        flight_speed = st.slider("飞行速度 (m/s)", 1, 30, 10, 1, key="fs")

        if st.button("🚀 规划航线", use_container_width=True, type="primary"):
            a = st.session_state.point_a
            b = st.session_state.point_b
            start = Point(lng=a[1], lat=a[0])
            end = Point(lng=b[1], lat=b[0])
            obs = st.session_state.obstacles
            strat = strategy_map[strategy]

            route = plan_route(start, end, obs, safety_radius, strat, flight_height)
            st.session_state.planned_route = route

            stats = calculate_route_stats(route, flight_speed)
            st.session_state.route_stats = stats

            st.session_state.topology.initialize_default(a[0], a[1])

            blocking = [o for o in obs if o.height >= flight_height]
            if blocking:
                st.success(f"航线规划完成! 共 {stats['num_waypoints']} 个航点, "
                           f"总距离: {stats['total_distance']:.1f}m, "
                           f"预计用时: {stats['eta_seconds']:.1f}s "
                           f"(绕开 {len(blocking)} 个阻挡障碍物)")
            else:
                st.success(f"航线规划完成! 无障碍物阻挡, 直线飞行 "
                           f"总距离: {stats['total_distance']:.1f}m, "
                           f"预计用时: {stats['eta_seconds']:.1f}s")
            st.rerun()

        if st.session_state.planned_route and "route_stats" in st.session_state:
            stats = st.session_state.route_stats
            st.subheader("航线统计")
            st.metric("航点数", stats["num_waypoints"])
            st.metric("总距离", f"{stats['total_distance']:.1f} m")
            st.metric("预计时间", f"{stats['eta_seconds']:.1f} s")

    with col_preview:
        st.subheader("航线预览")
        st.info("💡 使用地图左侧工具栏绘制矩形或圆形框选障碍物，绘制完成后点击下方按钮确认添加")

        a = st.session_state.point_a
        b = st.session_state.point_b

        center_lat = (a[0] + b[0]) / 2
        center_lng = (a[1] + b[1]) / 2
        m = create_map(center_lat, center_lng, zoom=17, height=550)

        plugins.Fullscreen().add_to(m)
        add_context_menu(m)
        add_draw_plugin(m)

        # A and B markers
        folium.CircleMarker(
            location=[a[0], a[1]], radius=14,
            color="#00cc00", fill=True, fill_color="#00cc00", fill_opacity=0.8,
            popup="<b>A点 (起点)</b>",
        ).add_to(m)
        folium.Marker(
            location=[a[0], a[1]],
            icon=folium.DivIcon(html='<div style="font-size:14px;font-weight:bold;color:#00cc00;'
                                'text-shadow:0 0 4px black;">A</div>'),
        ).add_to(m)

        folium.CircleMarker(
            location=[b[0], b[1]], radius=14,
            color="#0066ff", fill=True, fill_color="#0066ff", fill_opacity=0.8,
            popup="<b>B点 (终点)</b>",
        ).add_to(m)
        folium.Marker(
            location=[b[0], b[1]],
            icon=folium.DivIcon(html='<div style="font-size:14px;font-weight:bold;color:#0066ff;'
                                'text-shadow:0 0 4px black;">B</div>'),
        ).add_to(m)

        # Direct line
        folium.PolyLine(
            locations=[[a[0], a[1]], [b[0], b[1]]],
            color="#ffcc00", weight=2, dash_array="6 4",
        ).add_to(m)

        # Obstacles — color by whether they block at current flight height
        blocking_count = 0
        for obs in st.session_state.obstacles:
            is_blocking = obs.height >= flight_height
            if is_blocking:
                color = "#ff4444"
                blocking_count += 1
            else:
                color = "#ff8800"
            folium.Circle(
                location=[obs.lat, obs.lng], radius=obs.radius,
                color=color, weight=2, fill=True, fill_color=color, fill_opacity=0.25,
                popup=f"障碍物 r={obs.radius:.0f}m h={obs.height:.0f}m "
                      f"{'🚫阻挡' if is_blocking else '✅飞越'}",
            ).add_to(m)

        # Planned route
        if st.session_state.planned_route:
            route = st.session_state.planned_route
            route_coords = [[p.lat, p.lng] for p in route]
            folium.PolyLine(
                locations=route_coords, color="#00ff88", weight=6,
                popup="规划航线",
            ).add_to(m)
            for wp in route[1:-1]:
                folium.CircleMarker(
                    location=[wp.lat, wp.lng], radius=6,
                    color="#ff8800", fill=True, fill_color="#ff8800",
                    popup=f"航点 ({wp.lat:.5f}, {wp.lng:.5f})",
                ).add_to(m)

        click_mode_p = st.radio(
            "🖱️ 左键点击设置坐标",
            ["关闭", "设为 A 点", "设为 B 点"],
            horizontal=True, key="click_mode_tab3",
        )
        map_data_p = st_folium(m, width=800, height=550, key="map_tab3")

        if click_mode_p != "关闭" and map_data_p and map_data_p.get("last_clicked"):
            lc = map_data_p["last_clicked"]
            if lc and lc.get("lat") is not None:
                if click_mode_p == "设为 A 点":
                    st.session_state.point_a = (lc["lat"], lc["lng"])
                    st.success(f"A点已设为 ({lc['lat']:.6f}, {lc['lng']:.6f})")
                    st.rerun()
                elif click_mode_p == "设为 B 点":
                    st.session_state.point_b = (lc["lat"], lc["lng"])
                    st.success(f"B点已设为 ({lc['lat']:.6f}, {lc['lng']:.6f})")
                    st.rerun()

        # Confirm button for drawing obstacles
        if st.button("📐 确认框选障碍物", key="confirm_draw_tab3", use_container_width=True):
            if map_data_p and map_data_p.get("all_drawings"):
                new_obs = parse_drawings_to_obstacles(map_data_p["all_drawings"])
                if new_obs:
                    st.session_state.obstacles.extend(new_obs)
                    save_obstacles(st.session_state.obstacles)
                    st.success(f"已从地图框选添加 {len(new_obs)} 个障碍物")
                    st.rerun()
            else:
                st.info("未检测到框选形状，请先在地图上使用左侧工具栏绘制矩形或圆形")

        st.caption("🟢 起点A | 🔵 终点B | 🔴 障碍物 | 🟡 A-B直线 | 🟢 规划航线 | 🟠 航点")

# ===================================================================
# Tab 4: Flight Monitor (Folium)
# ===================================================================
elif tab == "📡 飞行监控":
    st.title("📡 飞行监控界面")
    st.markdown("实时动态监控无人机飞行状态")

    if st.session_state.planned_route is None:
        st.warning("⚠️ 请先在「航线规划」页面完成航线规划")
    else:
        flight = st.session_state.flight
        route = st.session_state.planned_route
        flight_speed = st.session_state.get("fs", 10)

        col_ctrl, col_status = st.columns([1, 3])

        with col_ctrl:
            st.subheader("飞行控制")

            if not flight.flying and not flight.completed:
                if st.button("▶️ 按航点起飞", use_container_width=True, type="primary"):
                    flight.start_flight(route, flight_speed)
                    st.session_state.flight_started = True
                    st.rerun()

            if flight.flying:
                if st.button("⏹️ 紧急停止", use_container_width=True):
                    flight.stop_flight()
                    st.rerun()

            if flight.completed:
                st.success("✅ 飞行完成!")
                if st.button("🔄 重新飞行", use_container_width=True):
                    flight.start_flight(route, flight_speed)
                    st.rerun()

            st.divider()
            st.metric("飞行高度", f"{st.session_state.flight_height} m")
            st.metric("安全半径", f"{st.session_state.safety_radius} m")
            st.metric("绕飞策略", st.session_state.route_strategy)

        with col_status:
            st.subheader("实时飞行数据")

            if flight.flying or flight.completed:
                if flight.flying:
                    time.sleep(0.3)
                    st.rerun()

                snap = flight.get_snapshot()

                m1, m2, m3, m4, m5 = st.columns(5)
                with m1:
                    wp_text = f"{snap['current_wp']}/{snap['total_wp']}"
                    st.metric("当前航点", wp_text)
                with m2:
                    st.metric("飞行速度", f"{snap['speed']:.1f} m/s")
                with m3:
                    mins, secs = divmod(snap["elapsed_time"], 60)
                    st.metric("已用时间", f"{int(mins)}分{secs:.0f}秒")
                with m4:
                    st.metric("剩余距离", f"{snap['remaining_distance']:.1f} m")
                with m5:
                    eta_m, eta_s = divmod(snap["eta_seconds"], 60)
                    st.metric("预计到达", f"{int(eta_m)}分{eta_s:.0f}秒")

                batt = snap["battery"]
                st.markdown(f"**🔋 模拟电量**")
                st.progress(batt / 100, text=f"{batt:.1f}%")

                if snap["total_distance"] > 0:
                    progress = 1 - (snap["remaining_distance"] / snap["total_distance"])
                    st.markdown("**📊 任务进度**")
                    st.progress(min(1.0, max(0.0, progress)),
                                text=f"{progress*100:.1f}%")

                st.subheader("实时位置")

                pos = snap["position"]
                center_lat = pos.lat if pos else route[0].lat
                center_lng = pos.lng if pos else route[0].lng

                m = create_map(center_lat, center_lng, zoom=17, height=450)

                plugins.Fullscreen().add_to(m)
                add_context_menu(m)

                # Route path (planned)
                route_coords = [[p.lat, p.lng] for p in route]
                folium.PolyLine(
                    locations=route_coords, color="#ffffff", weight=2, dash_array="6 6",
                    popup="规划航线",
                ).add_to(m)

                # Flight trail (actual path flown)
                trail = snap.get("trail", [])
                if trail and len(trail) >= 2:
                    trail_coords = [[p.lat, p.lng] for p in trail]
                    folium.PolyLine(
                        locations=trail_coords, color="#ff00ff", weight=4, opacity=0.9,
                        popup=f"飞行轨迹 ({len(trail)} 个记录点)",
                    ).add_to(m)

                # Waypoints
                for i, wp in enumerate(route):
                    if i == 0:
                        color = "#00cc00"
                        label = "A (起点)"
                    elif i == len(route) - 1:
                        color = "#0066ff"
                        label = "B (终点)"
                    else:
                        color = "#ffaa00"
                        label = f"航点 {i}"
                    folium.CircleMarker(
                        location=[wp.lat, wp.lng], radius=6,
                        color=color, fill=True, fill_color=color,
                        popup=label,
                    ).add_to(m)

                # Current drone position
                if pos:
                    folium.CircleMarker(
                        location=[pos.lat, pos.lng], radius=16,
                        color="#00ffff", fill=True, fill_color="#00ffff", fill_opacity=0.9,
                        popup=f"<b>🛸 无人机</b><br>电量: {batt:.1f}%<br>"
                              f"速度: {snap['speed']:.1f} m/s",
                    ).add_to(m)
                    # Pulsing effect with larger outer circle
                    folium.Circle(
                        location=[pos.lat, pos.lng], radius=10,
                        color="#00ffff", weight=1, fill=True, fill_color="#00ffff", fill_opacity=0.2,
                    ).add_to(m)

                st_folium(m, width=800, height=450, returned_objects=[])

                trail = snap.get("trail", [])
                if trail:
                    st.caption(f"🟣 紫色实线 = 飞行轨迹 ({len(trail)} 点) | ⬜ 白色虚线 = 规划航线 | 🔵 青色 = 当前飞机位置")
                else:
                    st.caption("⬜ 白色虚线 = 规划航线 | 🔵 青色 = 当前飞机位置")

                if pos:
                    st.session_state.topology.update_drone_position(pos.lat, pos.lng)

            else:
                st.info("点击「按航点起飞」开始飞行模拟")

# ===================================================================
# Tab 5: Communication Topology
# ===================================================================
elif tab == "🔗 通信拓扑":
    st.title("🔗 通信拓扑结构")
    st.markdown("无人机通信网络节点连接状态与信号强度")

    topo = st.session_state.topology

    if not topo.nodes:
        a = st.session_state.point_a
        topo.initialize_default(a[0], a[1])

    col_graph, col_info = st.columns([2, 1])

    with col_graph:
        st.subheader("网络拓扑图")

        if topo.nodes:
            map_center_lat = (st.session_state.point_a[0] + st.session_state.point_b[0]) / 2
            map_center_lon = (st.session_state.point_a[1] + st.session_state.point_b[1]) / 2

            tm = create_map(map_center_lat, map_center_lon, zoom=17, height=500)
            add_context_menu(tm)

            # Edges between nodes
            for link in topo.links:
                src = next(n for n in topo.nodes if n.id == link.source)
                tgt = next(n for n in topo.nodes if n.id == link.target)
                edge_color = "#00ff96" if link.signal_quality > 50 else "#ff9600"
                edge_weight = max(1, link.signal_quality / 25)
                folium.PolyLine(
                    locations=[[src.lat, src.lng], [tgt.lat, tgt.lng]],
                    color=edge_color, weight=edge_weight, opacity=0.8,
                    popup=f"{link.source} → {link.target}<br>"
                          f"信号质量: {link.signal_quality:.0f}%<br>"
                          f"延迟: {link.latency_ms:.1f}ms",
                ).add_to(tm)

            # Node markers
            for node in topo.nodes:
                if node.node_type == "ground":
                    icon_html = '<div style="font-size:18px;">🖥️</div>'
                    radius = 16
                    color = "#00ff88"
                elif node.node_type == "drone":
                    icon_html = '<div style="font-size:18px;">🛸</div>'
                    radius = 14
                    color = "#00aaff" if node.connected else "#ff4444"
                else:
                    icon_html = '<div style="font-size:16px;">📡</div>'
                    radius = 12
                    color = "#ffaa00"

                signal_pct = max(0, (node.signal_strength + 90) / 60 * 100)

                folium.CircleMarker(
                    location=[node.lat, node.lng], radius=radius,
                    color=color, fill=True, fill_color=color, fill_opacity=0.7,
                    popup=folium.Popup(
                        f"<b>{node.name}</b><br>"
                        f"信号: {node.signal_strength:.0f} dBm<br>"
                        f"质量: {signal_pct:.0f}%<br>"
                        f"状态: {'✅ 连接' if node.connected else '❌ 断开'}",
                        max_width=200,
                    ),
                ).add_to(tm)
                folium.Marker(
                    location=[node.lat, node.lng],
                    icon=folium.DivIcon(html=icon_html),
                ).add_to(tm)

            # ---- Flight route & trail overlay ----
            route = st.session_state.planned_route
            flight = st.session_state.flight

            if route:
                route_coords = [[p.lat, p.lng] for p in route]

                if flight.flying or flight.completed:
                    snap = flight.get_snapshot()
                    trail = snap.get("trail", [])
                    pos = snap.get("position")

                    # Flown trail — purple solid
                    if trail and len(trail) >= 2:
                        trail_coords = [[p.lat, p.lng] for p in trail]
                        folium.PolyLine(
                            locations=trail_coords, color="#ff00ff", weight=4, opacity=0.9,
                            popup=f"已飞行轨迹 ({len(trail)} 点)",
                        ).add_to(tm)

                    # Remaining route — from current position to end
                    if pos and snap["current_wp"] < len(route):
                        remaining_coords = [[pos.lat, pos.lng]]
                        for i in range(snap["current_wp"] + 1, len(route)):
                            remaining_coords.append([route[i].lat, route[i].lng])
                        if len(remaining_coords) >= 2:
                            folium.PolyLine(
                                locations=remaining_coords, color="#ff8800", weight=3,
                                dash_array="6 4", opacity=0.8,
                                popup=f"剩余航线 ({snap['remaining_distance']:.0f}m)",
                            ).add_to(tm)

                    # Current drone position
                    if pos:
                        folium.CircleMarker(
                            location=[pos.lat, pos.lng], radius=12,
                            color="#00ffff", fill=True, fill_color="#00ffff", fill_opacity=0.9,
                            popup=f"<b>🛸 无人机</b><br>电量: {snap['battery']:.1f}%",
                        ).add_to(tm)
                else:
                    # Not flying — show full planned route
                    folium.PolyLine(
                        locations=route_coords, color="#ffcc00", weight=3, dash_array="6 4",
                        popup="规划航线",
                    ).add_to(tm)

            st_folium(tm, width=800, height=500, returned_objects=[])

            # Caption with legend
            flight = st.session_state.flight
            if flight.flying or flight.completed:
                st.caption("🟣 紫色实线 = 已飞行轨迹 | 🟠 橙色虚线 = 剩余航线 | 🔵 青色 = 飞机位置")
            elif st.session_state.planned_route:
                st.caption("🟡 黄色虚线 = 规划航线 | 请在「飞行监控」中启动飞行")

            # Auto-refresh while flying
            if flight.flying:
                time.sleep(0.5)
                st.rerun()

    with col_info:
        st.subheader("节点状态")

        for node in topo.nodes:
            icon = "🖥️" if node.node_type == "ground" else "🛸" if node.node_type == "drone" else "📡"
            status = "🟢" if node.connected else "🔴"
            st.markdown(f"**{icon} {node.name}** {status}")
            signal_pct = max(0, (node.signal_strength + 90) / 60 * 100)
            st.progress(signal_pct / 100, text=f"信号: {node.signal_strength:.0f} dBm")

        st.divider()
        st.subheader("链路信息")
        if topo.links:
            for link in topo.links[:6]:
                qi = "🟢" if link.signal_quality > 70 else "🟡" if link.signal_quality > 30 else "🔴"
                st.text(f"{qi} {link.source}→{link.target}")
                st.text(f"  质量:{link.signal_quality:.0f}% 延迟:{link.latency_ms:.1f}ms")

        st.divider()
        st.subheader("拓扑图例")
        st.markdown("🖥️ 地面站 — 控制中心")
        st.markdown("🛸 无人机 — 移动节点")
        st.markdown("📡 中继节点 — 信号转发")
        st.markdown("🟢 连接正常 | 🔴 连接断开")
        st.divider()
        st.subheader("航线图例")
        st.markdown("🟡 黄色虚线 — 规划航线")
        st.markdown("🟣 紫色实线 — 已飞行轨迹")
        st.markdown("🟠 橙色虚线 — 剩余航线")
        st.markdown("🔵 青色圆点 — 飞机当前位置")

        if st.button("🔄 刷新拓扑", use_container_width=True):
            a = st.session_state.point_a
            topo.initialize_default(a[0], a[1])
            if st.session_state.flight.flying:
                snap = st.session_state.flight.get_snapshot()
                if snap["position"]:
                    topo.update_drone_position(snap["position"].lat, snap["position"].lng)
            st.rerun()

# ---- Footer ----
st.sidebar.divider()
st.sidebar.caption("南京科技职业学院")
st.sidebar.caption("无人机通信与飞行监控系统 v1.0")
