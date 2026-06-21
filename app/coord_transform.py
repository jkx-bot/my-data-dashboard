# coord_transform.py
# WGS-84 与 GCJ-02 坐标系转换
# 中国地图法规要求使用GCJ-02加密坐标系

import math

pi = 3.1415926535897932384626
a = 6378245.0  # 长半轴
ee = 0.00669342162296594323  # 偏心率平方

def out_of_china(lat, lon):
    """判断是否在中国境外，境外不需要转换"""
    if lon < 72.004 or lon > 137.8347:
        return True
    if lat < 0.8293 or lat > 55.8271:
        return True
    return False

def transform_lat(x, y):
    """纬度转换辅助函数"""
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * pi) + 20.0 * math.sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * pi) + 40.0 * math.sin(y / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * pi) + 320 * math.sin(y * pi / 30.0)) * 2.0 / 3.0
    return ret

def transform_lon(x, y):
    """经度转换辅助函数"""
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * pi) + 20.0 * math.sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * pi) + 40.0 * math.sin(x / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * pi) + 300.0 * math.sin(x / 30.0 * pi)) * 2.0 / 3.0
    return ret

def wgs84_to_gcj02(lat, lon):
    """
    WGS-84坐标系转GCJ-02坐标系
    参数: lat - 纬度, lon - 经度
    返回: (gcj_lat, gcj_lon)
    """
    if out_of_china(lat, lon):
        return lat, lon
    
    dlat = transform_lat(lon - 105.0, lat - 35.0)
    dlon = transform_lon(lon - 105.0, lat - 35.0)
    
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    
    gcj_lat = lat + dlat
    gcj_lon = lon + dlon
    return gcj_lat, gcj_lon

def gcj02_to_wgs84(lat, lon):
    """GCJ-02坐标系转WGS-84坐标系（近似）"""
    if out_of_china(lat, lon):
        return lat, lon
    
    dlat = transform_lat(lon - 105.0, lat - 35.0)
    dlon = transform_lon(lon - 105.0, lat - 35.0)
    
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    
    wgs_lat = lat - dlat
    wgs_lon = lon - dlon
    return wgs_lat, wgs_lon

# 南京科技职业学院坐标（约北纬32.14°，东经118.78°）
SCHOOL_LAT = 32.14
SCHOOL_LON = 118.78