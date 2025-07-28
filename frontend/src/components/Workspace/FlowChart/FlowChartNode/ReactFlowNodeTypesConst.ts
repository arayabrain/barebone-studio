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
import {
  getAllFileTypeConfigs,
  COMPONENT_MAPPING,
} from "config/fileTypes.config"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ComponentType = React.ComponentType<NodeProps<any>>

// Create node types mapping from config
const createNodeTypesFromConfig = () => {
  const nodeTypes: Record<string, ComponentType> = {
    AlgorithmNode, // Algorithm node is not part of file types
  }

  // Create component map from imported components and config
  const componentMap: Record<string, ComponentType> = {
    [COMPONENT_MAPPING.ImageFileNode]: ImageFileNode,
    [COMPONENT_MAPPING.CsvFileNode]: CsvFileNode,
    [COMPONENT_MAPPING.MatlabFileNode]: MatlabFileNode,
    [COMPONENT_MAPPING.HDF5FileNode]: HDF5FileNode,
    [COMPONENT_MAPPING.FluoFileNode]: FluoFileNode,
    [COMPONENT_MAPPING.BehaviorFileNode]: BehaviorFileNode,
    [COMPONENT_MAPPING.MicroscopeFileNode]: MicroscopeFileNode,
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
