import json
import os
import shutil
from glob import glob
from pathlib import PurePath
from typing import Dict, List
from urllib.parse import urlparse

import requests
import tifffile
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from requests.models import Response
from sqlmodel import Session
from tqdm import tqdm

from studio.app.common.core.auth.auth_dependencies import get_user_remote_bucket_name
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.remote_storage_controller import (
    RemoteStorageController,
    RemoteStorageSimpleWriter,
)
from studio.app.common.core.utils.file_reader import JsonReader
from studio.app.common.core.utils.filepath_creater import (
    create_directory,
    join_filepath,
)
from studio.app.common.core.workspace.workspace_data_capacity_services import (
    WorkspaceDataCapacityService,
)
from studio.app.common.core.workspace.workspace_dependencies import (
    is_workspace_available,
    is_workspace_owner,
)
from studio.app.common.db.database import get_db
from studio.app.common.schemas.files import (
    DownloadFileRequest,
    DownloadStatus,
    FilePath,
    TreeNode,
)
from studio.app.const import ACCEPT_FILE_EXT, FILETYPE
from studio.app.dir_path import DIRPATH

router = APIRouter(prefix="/files", tags=["files"])

logger = AppLogger.get_logger()


class DirTreeGetter:
    @classmethod
    def get_tree(
        cls, workspace_id, file_types: List[str], dirname: str = None
    ) -> List[TreeNode]:
        nodes: List[TreeNode] = []

        if dirname is None:
            absolute_dirpath = join_filepath([DIRPATH.INPUT_DIR, workspace_id])
        else:
            absolute_dirpath = join_filepath([DIRPATH.INPUT_DIR, workspace_id, dirname])

        if not os.path.exists(absolute_dirpath):
            return nodes

        sorted_listdir = sorted(
            os.listdir(absolute_dirpath),
            key=lambda x: (not os.path.isdir(join_filepath([absolute_dirpath, x])), x),
        )

        IMAGE_SHAPE_DICT = (
            get_image_shape_dict(workspace_id)
            if file_types == ACCEPT_FILE_EXT.TIFF_EXT.value
            else {}
        )

        for node_name in sorted_listdir:
            if dirname is None:
                relative_path = node_name
            else:
                relative_path = join_filepath([dirname, node_name])

            search_dirpath = join_filepath([absolute_dirpath, node_name])

            if os.path.isfile(search_dirpath) and node_name.endswith(tuple(file_types)):
                shape = IMAGE_SHAPE_DICT.get(relative_path, {}).get("shape")
                if shape is None and file_types == ACCEPT_FILE_EXT.TIFF_EXT.value:
                    shape = update_image_shape(workspace_id, relative_path)
                nodes.append(
                    TreeNode(
                        path=relative_path,
                        name=node_name,
                        isdir=False,
                        nodes=[],
                        shape=shape,
                    )
                )
            elif (
                os.path.isdir(search_dirpath)
                and len(cls.accept_files(search_dirpath, file_types)) > 0
            ):
                nodes.append(
                    TreeNode(
                        path=node_name,
                        name=node_name,
                        isdir=True,
                        nodes=cls.get_tree(workspace_id, file_types, relative_path),
                    )
                )

        return nodes

    @classmethod
    def accept_files(cls, path: str, file_types: List[str]):
        files_list = []
        for file_type in file_types:
            files_list.extend(
                glob(join_filepath([path, "**", f"*{file_type}"]), recursive=True)
            )

        return files_list


def get_image_shape_dict(workspace_id):
    dirpath = join_filepath([DIRPATH.INPUT_DIR, workspace_id])
    try:
        tiff_format_dict = JsonReader.read(
            join_filepath([dirpath, ".image_shape.json"])
        )
        return tiff_format_dict
    except FileNotFoundError:
        return {}


def update_image_shape(workspace_id, relative_file_path):
    dirpath = join_filepath([DIRPATH.INPUT_DIR, workspace_id])
    filepath = join_filepath([dirpath, relative_file_path])

    try:
        img = tifffile.imread(filepath)
        shape = img.shape
    except:  # noqa
        shape = []

    tiff_format_file = join_filepath([dirpath, ".image_shape.json"])
    try:
        tiff_format_dict = JsonReader.read(tiff_format_file)
    except FileNotFoundError:
        tiff_format_dict = {}
    tiff_format_dict[relative_file_path] = {"shape": shape}

    with open(tiff_format_file, "w") as f:
        json.dump(tiff_format_dict, f, indent=4)

    return shape


