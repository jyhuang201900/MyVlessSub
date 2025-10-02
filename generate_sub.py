import requests
import base64
from urllib.parse import quote

# --- 配置区 ---
# VLESS 模板文件路径
TEMPLATE_FILE = "vless_template.txt"
# 本地优选域名文件路径
DOMAINS_FILE = "domains.txt"
# 远程优选IP源 URL (这里使用一个常见的源作为示例)
REMOTE_IP_URL = "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_IPs_port_443.txt"
# 生成的订阅文件名
OUTPUT_FILE = "sub.txt"
# --- 配置区结束 ---

def fetch_from_url(url):
    """从URL获取地址列表，自动过滤空行和注释"""
    try:
        print(f"🔄 正在从 URL 获取优选IP: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # 如果请求失败则抛出异常
        
        content = response.text
        # 按行分割，去除首尾空白，并过滤掉空行和以'#'开头的注释行
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith('#')]
        
        print(f"✅ 成功从 URL 获取 {len(lines)} 个IP地址。")
        return lines
    except requests.RequestException as e:
        print(f"❌ 从 URL 获取IP失败: {e}")
        return []

def fetch_from_file(file_path):
    """从本地文件获取地址列表，自动过滤空行和注释"""
    try:
        print(f"🔄 正在从本地文件读取优选域名: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            # 逻辑同上
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            
            print(f"✅ 成功从本地文件获取 {len(lines)} 个域名。")
            return lines
    except FileNotFoundError:
        print(f"❌ 错误: 找不到本地域名文件 {file_path}")
        return []
    except Exception as e:
        print(f"❌ 读取本地文件时发生错误: {e}")
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

    # 2. 获取所有的连接地址
    ip_addresses = fetch_from_url(REMOTE_IP_URL)
    domain_addresses = fetch_from_file(DOMAINS_FILE)
    
    # 将IP和域名合并为一个地址池
    all_addresses = ip_addresses + domain_addresses
    
    if not all_addresses:
        print("⚠️ 警告: 未能获取任何IP或域名，无法生成节点。")
        return

    # 3. 遍历地址池生成所有节点链接
    node_links = []
    print("\n🚀 开始生成节点链接...")
    for i, address in enumerate(all_addresses):
        # 替换模板中的 [ADDRESS] 占位符
        node_link = vless_template.replace("[ADDRESS]", address)
        
        # 生成一个可读的节点名称
        # 使用 url-safe 的 quote 函数对名称进行编码
        node_name = quote(f"CF-Node-{i+1:03d}-{address}")
        
        # 将编码后的名称附加到链接末尾
        final_link = f"{node_link}#{node_name}"
        node_links.append(final_link)

    print(f"🎉 总共生成了 {len(node_links)} 个节点。")

    # 4. 将所有链接用换行符连接，并进行Base64编码
    subscription_content = "\n".join(node_links)
    encoded_content = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')

    # 5. 将编码后的内容写入输出文件
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(encoded_content)
        print(f"\n✨ 订阅文件已成功生成！✨\n✨ 文件名: {OUTPUT_FILE} ✨\n")
    except Exception as e:
        print(f"❌ 写入订阅文件时发生错误: {e}")

if __name__ == "__main__":
    generate_subscription()
