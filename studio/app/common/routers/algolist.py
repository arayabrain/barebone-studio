import inspect
from typing import Dict, List, ValuesView

from fastapi import APIRouter

from studio.app.common.core.snakemake.smk_utils import SmkInternalUtils
from studio.app.common.schemas.algolist import Algo, AlgoList, Arg, Return
from studio.app.const import NOT_DISPLAY_ARGS_LIST
from studio.app.wrappers import wrapper_dict

router = APIRouter()


class NestDictGetter:
    @classmethod
    def get_nest_dict(cls, parent_value, parent_key: str) -> Dict[str, Algo]:
        algo_dict = {}
        for key, value in parent_value.items():
            algo_dict[key] = {}
            if isinstance(value, dict) and "function" not in value:
                algo_dict[key]["children"] = cls.get_nest_dict(
                    value, cls._parent_key(parent_key, key)
                )
            else:
                sig = inspect.signature(value["function"])
                returns_list = None
                if sig.return_annotation is not inspect._empty:
                    returns_list = cls._return_list(sig.return_annotation.items())

                # get conda env infomations
                conda_name = value.get("conda_name")
                if conda_name is None:
                    # If conda env is not used, always returns True.
                    conda_env_exists = True
                else:
                    conda_env_exists = SmkInternalUtils.verify_conda_env_exists(
                        conda_name
                    )

                algo_dict[key] = Algo(
                    args=cls._args_list(sig.parameters.values()),
                    returns=returns_list,
                    parameter=value["parameter"] if "parameter" in value else None,
                    path=cls._parent_key(parent_key, key),
                    conda_name=conda_name,
                    conda_env_exists=conda_env_exists,
                )

        return algo_dict

    @classmethod
    def _args_list(cls, arg_params: ValuesView[inspect.Parameter]) -> List[Arg]:
        return [
            Arg(
                name=x.name,
                type=x.annotation.__name__,
                isNone=x.default is None,
            )
            for x in arg_params
            if x.name not in NOT_DISPLAY_ARGS_LIST
        ]

    @classmethod
    def _return_list(cls, return_params: ValuesView[inspect.Parameter]) -> List[Return]:
        return [Return(name=k, type=v.__name__) for k, v in return_params]

    @classmethod
    def _parent_key(cls, parent_key: str, key: str) -> str:
        if parent_key == "":
            return key
        else:
            return f"{parent_key}/{key}"


@router.get("/algolist", response_model=AlgoList, tags=["others"])
async def get_algolist() -> Dict[str, Algo]:
    """_summary_

    Returns:
        {
            'caiman': {
                'children': {
                    'caiman_mc' : {
                        'args': ['images', 'timeseries'],
                        'return': ['images'],
                        'path': 'caiman/caiman_mc',
                        'conda_name': 'conda_name',
                        'conda_env_exists': True,
                    },
                    'caiman_cnmf': {
                        'args': ['images', 'timeseries'],
                        'return': ['images'],
                        'path': 'caiman/caiman_cnmf',
                        'conda_name': 'conda_name',
                        'conda_env_exists': True,
                    }
                }
            }
        }
    """

    return NestDictGetter.get_nest_dict(wrapper_dict, "")
