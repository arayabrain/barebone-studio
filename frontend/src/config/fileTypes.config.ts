export interface FileTypeConfig {
  key: string
  displayName: string
  reactFlowNodeType: string
  treeType: string
  hasFilePath: boolean
  filePathType: "single" | "array"
  hasSpecialPath?: {
    name: string
    type: "matPath" | "hdf5Path"
  }
  defaultParam: Record<string, unknown>
  nodeComponent: string
  stateFileType?: string // For special cases like FLUO/BEHAVIOR stored as CSV
  dataType: string // Mapping to DATA_TYPE for visualization
  componentPath: string // Path for dynamic component import
}

export const FILE_TYPE_CONFIGS: Record<string, FileTypeConfig> = {
  IMAGE: {
    key: "image",
    displayName: "imageData",
    reactFlowNodeType: "ImageFileNode",
    treeType: "image",
    hasFilePath: true,
    filePathType: "array",
    defaultParam: {},
    nodeComponent: "ImageFileNode",
    dataType: "image",
    componentPath: "components/Workspace/FlowChart/FlowChartNode/ImageFileNode",
  },
  CSV: {
    key: "csv",
    displayName: "csvData",
    reactFlowNodeType: "CsvFileNode",
    treeType: "csv",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {
      setHeader: null,
      setIndex: false,
      transpose: false,
    },
    nodeComponent: "CsvFileNode",
    dataType: "csv",
    componentPath: "components/Workspace/FlowChart/FlowChartNode/CsvFileNode",
  },
  HDF5: {
    key: "hdf5",
    displayName: "hdf5Data",
    reactFlowNodeType: "HDF5FileNode",
    treeType: "hdf5",
    hasFilePath: true,
    filePathType: "single",
    hasSpecialPath: {
      name: "hdf5Path",
      type: "hdf5Path",
    },
    defaultParam: {},
    nodeComponent: "HDF5FileNode",
    dataType: "hdf5",
    componentPath: "components/Workspace/FlowChart/FlowChartNode/HDF5FileNode",
  },
  FLUO: {
    key: "fluo",
    displayName: "fluoData",
    reactFlowNodeType: "FluoFileNode",
    treeType: "fluo",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {
      setHeader: null,
      setIndex: false,
      transpose: false,
    },
    nodeComponent: "FluoFileNode",
    // Special handling: stored as CSV in state
    stateFileType: "csv",
    dataType: "fluo",
    componentPath: "components/Workspace/FlowChart/FlowChartNode/FluoFileNode",
  },
  BEHAVIOR: {
    key: "behavior",
    displayName: "behaviorData",
    reactFlowNodeType: "BehaviorFileNode",
    treeType: "behavior",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {
      setHeader: null,
      setIndex: false,
      transpose: false,
    },
    nodeComponent: "BehaviorFileNode",
    // Special handling: stored as CSV in state
    stateFileType: "csv",
    dataType: "behavior",
    componentPath:
      "components/Workspace/FlowChart/FlowChartNode/BehaviorFileNode",
  },
  MATLAB: {
    key: "matlab",
    displayName: "matlabData",
    reactFlowNodeType: "MatlabFileNode",
    treeType: "matlab",
    hasFilePath: true,
    filePathType: "single",
    hasSpecialPath: {
      name: "matPath",
      type: "matPath",
    },
    defaultParam: {},
    nodeComponent: "MatlabFileNode",
    dataType: "matlab",
    componentPath:
      "components/Workspace/FlowChart/FlowChartNode/MatlabFileNode",
  },
  MICROSCOPE: {
    key: "microscope",
    displayName: "microscopeData",
    reactFlowNodeType: "MicroscopeFileNode",
    treeType: "microscope",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {},
    nodeComponent: "MicroscopeFileNode",
    dataType: "matlab",
    componentPath:
      "components/Workspace/FlowChart/FlowChartNode/MicroscopeFileNode",
  },
} as const

// 自動生成される型定義
export type FILE_TYPE_KEY = keyof typeof FILE_TYPE_CONFIGS
export type FILE_TYPE = (typeof FILE_TYPE_CONFIGS)[FILE_TYPE_KEY]["key"]

// 既存のコンスタントと互換性を保つ
export const FILE_TYPE_SET = Object.fromEntries(
  Object.entries(FILE_TYPE_CONFIGS).map(([key, config]) => [key, config.key]),
) as Record<FILE_TYPE_KEY, string>

