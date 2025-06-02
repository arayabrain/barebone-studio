import os
import shutil

from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.dir_path import DIRPATH

workspace_id = "default"
unique_id = "0123"

output_test_dir = f"{DIRPATH.DATA_DIR}/output_test"

shutil.copytree(
    f"{output_test_dir}/{workspace_id}/{unique_id}",
    f"{DIRPATH.OUTPUT_DIR}/{workspace_id}/{unique_id}",
    dirs_exist_ok=True,
)


def test_get(client):
    response = client.get(f"/experiments/{workspace_id}")
    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, dict)
    assert isinstance(data[next(iter(data))], dict)


def test_delete(client):
    dirname = "delete_dir"
    dirpath = join_filepath([f"{DIRPATH.DATA_DIR}/output/{workspace_id}", dirname])
    os.makedirs(dirpath, exist_ok=True)

    # Add dummy experiment.yaml
    config_path = ExptConfigReader.get_experiment_yaml_path(workspace_id, dirname)
    with open(config_path, "w") as f:
        f.write("name: Dummy Experiment\nsuccess: success")

    assert os.path.exists(dirpath)
    response = client.delete(f"/experiments/{workspace_id}/{dirname}")
    assert response.status_code == 200
    assert not os.path.exists(dirpath)


def test_delete_list(client):
    uidList = ["delete_dir1", "delete_dir2"]
    for name in uidList:
        dirpath = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id, name])
        os.makedirs(dirpath, exist_ok=True)

        # Add dummy experiment.yaml
        config_path = ExptConfigReader.get_experiment_yaml_path(workspace_id, name)
        with open(config_path, "w") as f:
            f.write("name: Dummy Experiment\nsuccess: success")

        assert os.path.exists(dirpath)

    response = client.post(
        f"/experiments/delete/{workspace_id}", json={"uidList": uidList}
    )
    assert response.status_code == 200

    for name in uidList:
        dirpath = join_filepath([DIRPATH.OUTPUT_DIR, workspace_id, name])
        assert not os.path.exists(dirpath)


def test_download_config(client):
    response = client.get(f"/experiments/download/config/{workspace_id}/{unique_id}")
    assert response.status_code == 200
    assert response.url == "http://testserver/experiments/download/config/default/0123"


def test_expt_rename(client):
    origin_name = "New flow"
    new_name = "TEST RENAME WORKFLOW"
    response = client.patch(
        f"/experiments/{workspace_id}/{unique_id}/rename", json={"new_name": new_name}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == new_name
    response = client.patch(
        f"/experiments/{workspace_id}/{unique_id}/rename",
        json={"new_name": origin_name},
    )
