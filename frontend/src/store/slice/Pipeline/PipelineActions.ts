import { createAsyncThunk } from "@reduxjs/toolkit"

import {
  runApi,
  runByUidApi,
  runResult,
  RunResultDTO,
  RunPostData,
  cancelResultApi,
  runFilterApi,
} from "api/run/Run"
import { TDataFilterParam } from "store/slice/AlgorithmNode/AlgorithmNodeType"
import {
  selectPipelineLatestUid,
  selectRunResultPendingNodeIdList,
} from "store/slice/Pipeline/PipelineSelectors"
import { PIPELINE_SLICE_NAME } from "store/slice/Pipeline/PipelineType"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { ThunkApiConfig } from "store/store"

export const run = createAsyncThunk<
  string,
  { runPostData: RunPostData },
  ThunkApiConfig
>(`${PIPELINE_SLICE_NAME}/run`, async ({ runPostData }, thunkAPI) => {
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (workspaceId) {
    try {
      const responseData = await runApi(workspaceId, runPostData)
      return responseData
    } catch (e) {
      return thunkAPI.rejectWithValue(e)
    }
  } else {
    return thunkAPI.rejectWithValue("workspace id does not exist.")
  }
})

export const runApplyFilter = createAsyncThunk<
  string,
  {
    dataFilterParam?: TDataFilterParam
    nodeId: string
  },
  ThunkApiConfig
>(
  `${PIPELINE_SLICE_NAME}/run/filter`,
  async ({ dataFilterParam, nodeId }, thunkAPI) => {
    const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
    const currentUid = selectPipelineLatestUid(thunkAPI.getState())

    if (!currentUid) {
      return thunkAPI.rejectWithValue("uid does not exist.")
    }

    if (workspaceId) {
      try {
        const response = await runFilterApi(
          workspaceId,
          currentUid,
          nodeId,
          dataFilterParam,
        )
        return response
      } catch (e) {
        return thunkAPI.rejectWithValue(e)
      }
    } else {
      return thunkAPI.rejectWithValue("workspace id does not exist.")
    }
  },
)

export const runByCurrentUid = createAsyncThunk<
  string,
  { runPostData: Omit<RunPostData, "name"> },
  ThunkApiConfig
>(
  `${PIPELINE_SLICE_NAME}/runByCurrentUid`,
  async ({ runPostData }, thunkAPI) => {
    const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
    const currentUid = selectPipelineLatestUid(thunkAPI.getState())
    if (workspaceId && currentUid != null) {
      try {
        const responseData = await runByUidApi(
          workspaceId,
          currentUid,
          runPostData,
        )
        return responseData
      } catch (e) {
        return thunkAPI.rejectWithValue(e)
      }
    } else {
      return thunkAPI.rejectWithValue(
        "workspaceId or currentUid dose not exist.",
      )
    }
  },
)

export const pollRunResult = createAsyncThunk<
  RunResultDTO,
  {
    uid: string
  },
  ThunkApiConfig
>(`${PIPELINE_SLICE_NAME}/pollRunResult`, async ({ uid }, thunkAPI) => {
  const pendingNodeIdList = selectRunResultPendingNodeIdList(
    thunkAPI.getState(),
  )
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (workspaceId) {
    try {
      const responseData = await runResult({
        workspaceId,
        uid,
        pendingNodeIdList,
      })
      return responseData
    } catch (e) {
      return thunkAPI.rejectWithValue(e)
    }
  } else {
    return thunkAPI.rejectWithValue("workspace id does not exist")
  }
})

export const cancelResult = createAsyncThunk<
  RunResultDTO,
  {
    uid: string
  },
  ThunkApiConfig
>(`${PIPELINE_SLICE_NAME}/cancelResult`, async ({ uid }, thunkAPI) => {
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (workspaceId) {
    try {
      const responseData = await cancelResultApi({
        workspaceId: workspaceId,
        uid,
      })
      return responseData
    } catch (e) {
      return thunkAPI.rejectWithValue(e)
    }
  } else {
    return thunkAPI.rejectWithValue("workspace id does not exist")
  }
})
