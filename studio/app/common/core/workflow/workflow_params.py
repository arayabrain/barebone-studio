from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.config_handler import ConfigReader
from studio.app.common.core.utils.filepath_finder import find_param_filepath
from studio.app.optinist.schemas.nwb import NWBParams
from studio.app.common.core.snakemake.smk import SmkParam

logger = AppLogger.get_logger()


def get_typecheck_params(message_params, name):
    default_params = ConfigReader.read(find_param_filepath(name))
    if message_params != {} and message_params is not None:
        params = check_types(nest2dict(message_params), default_params)
    else:
        params = default_params

    if name == "nwb":
        try:
            validated_params = NWBParams(**params)
            return validated_params
        except Exception as e:
            logger.error(f"Error converting params to NWBParams: {e}")
            return params
    elif name == "snakemake":
        try:
            validated_params = SmkParam(**params)
            return validated_params
        except Exception as e:
            logger.error(f"Error converting params to SmkParam: {e}")
            return params
    
    return params


def check_types(params, default_params):
    faq_url = "https://github.com/oist/optinist/wiki/FAQ"
    for key in params.keys():
        if key not in default_params:
            logger.error(f"Invalid Workflow yaml param: [{key}]. See {faq_url}")
            raise KeyError("Workflow yaml error, see FAQ")
        if isinstance(params[key], dict):
            params[key] = check_types(params[key], default_params[key])
        else:
            if not isinstance(type(params[key]), type(default_params[key])):
                data_type = type(default_params[key])
                p = params[key]
                if isinstance(data_type, str):
                    params[key] = str(p)
                elif isinstance(data_type, float):
                    params[key] = float(p)
                elif isinstance(data_type, int):
                    params[key] = int(p)

    return params


def nest2dict(value):
    nwb_dict = {}
    for _k, _v in value.items():
        if _v["type"] == "child":
            nwb_dict[_k] = _v["value"]
        elif _v["type"] == "parent":
            nwb_dict[_k] = nest2dict(_v["children"])

    return nwb_dict
