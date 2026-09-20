#!/usr/bin/env python3
# main.py
import sys
import argparse

from steps.post_processing_step import PostProcessingStep
from steps.context import BatchContext
from steps.video_trim_step import VideoTrimStep
from steps.video_merge_step import VideoMergeStep
from steps.extract_audio_step import AudioStep
from steps.extract_audio.audio_trim_step import AudioTrimStep
from steps.extract_subtitles import ExtractSubtitlesStep
from steps.input_parser import ParseJsonStep
from steps.prepare_dir_step import PrepareDirStep
from steps.subtitle.generate_subtitles_step import GenerateSubtitlesStep
from steps.calc_trim_segments import TrimSegmentsStep
from steps.srt_combination_step import SrtCombinationStep
from steps import config


def main(json_path):
    batch_ctx = BatchContext(json_path=json_path)
    
    # 阶段1：解析
    if not ParseJsonStep().run(batch_ctx):
        sys.exit(1)
        
    video_pipeline = [PrepareDirStep(), 
                      TrimSegmentsStep(),
                      AudioStep(), 
                      ExtractSubtitlesStep(),
                      GenerateSubtitlesStep(), 
                      SrtCombinationStep(debug=config.DEBUG),
                      AudioTrimStep(),
                      VideoTrimStep(),
                      VideoMergeStep()]
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

    # 阶段3：后处理（清理临时文件和上传subtitles）
    if not config.DEBUG:
        PostProcessingStep().run(batch_ctx)

if __name__ == "__main__":
    main(r"D:\sysu\10_myself\8_projects\Video_Maker\test\16h_srt\json.json")
