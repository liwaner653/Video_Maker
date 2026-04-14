# input_parser.py
import os
import json
from dataclasses import dataclass
from typing import List, Optional
import argparse

@dataclass
class VideoTask:
    """视频任务数据类，保存单个视频的解析结果（支持扩展新字段）"""
    video_path: str          # 视频文件完整路径
    audio_stream_index: int  # 音频轨道索引，默认0
    cut_front_seconds: float # 裁剪开头秒数，0表示不裁剪
    cut_back_seconds: float  # 裁剪结尾秒数，0表示不裁剪
    subtitle_lang: str       # 字幕语言（新增字段），默认德语"de"
    srt_stream_index: int = 0  # 字幕流索引，-1表示未指定或自动选择

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
                        audio_stream_index=0,
                        cut_front_seconds=0.0,
                        cut_back_seconds=0.0,
                        subtitle_lang="de",  # 文件夹模式默认德语
                        srt_stream_index=-1  # 文件夹模式默认-1
                    )
                )
        if not self.video_tasks:
            raise ValueError(f"文件夹 {self.input_str} 中未找到视频文件")
        print(f"✅ 解析文件夹完成，找到 {len(self.video_tasks)} 个视频任务")
    
    def _parse_json_file(self):
        """解析JSON文件：读取视频路径、音轨、裁剪秒数、字幕语言"""
        try:
            with open(self.input_str, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON文件解析失败：{e}")
        
        # JSON格式要求：列表，每个元素包含必要字段
        if not isinstance(json_data, list):
            raise ValueError("JSON文件必须是数组格式（列表）")
        
        for idx, item in enumerate(json_data):
            # 检查必填字段（修改并新增了裁剪参数）
            required_fields = ['video_path', 'audio_stream_index', 'cut_front_seconds', 'cut_back_seconds', 'subtitle_lang']
            missing_fields = [f for f in required_fields if f not in item]
            if missing_fields:
                raise ValueError(f"JSON第{idx+1}项缺少字段：{missing_fields}")
            
            # 验证字段类型和值
            video_path = item['video_path']
            if not os.path.isfile(video_path):
                raise ValueError(f"JSON第{idx+1}项视频文件不存在：{video_path}")
            
            audio_idx = int(item['audio_stream_index'])
            cut_front_sec = float(item['cut_front_seconds'])
            cut_back_sec = float(item['cut_back_seconds'])
            sub_lang = item['subtitle_lang'].strip()

             # 处理可选的srt_stream_index字段
            if 'srt_stream_index' in item:
                srt_idx = int(item['srt_stream_index'])
                if srt_idx < -1:  # 允许-1表示未指定
                    raise ValueError(f"JSON第{idx+1}项字幕流索引不能小于-1：{srt_idx}")
            else:
                srt_idx = -1  # 默认值
            
            # 分别验证开头和结尾裁剪的秒数不能为负
            if cut_front_sec < 0:
                raise ValueError(f"JSON第{idx+1}项开头裁剪秒数(cut_front_seconds)不能为负数：{cut_front_sec}")
            if cut_back_sec < 0:
                raise ValueError(f"JSON第{idx+1}项结尾裁剪秒数(cut_back_seconds)不能为负数：{cut_back_sec}")
            if not sub_lang:
                raise ValueError(f"JSON第{idx+1}项字幕语言不能为空")
            
            # 添加到任务列表
            self.video_tasks.append(
                VideoTask(
                    video_path=video_path,
                    audio_stream_index=audio_idx,
                    cut_front_seconds=cut_front_sec,
                    cut_back_seconds=cut_back_sec,
                    subtitle_lang=sub_lang,
                    srt_stream_index=srt_idx
                )
            )
        print(f"✅ 解析JSON完成，找到 {len(self.video_tasks)} 个视频任务")


def generate_video_json(folder_path: str, output_json_path: str, audio_stream_index=0, cut_front_seconds=0.0, cut_back_seconds=0.0, default_sub_lang: str = "de", default_srt_index: int = -1):
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
                "audio_stream_index": audio_stream_index,
                "cut_front_seconds": cut_front_seconds,
                "cut_back_seconds": cut_back_seconds,
                "subtitle_lang": default_sub_lang,
                "srt_stream_index": default_srt_index
            })
    
    if not json_data:
        raise ValueError(f"文件夹 {folder_path} 中未找到视频文件")
    
    # 写入JSON文件（格式化输出，便于编辑）
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    
    print(f"✅ JSON文件生成完成：{output_json_path}")
    print(f"   共包含 {len(json_data)} 个视频配置项（默认字幕语言：{default_sub_lang}）")


if __name__ == "__main__":
    # input_dir = input("请输入视频文件所在目录路径: ").strip()
    # generate_video_json(input_dir, os.path.join(input_dir, "json.json"), 
    #                     default_sub_lang='en', 
    #                     audio_stream_index=1,
    #                     cut_front_seconds=11,
    #                     cut_back_seconds=66,
    #                     default_srt_index=14
    #                     )
    
    parser = argparse.ArgumentParser(description="从视频文件夹生成 JSON 配置文件")
    parser.add_argument("folder_path", help="视频文件夹路径（必填）")
    parser.add_argument("--audio_stream_index", type=int, default=0,
                        help="默认音轨索引（默认: 0）")
    parser.add_argument("--cut_front_seconds", type=float, default=0.0,
                        help="默认开头裁剪秒数（默认: 0.0）")
    parser.add_argument("--cut_back_seconds", type=float, default=0.0,
                        help="默认结尾裁剪秒数（默认: 0.0）")
    parser.add_argument("--default_sub_lang", type=str, default="de",
                        help="默认字幕语言（默认: de）")
    parser.add_argument("--default_srt_index", type=int, default=-1,
                        help="默认字幕流索引（默认: -1）")
    
    args = parser.parse_args()
    
    generate_video_json(
        folder_path=args.folder_path,
        output_json_path=os.path.join(args.folder_path, "json.json"),
        audio_stream_index=args.audio_stream_index,
        cut_front_seconds=args.cut_front_seconds,
        cut_back_seconds=args.cut_back_seconds,
        default_sub_lang=args.default_sub_lang,
        default_srt_index=args.default_srt_index
    )
    