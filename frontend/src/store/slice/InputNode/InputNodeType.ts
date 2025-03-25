export const INPUT_NODE_SLICE_NAME = "inputNode"

export const FILE_TYPE_SET = {
  CSV: "csv",
  IMAGE: "image",
  HDF5: "hdf5",
  FLUO: "fluo",
  BEHAVIOR: "behavior",
  MATLAB: "matlab",
  MICROSCOPE: "microscope",
  MICROSCOPE_EXPDB: "microscope_expdb",
  EXPDB: "expdb",
} as const

export const FILE_TYPE_NODE_NAME_ALIAS = {
  MICROSCOPE_EXPDB: "microscope_database",
  EXPDB: "preprocessed_data",
} as const

export type FILE_TYPE = (typeof FILE_TYPE_SET)[keyof typeof FILE_TYPE_SET]

export type InputNode = {
  [nodeId: string]: InputNodeType
}

export type InputNodeType =
  | CsvInputNode
  | ImageInputNode
  | HDF5InputNode
  | MatlabInputNode
  | MicroscopeInputNode
  | MicroscopeExpdbInputNode
  | ExpDbInputNode

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

export interface MicroscopeExpdbInputNode
  extends InputNodeBaseType<"microscope_expdb", Record<never, never>> {
  selectedFilePath?: string
}

export interface ExpDbInputNode
  extends InputNodeBaseType<"expdb", Record<never, never>> {
  selectedFilePath?: string
}
