import requests
import base64
import re
import socket
import time
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 配置区 ---
TEMPLATE_FILE = "vless_template.txt"
DOMAINS_FILE = "domains.txt"
OUTPUT_FILE = "sub.txt"
FIXED_SNI_HOST = "bui.2514376.xyz"

REMOTE_IP_URL_1 = "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_IPs_port_443.txt"
DYNAMIC_IP_URL = "https://stock.hostmonit.com/CloudFlareYes"
GITHUB_IP_URL = "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"
EXTRA_IP_URL = "https://raw.githubusercontent.com/jyhuang201900/cfipcaiji/refs/heads/main/ip.txt"  # 新增的数据源

# 地理位置缓存
GEO_CACHE = {}
# --- 配置区结束 ---

def get_domain_location(domain):
    """通过域名/IP 获取地理位置"""
    if domain in GEO_CACHE:
        return GEO_CACHE[domain]

    try:
        ip = socket.gethostbyname(domain.split(':')[0])
        r = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                country = data.get("country", "")
                city = data.get("city", "")
                region = data.get("regionName", "")
                location = city or region or country or ip
                GEO_CACHE[domain] = location
                print(f"📍 {domain} -> {location}")
                time.sleep(0.1)
                return location
        GEO_CACHE[domain] = ip
        print(f"⚠️ {domain} 查询失败，使用IP: {ip}")
        return ip
    except Exception as e:
        print(f"❌ {domain} 位置解析失败: {e}")
        GEO_CACHE[domain] = domain
        return domain

def fetch_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"✅ 从本地文件 {file_path} 获取 {len(lines)} 个域名。")
            return [{"address": line, "name_suffix": get_domain_location(line)} for line in lines]
    except FileNotFoundError:
        print(f"❌ 找不到文件 {file_path}")
        return []

def fetch_simple_ips(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        lines = [line.strip() for line in r.text.splitlines() if line.strip() and not line.startswith('#')]
        print(f"✅ 从 {url} 获取 {len(lines)} 个IP。")
        return [{"address": line, "name_suffix": line} for line in lines]
    except Exception as e:
        print(f"❌ 获取 {url} 失败: {e}")
        return []

def fetch_dynamic_ips(url):
    print("🔄 获取动态IP...")
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml")
        results = []
        for row in soup.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) >= 5:
                ip = cols[0].text.strip()
                isp = cols[4].text.strip().replace(' ', '')
                results.append({"address": ip, "name_suffix": isp})
        print(f"✅ 获取 {len(results)} 个动态IP")
        return results
    except Exception as e:
        print(f"❌ 动态IP获取失败: {e}")
        return []

def fetch_github_ips(url):
    print("🔄 获取GitHub优选IP...")
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        regex = r'^([^:]+):(\d+)#(.*)$'
        results = []
        for line in r.text.strip().split("\n"):
            m = re.match(regex, line.strip())
            if m:
                ip, port, name = m.groups()
                results.append({"address": f"{ip}:{port}", "name_suffix": name.strip() or ip})
        print(f"✅ 获取 {len(results)} 个GitHubIP")
        return results
    except Exception as e:
        print(f"❌ GitHub IP 获取失败: {e}")
        return []

def generate_subscription():
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            tpl = f.read().strip()
        uuid = re.search(r'vless://([^@]+)@', tpl).group(1)
        params = re.search(r'\?(.+)', tpl).group(1)

        params = re.sub(r'host=[^&]+', f'host={FIXED_SNI_HOST}', params) if "host=" in params else params + f"&host={FIXED_SNI_HOST}"
        params = re.sub(r'sni=[^&]+', f'sni={FIXED_SNI_HOST}', params) if "sni=" in params else params + f"&sni={FIXED_SNI_HOST}"
    except FileNotFoundError:
        print(f"❌ 找不到模板文件 {TEMPLATE_FILE}")
        return

    print("\n--- 获取所有节点 ---")
    all_nodes = (
        fetch_from_file(DOMAINS_FILE) +
        fetch_simple_ips(REMOTE_IP_URL_1) +
        fetch_dynamic_ips(DYNAMIC_IP_URL) +
        fetch_github_ips(GITHUB_IP_URL) +
        fetch_simple_ips(EXTRA_IP_URL)  # 新增节点来源
    )
    if not all_nodes:
        print("⚠️ 没有节点，退出")
        return

    print("\n🚀 生成节点链接...")
    node_links = []
    for i, node in enumerate(all_nodes, start=1):
        address = node["address"]
        name_suffix = node.get("name_suffix", address)
        server_address = address if ":" in address and not re.search(r'[a-zA-Z]', address.split(':')[0]) else f"{address}:443"
        link = f"vless://{uuid}@{server_address}?{params}"
        node_name = f"CF-{name_suffix}-{i:03d}"
        node_links.append(f"{link}#{quote(node_name)}")

    print(f"🎉 生成 {len(node_links)} 节点")
    encoded_content = base64.b64encode("\n".join(node_links).encode("utf-8")).decode("utf-8")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(encoded_content)
    print(f"✨ 已写入 {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_subscription()
