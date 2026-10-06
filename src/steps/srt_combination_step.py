import os
import re
from datetime import timedelta
from typing import List, Optional

from steps.base_step import BaseStep
from steps.context import TaskContext, TrimSegment

# 字幕文件最小大小限制（20KB），用于过滤无效字幕文件
MIN_SRT_FILE_SIZE_KB = 20
MIN_SRT_FILE_SIZE_BYTES = MIN_SRT_FILE_SIZE_KB * 1024


def parse_srt_time(time_str: str) -> timedelta:
    """
    将SRT时间字符串解析为timedelta对象
    
    Args:
        time_str: SRT格式的时间字符串，如 "00:01:23,456"
    
    Returns:
        对应的timedelta对象
    """
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split(',')
    return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))


def format_srt_time(td: timedelta) -> str:
    """
    将timedelta对象格式化为SRT时间字符串
    
    Args:
        td: timedelta对象
    
    Returns:
        SRT格式的时间字符串，如 "00:01:23,456"
    """
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_srt_blocks(srt_content: str) -> List[dict]:
    """
    解析SRT字幕内容为字幕块列表
    
    Args:
        srt_content: SRT格式的字幕文件内容
    
    Returns:
        字幕块列表，每个块包含'start'(开始时间), 'end'(结束时间), 'text'(字幕文本)
    """
    # 按空行分割字幕块
    blocks = re.split(r'\n\n+', srt_content.strip())
    parsed_blocks = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        # 有效的SRT块至少需要3行：序号、时间线、字幕文本
        if len(lines) >= 3:
            try:
                index = int(lines[0])  # 字幕序号（暂不使用）
                times = lines[1].split(' --> ')
                if len(times) == 2:
                    start_td = parse_srt_time(times[0].strip())
                    end_td = parse_srt_time(times[1].strip())
                    text = '\n'.join(lines[2:])  # 字幕文本可能跨多行
                    parsed_blocks.append({
                        'start': start_td,
                        'end': end_td,
                        'text': text
                    })
            except Exception:
                # 解析失败时跳过该块
                continue
    return parsed_blocks


