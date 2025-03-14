import {
  createContext,
  memo,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react"
import { useDispatch, useSelector } from "react-redux"

import { FILE_TREE_TYPE } from "api/files/Files"
import { getTimeSeriesDataById } from "store/slice/DisplayData/DisplayDataActions"
import {
  selectPipelineNodeResultOutputFileDataType,
  selectPipelineNodeResultOutputFilePath,
} from "store/slice/Pipeline/PipelineSelectors"
import { selectVisualizeItemIdForWorkflowDialog } from "store/slice/VisualizeItem/VisualizeItemSelectors"
import { setTimeSeriesItemDrawOrderList } from "store/slice/VisualizeItem/VisualizeItemSlice"
import { AppDispatch } from "store/store"

export declare type FileSelectDialogValue = {
  filePath: string | string[]
  open: boolean
  fileTreeType?: FILE_TREE_TYPE
  multiSelect: boolean
  onSelectFile: (path: string | string[]) => void
}

export declare type FileInputUrl = {
  filePath?: string | string[]
  open: boolean
  nodeId: string
  requestId: string
  fileType?: FILE_TREE_TYPE
}

export declare type ClearWorkflowIdDialogValue = {
  open: boolean
  handleOk: () => void
  handleCancel: () => void
}

export declare type ErrorDialogValue = {
  anchorElRef: { current: Element | null }
  message: string
}

export const DialogContext = createContext<{
  onOpenOutputDialog: (nodeId: string) => void
  onOpenFileSelectDialog: (value: FileSelectDialogValue) => void
  onOpenInputUrlDialog: (value: FileInputUrl) => void
  onOpenClearWorkflowIdDialog: (value: ClearWorkflowIdDialogValue) => void
  onMessageError: (value: ErrorDialogValue) => void
  onOpenFilterDialog: (nodeId: string) => void
  onOpenLogs: (open: boolean) => void
  dialogFilterNodeId?: string
  isOutput: boolean
}>({
  onOpenOutputDialog: () => null,
  onOpenFileSelectDialog: () => null,
  onOpenClearWorkflowIdDialog: () => null,
  onOpenInputUrlDialog: () => null,
  onMessageError: () => null,
  onOpenFilterDialog: () => null,
  isOutput: false,
  onOpenLogs: () => null,
})

export const RoiSelectedContext = createContext<{
  roisSelected: number[]
  setRoiSelected: (index: number) => void
  itemId: number | null
  maxDim?: number
  maxRoi?: number
  setMaxDim?: (maxDim?: number) => void
  setMaxRoi?: (maxDim?: number) => void
}>({
  roisSelected: [],
  setRoiSelected: () => null,
  itemId: null,
})

export const useRoisSelected = () => useContext(RoiSelectedContext)

export const RoiSelectedProvider = memo(function RoiSelectedProviderMemo({
  children,
}: PropsWithChildren) {
  const [roisSelected, setRoisSelected] = useState<number[]>([])
  const [maxDim, setMaxDim] = useState<number>()
  const [maxRoi, setMaxRoi] = useState<number>()

  const { dialogFilterNodeId } = useContext(DialogContext)
  const dispatch = useDispatch<AppDispatch>()
  const filePath = useSelector(
    selectPipelineNodeResultOutputFilePath(dialogFilterNodeId!, "fluorescence"),
  )
  const dataType = useSelector(
    selectPipelineNodeResultOutputFileDataType(
      dialogFilterNodeId!,
      "fluorescence",
    ),
  )
  const itemId = useSelector(
    selectVisualizeItemIdForWorkflowDialog(
      dialogFilterNodeId!,
      filePath,
      dataType,
    ),
  )

  const setRoiSelected = useCallback(
    (index: number) => {
      const select = roisSelected.find((e) => e === index)
      let rois = []
      if (select !== undefined) {
        rois = roisSelected.filter((e) => e !== index)
      } else {
        rois = [...roisSelected, index]
      }
      setRoisSelected(rois)
      if (itemId) {
        dispatch(
          setTimeSeriesItemDrawOrderList({
            itemId,
            drawOrderList: rois.map((e) => String(e)),
          }),
        )
        if (!select) {
          dispatch(
            getTimeSeriesDataById({
              path: filePath,
              index: String(index),
              isFull: true,
            }),
          )
        }
      }
    },
    [dispatch, filePath, itemId, roisSelected],
  )

  useEffect(() => {
    return () => {
      if (!itemId) return
      dispatch(setTimeSeriesItemDrawOrderList({ itemId, drawOrderList: [] }))
    }
  }, [dispatch, itemId])

  return (
    <RoiSelectedContext.Provider
      value={{
        roisSelected,
        setRoiSelected,
        itemId,
        maxDim,
        maxRoi,
        setMaxDim,
        setMaxRoi,
      }}
    >
      {children}
    </RoiSelectedContext.Provider>
  )
})
