import { CSSProperties } from "react"

import { REACT_FLOW_NODE_TYPE_KEY } from "config/fileTypes.config"

export const INITIAL_IMAGE_ELEMENT_ID = "input_0"
export const INITIAL_IMAGE_ELEMENT_NAME = "NoName"
export const NANO_ID_LENGTH = 10
export const ALGO_NODE_STYLE: CSSProperties = {
  border: "1px solid #777",
  height: 140,
  width: 250,
  padding: 0,
  borderRadius: 0,
} as const

export const DATA_NODE_STYLE: CSSProperties = {
  border: "1px solid #777",
  height: 140,
  width: 250,
} as const

export const HANDLE_STYLE: CSSProperties = {
  height: "13%",
  width: "3%",
  border: "1px solid",
  borderColor: "#555",
  borderRadius: 0,
  top: 15,
}

// Re-export for backward compatibility
export { REACT_FLOW_NODE_TYPE_KEY }

export type REACT_FLOW_NODE_TYPE =
  (typeof REACT_FLOW_NODE_TYPE_KEY)[keyof typeof REACT_FLOW_NODE_TYPE_KEY]
