import { memo, useState } from "react"
import { useSelector, useDispatch } from "react-redux"
import { Handle, Position, NodeProps } from "reactflow"

import { Button, Typography } from "@mui/material"

import { ExpDbSelectDialog } from "components/Workspace/FlowChart/FlowChartNode/ExpDbNode"
import {
  toHandleId,
  isValidConnection,
} from "components/Workspace/FlowChart/FlowChartNode/FlowChartUtils"
import { useHandleColor } from "components/Workspace/FlowChart/FlowChartNode/HandleColorHook"
import { NodeContainer } from "components/Workspace/FlowChart/FlowChartNode/NodeContainer"
import { HANDLE_STYLE } from "const/flowchart"
import { deleteFlowNodeById } from "store/slice/FlowElement/FlowElementSlice"
import {
  selectMicroscopeExpdbInputNodeSelectedFilePath,
  selectInputNodeDefined,
} from "store/slice/InputNode/InputNodeSelectors"
import { FILE_TYPE_NODE_NAME_ALIAS } from "store/slice/InputNode/InputNodeType"

export const MicroscopeExpdbFileNode = memo(function MicroscopeExpdbFileNode(
  element: NodeProps,
) {
  const defined = useSelector(selectInputNodeDefined(element.id))
  if (defined) {
    return <MicroscopeExpdbFileNodeImple {...element} />
  } else {
    return null
  }
})

const MicroscopeExpdbFileNodeImple = memo(
  function MicroscopeExpdbFileNodeImple({
    id: nodeId,
    selected: elementSelected,
  }: NodeProps) {
    const dispatch = useDispatch()

    const returnType = "MicroscopeExpdbData"
    const microscopeColor = useHandleColor(returnType)

    const onClickDeleteIcon = () => {
      dispatch(deleteFlowNodeById(nodeId))
    }

    return (
      <NodeContainer nodeId={nodeId} selected={elementSelected}>
        <Typography>{FILE_TYPE_NODE_NAME_ALIAS.MICROSCOPE_EXPDB}</Typography>
        <button
          className="flowbutton"
          onClick={onClickDeleteIcon}
          style={{ color: "black", position: "absolute", top: -10, right: 10 }}
        >
          ×
        </button>
        <ExpDbSelect nodeId={nodeId} />
        <Handle
          type="source"
          position={Position.Right}
          id={toHandleId(nodeId, "microscope", returnType)}
          style={{ ...HANDLE_STYLE, background: microscopeColor }}
          isValidConnection={isValidConnection}
        />
      </NodeContainer>
    )
  },
)

const ExpDbSelect = memo(function ExpDbSelect({ nodeId }: { nodeId: string }) {
  const [open, setOpen] = useState(false)
  const experimentId = useSelector(
    selectMicroscopeExpdbInputNodeSelectedFilePath(nodeId),
  )

  return (
    <div>
      <Button size="small" variant="outlined" onClick={() => setOpen(true)}>
        Select
      </Button>
      <ExpDbSelectDialog
        nodeId={nodeId}
        open={open}
        setOpen={setOpen}
        experimentIdSelector={selectMicroscopeExpdbInputNodeSelectedFilePath}
      />
      <Typography>
        {experimentId
          ? `Selected experiment id: ${experimentId}`
          : "No experiment selected"}
      </Typography>
    </div>
  )
})
