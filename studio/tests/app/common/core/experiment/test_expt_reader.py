from studio.app.common.core.experiment.experiment import ExptConfig, ExptFunction
from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.workflow.workflow import NodeRunStatus

workspace_id = "default"
unique_id = "0123"


def test_read():
    exp_config = ExptConfigReader.read(workspace_id, unique_id)

    assert isinstance(exp_config, ExptConfig)
    assert isinstance(exp_config.workspace_id, str)
    assert isinstance(exp_config.unique_id, str)
    assert isinstance(exp_config.started_at, str)
    assert isinstance(exp_config.name, str)

    assert isinstance(exp_config.function, dict)
    assert isinstance(exp_config.function["input_0"].unique_id, str)
    assert isinstance(exp_config.function["input_0"].name, str)
    assert isinstance(exp_config.function["input_0"].success, str)


def test_read_function():
    func_config = {
        "sample1": {
            "unique_id": "a",
            "name": "a",
            "success": NodeRunStatus.SUCCESS.value,
            "hasNWB": False,
            "started_at": "2023-07-04 12:52:06",
            "finished_at": "2023-07-04 12:52:19",
            "outputPaths": {
                "Vcorr": {
                    "max_index": 1,
                    "path": (
                        "/tmp/optinist/output/default/838d4234/",
                        "suite2p_roi_m6v8o3dctg/Vcorr.json",
                    ),
                    "type": "images",
                },
                "all_roi": {
                    "max_index": None,
                    "path": (
                        "/tmp/optinist/output/default/838d4234/",
                        "suite2p_roi_m6v8o3dctg/all_roi.json",
                    ),
                    "type": "roi",
                },
            },
        }
    }

    function = ExptConfigReader.read_function(func_config)

    assert isinstance(function, dict)
    assert isinstance(function["sample1"], ExptFunction)
