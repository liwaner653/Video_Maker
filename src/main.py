#!/usr/bin/env python3
# main.py
import os
import sys
from input_parser import InputParser, generate_video_json
from extract_audio import extract_audio
from generate_subtitles import generate_subtitles
from embed_subtitle import embed_subtitle_to_video
from generate_thumbnail import generate_thumbnail
from extract_subtitles import extract_mkv_subtitles

JSON_PATH = r'D:\waner\4_ani\Pandora Hearts vf\json.json'

# ===================== 核心Main函数 =====================
def main():
#    # 1. 命令行参数解析
#    if len(sys.argv) < 2:
#        print("使用方法：")
#        print("  1. 处理文件夹/JSON：python main.py <输入路径(文件夹/JSON)>")
#        print("  2. 生成JSON：python main.py --generate-json <视频文件夹> <输出JSON路径> [默认字幕语言]")
#        sys.exit(1)
#    
#    # 处理生成JSON的特殊命令
#    if sys.argv[1] == '--generate-json':
#        if len(sys.argv) < 4:
#            print("生成JSON用法：python main.py --generate-json 视频文件夹 JSON输出路径 [默认字幕语言]")
#            sys.exit(1)
#        default_sub_lang = sys.argv[4] if len(sys.argv)>=5 else "de"
#        try:
#            generate_video_json(sys.argv[2], sys.argv[3], default_sub_lang)
#        except Exception as e:
#            print(f"❌ 生成JSON失败：{e}")
#        sys.exit(0)
    
    # 2. 解析输入（文件夹/JSON）→ 得到视频任务列表
    input_str = JSON_PATH # sys.argv[1]
    try:
        parser = InputParser(input_str)
        video_tasks = parser.video_tasks
        print(f"\n✅ 输入解析完成，共获取 {len(video_tasks)} 个视频任务")
    except Exception as e:
        print(f"❌ 输入解析失败：{e}")
        sys.exit(1)
    
    # 3. 配置输出目录（按功能分类）
    base_output = os.path.join(os.getcwd(), 'video_process_output')
    dir_config = {
        "thumbnail": os.path.join(base_output, "thumbnails"),  # 缩略图目录
        "audio": os.path.join(base_output, "audio"),            # 音频目录
        "subtitle": os.path.join(base_output, "subtitles"),     # 字幕目录
        "final_video": os.path.join(base_output, "final_videos")# 最终带字幕视频目录
    }
    # 创建所有输出目录
    for dir_path in dir_config.values():
        os.makedirs(dir_path, exist_ok=True)
    
    # 4. 批量处理每个视频任务（核心流程：解析→生成缩略图→提取音频→生成字幕→合成视频）
    print("\n" + "="*70)
    print("开始执行全流程：生成缩略图 → 提取音频 → 生成字幕 → 合成带字幕视频")
    print("="*70)
    
    # 统计结果
    stats = {
        "total": len(video_tasks),
        "thumb_success": 0,
        "audio_success": 0,
        "subtitle_success": 0,
        "video_success": 0,
        "failed_tasks": []
    }
    
    for idx, task in enumerate(video_tasks, 1):
        video_name = os.path.basename(task.video_path)
        print(f"\n【任务 {idx}/{stats['total']}】处理视频：{video_name}")
        print("-"*50)
        
        task_success = True

        # 配置当前视频的输出目录（在视频同级目录下创建子文件夹）
        video_dir = os.path.dirname(task.video_path)
        dir_config = {
            "thumbnail": os.path.join(video_dir, "thumbnails"),  # 视频同级/thumbnails
            "audio": os.path.join(video_dir, "audio"),            # 视频同级/audio
            "subtitle": os.path.join(video_dir, "subtitles"),     # 视频同级/subtitles
            "final_video": os.path.join(video_dir, "final_videos")# 视频同级/final_videos
        }
        # 创建当前视频的输出子目录（每个视频独立创建）
        for dir_path in dir_config.values():
            os.makedirs(dir_path, exist_ok=True)
        
        # 步骤1：调用独立的generate_image.py中的generate_thumbnail生成缩略图
        thumb_path = generate_thumbnail(
            video_path=task.video_path,
            output_dir=dir_config["thumbnail"],
            thumbnail_size="320:180",
            quality=2
        )
        if thumb_path:
            stats["thumb_success"] += 1
        else:
            task_success = False
            print(f"⚠️  缩略图生成失败，继续后续步骤...")
        
        # 步骤2：提取音频（调用extract_audio.py）
        audio_path = extract_audio(
            video_path=task.video_path,
            output_dir=dir_config["audio"],
            audio_stream_index=task.audio_stream_index,
            cut_seconds=task.cut_seconds
        )
        if audio_path:
            stats["audio_success"] += 1
        else:
            task_success = False
            print(f"⚠️  音频提取失败，跳过后续步骤")
            stats["failed_tasks"].append(video_name)
            continue
        
        # 步骤3：生成字幕（调用generate_subtitles.py）
        if task.srt_stream_index < 0:
            srt_path = generate_subtitles(
                audio_path=audio_path,
                output_dir=dir_config["subtitle"],
                model='turbo',
                subtitle_lang=task.subtitle_lang
            )
        else:
            srt_path = extract_mkv_subtitles(
                    video_path=task.video_path,
                    output_dir=dir_config["subtitle"],
                    target_track_indices=[task.srt_stream_index]
                )[0]

        stats["subtitle_success"] += 1
        
        # 步骤4：合成带字幕视频（调用embed_subtitle.py）
        final_video_path = embed_subtitle_to_video(
            thumbnail_path=thumb_path,
            srt_path=srt_path,
            audio_path=audio_path,
            output_dir=dir_config["final_video"],
        )
        if final_video_path:
            stats["video_success"] += 1
        else:
            task_success = False
            stats["failed_tasks"].append(video_name)
    
    # 5. 输出最终统计结果
    print("\n" + "="*70)
    print("📊 全流程处理完成 - 统计汇总")
    print("="*70)
    print(f"总任务数：{stats['total']}")
    print(f"缩略图生成成功：{stats['thumb_success']}/{stats['total']}")
    print(f"音频提取成功：{stats['audio_success']}/{stats['total']}")
    print(f"字幕生成成功：{stats['subtitle_success']}/{stats['total']}")
    print(f"带字幕视频合成成功：{stats['video_success']}/{stats['total']}")
    if stats["failed_tasks"]:
        print(f"❌ 失败任务列表：{stats['failed_tasks']}")
    print(f"\n📁 所有输出文件保存在：{base_output}")

if __name__ == "__main__":
    main()