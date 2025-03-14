from sqlmodel import Session, insert

from studio.app.optinist.dataclass.stat import StatData
from studio.app.optinist.models import Cell as CellModel
from studio.app.optinist.models import Experiment as ExperimentModel


def bulk_insert_cells(
    db: Session,
    experiment_uid: int,
    stat_data: StatData,
):
    experiment = db.query(ExperimentModel).get(experiment_uid)
    assert experiment is not None, "Experiment not found"

    db.query(CellModel).filter(CellModel.experiment_uid == experiment_uid).delete()

    p_value_resp = StatData.fill_nan_with_none(stat_data.p_value_resp)
    p_value_sel = StatData.fill_nan_with_none(stat_data.p_value_sel)
    p_value_ori_resp = StatData.fill_nan_with_none(stat_data.p_value_ori_resp)
    p_value_ori_sel = StatData.fill_nan_with_none(stat_data.p_value_ori_sel)
    dir_vector_angle = StatData.fill_nan_with_none(stat_data.dir_vector_angle)
    ori_vector_angle = StatData.fill_nan_with_none(stat_data.ori_vector_angle)
    oi = StatData.fill_nan_with_none(stat_data.oi)
    di = StatData.fill_nan_with_none(stat_data.di)
    dsi = StatData.fill_nan_with_none(stat_data.dsi)
    osi = StatData.fill_nan_with_none(stat_data.osi)
    r_best_dir = StatData.fill_nan_with_none(stat_data.r_best_dir)
    dir_tuning_width = StatData.fill_nan_with_none(stat_data.dir_tuning_width)
    ori_tuning_width = StatData.fill_nan_with_none(stat_data.ori_tuning_width)
    sf_bandwidth = StatData.fill_nan_with_none(stat_data.sf_bandwidth)
    best_sf = StatData.fill_nan_with_none(stat_data.best_sf)
    sf_si = StatData.fill_nan_with_none(stat_data.sf_si)

    db.execute(
        insert(CellModel),
        [
            {
                "cell_number": i,
                "experiment_uid": experiment_uid,
                "statistics": {
                    "p_value_resp": p_value_resp[i],
                    "p_value_sel": p_value_sel[i],
                    "p_value_ori_resp": p_value_ori_resp[i],
                    "p_value_ori_sel": p_value_ori_sel[i],
                    "dir_vector_angle": dir_vector_angle[i],
                    "ori_vector_angle": ori_vector_angle[i],
                    "oi": oi[i],
                    "di": di[i],
                    "dsi": dsi[i],
                    "osi": osi[i],
                    "r_best_dir": r_best_dir[i],
                    "dir_tuning_width": dir_tuning_width[i],
                    "ori_tuning_width": ori_tuning_width[i],
                    "sf_bandwidth": sf_bandwidth[i],
                    "best_sf": best_sf[i],
                    "sf_si": sf_si[i],
                },
            }
            for i in range(stat_data.ncells)
        ],
    )
    db.flush()
    return True


def bulk_delete_cells(db: Session, experiment_uid: int):
    db.query(CellModel).filter(CellModel.experiment_uid == experiment_uid).delete()

    db.flush()
    return True
