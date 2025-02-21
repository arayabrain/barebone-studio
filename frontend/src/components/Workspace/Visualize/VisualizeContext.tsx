import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react"
import { useSelector, useDispatch, shallowEqual } from "react-redux"

import { getTimeSeriesDataById } from "store/slice/DisplayData/DisplayDataActions"
import { selectStatusRoiTempAdd } from "store/slice/DisplayData/DisplayDataSelectors"
import { selectVisualizeDataFilePath } from "store/slice/VisualizeItem/VisualizeItemSelectors"
import {
  setTimeSeriesItemDrawOrder,
  setTimeSeriesItemDrawOrderList,
} from "store/slice/VisualizeItem/VisualizeItemSlice"
import { AppDispatch, RootState, store } from "store/store"

type TVisualizeContext = {
  roisClick: { [itemId: string]: number[] }
  setRoisClick: (itemId: number, roi: number) => void
  setRoisClickWithGetTime: (itemId: number, roi: number) => void
  resetRoisClick: (itemId: number) => void
  links: { [linkItemId: string]: string | number }
  setLinks: (itemId: number, linkItemId: number) => () => void
  isVisualize?: boolean
}

const VisualizeContext = createContext<TVisualizeContext>({
  roisClick: {},
  setRoisClick: () => null,
  setRoisClickWithGetTime: () => null,
  resetRoisClick: () => null,
  links: {},
  setLinks: () => () => null,
  isVisualize: false,
})

export const useVisualize = () => useContext(VisualizeContext)

export const VisualizeProvider = ({ children }: PropsWithChildren) => {
  const [rois, setRois] = useState<{ [key: string]: number[] }>({})
  const [links, _setLinks] = useState<{ [itemId: string]: string | number }>({})
  const dispatch = useDispatch<AppDispatch>()
  const selectedStatusTempAdd = useSelector(
    selectStatusRoiTempAdd,
    shallowEqual,
  )

  const linksRef = useRef(links)
  const roisRef = useRef(rois)

  useEffect(() => {
    linksRef.current = links
  }, [links])

  useEffect(() => {
    roisRef.current = rois
  }, [rois])

  const setRoisClick = useCallback(
    (itemId: string | number, roi: number) => {
      setRois((pre) => ({
        ...pre,
        [itemId]: pre[itemId]?.some((e) => e === roi)
          ? pre[itemId].filter((e) => e !== roi)
          : [...(pre[itemId] || []), roi],
      }))
      const fluorescenceId = linksRef.current[itemId]
      if (fluorescenceId !== undefined) {
        dispatch(
          setTimeSeriesItemDrawOrder({
            itemId: Number(fluorescenceId),
            drawOrder: String(roi),
          }),
        )
      }
    },
    [dispatch],
  )
  const setRoisClickWithGetTime = useCallback(
    async (itemId: string | number, roi: number) => {
      setRois((pre) => ({
        ...pre,
        [itemId]: pre[itemId]?.some((e) => e === roi)
          ? pre[itemId].filter((e) => e !== roi)
          : [...(pre[itemId] || []), roi],
      }))
      const fluorescenceId = linksRef.current[itemId]
      if (fluorescenceId !== undefined) {
        dispatch(
          setTimeSeriesItemDrawOrder({
            itemId: Number(fluorescenceId),
            drawOrder: String(roi),
          }),
        )
        const path = selectVisualizeDataFilePath(fluorescenceId as number)(
          store.getState() as RootState,
        )
        await dispatch(
          getTimeSeriesDataById({ path: path!, index: String(roi) }),
        ).unwrap()
      }
    },
    [dispatch],
  )

  const resetRoisClick = useCallback(
    (itemId: string | number) => {
      setRois((pre) => ({ ...pre, [itemId]: [] }))
      const fluorescenceId = linksRef.current[itemId]
      if (fluorescenceId !== undefined) {
        dispatch(
          setTimeSeriesItemDrawOrderList({
            itemId: Number(fluorescenceId),
            drawOrderList: [],
          }),
        )
      }
    },
    [dispatch],
  )

  const setLinks = useCallback(
    (itemId: number, linkItemId: number) => {
      _setLinks((pre) => ({ ...pre, [linkItemId]: itemId }))
      const drawOrders = roisRef.current[linkItemId] || []
      dispatch(
        setTimeSeriesItemDrawOrderList({
          itemId: Number(itemId),
          drawOrderList: drawOrders.map((e) => String(e)),
        }),
      )
      drawOrders.forEach(async (e) => {
        const path = selectVisualizeDataFilePath(itemId)(
          store.getState() as RootState,
        )
        if (!path) return
        if (!selectedStatusTempAdd.includes(Number(e))) {
          await dispatch(
            getTimeSeriesDataById({ path, index: String(e) }),
          ).unwrap()
        }
      })
      return () => {
        dispatch(
          setTimeSeriesItemDrawOrderList({
            itemId: Number(itemId),
            drawOrderList: [],
          }),
        )
        _setLinks((pre) => {
          delete pre[linkItemId]
          return pre
        })
      }
    },
    [dispatch, selectedStatusTempAdd],
  )

  return (
    <VisualizeContext.Provider
      value={{
        roisClick: rois,
        setRoisClick,
        links,
        setLinks,
        resetRoisClick,
        setRoisClickWithGetTime,
        isVisualize: true,
      }}
    >
      {children}
    </VisualizeContext.Provider>
  )
}
