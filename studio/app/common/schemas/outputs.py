from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Union


@dataclass
class PlotMetaData:
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    title: Optional[str] = None

    def value_present_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class OutputData:
    data: Union[List, Dict, str]
    columns: List[str] = None
    index: List[str] = None
    meta: Optional[PlotMetaData] = None


@dataclass
class JsonTimeSeriesData(OutputData):
    xrange: list = None
    std: Dict[str, dict] = None


@dataclass
class TextPosition:
    pos: Optional[int] = None
    start_of_line: Optional[int] = None
    end_of_line: Optional[int] = None


@dataclass
class PaginatedLineResult:
    next_offset: int
    prev_offset: int
    data: "list[str]"
