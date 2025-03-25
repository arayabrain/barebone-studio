import { CustomEdge } from "components/Workspace/FlowChart/CustomEdge"
import { AlgorithmNode } from "components/Workspace/FlowChart/FlowChartNode/AlgorithmNode"
import { BehaviorFileNode } from "components/Workspace/FlowChart/FlowChartNode/BehaviorFileNode"
import { CsvFileNode } from "components/Workspace/FlowChart/FlowChartNode/CsvFileNode"
import { ExpDbNode } from "components/Workspace/FlowChart/FlowChartNode/ExpDbNode"
import { FluoFileNode } from "components/Workspace/FlowChart/FlowChartNode/FluoFileNode"
import { HDF5FileNode } from "components/Workspace/FlowChart/FlowChartNode/HDF5FileNode"
import { ImageFileNode } from "components/Workspace/FlowChart/FlowChartNode/ImageFileNode"
import { MatlabFileNode } from "components/Workspace/FlowChart/FlowChartNode/MatlabFileNode"
import { MicroscopeExpdbFileNode } from "components/Workspace/FlowChart/FlowChartNode/MicroscopeExpdbFileNode"
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
  MicroscopeExpdbFileNode,
  ExpDbNode,
} as const

export const reactFlowEdgeTypes = {
  buttonedge: CustomEdge,
} as const
