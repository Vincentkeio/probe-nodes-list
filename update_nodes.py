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
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        nodes = []
        
        # 预定义省份列表用于匹配标题
        provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆", "内蒙"]

        # 查找所有可能的卡片容器 (根据Bootstrap常见结构)
        # 你的描述：容器标题是省份。
        # 我们遍历所有 div，寻找包含省份名称的 header
        cards = soup.find_all('div', class_=re.compile(r'card|panel|col', re.I))
        
        # 如果通过 class 找不到，就遍历所有 div (兜底)
        if len(cards) < 5:
            cards = soup.find_all('div')

        for card in cards:
            text_content = card.get_text(separator="\n", strip=True)
            lines = text_content.split('\n')
            
            # --- 步骤1：确定当前卡片的省份 ---
            current_province = None
            
            # 扫描前几行寻找省份
            header_text = "".join(lines[:3]) 
            for p in provinces:
                if p in header_text:
                    current_province = p
                    break
            
            # 修正：内蒙 -> 内蒙古
            if current_province == "内蒙": current_province = "内蒙古"

            # 如果这个 div 不包含省份信息，跳过
            if not current_province:
                continue

            # --- 步骤2：在卡片内扫描 ISP 和 IP ---
            current_isp = "未知" # 默认 ISP
            
            for line in lines:
                line = line.strip()
                if not line: continue

                # A. 检测运营商关键词 (切换状态)
                if "电信" in line or "CT" in line.upper():
                    current_isp = "电信"
                    continue # 这一行是标题，跳过
                elif "联通" in line or "CU" in line.upper():
                    current_isp = "联通"
                    continue
                elif "移动" in line or "CM" in line.upper():
                    current_isp = "移动"
                    continue
                
                # B. 检测 IP 地址
                # 使用正则提取 IP
                ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                if ip_match:
                    ip = ip_match.group(1)
                    
                    # 过滤内网/无效 IP
                    if ip.startswith("127.") or ip.startswith("192.168") or ip == "0.0.0.0":
                        continue
                    
                    # 只有当运营商已知时才保存（或者你可以允许未知）
                    if current_isp != "未知":
                        node_entry = {
                            "province": current_province,
                            "isp": current_isp,
                            "ip": ip
                        }
                        
                        # 简单的查重 (根据 IP)
                        if not any(n['ip'] == ip for n in nodes):
                            nodes.append(node_entry)

        return nodes

    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

if __name__ == "__main__":
    print("正在抓取并解析数据...")
    data = fetch_wuxie_nodes()
    
    if data:
        print(f"抓取成功，共找到 {len(data)} 个节点。")
        # 打印前2个看看格式对不对
        print("示例数据:", json.dumps(data[:2], ensure_ascii=False))
        
        with open('nodes.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    else:
        print("未找到数据，可能网页结构不匹配。")
