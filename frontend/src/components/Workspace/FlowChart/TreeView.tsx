import { memo, useCallback, useEffect } from "react"
import { useDrag } from "react-dnd"
import { useSelector, useDispatch } from "react-redux"

import AddIcon from "@mui/icons-material/Add"
import ChevronRightIcon from "@mui/icons-material/ChevronRight"
import ExpandMoreIcon from "@mui/icons-material/ExpandMore"
import { styled, Typography, Tooltip } from "@mui/material"
import IconButton from "@mui/material/IconButton"
import { treeItemClasses } from "@mui/x-tree-view"
import { TreeItem } from "@mui/x-tree-view/TreeItem"
import { TreeView } from "@mui/x-tree-view/TreeView"

import { getDocumentationUrl } from "components/utils/DocsAlgoUrlUtils"
import { CondaNoticeButton } from "components/Workspace/FlowChart/Buttons/CondaNoticeButton"
import ExternalLinkButton from "components/Workspace/FlowChart/Buttons/ExternalLinkButton"
import {
  DND_ITEM_TYPE_SET,
  TreeItemCollectedProps,
  TreeItemDragObject,
  TreeItemDropResult,
} from "components/Workspace/FlowChart/DnDItemType"
import { getAllFileTypeConfigs } from "config/fileTypes.config"
import { REACT_FLOW_NODE_TYPE_KEY } from "const/flowchart"
import { FileNodeFactory } from "factories/FileNodeFactory"
import { getAlgoList } from "store/slice/AlgorithmList/AlgorithmListActions"
import {
  selectAlgorithmListIsLatest,
  selectAlgorithmListTree,
} from "store/slice/AlgorithmList/AlgorithmListSelectors"
import {
  AlgorithmChild,
  AlgorithmNodeType,
} from "store/slice/AlgorithmList/AlgorithmListType"
import { isAlgoChild } from "store/slice/AlgorithmList/AlgorithmListUtils"
import {
  addAlgorithmNode,
  addInputNode,
} from "store/slice/FlowElement/FlowElementActions"
import {
  NODE_TYPE,
  NODE_TYPE_SET,
} from "store/slice/FlowElement/FlowElementType"
import { FILE_TYPE } from "store/slice/InputNode/InputNodeType"
import { selectPipelineLatestUid } from "store/slice/Pipeline/PipelineSelectors"
import { AppDispatch } from "store/store"
import { getNanoId } from "utils/nanoid/NanoIdUtils"

export const AlgorithmTreeView = memo(function AlgorithmTreeView() {
  const dispatch = useDispatch<AppDispatch>()
  const algoList = useSelector(selectAlgorithmListTree)
  const isLatest = useSelector(selectAlgorithmListIsLatest)
  const workflowId = useSelector(selectPipelineLatestUid)
  const runAlready = typeof workflowId !== "undefined"

  useEffect(() => {
    if (!isLatest) {
      dispatch(getAlgoList())
    }
  }, [dispatch, isLatest])

  const onAddAlgoNode = useCallback(
    (
      nodeName: string,
      functionPath: string,
      position?: { x: number; y: number },
    ) => {
      const name = nodeName
      const newNode = {
        id: `${name}_${getNanoId()}`,
        type: REACT_FLOW_NODE_TYPE_KEY.AlgorithmNode,
        data: { label: name, type: NODE_TYPE_SET.ALGORITHM },
        position,
      }
      dispatch(
        addAlgorithmNode({
          node: newNode,
          name,
          functionPath,
          runAlready,
        }),
      )
    },
    [dispatch, runAlready],
  )

  return (
    <TreeView
      sx={{
        flexGrow: 1,
        height: "100%",
      }}
      defaultCollapseIcon={<ExpandMoreIcon />}
      defaultExpandIcon={<ChevronRightIcon />}
    >
      <TreeItem nodeId="Data" label="Data">
        {getAllFileTypeConfigs().map((config) => (
          <InputNodeComponent
            key={config.key}
            fileName={config.key}
            nodeName={config.displayName}
            fileType={config.key as FILE_TYPE}
            config={config}
          />
        ))}
      </TreeItem>
      <TreeItem nodeId="Algorithm" label="Algorithm">
        {Object.entries(algoList).map(([name, node], i) => (
          <AlgoNodeComponentRecursive
            name={name}
            node={node}
            onAddAlgoNode={onAddAlgoNode}
            key={i.toFixed()}
          />
        ))}
      </TreeItem>
    </TreeView>
  )
})

interface InputNodeComponentProps {
  fileName: string
  nodeName: string
  fileType: FILE_TYPE
  config: import("config/fileTypes.config").FileTypeConfig
}

const InputNodeComponent = memo(function InputNodeComponent({
  fileName,
  nodeName,
  fileType,
  config,
}: InputNodeComponentProps) {
  const dispatch = useDispatch()

  const onAddDataNode = useCallback(
    (
      nodeType: NODE_TYPE,
      nodeName: string,
      fileType: FILE_TYPE,
      position?: { x: number; y: number },
    ) => {
      const newNode = FileNodeFactory.createReactFlowNode(
        nodeName,
        config,
        position,
      )
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      newNode.data.type = nodeType as any
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      dispatch(addInputNode({ node: newNode as any, fileType }))
    },
    [dispatch, config],
  )

  const { isDragging, dragRef } = useLeafItemDrag(
    useCallback(
      (position) => {
        onAddDataNode(NODE_TYPE_SET.INPUT, nodeName, fileType, position)
      },
      [onAddDataNode, nodeName, fileType],
    ),
  )

  return (
    <LeafItem
      ref={dragRef}
      style={{
        opacity: isDragging ? 0.6 : 1,
      }}
      onFocusCapture={(e) => e.stopPropagation()}
      nodeId={fileName}
      label={
        <AddButton
          name={fileName}
          onClick={() => onAddDataNode(NODE_TYPE_SET.INPUT, nodeName, fileType)}
        />
      }
    />
  )
})

