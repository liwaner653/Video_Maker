#!/usr/bin/env python3
# generate_image.py
import os
import sys
import subprocess
from typing import Optional

from steps.base_step import BaseStep
from steps.context import TaskContext

class ThumbnailStep(BaseStep):
    @property
    def step_name(self): return "缩略图生成"

    def execute(self, context: TaskContext) -> bool:
        task = context.task
        if task.thumbnail.pic_path:
            context.thumb_path = task.thumbnail.pic_path
            return True
        else:
            # 如果check_exist为True，检查输出目录中是否存在同名缩略图文件
            if task.thumbnail.check_exist:
                existing_thumb = self._find_existing_thumbnail(task.video_path, context.thumb_dir)
                if existing_thumb:
                    print(f"✅ 检测到已存在的缩略图文件：{existing_thumb}")
                    context.thumb_path = existing_thumb
                    return True
            
            # 获取所有标记为需要生成缩略图的片段
            thumbnail_segments = [seg for seg in context.trim_segments if seg.thumbnail]
            
            if not thumbnail_segments:
                # 如果没有标记为thumbnail=True的片段，使用完整视频生成缩略图
                thumb_path = generate_thumbnail(
                    video_path=task.video_path,
                    output_dir=context.thumb_dir,
                    thumbnail_size="320:180",
                    quality=2,
                    blur_sigma=task.thumbnail.blur_sigma,
                    start_time=0.0,
                    end_time=0.0
                )
                if thumb_path:
                    context.thumb_path = thumb_path
                    return True
                context.error_msg = "缩略图生成失败"
                return False
            
            # 计算合并后的时间范围：第一个thumbnail片段的开始时间到最后一个thumbnail片段的结束时间
            merged_start_time = thumbnail_segments[0].start_time
            merged_end_time = thumbnail_segments[-1].end_time
            
            # 在合并的时间范围内生成单个缩略图
            thumb_path = generate_thumbnail(
                video_path=task.video_path,
                output_dir=context.thumb_dir,
                thumbnail_size="320:180",
                quality=2,
                blur_sigma=task.thumbnail.blur_sigma,
                trim_start_time=merged_start_time,
                trim_end_time=merged_end_time
            )
            if thumb_path:
                context.thumb_path = thumb_path
                return True
            context.error_msg = "缩略图生成失败"
            return False
    
    def _find_existing_thumbnail(self, video_path: str, output_dir: str) -> Optional[str]:
        """
        查找输出目录中是否存在与视频文件同名的缩略图文件
        会检查_16grid.jpg和_thumb.jpg两种格式
        
        :param video_path: 视频文件路径
        :param output_dir: 输出目录
        :return: 存在则返回完整路径，否则返回None
        """
        if not os.path.exists(output_dir):
            return None
        
        video_name = os.path.basename(video_path)
        name_no_ext = os.path.splitext(video_name)[0]
        
        # 尝试_16grid.jpg格式（默认）
        thumb_16grid = os.path.join(output_dir, name_no_ext + "_16grid.jpg")
        if os.path.isfile(thumb_16grid):
            return thumb_16grid
        
        # 尝试_thumb.jpg格式（单帧）
        thumb_single = os.path.join(output_dir, name_no_ext + "_thumb.jpg")
        if os.path.isfile(thumb_single):
            return thumb_single
        
        return None

def generate_thumbnail(
    video_path: str,
    output_dir: str,
    thumbnail_size: str = "320:180",
    quality: int = 2,
    is_16grid: bool = True,
    blur_sigma: float = 0.0,  # 【新增代码 1】增加模糊度参数，默认0(不模糊)
    trim_start_time: float = 0.0,  # 【新增代码】修剪范围开始时间（秒）
    trim_end_time: float = 0.0     # 【新增代码】修剪范围结束时间（秒），0表示到末尾
) -> Optional[str]:
    """
    生成视频缩略图（支持单帧/16宫格两种模式）
    :param video_path: 视频文件完整路径
    :param output_dir: 缩略图输出目录
    :param thumbnail_size: 单个缩略图分辨率，格式"宽:高"（如320:180）
    :param quality: 图片质量（1-31，1最高，31最低）
    :param is_16grid: 是否生成16宫格缩略图（False=单帧，True=16宫格）
    :param blur_sigma: 模糊度（0=不模糊）
    :param trim_start_time: 修剪范围开始时间（秒）
    :param trim_end_time: 修剪范围结束时间（秒），0表示到末尾
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
        
        # 【新增逻辑】确定有效的修剪范围
        effective_start = trim_start_time if trim_start_time > 0 else 0.0
        effective_end = trim_end_time if trim_end_time > 0 else video_duration
        effective_duration = effective_end - effective_start
        
        if effective_duration <= 0:
            print(f"❌ 错误：修剪范围无效 -> 开始: {effective_start:.2f}s, 结束: {effective_end:.2f}s")
            return None
        
        print(f"📐 缩略图生成范围：开始={effective_start:.2f}s, 结束={effective_end:.2f}s, 时长={effective_duration:.2f}s")
        
        # 5. 构建FFmpeg命令
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", video_path, "-loglevel", "error"]
        
        if is_16grid:
            interval = effective_duration / 16
            # 【新增代码 2】按需拼接模糊滤镜
            vf_str = f"fps=1/{interval},scale={thumbnail_size},tile=4x4"
            if blur_sigma > 0:
                vf_str += f",gblur=sigma={blur_sigma}"
            
            # 【新增逻辑】添加修剪范围限制
            if effective_start > 0:
                ffmpeg_cmd.extend(["-ss", str(effective_start)])
            if effective_duration < video_duration:
                ffmpeg_cmd.extend(["-t", str(effective_duration)])
                
            ffmpeg_cmd.extend([
                "-vf", vf_str,
                "-frames:v", "1",
                "-q:v", str(quality),
                thumb_path
            ])
        else:
            mid_time = effective_start + effective_duration / 2
            # 【新增代码 3】按需拼接模糊滤镜
            vf_str = f"scale={thumbnail_size}"
            if blur_sigma > 0:
                vf_str += f",gblur=sigma={blur_sigma}"
                
            ffmpeg_cmd.extend([
                "-ss", str(mid_time),
                "-vframes", "1",
                "-vf", vf_str, # 将原来的 -s 替换为统一的 -vf 处理
                "-q:v", str(quality),
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