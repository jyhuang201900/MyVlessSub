import requests
import base64
import os
from urllib.parse import quote

# --- 配置信息 ---
# Cloudflare IP列表的URL，你可以根据需要更换
CF_IP_URL = "https://raw.githubusercontent.com/XIU2/CloudflareSpeedTest/master/ip.txt"
# 读取模板和域名文件的路径
TEMPLATE_FILE = "vless_template.txt"
DOMAINS_FILE = "domains.txt"
# 输出目录和文件名
OUTPUT_DIR = "output"
OUTPUT_FILE_NAME = "sub" # 生成的订阅文件名将是 sub

def get_cf_ips():
    """从URL获取Cloudflare IP列表"""
    print("正在获取最新的Cloudflare IP列表...")
    try:
        response = requests.get(CF_IP_URL, timeout=10)
        response.raise_for_status()
        # 按行分割，并去除空行
        ips = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"成功获取 {len(ips)} 个IP地址。")
        return ips
    except requests.RequestException as e:
        print(f"获取IP列表失败: {e}")
        return []

def generate_subscription():
    """生成订阅文件"""
    try:
        with open(TEMPLATE_FILE, 'r') as f:
            template = f.read().strip()
        with open(DOMAINS_FILE, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]
    except FileNotFoundError as e:
        print(f"错误：找不到文件 {e.filename}。请确保 {TEMPLATE_FILE} 和 {DOMAINS_FILE} 文件存在。")
        return

    cf_ips = get_cf_ips()
    if not cf_ips or not domains or not template:
        print("IP、域名或模板为空，无法生成订阅。")
        return

    all_nodes = []
    node_count = 0

    print(f"开始为 {len(domains)} 个域名和 {len(cf_ips)} 个IP生成节点...")
    for domain in domains:
        for ip in cf_ips:
            # 替换模板中的占位符
            node_url = template.replace("[IP]", ip).replace("[HOST]", domain)
            
            # 为节点生成一个唯一的名称
            node_name = f"CF-{domain}-{ip}"
            # 对节点名称进行URL编码，并附加到链接末尾
            encoded_node_name = quote(node_name)
            final_node_url = f"{node_url}#{encoded_node_name}"
            
            all_nodes.append(final_node_url)
            node_count += 1

    print(f"总共生成了 {node_count} 个节点配置。")

    # 将所有节点链接用换行符连接
    subscription_content = "\n".join(all_nodes)
    
    # Base64编码
    encoded_subscription = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')

    # 创建输出目录（如果不存在）
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # 写入最终的Base64编码的订阅文件
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE_NAME)
    with open(output_path, 'w') as f:
        f.write(encoded_subscription)
        
    print(f"订阅文件已成功生成并保存到: {output_path}")

if __name__ == "__main__":
    generate_subscription()

