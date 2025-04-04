from studio.app.common.core.experiment.experiment import ExptOutputPathIds
from studio.app.common.core.logger import AppLogger
from studio.app.common.dataclass import HeatMapData, ScatterData
from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass import FluoData, IscellData
from studio.app.optinist.wrappers.optinist.utils import standard_norm

logger = AppLogger.get_logger()


def Granger(
    neural_data: FluoData,
    output_dir: str,
    iscell: IscellData = None,
    params: dict = None,
    **kwargs,
) -> dict():
    # modules specific to function
    # from sklearn.preprocessing import StandardScaler
    import itertools

    import numpy as np
    from statsmodels.tsa.stattools import adfuller, coint, grangercausalitytests
    from tqdm import tqdm

    function_id = ExptOutputPathIds(output_dir).function_id
    logger.info("start granger: %s", function_id)

    neural_data = neural_data.data
    IOparams = params["I/O"]

    # data should be time x component matrix
    if IOparams["transpose"]:
        X = neural_data.transpose()
    else:
        X = neural_data

    if iscell is not None:
        iscell = iscell.data
        ind = np.where(iscell > 0)[0]
        X = X[:, ind]

    num_cell = X.shape[1]
    comb = list(itertools.permutations(range(num_cell), 2))  # combinations with dup
    num_comb = len(comb)

    # preprocessing
    tX = standard_norm(X, IOparams["standard_mean"], IOparams["standard_std"])

    # calculate dickey-fuller test
    # augmented dickey-fuller test
    # - if p val is large
    #   -> it cannot reject  there is a unit root
    # - small p-val means OK
    #   -> means this is not unit root process that it can apply Causality test

    adf = {
        "adf_teststat": np.zeros([num_cell], dtype="float64"),
        "adf_pvalue": np.zeros([num_cell], dtype="float64"),
        "adf_usedlag": np.zeros([num_cell], dtype="int"),
        "adf_nobs": np.zeros([num_cell], dtype="int"),
        "adf_critical_values": np.zeros([num_cell, 3], dtype="float64"),
        "adf_icbest": np.zeros([num_cell], dtype="float64"),
    }
    params = params["Granger"]  # remove nested dict

    if params["use_adfuller_test"]:
        logger.info("Running adfuller test ")

        for i in tqdm(range(num_cell)):
            tp = adfuller(tX[:, i], **params["adfuller"])

            adf["adf_teststat"][i] = tp[0]
            adf["adf_pvalue"][i] = tp[1]
            if len(tp) > 2:
                if isinstance(tp[2], (int, float)):
                    adf["adf_usedlag"][i] = tp[2]
                elif isinstance(tp[2], dict):
                    adf["adf_usedlag"][i] = tp[2].get("usedlag", 0)
                else:
                    adf["adf_usedlag"][i] = 0

            if len(tp) > 3:
                if isinstance(tp[3], (int, float)):
                    adf["adf_nobs"][i] = tp[3]
                elif isinstance(tp[3], dict):
                    adf["adf_nobs"][i] = tp[3].get("nobs", 0)
                else:
                    adf["adf_nobs"][i] = 0

            if len(tp) > 4:
                if isinstance(tp[4], dict):
                    adf["adf_critical_values"][i, :] = np.array(
                        [tp[4].get("1%", 0), tp[4].get("5%", 0), tp[4].get("10%", 0)]
                    )
                else:
                    adf["adf_critical_values"][i, :] = np.zeros(3)
            else:
                adf["adf_critical_values"][i, :] = np.zeros(3)

            if len(tp) > 5:
                adf["adf_icbest"][i] = tp[5] if isinstance(tp[5], (int, float)) else 0
            else:
                adf["adf_icbest"][i] = 0

    #  test for cointegration
    # augmented engle-granger two-step test
    # Test for no-cointegration of a univariate equation
    # if p val is small, the relation is cointegration
    # -> check this if ADF pval is large
    cit = {
        "cit_count_t": np.zeros([num_comb], dtype="float64"),
        "cit_pvalue": np.zeros([num_comb], dtype="int"),
        "cit_crit_value": np.zeros([num_comb, 3], dtype="float64"),
    }

    if params["use_coint_test"]:
        logger.info("Running cointegration test ")

        for i in tqdm(range(num_comb)):
            tp = coint(X[:, comb[i][0]], X[:, comb[i][1]], **params["coint"])
            if not np.isnan(tp[0]):
                cit["cit_count_t"][i] = tp[0]
            if not np.isnan(tp[1]):
                cit["cit_pvalue"][i] = tp[1]
            cit["cit_crit_value"][i, :] = tp[2]

    #  Granger causality
    logger.info("Running granger test ")

    if hasattr(params["Granger_maxlag"], "__iter__"):
        num_lag = len(params["Granger_maxlag"])
    else:
        num_lag = params["Granger_maxlag"]

    GC = {
        "gc_combinations": comb,
        "gc_ssr_ftest": np.zeros([num_comb, num_lag, 4], dtype="float64"),
        "gc_ssr_chi2test": np.zeros([num_comb, num_lag, 3], dtype="float64"),
        "gc_lrtest": np.zeros([num_comb, num_lag, 3], dtype="float64"),
        "gc_params_ftest": np.zeros([num_comb, num_lag, 4], dtype="float64"),
        "gc_OLS_restricted": [[0] * num_lag for i in range(num_comb)],
        "gc_OLS_unrestricted": [[0] * num_lag for i in range(num_comb)],
        "gc_OLS_restriction_matrix": [[0] * num_lag for i in range(num_comb)],
        "Granger_fval_mat": [np.zeros([num_cell, num_cell]) for i in range(num_lag)],
    }

    for i in tqdm(range(len(comb))):
        # The Null hypothesis for grangercausalitytests is
        # that the time series in the second column1,
        # does NOT Granger cause the time series in the first column0
        # column 1 -> column 0
        tp = grangercausalitytests(
            tX[:, [comb[i][0], comb[i][1]]],
            params["Granger_maxlag"],
            verbose=False,
            addconst=params["Granger_addconst"],
        )

        for j in range(len(tp)):  # number of lag
            GC["gc_ssr_ftest"][i, j, :] = tp[j + 1][0]["ssr_ftest"][
                0:4
            ]  # ssr based F test (F, pval, df_denom, df_num)
            GC["gc_ssr_chi2test"][i, j, :] = tp[j + 1][0]["ssr_chi2test"][
                0:3
            ]  # ssr based chi2test (chi2, pval, df)
            GC["gc_lrtest"][i, j, :] = tp[j + 1][0]["lrtest"][
                0:3
            ]  # likelihood ratio test (chi2, pval, df)
            GC["gc_params_ftest"][i, j, :] = tp[j + 1][0]["params_ftest"][
                0:4
            ]  # parameter F test (F, pval, df_denom, df_num)
            GC["gc_OLS_restricted"][i][j] = tp[j + 1][1][0]
            GC["gc_OLS_unrestricted"][i][j] = tp[j + 1][1][1]
            GC["gc_OLS_restriction_matrix"][i][j] = tp[j + 1][1][2]

            GC["Granger_fval_mat"][j][comb[i][0], comb[i][1]] = tp[j + 1][0][
                "ssr_ftest"
            ][0]

    GC["Granger_fval_mat"] = np.array(GC["Granger_fval_mat"])

    # main results for plot
    info = {}
    info["Granger_fval_mat_heatmap"] = HeatMapData(
        GC["Granger_fval_mat"][0], file_name="gfm_heatmap"
    )
    info["Granger_fval_mat_scatter"] = ScatterData(
        GC["Granger_fval_mat"][0], file_name="gfm"
    )

    # NWB追加
    nwbfile = {}
    nwbfile[NWBDATASET.POSTPROCESS] = {
        function_id: {
            "Granger_fval_mat": GC["Granger_fval_mat"][0],
            "gc_combinations": GC["gc_combinations"],
            "gc_ssr_ftest": GC["gc_ssr_ftest"],
            "gc_ssr_chi2test": GC["gc_ssr_chi2test"],
            "gc_lrtest": GC["gc_lrtest"],
            "gc_params_ftest": GC["gc_params_ftest"],
            "cit_pvalue": cit["cit_pvalue"],
            "adf_pvalue": adf["adf_pvalue"],
        }
    }

    info["nwbfile"] = nwbfile

    return info
