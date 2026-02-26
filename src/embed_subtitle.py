#!/usr/bin/env python3
# embed_subtitle.py
import os
import subprocess

def embed_subtitle_to_video(
    thumbnail_path: str, 
    srt_path: str, 
    audio_path: str,
    output_dir: str
) -> str | None:
    """
    将单张图片、AAC音频和SRT字幕合成为一个视频，字幕烧录入画面。
    """
    # 1. 检查输入文件是否存在
    for path, name in [(thumbnail_path, "图片"), (srt_path, "字幕"), (audio_path, "音频")]:
        if not os.path.exists(path):
            print(f"❌ 错误：{name}文件不存在 -> {path}")
            return None
    
    # 2. 准备输出路径 (统一正斜杠，防止路径拼接报错)
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_video_path = os.path.join(output_dir, f"{base_name}.mp4").replace('\\', '/')
    
    if os.path.exists(output_video_path):
        print(f"⚠️ 视频已存在，跳过：{output_video_path}")
        return None

    # 3. 处理字幕路径 (关键修复：转义Windows盘符冒号，防止FFmpeg解析失败)
    safe_srt_path = srt_path.replace('\\', '/').replace(':', r'\:')
    
    # 4. 构建 FFmpeg 命令
    command = [
        'ffmpeg', '-y',
        
        # --- 输入 1: 图片流 ---
        '-loop', '1',               # 循环播放这张图片
        '-framerate', '30',         # 设置视频帧率为30，保证画面流畅和字幕渲染正常
        '-i', thumbnail_path,
        
        # --- 输入 2: 音频流 ---
        '-i', audio_path,
        
        # --- 滤镜: 烧录字幕 ---
        '-vf', f"subtitles='{safe_srt_path}':force_style='FontName=SimHei'",
        
        # --- 视频编码设置 ---
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-tune', 'stillimage',      # 【新增优化】专门针对静态图片的优化，能减小文件体积
        '-pix_fmt', 'yuv420p',      # 【新增优化】色彩空间格式。如果不加，某些浏览器和手机播放会黑屏
        
        # --- 音频编码设置 ---
        '-c:a', 'copy',             # 直接拷贝原音频流，无损且快速
        
        # --- 截断设置 ---
        '-shortest',                # 因为图片是无限循环的，所以以音频的长度为准结束合成
        
        output_video_path
    ]
    
    print(f"📽️ 开始合成：{base_name}.mp4")
    try:
        # capture_output=True 可以截获输出，如果报错可以通过 e.stderr 打印具体原因
        subprocess.run(command, check=True, capture_output=True, text=True)
        if os.path.exists(output_video_path):
            print(f"✅ 成功生成视频：{output_video_path}")
            return output_video_path
        else:
            print("❌ 错误：命令执行成功但未找到输出文件。")
            return None
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 报错了：\n{e.stderr}")
        return None

if __name__ == "__main__":
    # 测试路径
    thumb = r'D:\waner\4_ani\programs\demo_video\1\12.jpg'
    srt   = r'D:\waner\4_ani\programs\demo_video\1\12.srt'
    audio = r'D:\waner\4_ani\programs\demo_video\1\12.aac'
    out_dir = r'D:\waner\4_ani\programs\demo_video\1'
    
    embed_subtitle_to_video(thumb, srt, audio, out_dir)