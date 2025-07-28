export interface FileTypeConfig {
  key: string
  displayName: string
  hasFilePath: boolean
  filePathType: "single" | "array"
  hasSpecialPath?: {
    name: string
    type: "matPath" | "hdf5Path"
  }
  defaultParam: Record<string, unknown>
  stateFileType?: string // For special cases like FLUO/BEHAVIOR stored as CSV
  // Optional overrides - defaults to generated from key or REACT_FLOW_NODE_TYPE_KEY
  treeType?: string
  dataType?: string
  nodeType?: string // Unified: replaces nodeComponent and reactFlowNodeType
  componentPath?: string
}

// Enhanced config with computed properties
export interface EnhancedFileTypeConfig
  extends Required<Omit<FileTypeConfig, "hasSpecialPath" | "stateFileType">> {
  hasSpecialPath?: FileTypeConfig["hasSpecialPath"]
  stateFileType?: string
  // Backward compatibility properties
  nodeComponent: string // Same as nodeType for compatibility
  reactFlowNodeType: string // Same as nodeType for compatibility
}

// Define file tree types to maintain type compatibility
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

// Define node types first to avoid circular dependencies
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

// Streamlined config - nodeType references REACT_FLOW_NODE_TYPE_KEY
export const FILE_TYPE_CONFIGS: Record<string, FileTypeConfig> = {
  IMAGE: {
    key: "image",
    displayName: "imageData",
    hasFilePath: true,
    filePathType: "array",
    defaultParam: {},
    nodeType: REACT_FLOW_NODE_TYPE_KEY.ImageFileNode,
  },
  CSV: {
    key: "csv",
    displayName: "csvData",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {
      setHeader: null,
      setIndex: false,
      transpose: false,
    },
    nodeType: REACT_FLOW_NODE_TYPE_KEY.CsvFileNode,
  },
  HDF5: {
    key: "hdf5",
    displayName: "hdf5Data",
    hasFilePath: true,
    filePathType: "single",
    hasSpecialPath: {
      name: "hdf5Path",
      type: "hdf5Path",
    },
    defaultParam: {},
    nodeType: REACT_FLOW_NODE_TYPE_KEY.HDF5FileNode,
  },
  FLUO: {
    key: "fluo",
    displayName: "fluoData",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {
      setHeader: null,
      setIndex: false,
      transpose: false,
    },
    stateFileType: "csv", // Special: stored as CSV in state
    nodeType: REACT_FLOW_NODE_TYPE_KEY.FluoFileNode,
  },
  BEHAVIOR: {
    key: "behavior",
    displayName: "behaviorData",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {
      setHeader: null,
      setIndex: false,
      transpose: false,
    },
    stateFileType: "csv", // Special: stored as CSV in state
    nodeType: REACT_FLOW_NODE_TYPE_KEY.BehaviorFileNode,
  },
  MATLAB: {
    key: "matlab",
    displayName: "matlabData",
    hasFilePath: true,
    filePathType: "single",
    hasSpecialPath: {
      name: "matPath",
      type: "matPath",
    },
    defaultParam: {},
    nodeType: REACT_FLOW_NODE_TYPE_KEY.MatlabFileNode,
  },
  MICROSCOPE: {
    key: "microscope",
    displayName: "microscopeData",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {},
    dataType: "matlab", // Special: uses matlab data type
    nodeType: REACT_FLOW_NODE_TYPE_KEY.MicroscopeFileNode,
  },
} as const

// Enhanced configs with computed properties
const ENHANCED_FILE_TYPE_CONFIGS: Record<string, EnhancedFileTypeConfig> =
  Object.fromEntries(
    Object.entries(FILE_TYPE_CONFIGS).map(([configKey, config]) => {
      // Get nodeType from config or generate from key
      const nodeType =
        config.nodeType ||
        `${config.key.charAt(0).toUpperCase() + config.key.slice(1)}FileNode`

      return [
        configKey,
        {
          ...config,
          // Auto-generate missing properties
          treeType: config.treeType || config.key,
          dataType: config.dataType || config.key,
          nodeType,
          // Backward compatibility - both point to the same nodeType
          nodeComponent: nodeType,
          reactFlowNodeType: nodeType,
          componentPath:
            config.componentPath ||
            `components/Workspace/FlowChart/FlowChartNode/${nodeType}`,
        },
      ]
    }),
  ) as Record<string, EnhancedFileTypeConfig>

// Auto-generated type definitions
type FILE_TYPE_KEY = keyof typeof FILE_TYPE_CONFIGS
export type FILE_TYPE = (typeof FILE_TYPE_CONFIGS)[FILE_TYPE_KEY]["key"]

// 既存のコンスタントと互換性を保つ
export const FILE_TYPE_SET = Object.fromEntries(
  Object.entries(FILE_TYPE_CONFIGS).map(([key, config]) => [key, config.key]),
) as Record<FILE_TYPE_KEY, string>

export function getFileTypeConfig(
  fileType: FILE_TYPE,
): EnhancedFileTypeConfig | undefined {
  return Object.values(ENHANCED_FILE_TYPE_CONFIGS).find(
    (config) => config.key === fileType,
  )
}

export function getAllFileTypeConfigs(): EnhancedFileTypeConfig[] {
  return Object.values(ENHANCED_FILE_TYPE_CONFIGS)
}

// Auto-generated component mapping from ENHANCED_FILE_TYPE_CONFIGS
export const COMPONENT_MAPPING = Object.fromEntries(
  Object.values(ENHANCED_FILE_TYPE_CONFIGS).map((config) => [
    config.nodeType,
    config.nodeType,
  ]),
) as Record<string, string>

// Auto-generated data type mapping from ENHANCED_FILE_TYPE_CONFIGS
export const DATA_TYPE_MAPPING = Object.fromEntries(
  Object.values(ENHANCED_FILE_TYPE_CONFIGS).map((config) => [
    config.dataType,
    config.dataType,
  ]),
) as Record<string, string>
