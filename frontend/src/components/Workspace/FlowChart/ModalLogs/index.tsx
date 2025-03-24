import {
  KeyboardEvent as KeyboardEventReact,
  MouseEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"

import { keyframes } from "@emotion/react"
import styled from "@emotion/styled"
import AdbIcon from "@mui/icons-material/Adb"
import ArrowBackIosIcon from "@mui/icons-material/ArrowBackIos"
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos"
import CloseIcon from "@mui/icons-material/Close"
import ErrorIcon from "@mui/icons-material/Error"
import GradeIcon from "@mui/icons-material/Grade"
import InfoIcon from "@mui/icons-material/Info"
import KeyboardDoubleArrowDownIcon from "@mui/icons-material/KeyboardDoubleArrowDown"
import MenuIcon from "@mui/icons-material/Menu"
import SearchIcon from "@mui/icons-material/Search"
import WarningIcon from "@mui/icons-material/Warning"
import { Box, Modal, Tooltip } from "@mui/material"

import { TLevelsLog } from "components/Workspace/FlowChart/ModalLogs/helpers/service"
import {
  TLogs,
  useLogs,
} from "components/Workspace/FlowChart/ModalLogs/helpers/useLogs"
import ScrollLogs from "components/Workspace/FlowChart/ModalLogs/ScrollLogs"

type Props = {
  isOpen?: boolean
  onClose?: () => void
}

const SPACE_CHECK_SCROLL = 50

const ModalLogs = ({ isOpen = false, onClose }: Props) => {
  const [levels, setLevels] = useState<TLevelsLog[]>([])
  const [keyword, setKeywork] = useState("")
  const [openSearch, setOpenSearch] = useState(false)
  const [searchId, setSearchId] = useState("")
  const [openSearchLevels, setOpenSearchLevels] = useState(false)
  const [visibleScrollEnd, setVisibleScrollEnd] = useState(false)

  const { logs, onPrevSearchApi, onNextSearchApi, isError, reset } = useLogs(
    levels,
    keyword,
    !visibleScrollEnd,
  )
  const logsRef = useRef(logs)
  const scrollLogs = useRef<HTMLDivElement>(null)
  const modalContent = useRef<HTMLDivElement>(null)
  const allowSearchChangeLogs = useRef({ next: false, pre: false })

  const getTopElement = useCallback((elementId: string) => {
    const id = `#scroll_item_${elementId}`
    const element = scrollLogs.current?.querySelector(id)
    if (!element) return -1
    const topParent = modalContent.current?.getBoundingClientRect()?.top
    const { top } = element.getBoundingClientRect()
    return top - (topParent || 0)
  }, [])

  const makeLogsWithKey = useCallback((key: string) => {
    return logsRef.current.filter((e) =>
      e.text.toLowerCase().includes(key.toLowerCase()),
    )
  }, [])

  const makeLogsWithTop = useCallback(
    (_logs: TLogs[]) => {
      return _logs.map((e) => ({ ...e, top: getTopElement(e.id) }))
    },
    [getTopElement],
  )

  const getLogWithKeyword = useCallback(
    (key: string) => {
      if (!key) return
      const list = makeLogsWithTop(makeLogsWithKey(key))
      let item = list.filter((e) => e.top > 0)[0]
      if (!item) item = list.toSorted((a, b) => (a.top > b.top ? -1 : 1))[0]
      return item
    },
    [makeLogsWithKey, makeLogsWithTop],
  )

  const getSearchId = useCallback(
    (search: string) => {
      const item = getLogWithKeyword(search.toLowerCase())
      setSearchId(item?.id ?? "")
    },
    [getLogWithKeyword],
  )

  const onNextSearch = useCallback(
    (withApi = true) => {
      const list = makeLogsWithTop(makeLogsWithKey(keyword.trim()))
      const index = list.findIndex((e) => e.id === searchId)
      const item = list.find((_, i) => i > index)
      allowSearchChangeLogs.current.next = !item
      if (item) setSearchId(item.id)
      else if (withApi) onNextSearchApi()
    },
    [keyword, makeLogsWithKey, makeLogsWithTop, onNextSearchApi, searchId],
  )

  const onPrevSearch = useCallback(
    (withApi = true) => {
      const list = makeLogsWithTop(makeLogsWithKey(keyword.trim()))
      const index = list.toReversed().findIndex((e) => e.id === searchId)
      const item = list.toReversed().find((_, i) => i > index)
      allowSearchChangeLogs.current.pre = !item
      if (item) setSearchId(item.id)
      else if (withApi) onPrevSearchApi()
    },
    [keyword, makeLogsWithKey, makeLogsWithTop, onPrevSearchApi, searchId],
  )

  useEffect(() => {
    getSearchId(keyword.trim())
  }, [getSearchId, keyword])

  const onChangeTypeFilter = useCallback(
    (t: TLevelsLog) => {
      let _levels = []
      if (levels?.includes(t)) _levels = levels.filter((e) => e !== t)
      else _levels = [...(levels || []), t]
      setLevels(_levels)
    },
    [levels],
  )

  const onKeyDown = useCallback(
    (event: KeyboardEventReact<HTMLInputElement>) => {
      if (event.code === "Escape") {
        event.preventDefault()
        event.stopPropagation()
        setOpenSearch(false)
      } else if (event.code === "Enter") onNextSearch()
    },
    [onNextSearch],
  )

  const onWindowKeydown = useCallback((event: KeyboardEvent) => {
    if (event.code === "Escape") {
      event.preventDefault()
      event.stopPropagation()
      setOpenSearch(false)
      setOpenSearchLevels(false)
    }
  }, [])

  useEffect(() => {
    if (!openSearch && !openSearchLevels) return
    document.addEventListener("keydown", onWindowKeydown)
    return () => {
      document.removeEventListener("keydown", onWindowKeydown)
    }
  }, [openSearchLevels, openSearch, onWindowKeydown])

  const onStartReached = useCallback(() => {
    if (!logsRef.current.length) return
    onPrevSearchApi("")
  }, [onPrevSearchApi])

  const onScroll = useCallback((event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLDivElement
    const { clientHeight: _ch, scrollHeight: _sch, scrollTop } = target
    setVisibleScrollEnd(_sch - scrollTop > _ch + SPACE_CHECK_SCROLL)
  }, [])

  const onScrollEnd = useCallback(() => {
    if (!scrollLogs.current) return
    const { clientHeight: _ch, scrollHeight: _sch } = scrollLogs.current
    scrollLogs.current.scrollTo({ top: _sch - _ch, behavior: "smooth" })
  }, [])

  useEffect(() => {
    logsRef.current = logs
    if (!logs.length) return
    if (allowSearchChangeLogs.current.next) onNextSearch(false)
    else if (allowSearchChangeLogs.current.pre) onPrevSearch(false)
    allowSearchChangeLogs.current.next = false
    allowSearchChangeLogs.current.next = false
  }, [logs, onNextSearch, onPrevSearch])

  useEffect(() => {
    reset()
    setSearchId("")
    setVisibleScrollEnd(false)
    allowSearchChangeLogs.current = { next: false, pre: false }
    if (keyword.length) allowSearchChangeLogs.current.next = true
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reset, levels])

  useEffect(() => {
    if (!openSearch) setKeywork("")
  }, [openSearch])

  useEffect(() => {
    if (!openSearchLevels && levels.length) setLevels([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openSearchLevels])

  const onLayout = useCallback(
    (layout: { height: number; scrollHeight: number }) => {
      if (layout.scrollHeight <= layout.height) onPrevSearch()
    },
    [onPrevSearch],
  )

  return (
    <Modal
      disableEscapeKeyDown={openSearch || openSearchLevels}
      style={{ display: "flex" }}
      open={isOpen}
      onClose={onClose}
    >
      <Content ref={modalContent}>
        <ScrollLogs
          ref={scrollLogs}
          searchId={searchId}
          logs={logs}
          keyword={keyword}
          onStartReached={onStartReached}
          isError={isError}
          onScroll={onScroll}
          onLayout={onLayout}
        />
        <ButtonCloseModal onClick={onClose}>
          <CloseIcon />
        </ButtonCloseModal>
        {openSearch ? (
          <BoxSearch isOpen>
            <Box display="flex">
              <BoxIconSearch marginLeft="8px" onClick={() => onPrevSearch()}>
                <ArrowBackIosIcon />
              </BoxIconSearch>
              <BoxIconSearch onClick={() => onNextSearch()}>
                <ArrowForwardIosIcon />
              </BoxIconSearch>
            </Box>
            <InputSearch
              autoFocus
              value={keyword}
              placeholder="Search logs"
              onChange={(e) => setKeywork(e.target.value)}
              onKeyDown={onKeyDown}
            />
            <ButtonClose onClick={() => setOpenSearch(false)}>
              <CloseIcon />
            </ButtonClose>
          </BoxSearch>
        ) : (
          <BoxSearch width={"auto !important"}>
            <ButtonClose onClick={() => setOpenSearch(true)}>
              <Tooltip title="Search logs">
                <SearchIcon />
              </Tooltip>
            </ButtonClose>
          </BoxSearch>
        )}

        {openSearchLevels ? (
          <BoxFilter>
            <Box position="relative">
              <MenuFilter
                active={!levels?.length}
                onClick={() => setLevels([])}
              >
                <InfoIcon />
                <span>{TLevelsLog.ALL}</span>
              </MenuFilter>
              <BoxCloseLevel onClick={() => setOpenSearchLevels(false)}>
                <CloseIcon />
              </BoxCloseLevel>
            </Box>
            <MenuFilter
              active={levels?.includes(TLevelsLog.INFO)}
              onClick={() => onChangeTypeFilter(TLevelsLog.INFO)}
            >
              <InfoIcon />
              <span>{TLevelsLog.INFO}</span>
            </MenuFilter>
            <MenuFilter
              active={levels?.includes(TLevelsLog.WARNING)}
              onClick={() => onChangeTypeFilter(TLevelsLog.WARNING)}
            >
              <WarningIcon />
              <span>{TLevelsLog.WARNING}</span>
            </MenuFilter>
            <MenuFilter
              active={levels?.includes(TLevelsLog.DEBUG)}
              onClick={() => onChangeTypeFilter(TLevelsLog.DEBUG)}
            >
              <AdbIcon />
              <span>{TLevelsLog.DEBUG}</span>
            </MenuFilter>
            <MenuFilter
              active={levels?.includes(TLevelsLog.ERROR)}
              onClick={() => onChangeTypeFilter(TLevelsLog.ERROR)}
            >
              <ErrorIcon />
              <span>{TLevelsLog.ERROR}</span>
            </MenuFilter>
            <MenuFilter
              active={levels?.includes(TLevelsLog.CRITICAL)}
              onClick={() => onChangeTypeFilter(TLevelsLog.CRITICAL)}
            >
              <GradeIcon />
              <span>{TLevelsLog.CRITICAL}</span>
            </MenuFilter>
          </BoxFilter>
        ) : (
          <BoxMenu onClick={() => setOpenSearchLevels(true)}>
            <Tooltip title="Filter log levels">
              <MenuIcon />
            </Tooltip>
          </BoxMenu>
        )}
        {visibleScrollEnd ? (
          <BoxScrollDown onClick={onScrollEnd}>
            <KeyboardDoubleArrowDownIcon />
          </BoxScrollDown>
        ) : null}
      </Content>
    </Modal>
  )
}

const BoxCloseLevel = styled(Box)`
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  right: 8px;
  cursor: pointer;

  svg {
    font-size: 20px;
  }
`

const MenuFilter = styled(Box, {
  shouldForwardProp: (props) => props !== "active",
})<{ active?: boolean }>`
  display: flex;
  padding: 5px 16px;
  align-items: center;
  color: white;
  cursor: pointer;
  gap: 4px;
  padding-left: 5px;
  color: ${({ active }) => (active ? "rgb(0, 0, 0)" : "rgba(0, 0, 0, 0.3)")};
  svg {
    width: 30px;
  }
  border-bottom: 2px solid;
  border-color: ${({ active }) => (active ? "rgb(0, 0, 0)" : "transparent")};
  &:hover {
    color: rgba(0, 0, 0, 0.8);
  }
`

const BoxFilter = styled(Box)`
  position: absolute;
  right: 5px;
  top: 85px;
  background: white;
  min-width: 150px;
`

const BoxSearch = styled(Box, {
  shouldForwardProp: (props) => props !== "isOpen",
})<{ isOpen?: boolean }>`
  position: absolute;
  right: 5px;
  top: 39px;
  height: 37px;
  width: 320px;
  display: flex;
  align-items: center;
  border: ${({ isOpen }) =>
    !isOpen ? "none" : "1px solid rgba(255, 255, 255, 0.5)"};
  border-radius: ${({ isOpen }) => (isOpen ? "4px" : "40px")};
  background-color: ${({ isOpen }) => (isOpen ? "black" : "transparent")};
  svg {
    font-size: ${({ isOpen }) => (isOpen ? "14px" : "18px")};
  }
`

const InputSearch = styled("input")`
  height: 23px;
  background-color: transparent;
  outline: none;
  border: none;
  color: white;
  padding: 8px 10px;
  flex: 1;
`

const BoxIconSearch = styled(Box)`
  color: white;
  height: 40px;
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  svg {
    font-size: 14px;
  }
`

const Content = styled(Box)`
  width: 1600px;
  max-width: 85%;
  height: 700px;
  max-height: 80%;
  background-color: black;
  position: relative;
  white-space: pre-wrap;
  margin: auto;
  padding: 12px 0 12px 0;
  outline: none;
`

const ButtonClose = styled(Box)`
  width: 37px;
  height: 39px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: white;
  svg {
    font-size: 16px;
  }
`

const ButtonCloseModal = styled(ButtonClose)`
  position: absolute;
  top: 0;
  right: 5px;
  height: 39px;
  svg {
    font-size: 20px;
  }
`

const BoxMenu = styled(ButtonClose)`
  position: absolute;
  top: 85px;
  right: 5px;
  height: 39px;
  svg {
    font-size: 20px;
  }
`

const rotate = keyframes`
    0% {
      transform: translateY(-5px);
    }
    50% {
      transform: translateY(0);
    }
    100% {
      transform: translateY(-5px);
    }
  `

const BoxScrollDown = styled(Box)`
  position: absolute;
  bottom: 10px;
  right: 5px;
  color: white;
  width: 30px;
  height: 30px;
  animation: ${rotate} 2s linear infinite;
  cursor: pointer;
`

export default ModalLogs
