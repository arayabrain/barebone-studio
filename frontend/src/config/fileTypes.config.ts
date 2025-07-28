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
  // Optional overrides - defaults to generated from key
  treeType?: string
  dataType?: string
  nodeComponent?: string
  reactFlowNodeType?: string
  componentPath?: string
}

// Enhanced config with computed properties
export interface EnhancedFileTypeConfig
  extends Required<Omit<FileTypeConfig, "hasSpecialPath" | "stateFileType">> {
  hasSpecialPath?: FileTypeConfig["hasSpecialPath"]
  stateFileType?: string
}

// Simplified config - values auto-generated when not specified
export const FILE_TYPE_CONFIGS: Record<string, FileTypeConfig> = {
  IMAGE: {
    key: "image",
    displayName: "imageData",
    hasFilePath: true,
    filePathType: "array",
    defaultParam: {},
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
  },
  MICROSCOPE: {
    key: "microscope",
    displayName: "microscopeData",
    hasFilePath: true,
    filePathType: "single",
    defaultParam: {},
    dataType: "matlab", // Special: uses matlab data type
  },
} as const

// Helper functions for generating component properties
function generateComponentName(key: string): string {
  return key.charAt(0).toUpperCase() + key.slice(1) + "FileNode"
}

function generateComponentPath(componentName: string): string {
  return `components/Workspace/FlowChart/FlowChartNode/${componentName}`
}

// Enhanced configs with auto-generated properties
export const ENHANCED_FILE_TYPE_CONFIGS: Record<
  string,
  EnhancedFileTypeConfig
> = Object.fromEntries(
  Object.entries(FILE_TYPE_CONFIGS).map(([configKey, config]) => [
    configKey,
    {
      ...config,
      treeType: config.treeType || config.key,
      dataType: config.dataType || config.key,
      nodeComponent: config.nodeComponent || generateComponentName(config.key),
      reactFlowNodeType:
        config.reactFlowNodeType || generateComponentName(config.key),
      componentPath:
        config.componentPath ||
        generateComponentPath(
          config.nodeComponent || generateComponentName(config.key),
        ),
    },
  ]),
) as Record<string, EnhancedFileTypeConfig>

// 自動生成される型定義
export type FILE_TYPE_KEY = keyof typeof FILE_TYPE_CONFIGS
export type FILE_TYPE = (typeof FILE_TYPE_CONFIGS)[FILE_TYPE_KEY]["key"]

// 既存のコンスタントと互換性を保つ
export const FILE_TYPE_SET = Object.fromEntries(
  Object.entries(FILE_TYPE_CONFIGS).map(([key, config]) => [key, config.key]),
) as Record<FILE_TYPE_KEY, string>

// Auto-generated from FILE_TYPE_CONFIGS
export const FILE_TYPES = Object.fromEntries(
  Object.entries(FILE_TYPE_CONFIGS).map(([key, config]) => [key, config.key]),
) as Record<string, string>

export type FILE_TYPE_LITERAL = (typeof FILE_TYPES)[keyof typeof FILE_TYPES]

// Manually defined to maintain type compatibility
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

// Manually defined to maintain type compatibility
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

// ヘルパー関数 - Enhanced configs使用
export function getFileTypeConfig(
  fileType: FILE_TYPE,
): EnhancedFileTypeConfig | undefined {
  return Object.values(ENHANCED_FILE_TYPE_CONFIGS).find(
    (config) => config.key === fileType,
  )
}

export function getFileTypeConfigByKey(
  key: FILE_TYPE_KEY,
): EnhancedFileTypeConfig {
  return ENHANCED_FILE_TYPE_CONFIGS[key]
}

export function getAllFileTypeConfigs(): EnhancedFileTypeConfig[] {
  return Object.values(ENHANCED_FILE_TYPE_CONFIGS)
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

// Auto-generated component mapping from ENHANCED_FILE_TYPE_CONFIGS
export const COMPONENT_MAPPING = Object.fromEntries(
  Object.values(ENHANCED_FILE_TYPE_CONFIGS).map((config) => [
    config.nodeComponent,
    config.nodeComponent,
  ]),
) as Record<string, string>

// Auto-generated data type mapping from ENHANCED_FILE_TYPE_CONFIGS
export const DATA_TYPE_MAPPING = Object.fromEntries(
  Object.values(ENHANCED_FILE_TYPE_CONFIGS).map((config) => [
    config.dataType,
    config.dataType,
  ]),
) as Record<string, string>
