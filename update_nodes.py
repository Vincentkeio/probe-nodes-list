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
        
        # 预定义省份列表，用于从标题中提取
        known_provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门", "台湾"]

        # 1. 查找页面上所有的表格
        tables = soup.find_all('table')

        for table in tables:
            # --- A. 确定该表格所属的省份 ---
            # 逻辑：从当前表格开始，向前找（previous_elements），直到找到一个包含省份名的标题
            current_province = "未知"
            
            # 限制回溯步数，防止找错到上一个大区块
            prev_generator = table.previous_elements
            step_limit = 50 
            steps = 0
            
            for elem in prev_generator:
                if steps > step_limit: break
                steps += 1
                
                # 跳过空文本
                if not elem.name: continue 
                
                text = elem.get_text(strip=True)
                # 检查是否包含省份名
                found_prov = False
                for p in known_provinces:
                    if p in text:
                        current_province = p
                        found_prov = True
                        break
                if found_prov:
                    break
            
            # 如果找不到省份，可能是页面结构特殊，暂时跳过或标记未知
            if current_province == "未知":
                continue

            # --- B. 解析表格结构 (列映射) ---
            # 我们需要知道哪一列是移动，哪一列是电信
            # 格式通常是：[空] | 移动 | 联通 | 电信
            rows = table.find_all('tr')
            if not rows: continue

            col_map = {} # { index: 'ISP_CODE' }
            
            # 遍历所有行寻找表头和数据
            for row in rows:
                cols = row.find_all(['td', 'th'])
                col_texts = [c.get_text(strip=True) for c in cols]
                
                # 1. 识别表头行 (包含 ISP 关键字)
                if any(k in "".join(col_texts) for k in ["移动", "联通", "电信"]):
                    for idx, text in enumerate(col_texts):
                        if "移动" in text or "CM" in text.upper():
                            col_map[idx] = "CM" # China Mobile
                        elif "联通" in text or "CU" in text.upper():
                            col_map[idx] = "CU" # China Unicom
                        elif "电信" in text or "CT" in text.upper():
                            col_map[idx] = "CT" # China Telecom
                    continue # 处理完表头，继续下一行

                # 2. 识别数据行 (通常以 'IP' 开头，或者包含 IP 地址)
                # 检查这一行是否有 IP 地址
                row_str = "".join(col_texts)
                # 简单的 IP 正则
                if not re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', row_str):
                    continue
                
                # 这是一个数据行，开始提取
                for idx, cell_text in enumerate(col_texts):
                    # 如果这一列的索引在我们的映射表中 (即这一列是 ISP 列)
                    if idx in col_map:
                        isp_code = col_map[idx]
                        
                        # 提取该单元格内的 IP
                        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', cell_text)
                        if ip_match:
                            ip = ip_match.group(1)
                            
                            # 过滤无效 IP
                            if ip.startswith("127.") or ip.startswith("192.168") or ip == "0.0.0.0":
                                continue

                            # 转换 ISP 代码为中文 (如果需要)
                            isp_name_map = {"CT": "电信", "CU": "联通", "CM": "移动"}
                            
                            # 组装最终数据
                            node_entry = {
                                "province": current_province,
                                "isp": isp_name_map.get(isp_code, "未知"),
                                "ip": ip
                            }
                            
                            # 查重
                            if not any(n['ip'] == ip for n in nodes):
                                nodes.append(node_entry)

        return nodes

    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

if __name__ == "__main__":
    print("正在根据表格结构精确抓取 tcping.wuxie.de ...")
    data = fetch_wuxie_nodes()
    
    if data:
        print(f"抓取成功，共找到 {len(data)} 个节点。")
        # 打印前 3 个看看效果
        print("Preview:", json.dumps(data[:3], ensure_ascii=False, indent=2))
        
        with open('nodes.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    else:
        print("未找到数据。")
