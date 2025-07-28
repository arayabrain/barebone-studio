import { memo } from "react"
import { useSelector, useDispatch } from "react-redux"
import { Handle, Position, NodeProps } from "reactflow"

import { FileSelect } from "components/Workspace/FlowChart/FlowChartNode/FileSelect"
import {
  toHandleId,
  isValidConnection,
} from "components/Workspace/FlowChart/FlowChartNode/FlowChartUtils"
import { useHandleColor } from "components/Workspace/FlowChart/FlowChartNode/HandleColorHook"
import { NodeContainer } from "components/Workspace/FlowChart/FlowChartNode/NodeContainer"
import { HANDLE_STYLE } from "const/flowchart"
import { deleteFlowNodeById } from "store/slice/FlowElement/FlowElementSlice"
import { setInputNodeFilePath } from "store/slice/InputNode/InputNodeActions"
import {
  selectBatchImageInputNodeSelectedFilePath,
  selectInputNodeDefined,
} from "store/slice/InputNode/InputNodeSelectors"
import { FILE_TYPE_SET } from "store/slice/InputNode/InputNodeType"
import { arrayEqualityFn } from "utils/EqualityUtils"

export const BatchImageFileNode = memo(function BatchImageFileNode(
  element: NodeProps,
) {
  const defined = useSelector(selectInputNodeDefined(element.id))
  if (defined) {
    return <BatchImageFileNodeImple {...element} />
  } else {
    return null
  }
})

const BatchImageFileNodeImple = memo(function BatchImageFileNodeImple({
  id: nodeId,
  selected: elementSelected,
}: NodeProps) {
  const dispatch = useDispatch()
  const filePath = useSelector(
    selectBatchImageInputNodeSelectedFilePath(nodeId),
    (a, b) => (a != null && b != null ? arrayEqualityFn(a, b) : a === b),
  )
  const onChangeFilePath = (path: string[]) => {
    dispatch(setInputNodeFilePath({ nodeId, filePath: path }))
  }

  const returnType = "ImageData"
  const imageColor = useHandleColor(returnType)

  const onClickDeleteIcon = () => {
    dispatch(deleteFlowNodeById(nodeId))
  }

  return (
    <NodeContainer nodeId={nodeId} selected={elementSelected}>
      <button
        className="flowbutton"
        onClick={onClickDeleteIcon}
        style={{ color: "black", position: "absolute", top: -10, right: 10 }}
      >
        ×
      </button>
      <FileSelect
        nodeId={nodeId}
        multiSelect
        onChangeFilePath={(path) => {
          if (Array.isArray(path)) {
            onChangeFilePath(path)
          }
        }}
        fileType={FILE_TYPE_SET.BATCH_IMAGE}
        filePath={typeof filePath === "string" ? [filePath] : filePath || []}
      />
      <Handle
        type="source"
        position={Position.Right}
        id={toHandleId(nodeId, "batch_image", returnType)}
        style={{
          ...HANDLE_STYLE,
          background: imageColor,
        }}
        isValidConnection={isValidConnection}
      />
    </NodeContainer>
  )
})
