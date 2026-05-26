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

if __name__ == "__main__":
    folder_path = input("请输入文件夹路径: ")
    process_videos(folder_path)