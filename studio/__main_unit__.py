import argparse
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_pagination import add_pagination
from starlette.middleware.cors import CORSMiddleware

from studio.app.common.core.auth.auth_dependencies import (
    get_admin_user,
    get_current_user,
)
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.mode import MODE
from studio.app.common.core.storage.remote_storage_controller import RemoteStorageType
from studio.app.common.core.workspace.workspace_dependencies import (
    is_workspace_available,
    is_workspace_owner,
)
from studio.app.common.routers import (
    algolist,
    auth,
    experiment,
    files,
    logs,
    outputs,
    params,
    run,
    storage_alerts,
    subscriptions,
    users_admin,
    users_me,
    users_search,
    workflow,
    workspace,
)
from studio.app.dir_path import DIRPATH
from studio.app.optinist.routers import hdf5, mat, nwb, roi
from studio.app.version import Version

logger = AppLogger.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup event
    """
    import platform
    import sys

    sys_version = sys.version.replace("\n", " ")
    mode = "standalone" if MODE.IS_STANDALONE else "multiuser"
    remote_storage_type = RemoteStorageType.get_activated_type()

    logger = AppLogger.get_logger()
    logger.info(
        f'"Studio" application startup complete.\n'
        f"    # Platform: {platform.platform()}\n"
        f"    # Python Version: {sys_version}\n"
        f"    # App Version: {Version.APP_VERSION}\n"
        f"    # Env:DATA_DIR: {DIRPATH.DATA_DIR}\n"
        f"    # Mode: {mode}\n"
        f"    # REMOTE_STORAGE_TYPE: {remote_storage_type}\n"
    )

    yield

    # Shutdown event
    logger.info('"Studio" application shutdown.')


app = FastAPI(docs_url="/docs", openapi_url="/openapi", lifespan=lifespan)


@app.get("/health")
async def health_check():
    try:
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Exception in health check: {str(e)}")
        return {
            "status": "warning",
            "details": {"application": "running", "error": str(e)},
        }


add_pagination(app)

# common routers
app.include_router(algolist.router, dependencies=[Depends(get_current_user)])
app.include_router(auth.router)
app.include_router(experiment.router, dependencies=[Depends(get_current_user)])
app.include_router(files.router, dependencies=[Depends(get_current_user)])
app.include_router(logs.router, dependencies=[Depends(get_current_user)])
app.include_router(outputs.router, dependencies=[Depends(get_current_user)])
app.include_router(params.router, dependencies=[Depends(get_current_user)])
app.include_router(run.router, dependencies=[Depends(get_current_user)])
app.include_router(storage_alerts.router, dependencies=[Depends(get_current_user)])
app.include_router(users_admin.router, dependencies=[Depends(get_admin_user)])
app.include_router(users_me.router, dependencies=[Depends(get_current_user)])
app.include_router(users_search.router, dependencies=[Depends(get_current_user)])
app.include_router(workflow.router, dependencies=[Depends(get_current_user)])
app.include_router(workspace.router, dependencies=[Depends(get_current_user)])
app.include_router(subscriptions.router, dependencies=[Depends(get_current_user)])

# optinist routers
app.include_router(hdf5.router, dependencies=[Depends(get_current_user)])
app.include_router(mat.router, dependencies=[Depends(get_current_user)])
app.include_router(nwb.router, dependencies=[Depends(get_current_user)])
app.include_router(roi.router, dependencies=[Depends(get_current_user)])


def skip_dependencies():
    pass


if MODE.IS_STANDALONE:
    app.dependency_overrides[get_current_user] = skip_dependencies
    app.dependency_overrides[get_admin_user] = skip_dependencies
    app.dependency_overrides[is_workspace_owner] = skip_dependencies
    app.dependency_overrides[is_workspace_available] = skip_dependencies

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/is_standalone", response_model=bool, tags=["others"])
async def is_standalone():
    return MODE.IS_STANDALONE


os.makedirs(f"{DIRPATH.FRONTEND_DIRS.BUILD}/static", exist_ok=True)
app.mount(
    "/static",
    StaticFiles(directory=f"{DIRPATH.FRONTEND_DIRS.BUILD}/static"),
    name="static",
)

public_templates = Jinja2Templates(directory=DIRPATH.FRONTEND_DIRS.PUBLIC)
build_templates = Jinja2Templates(directory=DIRPATH.FRONTEND_DIRS.BUILD)


@app.get("/")
async def root(request: Request):
    if os.path.exists(f"{DIRPATH.FRONTEND_DIRS.BUILD}/index.html"):
        return build_templates.TemplateResponse("index.html", {"request": request})
    else:
        return public_templates.TemplateResponse(
            "no-built-pages.html", {"request": request}
        )


@app.get("/{_:path}")
async def any_pages(request: Request):
    """
    Requests that don't match any routers come here.
    """
    # For backend API requests, it returns 404
    # (Determined by request.headers)
    if "application/json" in request.headers.get("accept", ""):
        return Response(status_code=status.HTTP_404_NOT_FOUND, content="")
    # In all other cases, forward to frontend.
    else:
        return await root(request)


def main(develop_mode: bool = False):
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    logging_config = AppLogger.get_logging_config()

    logger.info(f"Starting Optinist server on {args.host}:{args.port}")

    if develop_mode:
        if args.workers > 1:
            reload = False
            reload_options = {}
        else:
            reload = args.reload
            reload_options = {"reload_dirs": ["studio"]} if args.reload else {}

        uvicorn.run(
            "studio.__main_unit__:app",
            host=args.host,
            port=args.port,
            log_config=logging_config,
            workers=args.workers,
            reload=reload,
            **reload_options,
        )
    else:
        uvicorn.run(
            "studio.__main_unit__:app",
            host=args.host,
            port=args.port,
            log_config=logging_config,
            workers=args.workers,
            reload=False,
        )
