import os
import shutil
import subprocess

from steps.base_step import BaseStep
from steps.context import BatchContext
from steps.config import GIT_REPO_PATH


class PostProcessingStep(BaseStep):
    @property
    def step_name(self): return "后处理步骤"

    def execute(self, context: BatchContext) -> bool:
        print("\n" + "="*70)
        print("开始执行后处理步骤...")
        
        # 第一步：删除临时文件夹
        if not self._cleanup_temp_dirs(context):
            return False
        
        # 第二步：上传subtitles文件夹至git
        if not self._upload_subtitles_to_git(context):
            return False
        
        return True
    
    def _cleanup_temp_dirs(self, context: BatchContext) -> bool:
        """删除临时文件夹"""
        print("\n[1/2] 清理临时文件夹...")
        dirs_to_delete = set()
        for ctx in context.task_contexts:
            #if ctx.thumb_dir: dirs_to_delete.add(ctx.thumb_dir)
            if ctx.audio_dir: dirs_to_delete.add(ctx.audio_dir)
            
        for path in dirs_to_delete:
            if os.path.exists(path):
                shutil.rmtree(path)
                print(f"🧹 已清理: {path}")
        return True
    
    def _upload_subtitles_to_git(self, context: BatchContext) -> bool:
        """上传subtitles文件夹至git"""
        print("\n[2/2] 上传subtitles文件夹至git...")
        git_repo_path = GIT_REPO_PATH
        
        if not os.path.exists(git_repo_path):
            print(f"❌ Git仓库路径不存在: {git_repo_path}")
            return False
        
        for ctx in context.task_contexts:
            if not ctx.subtitle_dir or not os.path.exists(ctx.subtitle_dir):
                print(f"⚠️ 跳过 {ctx.video_name}：subtitle_dir不存在或为空")
                continue
            
            # 获取subtitle_dir的父目录名称
            subtitle_parent_dir = os.path.dirname(ctx.subtitle_dir)
            parent_dir_name = os.path.basename(subtitle_parent_dir)
            
            # 构建新的文件夹名称: "parent_folder_name_language"
            new_folder_name = f"{parent_dir_name} {ctx.lang}"
            new_path = os.path.join(git_repo_path, new_folder_name)
            
            try:
                # 如果目标路径已存在，先删除
                if os.path.exists(new_path):
                    shutil.rmtree(new_path)
                    print(f"🗑️  已删除已存在的文件夹: {new_path}")
                
                # 移动subtitles文件夹到git仓库
                shutil.move(ctx.subtitle_dir, new_path)
                print(f"📦 已移动: {ctx.subtitle_dir} -> {new_path}")
                
                # 执行git命令
                subprocess.run(["git", "add", new_folder_name], check=True, cwd=git_repo_path)
                print(f"✅ git add: {new_folder_name}")
                
                subprocess.run(["git", "commit", "-m", new_folder_name], check=True, cwd=git_repo_path)
                print(f"✅ git commit: {new_folder_name}")
                
            except subprocess.CalledProcessError as e:
                print(f"❌ Git命令执行失败 ({new_folder_name}): {e}")
                return False
            except Exception as e:
                print(f"❌ 处理 {ctx.video_name} 时出错: {e}")
                return False
        
        return True
