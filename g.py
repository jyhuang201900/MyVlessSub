import requests
import base64
import re
import socket
from urllib.parse import quote
from bs4 import BeautifulSoup
import time

# --- 配置区 ---
TEMPLATE_FILE = "vless_template.txt"
DOMAINS_FILE = "domains.txt"
OUTPUT_FILE = "sub.txt"
FIXED_SNI_HOST = "bui.2514376.xyz"

REMOTE_IP_URL_1 = "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_IPs_port_443.txt"
DYNAMIC_IP_URL = "https://stock.hostmonit.com/CloudFlareYes"
GITHUB_IP_URL = "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"

# 地理位置缓存
GEO_CACHE = {}
# --- 配置区结束 ---

def get_domain_location(domain):
    """通过域名获取地理位置（优化版：查询ASN/域名托管位置）"""
    if domain in GEO_CACHE:
        return GEO_CACHE[domain]
    
    try:
        # 1. 解析域名为IP
        clean_domain = domain.split(':')[0]
        ip = socket.gethostbyname(clean_domain)
        
        # 2. 查询IP的ASN和托管信息
        response = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,as,org&lang=zh-CN", 
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                # 优先使用 ISP/组织名称（更准确）
                isp = data.get('isp', '')
                org = data.get('org', '')
                asn = data.get('as', '')
                
                # 判断是否为CDN
                cdn_keywords = ['cloudflare', 'akamai', 'fastly', 'cloudfront', 'cdn']
                is_cdn = any(kw in isp.lower() or kw in org.lower() for kw in cdn_keywords)
                
                if is_cdn:
                    # 对于CDN，使用ASN组织名
                    location = asn.split(' ', 1)[1] if ' ' in asn else org or isp
                    print(f"  🌐 {clean_domain} -> {location} (CDN)")
                else:
                    # 非CDN使用城市/地区
                    city = data.get('city', '')
                    region = data.get('regionName', '')
                    country = data.get('country', '')
                    location = city or region or country
                    print(f"  📍 {clean_domain} -> {location}")
                
                GEO_CACHE[domain] = location
                time.sleep(0.15)  # 避免API限流
                return location
        
        # API失败时的备用方案
        print(f"  ⚠️  {clean_domain} 位置查询失败，使用IP: {ip}")
        GEO_CACHE[domain] = ip
        return ip
        
    except Exception as e:
        print(f"  ❌ {domain} 解析失败: {e}")
        # 尝试从域名后缀猜测位置
        fallback = get_location_from_domain_suffix(domain)
        GEO_CACHE[domain] = fallback
        return fallback

def get_location_from_domain_suffix(domain):
    """从域名后缀推测位置（备用方案）"""
    suffix_map = {
        '.cn': '中国',
        '.hk': '香港',
        '.tw': '台湾',
        '.jp': '日本',
        '.kr': '韩国',
        '.sg': '新加坡',
        '.us': '美国',
        '.uk': '英国',
        '.de': '德国',
        '.fr': '法国',
    }
    
    for suffix, location in suffix_map.items():
        if domain.endswith(suffix):
            return location
    
    return domain.split(':')[0]  # 默认返回域名本身

def fetch_from_file(file_path):
    """从本地文件读取地址列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"✅ 从本地文件 {file_path} 获取 {len(lines)} 个域名。")
            
            results = []
            for line in lines:
                location = get_domain_location(line)
                results.append({"address": line, "name_suffix": location})
            
            return results
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {file_path}")
        return []

def fetch_simple_ips(url):
    """从URL获取简单的IP列表"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() 
                if line.strip() and not line.strip().startswith('#')]
        print(f"✅ 从 {url.split('/')[-1]} 获取 {len(lines)} 个IP。")
        
        # 为IP地址也查询位置
        results = []
        for line in lines[:50]:  # 限制查询数量避免超时
            location = get_ip_location(line)
            results.append({"address": line, "name_suffix": location})
        
        # 剩余IP使用默认标识
        results.extend([{"address": line, "name_suffix": line} 
                       for line in lines[50:]])
        
        return results
    except requests.RequestException as e:
        print(f"❌ 从 {url.split('/')[-1]} 获取IP失败: {e}")
        return []

def get_ip_location(ip):
    """查询IP地址的地理位置"""
    if ip in GEO_CACHE:
        return GEO_CACHE[ip]
    
    try:
        clean_ip = ip.split(':')[0]
        response = requests.get(
            f"http://ip-api.com/json/{clean_ip}?fields=city,regionName,country,isp&lang=zh-CN",
            timeout=3
        )
        
        if response.status_code == 200:
            data = response.json()
            city = data.get('city', '')
            region = data.get('regionName', '')
            country = data.get('country', '')
            location = city or region or country or clean_ip
            GEO_CACHE[ip] = location
            time.sleep(0.1)
            return location
            
    except Exception:
        pass
    
    GEO_CACHE[ip] = ip
    return ip

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
                address = f"{ip}:{port}"
                name_suffix = name.strip() or ip
                results.append({"address": address, "name_suffix": name_suffix})
        
        print(f"✅ 成功从 GitHub 获取 {len(results)} 个优选IP。")
        return results
    except requests.RequestException as e:
        print(f"❌ GitHub: 获取优选IP失败: {e}")
        return []

def generate_subscription():
    """主函数，生成订阅文件"""
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
        print("\n⚠️ 警告: 未能获取任何地址信息，无法生成订阅。")
        return

    node_links = []
    print("\n🚀 开始生成节点链接...")
    
    for i, node in enumerate(all_nodes):
        address = node["address"]
        name_suffix = node.get("name_suffix", address)
        
        if ":" in address and not re.search(r'[a-zA-Z]', address.split(':')[0]):
            server_address = address
        else:
            server_address = f"{address}:443"
            
        link = f"vless://{uuid}@{server_address}?{params}"
        node_name = f"CF-{name_suffix}-{i+1:03d}"
        
        final_link = f"{link}#{quote(node_name)}"
        node_links.append(final_link)

    print(f"🎉 总共生成了 {len(node_links)} 个节点。")

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
