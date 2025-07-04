import gc
from abc import ABC, abstractmethod
from typing import Optional

from studio.app.common.core.workflow.workflow import OutputPath


class BaseData(ABC):
    def __init__(self, file_name):
        self.file_name = file_name

    @abstractmethod
    def save_json(self, json_dir):
        pass

    @property
    def output_path(self) -> Optional[OutputPath]:
        return None

    def __del__(self):
        del self
        gc.collect()
