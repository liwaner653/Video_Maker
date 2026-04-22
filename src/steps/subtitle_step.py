
from steps.base_step import BaseStep
from steps.context import TaskContext
from steps.extract_subtitles import extract_mkv_subtitles
from steps.generate_subtitles import generate_subtitles


class SubtitleStep(BaseStep):
    @property
    def step_name(self): return "字幕生成"

    def execute(self, context: TaskContext) -> bool:
        task = context.task
        cf, cb = (task.trim.cut_front_seconds, task.trim.cut_back_seconds) if task.trim else (0.0, 0.0)
        srt_index = task.subtitle.srt_stream_index if task.subtitle else -1

        if srt_index < 0:
            srt_path = generate_subtitles(
                audio_path=context.audio_path,
                output_dir=context.subtitle_dir,
                model='turbo',
                subtitle_lang=task.subtitle.subtitle_lang if task.subtitle else "de"
            )
        else:
            subtitles = extract_mkv_subtitles(task.video_path, context.subtitle_dir, [srt_index], cf, cb)
            srt_path = subtitles[0] if subtitles else None

        # 需求6：如果字幕生成失败或被判断为无效，不中断，赋空值继续
        if srt_path:
            context.srt_path = srt_path
        else:
            print("⚠️ 字幕处理失败或文件无效，将跳过字幕烧录。")
            context.srt_path = "" 
        return True # 始终返回True，允许后续合成执行