import { RootState } from "store/store"
import { getChildParam } from "utils/param/ParamUtils"

export const selectAlgorithmNode = (state: RootState) => state.algorithmNode

export const selectAlgorithmNodeById = (nodeId: string) => (state: RootState) =>
  state.algorithmNode[nodeId]

export const selectAlgorithmNodeDefined =
  (nodeId: string) => (state: RootState) =>
    Object.keys(state.algorithmNode).includes(nodeId)

export const selectAlgorithmFunctionPath =
  (nodeId: string) => (state: RootState) =>
    selectAlgorithmNodeById(nodeId)(state).functionPath

export const selectAlgorithmName = (nodeId: string) => (state: RootState) =>
  selectAlgorithmNodeById(nodeId)(state).name

export const selectAlgorithmParams = (nodeId: string) => (state: RootState) =>
  selectAlgorithmNodeById(nodeId)(state)?.params

export const selectAlgorithmFilterParams =
  (nodeId: string) => (state: RootState) =>
    selectAlgorithmNodeById(nodeId)(state)?.draftDataFilterParam

export const selectAlgorithmDataFilterParam =
  (nodeId: string) => (state: RootState) => {
    const s = selectAlgorithmNodeById(nodeId)(state)
    return s?.draftDataFilterParam || s?.dataFilterParam
  }
export const selectAlgorithmFilterParamLoadingApi =
  (nodeId: string) => (state: RootState) => {
    return selectAlgorithmNodeById(nodeId)(state)?.loadingFilterParamApi
  }

export const selectAlgorithmDataFilterParamObject =
  (nodeId: string) => (state: RootState) => {
    const dataFilterParam =
      selectAlgorithmNodeById(nodeId)(state)?.dataFilterParam
    if (!dataFilterParam) return undefined
    const { dim1, roi } = dataFilterParam
    return {
      dim1: dim1?.filter(Boolean),
      roi: roi?.filter(Boolean),
    }
  }

export const selectAlgorithmIsUpdated =
  (nodeId: string) => (state: RootState) => {
    const isUpdate = selectAlgorithmNodeById(nodeId)(state).isUpdate
    const originalValue = selectAlgorithmNodeById(nodeId)(state).originalValue
    const param = selectAlgorithmParams(nodeId)(state)
    return (
      !(JSON.stringify(originalValue) === JSON.stringify(param)) && isUpdate
    )
  }

export const selectAlgorithmParamsExit =
  (nodeId: string) => (state: RootState) =>
    selectAlgorithmNodeById(nodeId)(state).params !== null

export const selectAlgorithmParamsKeyList =
  (nodeId: string) => (state: RootState) =>
    Object.keys(selectAlgorithmNodeById(nodeId)(state)?.params ?? {})

export const selectAlgorithmParamsValue =
  (nodeId: string, path: string) => (state: RootState) => {
    const params = selectAlgorithmParams(nodeId)(state)
    if (params != null) {
      const target = getChildParam(path, params)
      return target?.value
    } else {
      throw new Error("AlgorithmParam is null")
    }
  }

export const selectAlgorithmParam =
  (nodeId: string, paramKey: string) => (state: RootState) => {
    const params = selectAlgorithmParams(nodeId)(state)
    if (params != null) {
      return params[paramKey]
    } else {
      throw new Error("AlgorithmParam is null")
    }
  }

export const selectAlgorithmNodeNotExist = (state: RootState) =>
  Object.keys(selectAlgorithmNode(state)).length === 0