def write_srt_blocks(blocks: List[dict], output_path: str) -> None:
    """
    将字幕块列表写入SRT文件
    
    Args:
        blocks: 字幕块列表
        output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, block in enumerate(blocks, 1):
            start_str = format_srt_time(block['start'])
            end_str = format_srt_time(block['end'])
            f.write(f"{i}\n")              # 字幕序号
            f.write(f"{start_str} --> {end_str}\n")  # 时间线
            f.write(f"{block['text']}\n\n")  # 字幕文本（末尾空行分隔）


def adjust_extracted_srt(srt_path: str, segments: List[TrimSegment], output_path: str) -> bool:
    """
    调整从原始视频提取的字幕时间轴，使其匹配剪辑后的片段
    
    当从完整视频中提取字幕后，需要根据剪辑片段调整时间轴：
    1. 只保留落在剪辑片段范围内的字幕
    2. 将字幕时间偏移到新的时间轴起点
    3. 跳过没有字幕的片段时间
    
    Args:
        srt_path: 原始字幕文件路径
        segments: 剪辑片段列表
        output_path: 输出调整后字幕的路径
    
    Returns:
        成功返回True，失败返回False
    """
    if not os.path.exists(srt_path):
        return False
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = parse_srt_blocks(content)
    if not blocks:
        return False
    
    adjusted_blocks = []
    
    if not segments:
        return False
    
    # offset 针对整个视频，初始值为第一个 segment 的 start_time
    offset = timedelta(seconds=segments[0].start_time)
    
    block_index = 0
    num_blocks = len(blocks)
    
    for seg in segments:
        segment_start = seg.start_time
        segment_end = seg.end_time
        segment_duration = timedelta(seconds=segment_end - segment_start)
        
        if not seg.audio:
            offset += segment_duration
        else:
            seg_start_td = timedelta(seconds=segment_start)
            seg_end_td = timedelta(seconds=segment_end)
            
            while block_index < num_blocks:
                block = blocks[block_index]
                block_start = block['start']
                block_end = block['end']
                
                # 检查 block 是否与当前 segment 有交集
                if (block_start >= seg_start_td and block_start <= seg_end_td) or \
                   (block_end >= seg_start_td and block_end <= seg_end_td):
                    adjusted_start = block_start - offset
                    adjusted_end = block_end - offset
                    
                    if adjusted_end.total_seconds() > 0:
                        if adjusted_start.total_seconds() < 0:
                            adjusted_start = timedelta(seconds=0)
                        
                        adjusted_blocks.append({
                            'start': adjusted_start,
                            'end': adjusted_end,
                            'text': block['text']
                        })
                    block_index += 1
                elif block_end < seg_start_td:
                    # block 在当前 segment 之前，跳过
                    block_index += 1
                else:
                    # block 在当前 segment 之后，停止处理当前 segment
                    break
    
    if adjusted_blocks:
        write_srt_blocks(adjusted_blocks, output_path)
        return True
    return False


def combine_segment_srt(segments: List[TrimSegment], output_path: str) -> bool:
    """
    将多个片段的字幕文件合并为一个完整的字幕文件
    
    当多个片段各自有独立的字幕文件时，需要将它们合并：
    1. 依次读取每个片段的字幕文件
    2. 将字幕时间依次偏移，保证时间轴连续
    3. 合并所有字幕块并写入输出文件
    
    注意：本函数只负责合并，源字幕文件的删除由调用方在产物校验通过后执行。
    
    Args:
        segments: 剪辑片段列表（包含字幕路径信息）
        output_path: 合并后字幕文件的输出路径
    
    Returns:
        成功返回True，失败返回False
    """
    combined_blocks = []
    offset = timedelta(seconds=0)  # 时间偏移量，初始为0
    
    for seg in segments:
        segment_duration = timedelta(seconds=seg.end_time - seg.start_time)
        
        if seg.srt and seg.srt_path and os.path.exists(seg.srt_path):
            with open(seg.srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            blocks = parse_srt_blocks(content)
            
            for block in blocks:
                adjusted_block = {
                    'start': block['start'] + offset,
                    'end': block['end'] + offset,
                    'text': block['text']
                }
                combined_blocks.append(adjusted_block)
        
        offset += segment_duration
    
    if combined_blocks:
        write_srt_blocks(combined_blocks, output_path)
        return True
    return False


class SrtCombinationStep(BaseStep):
    """
    字幕合并与时间轴调整步骤
    
    负责处理视频字幕的合并和时间轴调整，支持三种场景：
    1. 多个片段各有独立字幕文件 → 合并字幕
    2. 单个片段有生成的字幕文件 → 直接使用
    3. 从完整视频提取的字幕 → 根据剪辑片段调整时间轴
    
    处理完成后将结果字幕路径存入context.srt_path
    """
    
    def __init__(self, debug: bool = False):
        """
        Args:
            debug: 是否开启调试模式（跳过文件大小检查）
        """
        self.debug = debug
    
    @property
    def step_name(self) -> str:
        return "字幕合并与时间轴调整"
    
    def execute(self, context: TaskContext) -> bool:
        """
        将字幕归一化到最终产物 context.final_srt_path
        
        进入本步骤时字幕有三种互斥的来源形态：
        1. 逐片段生成的字幕（各 seg.srt_path 非空）→ 合并为最终产物
        2. 从视频提取的字幕（srt_stream_index>=0）且有剪辑片段 → 调整时间轴
        3. 字幕已是最终产物（提取后无需调整 / 完整音频whisper）→ 直通
        
        Args:
            context: 任务上下文，包含剪辑片段列表和字幕路径信息
        
        Returns:
            始终返回True（失败时会清空context.srt_path）
        """
        task = context.task
        output_srt_path = context.final_srt_path

        # check_exist：最终产物已存在则直接复用
        if task.subtitle and task.subtitle.check_exist and os.path.exists(output_srt_path):
            context.srt_path = output_srt_path
            print(f"⏭️ 跳过字幕合并（check_exist=true，文件已存在）: {output_srt_path}")
            return True

        # 逐片段生成字幕的源文件列表（whisper场景）
        segment_srt_paths = [
            seg.srt_path for seg in context.trim_segments
            if seg.srt and seg.srt_path
        ]

        # 没有任何字幕源
        if not context.srt_path and not segment_srt_paths:
            print("⚠️ 没有可处理的字幕文件")
            context.srt_path = ""
            return True

        success = False

        if segment_srt_paths:
            # 形态1：片段字幕 → 合并
            success = combine_segment_srt(context.trim_segments, output_srt_path)
        elif context.srt_stream_index >= 0 and any(seg.srt for seg in context.trim_segments):
            # 形态2：提取字幕 + 有剪辑片段 → 调整时间轴（临时文件原子替换，避免残留污染）
            print("📝 调整提取字幕的时间轴...")
            tmp_srt_path = output_srt_path + ".tmp"
            success = adjust_extracted_srt(context.srt_path, context.trim_segments, tmp_srt_path)
            if success:
                os.replace(tmp_srt_path, output_srt_path)
            elif os.path.exists(tmp_srt_path):
                os.remove(tmp_srt_path)
        elif os.path.abspath(context.srt_path) == os.path.abspath(output_srt_path):
            # 形态3：字幕已是最终产物（提取无需调整 / 完整音频whisper）→ 直通
            print("📝 字幕已是最终产物，无需调整时间轴")
            success = True

        # 结果校验
        if success and os.path.exists(output_srt_path):
            file_size = os.path.getsize(output_srt_path)
            print(f"📊 字幕文件大小: {file_size / 1024:.2f} KB")

            # 检查字幕文件大小是否达标（调试模式跳过检查）
            if self.debug or file_size >= MIN_SRT_FILE_SIZE_BYTES:
                context.srt_path = output_srt_path

                # 合并产物校验通过后，删除combine前的片段源字幕（最终产物自身除外）
                output_abs = os.path.abspath(output_srt_path)
                for src_path in segment_srt_paths:
                    if os.path.exists(src_path) and os.path.abspath(src_path) != output_abs:
                        try:
                            os.remove(src_path)
                            print(f"🗑️ 删除源字幕文件: {src_path}")
                        except Exception as e:
                            print(f"⚠️ 删除源字幕文件失败 {src_path}: {e}")

                if self.debug:
                    print(f"✅ 调试模式：跳过文件大小检查，字幕处理完成: {context.srt_path}")
                else:
                    print(f"✅ 字幕处理完成: {context.srt_path}")
            else:
                context.srt_path = ""
                print(f"⚠️ 字幕文件小于 {MIN_SRT_FILE_SIZE_KB}KB，将跳过字幕合成")
        else:
            context.srt_path = ""
            print("⚠️ 字幕处理失败，将跳过字幕合成")

        return True
