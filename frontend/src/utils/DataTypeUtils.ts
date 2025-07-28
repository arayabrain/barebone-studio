import {
  DATA_TYPE,
  DATA_TYPE_SET,
} from "store/slice/DisplayData/DisplayDataType"
import { FILE_TYPE, FILE_TYPE_SET } from "store/slice/InputNode/InputNodeType"

/**
 * Converts FILE_TYPE to DATA_TYPE
 * Used for converting InputNode file types to DisplayData types
 */
export function toDataTypeFromFileType(fileType: FILE_TYPE): DATA_TYPE {
  switch (fileType) {
    case FILE_TYPE_SET.IMAGE:
      return DATA_TYPE_SET.IMAGE
    case FILE_TYPE_SET.CSV:
      return DATA_TYPE_SET.CSV
    case FILE_TYPE_SET.HDF5:
      return DATA_TYPE_SET.HDF5
    case FILE_TYPE_SET.FLUO:
      return DATA_TYPE_SET.FLUO
    case FILE_TYPE_SET.BEHAVIOR:
      return DATA_TYPE_SET.BEHAVIOR
    case FILE_TYPE_SET.MATLAB:
    case FILE_TYPE_SET.MICROSCOPE:
      return DATA_TYPE_SET.MATLAB
    default:
      return DATA_TYPE_SET.CSV
  }
}
