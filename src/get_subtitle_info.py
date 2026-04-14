# get_subtitle_info.py
import subprocess
import json
import os

# 定义支持的视频文件后缀，用于在文件夹模式下过滤非视频文件
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts'}

def get_target_subtitle_indices(video_path: str, target_lang: str = "", target_title: str = "") -> list:
    """
    获取视频中符合指定语言和标题关键字的字幕轨道索引。
    
    Args:
        video_path: 视频文件的完整路径
        target_lang: 目标语言关键字（不区分大小写，如 'ger', 'chi', 'eng'）
        target_title: 目标标题关键字（不区分大小写，如 'forced', '简体'）
        
    Returns:
        list: 符合条件的轨道索引列表
    """
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 's',
        '-show_entries', 'stream=index,codec_name:stream_tags=language,title',
        '-of', 'json',
        video_path
    ]
    
    matching_indices = []
    
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, encoding='utf-8')
        info = json.loads(result.stdout)
        streams = info.get('streams', [])
        
        if not streams:
            print(f"  ⚠️ 无字幕: {os.path.basename(video_path)}")
            return matching_indices

        for stream in streams:
            index = stream.get('index')
            tags = stream.get('tags', {})
            
            # 获取语言和标题，转为小写以实现不区分大小写的匹配
            language = tags.get('language', 'und').lower()
            title = tags.get('title', '').lower()
            codec = stream.get('codec_name', '未知')
            
            # 校验逻辑：如果用户输入了条件，则必须包含该关键字；如果为空，则默认该条件通过
            lang_match = (not target_lang) or (target_lang.lower() in language)
            title_match = (not target_title) or (target_title.lower() in title)
            
            if lang_match and title_match:
                matching_indices.append(index)
                print(f"  ✅ 找到匹配轨道 -> 索引: {index} | 语言: {tags.get('language', 'und')} | 名称: {tags.get('title', '无')} | 格式: {codec}")

    except subprocess.CalledProcessError as e:
        print(f"  ❌ ffprobe 处理失败: {os.path.basename(video_path)}\n  错误信息: {e.stderr.strip()}")
    except json.JSONDecodeError:
        print(f"  ❌ JSON 解析失败: {os.path.basename(video_path)}")
        
    return matching_indices

def process_path(input_path: str, target_lang: str, target_title: str):
    """
    处理用户输入的路径（文件或文件夹）
    """
    if os.path.isfile(input_path):
        # 如果是单一文件，直接判断后缀并处理
        ext = os.path.splitext(input_path)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            print(f"\n正在分析文件: {os.path.basename(input_path)}")
            get_target_subtitle_indices(input_path, target_lang, target_title)
        else:
            print(f"❌ 提示：文件 '{input_path}' 不是支持的视频格式。")
            
    elif os.path.isdir(input_path):
        # 如果是文件夹，遍历其中的文件
        print(f"\n📁 正在扫描文件夹: {input_path}")
        video_files = []
        
        for root, _, files in os.walk(input_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in VIDEO_EXTENSIONS:
                    video_files.append(os.path.join(root, file))
                    
        if not video_files:
            print("⚠️ 文件夹中未找到支持的视频文件。")
            return
            
        print(f"共发现 {len(video_files)} 个视频文件，开始批量分析...\n")
        print("-" * 50)
        
        for i, video_file in enumerate(video_files, 1):
            print(f"[{i}/{len(video_files)}] 正在分析: {os.path.basename(video_file)}")
            get_target_subtitle_indices(video_file, target_lang, target_title)
            print("-" * 50)
    else:
        print(f"❌ 错误：找不到文件或路径无效 '{input_path}'")

if __name__ == "__main__":
    print("=== 🎬 视频字幕轨道提取工具 (支持批量与过滤) ===")
    
    # 1. 获取路径
    user_input = input("请输入视频文件或文件夹的完整路径: ").strip().strip('"\'')
    
    # 2. 获取过滤条件
    print("\n-- 设置过滤条件 (直接回车表示不限制) --")
    target_lang = input("请输入目标语言关键字 (例如: ger, chi, eng): ").strip()
    target_title = input("请输入目标名称关键字 (例如: forced, 简体): ").strip()
    
    # 3. 开始处理
    process_path(user_input, target_lang, target_title)