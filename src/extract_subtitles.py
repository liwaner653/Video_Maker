import subprocess
import json
import os

def extract_mkv_subtitles(video_path, output_dir, target_track_indices=None):
    """
    分析 MKV 视频并提取所有文本字幕轨为 SRT 文件。
    """
    if not os.path.isfile(video_path):
        print(f"❌ 错误: 找不到文件 {video_path}")
        return None

    # 创建输出目录（如果不存在）
    os.makedirs(output_dir, exist_ok=True)

    print(f"正在分析视频: {video_path} ...\n")
    
    # 构建 ffprobe 命令，获取所有字幕流的信息 (以 JSON 格式输出)
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "stream=index,codec_name:stream_tags=language,title",
        "-select_streams", "s",  # 只选择字幕流 (subtitles)
        "-of", "json",
        video_path
    ]

    try:
        # 执行 ffprobe 命令
        result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        probe_data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ 解析视频失败，请检查视频文件或 FFmpeg 安装。错误信息:\n{e.stderr}")
        return None
    except json.JSONDecodeError:
        print("❌ 无法解析 ffprobe 的输出。")
        return None

    streams = probe_data.get("streams", [])
    if not streams:
        print("ℹ️ 在此视频中未找到任何字幕轨。")
        return None

    print(f"✅ 找到 {len(streams)} 条字幕轨，准备开始提取...\n")

    # 筛选目标轨道（如果指定了的话）
    if target_track_indices is not None:
        streams = [s for s in streams if s.get("index") in target_track_indices]
        if not streams:
            print(f"\n⚠️ 未找到指定的轨道: {target_track_indices}")
            return None
        print(f"\n✅ 筛选出 {len(streams)} 条目标轨道，准备提取...")
    else:
        print(f"\n✅ 找到 {len(streams)} 条字幕轨，准备开始提取...\n")
    
    # 获取文件名（不带扩展名）
    video_basename = os.path.splitext(os.path.basename(video_path))[0]

    # 初始化成功提取的文件路径列表
    extracted_files = []

    for stream in streams:
        stream_index = stream.get("index")
        codec_name = stream.get("codec_name", "unknown")
        
        # 获取语言和标题（如果没有则使用默认值）
        tags = stream.get("tags", {})
        language = tags.get("language", "und") # und 表示 undefined
        title = tags.get("title", "")
        
        # 过滤掉图片类型的字幕（如蓝光的 PGS 或 DVD 的 VobSub），因为它们无法直接转为 SRT 文本
        if codec_name in ["hdmv_pgs_subtitle", "dvd_subtitle"]:
            print(f"⚠️ 跳过流 {stream_index} ({language}): 图片型字幕 ({codec_name}) 无法直接提取为 SRT 文本，需要 OCR 识别。")
            continue
            
        # 构造输出文件名：原文件名_流索引_语言.srt
        output_filename = f"{video_basename}_track{stream_index}.srt"
        output_file = os.path.join(output_dir, output_filename)
        
        # 替换文件名中可能引起问题的非法字符
        # output_file = output_file.replace("/", "-").replace("\\", "-").replace(":", "-")

        print(f"▶️ 正在提取流 {stream_index} ({language}, {codec_name}) -> {output_file}")
        
        # 构建 ffmpeg 提取命令
        # -map 0:{stream_index} 精确选择指定的流
        # -c:s srt 强制将字幕（如 ASS/SSA）转换为 SRT 格式
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # 覆盖已存在的文件
            "-v", "error",
            "-i", video_path,
            "-map", f"0:{stream_index}",
            "-c:s", "srt",
            output_file
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"   ✔️ 提取成功!")
            extracted_files.append(output_file)
        except subprocess.CalledProcessError as e:
            print(f"   ❌ 提取失败。流索引: {stream_index}")

    print("\n🎉 所有支持的字幕轨提取完毕！")
    return extracted_files

def main():
    # 这里输入你的 MKV 视频文件路径
    # 注意：如果是 Windows 系统，路径中的反斜杠最好写成双反斜杠 \\，或者在字符串前加 r
    video_file = r"C:\Users\waner\Downloads\Takopii no Genzai\Takopii no Genzai - 01.mkv"  
    target_tracks = [5]
    output_dir = os.path.join(os.path.dirname(video_file), "subtitles")
    
    # 将视频文件路径传给提取字幕函数
    extract_mkv_subtitles(video_file, output_dir=output_dir, target_track_indices=target_tracks)

if __name__ == "__main__":
    main()