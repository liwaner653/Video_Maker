#!/usr/bin/env python3
# video_merge_step.py
import json
import os
import subprocess
import tempfile
from .base_step import BaseStep
from .context import TaskContext


def merge_video_audio_subtitle(
    trimmed_video_path: str,
    audio_path: str,
    srt_path: str,
    additional_video_path: str,
    output_dir: str,
    base_name: str
) -> str | None:
    if not os.path.exists(trimmed_video_path):
        print(f"❌ 裁剪后的视频不存在: {trimmed_video_path}")
        return None

    if not os.path.exists(audio_path):
        print(f"❌ 音频文件不存在: {audio_path}")
        return None

    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, f"{base_name}.mkv").replace('\\', '/')

    has_srt = srt_path and os.path.exists(srt_path)
    has_additional_video = additional_video_path and os.path.exists(additional_video_path)

    first_merge_path = os.path.join(output_dir, "first_merge.mkv").replace('\\', '/')

    command = [
        'ffmpeg', '-y',
        '-i', trimmed_video_path,
        '-i', audio_path
    ]

    if has_srt:
        safe_srt_path = srt_path.replace('\\', '/').replace(':', r'\:').replace("'", "\\'")
        command.extend(['-vf', f"subtitles='{safe_srt_path}':force_style='FontName=SimHei,FontSize=16'"])

    command.extend([
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        # 音频在 AudioStep 已统一转为 AAC 48kHz 立体声，这里直接流拷贝
        '-c:a', 'copy',
        '-shortest',
        first_merge_path
    ])

    print(f"📽️ 合并画面+音频{'+字幕' if has_srt else ''}...")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        if not os.path.exists(first_merge_path):
            print("❌ 错误：第一次合并未生成输出文件")
            return None
        print("✅ 第一次合并完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 第一次合并报错: {e.stderr}")
        return None

    if has_additional_video:
        print(f"🔗 合并额外视频: {os.path.basename(additional_video_path)}")
        return concat_videos_stream_copy(
            first_path=first_merge_path,
            additional_path=additional_video_path,
            output_dir=output_dir,
            final_output_path=final_output_path
        )
    else:
        os.replace(first_merge_path, final_output_path.replace('/', '\\'))
        if os.path.exists(final_output_path):
            print(f"✅ 成功生成最终视频: {final_output_path}")
            return final_output_path
        else:
            print("❌ 错误：重命名输出文件失败")
            return None


