import os
import re
import sys

def process_videos(folder_path):
    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a valid directory")
        return
    
    titles = []
    video_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.flv', '.wmv')
    
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(video_extensions):
            match = re.search(r'-([^\[]+)\[', filename)
            if match:
                title = match.group(1).strip()
                titles.append(title)
            
            ep_match = re.search(r'E(\d{2})', filename)
            if ep_match:
                episode = ep_match.group(1)
                ext = os.path.splitext(filename)[1]
                new_name = f"{episode}{ext}"
                old_path = os.path.join(folder_path, filename)
                new_path = os.path.join(folder_path, new_name)
                os.rename(old_path, new_path)
                print(f"Renamed: {filename} -> {new_name}")
    
    txt_path = os.path.join(folder_path, 'titles.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        for title in titles:
            f.write(title + '\n')
    
    print(f"Created {txt_path} with {len(titles)} titles")

def rename_videos_with_titles(folder_path, txt_path):
    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a valid directory")
        return
    if not os.path.isfile(txt_path):
        print(f"Error: {txt_path} is not a valid file")
        return

    with open(txt_path, 'r', encoding='utf-8') as f:
        titles = [line.strip() for line in f if line.strip()]

    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.mp4'):
            match = re.search(r'^(\d{2})_', filename)
            if match:
                num_str = match.group(1)
                num = int(num_str)
                if 1 <= num <= len(titles):
                    ext = os.path.splitext(filename)[1]
                    title = titles[num - 1]
                    new_name = f"{num_str} {title}{ext}"
                    old_path = os.path.join(folder_path, filename)
                    new_path = os.path.join(folder_path, new_name)
                    os.rename(old_path, new_path)
                    print(f"Renamed: {filename} -> {new_name}")


if __name__ == "__main__":
    print("选择功能：")
    print("1. process_videos - 处理视频并提取标题")
    print("2. rename_videos_with_titles - 使用txt文件重命名视频")
    choice = input("请输入选项 (1 或 2): ").strip()
    
    if choice == "1":
        folder_path = input("请输入文件夹路径: ")
        process_videos(folder_path)
    elif choice == "2":
        folder_path = input("请输入文件夹路径: ")
        txt_path = input("请输入txt文件路径: ")
        rename_videos_with_titles(folder_path, txt_path)
    else:
        print("无效选项")