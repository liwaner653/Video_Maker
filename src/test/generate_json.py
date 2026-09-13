import json
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'steps'))
from util import get_video_chapters


def create_video_parts_from_chapters(video_path: str) -> list:
    """
    根据视频章节信息生成 video_parts 配置
    若章节标题包含 OP、Opening、ED、Ending 等关键词，则该章节的 srt=False
    若没有任何章节包含这些关键词，返回空列表
    
    Args:
        video_path: 视频文件路径
    
    Returns:
        video_parts 配置列表
    """
    # 定义关键词（不区分大小写）
    skip_srt_keywords = ['op', 'opening', 'ed', 'ending']
    
    chapters = get_video_chapters(video_path)
    if not chapters:
        return []
    
    video_parts = []
    has_keyword_chapter = False
    
    # 按章节开始时间排序
    sorted_chapters = sorted(chapters.items(), key=lambda x: x[1]["start_time"])
    
    last_chapter_skip_srt = True # 忽略连续章节
    for chapter_name, chapter_info in sorted_chapters:
        # 检查章节名称是否包含关键词
        chapter_name_lower = chapter_name.lower()
        is_skip_srt = any(keyword in chapter_name_lower for keyword in skip_srt_keywords)
        
        if is_skip_srt:
            has_keyword_chapter = True
            video_parts.append({
                "start_chapter_name": chapter_name,
                "srt": False
            })
            last_chapter_skip_srt = True
        elif last_chapter_skip_srt:
            last_chapter_skip_srt = False
            video_parts.append({
                "start_chapter_name": chapter_name
            })
    
    # 如果没有任何章节包含关键词，返回空列表
    if not has_keyword_chapter:
        return []
    
    return video_parts


def generate_video_json(folder_path: str, output_json_path: str, video_parts: list = None,
                        auto_detect_chapters: bool = False,
                        cut_front_seconds=0.0, cut_back_seconds=0.0, start_chapter_name="", end_chapter_name="",
                        default_sub_lang: str = "de", default_pic_path: str = "", default_blur_sigma: float = 0.0,
                        default_target_titles: list = None):
    """
    从视频文件夹生成JSON配置文件
    Args:
        folder_path: 视频文件夹路径
        output_json_path: 生成的JSON文件保存路径
        video_parts: 自定义视频片段配置列表，若提供则优先使用
        auto_detect_chapters: 是否自动检测章节信息生成 video_parts，若章节标题包含 OP/Opening/ED/Ending 则 srt=False
        cut_front_seconds: 默认开头裁剪秒数
        cut_back_seconds: 默认结尾裁剪秒数
        start_chapter_name: 默认开始章节名称
        end_chapter_name: 默认结束章节名称
        default_sub_lang: 默认字幕语言，默认德语"de"
        default_blur_sigma: 默认模糊度，默认0.0(不模糊)
        default_target_titles: 默认字幕标题关键字过滤列表，默认 ['cc', 'sdh', 'Dub']
    """
    if default_target_titles is None:
        default_target_titles = ['cc', 'sdh', 'Dub']
    if not os.path.isdir(folder_path):
        raise ValueError(f"文件夹不存在：{folder_path}")
    
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov')
    json_data = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(video_extensions):
            video_path = os.path.abspath(os.path.join(folder_path, filename))
            
            task_data = {
                "video_path": video_path,
                "audio": {
                    "audio_stream_index": 0,
                    "check_exist": True
                },
                "subtitle": {
                    "subtitle_lang": default_sub_lang,
                    "check_exist": True,
                    "target_titles": default_target_titles
                },
                "thumbnail": {
                    "pic_path": default_pic_path,
                    "blur_sigma": default_blur_sigma,
                    "check_exist": True
                },
                "final_video": {
                    "check_exist": True
                }
            }
            
            # 优先使用自定义 video_parts
            if video_parts:
                task_data["video_parts"] = video_parts
            # 其次尝试自动检测章节
            elif auto_detect_chapters:
                auto_parts = create_video_parts_from_chapters(video_path)
                if auto_parts:
                    task_data["video_parts"] = auto_parts
                    print(f"   📹 {filename}: 检测到 {len(auto_parts)} 个章节，已设置 video_parts")
                else:
                    print(f"   📹 {filename}: 无需设置 video_parts")

            
            json_data.append(task_data)
    
    if not json_data:
        raise ValueError(f"文件夹 {folder_path} 中未找到视频文件")
    
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    
    print(f"✅ JSON文件生成完成：{output_json_path}")
    print(f"   共包含 {len(json_data)} 个视频配置项（默认字幕语言：{default_sub_lang}）")


if __name__ == "__main__":
    input_dir = input("请输入视频文件所在目录路径: ").strip()
    generate_video_json(input_dir, os.path.join(input_dir, "json.json"), 
                        default_sub_lang='en'
                        #, default_blur_sigma=5.0
                        #, auto_detect_chapters=True
                        )