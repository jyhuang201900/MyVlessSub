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

# 1. 原始的远程优选IP源 (来自代码2)
REMOTE_IP_URL_1 = "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_IPs_port_443.txt"

# 2. 新增的动态IP源 (来自代码1)
DYNAMIC_IP_URL = "https://stock.hostmonit.com/CloudFlareYes"

# 3. 新增的GitHub优选IP源 (来自代码1)
GITHUB_IP_URL = "https://raw.githubusercontent.com/qwer-search/bestip/refs/heads/main/kejilandbestip.txt"
# --- 配置区结束 ---

def fetch_from_file(file_path):
    """从本地文件读取地址列表"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            print(f"✅ 从本地文件 {file_path} 获取 {len(lines)} 个域名。")
            return [{"address": line} for line in lines]
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
        return [{"address": line} for line in lines]
    except requests.RequestException as e:
        print(f"❌ 从 URL {url.split('/')[-1]} 获取IP失败: {e}")
        return []

def fetch_dynamic_ips(url):
    """(新增) 从 hostmonit 解析动态IP地址和ISP信息"""
    print("🔄 正在从 hostmonit 获取动态IP...")
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        results = []
        # find_all('tr')[1:] 会跳过表头
        for row in soup.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) >= 5:
                ip = cols[0].text.strip()
                # 将地区信息作为节点名的一部分，替换空格
                isp = cols[4].text.strip().replace(' ', '')
                if ip and isp:
                    results.append({"address": ip, "name_suffix": isp})
        
        print(f"✅ 成功从 hostmonit 获取 {len(results)} 个动态IP。")
        return results
    except Exception as e:
        print(f"❌ hostmonit: 获取或解析失败: {e}")
        return []

def fetch_github_ips(url):
    """(新增) 从 GitHub Raw URL 解析带自定义端口和名称的IP"""
    print(f"🔄 正在从 GitHub 获取优选IP...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        results = []
        # 正则表达式匹配: IP:端口#名称
        regex = r'^([^:]+):(\d+)#(.*)$'
        for line in response.text.strip().split('\n'):
            match = re.match(regex, line.strip())
            if match:
                ip, port, name = match.groups()
                # 注意：这里我们直接用IP:端口替换[ADDRESS]:443
                address = f"{ip}:{port}"
                # 使用#后面的内容作为节点名后缀
                name_suffix = name.strip() or ip
                results.append({"address": address, "name_suffix": name_suffix})
        
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
    # 每个元素都是一个字典，如 {"address": "1.1.1.1", "name_suffix": "Cloudflare"}
    all_addresses_info = domains + simple_ips + dynamic_ips + github_ips
  
    if not all_addresses_info:
        print("\n⚠️ 警告: 未能获取任何地址信息，无法生成订阅。")
        return

    # 3. 遍历地址池生成所有节点链接
    node_links = []
    print("\n🚀 开始生成节点链接...")
    for i, info in enumerate(all_addresses_info):
        address = info["address"]
        name_suffix = info.get("name_suffix", address) # 如果没有提供后缀，就用地址本身
        
        # 核心替换逻辑
        # 对于 GitHub IP，它会是 "ip:port"，需要特殊处理
        if ":" in address and not re.search(r'[a-zA-Z]', address.split(':')[0]): # 简单判断是否是 IP:PORT 格式
            node_link = vless_template.replace(f"[ADDRESS]:443", address)
        else:
            node_link = vless_template.replace("[ADDRESS]", address)
      
        # 生成一个可读且唯一的节点名称
        node_name = quote(f"CF-Node-{i+1:03d}-{name_suffix}")
        
        final_link = f"{node_link}#{node_name}"
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
