import requests
from bs4 import BeautifulSoup
import json
import re

def fetch_wuxie_nodes():
    url = "https://tcping.wuxie.de/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8' # 确保中文不乱码
        soup = BeautifulSoup(response.text, 'html.parser')
        
        nodes = []
        
        # 假设该网站是一个表格结构，我们需要找到所有的 tr
        # 注意：实际 HTML 结构可能需要根据网页微调，这里是通用表格提取逻辑
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all(['td', 'th'])
            # 过滤掉表头或无效行，假设每一行至少有3列信息：地区、运营商、IP
            if len(cols) < 3:
                continue
                
            text_content = [c.get_text(strip=True) for c in cols]
            raw_line = " ".join(text_content)

            # 提取 IP 地址的正则
            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', raw_line)
            if not ip_match:
                continue
            
            ip = ip_match.group(1)
            
            # 简单的关键词判断运营商
            isp = "other"
            if "电信" in raw_line or "CT" in raw_line:
                isp = "CT"
            elif "联通" in raw_line or "CU" in raw_line:
                isp = "CU"
            elif "移动" in raw_line or "CM" in raw_line:
                isp = "CM"
            
            # 提取地区名称（去掉IP和常见无用字符）
            name = raw_line.replace(ip, "").strip()
            
            node_data = {
                "name": name, # 例如：江苏镇江电信
                "isp": isp,   # CT/CU/CM
                "ip": ip      # 221.x.x.x
            }
            
            # 过滤重复 IP
            if not any(d['ip'] == ip for d in nodes):
                nodes.append(node_data)

        return nodes

    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

if __name__ == "__main__":
    print("正在抓取 tcping.wuxie.de ...")
    data = fetch_wuxie_nodes()
    
    if data:
        # 写入 JSON 文件
        with open('nodes.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"成功！已抓取 {len(data)} 个节点，保存为 nodes.json")
    else:
        print("抓取失败或未找到数据。")
