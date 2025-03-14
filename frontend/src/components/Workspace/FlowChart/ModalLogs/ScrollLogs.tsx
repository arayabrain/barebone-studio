import {
  forwardRef,
  MouseEvent,
  MutableRefObject,
  useCallback,
  useEffect,
  useRef,
} from "react"

import styled from "@emotion/styled"
import { Box } from "@mui/material"

type Props = {
  logs: { text: string; id: string }[]
  keyword: string
  onLayout?: (layout: { height: number; scrollHeight: number }) => void
  onStartReached?: () => void
  searchId?: string
  isError?: boolean
  onScroll?: (event: MouseEvent<HTMLDivElement>) => void
}

const ScrollLogs = forwardRef(function ScrollLogsRef(
  {
    logs,
    keyword,
    onLayout,
    onStartReached,
    searchId,
    isError,
    onScroll: _onScroll,
  }: Props,
  ref,
) {
  const scrollRef = ref as MutableRefObject<HTMLDivElement>
  const refHeight = useRef(-1)
  const refScrollHeight = useRef(-1)
  const isUserScroll = useRef(true)

  const getLayout = useCallback(() => {
    if (!scrollRef.current) return
    const { clientHeight, scrollHeight, scrollTop } = scrollRef.current
    onLayout?.({ height: clientHeight, scrollHeight })
    if (
      refHeight.current !== clientHeight ||
      refScrollHeight.current !== scrollHeight
    ) {
      const change = scrollHeight - refScrollHeight.current
      isUserScroll.current = false
      if (!keyword.length) {
        if (scrollTop <= 3) {
          scrollRef.current.scrollTo({ top: change })
        } else if (
          refScrollHeight.current - refHeight.current <=
          scrollTop + 3
        ) {
          scrollRef.current.scrollTo({ top: scrollHeight - clientHeight + 50 })
        }
      }
      refHeight.current = clientHeight
      refScrollHeight.current = scrollHeight
      setTimeout(() => (isUserScroll.current = true), 10)
    }
  }, [keyword.length, onLayout, scrollRef])

  useEffect(() => {
    const ob = new MutationObserver(getLayout)
    ob.observe(scrollRef.current, { childList: true })
    return () => {
      ob.disconnect()
    }
  }, [getLayout, scrollRef])

  useEffect(() => {
    if (!scrollRef.current) return
    const element = scrollRef.current.querySelector(`#scroll_item_${searchId}`)
    if (!element) return
    element.scrollIntoView({ block: "nearest" })
  }, [scrollRef, searchId])

  const onScroll = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      _onScroll?.(event)
      if (!isUserScroll.current) return
      const top = (event.target as HTMLDivElement).scrollTop
      if (top <= 0) onStartReached?.()
    },
    [_onScroll, onStartReached],
  )

  const renderItem = useCallback(
    ({ item }: { item: { text: string; id: string } }) => {
      if (!keyword.trim()) return <BoxItem>{item.text}</BoxItem>
      const indexx = item.text
        .toLowerCase()
        .indexOf(keyword.trim().toLowerCase())
      const keys = [
        item.text.substring(0, indexx),
        `<span style="background: ${searchId === item.id ? "#ff9632" : "#ffff00"}; color: #555f64">${item.text.substring(indexx, indexx + keyword.trim().length)}</span>`,
        item.text.substring(indexx + keyword.trim().length, item.text.length),
      ]
      if (indexx > -1) {
        return (
          <BoxItem
            dangerouslySetInnerHTML={{
              __html: keys.join(""),
            }}
          />
        )
      }
      return <BoxItem>{item.text}</BoxItem>
    },
    [searchId, keyword],
  )

  return (
    <BoxScroll ref={ref} onScroll={onScroll}>
      {isError ? (
        <BoxError>Failed to retrieve log</BoxError>
      ) : (
        logs.map((e) => (
          <div id={`scroll_item_${e.id}`} key={`${e}_${e.id}`}>
            {renderItem({ item: e })}
          </div>
        ))
      )}
    </BoxScroll>
  )
})

const BoxScroll = styled(Box)`
  height: 100%;
  overflow: auto;
  font-family: Monospaced, sans-serif;

  &::-webkit-scrollbar {
    width: 4px;
    position: absolute;
    z-index: 9999;
  }

  &::-webkit-scrollbar-thumb {
    background-color: white;
    border-radius: 10px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background-color: #555;
  }
`

const BoxError = styled("p")`
  font-size: 20px;
  color: #ff0000;
  padding-left: 15px;
  font-weight: 600;
`

const BoxItem = styled("div")`
  -webkit-font-smoothing: auto;
  color: white;
  font-size: 12px;
  padding: 0px 16px;
`

export default ScrollLogs
