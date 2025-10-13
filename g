import requests
import base64
import re
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 配置区 ---
TEMPLATE_FILE = "vless_template.txt"   # VLESS 模板文件路径
DOMAINS_FILE = "domains.txt"           # 本地优选域名文件路径
OUTPUT_FILE = "sub.txt"                # 生成的订阅文件名
FIXED_SNI_HOST = "bui.2514376.xyz"     # 固定的 SNI 和 HOST 值

REMOTE_IP_URL_1 = "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_IPs_port_443.txt"
DYNAMIC_IP_URL = "https://stock.hostmonit.com/CloudFlareYes"
GITHUB_IP_URL = "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"
# --- 配置区结束 ---

def fetch_from_file(file_path):
    """从本地文件读取地址列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"✅ 从本地文件 {file_path} 获取 {len(lines)} 个域名。")
            return [{"address": line, "name_suffix": line} for line in lines]
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {file_path}")
        return []

def fetch_simple_ips(url):
    """从URL获取简单的IP列表"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip() and not line.strip().startswith('#')]
        print(f"✅ 从 {url} 获取 {len(lines)} 个IP。")
        return [{"address": line, "name_suffix": line} for line in lines]
    except requests.RequestException as e:
        print(f"❌ 获取 {url} 失败: {e}")
        return []

def fetch_dynamic_ips(url):
    """从 hostmonit 解析动态IP地址和ISP信息"""
    print("🔄 正在从 hostmonit 获取动态IP...")
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        results = []
        for row in soup.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) >= 5:
                ip = cols[0].text.strip()
                isp = cols[4].text.strip().replace(' ', '')
                if ip and isp:
                    results.append({"address": ip, "name_suffix": isp})
        
        print(f"✅ 成功从 hostmonit 获取 {len(results)} 个动态IP。")
        return results
    except Exception as e:
        print(f"❌ hostmonit: 获取或解析失败: {e}")
        return []

def fetch_github_ips(url):
    """从 GitHub 解析带端口和名称的IP"""
    print("🔄 正在从 GitHub 获取优选IP...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        results = []
        regex = r'^([^:]+):(\d+)#(.*)$'
        for line in response.text.strip().split('\n'):
            match = re.match(regex, line.strip())
            if match:
                ip, port, name = match.groups()
                address = f"{ip}:{port}"
                name_suffix = name.strip() or ip
                results.append({"address": address, "name_suffix": name_suffix})
        
        print(f"✅ 成功从 GitHub 获取 {len(results)} 个优选IP。")
        return results
    except requests.RequestException as e:
        print(f"❌ GitHub: 获取优选IP失败: {e}")
        return []

def generate_subscription():
    """生成订阅文件"""
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            vless_template = f.read().strip()
            
            uuid_match = re.search(r'vless://([^@]+)@', vless_template)
            uuid = uuid_match.group(1) if uuid_match else ""
            
            params_match = re.search(r'\?(.+)', vless_template)
            params = params_match.group(1) if params_match else ""
            
            if "host=" not in params:
                params = params.rstrip("#") + f"&host={FIXED_SNI_HOST}"
            else:
                params = re.sub(r'host=[^&]+', f'host={FIXED_SNI_HOST}', params)
                
            if "sni=" not in params:
                params = params.rstrip("#") + f"&sni={FIXED_SNI_HOST}"
            else:
                params = re.sub(r'sni=[^&]+', f'sni={FIXED_SNI_HOST}', params)
                
    except FileNotFoundError:
        print(f"❌ 致命错误: 找不到模板文件 {TEMPLATE_FILE}。程序已终止。")
        return

    print("\n--- 开始获取所有节点地址 ---")
    domains = fetch_from_file(DOMAINS_FILE)
    simple_ips = fetch_simple_ips(REMOTE_IP_URL_1)
    dynamic_ips = fetch_dynamic_ips(DYNAMIC_IP_URL)
    github_ips = fetch_github_ips(GITHUB_IP_URL)
    
    all_nodes = domains + simple_ips + dynamic_ips + github_ips
  
    if not all_nodes:
        print("⚠️ 未能获取任何地址信息，无法生成订阅。")
        return

    print("\n🚀 开始生成节点链接...")
    node_links = []
    for i, node in enumerate(all_nodes, start=1):  # 从1开始编号
        address = node["address"]
        name_suffix = node.get("name_suffix", address)
        
        if ":" in address and not re.search(r'[a-zA-Z]', address.split(':')[0]):
            server_address = address
        else:
            server_address = f"{address}:443"
            
        link = f"vless://{uuid}@{server_address}?{params}"
        
        # 保留原来代码2的命名方式 + 序号
        node_name = f"{name_suffix}-{i:03d}"  # 三位序号，比如 -001
        final_link = f"{link}#{quote(node_name)}"
        node_links.append(final_link)

    print(f"🎉 总共生成了 {len(node_links)} 个节点。")

    subscription_content = "\n".join(node_links)
    encoded_content = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(encoded_content)
        print(f"✨ 订阅文件已成功生成！ 文件名: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ 写入订阅文件时发生错误: {e}")

if __name__ == "__main__":
    generate_subscription()
