import os

from steps.base_step import BaseStep
from steps.context import TaskContext

class PrepareDirStep(BaseStep):
    @property
    def step_name(self): return "目录准备"

    def execute(self, context: TaskContext) -> bool:
        video_dir = os.path.dirname(context.task.video_path)
        
        context.thumb_dir = os.path.join(video_dir, f"thumbnails_{context.lang}")
        context.audio_dir = os.path.join(video_dir, f"audio_{context.lang}")
        context.subtitle_dir = os.path.join(video_dir, f"subtitles_{context.lang}")
        context.final_video_dir = os.path.join(video_dir, f"final_videos_{context.lang}")
        context.trimmed_video_dir = os.path.join(video_dir, f"trimmed_videos_{context.lang}")

        for d in [context.thumb_dir, context.audio_dir, context.subtitle_dir, context.final_video_dir, context.trimmed_video_dir]:
            os.makedirs(d, exist_ok=True)
        return True