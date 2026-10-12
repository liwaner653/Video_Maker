import subprocess
import json

from steps.config import LANG_FALLBACK_MAP


def normalize_subtitle_lang(subtitle_lang: str) -> str:
    """将不支持的语言代码归一化为默认语言（如 und → en）"""
    return LANG_FALLBACK_MAP.get((subtitle_lang or "").lower(), subtitle_lang)


def get_video_duration(video_path: str) -> float:
    """使用 ffprobe 获取视频总时长（秒）"""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def get_video_chapters(video_path: str) -> dict:
    """
    从视频文件中提取所有章节信息
    返回格式: {
        "chapter_name": {
            "start_time": 浮点数（秒）,
            "end_time": 浮点数（秒）
        },
        ...
    }
    """
    chapters = {}
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "chapter=start_time,end_time:chapter_tags=title",
            "-of", "json", video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)

        if "chapters" not in data:
            return chapters

        for chapter in data["chapters"]:
            start_time = float(chapter.get("start_time", 0.0))
            end_time = float(chapter.get("end_time", 0.0))
            tags = chapter.get("tags", {})
            title = tags.get("title", "")

            if title:
                chapters[title] = {
                    "start_time": start_time,
                    "end_time": end_time
                }
    except Exception as e:
        print(f"⚠️ 读取章节信息失败: {e}")

    return chapters

if __name__ == "__main__":
    x = get_video_duration('D:/waner/4_ani/[Trix] Blue Box S01 [BD 1080p AV1 Opus] (Dual Audio, Multi Subs)/[Trix] Blue Box S01E01 [BD 1080p AV1 Opus] (Dual Audio, Multi Subs).mkv')
    print(x)