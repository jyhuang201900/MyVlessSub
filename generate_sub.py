import requests
import base64
import re
from urllib.parse import urlparse, parse_qs, quote
from bs4 import BeautifulSoup

# --- 配置区 ---
TEMPLATE_FILE = "vless_template.txt"
DOMAINS_FILE = "domains.txt"
OUTPUT_FILE = "sub.txt"

# 1. 原始的远程优选IP源
REMOTE_IP_URL_1 = "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_IPs_port_443.txt"

# 2. 新增的动态IP源
DYNAMIC_IP_URL = "https://stock.hostmonit.com/CloudFlareYes"

# 3. 新增的GitHub优选IP源
GITHUB_IP_URL = "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"
# --- 配置区结束 ---

# 全局变量，用于存储从模板中解析出的配置
VLESS_CONFIG = {}

def parse_template(template_file):
    """解析VLESS模板文件，提取核心配置"""
    global VLESS_CONFIG
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            template_url = f.read().strip()
        
        parsed = urlparse(template_url)
        params = parse_qs(parsed.query)

        VLESS_CONFIG = {
            "uuid": parsed.username,
            "host": params.get('host', [None])[0],
            "path": params.get('path', [None])[0],
            "sni": params.get('sni', [None])[0]
        }
        
        # UUID 是必须的，否则无法生成链接
        if not VLESS_CONFIG["uuid"]:
            print("❌ 模板文件错误: 未能解析出 UUID。")
            return False
        
        print("✅ VLESS模板解析成功！")
        return True
    except FileNotFoundError:
        print(f"❌ 致命错误: 找不到模板文件 {template_file}。")
        return False
    except Exception as e:
        print(f"❌ 解析模板时发生错误: {e}")
        return False

def generate_vless_url(address_info):
    """根据地址信息和全局配置动态生成VLESS URL"""
    addr = address_info.get("ip") or address_info.get("domain")
    port = address_info.get("port", 443)
    protocol_type = address_info.get("protocol", "TLS")
    name_suffix = address_info.get("name", addr)

    # 从全局配置中安全地获取值，如果不存在则使用默认值
    uuid = VLESS_CONFIG.get("uuid")
    ws_host = VLESS_CONFIG.get("host")
    ws_path = VLESS_CONFIG.get("path", "/") # 如果路径不存在，默认为 "/"
    sni = VLESS_CONFIG.get("sni")

    # 核心参数检查
    if not uuid:
        # 这个情况基本不会发生，因为 parse_template 会先检查
        print(f"⚠️ 警告: UUID为空，跳过节点 {addr}")
        return None

    params = { "encryption": "none", "type": "ws" }
    
    if ws_host:
        params["host"] = ws_host
    
    # 路径参数处理：直接使用，因为 parse_qs 已经解码了
    # 我们用 quote 重新编码，但指定安全字符，防止双重编码
    params["path"] = quote(ws_path, safe='/?&=')

    if protocol_type == "TLS":
        params["security"] = "tls"
        if sni:
            params["sni"] = sni
        params["fp"] = "randomized"
    else: # HTTP
        params["security"] = "none"

    param_str = "&".join([f"{k}={v}" for k, v in params.items() if v is not None])
    node_name = quote(f"{protocol_type}-{address_info['counter']}-{name_suffix}")
    
    return f"vless://{uuid}@{addr}:{port}?{param_str}#{node_name}"

