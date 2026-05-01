"""
字幕处理模块 - 支持多种格式的字幕提取和时间调整
"""
from abc import ABC, abstractmethod
from datetime import timedelta
import os
import re
from typing import Optional, Tuple


class SubtitleHandler(ABC):
    """字幕处理基类"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
    
    @abstractmethod
    def adjust_timestamps(self, start_time: float, end_time: float) -> None:
        """
        调整字幕时间戳
        :param start_time: 开始时间（秒）
        :param end_time: 结束时间（秒），0表示到末尾
        """
        pass
    
    @staticmethod
    def _parse_timedelta(time_str: str) -> Optional[timedelta]:
        """解析时间字符串为 timedelta"""
        raise NotImplementedError
    
    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """格式化 timedelta 为时间字符串"""
        raise NotImplementedError


class SrtSubtitleHandler(SubtitleHandler):
    """SRT 格式字幕处理"""
    
    @staticmethod
    def _parse_timedelta(time_str: str) -> Optional[timedelta]:
        """解析 SRT 时间格式：HH:MM:SS,mmm"""
        try:
            h, m, s_ms = time_str.split(':')
            s, ms = s_ms.split(',')
            return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))
        except Exception:
            return None
    
    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """格式化为 SRT 时间格式：HH:MM:SS,mmm"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    def clean_styles(self) -> None:
        """
        清除 SRT 字幕中的所有样式标签
        包括：HTML 标签、ASS 格式标签、字体标签等
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        blocks = re.split(r'\n\n+', content.strip())
        new_blocks = []
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                new_blocks.append(block)
                continue
            
            # 保留序号和时间行
            new_lines = lines[:2]
            
            # 处理文本行：清除所有样式标签
            for text_line in lines[2:]:
                # 清除 ASS 格式标签 {\c&Hnnnnn&} 等
                text_line = re.sub(r'\{[^}]*\}', '', text_line)
                # 清除 HTML/XML 标签 <tag>...</tag>
                text_line = re.sub(r'<[^>]+>', '', text_line)
                # 清除 HTML 实体 &#...;
                text_line = re.sub(r'&#\d+;', '', text_line)
                # 清除多余空白
                text_line = text_line.strip()
                if text_line:  # 只保留非空行
                    new_lines.append(text_line)
            
            # 只有包含实际文本的块才保留
            if len(new_lines) > 2:
                new_blocks.append('\n'.join(new_lines))
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(new_blocks) + '\n')

    def adjust_timestamps(self, start_time: float, end_time: float) -> None:
        """调整 SRT 字幕时间戳"""
        if start_time <= 0 and end_time <= 0:
            return
        
        front_td = timedelta(seconds=start_time)
        end_threshold_s = end_time if end_time > 0 else float('inf')
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        blocks = re.split(r'\n\n+', content.strip())
        new_blocks = []
        new_index = 1
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            times = lines[1].split(' --> ')
            if len(times) != 2:
                continue
            
            start_td = self._parse_timedelta(times[0].strip())
            end_td = self._parse_timedelta(times[1].strip())
            
            if start_td is None or end_td is None:
                continue
            
            # 结尾限制逻辑
            if end_time > 0 and start_td.total_seconds() >= end_threshold_s:
                continue
            if end_time > 0 and end_td.total_seconds() > end_threshold_s:
                end_td = timedelta(seconds=end_threshold_s)
            
            # 开头限制逻辑
            start_td -= front_td
            end_td -= front_td
            
            if end_td.total_seconds() < 0:
                continue
            if start_td.total_seconds() < 0:
                start_td = timedelta(seconds=0)
            
            # 重组字幕块
            new_lines = [
                str(new_index),
                f"{self._format_timedelta(start_td)} --> {self._format_timedelta(end_td)}"
            ]
            new_lines.extend(lines[2:])
            new_blocks.append('\n'.join(new_lines))
            new_index += 1
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(new_blocks) + '\n')


class AssSubtitleHandler(SubtitleHandler):
    """ASS/SSA 格式字幕处理 (SubStation Alpha)"""
    
    @staticmethod
    def _parse_timedelta(time_str: str) -> Optional[timedelta]:
        """解析 ASS 时间格式：H:MM:SS.cc"""
        try:
            parts = time_str.split(':')
            h = int(parts[0])
            m = int(parts[1])
            s_cs = parts[2].split('.')
            s = int(s_cs[0])
            cs = int(s_cs[1]) if len(s_cs) > 1 else 0
            return timedelta(hours=h, minutes=m, seconds=s, centiseconds=cs)
        except Exception:
            return None
    
    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """格式化为 ASS 时间格式：H:MM:SS.cc"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        centiseconds = int((td.microseconds / 10000) % 100)
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
    
    def adjust_timestamps(self, start_time: float, end_time: float) -> None:
        """调整 ASS 字幕时间戳"""
        if start_time <= 0 and end_time <= 0:
            return
        
        front_td = timedelta(seconds=start_time)
        end_threshold_s = end_time if end_time > 0 else float('inf')
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            # 查找 Dialogue 行
            if line.startswith('Dialogue:'):
                parts = line.split(',', 9)  # Dialogue: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
                if len(parts) >= 10:
                    start_str = parts[1].strip()
                    end_str = parts[2].strip()
                    
                    start_td = self._parse_timedelta(start_str)
                    end_td = self._parse_timedelta(end_str)
                    
                    if start_td is None or end_td is None:
                        new_lines.append(line)
                        continue
                    
                    # 应用时间调整逻辑
                    if end_time > 0 and start_td.total_seconds() >= end_threshold_s:
                        continue  # 跳过该行
                    if end_time > 0 and end_td.total_seconds() > end_threshold_s:
                        end_td = timedelta(seconds=end_threshold_s)
                    
                    start_td -= front_td
                    end_td -= front_td
                    
                    if end_td.total_seconds() < 0:
                        continue
                    if start_td.total_seconds() < 0:
                        start_td = timedelta(seconds=0)
                    
                    # 重组行
                    parts[1] = self._format_timedelta(start_td)
                    parts[2] = self._format_timedelta(end_td)
                    new_lines.append(','.join(parts))
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)


