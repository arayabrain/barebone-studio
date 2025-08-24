import { memo, useState, useEffect } from "react"
import { useDispatch, useSelector } from "react-redux"
import { Handle, Position, NodeProps } from "reactflow"

import FolderIcon from "@mui/icons-material/Folder"
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined"
import { Typography } from "@mui/material"
import Button from "@mui/material/Button"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import LinearProgress from "@mui/material/LinearProgress"
import { useTheme } from "@mui/material/styles"
import { TreeItem } from "@mui/x-tree-view/TreeItem"
import { TreeView } from "@mui/x-tree-view/TreeView"

import { FileSelect } from "components/Workspace/FlowChart/FlowChartNode/FileSelect"
import { toHandleId } from "components/Workspace/FlowChart/FlowChartNode/FlowChartUtils"
import { NodeContainer } from "components/Workspace/FlowChart/FlowChartNode/NodeContainer"
import { HANDLE_STYLE } from "const/flowchart"
import { deleteFlowNodeById } from "store/slice/FlowElement/FlowElementSlice"
import { NodeIdProps } from "store/slice/FlowElement/FlowElementType"
import { getHDF5Tree } from "store/slice/HDF5/HDF5Action"
import {
  selectHDF5IsLoading,
  selectHDF5Nodes,
} from "store/slice/HDF5/HDF5Selectors"
import { HDF5TreeNodeType } from "store/slice/HDF5/HDF5Type"
import { setInputNodeFilePath } from "store/slice/InputNode/InputNodeActions"
import {
  selectInputNodeDefined,
  selectInputNodeSelectedFilePath,
  selectInputNodeHDF5Path,
} from "store/slice/InputNode/InputNodeSelectors"
import { setInputNodeHDF5Path } from "store/slice/InputNode/InputNodeSlice"
import { FILE_TYPE_SET } from "store/slice/InputNode/InputNodeType"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { AppDispatch } from "store/store"
import { arrayEqualityFn } from "utils/EqualityUtils"

type ItemSelectProps = {
  open: boolean
  setOpen: (value: boolean) => void
  filePath: string[] | undefined
} & NodeIdProps

export const BatchHDF5FileNode = memo(function BatchHDF5FileNode(
  element: NodeProps,
) {
  const defined = useSelector(selectInputNodeDefined(element.id))
  if (defined) {
    return <BatchHDF5FileNodeImple {...element} />
  } else {
    return null
  }
})

const BatchHDF5FileNodeImple = memo(function BatchHDF5FileNodeImple({
  id: nodeId,
  selected,
}: NodeProps) {
  const dispatch = useDispatch()
  const filePath = useSelector(
    selectInputNodeSelectedFilePath(nodeId),
    (a, b) =>
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
        fileType={FILE_TYPE_SET.BATCH_HDF5}
        filePath={
          Array.isArray(filePath) ? filePath : filePath ? [filePath] : []
        }
      />
      {filePath !== undefined &&
        Array.isArray(filePath) &&
        filePath.length > 0 && (
          <ItemSelect
            open={open}
            setOpen={setOpen}
            nodeId={nodeId}
            filePath={filePath}
          />
        )}
      <Handle
        type="source"
        position={Position.Right}
        id={toHandleId(nodeId, "hdf5", "HDF5Data")}
        style={{ ...HANDLE_STYLE }}
      />
    </NodeContainer>
  )
})

