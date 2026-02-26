#!/usr/bin/env python3
# generate_image.py
import os
import sys
import subprocess
from typing import Optional

def generate_thumbnail(
    video_path: str,
    output_dir: str,
    thumbnail_size: str = "320:180",
    quality: int = 2,
    is_16grid: bool = True
) -> Optional[str]:
    """
    生成视频缩略图（支持单帧/16宫格两种模式）
    :param video_path: 视频文件完整路径
    :param output_dir: 缩略图输出目录
    :param thumbnail_size: 单个缩略图分辨率，格式"宽:高"（如320:180）
    :param quality: 图片质量（1-31，1最高，31最低）
    :param is_16grid: 是否生成16宫格缩略图（False=单帧，True=16宫格）
    :return: 生成的缩略图路径，失败返回None
    """
    # 1. 基础校验
    if not os.path.exists(video_path):
        print(f"❌ 错误：视频文件不存在 -> {video_path}")
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. 检查FFmpeg/ffprobe依赖
    def check_tool(tool_name: str) -> bool:
        try:
            subprocess.run([tool_name, "-version"], capture_output=True, check=True, text=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ 错误：未找到{tool_name}，请安装FFmpeg并配置到环境变量")
            return False
    
    if not check_tool("ffmpeg") or not check_tool("ffprobe"):
        return None
    
    # 3. 生成缩略图文件名
    video_name = os.path.basename(video_path)
    name_no_ext = os.path.splitext(video_name)[0]
    suffix = "_16grid" if is_16grid else "_thumb"
    thumb_path = os.path.join(output_dir, f"{name_no_ext}{suffix}.jpg")
    
    try:
        # 4. 获取视频时长（用于计算采样间隔）
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        duration_output = subprocess.check_output(duration_cmd, text=True, stderr=subprocess.STDOUT)
        video_duration = float(duration_output.strip())
        
        if video_duration <= 0:
            print(f"❌ 错误：视频时长异常 -> {video_path}")
            return None
        
        # 5. 构建FFmpeg命令
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", video_path, "-loglevel", "error"]
        
        if is_16grid:
            # 5.1 16宫格模式（均匀采样16帧拼接）
            interval = video_duration / 16  # 16帧的采样间隔
            ffmpeg_cmd.extend([
                "-vf", f"fps=1/{interval},scale={thumbnail_size},tile=4x4",
                "-frames:v", "1",  # 只输出1张拼接图
                "-q:v", str(quality),
                thumb_path
            ])
        else:
            # 5.2 单帧模式（取视频中间帧）
            mid_time = video_duration / 2
            ffmpeg_cmd.extend([
                "-ss", str(mid_time),  # 跳转到视频中间
                "-vframes", "1",       # 只取1帧
                "-s", thumbnail_size,  # 分辨率
                "-q:v", str(quality),  # 质量
                thumb_path
            ])
        
        # 6. 执行命令
        subprocess.run(ffmpeg_cmd, check=True)
        
        if os.path.exists(thumb_path):
            print(f"✅ 缩略图生成完成：{thumb_path}")
            return thumb_path
        else:
            print(f"❌ 错误：缩略图文件未生成 -> {thumb_path}")
            return None
    
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg执行失败 {video_name}：{e.stderr[:200] if e.stderr else '未知错误'}")
        return None
    except Exception as e:
        print(f"❌ 缩略图生成异常 {video_name}：{str(e)[:200]}")
        return None

# 单独运行时的命令行逻辑
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("使用方法：")
        print("  单帧缩略图：python generate_image.py <视频文件路径> <输出目录> [分辨率] [质量]")
        print("  16宫格缩略图：python generate_image.py <视频文件路径> <输出目录> [分辨率] [质量] --16grid")
        print("示例：")
        print("  python generate_image.py ./test.mp4 ./thumbnails 320:180 2")
        print("  python generate_image.py ./test.mp4 ./thumbnails 480:270 1 --16grid")
        sys.exit(1)
    
    # 解析命令行参数
    video_path = sys.argv[1]
    output_dir = sys.argv[2]
    thumbnail_size = sys.argv[3] if len(sys.argv) >=4 else "320:180"
    quality = int(sys.argv[4]) if len(sys.argv) >=5 else 2
    is_16grid = True if "--16grid" in sys.argv else True
    
    # 调用生成函数
    generate_thumbnail(
        video_path=video_path,
        output_dir=output_dir,
        thumbnail_size=thumbnail_size,
        quality=quality,
        is_16grid=is_16grid
    )