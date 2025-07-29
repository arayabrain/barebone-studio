import {
  DATA_TYPE_MAPPING,
  EnhancedFileTypeConfig,
  FileTypeConfig,
  getFileTypeConfig,
} from "config/fileTypes.config"
import {
  DATA_TYPE,
  DATA_TYPE_SET,
} from "store/slice/DisplayData/DisplayDataType"
import { NODE_TYPE_SET } from "store/slice/FlowElement/FlowElementType"
import { FILE_TYPE, FILE_TYPE_SET } from "store/slice/InputNode/InputNodeType"
import { getNanoId } from "utils/nanoid/NanoIdUtils"

export interface CreateInputNodeResult {
  fileType: FILE_TYPE
  param: Record<string, unknown>
}

export interface CreateReactFlowNodeResult {
  id: string
  type: string
  data: {
    label: string
    type: string
  }
  position?: { x: number; y: number }
}

export class FileNodeFactory {
  static createInputNode(fileType: FILE_TYPE): CreateInputNodeResult {
    const config = getFileTypeConfig(fileType)
    if (!config) {
      throw new Error(`Unsupported file type: ${fileType}`)
    }

    // Map special cases
    let actualFileType: FILE_TYPE
    switch (fileType) {
      case FILE_TYPE_SET.FLUO:
      case FILE_TYPE_SET.BEHAVIOR:
        actualFileType = FILE_TYPE_SET.CSV
        break
      default:
        actualFileType = fileType
    }

    return {
      fileType: actualFileType,
      param: { ...config.defaultParam },
    }
  }

  static createReactFlowNode(
    nodeName: string,
    config: FileTypeConfig,
    position?: { x: number; y: number },
  ): CreateReactFlowNodeResult {
    // Convert to enhanced config if needed
    const enhancedConfig = getFileTypeConfig(config.key)
    if (!enhancedConfig) {
      throw new Error(
        `Cannot find enhanced config for file type: ${config.key}`,
      )
    }

    return {
      id: `input_${getNanoId()}`,
      type: enhancedConfig.reactFlowNodeType,
      data: {
        label: nodeName,
        type: NODE_TYPE_SET.INPUT,
      },
      position,
    }
  }

  static getReactFlowNodeType(fileType: FILE_TYPE): string {
    const config = getFileTypeConfig(fileType)
    if (!config) {
      throw new Error(`Unsupported file type: ${fileType}`)
    }
    return config.reactFlowNodeType
  }

  static getDefaultParam(fileType: FILE_TYPE): Record<string, unknown> {
    const config = getFileTypeConfig(fileType)
    if (!config) {
      throw new Error(`Unsupported file type: ${fileType}`)
    }
    return { ...config.defaultParam }
  }

  static hasSpecialPath(fileType: FILE_TYPE): boolean {
    const config = getFileTypeConfig(fileType)
    return Boolean(config?.hasSpecialPath)
  }

  static getSpecialPathName(fileType: FILE_TYPE): string | undefined {
    const config = getFileTypeConfig(fileType)
    return config?.hasSpecialPath?.name
  }

  static getFilePathType(fileType: FILE_TYPE): "single" | "array" {
    const config = getFileTypeConfig(fileType)
    return config?.filePathType || "single"
  }

  static getSpecialPathConfig(
    fileType: FILE_TYPE,
  ): EnhancedFileTypeConfig["hasSpecialPath"] {
    const config = getFileTypeConfig(fileType)
    return config?.hasSpecialPath
  }

  static getDataType(fileType: FILE_TYPE): string {
    const config = getFileTypeConfig(fileType)
    return config?.dataType || "csv"
  }

  static getTreeType(fileType: FILE_TYPE): string {
    const config = getFileTypeConfig(fileType)
    return config?.treeType || "csv"
  }

  static getFileTypeConfig(
    fileType: FILE_TYPE,
  ): EnhancedFileTypeConfig | undefined {
    return getFileTypeConfig(fileType)
  }

  // Generate selector function names dynamically
  static generateSelectorName(fileType: FILE_TYPE, suffix: string): string {
    const config = getFileTypeConfig(fileType)
    if (!config) return `selectGeneric${suffix}`

    // Capitalize first letter for function name
    const capitalizedName =
      config.key.charAt(0).toUpperCase() + config.key.slice(1)
    return `select${capitalizedName}InputNode${suffix}`
  }

  /**
   * Converts FILE_TYPE to DATA_TYPE
   * Used for converting InputNode file types to DisplayData types
   * Uses config-driven approach via DATA_TYPE_MAPPING
   */
  static toDataTypeFromFileType(fileType: FILE_TYPE): DATA_TYPE {
    const dataTypeString = FileNodeFactory.getDataType(fileType)

    // Use mapping from config instead of hardcoded strings
    const mappedType =
      DATA_TYPE_MAPPING[dataTypeString as keyof typeof DATA_TYPE_MAPPING]
    if (mappedType) {
      return DATA_TYPE_SET[
        mappedType.toUpperCase() as keyof typeof DATA_TYPE_SET
      ]
    }

    // Fallback to CSV for unknown types
    return DATA_TYPE_SET.CSV
  }
}
