from studio.app.common.core.experiment.experiment import ExptOutputPathIds
from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass import BarData, ScatterData
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass import BehaviorData, FluoData, IscellData
from studio.app.optinist.wrappers.optinist.utils import standard_norm

logger = AppLogger.get_logger()


def CCA(
    neural_data: FluoData,
    behaviors_data: BehaviorData,
    output_dir: str,
    iscell: IscellData = None,
    params: dict = None,
    **kwargs,
) -> dict():
    import numpy as np
    from sklearn.cross_decomposition import CCA

    function_id = ExptOutputPathIds(output_dir).function_id
    logger.info("start cca: %s", function_id)

    neural_data = neural_data.data
    behaviors_data = behaviors_data.data
    IOparams = params["I/O"]

    # data should be time x component matrix
    if IOparams["transpose_x"]:
        X = neural_data.transpose()
    else:
        X = neural_data

    if IOparams["transpose_y"]:
        Y = behaviors_data.transpose()
    else:
        Y = behaviors_data

    assert (
        X.shape[0] == Y.shape[0]
    ), f"""
        neural_data and behaviors_data is not same dimension,
        neural.shape{X.shape}, behavior.shape{Y.shape}"""

    if iscell is not None:
        iscell = iscell.data
        ind = np.where(iscell > 0)[0]
        X = X[:, ind]

    # Handle target_index as either a list, slice notation, or single index
    target_idx = IOparams["target_index"]
    if isinstance(target_idx, str):
        target_idx = target_idx.strip("[] ")
        if ":" in target_idx:
            parts = [p.strip() for p in target_idx.split(":")]
            start = int(parts[0]) if parts[0] else None
            end = int(parts[1]) if parts[1] else None
            Y = Y[:, start:end]
        else:
            indices = list(map(int, target_idx.split(",")))
            Y = Y[:, indices]
    elif isinstance(target_idx, (list, np.ndarray)):
        indices = [int(i) for i in target_idx]
        Y = Y[:, indices]
    else:
        Y = Y[:, int(target_idx)]

    # preprocessing
    tX = standard_norm(X, IOparams["standard_x_mean"], IOparams["standard_x_std"])
    tY = standard_norm(Y, IOparams["standard_y_mean"], IOparams["standard_y_std"])

    # calculate CCA
    cca = CCA(**params["CCA"])
    projX, projY = cca.fit_transform(tX, tY)

    proj = np.concatenate([projX, projY], axis=1)

    # NWB追加
    nwbfile = {}
    nwbfile[NWBDATASET.POSTPROCESS] = {
        function_id: {
            "projectedNd": proj,
            "x_weights": cca.x_weights_,  # singular vectors
            "y_weights": cca.y_weights_,
            "x_loadings_": cca.x_rotations_,
            "y_loadings_": cca.x_rotations_,
            "coef": cca.coef_,
            "n_iter_": cca.n_iter_,
        }
    }

    info = {
        "projectedNd": ScatterData(proj, file_name="projectedNd"),
        "coef": BarData(cca.coef_.flatten(), file_name="coef"),
        "nwbfile": nwbfile,
    }

    return info
