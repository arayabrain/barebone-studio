import { CustomEdge } from "components/Workspace/FlowChart/CustomEdge"
import { AlgorithmNode } from "components/Workspace/FlowChart/FlowChartNode/AlgorithmNode"
import { BatchImageFileNode } from "components/Workspace/FlowChart/FlowChartNode/BatchImageFileNode"
import { BehaviorFileNode } from "components/Workspace/FlowChart/FlowChartNode/BehaviorFileNode"
import { CsvFileNode } from "components/Workspace/FlowChart/FlowChartNode/CsvFileNode"
import { FluoFileNode } from "components/Workspace/FlowChart/FlowChartNode/FluoFileNode"
import { HDF5FileNode } from "components/Workspace/FlowChart/FlowChartNode/HDF5FileNode"
import { ImageFileNode } from "components/Workspace/FlowChart/FlowChartNode/ImageFileNode"
import { MatlabFileNode } from "components/Workspace/FlowChart/FlowChartNode/MatlabFileNode"
import { MicroscopeFileNode } from "components/Workspace/FlowChart/FlowChartNode/MicroscopeFileNode"

export const reactFlowNodeTypes = {
  ImageFileNode,
  CsvFileNode,
  MatlabFileNode,
  HDF5FileNode,
  AlgorithmNode,
  FluoFileNode,
  BehaviorFileNode,
  MicroscopeFileNode,
  BatchImageFileNode,
} as const

export const reactFlowEdgeTypes = {
  buttonedge: CustomEdge,
} as const
