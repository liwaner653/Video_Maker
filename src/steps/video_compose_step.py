#!/usr/bin/env python3
# embed_subtitle.py
import os
import subprocess

from steps.base_step import BaseStep
from steps.context import TaskContext

class VideoComposeStep(BaseStep):
    @property
    def step_name(self): return "视频合成"

    def execute(self, context: TaskContext) -> bool:
        final_video_path = embed_subtitle_to_video(
            thumbnail_path=context.thumb_path,
            srt_path=context.srt_path, # 可能为空
            audio_path=context.audio_path,
            output_dir=context.final_video_dir,
        )
        if final_video_path:
            context.final_video_path = final_video_path
            return True
        context.error_msg = "视频合成失败"
        return False
        
def embed_subtitle_to_video(
    thumbnail_path: str, 
    srt_path: str, 
    audio_path: str,
    output_dir: str
) -> str | None:
    # 1. 检查必要文件（图片、音频必须存在）
    for path, name in [(thumbnail_path, "图片"), (audio_path, "音频")]:
        if not os.path.exists(path):
            print(f"❌ 错误：{name}文件不存在 -> {path}")
            return None
            
    # 【新增代码】判断是否包含有效字幕
    has_srt = srt_path and os.path.exists(srt_path)
    if not has_srt:
        print("⚠️ 未提供字幕或字幕不存在，将仅合成音频与图片。")
    
    # 2. 准备输出路径 (统一正斜杠，防止路径拼接报错)
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_video_path = os.path.join(output_dir, f"{base_name}.mp4").replace('\\', '/')
    
    # 3. 处理字幕路径 (关键修复：转义Windows盘符冒号，防止FFmpeg解析失败)
    safe_srt_path = srt_path.replace('\\', '/').replace(':', r'\:').replace("'", "\\'")
    
    # 4. 构建 FFmpeg 命令
    command = [
        'ffmpeg', '-y',
        '-loop', '1',
        '-framerate', '30',
        '-i', thumbnail_path,
        '-i', audio_path
    ]
    
    # 【新增代码】按需追加字幕滤镜
    if has_srt:
        safe_srt_path = srt_path.replace('\\', '/').replace(':', r'\:').replace("'", "\\'")
        command.extend(['-vf', f"subtitles='{safe_srt_path}':force_style='FontName=SimHei',FontSize=16"])
        
    # 编码设置
    command.extend([
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-tune', 'stillimage',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'copy',
        '-shortest',
        output_video_path
    ])
#    # 4. 构建 FFmpeg 命令
#    command = [
#        'ffmpeg', '-y',
#        
#        # --- 输入 1: 图片流 ---
#        '-loop', '1',               # 循环播放这张图片
#        '-framerate', '30',         # 设置视频帧率为30，保证画面流畅和字幕渲染正常
#        '-i', thumbnail_path,
#        
#        # --- 输入 2: 音频流 ---
#        '-i', audio_path,
#        
#        # --- 滤镜: 烧录字幕 ---
#        '-vf', f"subtitles='{safe_srt_path}':force_style='FontName=SimHei'",
#        
#        # --- 视频编码设置 ---
#        '-c:v', 'libx264',
#        '-preset', 'medium',
#        '-crf', '23',
#        '-tune', 'stillimage',      # 【新增优化】专门针对静态图片的优化，能减小文件体积
#        '-pix_fmt', 'yuv420p',      # 【新增优化】色彩空间格式。如果不加，某些浏览器和手机播放会黑屏
#        
#        # --- 音频编码设置 ---
#        '-c:a', 'copy',             # 直接拷贝原音频流，无损且快速
#        
#        # --- 截断设置 ---
#        '-shortest',                # 因为图片是无限循环的，所以以音频的长度为准结束合成
#        
#        output_video_path
#    ]
    
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

