import { memo, useEffect, useState } from "react"
import { useDispatch, useSelector } from "react-redux"
import { Handle, Position, NodeProps } from "reactflow"

import FolderIcon from "@mui/icons-material/Folder"
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined"
import { Box, Checkbox, Typography, Tooltip, Divider } from "@mui/material"
import Button from "@mui/material/Button"
import { CheckboxProps } from "@mui/material/Checkbox"
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
import { setInputNodeFilePath } from "store/slice/InputNode/InputNodeActions"
import {
  selectInputNodeDefined,
  selectInputNodeSelectedFilePath,
  selectInputNodeMatlabPath,
} from "store/slice/InputNode/InputNodeSelectors"
import { setInputNodeMatlabPath } from "store/slice/InputNode/InputNodeSlice"
import { FILE_TYPE_SET } from "store/slice/InputNode/InputNodeType"
import { getMatlabTree } from "store/slice/Matlab/MatlabAction"
import {
  selectMatlabIsLoading,
  selectMatlabNodes,
} from "store/slice/Matlab/MatlabSelectors"
import { MatlabTreeNodeType } from "store/slice/Matlab/MatlabType"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { AppDispatch } from "store/store"
import { arrayEqualityFn } from "utils/EqualityUtils"

type ItemSelectProps = {
  open: boolean
  setOpen: (value: boolean) => void
  filePath: string[] | undefined
} & NodeIdProps

export const BatchMatlabFileNode = memo(function BatchMatlabFileNode(
  element: NodeProps,
) {
  const defined = useSelector(selectInputNodeDefined(element.id))
  if (defined) {
    return <BatchMatlabFileNodeImple {...element} />
  } else {
    return null
  }
})

const BatchMatlabFileNodeImple = memo(function BatchMatlabFileNodeImple({
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
        fileType={FILE_TYPE_SET.BATCH_MATLAB}
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
        id={toHandleId(nodeId, "matlab", "MatlabData")}
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
  const dispatch = useDispatch<AppDispatch>()
  const [fileSelect, setFileSelect] = useState("")

  const structureFileName = useSelector(selectInputNodeMatlabPath(nodeId))

  const onClickOk = () => {
    dispatch(setInputNodeMatlabPath({ nodeId, path: fileSelect }))
    setOpen?.(false)
  }

  const onClickCancel = () => {
    setFileSelect("")
    setOpen?.(false)
  }

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
          fileSelect={fileSelect}
          setFileSelect={setFileSelect}
          filePath={filePath}
        />
        <DialogActions>
          <Button onClick={onClickCancel} color="primary" variant="outlined">
            cancel
          </Button>
          <Button onClick={onClickOk} variant="contained" autoFocus>
            OK
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
})

const Structure = memo(function Structure({
  nodeId,
  fileSelect,
  setFileSelect,
  filePath,
}: NodeIdProps & {
  fileSelect: string
  setFileSelect: (value: string) => void
  filePath: string[] | undefined
}) {
  const theme = useTheme()
  return (
    <DialogContent dividers>
      {filePath && filePath.length > 0 && (
        <Typography
          variant="caption"
          color="textSecondary"
          style={{ marginBottom: theme.spacing(1), display: "block" }}
        >
          Using first file for structure: {filePath[0]}
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
        {filePath && filePath.length > 0 && (
          <FileTreeView
            nodeId={nodeId}
            fileSelect={fileSelect}
            setFileSelect={setFileSelect}
            filePath={filePath[0]}
          />
        )}
      </div>
      <Typography>Select File</Typography>
      <Typography variant="subtitle2">{fileSelect || "---"}</Typography>
    </DialogContent>
  )
})

const FileTreeView = memo(function FileTreeView({
  nodeId,
  fileSelect,
  setFileSelect,
  filePath,
}: NodeIdProps & {
  fileSelect: string
  setFileSelect: (value: string) => void
  filePath: string
}) {
  const [tree, isLoading] = useMatlabTree(filePath)
  return (
    <div>
      {isLoading && <LinearProgress />}
      <Box display={"flex"} paddingBottom={1}>
        <Box flexGrow={4}>Structure</Box>
        <Box flexGrow={2}>Type</Box>
        <Box flexGrow={3}>Shape</Box>
        <Box flexGrow={1}></Box>
      </Box>
      <Divider />
      <TreeView>
        {tree?.map((node, i) => (
          <TreeNode
            fileSelect={fileSelect}
            setFileSelect={setFileSelect}
            key={`matlabtree-${nodeId}-${i}`}
            node={node}
            nodeId={nodeId}
          />
        ))}
      </TreeView>
    </div>
  )
})

interface TreeItemLabelProps {
  isFile: boolean
  shape: number[]
  type: string | null
  label: string
  checkboxProps: CheckboxProps
}

const TreeItemLabel = memo(function TreeItemLabel({
  isFile = false,
  label,
  shape,
  type,
  checkboxProps,
}: TreeItemLabelProps) {
  return (
    <Box display="flex" alignItems="center" gap={2}>
      <Tooltip
        title={<span style={{ fontSize: 14 }}>{label}</span>}
        placement={"left"}
      >
        <Box
          width={isFile ? "35%" : "32%"}
          overflow={"hidden"}
          textOverflow={"ellipsis"}
        >
          {label}
        </Box>
      </Tooltip>
      <Box width={"20%"}>{type}</Box>
      <Box width={"25%"}>{shape ? `(${shape.join(", ")})` : ""}</Box>
      <Box>
        <Checkbox
          {...checkboxProps}
          disableRipple
          size="small"
          sx={{
            marginRight: "4px",
            padding: "2px",
          }}
        />
      </Box>
    </Box>
  )
})

interface TreeNodeProps extends NodeIdProps {
  setFileSelect?: (value: string) => void
  fileSelect?: string
  node: MatlabTreeNodeType
}

const TreeNode = memo(function TreeNode({
  node,
  nodeId,
  setFileSelect,
  fileSelect,
}: TreeNodeProps) {
  const dispatch = useDispatch()
  const structureFileName = useSelector(selectInputNodeMatlabPath(nodeId))
  useEffect(() => {
    if (!structureFileName) return
    setFileSelect?.(structureFileName)
    //eslint-disable-next-line
  }, [dispatch, structureFileName])
  const onClickFile = (path: string) => {
    setFileSelect?.(path === fileSelect ? "" : path)
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
            setFileSelect={setFileSelect}
            fileSelect={fileSelect}
            node={childNode}
            key={i}
            nodeId={nodeId}
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
        label={
          <TreeItemLabel
            isFile={true}
            label={node.name}
            type={node.dataType}
            shape={node.shape}
            checkboxProps={{
              checked: fileSelect === node.path,
            }}
          />
        }
        onClick={() => onClickFile(node.path)}
      />
    )
  }
})

function useMatlabTree(
  filePath: string,
): [MatlabTreeNodeType[] | undefined, boolean] {
  const dispatch = useDispatch<AppDispatch>()
  const tree = useSelector(selectMatlabNodes())
  const isLoading = useSelector(selectMatlabIsLoading())
  const workspaceId = useSelector(selectCurrentWorkspaceId)
  useEffect(() => {
    if (workspaceId && !isLoading && filePath) {
      dispatch(getMatlabTree({ path: filePath as string, workspaceId }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, filePath])
  return [tree, isLoading]
}
