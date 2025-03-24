import { stringify } from "qs"
import { v4 as uuidv4 } from "uuid"

import axios from "utils/axios"

export enum TLevelsLog {
  ALL = "ALL",
  INFO = "INFO",
  ERROR = "ERROR",
  DEBUG = "DEBUG",
  WARNING = "WARNING",
  CRITICAL = "CRITICAL",
}

export type TParams<T = unknown> = {
  levels?: TLevelsLog[]
  search?: string
} & T

export type TParamQueryLogs = TParams & { reverse?: boolean; offset: number }

export const serviceLogs = async (params: TParamQueryLogs) => {
  const { data, config } = await axios.get("/logs", {
    params,
    paramsSerializer: (params) => stringify(params, { arrayFormat: "repeat" }),
  })
  return {
    data: data.data.map((e: string) => ({ text: e, id: uuidv4() })),
    params: config.params,
    offset: { next: data.next_offset, pre: data.prev_offset },
  }
}
