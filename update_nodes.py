import requests
from bs4 import BeautifulSoup
import json
import re

def fetch_wuxie_nodes():
    url = "https://tcping.wuxie.de/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        nodes = []
        
        # 预定义省份列表
        known_provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门", "台湾"]

        # 查找页面上所有的表格
        tables = soup.find_all('table')

        for table in tables:
            # --- 1. 确定省份 (向上回溯) ---
            current_province = "未知"
            # 限制回溯步数
            prev_generator = table.previous_elements
            steps = 0
            for elem in prev_generator:
                if steps > 100: break #稍微增加回溯深度以防IPv6表格离标题太远
                steps += 1
                if not elem.name: continue 
                text = elem.get_text(strip=True)
                
                # 找到省份就停止
                found = False
                for p in known_provinces:
                    if p in text:
                        current_province = p
                        found = True
                        break
                if found: break
            
            if current_province == "未知": continue

            # --- 2. 确定列映射 (ISP Map) ---
            rows = table.find_all('tr')
            col_map = {} # { index: 'ISP_CODE' }
            
            # 先扫描表头行
            for row in rows:
                cols = row.find_all(['td', 'th'])
                col_texts = [c.get_text(strip=True) for c in cols]
                full_row_text = "".join(col_texts)
                
                if any(k in full_row_text for k in ["移动", "联通", "电信"]):
                    for idx, text in enumerate(col_texts):
                        if "移动" in text or "CM" in text.upper():
                            col_map[idx] = "CM"
                        elif "联通" in text or "CU" in text.upper():
                            col_map[idx] = "CU"
                        elif "电信" in text or "CT" in text.upper():
                            col_map[idx] = "CT"
                    break # 找到表头后停止扫描表头

            # --- 3. 提取数据 (IPv4 和 IPv6) ---
            for row in rows:
                cols = row.find_all(['td', 'th'])
                col_texts = [c.get_text(strip=True) for c in cols]
                
                for idx, cell_text in enumerate(col_texts):
                    # 只处理即使 ISP 列
                    if idx in col_map:
                        isp_code = col_map[idx]
                        
                        # A. 尝试匹配 IPv4
                        # 正则：数字.数字.数字.数字
                        v4_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', cell_text)
                        
                        # B. 尝试匹配 IPv6
                        # 正则：包含冒号的十六进制串 (简化版，防止误伤时间等，需配合长度判断)
                        # 这是一个比较通用的抓取 IPv6 的正则
                        v6_match = re.search(r'([a-fA-F0-9]{1,4}:[:a-fA-F0-9]+)', cell_text)
                        
                        ip = None
                        ip_type = None

                        if v4_match:
                            ip = v4_match.group(1)
                            ip_type = "IPv4"
                            # 过滤内网 IP
                            if ip.startswith("127.") or ip.startswith("192.168"): continue

                        elif v6_match and ":" in cell_text:
                            # 二次确认 IPv6 格式 (至少有2个冒号)
                            candidate = v6_match.group(1)
                            if candidate.count(':') >= 2:
                                ip = candidate
                                ip_type = "IPv6"

                        # 如果提取到了 IP，保存
                        if ip:
                            isp_name_map = {"CT": "电信", "CU": "联通", "CM": "移动"}
                            
                            node_entry = {
                                "province": current_province,
                                "isp": isp_name_map.get(isp_code, "未知"),
                                "ip": ip,
                                "type": ip_type
                            }
                            
                            # 查重 (避免重复添加)
                            if not any(n['ip'] == ip for n in nodes):
                                nodes.append(node_entry)

        return nodes

    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

if __name__ == "__main__":
    print("正在全量抓取 (IPv4 + IPv6) ...")
    data = fetch_wuxie_nodes()
    
    if data:
        print(f"抓取成功！共找到 {len(data)} 个节点。")
        # 统计一下 IPv4 和 IPv6 的数量
        v4_count = sum(1 for x in data if x['type'] == 'IPv4')
        v6_count = sum(1 for x in data if x['type'] == 'IPv6')
        print(f"IPv4: {v4_count} 个, IPv6: {v6_count} 个")
        
        # 打印示例
        print("示例数据:", json.dumps(data[:3], ensure_ascii=False, indent=2))
        
        with open('nodes.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    else:
        print("未找到数据。")
