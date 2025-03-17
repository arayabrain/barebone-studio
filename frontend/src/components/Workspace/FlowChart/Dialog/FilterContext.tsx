import {
  createContext,
  Dispatch,
  PropsWithChildren,
  SetStateAction,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react"
import { useSelector, useDispatch, shallowEqual } from "react-redux"

import { DialogContext } from "components/Workspace/FlowChart/Dialog/DialogContext"
import { selectAlgorithmDataFilterParam } from "store/slice/AlgorithmNode/AlgorithmNodeSelectors"
import { TDataFilterParam } from "store/slice/AlgorithmNode/AlgorithmNodeType"
import { getRoiData } from "store/slice/DisplayData/DisplayDataActions"
import { selectOutputFilePathCellRoi } from "store/slice/Pipeline/PipelineSelectors"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { AppDispatch } from "store/store"

const BoxFilterContext = createContext<{
  filterParam?: TDataFilterParam
  roiPath: string
  setFilterParam: Dispatch<SetStateAction<TDataFilterParam | undefined>>
}>({
  filterParam: undefined,
  setFilterParam: () => null,
  roiPath: "",
})

export const useBoxFilter = () => useContext(BoxFilterContext)

export const BoxFilterProvider = ({
  children,
  nodeId,
}: PropsWithChildren<{ nodeId: string }>) => {
  const filterSelector = useSelector(
    selectAlgorithmDataFilterParam(nodeId),
    shallowEqual,
  )
  const [filterParam, setFilterParam] = useState<TDataFilterParam | undefined>(
    filterSelector,
  )
  const { isOutput } = useContext(DialogContext)
  const dispatch = useDispatch<AppDispatch>()
  const workspaceId = useSelector(selectCurrentWorkspaceId)
  const isExistFilterRoi = useMemo(
    () => filterParam?.roi?.length,
    [filterParam?.roi?.length],
  )
  const path = useSelector(selectOutputFilePathCellRoi(nodeId))

  useEffect(() => {
    if (isOutput && path && isExistFilterRoi && workspaceId) {
      dispatch(getRoiData({ workspaceId, path }))
    }
  }, [dispatch, path, isExistFilterRoi, isOutput, workspaceId])

  return (
    <BoxFilterContext.Provider
      value={{ filterParam, setFilterParam, roiPath: path }}
    >
      {children}
    </BoxFilterContext.Provider>
  )
}
