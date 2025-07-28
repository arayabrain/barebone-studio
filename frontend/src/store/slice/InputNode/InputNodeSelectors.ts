// FILE_TYPE, InputNodeType available for extensions if needed
import {
  isHDF5InputNode,
  isCsvInputNode,
  isImageInputNode,
  isMatlabInputNode,
  isMicroscopeInputNode,
} from "store/slice/InputNode/InputNodeUtils"
import { RootState } from "store/store"
// getAllFileTypeConfigs available for dynamic selector generation if needed

// Generic selector factory available for future extensions if needed
// function createTypedFilePathSelector(fileType: FILE_TYPE, typePredicate: (node: InputNodeType) => boolean) {...}

export const selectInputNode = (state: RootState) => state.inputNode

export const selectInputNodeById = (nodeId: string) => (state: RootState) =>
  state.inputNode[nodeId]

export const selectInputNodeDefined = (nodeId: string) => (state: RootState) =>
  Object.keys(state.inputNode).includes(nodeId)

export const selectInputNodeFileType = (nodeId: string) => (state: RootState) =>
  selectInputNodeById(nodeId)(state).fileType

export const selectInputNodeSelectedFilePath =
  (nodeId: string) => (state: RootState) => {
    return selectInputNodeById(nodeId)(state).selectedFilePath
  }

// Create typed selectors with specific return types
export const selectCsvInputNodeSelectedFilePath =
  (nodeId: string) => (state: RootState) => {
    const node = selectInputNodeById(nodeId)(state)
    if (isCsvInputNode(node)) {
      return node.selectedFilePath as string | undefined
    } else {
      throw new Error("invalid input node type")
    }
  }

export const selectImageInputNodeSelectedFilePath =
  (nodeId: string) => (state: RootState) => {
    const node = selectInputNodeById(nodeId)(state)
    if (isImageInputNode(node)) {
      return node.selectedFilePath as string[] | undefined
    } else {
      throw new Error("invalid input node type")
    }
  }

export const selectHDF5InputNodeSelectedFilePath =
  (nodeId: string) => (state: RootState) => {
    const node = selectInputNodeById(nodeId)(state)
    if (isHDF5InputNode(node)) {
      return node.selectedFilePath as string | undefined
    } else {
      throw new Error("invalid input node type")
    }
  }

export const selectMatlabInputNodeSelectedFilePath =
  (nodeId: string) => (state: RootState) => {
    const node = selectInputNodeById(nodeId)(state)
    if (isMatlabInputNode(node)) {
      return node.selectedFilePath as string | undefined
    } else {
      throw new Error("invalid input node type")
    }
  }

export const selectMicroscopeInputNodeSelectedFilePath =
  (nodeId: string) => (state: RootState) => {
    const node = selectInputNodeById(nodeId)(state)
    if (isMicroscopeInputNode(node)) {
      return node.selectedFilePath as string | undefined
    } else {
      throw new Error("invalid input node type")
    }
  }

// Dynamic selectors generation capability is available for future extensions via getAllFileTypeConfigs()

export const selectFilePathIsUndefined = (state: RootState) =>
  Object.keys(state.inputNode).length === 0 ||
  Object.values(state.inputNode).filter((inputNode) => {
    if (isHDF5InputNode(inputNode)) {
      return inputNode.selectedFilePath == null || inputNode.hdf5Path == null
    } else {
      const filePath = inputNode.selectedFilePath
      if (Array.isArray(filePath)) {
        return filePath.length === 0
      } else {
        return filePath == null
      }
    }
  }).length > 0

export const selectInputNodeParam = (nodeId: string) => (state: RootState) =>
  selectInputNodeById(nodeId)(state).param

const selectCsvInputNodeParam = (nodeId: string) => (state: RootState) => {
  const inputNode = selectInputNodeById(nodeId)(state)
  if (isCsvInputNode(inputNode)) {
    return inputNode.param
  } else {
    throw new Error(`The InputNode is not CsvInputNode. (nodeId: ${nodeId})`)
  }
}

export const selectCsvInputNodeParamSetHeader =
  (nodeId: string) => (state: RootState) =>
    selectCsvInputNodeParam(nodeId)(state).setHeader

export const selectCsvInputNodeParamSetIndex =
  (nodeId: string) => (state: RootState) =>
    selectCsvInputNodeParam(nodeId)(state).setIndex

export const selectCsvInputNodeParamTranspose =
  (nodeId: string) => (state: RootState) =>
    selectCsvInputNodeParam(nodeId)(state).transpose

export const selectInputNodeHDF5Path =
  (nodeId: string) => (state: RootState) => {
    const item = selectInputNodeById(nodeId)(state)
    if (isHDF5InputNode(item)) {
      return item.hdf5Path
    } else {
      return undefined
    }
  }

export const selectInputNodeMatlabPath =
  (nodeId: string) => (state: RootState) => {
    const item = selectInputNodeById(nodeId)(state)
    if (isMatlabInputNode(item)) {
      return item.matPath
    } else {
      return undefined
    }
  }
