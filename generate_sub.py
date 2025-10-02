import requests
import base64
import re
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 配置区 ---
# VLESS 模板文件路径
TEMPLATE_FILE = "vless_template.txt"
# 本地优选域名文件路径
DOMAINS_FILE = "domains.txt"
# 生成的订阅文件名
OUTPUT_FILE = "sub.txt"

# 1. 原始的远程优选IP源
REMOTE_IP_URL_1 = "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_IPs_port_443.txt"

# 2. 动态IP源
DYNAMIC_IP_URL = "https://stock.hostmonit.com/CloudFlareYes"

# 3. GitHub优选IP源
GITHUB_IP_URL = "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"
# --- 配置区结束 ---

def fetch_from_file(file_path):
    """从本地文件读取域名列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"✅ 从本地文件 {file_path} 获取 {len(lines)} 个域名。")
            return [{"domain": line, "type": "domain"} for line in lines]
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {file_path}")
        return []

def fetch_simple_ips(url):
    """从URL获取简单的IP列表"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip() and not line.strip().startswith('#')]
        print(f"✅ 从 URL {url.split('/')[-1]} 获取 {len(lines)} 个IP。")
        return [{"ip": line, "port": "443", "type": "ip", "name_suffix": line} for line in lines]
    except requests.RequestException as e:
        print(f"❌ 从 URL {url.split('/')[-1]} 获取IP失败: {e}")
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
                    results.append({
                        "ip": ip, 
                        "port": "443", 
                        "type": "ip", 
                        "name_suffix": isp
                    })
        
        print(f"✅ 成功从 hostmonit 获取 {len(results)} 个动态IP。")
        return results
    except Exception as e:
        print(f"❌ hostmonit: 获取或解析失败: {e}")
        return []

def fetch_github_ips(url):
    """从 GitHub Raw URL 解析带自定义端口和名称的IP"""
    print(f"🔄 正在从 GitHub 获取优选IP...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        results = []
        regex = r'^([^:]+):(\d+)#(.*)$'
        for line in response.text.strip().split('\n'):
            match = re.match(regex, line.strip())
            if match:
                ip, port, name = match.groups()
                name_suffix = name.strip() or ip
                results.append({
                    "ip": ip,
                    "port": port,
                    "type": "ip",
                    "name_suffix": name_suffix
                })
        
        print(f"✅ 成功从 GitHub 获取 {len(results)} 个优选IP。")
        return results
    except requests.RequestException as e:
        print(f"❌ GitHub: 获取优选IP失败: {e}")
        return []

def generate_subscription():
    """主函数，生成订阅文件"""
    # 1. 读取VLESS模板
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            vless_template = f.read().strip()
            
            # 从模板中提取UUID和其他参数
            uuid_match = re.search(r'vless://([^@]+)@', vless_template)
            uuid = uuid_match.group(1) if uuid_match else ""
            
            # 提取查询参数部分
            params_match = re.search(r'\?(.+)#', vless_template)
            params = params_match.group(1) if params_match else ""
            
    except FileNotFoundError:
        print(f"❌ 致命错误: 找不到模板文件 {TEMPLATE_FILE}。程序已终止。")
        return

    # 2. 从所有来源获取地址
    print("\n--- 开始获取所有节点地址 ---")
    domains = fetch_from_file(DOMAINS_FILE)
    simple_ips = fetch_simple_ips(REMOTE_IP_URL_1)
    dynamic_ips = fetch_dynamic_ips(DYNAMIC_IP_URL)
    github_ips = fetch_github_ips(GITHUB_IP_URL)
    
    # 将所有来源的地址合并
    all_nodes = domains + simple_ips + dynamic_ips + github_ips
  
    if not all_nodes:
        print("\n⚠️ 警告: 未能获取任何地址信息，无法生成订阅。")
        return

    # 3. 遍历节点生成链接
    node_links = []
    print("\n🚀 开始生成节点链接...")
    
    for i, node in enumerate(all_nodes):
        # 根据节点类型生成不同的链接
        if node["type"] == "domain":
            # 域名类型节点
            domain = node["domain"]
            server = "www.visa.com.sg"  # 默认服务器地址
            
            # 构建VLESS链接
            link = f"vless://{uuid}@{server}:443?encryption=none&security=tls&type=ws&host={domain}&sni={domain}&fp=random&path=/？ed=2560"
            name = f"Domain-{i+1:03d}-{domain}"
            
        elif node["type"] == "ip":
            # IP类型节点
            ip = node["ip"]
            port = node["port"]
            name_suffix = node.get("name_suffix", ip)
            
            # 构建VLESS链接
            link = f"vless://{uuid}@{ip}:{port}?{params}"
            name = f"IP-{i+1:03d}-{name_suffix}"
        
        # 添加节点名称并进行URL编码
        final_link = f"{link}#{quote(name)}"
        node_links.append(final_link)

    print(f"🎉 总共生成了 {len(node_links)} 个节点。")

    # 4. Base64编码并写入文件
    subscription_content = "\n".join(node_links)
    encoded_content = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(encoded_content)
        print(f"\n✨ 订阅文件已成功生成！✨\n   文件名: {OUTPUT_FILE}\n")
    except Exception as e:
        print(f"❌ 写入订阅文件时发生错误: {e}")

if __name__ == "__main__":
    generate_subscription()
