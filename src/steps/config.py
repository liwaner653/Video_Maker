"""
配置文件
"""

# Git仓库路径 - 用于上传subtitles文件夹
GIT_REPO_PATH = r"D:\waner\6_projects\Anime_Deutsch_Learning\other languages"

# 调试模式 - 设置为True跳过字幕文件大小检查
DEBUG = True

# 支持的视频文件扩展名
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts')

# 语言缩写到全称映射字典
LANG_MAP = {
    'en': ['english', 'eng', 'en'],
    'de': ['german', 'ger', 'deu', 'de'],
    'zh': ['chinese', 'chi', 'zho', 'zh'],
    'ja': ['japanese', 'jpn', 'ja'],
    'fr': ['french', 'fre', 'fra', 'fr'],
    'es': ['spanish', 'spa', 'es'],
    'ru': ['russian', 'rus', 'ru'],
    'pt': ['portuguese', 'por', 'pt'],
}