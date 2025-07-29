import { FILE_TYPE_SET, FILE_TYPE } from "config/fileTypes.config"

export const INPUT_NODE_SLICE_NAME = "inputNode"

// Re-export for backward compatibility
export { FILE_TYPE_SET }
export type { FILE_TYPE }

export type InputNode = {
  [nodeId: string]: InputNodeType
}

export type InputNodeType =
  | CsvInputNode
  | ImageInputNode
  | HDF5InputNode
  | MatlabInputNode
  | MicroscopeInputNode
  | BatchImageInputNode

interface InputNodeBaseType<
  T extends FILE_TYPE,
  P extends { [key: string]: unknown },
> {
  fileType: T
  selectedFilePath?: string | string[]
  param: P
}

export type CsvInputParamType = {
  setHeader: number | null
  setIndex: boolean
  transpose: boolean
}

export interface CsvInputNode
  extends InputNodeBaseType<"csv", CsvInputParamType> {
  selectedFilePath?: string
}

export interface MatlabInputNode
  extends InputNodeBaseType<"matlab", Record<never, never>> {
  selectedFilePath?: string
  matPath?: string
}

export interface ImageInputNode
  extends InputNodeBaseType<"image", Record<never, never>> {
  selectedFilePath?: string[]
}

export interface HDF5InputNode
  extends InputNodeBaseType<"hdf5", Record<never, never>> {
  selectedFilePath?: string
  hdf5Path?: string
}

export interface MicroscopeInputNode
  extends InputNodeBaseType<"microscope", Record<never, never>> {
  selectedFilePath?: string
}

export interface BatchImageInputNode
  extends InputNodeBaseType<"batch_image", Record<never, never>> {
  selectedFilePath?: string[]
}