export interface AlgoNodeComponentBaseProps {
  name: string
  onAddAlgoNode: (
    nodeName: string,
    functionPath: string,
    position?: { x: number; y: number },
  ) => void
}

interface AlgoNodeComponentRecursiveProps extends AlgoNodeComponentBaseProps {
  node: AlgorithmNodeType
}

const AlgoNodeComponentRecursive = memo(function AlgoNodeComponentRecursive({
  name,
  node,
  onAddAlgoNode,
}: AlgoNodeComponentRecursiveProps) {
  if (isAlgoChild(node)) {
    return (
      <AlgoNodeComponent
        name={name}
        node={node}
        onAddAlgoNode={onAddAlgoNode}
      />
    )
  } else {
    return (
      <TreeItem nodeId={name} label={name}>
        {Object.entries(node.children).map(([name, node], i) => (
          <AlgoNodeComponentRecursive
            name={name}
            node={node}
            onAddAlgoNode={onAddAlgoNode}
            key={i.toFixed()}
          />
        ))}
      </TreeItem>
    )
  }
})

interface AlgoNodeComponentProps extends AlgoNodeComponentBaseProps {
  node: AlgorithmChild
}

const AlgoNodeComponent = memo(function AlgoNodeComponent({
  name,
  node,
  onAddAlgoNode,
}: AlgoNodeComponentProps) {
  const { isDragging, dragRef } = useLeafItemDrag(
    useCallback(
      (position) => {
        onAddAlgoNode(name, node.functionPath, position)
      },
      [onAddAlgoNode, name, node],
    ),
  )

  return (
    <LeafItem
      ref={dragRef}
      style={{
        opacity: isDragging ? 0.6 : 1,
      }}
      onFocusCapture={(e) => e.stopPropagation()}
      nodeId={name}
      label={
        <>
          <div
            style={{
              display: "flex", // Place Items on single line.
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {node.condaEnvExists ? (
              <AddButton
                name={name}
                showParameterUrl={true}
                onClick={() => onAddAlgoNode(name, node.functionPath)}
              />
            ) : (
              <CondaNoticeButton
                name={name}
                showParameterUrl={true}
                node={node}
                onSkipClick={(_event, reason) => {
                  // Cancel operation from other than Skip (Cancel) button does nothing.
                  // *In the cancel button click, the reason is undefined..
                  if (reason !== undefined) {
                    return
                  }
                  onAddAlgoNode(name, node.functionPath)
                }}
              />
            )}
          </div>
        </>
      }
    />
  )
})

interface AddButtonProps {
  name: string
  showParameterUrl?: boolean
  onClick: () => void
}

const AddButton = memo(function AddButton({
  name,
  showParameterUrl = false,
  onClick,
}: AddButtonProps) {
  return (
    <>
      <IconButton
        aria-label="add"
        style={{ padding: 2 }}
        size="large"
        onClick={onClick}
      >
        <AddIcon />
      </IconButton>
      <Tooltip
        title={name}
        placement="top"
        PopperProps={{
          modifiers: [
            {
              name: "offset",
              options: {
                offset: [0, -15], // [horizontal, vertical] - decrease the number to move closer
              },
            },
          ],
        }}
      >
        <Typography
          variant="inherit"
          style={{
            display: "inline-block",
          }}
        >
          {name}
        </Typography>
      </Tooltip>
      {showParameterUrl && (
        <ExternalLinkButton
          url={getDocumentationUrl(name)}
          linkStyle={{
            textDecoration: "underline",
            color: "inherit",
            cursor: "pointer",
            marginLeft: "5px",
            display: "inline-flex",
            alignItems: "center",
          }}
          iconStyle={{
            fontSize: "12px",
            color: "#808080",
          }}
        />
      )}
    </>
  )
})

// 未使用icon分の幅を消す
const LeafItem = styled(TreeItem)({
  // background: 'red',
  [`& .${treeItemClasses.iconContainer}`]: {
    margin: 0,
    width: 0,
  },
})

function useLeafItemDrag(
  onDragEnd: (position: { x: number; y: number }) => void,
) {
  const [{ isDragging }, dragRef] = useDrag<
    TreeItemDragObject,
    TreeItemDropResult,
    TreeItemCollectedProps
  >(
    () => ({
      type: DND_ITEM_TYPE_SET.TREE_ITEM,
      end: (_, monitor) => {
        const position = monitor.getDropResult()?.position
        if (monitor.didDrop() && position != null) {
          onDragEnd(position)
        }
      },
      collect: (monitor) => ({
        isDragging: monitor.isDragging(),
      }),
    }),
    [onDragEnd],
  )
  return { isDragging, dragRef }
}
