/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  memo,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react"
import PlotlyChart from "react-plotlyjs-ts"
import { useSelector, useDispatch, shallowEqual } from "react-redux"

import createColormap from "colormap"
import { LegendClickEvent } from "plotly.js"

import { LinearProgress, Typography } from "@mui/material"

import { getRoiDataApi, TimeSeriesData } from "api/outputs/Outputs"
import {
  DialogContext,
  useRoisSelected,
} from "components/Workspace/FlowChart/Dialog/DialogContext"
import { useBoxFilter } from "components/Workspace/FlowChart/Dialog/FilterContext"
import { DisplayDataContext } from "components/Workspace/Visualize/DataContext"
import { useVisualize } from "components/Workspace/Visualize/VisualizeContext"
import { selectAlgorithmDataFilterParam } from "store/slice/AlgorithmNode/AlgorithmNodeSelectors"
import {
  getTimeSeriesDataById,
  getTimeSeriesInitData,
} from "store/slice/DisplayData/DisplayDataActions"
import {
  selectRoiUniqueList,
  selectTimeSeriesData,
  selectTimeSeriesDataError,
  selectTimeSeriesDataIsFulfilled,
  selectTimeSeriesDataIsInitialized,
  selectTimeSeriesDataIsPending,
  selectTimeSeriesStd,
  selectTimeSeriesXrange,
  selectTimesSeriesMeta,
} from "store/slice/DisplayData/DisplayDataSelectors"
import { selectFrameRate } from "store/slice/Experiments/ExperimentsSelectors"
import {
  selectOutputFilePathCellRoi,
  selectPipelineLatestUid,
} from "store/slice/Pipeline/PipelineSelectors"
import {
  selectTimeSeriesItemDrawOrderList,
  selectTimeSeriesItemOffset,
  selectTimeSeriesItemShowGrid,
  selectTimeSeriesItemShowLine,
  selectTimeSeriesItemShowTickLabels,
  selectTimeSeriesItemSpan,
  selectTimeSeriesItemXrange,
  selectTimeSeriesItemZeroLine,
  selectVisualizeItemHeight,
  selectVisualizeItemWidth,
  selectTimeSeriesItemKeys,
  selectVisualizeSaveFilename,
  selectVisualizeSaveFormat,
  selectImageItemRangeUnit,
} from "store/slice/VisualizeItem/VisualizeItemSelectors"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { AppDispatch } from "store/store"

export const TimeSeriesPlot = memo(function TimeSeriesPlot() {
  const { itemId, filePath: path } = useContext(DisplayDataContext)
  const dispatch = useDispatch<AppDispatch>()
  const isPending = useSelector(selectTimeSeriesDataIsPending(path))
  const isInitialized = useSelector(selectTimeSeriesDataIsInitialized(path))
  const error = useSelector(selectTimeSeriesDataError(path))
  const isFulfilled = useSelector(selectTimeSeriesDataIsFulfilled(path))
  const { dialogFilterNodeId } = useContext(DialogContext)

  useEffect(() => {
    dispatch(
      getTimeSeriesInitData({ path, itemId, isFull: !!dialogFilterNodeId }),
    )
  }, [dispatch, path, itemId, dialogFilterNodeId])

  if (!isInitialized) {
    return <LinearProgress />
  } else if (error != null) {
    return <Typography color="error">{error}</Typography>
  } else if (isPending || isFulfilled) {
    return <TimeSeriesPlotImple />
  } else {
    return null
  }
})

