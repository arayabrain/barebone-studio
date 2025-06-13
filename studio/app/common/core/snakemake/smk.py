from dataclasses import dataclass
from typing import Dict, List, Union

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


class SmkParam(BaseModel):
    use_conda: bool
    cores: int
    forceall: bool
    forcetargets: bool
    lock: bool
    forcerun: List[ForceRun] = []
