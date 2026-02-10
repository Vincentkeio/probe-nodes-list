import requests
from bs4 import BeautifulSoup
import json
import re
import sys # 引入 sys 模块用于控制退出状态

def fetch_wuxie_nodes():
    url = "https://tcping.wuxie.de/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        
        # 如果状态码不是 200 (例如 404, 500)，直接抛出异常
        response.raise_for_status() 
        
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        nodes = []
        known_provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门", "台湾"]

        tables = soup.find_all('table')

        for table in tables:
            # --- 1. 省份回溯 ---
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

            # --- 2. 列映射 ---
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

            # --- 3. 数据提取 ---
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

    except Exception as e:
        print(f"Error fetching data: {e}")
        return [] # 返回空列表

if __name__ == "__main__":
    print("开始抓取...")
    data = fetch_wuxie_nodes()
    
    # === 安全检查 ===
    # 设定一个最小阈值，比如 10 个节点。
    # 如果抓取到的节点少于 10 个，说明网站可能挂了，或者改版了导致解析失败。
    MIN_NODES_THRESHOLD = 10 
    
    if data and len(data) >= MIN_NODES_THRESHOLD:
        print(f"数据校验通过！抓取到 {len(data)} 个节点。正在写入文件...")
        with open('nodes.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("更新成功。")
    else:
        # === 熔断触发 ===
        print("【严重警告】抓取失败或数据异常！")
        print(f"原因：抓取到的节点数量 ({len(data)}) 少于安全阈值 ({MIN_NODES_THRESHOLD})。")
        print("为了防止覆盖有效数据，本次操作已终止，原 nodes.json 未被修改。")
        
        # 抛出非 0 退出码，告诉 GitHub Action 这一步出错了
        sys.exit(1)
