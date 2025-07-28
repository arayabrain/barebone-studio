import { DATA_TYPE_MAPPING } from "config/fileTypes.config"
import { FileNodeFactory } from "factories/FileNodeFactory"
import {
  DATA_TYPE,
  DATA_TYPE_SET,
} from "store/slice/DisplayData/DisplayDataType"
import { FILE_TYPE } from "store/slice/InputNode/InputNodeType"

/**
 * Converts FILE_TYPE to DATA_TYPE
 * Used for converting InputNode file types to DisplayData types
 * Now uses config-driven approach via FileNodeFactory and DATA_TYPE_MAPPING
 */
export function toDataTypeFromFileType(fileType: FILE_TYPE): DATA_TYPE {
  const dataTypeString = FileNodeFactory.getDataType(fileType)

  // Use mapping from config instead of hardcoded strings
  const mappedType =
    DATA_TYPE_MAPPING[dataTypeString as keyof typeof DATA_TYPE_MAPPING]
  if (mappedType) {
    return DATA_TYPE_SET[mappedType.toUpperCase() as keyof typeof DATA_TYPE_SET]
  }

  // Fallback to CSV for unknown types
  return DATA_TYPE_SET.CSV
}
