import subprocess
import os
import shutil
from typing import Optional

from steps.base_step import BaseStep
from steps.context import TaskContext


class GenerateSubtitlesStep(BaseStep):
    @property
    def step_name(self):
        return "字幕生成"

    def execute(self, context: TaskContext) -> bool:
        task = context.task

        # 如果check_exist为True，检查最终字幕产物是否已存在
        if task.subtitle and task.subtitle.check_exist:
            existing_srt = self._find_existing_subtitle(context.final_srt_path)
            if existing_srt:
                print(f"✅ 检测到已存在的字幕文件：{existing_srt}")
                context.srt_path = existing_srt
                return True

        # 如果已有字幕路径（从 ExtractSubtitlesStep），直接使用
        if context.srt_path:
            print(f"✅ 使用已提取的字幕：{context.srt_path}")
            return True

        # 获取需要生成字幕的片段
        srt_segments = [seg for seg in context.trim_segments if seg.srt]
        
        if not srt_segments:
            # 没有标记为srt=True的片段，使用完整视频生成字幕
            print("⚠️ 未找到标记为srt=True的片段，将使用完整音频生成字幕")
            srt_path = generate_subtitles(
                audio_path=context.audio_path,
                output_dir=context.subtitle_dir,
                model='turbo',
                subtitle_lang=task.subtitle.subtitle_lang if task.subtitle else "de"
            )
            if srt_path:
                context.srt_path = srt_path
            else:
                print("⚠️ 字幕生成失败或文件无效，将跳过字幕烧录。")
                context.srt_path = ""
            return True

        # 为每个标记为srt=True的片段生成独立的字幕文件
        video_name = os.path.basename(task.video_path)
        name_no_ext = os.path.splitext(video_name)[0]
        
        generated_srt_paths = []
        srt_segment_indices = [i for i, seg in enumerate(context.trim_segments) if seg.srt]
        
        for i, (seg_idx, segment) in enumerate(zip(srt_segment_indices, srt_segments)):
            adjusted_start_time = segment.start_time - segment.offset
            adjusted_end_time = segment.end_time - segment.offset
            srt_path = generate_subtitles_for_segment(
                video_path=task.video_path,
                audio_path=context.audio_path,
                output_dir=context.subtitle_dir,
                start_time=adjusted_start_time,
                end_time=adjusted_end_time,
                segment_index=i,
                video_name_no_ext=name_no_ext,
                model='turbo',
                subtitle_lang=task.subtitle.subtitle_lang if task.subtitle else "de"
            )
            if srt_path:
                generated_srt_paths.append(srt_path)
                # 将字幕路径存储到对应的TrimSegment中
                context.trim_segments[seg_idx].srt_path = srt_path

        if generated_srt_paths:
            # 设置第一个生成的字幕路径到context
            context.srt_path = generated_srt_paths[0]
            print(f"✅ 共生成 {len(generated_srt_paths)} 个字幕文件")
            for idx, path in enumerate(generated_srt_paths):
                print(f"   - 片段 {idx}: {path}")
        else:
            print("⚠️ 字幕生成失败或文件无效，将跳过字幕烧录。")
            context.srt_path = ""
            
        return True

    def _find_existing_subtitle(self, final_srt_path: str) -> Optional[str]:
        """
        检查最终字幕产物（canonical路径）是否已存在

        :param final_srt_path: 最终字幕产物路径（{subtitle_dir}/{视频名}.srt）
        :return: 存在则返回该路径，否则返回None
        """
        if os.path.isfile(final_srt_path):
            return final_srt_path
        return None


