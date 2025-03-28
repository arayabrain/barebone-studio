import {
  Node,
  NodeChange,
  Edge,
  EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
  Position,
  Transform,
} from "reactflow"

import { createSlice, PayloadAction, isAnyOf } from "@reduxjs/toolkit"

import { isInputNodePostData } from "api/run/RunUtils"
import {
  ALGO_NODE_STYLE,
  DATA_NODE_STYLE,
  INITIAL_IMAGE_ELEMENT_ID,
  INITIAL_IMAGE_ELEMENT_NAME,
  REACT_FLOW_NODE_TYPE_KEY,
} from "const/flowchart"
import { uploadFile } from "store/slice/FileUploader/FileUploaderActions"
import {
  addAlgorithmNode,
  addInputNode,
} from "store/slice/FlowElement/FlowElementActions"
import {
  FLOW_ELEMENT_SLICE_NAME,
  FlowElement,
  NODE_TYPE_SET,
  NodeData,
  ElementCoord,
} from "store/slice/FlowElement/FlowElementType"
import { getLabelByPath } from "store/slice/FlowElement/FlowElementUtils"
import { setInputNodeFilePath } from "store/slice/InputNode/InputNodeActions"
import {
  reproduceWorkflow,
  importWorkflowConfig,
  fetchWorkflow,
} from "store/slice/Workflow/WorkflowActions"

const initialNodes: Node<NodeData>[] = [
  {
    id: INITIAL_IMAGE_ELEMENT_ID,
    type: REACT_FLOW_NODE_TYPE_KEY.ImageFileNode,
    data: {
      type: NODE_TYPE_SET.INPUT,
      label: INITIAL_IMAGE_ELEMENT_NAME,
    },
    style: DATA_NODE_STYLE,
    position: { x: 50, y: 150 },
  },
]

const initialFlowPosition: Transform = [0, 0, 0.7] // [x, y, zoom]

const initialElementCoord: ElementCoord = {
  x: 100,
  y: 150,
}

const initialState: FlowElement = {
  flowNodes: initialNodes,
  flowEdges: [],
  flowPosition: initialFlowPosition,
  elementCoord: initialElementCoord,
  loading: false,
}