// より具体的な型定義
export const FILE_TYPES = {
  CSV: "csv" as const,
  IMAGE: "image" as const,
  HDF5: "hdf5" as const,
  FLUO: "fluo" as const,
  BEHAVIOR: "behavior" as const,
  MATLAB: "matlab" as const,
  MICROSCOPE: "microscope" as const,
} as const

export type FILE_TYPE_LITERAL = (typeof FILE_TYPES)[keyof typeof FILE_TYPES]

export const FILE_TREE_TYPE_SET = {
  IMAGE: "image",
  CSV: "csv",
  HDF5: "hdf5",
  FLUO: "fluo",
  BEHAVIOR: "behavior",
  MATLAB: "matlab",
  MICROSCOPE: "microscope",
  ALL: "all",
} as const

export const REACT_FLOW_NODE_TYPE_KEY = {
  ImageFileNode: "ImageFileNode",
  CsvFileNode: "CsvFileNode",
  HDF5FileNode: "HDF5FileNode",
  FluoFileNode: "FluoFileNode",
  BehaviorFileNode: "BehaviorFileNode",
  MatlabFileNode: "MatlabFileNode",
  MicroscopeFileNode: "MicroscopeFileNode",
  AlgorithmNode: "AlgorithmNode",
} as const

// ヘルパー関数
export function getFileTypeConfig(
  fileType: FILE_TYPE,
): FileTypeConfig | undefined {
  return Object.values(FILE_TYPE_CONFIGS).find(
    (config) => config.key === fileType,
  )
}

export function getFileTypeConfigByKey(key: FILE_TYPE_KEY): FileTypeConfig {
  return FILE_TYPE_CONFIGS[key]
}

export function getAllFileTypeConfigs(): FileTypeConfig[] {
  return Object.values(FILE_TYPE_CONFIGS)
}

// Type generation helpers for new file types
export function generateFileTypeInterface(config: FileTypeConfig): string {
  const interfaceName = `${config.key.charAt(0).toUpperCase() + config.key.slice(1)}InputNode`
  const fileType = config.stateFileType || config.key

  let specialPathProperty = ""
  if (config.hasSpecialPath) {
    specialPathProperty = `\n  ${config.hasSpecialPath.name}?: string`
  }

  return `
export interface ${interfaceName}
  extends InputNodeBaseType<"${fileType}", Record<string, unknown>> {
  selectedFilePath?: ${config.filePathType === "array" ? "string[]" : "string"}${specialPathProperty}
}`
}

export function generateTypePredicateFunction(config: FileTypeConfig): string {
  const functionName = `is${config.key.charAt(0).toUpperCase() + config.key.slice(1)}InputNode`
  const interfaceName = `${config.key.charAt(0).toUpperCase() + config.key.slice(1)}InputNode`

  return `
export function ${functionName}(
  inputNode: InputNodeType,
): inputNode is ${interfaceName} {
  return inputNode.fileType === FILE_TYPE_SET.${config.key.toUpperCase()}
}`
}

// Development helper: Generate code snippets for new file types
export function generateNewFileTypeCode(newConfig: FileTypeConfig): {
  interface: string
  predicate: string
  selector: string
  import: string
} {
  const capitalizedName =
    newConfig.key.charAt(0).toUpperCase() + newConfig.key.slice(1)

  return {
    interface: generateFileTypeInterface(newConfig),
    predicate: generateTypePredicateFunction(newConfig),
    selector: `export const select${capitalizedName}InputNodeSelectedFilePath = createTypedFilePathSelector("${newConfig.key}", is${capitalizedName}InputNode)`,
    import: `import { ${capitalizedName}FileNode } from "${newConfig.componentPath}"`,
  }
}

// Component mapping for ReactFlowNodeTypesConst
export const COMPONENT_MAPPING = {
  ImageFileNode: "ImageFileNode",
  CsvFileNode: "CsvFileNode",
  HDF5FileNode: "HDF5FileNode",
  FluoFileNode: "FluoFileNode",
  BehaviorFileNode: "BehaviorFileNode",
  MatlabFileNode: "MatlabFileNode",
  MicroscopeFileNode: "MicroscopeFileNode",
} as const

// Data type mapping for DataTypeUtils - maps config dataType to DATA_TYPE_SET values
export const DATA_TYPE_MAPPING = {
  image: "image",
  csv: "csv",
  hdf5: "hdf5",
  fluo: "fluo",
  behavior: "behavior",
  matlab: "matlab",
} as const
