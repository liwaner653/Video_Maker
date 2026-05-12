import json
import os


def generate_video_json(folder_path: str, output_json_path: str, cut_front_seconds=0.0, cut_back_seconds=0.0, start_chapter_name="", end_chapter_name="", default_sub_lang: str = "de", default_pic_path: str = "", default_blur_sigma: float = 0.0):
    """
    从视频文件夹生成JSON配置文件
    Args:
        folder_path: 视频文件夹路径
        output_json_path: 生成的JSON文件保存路径
        cut_front_seconds: 默认开头裁剪秒数
        cut_back_seconds: 默认结尾裁剪秒数
        start_chapter_name: 默认开始章节名称
        end_chapter_name: 默认结束章节名称
        default_sub_lang: 默认字幕语言，默认德语"de"
        default_blur_sigma: 默认模糊度，默认0.0(不模糊)
    """
    if not os.path.isdir(folder_path):
        raise ValueError(f"文件夹不存在：{folder_path}")
    
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov')
    json_data = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(video_extensions):
            video_path = os.path.abspath(os.path.join(folder_path, filename))
            part_data = {}
            if cut_front_seconds > 0:
                part_data["cut_front_seconds"] = cut_front_seconds
            if cut_back_seconds > 0:
                part_data["cut_back_seconds"] = cut_back_seconds
            if start_chapter_name:
                part_data["start_chapter_name"] = start_chapter_name
            if end_chapter_name:
                part_data["end_chapter_name"] = end_chapter_name
            
            task_data = {
                "video_path": video_path,
                "audio": {
                    "audio_stream_index": 0,
                    "check_exist": False
                },
                "subtitle": {
                    "subtitle_lang": default_sub_lang,
                    "check_exist": False
                },
                "thumbnail": {
                    "pic_path": default_pic_path,
                    "blur_sigma": default_blur_sigma,
                    "check_exist": False
                },
                "final_video": {
                    "check_exist": False
                }
            }
            
            if part_data:
                task_data["video_parts"] = [part_data]
            
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
                        default_sub_lang='en',
                        start_chapter_name='Opening',
                        end_chapter_name='Ending'
                        )