def batch_embed_subtitles(
    image_folder: str,
    srt_folder: str,
    audio_folder: str,
    output_dir: str
) -> None:
    """
    批量合成视频。
    遍历 image_folder 中的文件，寻找 srt_folder 和 audio_folder 中同名的文件进行合成。
    
    参数:
        image_folder: 图片文件夹路径
        srt_folder: SRT字幕文件夹路径
        audio_folder: 音频文件夹路径
        output_dir: 视频输出文件夹路径
    """
    # 1. 检查文件夹是否存在
    for path, name in [(image_folder, "图片文件夹"), (srt_folder, "字幕文件夹"), (audio_folder, "音频文件夹")]:
        if not os.path.isdir(path):
            print(f"❌ 错误：{name}不存在 -> {path}")
            return

    # 2. 获取所有待处理的文件名基础名 (不带扩展名)
    # 这里假设以图片文件夹为基准进行遍历，您也可以改为遍历音频文件夹
    supported_image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
    
    # 收集所有有效的基准文件名
    base_names = []
    for filename in os.listdir(image_folder):
        if filename.lower().endswith(supported_image_exts):
            base_name = os.path.splitext(filename)[0]
            base_names.append(base_name)

    if not base_names:
        print(f"⚠️ 在图片文件夹中未找到支持的图片文件 ({supported_image_exts})")
        return

    print(f"📂 找到 {len(base_names)} 个待处理的任务。开始批量合成...")

    # 3. 逐一处理
    success_count = 0
    skip_count = 0
    fail_count = 0

    for base_name in base_names:
        # 构建三个输入文件的完整路径
        # 注意：这里需要确定具体的扩展名。
        # 策略：在对应文件夹中查找以 base_name 开头的文件
        
        img_path = None
        srt_path = None
        audio_path = None

        # 查找图片
        for f in os.listdir(image_folder):
            if f.startswith(base_name) and f.lower().endswith(supported_image_exts):
                img_path = os.path.join(image_folder, f)
                break
        
        # 查找 SRT
        for f in os.listdir(srt_folder):
            if f.startswith(base_name) and f.lower().endswith('.srt'):
                srt_path = os.path.join(srt_folder, f)
                break
                
        # 查找音频 (支持常见音频格式)
        supported_audio_exts = ('.aac', '.mp3', '.wav', '.m4a', '.flac')
        for f in os.listdir(audio_folder):
            if f.startswith(base_name) and f.lower().endswith(supported_audio_exts):
                audio_path = os.path.join(audio_folder, f)
                break

        # 验证文件是否都找齐了
        if not img_path or not srt_path or not audio_path:
            missing = []
            if not img_path: missing.append("图片")
            if not srt_path: missing.append("SRT字幕")
            if not audio_path: missing.append("音频")
            print(f"⚠️ 跳过 '{base_name}': 缺失文件 [{', '.join(missing)}]")
            skip_count += 1
            continue

        # 调用单文件处理函数
        result = embed_subtitle_to_video(img_path, srt_path, audio_path, output_dir)
        
        if result:
            success_count += 1
        else:
            # embed_subtitle_to_video 内部已经打印了错误或跳过信息
            # 如果是因为文件已存在跳过的，通常返回None，这里简单统计为skip或fail均可，
            # 根据原函数逻辑，已存在返回None，报错也返回None。
            # 为了区分，我们可以检查输出文件是否存在来反推，或者简单归类。
            # 这里暂且将非成功生成的都视为未新增成功（包含已存在和失败）
            if os.path.exists(os.path.join(output_dir, f"{base_name}.mp4")):
                 skip_count += 1 # 实际上是已存在
            else:
                 fail_count += 1

    print("-" * 30)
    print(f"🎉 批量处理完成！")
    print(f"✅ 成功生成: {success_count}")
    print(f"⚠️ 跳过/已存在: {skip_count}")
    print(f"❌ 失败: {fail_count}")

# 使用示例（您可以取消注释并修改路径来测试）
if __name__ == "__main__":
    # 原有的单文件测试
    # thumb = r'D:\waner\4_ani\programs\demo_video\1\12.jpg'
    # srt   = r'D:\waner\4_ani\programs\demo_video\1\12.srt'
    # audio = r'D:\waner\4_ani\programs\demo_video\1\12.aac'
    # out_dir = r'D:\waner\4_ani\programs\demo_video\1'
    # embed_subtitle_to_video(thumb, srt, audio, out_dir)

    # 新增的批量测试
    # img_dir = r'D:\waner\4_ani\frieren multi\de\thumbnails de'      # 图片文件夹
    # srt_dir = r'D:\waner\4_ani\frieren multi\de\subtitles de'         # SRT文件夹
    # audio_dir = r'D:\waner\4_ani\frieren multi\de\audio de'     # 音频文件夹
    # out_root = r'D:\waner\4_ani\frieren multi\de\final_videos de'     # 输出文件夹

    img_dir = r'D:\waner\4_ani\frieren multi\fr\thumbnails'      # 图片文件夹
    srt_dir = r'D:\waner\4_ani\frieren multi\fr\frieren s01 fr'         # SRT文件夹
    audio_dir = r'D:\waner\4_ani\frieren multi\fr\audio'     # 音频文件夹
    out_root = r'D:\waner\4_ani\frieren multi\fr\fr final video'     # 输出文件夹
    
    batch_embed_subtitles(img_dir, srt_dir, audio_dir, out_root)
    pass
