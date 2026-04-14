#!/usr/bin/env python3
# extract_audio.py
import os
import sys
import subprocess
from util import get_video_duration


def extract_audio(video_path: str, output_dir: str, audio_stream_index: int = 0, cut_front_seconds: float = 0.0, cut_back_seconds: float = 0.0):
    """
    提取视频指定音轨的音频（AAC编码）
    :param video_path: 视频文件路径
    :param output_dir: 音频输出目录
    :param audio_stream_index: 音频轨道索引（默认0）
    :param cut_front_seconds: 裁剪开头秒数（默认0，不裁剪）
    :param cut_back_seconds: 裁剪结尾秒数（默认0，不裁剪）
    :return: 生成的音频文件路径，失败返回None
    """
    if not os.path.exists(video_path):
        print(f"错误：视频文件不存在 {video_path}")
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成音频文件名
    video_name = os.path.basename(video_path)
    audio_name = os.path.splitext(video_name)[0] + '.aac'
    audio_path = os.path.join(output_dir, audio_name)
    
    # 构建ffmpeg命令 (按照从左到右顺序拼接)
    command = ["ffmpeg"]
    
    # 处理开头裁剪（-ss 放在 -i 前更高效）
    if cut_front_seconds > 0:
        command.extend(["-ss", str(cut_front_seconds)])
        
    # 处理结尾裁剪
    if cut_back_seconds > 0:
        duration = get_video_duration(video_path)
        if duration > 0:
            end_time = duration - cut_back_seconds
            # 参数校验：防止开头和结尾裁剪加起来超过视频总时长
            if end_time <= cut_front_seconds:
                print(f"错误：视频总时长({duration:.2f}s) 不足以进行开头({cut_front_seconds}s)和结尾({cut_back_seconds}s)的裁剪！")
                return None
            # -to 放在 -i 之前，表示读取文件直到该时间点
            command.extend(["-to", str(end_time)])
        else:
            print("错误：无法获取视频时长，无法完成结尾裁剪。")
            return None
            
    # 追加剩余参数
    command.extend([
        "-i", video_path,
        "-map", f"0:a:{audio_stream_index}",  # 选择指定音轨
        "-vn",  # 不处理视频流
        "-acodec", "aac",  # AAC编码
        "-y",  # 覆盖已有文件
        audio_path
    ])
    
    print(f"开始提取音频：{video_name} (音轨{audio_stream_index})")
    print(f"执行命令: {' '.join(command)}")
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ 音频提取完成：{audio_path}")
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"❌ 音频提取失败：{e.stderr}")
        return None

# 单独运行时的命令行逻辑
if __name__ == "__main__":
#     if len(sys.argv) < 3:
#         print("使用方法：python extract_audio.py <视频文件路径> <输出目录> [音轨索引] [开头裁剪秒数] [结尾裁剪秒数]")
#         print("示例：")
#         print("  python extract_audio.py ./test.mp4 ./audio 1 5.5 3.0")
#         sys.exit(1)
#     
#     video_path = sys.argv[1]
#     output_dir = sys.argv[2]
#     audio_stream_index = int(sys.argv[3]) if len(sys.argv) >= 4 else 0
#     cut_front_seconds = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.0
#     cut_back_seconds = float(sys.argv[5]) if len(sys.argv) >= 6 else 0.0
#     
#     extract_audio(video_path, output_dir, audio_stream_index, cut_front_seconds, cut_back_seconds)
    extract_audio('C:/Users/waner/Desktop/Trim.mp4', 
                  'C:/Users/waner/Desktop/Trim_cut.mp4', 
                  0, 0, 5)