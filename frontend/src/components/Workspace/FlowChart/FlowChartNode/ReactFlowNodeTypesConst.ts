import React from "react"
import { NodeProps } from "reactflow"

import { CustomEdge } from "components/Workspace/FlowChart/CustomEdge"
import { AlgorithmNode } from "components/Workspace/FlowChart/FlowChartNode/AlgorithmNode"
import { BehaviorFileNode } from "components/Workspace/FlowChart/FlowChartNode/BehaviorFileNode"
import { CsvFileNode } from "components/Workspace/FlowChart/FlowChartNode/CsvFileNode"
import { FluoFileNode } from "components/Workspace/FlowChart/FlowChartNode/FluoFileNode"
import { HDF5FileNode } from "components/Workspace/FlowChart/FlowChartNode/HDF5FileNode"
import { ImageFileNode } from "components/Workspace/FlowChart/FlowChartNode/ImageFileNode"
import { MatlabFileNode } from "components/Workspace/FlowChart/FlowChartNode/MatlabFileNode"
import { MicroscopeFileNode } from "components/Workspace/FlowChart/FlowChartNode/MicroscopeFileNode"
import { getAllFileTypeConfigs } from "config/fileTypes.config"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ComponentType = React.ComponentType<NodeProps<any>>

// Create node types mapping from config
const createNodeTypesFromConfig = () => {
  const nodeTypes: Record<string, ComponentType> = {
    AlgorithmNode, // Algorithm node is not part of file types
  }

  // Dynamic component mapping from config
  const componentMap: Record<string, ComponentType> = {
    ImageFileNode,
    CsvFileNode,
    MatlabFileNode,
    HDF5FileNode,
    FluoFileNode,
    BehaviorFileNode,
    MicroscopeFileNode,
  }

  getAllFileTypeConfigs().forEach((config) => {
    const component = componentMap[config.nodeComponent]
    if (component) {
      nodeTypes[config.reactFlowNodeType] = component
    }
  })

  return nodeTypes
}

export const reactFlowNodeTypes = createNodeTypesFromConfig()

export const reactFlowEdgeTypes = {
  buttonedge: CustomEdge,
} as const
