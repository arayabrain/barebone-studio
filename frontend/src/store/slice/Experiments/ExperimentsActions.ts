import { createAsyncThunk } from "@reduxjs/toolkit"

import {
  ExperimentsDTO,
  getExperimentsApi,
  deleteExperimentByUidApi,
  deleteExperimentByListApi,
  copyExperimentByListApi,
  syncRemoteExperimentApi,
} from "api/experiments/Experiments"
import { EXPERIMENTS_SLICE_NAME } from "store/slice/Experiments/ExperimentsType"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { ThunkApiConfig } from "store/store"

export const getExperiments = createAsyncThunk<
  ExperimentsDTO,
  undefined,
  ThunkApiConfig
>(`${EXPERIMENTS_SLICE_NAME}/getExperiments`, async (_, thunkAPI) => {
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (workspaceId) {
    try {
      const response = await getExperimentsApi(workspaceId)
      return response
    } catch (e) {
      return thunkAPI.rejectWithValue(e)
    }
  } else {
    return thunkAPI.rejectWithValue("workspace id does not exist.")
  }
})

export const deleteExperimentByUid = createAsyncThunk<
  boolean,
  string,
  ThunkApiConfig
>(`${EXPERIMENTS_SLICE_NAME}/deleteExperimentByUid`, async (uid, thunkAPI) => {
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (workspaceId) {
    try {
      const response = await deleteExperimentByUidApi(workspaceId, uid)
      return response
    } catch (e) {
      return thunkAPI.rejectWithValue(e)
    }
  } else {
    return thunkAPI.rejectWithValue("workspace id does not exist.")
  }
})

export const deleteExperimentByList = createAsyncThunk<
  boolean,
  string[],
  ThunkApiConfig
>(`${EXPERIMENTS_SLICE_NAME}/deleteExperimentByList`, async (uid, thunkAPI) => {
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (workspaceId) {
    try {
      const response = await deleteExperimentByListApi(workspaceId, uid)
      return response
    } catch (e) {
      return thunkAPI.rejectWithValue(e)
    }
  } else {
    return thunkAPI.rejectWithValue("workspace id does not exist.")
  }
})

export const copyExperimentByList = createAsyncThunk<
  boolean,
  string[],
  ThunkApiConfig
>(`${EXPERIMENTS_SLICE_NAME}/copyExperimentByList`, async (uid, thunkAPI) => {
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (!workspaceId) {
    return thunkAPI.rejectWithValue("workspace id does not exist.")
  }

  try {
    const response = await copyExperimentByListApi(workspaceId, uid)
    if (!response) {
      return thunkAPI.rejectWithValue("Copy API returned falsy result.")
    }
    // Don't return anything if success is only indicated by non-error
    return true
  } catch (e) {
    return thunkAPI.rejectWithValue(e)
  }
})

export const syncRemoteExperiment = createAsyncThunk<
  boolean,
  string,
  ThunkApiConfig
>(`${EXPERIMENTS_SLICE_NAME}/syncRemoteExperiment`, async (uid, thunkAPI) => {
  const workspaceId = selectCurrentWorkspaceId(thunkAPI.getState())
  if (workspaceId) {
    try {
      const response = await syncRemoteExperimentApi(workspaceId, uid)
      return response
    } catch (e) {
      return thunkAPI.rejectWithValue(e)
    }
  } else {
    return thunkAPI.rejectWithValue("sync remote storage experiment failed.")
  }
})
