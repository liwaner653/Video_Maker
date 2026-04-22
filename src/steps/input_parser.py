# input_parser.py
import os
import json
from typing import List
import argparse
from steps.base_step import BaseStep
from steps.context import BatchContext, TaskContext
from video_task import VideoTask, Audio, Trim, Subtitle, Thumbnail

class ParseJsonStep(BaseStep):
    @property
    def step_name(self): return "解析JSON输入"

    def execute(self, context: BatchContext) -> bool:
        try:
            parser = InputParser(context.json_path)
            for task in parser.video_tasks:
                lang = task.subtitle.subtitle_lang if task.subtitle and task.subtitle.subtitle_lang else "und"
                ctx = TaskContext(
                    task=task,
                    video_name=os.path.basename(task.video_path),
                    lang=lang
                )
                context.task_contexts.append(ctx)
            print(f"✅ 解析完成，获取 {len(context.task_contexts)} 个视频任务")
            return True
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            return False

class InputParser:
    """输入解析类：识别输入是文件夹/JSON文件，解析为统一的视频任务列表"""
    
    def __init__(self, input_str: str):
        self.input_str = input_str  # 输入的字符串（文件夹路径/JSON路径）
        self.video_tasks: List[VideoTask] = []  # 解析后的视频任务列表
        self._parse_input()  # 初始化时自动解析
    
    def _parse_input(self):
        """核心解析逻辑：区分文件夹/JSON文件"""
        # 检查输入是否为JSON文件
        if self.input_str.endswith('.json') and os.path.isfile(self.input_str):
            self._parse_json_file()
        # 检查输入是否为文件夹
        elif os.path.isdir(self.input_str):
            self._parse_folder()
        else:
            raise ValueError(f"输入无效：{self.input_str} 既不是文件夹也不是JSON文件")
    
    def _parse_folder(self):
        """解析文件夹：遍历视频文件，默认音轨0、不裁剪、德语字幕"""
        video_extensions = ('.mp4', '.mkv', '.avi', '.mov')
        for filename in os.listdir(self.input_str):
            if filename.lower().endswith(video_extensions):
                video_path = os.path.join(self.input_str, filename)
                self.video_tasks.append(
                    VideoTask(
                        video_path=video_path,
                        audio=Audio(audio_stream_index=0),
                        trim=Trim(cut_front_seconds=0.0, cut_back_seconds=0.0),
                        subtitle=Subtitle(subtitle_lang="de", srt_stream_index=-1),
                        thumbnail=Thumbnail(pic_path="")
                    )
                )
        if not self.video_tasks:
            raise ValueError(f"文件夹 {self.input_str} 中未找到视频文件")
        print(f"✅ 解析文件夹完成，找到 {len(self.video_tasks)} 个视频任务")
    
    def _parse_json_file(self):
        """解析JSON文件：读取嵌套对象结构"""
        try:
            with open(self.input_str, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON文件解析失败：{e}")
        
        # JSON格式要求：列表，每个元素包含必要字段
        if not isinstance(json_data, list):
            raise ValueError("JSON文件必须是数组格式（列表）")
        
        for idx, item in enumerate(json_data):
            # 检查必填字段
            required_fields = ['video_path', 'audio', 'thumbnail']
            missing_fields = [f for f in required_fields if f not in item]
            if missing_fields:
                raise ValueError(f"JSON第{idx+1}项缺少字段：{missing_fields}")
            
            # 验证video_path
            video_path = item['video_path']
            if not os.path.isfile(video_path):
                raise ValueError(f"JSON第{idx+1}项视频文件不存在：{video_path}")
            
            # 解析audio对象
            audio_data = item['audio']
            if 'audio_stream_index' not in audio_data:
                raise ValueError(f"JSON第{idx+1}项audio对象缺少audio_stream_index")
            audio = Audio(int(audio_data['audio_stream_index']))
            
            # 解析可选的trim对象
            trim = None
            if 'trim' in item:
                trim_data = item['trim']
                cut_front = float(trim_data.get('cut_front_seconds', 0.0))
                cut_back = float(trim_data.get('cut_back_seconds', 0.0))
                if cut_front < 0 or cut_back < 0:
                    raise ValueError(f"JSON第{idx+1}项trim对象裁剪秒数不能为负")
                trim = Trim(cut_front, cut_back)
            
            # 解析可选的subtitle对象
            subtitle = None
            if 'subtitle' in item:
                sub_data = item['subtitle']
                if 'subtitle_lang' not in sub_data:
                    raise ValueError(f"JSON第{idx+1}项subtitle对象缺少subtitle_lang")
                sub_lang = sub_data['subtitle_lang'].strip()
                if not sub_lang:
                    raise ValueError(f"JSON第{idx+1}项字幕语言不能为空")
                srt_idx = int(sub_data.get('srt_stream_index', -1))
                if srt_idx < -1:
                    raise ValueError(f"JSON第{idx+1}项字幕流索引不能小于-1：{srt_idx}")
                subtitle = Subtitle(sub_lang, srt_idx)
            
            # 解析thumbnail对象
            thumbnail_data = item['thumbnail']
            pic_path = thumbnail_data.get('pic_path', "").strip()
            if pic_path and not os.path.isfile(pic_path):
                raise ValueError(f"JSON第{idx+1}项thumbnail对象指定的封面图片不存在：{pic_path}")
            thumbnail = Thumbnail(pic_path)
            
            # 添加到任务列表
            self.video_tasks.append(
                VideoTask(
                    video_path=video_path,
                    audio=audio,
                    trim=trim,
                    subtitle=subtitle,
                    thumbnail=thumbnail
                )
            )
        print(f"✅ 解析JSON完成，找到 {len(self.video_tasks)} 个视频任务")


def generate_video_json(folder_path: str, output_json_path: str, audio_stream_index=0, cut_front_seconds=0.0, cut_back_seconds=0.0, default_sub_lang: str = "de", default_srt_index: int = -1, default_pic_path: str = ""):
    """
    从视频文件夹生成JSON配置文件
    Args:
        folder_path: 视频文件夹路径
        output_json_path: 生成的JSON文件保存路径
        audio_stream_index: 默认音轨索引
        cut_front_seconds: 默认开头裁剪秒数
        cut_back_seconds: 默认结尾裁剪秒数
        default_sub_lang: 默认字幕语言，默认德语"de"
        default_srt_index: 默认字幕流索引
    """
    if not os.path.isdir(folder_path):
        raise ValueError(f"文件夹不存在：{folder_path}")
    
    # 遍历视频文件生成JSON数据
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov')
    json_data = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(video_extensions):
            video_path = os.path.abspath(os.path.join(folder_path, filename))
            json_data.append({
                "video_path": video_path,
                "audio": {"audio_stream_index": audio_stream_index},
                "trim": {"cut_front_seconds": cut_front_seconds, "cut_back_seconds": cut_back_seconds},
                "subtitle": {"subtitle_lang": default_sub_lang, "srt_stream_index": default_srt_index},
                "thumbnail": {"pic_path": default_pic_path}
            })
    
    if not json_data:
        raise ValueError(f"文件夹 {folder_path} 中未找到视频文件")
    
    # 写入JSON文件（格式化输出，便于编辑）
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    
    print(f"✅ JSON文件生成完成：{output_json_path}")
    print(f"   共包含 {len(json_data)} 个视频配置项（默认字幕语言：{default_sub_lang}）")


if __name__ == "__main__":
    input_dir = input("请输入视频文件所在目录路径: ").strip()
    generate_video_json(input_dir, os.path.join(input_dir, "json.json"), 
                        default_sub_lang='ru'
                        )
    
#    parser = argparse.ArgumentParser(description="从视频文件夹生成 JSON 配置文件")
#    parser.add_argument("folder_path", help="视频文件夹路径（必填）")
#    parser.add_argument("--audio_stream_index", type=int, default=0,
#                        help="默认音轨索引（默认: 0）")
#    parser.add_argument("--cut_front_seconds", type=float, default=0.0,
#                        help="默认开头裁剪秒数（默认: 0.0）")
#    parser.add_argument("--cut_back_seconds", type=float, default=0.0,
#                        help="默认结尾裁剪秒数（默认: 0.0）")
#    parser.add_argument("--default_sub_lang", type=str, default="de",
#                        help="默认字幕语言（默认: de）")
#    parser.add_argument("--default_srt_index", type=int, default=-1,
#                        help="默认字幕流索引（默认: -1）")
#    parser.add_argument("--default_pic_path", type=str, default="", help="默认封面图路径（默认: 空）")
#    
#    generate_video_json(
#        folder_path=parser.folder_path,
#        output_json_path=os.path.join(parser.folder_path, "json.json"),
#        audio_stream_index=parser.audio_stream_index,
#        cut_front_seconds=parser.cut_front_seconds,
#        cut_back_seconds=parser.cut_back_seconds,
#        default_sub_lang=parser.default_sub_lang,
#        default_srt_index=parser.default_srt_index,
#        default_pic_path=parser.default_pic_path
#    )
    