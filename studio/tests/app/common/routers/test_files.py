from fastapi.testclient import TestClient

from studio.app.common.routers.files import DirTreeGetter, router
from studio.app.common.schemas.files import TreeNode

client = TestClient(router)


def test_create_files():
    response = client.get("/files?file_type=image")
    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert len(data) > 0


def test_DirTreeGetter_tif():
    output = DirTreeGetter.get_tree([".tif", ".tiff", ".TIF", ".TIFF"], "files")
    assert len(output) == 4
    assert isinstance(output[0], TreeNode)