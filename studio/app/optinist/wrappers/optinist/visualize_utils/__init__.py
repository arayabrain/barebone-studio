from studio.app.optinist.wrappers.optinist.visualize_utils.fluo_from_hdf5 import (
    fluo_from_hdf5,
)
from studio.app.optinist.wrappers.optinist.visualize_utils.microscope_to_img import (
    microscope_to_img,
)
from studio.app.optinist.wrappers.optinist.visualize_utils.roi_fluo_from_hdf5 import (
    roi_fluo_from_hdf5,
)
from studio.app.optinist.wrappers.optinist.visualize_utils.roi_from_hdf5 import (
    roi_from_hdf5,
)
from studio.app.optinist.wrappers.optinist.visualize_utils.vacant_roi import vacant_roi

utils_wrapper_dict = {
    "microscope_to_img": {
        "function": microscope_to_img,
        "conda_name": "microscope",
    },
    "fluo_from_hdf5": {
        "function": fluo_from_hdf5,
        "conda_name": "optinist",
    },
    "roi_from_hdf5": {
        "function": roi_from_hdf5,
        "conda_name": "optinist",
    },
    "roi_fluo_from_hdf5": {
        "function": roi_fluo_from_hdf5,
        "conda_name": "optinist",
    },
    "vacant_roi": {
        "function": vacant_roi,
        "conda_name": "optinist",
    },
}
