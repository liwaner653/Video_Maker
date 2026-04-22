import os
import shutil

from steps.base_step import BaseStep
from steps.context import BatchContext


class CleanupStep(BaseStep):
    @property
    def step_name(self): return "清理临时文件夹"

    def execute(self, context: BatchContext) -> bool:
        print("\n" + "="*70)
        print("开始执行清理步骤...")
        dirs_to_delete = set()
        for ctx in context.task_contexts:
            if ctx.thumb_dir: dirs_to_delete.add(ctx.thumb_dir)
            if ctx.audio_dir: dirs_to_delete.add(ctx.audio_dir)
            
        for path in dirs_to_delete:
            if os.path.exists(path):
                shutil.rmtree(path)
                print(f"🧹 已清理: {path}")
        return True