# input_parser.py
import os
import json
from typing import List
import argparse
from steps.base_step import BaseStep
from steps.context import BatchContext, TaskContext
from steps.video_task import VideoTask, VideoPart, Audio, Subtitle, Thumbnail, FinalVideo

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
                        audio=Audio(audio_stream_index=0, check_exist=False),
                        parts=[VideoPart()],
                        subtitle=Subtitle(subtitle_lang="de", check_exist=False),
                        thumbnail=Thumbnail(pic_path="", blur_sigma=0.0, check_exist=False),
                        final_video=FinalVideo(check_exist=False)
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
            
            # 解析可选的audio对象
            audio = None
            if 'audio' in item:
                audio_data = item['audio']
                audio_stream_index = int(audio_data.get('audio_stream_index', 0))
                check_exist = bool(audio_data.get('check_exist', False))
                audio = Audio(audio_stream_index=audio_stream_index, check_exist=check_exist)
            
            # 解析可选的video_parts数组
            parts = []
            if 'video_parts' in item:
                video_parts_data = item['video_parts']
                if not isinstance(video_parts_data, list):
                    raise ValueError(f"JSON第{idx+1}项video_parts必须是数组")
                for part_idx, part_data in enumerate(video_parts_data):
                    parts.append(self._parse_video_part(part_data, idx+1, part_idx+1))
            elif 'video_part' in item:
                parts.append(self._parse_video_part(item['video_part'], idx+1, 1))
            else:
                parts = [VideoPart()]
            
            # 解析可选的subtitle对象
            subtitle = None
            if 'subtitle' in item:
                sub_data = item['subtitle']
                if 'subtitle_lang' not in sub_data:
                    raise ValueError(f"JSON第{idx+1}项subtitle对象缺少subtitle_lang")
                sub_lang = sub_data['subtitle_lang'].strip()
                if not sub_lang:
                    raise ValueError(f"JSON第{idx+1}项字幕语言不能为空")
                check_exist = bool(sub_data.get('check_exist', False))
                subtitle = Subtitle(sub_lang, check_exist=check_exist)
            
            # 解析thumbnail对象
            thumbnail_data = item['thumbnail']
            pic_path = thumbnail_data.get('pic_path', "").strip()
            if pic_path and not os.path.isfile(pic_path):
                raise ValueError(f"JSON第{idx+1}项thumbnail对象指定的封面图片不存在：{pic_path}")
            blur_sigma = float(thumbnail_data.get('blur_sigma', 0.0))
            if blur_sigma < 0:
                blur_sigma = 0.0
            check_exist = bool(thumbnail_data.get('check_exist', False))
            thumbnail = Thumbnail(pic_path, blur_sigma, check_exist=check_exist)
            
            # 解析可选的final_video对象
            final_video = FinalVideo(check_exist=False)
            if 'final_video' in item:
                fv_data = item['final_video']
                check_exist = bool(fv_data.get('check_exist', False))
                final_video = FinalVideo(check_exist=check_exist)
            
            # 添加到任务列表
            self.video_tasks.append(
                VideoTask(
                    video_path=video_path,
                    audio=audio,
                    subtitle=subtitle,
                    thumbnail=thumbnail,
                    final_video=final_video,
                    parts=parts
                )
            )
        print(f"✅ 解析JSON完成，找到 {len(self.video_tasks)} 个视频任务")
    
    def _parse_video_part(self, part_data: dict, item_idx: int, part_idx: int) -> VideoPart:
        """解析单个VideoPart对象"""
        name = part_data.get('name', "").strip()
        
        cut_front_seconds = part_data.get('cut_front_seconds')
        if cut_front_seconds is not None:
            cut_front_seconds = float(cut_front_seconds)
            if cut_front_seconds < 0:
                raise ValueError(f"JSON第{item_idx}项第{part_idx}个video_part的cut_front_seconds不能为负")
        
        cut_back_seconds = part_data.get('cut_back_seconds')
        if cut_back_seconds is not None:
            cut_back_seconds = float(cut_back_seconds)
            if cut_back_seconds < 0:
                raise ValueError(f"JSON第{item_idx}项第{part_idx}个video_part的cut_back_seconds不能为负")
        
        start_chapter_name = part_data.get('start_chapter_name', "").strip()
        
        last_seconds = part_data.get('last_seconds')
        if last_seconds is not None:
            last_seconds = float(last_seconds)
            if last_seconds < 0:
                raise ValueError(f"JSON第{item_idx}项第{part_idx}个video_part的last_seconds不能为负")
        
        end_chapter_name = part_data.get('end_chapter_name')
        if end_chapter_name is not None:
            end_chapter_name = end_chapter_name.strip()
        
        audio_offset_chapter_start_time = part_data.get('audio_offset_chapter_start_time', "").strip()
        
        thumbnail = bool(part_data.get('thumbnail', True))
        srt = bool(part_data.get('srt', True))
        audio = bool(part_data.get('audio', True))

        return VideoPart(
            name=name,
            cut_front_seconds=cut_front_seconds,
            cut_back_seconds=cut_back_seconds,
            start_chapter_name=start_chapter_name,
            last_seconds=last_seconds,
            end_chapter_name=end_chapter_name,
            thumbnail=thumbnail,
            srt=srt,
            audio=audio,
            audio_offset_chapter_start_time=audio_offset_chapter_start_time
        )
