#  decoding neural activity by GLM
#  input:  A:matrix[num_cell x timeseries ]   B:timeseries(behavior)[1 x timeseries]
#  Generalized linear modeling using statsmodels
#
#  https://www.statsmodels.org/stable/glm.html

from studio.app.common.core.experiment.experiment import ExptOutputPathIds
from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass import BarData, HTMLData, ScatterData
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass import BehaviorData, FluoData, IscellData
from studio.app.optinist.wrappers.optinist.utils import param_check, standard_norm

logger = AppLogger.get_logger()


def GLM(
    neural_data: FluoData,
    behaviors_data: BehaviorData,
    output_dir: str,
    iscell: IscellData = None,
    params: dict = None,
    **kwargs,
) -> dict():
    # modules specific to function
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm

    function_id = ExptOutputPathIds(output_dir).function_id
    logger.info("start glm: %s", function_id)

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

    Y = Y[:, IOparams["target_index"]].reshape(-1, 1)

    # preprocessing
    tX = standard_norm(X, IOparams["standard_x_mean"], IOparams["standard_x_std"])
    tY = standard_norm(Y, IOparams["standard_y_mean"], IOparams["standard_y_std"])

    params = param_check(params["GLM"])

    # calculate GLM
    tX = pd.DataFrame(tX)
    tY = pd.DataFrame(tY)

    if params["add_constant"]:
        tX = sm.add_constant(tX, prepend=False)

    # set family & link
    if params["family"] in ["Poisson", "NegativeBinomial"] or params["link"] in [
        "log",
        "reciprocal",
    ]:
        if np.any(tY <= 0):
            logger.warning(
                "Non-positive values detected in Y."
                "This may cause issues with the chosen family/link."
            )
            logger.warning("Consider using a different family/link combination.")

    family_class = getattr(sm.families, params["family"])
    link_class = getattr(sm.genmod.families.links, params["link"])

    if link_class in family_class.links:
        link = link_class()
    else:
        link = family_class.links[0]()
        logger.warning(
            f"Invalid link: {params['link']} for {params['family']}."
            "Using {link.__class__.__name__}."
        )

    params.update({"family": family_class(link=link), "link": link})

    # model fit
    try:
        model = sm.GLM(tY, tX, **params)
        Res = model.fit()
    except ValueError as e:
        error_message = f"Error fitting GLM: {str(e)}."
        "Check for NaN or inf values. Ensure your family/link choice is appropriate"
        logger.error(error_message)
        logger.info(f"X shape: {tX.shape}, Y shape: {tY.shape}")
        logger.info(
            f"X contains NaN: {np.isnan(tX.values).any()},"
            "X contains inf: {np.isinf(tX.values).any()}"
        )
        logger.info(
            f"Y contains NaN: {np.isnan(tY.values).any()},"
            "Y contains inf: {np.isinf(tY.values).any()}"
        )
        logger.info(f"Y min: {np.min(tY.values)}, Y max: {np.max(tY.values)}")
        raise ValueError(error_message)

    # NWB追加
    nwbfile = {}
    nwbfile[NWBDATASET.POSTPROCESS] = {
        function_id: {
            "actual_predicted": np.array([Res._endog, Res.mu]).transpose(),
            "params": Res.params.values,
            "pvalues": Res.pvalues.values,
            "tvalues": Res.tvalues.values,  # z
            "aic": [Res.aic],
            "bic_llf": [Res.bic_llf],
            "llf": [Res.llf],  # log-Likelihood
            "pearson_chi2": [Res.pearson_chi2],
            "df_model": [Res.df_model],
            "df_resid": [Res.df_resid],
            "scale": [Res.scale],
            "mu": Res.mu,
            "endog": Res._endog,
        }
    }

    # main results for plot
    # plot should be reconsidered --- what they should be!
    info = {
        "actual_predicted": ScatterData(
            np.array([Res._endog, Res.mu]).transpose(), file_name="actual_predicted"
        ),
        "params": BarData(Res.params.values, file_name="params"),
        "textout": HTMLData(Res.summary().as_html(), file_name="textout"),
        "nwbfile": nwbfile,
    }

    return info
