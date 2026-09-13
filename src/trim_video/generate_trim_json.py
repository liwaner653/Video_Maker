import json
import os
from typing import Optional, List


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


def interactive_generate_json():
    """交互式生成JSON配置文件"""
    print("=== 🎬 视频剪辑JSON配置生成器 ===")
    
    video_path = input("请输入视频文件路径: ").strip().strip('"\'')
    while not os.path.exists(video_path):
        print(f"❌ 文件不存在: {video_path}")
        video_path = input("请重新输入视频文件路径: ").strip().strip('"\'')
    
    output_dir = input("请输入输出目录（回车使用视频所在目录）: ").strip().strip('"\'')
    if not output_dir:
        output_dir = os.path.dirname(video_path)
    
    output_format = input("请输入输出格式（默认mp4）: ").strip() or "mp4"
    
    print("\n--- 音频配置 ---")
    audio_enabled = input("是否保留音频？(y/n，默认y): ").strip().lower() != 'n'
    audio_lang = ""
    audio_idx = -1
    if audio_enabled:
        audio_lang = input("请输入音轨语言（如 en, zh, ja，回车自动检测）: ").strip()
        audio_idx_input = input("请输入音轨索引（回车自动检测）: ").strip()
        audio_idx = int(audio_idx_input) if audio_idx_input else -1
    
    print("\n--- 字幕配置 ---")
    subtitle_enabled = input("是否启用字幕？(y/n，默认y): ").strip().lower() != 'n'
    subtitle_lang = ""
    subtitle_idx = -1
    subtitle_burn = True
    if subtitle_enabled:
        subtitle_lang = input("请输入字幕语言（如 en, zh, ja，回车自动检测）: ").strip()
        subtitle_idx_input = input("请输入字幕轨道索引（回车自动检测）: ").strip()
        subtitle_idx = int(subtitle_idx_input) if subtitle_idx_input else -1
        subtitle_burn = input("是否将字幕烧入视频？(y/n，默认y): ").strip().lower() != 'n'
    
    print("\n--- 剪辑片段配置 ---")
    segments = []
    while True:
        print(f"\n片段 {len(segments) + 1}")
        start_time = float(input("开始时间（秒）: ").strip())
        end_time = float(input("结束时间（秒）: ").strip())
        name = input("片段名称（可选）: ").strip()
        
        segments.append({
            "start_time": start_time,
            "end_time": end_time,
            "name": name
        })
        
        add_more = input("是否添加更多片段？(y/n，默认n): ").strip().lower()
        if add_more != 'y':
            break
    
    json_dir = os.path.join(output_dir, "config")
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    json_path = os.path.join(json_dir, f"{video_basename}_trim.json")
    
    generate_trim_json(
        video_path=video_path,
        output_path=json_path,
        segments=segments,
        audio_language=audio_lang,
        audio_stream_index=audio_idx,
        audio_enabled=audio_enabled,
        subtitle_language=subtitle_lang,
        subtitle_stream_index=subtitle_idx,
        subtitle_burn_in=subtitle_burn,
        subtitle_enabled=subtitle_enabled,
        output_dir=output_dir,
        output_format=output_format
    )
    
    print(f"\n🎉 配置完成！运行以下命令开始剪辑：")
    print(f"python -m src.trim_video.video_main {json_path}")


if __name__ == "__main__":
    interactive_generate_json()