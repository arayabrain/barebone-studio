import { memo, useState } from "react"
import { useDispatch, useSelector } from "react-redux"
import { Handle, Position, NodeProps } from "reactflow"

import { Action, ThunkAction } from "@reduxjs/toolkit"

import { StructureItemSelectDialog } from "components/Workspace/FlowChart/Dialog/StructureItemSelectDialog"
import {
  TreeNodeType,
  FileNodeConfig,
} from "components/Workspace/FlowChart/FlowChartNode/BaseStructuredFileNode"
import { FileSelect } from "components/Workspace/FlowChart/FlowChartNode/FileSelect"
import { toHandleId } from "components/Workspace/FlowChart/FlowChartNode/FlowChartUtils"
import { NodeContainer } from "components/Workspace/FlowChart/FlowChartNode/NodeContainer"
import { HANDLE_STYLE } from "const/flowchart"
import { deleteFlowNodeById } from "store/slice/FlowElement/FlowElementSlice"
import { setInputNodeFilePath } from "store/slice/InputNode/InputNodeActions"
import { selectInputNodeDefined } from "store/slice/InputNode/InputNodeSelectors"
import { RootState } from "store/store"
import { arrayEqualityFn } from "utils/EqualityUtils"

export interface BatchFileNodeConfig {
  fileType: string
  handleId: string
  handleType: string
  treeKeyPrefix: string
  selectFilePath: (
    nodeId: string,
  ) => (state: RootState) => string | string[] | undefined
  selectStructurePath: (
    nodeId: string,
  ) => (state: RootState) => string | undefined
  setStructurePath: (params: {
    nodeId: string
    path: string
  }) => Action<unknown>
  getTree: (params: {
    path: string
    workspaceId: number
  }) => ThunkAction<unknown, RootState, unknown, Action<unknown>>
  selectTree: () => (state: RootState) => TreeNodeType[] | undefined
  selectIsLoading: () => (state: RootState) => boolean
}

function createBatchConfigAdapter(
  config: BatchFileNodeConfig,
  _filePath: string[] | undefined,
): FileNodeConfig {
  return {
    ...config,
    selectFilePath: (nodeId: string) => (state: RootState) => {
      const paths = config.selectFilePath(nodeId)(state)
      if (Array.isArray(paths) && paths.length > 0) {
        return paths[0]
      }
      return paths
    },
  }
}

export function createBatchStructuredFileNode(config: BatchFileNodeConfig) {
  const BatchFileNode = memo(function BatchFileNode(element: NodeProps) {
    const defined = useSelector(selectInputNodeDefined(element.id))
    if (defined) {
      return <BatchFileNodeImple {...element} config={config} />
    } else {
      return null
    }
  })
  BatchFileNode.displayName = `Batch${config.fileType}FileNode`
  return BatchFileNode
}

const BatchFileNodeImple = memo(function BatchFileNodeImple({
  id: nodeId,
  selected,
  config,
}: NodeProps & { config: BatchFileNodeConfig }) {
  const dispatch = useDispatch()
  const filePath = useSelector(config.selectFilePath(nodeId), (a, b) =>
    a != null && b != null && Array.isArray(a) && Array.isArray(b)
      ? arrayEqualityFn(a, b)
      : a === b,
  )

  const [open, setOpen] = useState(false)
  const onChangeFilePath = (path: string[]) => {
    dispatch(setInputNodeFilePath({ nodeId, filePath: path }))
  }

  const onClickDeleteIcon = () => {
    dispatch(deleteFlowNodeById(nodeId))
  }

  return (
    <NodeContainer nodeId={nodeId} selected={selected}>
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
        setOpen={setOpen}
        fileType={config.fileType}
        filePath={
          Array.isArray(filePath) ? filePath : filePath ? [filePath] : []
        }
      />
      {filePath !== undefined &&
        Array.isArray(filePath) &&
        filePath.length > 0 && (
          <StructureItemSelectDialog
            open={open}
            setOpen={setOpen}
            nodeId={nodeId}
            config={createBatchConfigAdapter(config, filePath)}
            filePath={filePath[0]}
          />
        )}
      <Handle
        type="source"
        position={Position.Right}
        id={toHandleId(nodeId, config.handleId, config.handleType)}
        style={{ ...HANDLE_STYLE }}
      />
    </NodeContainer>
  )
})
