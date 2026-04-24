# input_parser.py
import os
import json
from typing import List
import argparse
from steps.base_step import BaseStep
from steps.context import BatchContext, TaskContext
from steps.video_task import VideoTask, Trim, Subtitle, Thumbnail

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
                    lang=lang,
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
                        trim=Trim(cut_front_seconds=0.0, cut_back_seconds=0.0, begin_chapter="", end_chapter=""),
                        subtitle=Subtitle(subtitle_lang="de"),
                        thumbnail=Thumbnail(pic_path="", blur_sigma=0.0)
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
            required_fields = ['video_path', 'subtitle', 'thumbnail']
            missing_fields = [f for f in required_fields if f not in item]
            if missing_fields:
                raise ValueError(f"JSON第{idx+1}项缺少字段：{missing_fields}")
            
            # 验证video_path
            video_path = item['video_path']
            if not os.path.isfile(video_path):
                raise ValueError(f"JSON第{idx+1}项视频文件不存在：{video_path}")
            
            # 解析可选的trim对象
            trim = None
            if 'trim' in item:
                trim_data = item['trim']
                cut_front = float(trim_data.get('cut_front_seconds', 0.0))
                cut_back = float(trim_data.get('cut_back_seconds', 0.0))
                if cut_front < 0 or cut_back < 0:
                    raise ValueError(f"JSON第{idx+1}项trim对象裁剪秒数不能为负")
                begin_chapter = trim_data.get('begin_chapter', "").strip()
                end_chapter = trim_data.get('end_chapter', "").strip()
                trim = Trim(cut_front, cut_back, begin_chapter, end_chapter)
            
            # 解析可选的subtitle对象
            subtitle = None
            if 'subtitle' in item:
                sub_data = item['subtitle']
                if 'subtitle_lang' not in sub_data:
                    raise ValueError(f"JSON第{idx+1}项subtitle对象缺少subtitle_lang")
                sub_lang = sub_data['subtitle_lang'].strip()
                if not sub_lang:
                    raise ValueError(f"JSON第{idx+1}项字幕语言不能为空")
                subtitle = Subtitle(sub_lang)
            
            # 解析thumbnail对象
            thumbnail_data = item['thumbnail']
            pic_path = thumbnail_data.get('pic_path', "").strip()
            if pic_path and not os.path.isfile(pic_path):
                raise ValueError(f"JSON第{idx+1}项thumbnail对象指定的封面图片不存在：{pic_path}")
            blur_sigma = float(thumbnail_data.get('blur_sigma', 0.0))
            if blur_sigma < 0:
                blur_sigma = 0.0
            thumbnail = Thumbnail(pic_path, blur_sigma)
            
            # 添加到任务列表
            self.video_tasks.append(
                VideoTask(
                    video_path=video_path,
                    trim=trim,
                    subtitle=subtitle,
                    thumbnail=thumbnail
                )
            )
        print(f"✅ 解析JSON完成，找到 {len(self.video_tasks)} 个视频任务")


    