const TimeSeriesPlotImple = memo(function TimeSeriesPlotImple() {
  const { filePath: path, itemId, nodeId } = useContext(DisplayDataContext)

  // 0番のデータとkeysだけをとってくる
  const dispatch = useDispatch<AppDispatch>()
  const timeSeriesData = useSelector(
    selectTimeSeriesData(path),
    timeSeriesDataEqualityFn,
  )

  const filterSelector = useSelector(
    selectAlgorithmDataFilterParam(nodeId),
    shallowEqual,
  )
  const workspaceId = useSelector(selectCurrentWorkspaceId)
  const meta = useSelector(selectTimesSeriesMeta(path))
  const dataXrange = useSelector(selectTimeSeriesXrange(path))
  const dataStd = useSelector(selectTimeSeriesStd(path))
  const rangeUnit = useSelector(selectImageItemRangeUnit(itemId))
  const stdBool = useSelector(selectTimeSeriesItemOffset(itemId))
  const span = useSelector(selectTimeSeriesItemSpan(itemId))
  const showgrid = useSelector(selectTimeSeriesItemShowGrid(itemId))
  const showline = useSelector(selectTimeSeriesItemShowLine(itemId))
  const showticklabels = useSelector(selectTimeSeriesItemShowTickLabels(itemId))
  const zeroline = useSelector(selectTimeSeriesItemZeroLine(itemId))
  const xrangeSelector = useSelector(selectTimeSeriesItemXrange(itemId))
  const drawOrderList = useSelector(selectTimeSeriesItemDrawOrderList(itemId))
  const width = useSelector(selectVisualizeItemWidth(itemId))
  const height = useSelector(selectVisualizeItemHeight(itemId))
  const dataKeysSelector = useSelector(selectTimeSeriesItemKeys(itemId))

  const [newDataXrange, setNewDataXrange] = useState<string[]>(dataXrange)
  const [newTimeSeriesData, setNewTimeSeriesData] = useState(timeSeriesData)
  const currentPipelineUid = useSelector(selectPipelineLatestUid)
  const frameRate = useSelector(selectFrameRate(currentPipelineUid))
  const { dialogFilterNodeId, isOutput } = useContext(DialogContext)
  const { setRoiSelected, setMaxDim } = useRoisSelected()
  const { filterParam = filterSelector, roiPath } = useBoxFilter()
  const roiUniqueListSelector = useSelector(
    selectRoiUniqueList(roiPath),
    shallowEqual,
  )
  const [roiUniqueList, setRoiUniqueList] = useState<null | string[]>(
    roiUniqueListSelector,
  )
  const { setRoisClick, links } = useVisualize()
  const itemIdRoi = useMemo(
    () => Object.keys(links).find((key) => links[key] === itemId),
    [itemId, links],
  )
  const pathCellRoi = useSelector(selectOutputFilePathCellRoi(nodeId))

  const isExistFilterRoi = useMemo(
    () => filterParam?.roi?.length,
    [filterParam?.roi?.length],
  )

  const getRoiUniqueList = useCallback(() => {
    if (workspaceId && pathCellRoi) {
      getRoiDataApi(pathCellRoi, { workspaceId }).then(({ data }) => {
        const roi1Ddata: number[] = data[0]
          .map((row) =>
            Array.from(new Set(row.filter((value) => value != null))),
          )
          .flat()
        const roiUniqueIds = Array.from(new Set(roi1Ddata))
          .sort((n1, n2) => n1 - n2)
          .map(String)
        setRoiUniqueList(roiUniqueIds)
      })
    }
  }, [pathCellRoi, workspaceId])

  useEffect(() => {
    if (isOutput && isExistFilterRoi) getRoiUniqueList()
  }, [getRoiUniqueList, isExistFilterRoi, isOutput])

  useEffect(() => {
    if (!isOutput || dialogFilterNodeId) {
      setRoiUniqueList(roiUniqueListSelector)
    }
  }, [dialogFilterNodeId, isOutput, roiUniqueListSelector])

  useEffect(() => {
    if (!timeSeriesData) return
    const max = Math.max(
      ...Object.keys(timeSeriesData).map(
        (e) => Object.keys(timeSeriesData[e]).length,
      ),
    )
    setMaxDim?.(max)
  }, [setMaxDim, timeSeriesData])

  const xrange = useMemo(() => {
    if (dialogFilterNodeId && filterParam) {
      const dim1 = filterParam?.dim1?.[0]
      if (dim1) return { left: dim1.start, right: dim1.end }
    }
    return xrangeSelector
  }, [dialogFilterNodeId, filterParam, xrangeSelector])

  const isExistParamsRoi = useCallback(
    (num: number) => {
      return (
        !isExistFilterRoi ||
        filterParam?.roi?.some(
          (roi) => num >= (roi.start || 0) && (!roi.end || num < roi.end),
        )
      )
    },
    [filterParam?.roi, isExistFilterRoi],
  )

  const dataKeys = useMemo(() => {
    const keys = dataKeysSelector.filter(
      (e) =>
        (roiUniqueList?.includes(e) ||
          (!dialogFilterNodeId && (!isOutput || !isExistFilterRoi))) &&
        isExistParamsRoi(Number(e)),
    )
    return keys
  }, [
    dataKeysSelector,
    dialogFilterNodeId,
    isExistFilterRoi,
    isExistParamsRoi,
    isOutput,
    roiUniqueList,
  ])

  useEffect(() => {
    const seriesData: TimeSeriesData = {}
    drawOrderList.forEach((key) => {
      seriesData[key] = timeSeriesData[key]
    })
    if (
      rangeUnit === "time" &&
      timeSeriesData &&
      Object.keys(timeSeriesData).length > 0
    ) {
      const newSeriesData: TimeSeriesData = {}
      Object.keys(seriesData).forEach((key) => {
        newSeriesData[key] = {}
        Object.keys(seriesData[key]).forEach((keyTime) => {
          const newKeyTime = Number(keyTime) / frameRate
          newSeriesData[key][newKeyTime] = seriesData[key][keyTime]
        })
      })
      setNewDataXrange(
        dataXrange.map((data) => String(Number(data) / frameRate)),
      )
      setNewTimeSeriesData(newSeriesData)
    } else {
      setNewDataXrange(dataXrange)
      setNewTimeSeriesData(seriesData)
    }
    //eslint-disable-next-line
  }, [rangeUnit, dataXrange, timeSeriesData, drawOrderList])

  const nshades = useMemo(() => {
    if (!dataKeys?.length) return 0
    return Math.max(...dataKeys.map((e) => Number(e)))
  }, [dataKeys])

  const colorScale = useMemo(() => {
    return createColormap({
      colormap: "jet",
      nshades: nshades < 100 ? Math.max(nshades, 6) : 100, //maxIndex >= 6 ? maxIndex : 6,
      format: "hex",
      alpha: 1,
    })
  }, [nshades])

  function getRoiColor(roiIndex: number): string {
    const colors = createColormap({
      colormap: "jet",
      nshades: 200,
      format: "hex",
    })
    return colors[(Math.abs(roiIndex) * 9) % 200]
  }

  const data = useMemo(() => {
    return Object.fromEntries(
      dataKeys.map((key) => {
        let y = newDataXrange.map((x) => newTimeSeriesData[key]?.[x])
        const color = dialogFilterNodeId
          ? colorScale[
              Math.floor(((Number(key) % 10) * 10 + Number(key) / 10) % nshades)
            ]
          : getRoiColor(Number(key))
        if (drawOrderList.includes(key) && !stdBool) {
          const activeIdx: number = drawOrderList.findIndex((v) => v === key)
          const mean: number = y.reduce((a, b) => a + b) / y.length
          const std: number =
            span *
            Math.sqrt(y.reduce((a, b) => a + Math.pow(b - mean, 2)) / y.length)
          y = y.map((value) => (value - mean) / (std + 1e-10) + activeIdx)
        }

        return [
          key,
          {
            name: key,
            x: newDataXrange,
            y: y,
            visible: drawOrderList.includes(key) ? true : "legendonly",
            line: { color },
            error_y: {
              type: "data",
              array:
                stdBool && Object.keys(dataStd).includes(key)
                  ? Object.values(dataStd[key])
                  : null,
              visible: true,
            },
          },
        ]
      }),
    )
  }, [
    drawOrderList,
    stdBool,
    span,
    dataStd,
    dataKeys,
    newDataXrange,
    dialogFilterNodeId,
    nshades,
    colorScale,
    newTimeSeriesData,
  ])

  const annotations = useMemo(() => {
    const range = rangeUnit === "time" ? frameRate : 1
    return drawOrderList.map((value) => {
      return {
        x:
          Number((newDataXrange.length - 1) / range) +
          newDataXrange.length / (10 * range),
        y: data[value]?.y[newDataXrange.length - 1],
        xref: "x",
        yref: "y",
        text: `cell: ${value}`,
        arrowhead: 1,
        ax: 0,
        ay: -10,
      }
    })
  }, [data, drawOrderList, newDataXrange, rangeUnit, frameRate])

  const layout = useMemo(
    () => ({
      title: {
        text: meta?.title,
        x: 0.1,
      },
      margin: {
        t: 60, // top
        l: 50, // left
        b: 30, // bottom
      },
      dragmode: "pan",
      autosize: true,
      width: width,
      height: height - 50,
      xaxis: {
        title: {
          text: meta?.xlabel ?? rangeUnit,
        },
        titlefont: {
          size: 12,
          color: "black",
        },
        tickfont: {
          size: 10,
          color: "black",
        },
        range:
          rangeUnit === "frames"
            ? [xrange.left, xrange.right]
            : [
                typeof xrange.left !== "undefined"
                  ? xrange.left / frameRate
                  : -2.5,
                typeof xrange.right !== "undefined"
                  ? xrange.right / frameRate
                  : dataXrange.length / frameRate + 6.8,
              ],
        showgrid: showgrid,
        showline: showline,
        showticklabels: showticklabels,
        zeroline: zeroline,
      },
      yaxis: {
        title: meta?.ylabel,
        showgrid: showgrid,
        showline: showline,
        showticklabels: showticklabels,
        zeroline: zeroline,
      },
      annotations: annotations,
      showlegend: true,
    }),
    [
      meta,
      xrange,
      showgrid,
      showline,
      showticklabels,
      zeroline,
      annotations,
      width,
      height,
      rangeUnit,
      dataXrange,
      frameRate,
    ],
  )

  const saveFileName = useSelector(selectVisualizeSaveFilename(itemId))
  const saveFormat = useSelector(selectVisualizeSaveFormat(itemId))

  const config = {
    displayModeBar: true,
    responsive: true,
    toImageButtonOptions: {
      format: saveFormat,
      filename: saveFileName,
    },
  }

  const onLegendClick = (event: LegendClickEvent) => {
    const clickedSeriesId = dataKeys[event.curveNumber]
    if (dialogFilterNodeId) {
      setRoiSelected(Number(clickedSeriesId))
      return false
    }
    if (itemIdRoi) setRoisClick(Number(itemIdRoi), Number(clickedSeriesId))
    // set DisplayNumbers
    if (!drawOrderList.includes(clickedSeriesId)) {
      dispatch(getTimeSeriesDataById({ path, index: clickedSeriesId }))
    }

    return false
  }

  return (
    <PlotlyChart
      data={Object.values(data)}
      layout={layout}
      config={config}
      onLegendClick={onLegendClick}
    />
  )
})

function timeSeriesDataEqualityFn(
  a: TimeSeriesData | undefined,
  b: TimeSeriesData | undefined,
) {
  if (a != null && b != null) {
    const aArray = Object.entries(a)
    const bArray = Object.entries(b)
    return (
      a === b ||
      (aArray.length === bArray.length &&
        aArray.every(([aKey, aValue], i) => {
          const [bKey, bValue] = bArray[i]
          return bKey === aKey && nestEqualityFun(bValue, aValue)
        }))
    )
  } else {
    return a === undefined && b === undefined
  }
}

function nestEqualityFun(
  a: {
    [key: number]: number
  },
  b: {
    [key: number]: number
  },
) {
  const aArray = Object.entries(a)
  const bArray = Object.entries(b)
  return (
    a === b ||
    (aArray.length === bArray.length &&
      aArray.every(([aKey, aValue], i) => {
        const [bKey, bValue] = bArray[i]
        return bKey === aKey && bValue === aValue
      }))
  )
}