def extract_audio_segment(video_path: str, audio_path: str, output_dir: str, 
                        start_time: float, end_time: float, segment_index: int) -> Optional[str]:
    """
    从完整音频文件或视频文件中提取音频片段
    
    :param video_path: 视频文件路径
    :param audio_path: 完整音频文件路径
    :param output_dir: 输出目录
    :param start_time: 开始时间（秒）
    :param end_time: 结束时间（秒）
    :param segment_index: 片段索引
    :return: 提取的音频片段路径，失败返回None
    """
    video_name = os.path.basename(video_path)
    name_no_ext = os.path.splitext(video_name)[0]
    ext = os.path.splitext(audio_path)[1] if audio_path else ".aac"
    
    temp_audio_path = os.path.join(output_dir, f"{name_no_ext}_seg{segment_index}_temp{ext}")
    
    try:
        duration = end_time - start_time
        
        if audio_path and os.path.exists(audio_path):
            # 从完整音频中提取
            command = [
                "ffmpeg",
                "-ss", str(start_time),
                "-i", audio_path,
                "-t", str(duration),
                "-acodec", "copy",
                "-y",
                temp_audio_path
            ]
        else:
            # 从视频中直接提取音频片段
            command = [
                "ffmpeg",
                "-ss", str(start_time),
                "-i", video_path,
                "-t", str(duration),
                "-vn",
                "-acodec", "aac",
                "-y",
                temp_audio_path
            ]
        
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ 提取音频片段 {segment_index} 完成: {temp_audio_path}")
        return temp_audio_path
    except subprocess.CalledProcessError as e:
        print(f"❌ 提取音频片段 {segment_index} 失败: {e.stderr}")
        return None


def generate_subtitles_for_segment(video_path: str, audio_path: str, output_dir: str,
                                 start_time: float, end_time: float, segment_index: int,
                                 video_name_no_ext: str, model: str = "turbo", 
                                 subtitle_lang: str = "de") -> Optional[str]:
    """
    为单个片段生成字幕
    
    :param video_path: 视频文件路径
    :param audio_path: 完整音频文件路径
    :param output_dir: 输出目录
    :param start_time: 开始时间（秒）
    :param end_time: 结束时间（秒）
    :param segment_index: 片段索引
    :param video_name_no_ext: 视频文件名（不含扩展名）
    :param model: Whisper模型
    :param subtitle_lang: 字幕语言
    :return: 生成的字幕文件路径，失败返回None
    """
    # 1. 提取音频片段
    temp_audio_path = extract_audio_segment(
        video_path, audio_path, output_dir, 
        start_time, end_time, segment_index
    )
    
    if not temp_audio_path:
        return None
    
    try:
        # 2. 重用generate_subtitles函数生成字幕
        temp_srt_path = generate_subtitles(
            audio_path=temp_audio_path,
            output_dir=output_dir,
            model=model,
            subtitle_lang=subtitle_lang
        )
        
        if not temp_srt_path:
            print(f"❌ 片段 {segment_index} 字幕生成失败")
            return None
        
        # 3. 重命名为包含时间范围标记的文件名
        srt_name = f"{video_name_no_ext}_srt{segment_index}_[{int(start_time)}-{int(end_time)}].srt"
        srt_path = os.path.join(output_dir, srt_name)
        
        if temp_srt_path != srt_path:
            shutil.move(temp_srt_path, srt_path)
        
        print(f"✅ 片段 {segment_index} 字幕生成完成: {srt_path}")
        return srt_path
    finally:
        # 4. 删除临时音频文件
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                print(f"🧹 删除临时音频文件: {temp_audio_path}")
            except Exception as e:
                print(f"⚠️ 删除临时音频文件失败: {e}")


def generate_subtitles(audio_path: str, output_dir: str, model: str = "turbo", subtitle_lang: str = "de") -> Optional[str]:
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
    
    print(f"开始生成字幕: {audio_name} (语言：{subtitle_lang})")
    print(f"执行命令: {' '.join(command)}")
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        
        if os.path.exists(srt_path):
            print(f"✅ 字幕生成完成: {srt_path}")
            return srt_path
        else:
            print(f"❌ 未找到生成的字幕文件")
            return None
    except FileNotFoundError:
        print("❌ Whisper 未安装或不在 PATH 中。请安装 OpenAI Whisper：pip install openai-whisper")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ 字幕生成失败: {e.stderr}")
        return None