const ItemSelect = memo(function ItemSelect({
  nodeId,
  open,
  setOpen,
  filePath,
}: ItemSelectProps) {
  const [selectedPath, setSelectedPath] = useState("")
  const structureFileName = useSelector(selectInputNodeHDF5Path(nodeId))

  // Display structure selection status
  const displayText = structureFileName
    ? `Structure: ${structureFileName}`
    : "No structure is selected."

  return (
    <>
      <Typography className="selectFilePath" variant="caption">
        {displayText}
      </Typography>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth>
        <DialogTitle>
          {"Select File Structure (Applied to all files)"}
        </DialogTitle>
        <Structure
          nodeId={nodeId}
          firstFilePath={filePath?.[0]}
          selectedPath={selectedPath}
          setSelectedPath={setSelectedPath}
        />
        <DialogActions>
          <Button onClick={() => setOpen(false)} variant="outlined">
            cancel
          </Button>
          <Button
            onClick={() => setOpen(false)}
            color="primary"
            variant="contained"
            autoFocus
          >
            OK
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
})

const Structure = memo(function Structure({
  nodeId,
  firstFilePath,
  selectedPath,
  setSelectedPath,
}: NodeIdProps & {
  firstFilePath: string | undefined
  selectedPath: string
  setSelectedPath: (path: string) => void
}) {
  const theme = useTheme()
  const structureFileName = useSelector(selectInputNodeHDF5Path(nodeId))

  // Initialize selectedPath with current structure if exists
  useEffect(() => {
    if (structureFileName && !selectedPath) {
      setSelectedPath(structureFileName)
    }
  }, [structureFileName, selectedPath, setSelectedPath])

  return (
    <DialogContent dividers>
      {firstFilePath && (
        <Typography
          variant="caption"
          color="textSecondary"
          style={{ marginBottom: theme.spacing(1), display: "block" }}
        >
          Using first file for structure: {firstFilePath}
        </Typography>
      )}
      <div
        style={{
          height: 300,
          overflow: "auto",
          marginBottom: theme.spacing(1),
          border: "1px solid",
          padding: theme.spacing(1),
          borderColor: theme.palette.divider,
        }}
      >
        <FileTreeView
          nodeId={nodeId}
          firstFilePath={firstFilePath}
          onSelectPath={setSelectedPath}
        />
      </div>
      <Typography>Select Structure</Typography>
      <Typography variant="subtitle2">{selectedPath || "---"}</Typography>
    </DialogContent>
  )
})

const FileTreeView = memo(function FileTreeView({
  nodeId,
  firstFilePath,
  onSelectPath,
}: NodeIdProps & {
  firstFilePath: string | undefined
  onSelectPath: (path: string) => void
}) {
  const [tree, isLoading] = useBatchHDF5Tree(nodeId, firstFilePath)
  return (
    <div>
      {isLoading && <LinearProgress />}
      <TreeView>
        {tree?.map((node, i) => (
          <TreeNode
            key={`hdf5tree-${nodeId}-${i}`}
            node={node}
            nodeId={nodeId}
            onSelectPath={onSelectPath}
          />
        ))}
      </TreeView>
    </div>
  )
})

interface TreeNodeProps extends NodeIdProps {
  node: HDF5TreeNodeType
  onSelectPath: (path: string) => void
}

const TreeNode = memo(function TreeNode({
  node,
  nodeId,
  onSelectPath,
}: TreeNodeProps) {
  const dispatch = useDispatch()

  const onClickFile = (path: string) => {
    // Update both local state and global state
    onSelectPath(path)
    dispatch(setInputNodeHDF5Path({ nodeId, path }))
  }

  if (node.isDir) {
    // Directory
    return (
      <TreeItem
        icon={<FolderIcon htmlColor="skyblue" />}
        nodeId={node.path}
        label={node.name}
      >
        {node.nodes.map((childNode, i) => (
          <TreeNode
            node={childNode}
            key={i}
            nodeId={nodeId}
            onSelectPath={onSelectPath}
          />
        ))}
      </TreeItem>
    )
  } else {
    // File
    return (
      <TreeItem
        icon={<InsertDriveFileOutlinedIcon fontSize="small" />}
        nodeId={node.path}
        label={node.name + `   (shape=${node.shape}, nbytes=${node.nbytes})`}
        onClick={() => onClickFile(node.path)}
      />
    )
  }
})

function useBatchHDF5Tree(
  _nodeId: string,
  firstFilePath: string | undefined,
): [HDF5TreeNodeType[] | undefined, boolean] {
  const dispatch = useDispatch<AppDispatch>()
  const tree = useSelector(selectHDF5Nodes())
  const isLoading = useSelector(selectHDF5IsLoading())
  const workspaceId = useSelector(selectCurrentWorkspaceId)

  useEffect(() => {
    if (workspaceId && !isLoading && firstFilePath) {
      dispatch(getHDF5Tree({ path: firstFilePath, workspaceId }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, firstFilePath])

  return [tree, isLoading]
}
