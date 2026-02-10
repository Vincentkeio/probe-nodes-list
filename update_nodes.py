import requests
from bs4 import BeautifulSoup
import json
import re
import sys
import os
from datetime import datetime

# === 配置区 ===
URL = "https://tcping.wuxie.de/"
JSON_FILE = "nodes.json"
MIN_NODES_THRESHOLD = 10 

def parse_web_time(time_str):
    """
    专门解析网页上的中文时间格式
    输入: 2026年02月09日 18:32:44
    输出: datetime 对象
    """
    try:
        return datetime.strptime(time_str, "%Y年%m月%d日 %H:%M:%S")
    except ValueError:
        return None

def parse_standard_time(time_str):
    """
    专门解析本地 JSON 里的标准时间格式
    输入: 2026-02-09 18:32:44
    输出: datetime 对象
    """
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def get_web_time_str(soup):
    """从网页 HTML 中提取原始中文时间字符串"""
    text = soup.get_text()
    match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日\s\d{1,2}:\d{1,2}:\d{1,2})", text)
    if match:
        return match.group(1)
    return None

def get_local_time_str():
    """读取本地 JSON 里的 updated_at"""
    if not os.path.exists(JSON_FILE):
        return None
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list): return None
            return data.get('updated_at')
    except:
        return None

def fetch_nodes_logic(soup):
    """核心抓取逻辑 (保持不变)"""
    nodes = []
    known_provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门", "台湾"]
    tables = soup.find_all('table')

    for table in tables:
        current_province = "未知"
        prev_generator = table.previous_elements
        steps = 0
        for elem in prev_generator:
            if steps > 100: break 
            steps += 1
            if not elem.name: continue 
            text = elem.get_text(strip=True)
            found = False
            for p in known_provinces:
                if p in text:
                    current_province = p
                    found = True
                    break
            if found: break
        
        if current_province == "未知": continue

        rows = table.find_all('tr')
        col_map = {} 
        for row in rows:
            cols = row.find_all(['td', 'th'])
            col_texts = [c.get_text(strip=True) for c in cols]
            full_row_text = "".join(col_texts)
            if any(k in full_row_text for k in ["移动", "联通", "电信"]):
                for idx, text in enumerate(col_texts):
                    if "移动" in text or "CM" in text.upper(): col_map[idx] = "CM"
                    elif "联通" in text or "CU" in text.upper(): col_map[idx] = "CU"
                    elif "电信" in text or "CT" in text.upper(): col_map[idx] = "CT"
                break 

        for row in rows:
            cols = row.find_all(['td', 'th'])
            col_texts = [c.get_text(strip=True) for c in cols]
            
            for idx, cell_text in enumerate(col_texts):
                if idx in col_map:
                    isp_code = col_map[idx]
                    v4_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', cell_text)
                    v6_match = re.search(r'([a-fA-F0-9]{1,4}:[:a-fA-F0-9]+)', cell_text)
                    ip = None
                    ip_type = None
                    if v4_match:
                        ip = v4_match.group(1)
                        ip_type = "IPv4"
                        if ip.startswith("127.") or ip.startswith("192.168"): continue
                    elif v6_match and ":" in cell_text:
                        candidate = v6_match.group(1)
                        if candidate.count(':') >= 2:
                            ip = candidate
                            ip_type = "IPv6"
                    if ip:
                        isp_name_map = {"CT": "电信", "CU": "联通", "CM": "移动"}
                        node_entry = {
                            "province": current_province,
                            "isp": isp_name_map.get(isp_code, "未知"),
                            "ip": ip,
                            "type": ip_type
                        }
                        if not any(n['ip'] == ip for n in nodes):
                            nodes.append(node_entry)
    return nodes

def main():
    print(">>> 启动标准时间版更新程序...")
    
    # 1. 获取网页
    try:
        headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36" }
        response = requests.get(URL, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"❌ 网络请求失败: {e}")
        sys.exit(1)

    # 2. 提取网页时间 (中文格式)
    web_time_raw = get_web_time_str(soup)
    web_dt = parse_web_time(web_time_raw) if web_time_raw else None
    
    if not web_dt:
        print("⚠️  警告：无法解析网页时间。停止更新。")
        sys.exit(0)

    # 3. 读取本地时间 (可能是中文，也可能是标准格式，需兼容)
    local_time_raw = get_local_time_str()
    local_dt = None
    if local_time_raw:
        # 先尝试按标准格式解析
        local_dt = parse_standard_time(local_time_raw)
        # 如果失败（说明是旧版json），尝试按中文格式解析
        if not local_dt:
            local_dt = parse_web_time(local_time_raw)

    print(f"   网页时间: {web_dt}")
    print(f"   本地时间: {local_dt if local_dt else '无'}")

    # 4. 比对逻辑
    should_update = False
    if not local_dt:
        should_update = True
    elif web_dt > local_dt:
        should_update = True
    elif web_dt == local_dt:
        print("💤 时间一致，跳过。")
    else:
        print("⚠️  网页时间滞后，跳过。")

    # 5. 执行更新
    if should_update:
        nodes = fetch_nodes_logic(soup)
        if len(nodes) >= MIN_NODES_THRESHOLD:
            # === 关键修改：转换成标准格式字符串 ===
            standard_time_str = web_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            final_data = {
                "updated_at": standard_time_str, # 例如: 2026-02-09 18:32:44
                "nodes": nodes
            }
            
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            print(f"🎉 成功！已更新。时间戳: {standard_time_str}")
        else:
            print("❌ 节点数不足，放弃更新。")
            sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
