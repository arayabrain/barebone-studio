import { createSlice, isAnyOf, PayloadAction } from "@reduxjs/toolkit"

import { isInputNodePostData } from "api/run/RunUtils"
import { INITIAL_IMAGE_ELEMENT_ID } from "const/flowchart"
import { FileNodeFactory } from "factories/FileNodeFactory"
import { uploadFile } from "store/slice/FileUploader/FileUploaderActions"
import { addInputNode } from "store/slice/FlowElement/FlowElementActions"
import {
  clearFlowElements,
  deleteFlowNodes,
  deleteFlowNodeById,
} from "store/slice/FlowElement/FlowElementSlice"
import { NODE_TYPE_SET } from "store/slice/FlowElement/FlowElementType"
import { setInputNodeFilePath } from "store/slice/InputNode/InputNodeActions"
import {
  CsvInputParamType,
  FILE_TYPE_SET,
  InputNode,
  INPUT_NODE_SLICE_NAME,
} from "store/slice/InputNode/InputNodeType"
import {
  isCsvInputNode,
  isHDF5InputNode,
  isMatlabInputNode,
} from "store/slice/InputNode/InputNodeUtils"
import {
  reproduceWorkflow,
  importWorkflowConfig,
  fetchWorkflow,
} from "store/slice/Workflow/WorkflowActions"

const initialState: InputNode = {
  [INITIAL_IMAGE_ELEMENT_ID]: {
    fileType: FILE_TYPE_SET.IMAGE,
    param: {},
  },
} as InputNode

export const inputNodeSlice = createSlice({
  name: INPUT_NODE_SLICE_NAME,
  initialState,
  reducers: {
    deleteInputNode(state, action: PayloadAction<string>) {
      delete state[action.payload]
    },
    setCsvInputNodeParam(
      state,
      action: PayloadAction<{
        nodeId: string
        param: CsvInputParamType
      }>,
    ) {
      const { nodeId, param } = action.payload
      const inputNode = state[nodeId]
      if (isCsvInputNode(inputNode)) {
        inputNode.param = param
      }
    },
    setInputNodeMatlabPath(
      state,
      action: PayloadAction<{
        nodeId: string
        path: string
      }>,
    ) {
      const { nodeId, path } = action.payload
      const item = state[nodeId]
      if (isMatlabInputNode(item)) {
        item.matPath = path
      }
    },
    setInputNodeHDF5Path(
      state,
      action: PayloadAction<{
        nodeId: string
        path: string
      }>,
    ) {
      const { nodeId, path } = action.payload
      const item = state[nodeId]
      if (isHDF5InputNode(item)) {
        item.hdf5Path = path
      }
    },
  },
  extraReducers: (builder) =>
    builder
      .addCase(setInputNodeFilePath, (state, action) => {
        const { nodeId, filePath } = action.payload
        const targetNode = state[nodeId]
        targetNode.selectedFilePath = filePath
        if (isHDF5InputNode(targetNode)) {
          targetNode.hdf5Path = undefined
        }
      })
      .addCase(addInputNode, (state, action) => {
        const { node, fileType } = action.payload
        if (node.data?.type === NODE_TYPE_SET.INPUT) {
          try {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            state[node.id] = FileNodeFactory.createInputNode(fileType) as any
          } catch (error) {
            // eslint-disable-next-line no-console
            console.warn(`Unsupported file type: ${fileType}`, error)
          }
        }
      })
      .addCase(clearFlowElements, () => initialState)
      .addCase(deleteFlowNodes, (state, action) => {
        action.payload.forEach((node) => {
          if (node.data?.type === NODE_TYPE_SET.INPUT) {
            delete state[node.id]
          }
        })
      })
      .addCase(deleteFlowNodeById, (state, action) => {
        if (Object.keys(state).includes(action.payload)) {
          delete state[action.payload]
        }
      })
      .addCase(uploadFile.fulfilled, (state, action) => {
        const { nodeId } = action.meta.arg
        if (nodeId != null) {
          const { resultPath } = action.payload
          const target = state[nodeId]
          if (target) {
            const filePathType = FileNodeFactory.getFilePathType(
              target.fileType,
            )
            if (filePathType === "array") {
              target.selectedFilePath = [resultPath]
            } else {
              target.selectedFilePath = resultPath
            }
          }
        }
      })
      .addCase(fetchWorkflow.rejected, () => initialState)
      .addCase(importWorkflowConfig.fulfilled, (_, action) => {
        const newState: InputNode = {}
        Object.values(action.payload.nodeDict)
          .filter(isInputNodePostData)
          .forEach((node) => {
            if (node.data?.fileType != null) {
              try {
                const baseNode = FileNodeFactory.createInputNode(
                  node.data.fileType,
                )
                // Use specific param for CSV nodes
                const param =
                  node.data.fileType === FILE_TYPE_SET.CSV
                    ? (node.data.param as CsvInputParamType)
                    : baseNode.param
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                newState[node.id] = {
                  ...baseNode,
                  param,
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                } as any
              } catch (error) {
                // eslint-disable-next-line no-console
                console.warn(
                  `Unsupported file type: ${node.data.fileType}`,
                  error,
                )
              }
            }
          })
        return newState
      })
      .addMatcher(
        isAnyOf(fetchWorkflow.fulfilled, reproduceWorkflow.fulfilled),
        (_, action) => {
          const newState: InputNode = {}
          Object.values(action.payload.nodeDict)
            .filter(isInputNodePostData)
            .forEach((node) => {
              if (node.data?.fileType != null) {
                try {
                  const baseNode = FileNodeFactory.createInputNode(
                    node.data.fileType,
                  )
                  const filePathType = FileNodeFactory.getFilePathType(
                    node.data.fileType,
                  )
                  const specialPath = FileNodeFactory.getSpecialPathConfig(
                    node.data.fileType,
                  )

                  // Use specific param for CSV nodes
                  const param =
                    node.data.fileType === FILE_TYPE_SET.CSV
                      ? (node.data.param as CsvInputParamType)
                      : baseNode.param

                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  const nodeState: any = {
                    ...baseNode,
                    param,
                    selectedFilePath:
                      filePathType === "array"
                        ? (node.data.path as string[])
                        : (node.data.path as string),
                  }

                  // Add special path properties if configured
                  if (specialPath) {
                    if (
                      specialPath.type === "hdf5Path" &&
                      "hdf5Path" in node.data
                    ) {
                      nodeState.hdf5Path = node.data.hdf5Path
                    } else if (
                      specialPath.type === "matPath" &&
                      "matPath" in node.data
                    ) {
                      nodeState.matPath = node.data.matPath
                    }
                  }

                  newState[node.id] = nodeState
                } catch (error) {
                  // eslint-disable-next-line no-console
                  console.warn(
                    `Unsupported file type: ${node.data.fileType}`,
                    error,
                  )
                }
              }
            })
          return newState
        },
      ),
})

export const {
  setCsvInputNodeParam,
  setInputNodeMatlabPath,
  setInputNodeHDF5Path,
} = inputNodeSlice.actions

export default inputNodeSlice.reducer
