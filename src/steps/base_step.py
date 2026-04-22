from abc import ABC, abstractmethod

# ===================== 2. 管道基类 =====================
class BaseStep(ABC):
    @property
    @abstractmethod
    def step_name(self) -> str: pass

    @abstractmethod
    def execute(self, context) -> bool: pass

    def run(self, context) -> bool:
        if not context.status: return False
        try:
            success = self.execute(context)
            if not success: context.status = False
            return success
        except Exception as e:
            context.status = False
            if hasattr(context, 'error_msg'):
                context.error_msg = f"{self.step_name}异常: {str(e)}"
                print(f"❌ {context.error_msg}")
            return False