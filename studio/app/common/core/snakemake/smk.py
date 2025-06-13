from dataclasses import dataclass
from typing import Dict, Union

from pydantic import BaseModel


@dataclass
class Rule:
    input: list
    return_arg: Union[str, Dict[str, str]]
    params: dict
    output: str
    type: str
    nwbfile: dict = None
    hdf5Path: str = None
    matPath: str = None
    path: str = None


@dataclass
class FlowConfig:
    rules: Dict[str, Rule]
    last_output: list
    nwb_template: dict


class ForceRun(BaseModel):
    nodeId: str
    name: str


@dataclass
class SmkParam:
    use_conda: bool
    cores: int
    lock: bool
