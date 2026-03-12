# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

# 设置页面标题和布局
st.set_page_config(page_title='我的数据看板', layout='wide')
st.title("📊 我的第一个数据可视化看板")

# 1. 加载数据 (这里用的是示例数据，你可以替换成自己的)
# 如果你想上传自己的CSV文件，可以取消下面两行的注释
# uploaded_file = st.file_uploader("上传你的CSV文件", type=["csv"])
# if uploaded_file is not None:
#     df = pd.read_csv(uploaded_file)

# 为了演示，我们创建一些示例数据
@st.cache_data
def load_data():
    return pd.DataFrame({
        '日期': pd.date_range('2024-01-01', periods=100),
        '销量': np.random.randint(100, 500, size=100),
        '类别': np.random.choice(['产品A', '产品B', '产品C'], size=100),
        '金额': np.random.randint(1000, 10000, size=100)
    })

# 尝试导入numpy，如果没安装会报错，但没关系，这只是示例
import numpy as np
df = load_data()

# 2. 侧边栏筛选器 (让看板交互起来)
st.sidebar.header("请筛选数据")
categories = st.sidebar.multiselect(
    "选择产品类别:",
    options=df['类别'].unique(),
    default=df['类别'].unique()
)

# 根据筛选条件过滤数据
filtered_df = df[df['类别'].isin(categories)]

# 3. 展示核心指标
col1, col2, col3 = st.columns(3)
col1.metric("总销量", filtered_df['销量'].sum())
col2.metric("总金额", f"¥ {filtered_df['金额'].sum():,}")
col3.metric("数据条数", len(filtered_df))

# 4. 展示图表 (使用Plotly)
col1, col2 = st.columns(2)

with col1:
    # 销量趋势图
    fig_line = px.line(filtered_df, x='日期', y='销量', color='类别', 
                       title='销量趋势图')
    st.plotly_chart(fig_line, use_container_width=True)

with col2:
    # 类别销量占比
    fig_pie = px.pie(filtered_df, values='销量', names='类别', 
                     title='各类别销量占比')
    st.plotly_chart(fig_pie, use_container_width=True)

# 5. 展示原始数据
st.subheader("筛选后的数据预览")
st.dataframe(filtered_df)
