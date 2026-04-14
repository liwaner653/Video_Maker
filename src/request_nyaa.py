import requests
from bs4 import BeautifulSoup

def search_nyaa(keyword):
    # 构建带查询参数的 URL
    url = f"https://nyaa.si/?q={keyword}"
    
    # 添加请求头模拟普通浏览器，防止被网站拦截
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 定位到包含结果的表格
    table = soup.find('table', class_='torrent-list')
    if not table:
        print("未找到任何结果。")
        return []

    results = []
    # 获取表格 tbody 中的所有 tr (行)
    rows = table.find('tbody').find_all('tr')
    
    for row in rows:
        # 使用 CSS 选择器提取标题
        # 排除包含评论数的 <a> 标签 (class='comments')
        title_tag = row.select_one('td[colspan="2"] a:not(.comments)')
        if not title_tag:
            continue
        title = title_tag.get('title', title_tag.text.strip())
        
        # 使用 CSS 选择器提取 href 以 'magnet:?' 开头的 <a> 标签
        magnet_tag = row.select_one('a[href^="magnet:?"]')
        magnet_link = magnet_tag['href'] if magnet_tag else "未找到磁力链接"
        
        results.append({
            'title': title,
            'magnet': magnet_link
        })
        
    return results

def main():
    print("--- Nyaa 搜索脚本 ---")
    keyword = input("请输入搜索关键字: ").strip()
    if not keyword:
        print("关键字不能为空！")
        return

    print("正在搜索，请稍候...")
    results = search_nyaa(keyword)
    
    if not results:
        return
        
    print(f"\n成功找到 {len(results)} 个结果:\n")
    # 打印搜索结果列表
    for i, res in enumerate(results):
        print(f"[{i}] {res['title']}")
        
    try:
        # 接收用户选择
        choice = input("\n请输入您想获取的条目编号 (输入 q 退出): ").strip()
        if choice.lower() == 'q':
            return
            
        choice_idx = int(choice)
        if 0 <= choice_idx < len(results):
            print("\n================ 磁力链接 ================\n")
            print(results[choice_idx]['magnet'])
            print("\n==========================================\n")
        else:
            print("错误：无效的输入编号。")
    except ValueError:
        print("错误：请输入有效的数字编号。")

if __name__ == "__main__":
    main()