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
  ...Object.fromEntries(
    Object.entries(FILE_TYPE_CONFIGS).map(([, config]) => [
      config.nodeComponent,
      config.reactFlowNodeType,
    ]),
  ),
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
