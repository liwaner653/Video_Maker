import os

from steps.base_step import BaseStep
from steps.context import TaskContext

class PrepareDirStep(BaseStep):
    @property
    def step_name(self): return "目录准备"

    def execute(self, context: TaskContext) -> bool:
        video_dir = os.path.dirname(context.task.video_path)
        lang = context.lang
        
        # 需求7：加上语言标识
        context.thumb_dir = os.path.join(video_dir, f"thumbnails_{lang}")
        context.audio_dir = os.path.join(video_dir, f"audio_{lang}")
        context.subtitle_dir = os.path.join(video_dir, f"subtitles_{lang}")
        context.final_video_dir = os.path.join(video_dir, f"final_videos_{lang}")
        
        for d in [context.thumb_dir, context.audio_dir, context.subtitle_dir, context.final_video_dir]:
            os.makedirs(d, exist_ok=True)
        return True