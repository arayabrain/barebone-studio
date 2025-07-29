import { FileNodeFactory } from "factories/FileNodeFactory"
import {
  CsvInputNode,
  ImageInputNode,
  HDF5InputNode,
  InputNodeType,
  FILE_TYPE_SET,
  FILE_TYPE,
  MatlabInputNode,
  MicroscopeInputNode,
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

// Helper functions using factory
export function hasSpecialPath(inputNode: InputNodeType): boolean {
  return FileNodeFactory.hasSpecialPath(inputNode.fileType)
}

export function getSpecialPathName(
  inputNode: InputNodeType,
): string | undefined {
  return FileNodeFactory.getSpecialPathName(inputNode.fileType)
}

// Config-driven dynamic type checking factory
export function createInputNodeTypePredicate(targetFileType: FILE_TYPE) {
  return (inputNode: InputNodeType): boolean => {
    return inputNode.fileType === targetFileType
  }
}

// Generate type predicates dynamically for new file types
export function generateTypePredicateFunction(fileType: FILE_TYPE): string {
  const config = FileNodeFactory.getFileTypeConfig(fileType)
  if (!config) return "isGenericInputNode"

  const capitalizedName =
    config.key.charAt(0).toUpperCase() + config.key.slice(1)
  return `is${capitalizedName}InputNode`
}
