import re
from enum import Enum

from studio.app.common.core.utils.file_reader import (
    ContentUnitReader,
    PaginatedFileReader,
)
from studio.app.dir_path import DIRPATH


class LogLevel(str, Enum):
    ALL = "ALL"
    INFO = "INFO"
    ERROR = "ERROR"
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class LogRecordReader(ContentUnitReader):
    """Log record reader that treats each log entry as a unit"""

    def __init__(self, levels: list[LogLevel], **kwargs) -> None:
        if LogLevel.ALL in levels:
            self.levels: list[bytes] = []
        else:
            self.levels: list[bytes] = [level.value.encode() for level in levels]

        self.start_pattern = re.compile(
            rb"(?=^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", re.MULTILINE
        )
        self.pattern = re.compile(
            rb"^(?P<asctime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) "
            rb"(?:\x1b\[\d+m)?(?P<levelprefix>\w+)(?:\x1b\[0m)?:?\s+"
            rb"\[(?P<name>[^\]]+)\] "
            rb"(?P<funcName>\w+)\(\):(?P<lineno>\d+) - "
            rb"(?P<message>.*)",
            re.DOTALL,
        )
        self.exclude_pattern: list[bytes] = [b"GET /logs", b"OPTIONS /logs"]

    def is_unit_start(self, line: bytes) -> bool:
        return bool(self.start_pattern.match(line))

    def parse(self, content: bytes) -> dict:
        if not content:
            return {"raw": b"", "parsed": False}

        match = self.pattern.match(content)
        if not match:
            return {"raw": content, "parsed": False}

        components = match.groupdict()

        return {
            "timestamp": components["asctime"],
            "level": components["levelprefix"],
            "name": components["name"],
            "function": components["funcName"],
            "line": int(components["lineno"]),
            "message": components["message"],
            "raw": content,
            "parsed": True,
        }

    def validate(self, content: bytes) -> bool:
        if any([pattern in content for pattern in self.exclude_pattern]):
            return False

        unit_dict = self.parse(content)
        if not unit_dict["parsed"]:
            return False

        if self.levels:
            return unit_dict["level"] in self.levels

        return True


class LogReader(PaginatedFileReader):
    def __init__(
        self,
        file_path=DIRPATH.LOG_FILE_PATH,
        levels: list[LogLevel] = [],
        **kwargs,
    ):
        super().__init__(file_path, **kwargs)
        self.file_path = file_path
        self.unit_reader = LogRecordReader(levels=levels)
