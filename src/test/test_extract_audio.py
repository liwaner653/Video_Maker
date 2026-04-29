import sys
import os

# 添加src/steps路径
# 获取根文件夹的绝对路径（B 的父目录）
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from steps.extract_audio.extract_audio_step import extract_audio

if __name__ == "__main__":
    """
    单独运行时的命令行逻辑
    
    使用方法：
        python extract_audio.py <视频文件路径> <输出目录> [音轨索引] [开始时间] [时长]
    
    示例：
        # 提取第0个音轨，从5秒开始，提取3秒
        python extract_audio.py ./test.mp4 ./audio 0 5 3
        
        # 提取第1个音轨，完整提取
        python extract_audio.py ./test.mp4 ./audio 1
    """
    
    if len(sys.argv) < 3:
        print("使用方法：python extract_audio.py <视频文件路径> <输出目录> [音轨索引] [开始时间] [时长]")
        print("示例：")
        print("  python extract_audio.py ./test.mp4 ./audio 0 5 3")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_dir = sys.argv[2]
    audio_stream_index = int(sys.argv[3]) if len(sys.argv) >= 4 else 0
    start_time = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.0
    duration = float(sys.argv[5]) if len(sys.argv) >= 6 else 0.0
    
    print(f"参数: 视频={video_path}, 输出={output_dir}, 音轨={audio_stream_index}, 开始={start_time}s, 时长={duration}s")
    result = extract_audio(video_path, output_dir, audio_stream_index, start_time, duration)
    
    if result:
        print(f"\n✅ 成功: {result}")
    else:
        print(f"\n❌ 失败")