def _probe_stream_params(video_path: str) -> dict:
    """读取视频的视频流/音频流关键参数"""
    probe_command = [
        'ffprobe', '-v', 'error',
        '-show_entries',
        'stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,time_base,sample_rate,channels',
        '-of', 'json', video_path
    ]
    result = subprocess.run(probe_command, check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get('streams', [])
    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    return {'video': video_stream, 'audio': audio_stream}


def _fps_to_float(fps_str: str) -> float:
    try:
        num, den = fps_str.split('/')
        return float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def _params_match(main_params: dict, other_params: dict) -> bool:
    """判断两段视频的编码参数是否一致，一致才能用 concat demuxer 免重编码拼接"""
    main_v, other_v = main_params['video'], other_params['video']
    if not main_v or not other_v:
        return False
    if main_v.get('codec_name') != other_v.get('codec_name'):
        return False
    if main_v.get('width') != other_v.get('width') or main_v.get('height') != other_v.get('height'):
        return False
    main_fps = _fps_to_float(main_v.get('r_frame_rate', '0/1'))
    other_fps = _fps_to_float(other_v.get('r_frame_rate', '0/1'))
    if abs(main_fps - other_fps) > 0.01:
        return False
    if main_v.get('pix_fmt') != other_v.get('pix_fmt'):
        return False
    # 容器时间基必须一致，否则 concat demuxer 流拷贝会产生错乱时间戳
    if main_v.get('time_base') != other_v.get('time_base'):
        return False

    main_a, other_a = main_params['audio'], other_params['audio']
    # 额外视频无音轨时视为可接受：拼接后该段无声，不影响主视频
    if main_a and other_a:
        if main_a.get('codec_name') != other_a.get('codec_name'):
            return False
        if int(main_a.get('sample_rate', 0)) != int(other_a.get('sample_rate', 0)):
            return False
        if main_a.get('channels') != other_a.get('channels'):
            return False
        if main_a.get('time_base') != other_a.get('time_base'):
            return False
    return True


def _normalize_additional_video(additional_path: str, main_params: dict) -> str | None:
    """将额外视频转码为主视频参数（mkv 容器），返回转码后的路径

    原文件是 .mkv 时转码后覆盖原文件；否则生成同名 .mkv 旁路文件，
    下次运行参数比对命中后直接复用，不再重复转码。
    统一 mkv 容器是为了与主视频保持相同时间基，避免 concat 流拷贝产生错乱时间戳。
    """
    main_v = main_params['video']
    width, height = main_v['width'], main_v['height']
    fps = main_v['r_frame_rate']

    root, _ = os.path.splitext(additional_path)
    target_path = f"{root}.mkv"
    temp_output = f"{root}_normalized_tmp.mkv".replace('\\', '/')

    normalize_command = ['ffmpeg', '-y', '-i', additional_path.replace('\\', '/')]
    normalize_command.extend([
        '-vf', f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1",
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
    ])
    if main_params['audio']:
        normalize_command.extend(['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2'])
    else:
        normalize_command.append('-an')
    normalize_command.extend(['-shortest', temp_output])

    print("🎞️ 额外视频参数与主视频不一致，转码为主视频参数（mkv）...")
    try:
        subprocess.run(normalize_command, check=True, capture_output=True, text=True)
        os.replace(temp_output, target_path)
        print(f"✅ 额外视频已转码: {target_path}")
        return target_path.replace('\\', '/')
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 转码额外视频报错: {e.stderr}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return None
    except OSError as e:
        print(f"❌ 写入转码文件失败: {e}")
        return None


def concat_videos_stream_copy(
    first_path: str,
    additional_path: str,
    output_dir: str,
    final_output_path: str
) -> str | None:
    """检查额外视频与主视频参数是否一致，不一致则转码为 mkv，最后用 concat demuxer 免重编码拼接"""
    try:
        main_params = _probe_stream_params(first_path)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"❌ 读取主视频参数失败: {e}")
        return None

    # 候选文件：若额外视频不是 mkv，优先复用之前转码生成的同名 .mkv
    root, ext = os.path.splitext(additional_path)
    candidates = []
    if ext.lower() != '.mkv':
        candidates.append(f"{root}.mkv")
    candidates.append(additional_path)

    concat_source = None
    for candidate in candidates:
        if not os.path.exists(candidate):
            continue
        try:
            candidate_params = _probe_stream_params(candidate)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        if _params_match(main_params, candidate_params):
            print(f"✅ 额外视频参数与主视频一致，直接拼接（免重编码）: {os.path.basename(candidate)}")
            concat_source = candidate.replace('\\', '/')
            break

    if not concat_source:
        concat_source = _normalize_additional_video(additional_path, main_params)
        if not concat_source:
            return None

    concat_list_path = os.path.join(output_dir, "concat_list.txt")
    with open(concat_list_path, 'w', encoding='utf-8') as f:
        f.write(f"file '{first_path}'\n")
        f.write(f"file '{concat_source}'\n")

    concat_command = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', concat_list_path,
        '-c', 'copy',
        final_output_path
    ]
    try:
        subprocess.run(concat_command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 合并额外视频报错: {e.stderr}")
        return None
    finally:
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)

    if os.path.exists(final_output_path):
        if os.path.exists(first_path):
            os.remove(first_path)
        print(f"✅ 成功合并额外视频: {final_output_path}")
        return final_output_path
    print("❌ 错误：合并额外视频后未找到输出文件")
    return None


class VideoMergeStep(BaseStep):
    @property
    def step_name(self):
        return "音视频合并"

    def execute(self, context: TaskContext) -> bool:
        base_name = os.path.splitext(os.path.basename(context.task.video_path))[0]
        if context.task.final_video.check_exist:
            expected_path = os.path.join(context.final_video_dir, f"{base_name}.mkv")
            if os.path.exists(expected_path):
                print(f"⏭️ 跳过音视频合并（check_exist=true，文件已存在）: {expected_path}")
                context.final_video_path = expected_path.replace('\\', '/')
                self._cleanup_trimmed_video(context, base_name)
                return True

        additional_video = context.task.final_video.additional_video_path

        merged_path = merge_video_audio_subtitle(
            trimmed_video_path=context.trimmed_video_path,
            audio_path=context.audio_path,
            srt_path=context.srt_path,
            additional_video_path=additional_video,
            output_dir=context.final_video_dir,
            base_name=base_name
        )

        if merged_path:
            context.final_video_path = merged_path
            self._cleanup_trimmed_video(context, base_name)
            return True
        context.error_msg = "音视频合并失败"
        return False

    def _cleanup_trimmed_video(self, context: TaskContext, base_name: str) -> None:
        """合并完成后删除中间的裁剪视频文件"""
        trimmed = context.trimmed_video_path or os.path.join(context.trimmed_video_dir, f"{base_name}_trimmed.mkv")
        if os.path.exists(trimmed):
            try:
                os.remove(trimmed)
                print(f"🧹 已清理中间视频: {trimmed}")
            except OSError as e:
                print(f"⚠️ 清理中间视频失败 {trimmed}: {e}")