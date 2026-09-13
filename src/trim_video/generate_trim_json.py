import json
import os
from typing import Optional, List

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'steps'))
from util import get_video_duration
from config import VIDEO_EXTENSIONS


def generate_trim_json(
    video_path: str,
    output_path: str,
    segments: List[dict],
    audio_language: str = "",
    audio_stream_index: int = -1,
    audio_enabled: bool = True,
    subtitle_language: str = "",
    subtitle_stream_index: int = -1,
    subtitle_burn_in: bool = True,
    subtitle_enabled: bool = True,
    output_dir: str = "",
    output_format: str = "mp4",
    crf: int = 23,
    preset: str = "medium",
    subtitle_target_titles: list = None
) -> bool:
    """
    生成视频剪辑任务的JSON配置文件
    
    :param video_path: 视频文件完整路径
    :param output_path: JSON配置文件输出路径
    :param segments: 剪辑片段列表，每个片段包含 start_time, end_time, name(可选)
    :param audio_language: 音轨语言
    :param audio_stream_index: 指定音轨索引
    :param audio_enabled: 是否启用音频
    :param subtitle_language: 字幕语言
    :param subtitle_stream_index: 指定字幕轨道索引
    :param subtitle_burn_in: 是否烧入字幕
    :param subtitle_enabled: 是否启用字幕
    :param output_dir: 输出目录
    :param output_format: 输出格式
    :param crf: 视频质量CRF值
    :param preset: 编码预设
    :param subtitle_target_titles: 字幕标题关键字过滤列表，默认 ['english']
    :return: 是否成功
    """
    if subtitle_target_titles is None:
        subtitle_target_titles = ['english']
    config = {
        "video_path": video_path,
        "output_dir": output_dir,
        "segments": segments,
        "audio": {
            "language": audio_language,
            "audio_stream_index": audio_stream_index,
            "enabled": audio_enabled
        },
        "subtitle": {
            "language": subtitle_language,
            "subtitle_stream_index": subtitle_stream_index,
            "burn_in": subtitle_burn_in,
            "enabled": subtitle_enabled,
            "target_titles": subtitle_target_titles
        },
        "output_format": output_format,
        "crf": crf,
        "preset": preset
    }
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"✅ JSON配置文件已生成: {output_path}")
        return True
    except Exception as e:
        print(f"❌ 生成JSON失败: {e}")
        return False


def generate_batch_trim_json(
    tasks: List[dict],
    output_path: str
) -> bool:
    """
    生成批量视频剪辑任务的JSON配置文件
    
    :param tasks: 任务列表，每个任务包含视频剪辑所需的配置
    :param output_path: JSON配置文件输出路径
    :return: 是否成功
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=4)
        print(f"✅ 批量JSON配置文件已生成: {output_path}")
        return True
    except Exception as e:
        print(f"❌ 生成JSON失败: {e}")
        return False


def interactive_generate_json(
    video_path: str = None,
    output_dir: str = "",
    output_format: str = "mp4",
    audio_language: str = "en",
    audio_stream_index: int = -1,
    audio_enabled: bool = True,
    subtitle_language: str = "en",
    subtitle_stream_index: int = -1,
    subtitle_burn_in: bool = True,
    subtitle_enabled: bool = True,
    start_time: float = 0.0,
    end_time: float = None,
    name: str = "",
    crf: int = 23,
    preset: str = "medium",
    subtitle_target_titles: list = None
):
    """
    交互式生成JSON配置文件，video_path 为视频文件夹路径，遍历其中所有视频文件，
    每个视频文件生成一个 JSON 对象，除 video_path 外其余参数均相同。
    
    :param video_path: 视频文件夹路径，为 None 时交互式输入
    :param output_dir: 输出目录，为空时使用视频文件夹
    :param output_format: 输出格式，默认 mp4
    :param audio_language: 音轨语言，默认 en
    :param audio_stream_index: 指定音轨索引，默认 -1（自动检测）
    :param audio_enabled: 是否启用音频，默认 True
    :param subtitle_language: 字幕语言，默认 en
    :param subtitle_stream_index: 指定字幕轨道索引，默认 -1（自动检测）
    :param subtitle_burn_in: 是否烧入字幕，默认 True
    :param subtitle_enabled: 是否启用字幕，默认 True
    :param start_time: 片段开始时间（秒），默认 0.0（视频开始）
    :param end_time: 片段结束时间（秒），为 None 时使用各视频总时长
    :param name: 片段名称（可选）
    :param crf: 视频质量CRF值，默认 23
    :param preset: 编码预设，默认 medium
    :param subtitle_target_titles: 字幕标题关键字过滤列表，默认 ['english']
    """
    print("=== 🎬 视频剪辑JSON配置生成器 ===")
    
    # 仅 video_path（文件夹）交互式输入
    if video_path is None:
        video_path = input("请输入视频文件夹路径: ").strip().strip('"\'')
        while not os.path.isdir(video_path):
            print(f"❌ 文件夹不存在: {video_path}")
            video_path = input("请重新输入视频文件夹路径: ").strip().strip('"\'')
    else:
        video_path = video_path.strip().strip('"\'')
        if not os.path.isdir(video_path):
            raise FileNotFoundError(f"视频文件夹不存在: {video_path}")
    
    # 输出目录默认使用视频文件夹
    if not output_dir:
        output_dir = video_path
    
    if subtitle_target_titles is None:
        subtitle_target_titles = ['english']
    
    # 遍历文件夹中的视频文件，每个视频生成一个 JSON 对象
    json_data = []
    for filename in sorted(os.listdir(video_path)):
        if filename.lower().endswith(VIDEO_EXTENSIONS):
            video_file = os.path.abspath(os.path.join(video_path, filename))
            
            # end_time 为 None 时取该视频总时长
            seg_end_time = end_time if end_time is not None else get_video_duration(video_file)
            
            task_data = {
                "video_path": video_file,
                "output_dir": output_dir,
                "segments": [{
                    "start_time": start_time,
                    "end_time": seg_end_time,
                    "name": name
                }],
                "audio": {
                    "language": audio_language,
                    "audio_stream_index": audio_stream_index,
                    "enabled": audio_enabled
                },
                "subtitle": {
                    "language": subtitle_language,
                    "subtitle_stream_index": subtitle_stream_index,
                    "burn_in": subtitle_burn_in,
                    "enabled": subtitle_enabled,
                    "target_titles": subtitle_target_titles
                },
                "output_format": output_format,
                "crf": crf,
                "preset": preset
            }
            json_data.append(task_data)
            print(f"   📹 {filename}")
    
    if not json_data:
        raise ValueError(f"文件夹 {video_path} 中未找到视频文件")
    
    # JSON 文件放在视频文件夹
    json_path = os.path.join(output_dir, "trim.json")
    generate_batch_trim_json(json_data, json_path)
    
    print(f"\n🎉 配置完成！共 {len(json_data)} 个视频任务，运行以下命令开始剪辑：")
    print(f"python -m src.trim_video.video_main {json_path}")
    return json_path


if __name__ == "__main__":
    interactive_generate_json()