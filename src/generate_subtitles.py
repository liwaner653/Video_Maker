import os
import sys
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

def generate_subtitles(audio_path: str, output_dir: str, model: str = "turbo", subtitle_lang: str = "de"):
    """
    使用Whisper生成指定语言的字幕
    :param audio_path: 音频文件路径
    :param output_dir: 字幕输出目录
    :param model: Whisper模型（默认turbo）
    :param subtitle_lang: 字幕语言（默认de，德语）
    :return: 生成的字幕文件路径，失败返回None
    """
    if not os.path.exists(audio_path):
        print(f"错误：音频文件不存在 {audio_path}")
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成字幕文件名
    audio_name = os.path.basename(audio_path)
    srt_name = os.path.splitext(audio_name)[0] + '.srt'
    srt_path = os.path.join(output_dir, srt_name)
    
    # 构建whisper命令
    command = [
        'whisper', audio_path,
        '--model', model,
        '--language', subtitle_lang,
        '--output_format', 'srt',
        '--output_dir', output_dir
    ]
    
    print(f"开始生成字幕：{audio_name} (语言：{subtitle_lang})")
    print(f"执行命令: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ 字幕生成完成：{srt_path}")
        print(f"result: {result}")
        return srt_path
    except subprocess.CalledProcessError as e:
        print(f"❌ 字幕生成失败：{e.stderr}")
        return None

# 单独运行时的命令行逻辑
if __name__ == "__main__":
#    if len(sys.argv) < 3:
#        print("使用方法：python generate_subtitles.py <音频文件路径> <输出目录> [模型] [字幕语言]")
#        print("示例：")
#        print("  python generate_subtitles.py ./audio/test.aac ./subtitles turbo de")
#        sys.exit(1)
    
    audio_path = r'' # sys.argv[1]
    output_dir = r'' # sys.argv[2]
    model = sys.argv[3] if len(sys.argv) >=4 else "turbo"
    subtitle_lang = sys.argv[4] if len(sys.argv) >=5 else "de"
    
    generate_subtitles(audio_path, output_dir, model, subtitle_lang)