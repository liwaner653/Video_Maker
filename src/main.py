#!/usr/bin/env python3
# main.py
import sys
import argparse

from steps.cleanup_step import CleanupStep
from steps.context import BatchContext
from steps.video_compose_step import VideoComposeStep
from steps.extract_audio import AudioStep
from steps.generate_thumbnail import ThumbnailStep
from steps.get_subtitle_index import GetSubtitleIndexStep
from steps.input_parser import ParseJsonStep
from steps.prepare_dir_step import PrepareDirStep
from steps.subtitle_step import SubtitleStep
from steps.calc_trim_time import CalcTrimTimeStep


def main(json_path):
    batch_ctx = BatchContext(json_path=json_path)
    
    # 阶段1：解析
    if not ParseJsonStep().run(batch_ctx):
        sys.exit(1)
        
    video_pipeline = [PrepareDirStep(), 
                      CalcTrimTimeStep(),
                      ThumbnailStep(), 
                      AudioStep(), 
                      GetSubtitleIndexStep(),
                      SubtitleStep(), 
                      VideoComposeStep()]
    total = len(batch_ctx.task_contexts)
    
    # 阶段2：循环处理每个视频
    for idx, ctx in enumerate(batch_ctx.task_contexts, 1):
        print(f"\n【任务 {idx}/{total}】处理视频：{ctx.video_name}")
        print("-" * 50)
        for step in video_pipeline:
            if not step.run(ctx):
                print(f"🛑 任务在 [{step.step_name}] 终止: {ctx.error_msg}")
                break

    # 打印统计
    success = sum(1 for c in batch_ctx.task_contexts if c.status)
    print("\n" + "="*70 + f"\n📊 统计：成功 {success}/{total} \n" + "="*70)

    # 阶段3：统一清理
    # CleanupStep().run(batch_ctx)

if __name__ == "__main__":
    main(r"D:\waner\4_ani\programs\Video_Maker\test\one piece\json.json")