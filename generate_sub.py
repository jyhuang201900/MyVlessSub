import requests
import base64
from urllib.parse import quote

# --- 文件和URL配置 ---
# Cloudflare 优选IP源
CF_IP_URL = "https://raw.githubusercontent.com/XIU2/CloudflareSpeedTest/master/ip.txt" 
# VLESS模板文件
TEMPLATE_FILE = "vless_template.txt"
# 优选域名文件
DOMAINS_FILE = "domains.txt"
# 输出的订阅文件名
OUTPUT_FILE_NAME = "sub.txt"

def get_addresses_from_url(url):
    """从URL获取内容并按行分割成列表"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # 过滤掉空行和无效行
        addresses = [line.strip() for line in response.text.split('\n'
                                                                ) if line.strip() and not line.startswith('#')]
        print(f"成功从 {url} 获取 {len(addresses)} 个地址。")
        return addresses
    except requests.RequestException as e:
        print(f"从 {url} 获取地址失败: {e}")
        return []

def get_addresses_from_file(file_path):
    """从本地文件获取内容并按行分割成列表"""
    try:
        with open(file_path, 'r') as f:
            # 过滤掉空行和注释行
            addresses = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"成功从 {file_path} 获取 {len(addresses)} 个地址。")
            return addresses
    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}。")
        return []

def generate_subscription():
    """主生成函数"""
    # 1. 读取VLESS模板
    try:
        with open(TEMPLATE_FILE, 'r') as f:
            template = f.read().strip()
    except FileNotFoundError:
        print(f"错误：找不到模板文件 {TEMPLATE_FILE}。无法继续。")
        return

    # 2. 获取所有连接地址
    ip_addresses = get_addresses_from_url(CF_IP_URL)
    domain_addresses = get_addresses_from_file(DOMAINS_FILE)
    
    # 合并所有地址源
    all_connect_addresses = ip_addresses + domain_addresses
    
    if not all_connect_addresses:
        print("未能获取任何IP或域名地址，无法生成订阅。")
        return

    # 3. 遍历地址池，生成节点链接
    all_nodes = []
    for address in all_connect_addresses:
        # 替换模板中的 [ADDRESS] 占位符
        node_url = template.replace("[ADDRESS]", address)
        
        # 创建一个描述性的节点名称
        node_type = "IP" if '.' in address and address.replace('.', '').isdigit() else "域名"
        node_name = f"CF-{node_type}-{address}"
        
        # 将节点名称附加到链接后面
        final_node_url = f"{node_url}#{quote(node_name)}"
        all_nodes.append(final_node_url)

    print(f"总共生成了 {len(all_nodes)} 个节点配置。")

    # 4. Base64编码并写入文件
    subscription_content = "\n".join(all_nodes)
    encoded_subscription = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')

    with open(OUTPUT_FILE_NAME, 'w', encoding='utf-8') as f:
        f.write(encoded_subscription)
        
    print(f"订阅文件已成功生成并保存到: {OUTPUT_FILE_NAME}")

if __name__ == "__main__":
    generate_subscription()
