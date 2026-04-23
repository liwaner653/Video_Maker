import subprocess

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

if __name__ == "__main__":
    x = get_video_duration('D:/waner/4_ani/[Trix] Blue Box S01 [BD 1080p AV1 Opus] (Dual Audio, Multi Subs)/[Trix] Blue Box S01E01 [BD 1080p AV1 Opus] (Dual Audio, Multi Subs).mkv')
    print(x)