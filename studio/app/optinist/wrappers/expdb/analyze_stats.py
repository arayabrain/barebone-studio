from studio.app.optinist.core.nwb.nwb import NWBDATASET
from studio.app.optinist.dataclass import ExpDbData, StatData
from studio.app.optinist.wrappers.expdb.anova1_mult import anova1_mult
from studio.app.optinist.wrappers.expdb.curvefit_tuning import curvefit_tuning
from studio.app.optinist.wrappers.expdb.stat_file_convert import stat_file_convert
from studio.app.optinist.wrappers.expdb.vector_average import vector_average


def analyze_stats(
    expdb: ExpDbData, output_dir: str, params: dict = None, **kwargs
) -> dict(stat=StatData):
    stat = stat_file_convert(expdb, output_dir, params).get("stat")
    stat = anova1_mult(stat, output_dir, params).get("stat")
    stat = vector_average(stat, output_dir, params).get("stat")
    stat = curvefit_tuning(stat, output_dir, params).get("stat")

    return {
        "stat": stat,
        "tuning_curve": stat.tuning_curve,
        "tuning_curve_polar": stat.tuning_curve_polar,
        "direction_responsivity_ratio": stat.direction_responsivity_ratio,
        "orientation_responsivity_ratio": stat.orientation_responsivity_ratio,
        "direction_selectivity": stat.direction_selectivity,
        "orientation_selectivity": stat.orientation_selectivity,
        "best_responsivity": stat.best_responsivity,
        "preferred_direction": stat.preferred_direction,
        "preferred_orientation": stat.preferred_orientation,
        "direction_tuning_width": stat.direction_tuning_width,
        "orientation_tuning_width": stat.orientation_tuning_width,
        "sf_selectivity": stat.stim_selectivity,
        "sf_responsivity": stat.stim_responsivity,
        "sf_responsivity_ratio": stat.sf_responsivity_ratio,
        "spatial_frequency_tuning": stat.sf_tuning_curve,
        "nwbfile": {NWBDATASET.ORISTATS: stat.nwb_dict_all},
    }