class VttSubtitleHandler(SubtitleHandler):
    """VTT 格式字幕处理 (WebVTT)"""
    
    @staticmethod
    def _parse_timedelta(time_str: str) -> Optional[timedelta]:
        """解析 VTT 时间格式：HH:MM:SS.mmm 或 MM:SS.mmm"""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                h, m, s_ms = parts
                s, ms = s_ms.split('.')
                return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))
            elif len(parts) == 2:
                m, s_ms = parts
                s, ms = s_ms.split('.')
                return timedelta(minutes=int(m), seconds=int(s), milliseconds=int(ms))
        except Exception:
            return None
    
    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """格式化为 VTT 时间格式"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def adjust_timestamps(self, start_time: float, end_time: float) -> None:
        """调整 VTT 字幕时间戳"""
        if start_time <= 0 and end_time <= 0:
            return
        
        front_td = timedelta(seconds=start_time)
        end_threshold_s = end_time if end_time > 0 else float('inf')
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是时间行
            if ' --> ' in line:
                times = line.split(' --> ')
                if len(times) == 2:
                    start_str = times[0].strip()
                    end_str = times[1].strip().split()[0]  # 去除可能的位置信息
                    
                    start_td = self._parse_timedelta(start_str)
                    end_td = self._parse_timedelta(end_str)
                    
                    if start_td is None or end_td is None:
                        new_lines.append(line)
                        i += 1
                        continue
                    
                    # 应用时间调整逻辑
                    if end_time > 0 and start_td.total_seconds() >= end_threshold_s:
                        # 跳过该字幕块
                        i += 1
                        while i < len(lines) and lines[i].strip() and ' --> ' not in lines[i]:
                            i += 1
                        continue
                    
                    if end_time > 0 and end_td.total_seconds() > end_threshold_s:
                        end_td = timedelta(seconds=end_threshold_s)
                    
                    start_td -= front_td
                    end_td -= front_td
                    
                    if end_td.total_seconds() < 0:
                        i += 1
                        while i < len(lines) and lines[i].strip() and ' --> ' not in lines[i]:
                            i += 1
                        continue
                    
                    if start_td.total_seconds() < 0:
                        start_td = timedelta(seconds=0)
                    
                    new_lines.append(f"{self._format_timedelta(start_td)} --> {self._format_timedelta(end_td)}\n")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
            
            i += 1
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)


class SubtitleHandlerFactory:
    """字幕处理器工厂"""
    
    _handlers = {
        'srt': SrtSubtitleHandler,
        'ass': AssSubtitleHandler,
        'ssa': AssSubtitleHandler,
        'vtt': VttSubtitleHandler,
        'webvtt': VttSubtitleHandler,
    }
    
    @classmethod
    def get_handler(cls, file_path: str) -> Optional[SubtitleHandler]:
        """根据文件后缀获取对应的处理器"""
        _, ext = os.path.splitext(file_path)
        ext = ext.lstrip('.').lower()
        
        handler_class = cls._handlers.get(ext)
        if handler_class:
            return handler_class(file_path)
        return None
    
    @classmethod
    def register_handler(cls, extension: str, handler_class):
        """注册新的处理器"""
        cls._handlers[extension.lower()] = handler_class


class CodecToFormatMapper:
    """FFmpeg codec 到输出格式的映射"""
    
    _codec_mapping = {
        # 文本格式
        'subrip': ('srt', 'srt'),
        'ass': ('ass', 'ass'),
        'ssa': ('ass', 'ssa'),
        'webvtt': ('webvtt', 'vtt'),
        'mov_text': ('mov_text', 'vtt'),
        'text': ('srt', 'srt'),
        'microdvd': ('microdvd', 'sub'),
        'srt': ('srt', 'srt'),
        'subrip_ext': ('srt', 'srt'),
        'cc_dec': ('srt', 'srt'),
    }
    
    @classmethod
    def get_output_format_and_ext(cls, codec_name: str) -> Tuple[str, str]:
        """
        根据 codec 获取输出格式和文件后缀
        :param codec_name: FFmpeg codec 名称
        :return: (ffmpeg_format, file_extension) 元组
        """
        codec_name = codec_name.lower().strip()
        
        if codec_name in cls._codec_mapping:
            return cls._codec_mapping[codec_name]
        
        # 默认降级为 srt
        print(f"⚠️ 未知字幕编码：{codec_name}，将使用 SRT 格式")
        return ('srt', 'srt')
    
    @classmethod
    def is_image_based_format(cls, codec_name: str) -> bool:
        """检查是否为图像类字幕格式"""
        image_formats = {'hdmv_pgs_subtitle', 'dvd_subtitle', 'xsub', 'dvb_subtitle'}
        return codec_name.lower().strip() in image_formats