@router.get(
    "/{workspace_id}",
    response_model=List[TreeNode],
    dependencies=[Depends(is_workspace_available)],
)
async def get_files(workspace_id: str, file_type: str = None):
    if file_type == FILETYPE.IMAGE:
        return DirTreeGetter.get_tree(workspace_id, ACCEPT_FILE_EXT.TIFF_EXT.value)
    elif file_type == FILETYPE.CSV:
        return DirTreeGetter.get_tree(workspace_id, ACCEPT_FILE_EXT.CSV_EXT.value)
    elif file_type == FILETYPE.HDF5:
        return DirTreeGetter.get_tree(workspace_id, ACCEPT_FILE_EXT.HDF5_EXT.value)
    elif file_type == FILETYPE.MICROSCOPE:
        return DirTreeGetter.get_tree(
            workspace_id, ACCEPT_FILE_EXT.MICROSCOPE_EXT.value
        )
    elif file_type == FILETYPE.MATLAB:
        return DirTreeGetter.get_tree(workspace_id, ACCEPT_FILE_EXT.MATLAB_EXT.value)
    else:
        return []


@router.post(
    "/{workspace_id}/shape/{filepath}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def set_shape(workspace_id: str, filepath: str):
    try:
        update_image_shape(workspace_id, filepath)
    except Exception as e:
        raise HTTPException(status=422, detail=str(e))
    return True


@router.post(
    "/{workspace_id}/upload/{filename}",
    response_model=FilePath,
    dependencies=[Depends(is_workspace_owner)],
)
async def create_file(
    workspace_id: str,
    filename: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    create_directory(join_filepath([DIRPATH.INPUT_DIR, workspace_id]))

    filepath = join_filepath([DIRPATH.INPUT_DIR, workspace_id, filename])

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    update_image_shape(workspace_id, filename)

    if WorkspaceDataCapacityService.is_available():
        background_tasks.add_task(
            WorkspaceDataCapacityService.update_workspace_data_usage, db, workspace_id
        )

    # Operate remote storage data.
    if RemoteStorageController.is_available():
        # upload input data to remote storage
        async with RemoteStorageSimpleWriter(
            remote_bucket_name
        ) as remote_storage_controller:
            await remote_storage_controller.upload_input_data(workspace_id, filename)

    return {"file_path": filename}


DOWNLOAD_STATUS: Dict[str, DownloadStatus] = {}


@router.delete(
    "/{workspace_id}/delete/{filename}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def delete_file(
    workspace_id: str,
    filename: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    filepath = join_filepath([DIRPATH.INPUT_DIR, workspace_id, filename])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        # Remove from remote storage if available
        if RemoteStorageController.is_available():
            async with RemoteStorageSimpleWriter(
                remote_bucket_name
            ) as remote_storage_controller:
                await remote_storage_controller.delete_input_data(
                    workspace_id, filename
                )

        # Remove local file
        os.remove(filepath)

        if WorkspaceDataCapacityService.is_available():
            background_tasks.add_task(
                WorkspaceDataCapacityService.update_workspace_data_usage,
                db,
                workspace_id,
            )

        return True
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{workspace_id}/download/status",
    response_model=DownloadStatus,
    dependencies=[Depends(is_workspace_available)],
)
async def get_download_status(workspace_id: str, file_name: str):
    filepath = join_filepath([DIRPATH.INPUT_DIR, workspace_id, file_name])
    try:
        return DOWNLOAD_STATUS[filepath]
    except:  # noqa
        raise HTTPException(status_code=404)


@router.post(
    "/{workspace_id}/download",
    dependencies=[Depends(is_workspace_owner)],
)
async def download_file(
    workspace_id: str,
    file: DownloadFileRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    path = PurePath(urlparse(file.url).path)
    if path.suffix not in ACCEPT_FILE_EXT.ALL_EXT.value:
        raise HTTPException(status_code=400, detail="Invalid url")

    create_directory(join_filepath([DIRPATH.INPUT_DIR, workspace_id]))

    try:
        res = requests.get(file.url, stream=True)
        res.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    background_tasks.add_task(download, db, res, path.name, workspace_id)
    background_tasks.add_task(update_image_shape, workspace_id, path.name)
    return {"file_name": path.name}


def download(
    db: Session, res: Response, file_name: str, workspace_id: str, chunk_size=1024
):
    total = int(res.headers.get("content-length", 0))
    filepath = join_filepath([DIRPATH.INPUT_DIR, workspace_id, file_name])
    current = 0

    try:
        with open(filepath, "wb") as file, tqdm(
            desc=filepath,
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in res.iter_content(chunk_size=chunk_size):
                size = file.write(data)
                current += size
                DOWNLOAD_STATUS[filepath] = DownloadStatus(total=total, current=current)
                bar.update(size)
    except Exception as e:
        DOWNLOAD_STATUS[filepath] = DownloadStatus(error=str(e))

    if WorkspaceDataCapacityService.is_available():
        WorkspaceDataCapacityService.update_workspace_data_usage(db, workspace_id)
