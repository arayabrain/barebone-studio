from studio.app.optinist.wrappers.optinist.basic_neural_analysis import (
    basic_neural_analysis_wrapper_dict,
)
from studio.app.optinist.wrappers.optinist.dimension_reduction import (
    dimension_reduction_wrapper_dict,
)
from studio.app.optinist.wrappers.optinist.neural_decoding import (
    neural_decoding_wrapper_dict,
)
from studio.app.optinist.wrappers.optinist.neural_population_analysis import (
    neural_population_analysis_wrapper_dict,
)
from studio.app.optinist.wrappers.optinist.visualize_utils import utils_wrapper_dict

optinist_wrapper_dict = {
    "OptiNiSt": {
        "Basic neural analysis": basic_neural_analysis_wrapper_dict,
        "Dimension reduction": dimension_reduction_wrapper_dict,
        "Neural decoding": neural_decoding_wrapper_dict,
        "Neural population analysis": neural_population_analysis_wrapper_dict,
        "Utils": utils_wrapper_dict,
    }
}
