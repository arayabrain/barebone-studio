import { useCallback, useEffect, useRef, useState } from "react"

import {
  serviceLogs,
  TLevelsLog,
  TParams,
} from "components/Workspace/FlowChart/ModalLogs/helpers/service"

export type TLogs = { text: string; id: string }

const TIME_INTERVAL_API = 2000

export const useLogs = (
  levels: TLevelsLog[],
  keyword: string,
  isRealtime: boolean,
) => {
  const [logs, setLogs] = useState<TLogs[]>([])
  const [isError, setIsError] = useState(false)
  const timeout = useRef<NodeJS.Timeout>()
  const paginate = useRef({ next: -1, pre: -1 })
  const levelsRef = useRef(levels)
  const keywordRef = useRef(keyword)
  const isErrorRef = useRef(isError)
  const isBlurScreen = useRef(false)

  useEffect(() => {
    isErrorRef.current = isError
  }, [isError])

  useEffect(() => {
    levelsRef.current = levels
  }, [levels])

  useEffect(() => {
    keywordRef.current = keyword
  }, [keyword])

  useEffect(() => {
    levelsRef.current = levels
  }, [levels])

  const getPrevLogsApi = useCallback(
    async (_params: TParams<{ offset: number }>) => {
      _params.levels = levelsRef.current
      const { data, offset } = await serviceLogs({ ..._params, reverse: true })
      paginate.current.pre = offset.pre
      return data
    },
    [],
  )

  const getNextDataApi = useCallback(
    async (_params: TParams<{ offset: number }>) => {
      _params.levels = levelsRef.current
      const { pre } = paginate.current
      const { data, offset } = await serviceLogs({ ..._params, reverse: false })
      paginate.current.next = offset.next
      if (!data.length && pre === -1) {
        const dataPre = await getPrevLogsApi({ ..._params, offset: offset.pre })
        return dataPre
      }
      return data
    },
    [getPrevLogsApi],
  )

  const onPrevSearchApi = useCallback(
    async (k?: string) => {
      const { pre } = paginate.current
      if (pre <= 0) return
      const search = keywordRef.current
      const data = await getPrevLogsApi({ offset: pre, search: k ?? search })
      setLogs((pre) => [...data, ...pre])
    },
    [getPrevLogsApi],
  )

  const onNextSearchApi = useCallback(
    async (k?: string) => {
      const search = keywordRef.current
      const { next } = paginate.current
      const data = await getNextDataApi({ offset: next, search: k ?? search })
      if (isErrorRef.current) setIsError(false)
      setLogs((pre) => [...pre, ...data])
    },
    [getNextDataApi],
  )

  const realtimeApi = useCallback(async () => {
    clearTimeout(timeout.current)
    if (isRealtime && !keywordRef.current) {
      await onNextSearchApi("").catch(() => setIsError(true))
    }
    if (!isBlurScreen.current) {
      timeout.current = setTimeout(realtimeApi, TIME_INTERVAL_API)
    }
  }, [isRealtime, onNextSearchApi])

  useEffect(() => {
    realtimeApi()
    return () => {
      clearTimeout(timeout.current)
    }
  }, [realtimeApi])

  useEffect(() => {
    return () => {
      isBlurScreen.current = true
    }
  }, [])

  const reset = useCallback(() => {
    setLogs([])
    paginate.current = { next: -1, pre: -1 }
    if (keywordRef.current.length) onNextSearchApi("")
    else realtimeApi()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onNextSearchApi])

  return { onPrevSearchApi, onNextSearchApi, logs, isError, reset }
}
