import {
  CsvInputNode,
  ImageInputNode,
  HDF5InputNode,
  ExpDbInputNode,
  InputNodeType,
  FILE_TYPE_SET,
  MatlabInputNode,
  MicroscopeInputNode,
  MicroscopeExpdbInputNode,
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

export function isMicroscopeExpDbInputNode(
  inputNode: InputNodeType,
): inputNode is MicroscopeExpdbInputNode {
  return inputNode.fileType === FILE_TYPE_SET.MICROSCOPE_EXPDB
}

export function isExpDbInputNode(
  inputNode: InputNodeType,
): inputNode is ExpDbInputNode {
  return inputNode.fileType === FILE_TYPE_SET.EXPDB
}
