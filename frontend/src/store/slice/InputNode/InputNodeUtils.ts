import {
  CsvInputNode,
  ImageInputNode,
  HDF5InputNode,
  InputNodeType,
  FILE_TYPE_SET,
  MatlabInputNode,
  MicroscopeInputNode,
  BatchImageInputNode,
  BatchCsvInputNode,
  BatchFluoInputNode,
  BatchBehaviorInputNode,
  BatchMicroscopeInputNode,
  BatchHDF5InputNode,
  BatchMatlabInputNode,
} from "store/slice/InputNode/InputNodeType"

export function isImageInputNode(
  inputNode: InputNodeType,
): inputNode is ImageInputNode {
  return inputNode.fileType === FILE_TYPE_SET.IMAGE
}

export function isCsvInputNode(
  inputNode: InputNodeType,
): inputNode is CsvInputNode {
  return inputNode.fileType === FILE_TYPE_SET.CSV
}

export function isMatlabInputNode(
  inputNode: InputNodeType,
): inputNode is MatlabInputNode {
  return inputNode.fileType === FILE_TYPE_SET.MATLAB
}

export function isHDF5InputNode(
  inputNode: InputNodeType,
): inputNode is HDF5InputNode {
  return inputNode.fileType === FILE_TYPE_SET.HDF5
}

export function isMicroscopeInputNode(
  inputNode: InputNodeType,
): inputNode is MicroscopeInputNode {
  return inputNode.fileType === FILE_TYPE_SET.MICROSCOPE
}

export function isBatchAnyInputNode(
  inputNode: InputNodeType,
): inputNode is
  | BatchImageInputNode
  | BatchCsvInputNode
  | BatchFluoInputNode
  | BatchBehaviorInputNode
  | BatchMicroscopeInputNode
  | BatchHDF5InputNode
  | BatchMatlabInputNode {
  return (
    isBatchImageInputNode(inputNode) ||
    isBatchCsvInputNode(inputNode) ||
    isBatchFluoInputNode(inputNode) ||
    isBatchBehaviorInputNode(inputNode) ||
    isBatchMicroscopeInputNode(inputNode) ||
    isBatchHDF5InputNode(inputNode) ||
    isBatchMatlabInputNode(inputNode)
  )
}

export function isBatchImageInputNode(
  inputNode: InputNodeType,
): inputNode is BatchImageInputNode {
  return inputNode.fileType === FILE_TYPE_SET.BATCH_IMAGE
}

export function isBatchCsvInputNode(
  inputNode: InputNodeType,
): inputNode is BatchCsvInputNode {
  return inputNode.fileType === FILE_TYPE_SET.BATCH_CSV
}

export function isBatchFluoInputNode(
  inputNode: InputNodeType,
): inputNode is BatchFluoInputNode {
  return inputNode.fileType === FILE_TYPE_SET.BATCH_FLUO
}

export function isBatchBehaviorInputNode(
  inputNode: InputNodeType,
): inputNode is BatchBehaviorInputNode {
  return inputNode.fileType === FILE_TYPE_SET.BATCH_BEHAVIOR
}

export function isBatchMicroscopeInputNode(
  inputNode: InputNodeType,
): inputNode is BatchMicroscopeInputNode {
  return inputNode.fileType === FILE_TYPE_SET.BATCH_MICROSCOPE
}

export function isBatchHDF5InputNode(
  inputNode: InputNodeType,
): inputNode is BatchHDF5InputNode {
  return inputNode.fileType === FILE_TYPE_SET.BATCH_HDF5
}

export function isBatchMatlabInputNode(
  inputNode: InputNodeType,
): inputNode is BatchMatlabInputNode {
  return inputNode.fileType === FILE_TYPE_SET.BATCH_MATLAB
}

// Helper function to check if a file type is CSV-based
export function isCsvBasedFileType(fileType: string): boolean {
  return [
    FILE_TYPE_SET.CSV,
    FILE_TYPE_SET.BATCH_CSV,
    FILE_TYPE_SET.FLUO,
    FILE_TYPE_SET.BATCH_FLUO,
    FILE_TYPE_SET.BEHAVIOR,
    FILE_TYPE_SET.BATCH_BEHAVIOR,
  ].includes(fileType)
}

// Helper function to check if an InputNode is CSV-based
export function isCsvBasedInputNode(
  inputNode: InputNodeType,
): inputNode is
  | CsvInputNode
  | BatchCsvInputNode
  | BatchFluoInputNode
  | BatchBehaviorInputNode {
  return isCsvBasedFileType(inputNode.fileType)
}