def fetch_from_file(file_path):
    """从本地文件读取地址列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"✅ 从本地文件 {file_path} 获取 {len(lines)} 个域名。")
            return lines
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {file_path}")
        return []

def fetch_simple_ips(url):
    """从URL获取简单的IP列表"""
    if not url: return []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip() and not line.strip().startswith('#')]
        print(f"✅ 从 URL {url.split('/')[-1]} 获取 {len(lines)} 个IP。")
        return lines
    except requests.RequestException as e:
        print(f"❌ 从 URL {url.split('/')[-1]} 获取IP失败: {e}")
        return []

def fetch_dynamic_ips(url):
    """从 hostmonit 解析动态IP地址和ISP信息"""
    if not url: return []
    print("🔄 正在从 hostmonit 获取动态IP...")
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        results = []
        for row in soup.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) >= 5:
                ip, isp = cols[0].text.strip(), cols[4].text.strip().replace(' ', '')
                if ip and isp:
                    results.append({"ip": ip, "name": isp})
        
        print(f"✅ 成功从 hostmonit 获取 {len(results)} 个动态IP。")
        return results
    except Exception as e:
        print(f"❌ hostmonit: 获取或解析失败: {e}")
        return []

def fetch_github_ips(url):
    """从 GitHub Raw URL 解析带自定义端口和名称的IP"""
    if not url: return []
    print(f"🔄 正在从 GitHub 获取优选IP...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        results, regex = [], r'^([^:]+):(\d+)#(.*)$'
        for line in response.text.strip().split('\n'):
            match = re.match(regex, line.strip())
            if match:
                results.append({"ip": match.group(1), "port": int(match.group(2)), "name": match.group(3).strip() or match.group(1)})
        
        print(f"✅ 成功从 GitHub 获取 {len(results)} 个优选IP。")
        return results
    except requests.RequestException as e:
        print(f"❌ GitHub: 获取优选IP失败: {e}")
        return []

def main():
    """主函数，生成订阅文件"""
    if not parse_template(TEMPLATE_FILE):
        return

    all_nodes_info = []
    counter = 1

    # --- 数据获取 ---
    print("\n--- 1. 获取所有节点地址 ---")
    data_sources = [
        ("domains", fetch_from_file(DOMAINS_FILE)),
        ("simple_ips", fetch_simple_ips(REMOTE_IP_URL_1)),
        ("dynamic_ips", fetch_dynamic_ips(DYNAMIC_IP_URL)),
        ("github_ips", fetch_github_ips(GITHUB_IP_URL))
    ]

    # --- 节点信息处理 ---
    print("\n--- 2. 处理节点信息 ---")
    for source_type, data in data_sources:
        if not data: continue
        
        if source_type == "domains":
            for domain in data:
                all_nodes_info.extend([
                    {"domain": domain, "protocol": "TLS", "counter": counter},
                    {"domain": domain, "port": 80, "protocol": "HTTP", "counter": counter + 1}
                ])
                counter += 2
        elif source_type == "simple_ips":
            for ip in data:
                all_nodes_info.append({"ip": ip, "protocol": "TLS", "counter": counter})
                counter += 1
        elif source_type == "dynamic_ips":
            for item in data:
                all_nodes_info.extend([
                    {"ip": item["ip"], "port": 443, "protocol": "TLS", "name": item["name"], "counter": counter},
                    {"ip": item["ip"], "port": 80, "protocol": "HTTP", "name": item["name"], "counter": counter + 1}
                ])
                counter += 2
        elif source_type == "github_ips":
            for item in data:
                all_nodes_info.append({"ip": item["ip"], "port": item["port"], "protocol": "TLS", "name": item["name"], "counter": counter})
                counter += 1

    if not all_nodes_info:
        print("\n⚠️ 警告: 未能获取任何节点信息，无法生成订阅。")
        return

    # --- 生成链接和文件 ---
    print(f"\n🚀 开始为 {len(all_nodes_info)} 个节点生成链接...")
    node_links = [link for info in all_nodes_info if (link := generate_vless_url(info)) is not None]
    
    subscription_content = "\n".join(node_links)
    encoded_content = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(encoded_content)
        print(f"\n✨ 订阅文件已成功生成！✨")
        print(f"   文件名: {OUTPUT_FILE}")
        print(f"   总节点数: {len(node_links)}")
    except Exception as e:
        print(f"❌ 写入订阅文件时发生错误: {e}")

if __name__ == "__main__":
    main()
