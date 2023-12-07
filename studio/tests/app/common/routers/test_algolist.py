from studio.app.common.routers.algolist import NestDictGetter
from studio.app.common.schemas.algolist import Algo
from studio.app.wrappers import wrapper_dict


def test_run(client):
    response = client.get("/algolist")
    output = response.json()

    assert response.status_code == 200
    assert isinstance(output, dict)
    assert "caiman" in output
    assert "children" in output["caiman"]
    assert "caiman_mc" in output["caiman"]["children"]

    assert "args" in output["caiman"]["children"]["caiman_mc"]
    assert "path" in output["caiman"]["children"]["caiman_mc"]
    assert "suite2p" in output


def test_NestDictGetter():
    output = NestDictGetter.get_nest_dict(wrapper_dict, "")

    assert isinstance(output, dict)
    assert "caiman" in output
    assert "children" in output["caiman"]
    assert "caiman_mc" in output["caiman"]["children"]

    assert isinstance(output["caiman"]["children"]["caiman_mc"], Algo)