export const flowElementSlice = createSlice({
  name: FLOW_ELEMENT_SLICE_NAME,
  initialState,
  reducers: {
    clearFlowElements: (state) => {
      state.flowNodes = applyNodeChanges(
        state.flowNodes.map((node) => {
          return { id: node.id, type: "remove" }
        }),
        state.flowNodes,
      )
      state.flowNodes = initialNodes
      state.flowEdges = applyEdgeChanges(
        state.flowEdges.map((edge) => {
          return { id: edge.id, type: "remove" }
        }),
        state.flowEdges,
      )
      state.flowPosition = initialFlowPosition
      state.elementCoord = initialElementCoord
    },
    setFlowPosition: (state, action: PayloadAction<Transform>) => {
      state.flowPosition = action.payload
    },
    setFlowNodes: (state, action: PayloadAction<Node[]>) => {
      state.flowNodes = action.payload
    },
    setFlowEdges: (state, action: PayloadAction<Edge[]>) => {
      state.flowEdges = action.payload
    },
    deleteFlowNodes: (state, action: PayloadAction<Node[]>) => {
      state.flowNodes = applyNodeChanges(
        action.payload.map((node) => {
          return { id: node.id, type: "remove" }
        }),
        state.flowNodes,
      )
    },
    setNodesChange: (state, action: PayloadAction<NodeChange[]>) => {
      state.flowNodes = applyNodeChanges(action.payload, state.flowNodes)
    },
    setEdgesChange: (state, action: PayloadAction<EdgeChange[]>) => {
      state.flowEdges = applyEdgeChanges(action.payload, state.flowEdges)
    },
    deleteFlowEdgeById: (state, action: PayloadAction<string>) => {
      const element = state.flowEdges.find((edge) => edge.id === action.payload)
      if (element !== undefined) {
        state.flowEdges = applyEdgeChanges(
          [{ id: element.id, type: "remove" }],
          state.flowEdges,
        )
      }
    },
    deleteFlowNodeById: (state, action: PayloadAction<string>) => {
      const element = state.flowNodes.find((node) => node.id === action.payload)
      if (element !== undefined) {
        state.flowNodes = applyNodeChanges(
          [{ id: element.id, type: "remove" }],
          state.flowNodes,
        )
        state.flowEdges = applyEdgeChanges(
          state.flowEdges
            .filter((edge) => {
              return (
                edge.source === action.payload || edge.target === action.payload
              )
            })
            .map((edge) => {
              return { id: edge.id, type: "remove" }
            }),
          state.flowEdges,
        )
      }
    },
    editFlowNodePositionById: (
      state,
      action: PayloadAction<{
        nodeId: string
        coord: {
          x: number
          y: number
        }
      }>,
    ) => {
      const { nodeId, coord } = action.payload
      const elementIdx = state.flowNodes.findIndex((node) => node.id === nodeId)
      const targetItem = state.flowNodes[elementIdx]
      targetItem.position = coord
    },
  },
  extraReducers: (builder) =>
    builder
      .addCase(addAlgorithmNode.fulfilled, (state, action) => {
        let { node } = action.meta.arg
        if (node.data?.type === NODE_TYPE_SET.ALGORITHM) {
          node = {
            ...node,
            style: {
              ...node.style,
              ...ALGO_NODE_STYLE,
            },
            targetPosition: Position.Left,
            sourcePosition: Position.Right,
          }
        }
        if (node.position != null) {
          state.flowNodes.push({ ...node, position: node.position })
        } else {
          state.flowNodes.push({ ...node, position: state.elementCoord })
          updateElementCoord(state)
        }
      })
      .addCase(addInputNode, (state, action) => {
        let { node } = action.payload
        if (node.data?.type === NODE_TYPE_SET.INPUT) {
          node = {
            ...node,
            style: {
              ...node.style,
              ...DATA_NODE_STYLE,
            },
            targetPosition: Position.Left,
            sourcePosition: Position.Right,
          }
        }
        if (node.position != null) {
          state.flowNodes.push({ ...node, position: node.position })
        } else {
          state.flowNodes.push({ ...node, position: state.elementCoord })
          updateElementCoord(state)
        }
      })
      .addCase(setInputNodeFilePath, (state, action) => {
        const { nodeId, filePath } = action.payload
        const label = getLabelByPath(filePath)
        const nodeIdx = state.flowNodes.findIndex((node) => node.id === nodeId)
        const targetNode = state.flowNodes[nodeIdx]
        if (targetNode.data != null) {
          targetNode.data.label = label
        }
      })
      .addCase(uploadFile.fulfilled, (state, action) => {
        const { nodeId } = action.meta.arg
        if (nodeId != null) {
          const nodeIdx = state.flowNodes.findIndex(
            (node) => node.id === nodeId,
          )
          const targetNode = state.flowNodes[nodeIdx]
          if (targetNode.data != null) {
            targetNode.data.label = getLabelByPath(action.payload.resultPath)
          }
        }
      })
      .addCase(fetchWorkflow.pending, (state) => {
        state.loading = true
      })
      .addCase(reproduceWorkflow.pending, (state) => {
        state.loading = true
      })
      .addCase(fetchWorkflow.rejected, () => initialState)
      .addCase(reproduceWorkflow.rejected, (state) => {
        state.loading = false
      })
      .addMatcher(
        isAnyOf(
          reproduceWorkflow.fulfilled,
          importWorkflowConfig.fulfilled,
          fetchWorkflow.fulfilled,
        ),
        (state, action) => {
          state.flowPosition = initialFlowPosition
          state.elementCoord = initialElementCoord
          state.flowNodes = Object.values(action.payload.nodeDict).map(
            (node) => {
              if (isInputNodePostData(node)) {
                return {
                  ...node,
                  data: {
                    label: node.data?.label ?? "",
                    type: node.data?.type ?? "input",
                  },
                  style: DATA_NODE_STYLE,
                }
              } else {
                return {
                  ...node,
                  data: {
                    label: node.data?.label ?? "",
                    type: node.data?.type ?? "algorithm",
                  },
                  style: ALGO_NODE_STYLE,
                }
              }
            },
          )
          state.flowEdges = Object.values(action.payload.edgeDict)
          state.loading = false
        },
      ),
})

function getRandomArbitrary(min: number, max: number) {
  return Math.random() * (max - min) + min
}

function updateElementCoord(state: FlowElement) {
  const { x } = state.elementCoord
  if (x > 800) {
    state.elementCoord.x = 300
    state.elementCoord.y += 100
  } else {
    state.elementCoord.x += 250
    state.elementCoord.y += getRandomArbitrary(-20, 20)
  }
}

export const {
  clearFlowElements,
  setNodesChange,
  setEdgesChange,
  setFlowPosition,
  setFlowNodes,
  setFlowEdges,
  deleteFlowNodes,
  deleteFlowEdgeById,
  deleteFlowNodeById,
  editFlowNodePositionById,
} = flowElementSlice.actions

export default flowElementSlice.reducer
