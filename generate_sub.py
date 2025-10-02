import requests
import base64
import os
from urllib.parse import quote

CF_IP_URL = "https://raw.githubusercontent.com/XIU2/CloudflareSpeedTest/master/ip.txt"
TEMPLATE_FILE = "vless_template.txt"
DOMAINS_FILE = "domains.txt"
OUTPUT_FILE_NAME = "sub" # 直接在根目录生成名为 sub 的文件

def get_cf_ips():
    print("正在获取最新的Cloudflare IP列表...")
    try:
        response = requests.get(CF_IP_URL, timeout=10)
        response.raise_for_status()
        ips = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"成功获取 {len(ips)} 个IP地址。")
        return ips
    except requests.RequestException as e:
        print(f"获取IP列表失败: {e}")
        return []

def generate_subscription():
    try:
        with open(TEMPLATE_FILE, 'r') as f: template = f.read().strip()
        with open(DOMAINS_FILE, 'r') as f: domains = [line.strip() for line in f if line.strip()]
    except FileNotFoundError as e:
        print(f"错误：找不到文件 {e.filename}。")
        return

    cf_ips = get_cf_ips()
    if not cf_ips or not domains or not template:
        print("IP、域名或模板为空，无法生成订阅。")
        return

    all_nodes = []
    for domain in domains:
        for ip in cf_ips:
            node_url = template.replace("[IP]", ip).replace("[HOST]", domain)
            node_name = f"CF-{domain}-{ip}"
            encoded_node_name = quote(node_name)
            final_node_url = f"{node_url}#{encoded_node_name}"
            all_nodes.append(final_node_url)

    print(f"总共生成了 {len(all_nodes)} 个节点配置。")
    subscription_content = "\n".join(all_nodes)
    encoded_subscription = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')

    with open(OUTPUT_FILE_NAME, 'w') as f:
        f.write(encoded_subscription)
        
    print(f"订阅文件已成功生成并保存到: {OUTPUT_FILE_NAME}")

if __name__ == "__main__":
    generate_subscription()
