import { memo, useContext, useEffect, useMemo } from "react"
import PlotlyChart from "react-plotlyjs-ts"
import { useSelector, useDispatch } from "react-redux"

import createColormap from "colormap"

import { LinearProgress, Typography } from "@mui/material"

import { DisplayDataContext } from "components/Workspace/Visualize/DataContext"
import { getRoiData } from "store/slice/DisplayData/DisplayDataActions"
import {
  selectRoiData,
  selectRoiDataError,
  selectRoiDataIsFulfilled,
  selectRoiDataIsInitialized,
  selectRoiDataIsPending,
  selectRoiMeta,
} from "store/slice/DisplayData/DisplayDataSelectors"
import {
  selectVisualizeItemHeight,
  selectVisualizeItemWidth,
  selectVisualizeSaveFilename,
  selectVisualizeSaveFormat,
} from "store/slice/VisualizeItem/VisualizeItemSelectors"
import { ColorType } from "store/slice/VisualizeItem/VisualizeItemType"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { AppDispatch } from "store/store"
import { twoDimarrayEqualityFn } from "utils/EqualityUtils"

export const RoiPlot = memo(function RoiPlot() {
  const { filePath: path } = useContext(DisplayDataContext)
  const isPending = useSelector(selectRoiDataIsPending(path))
  const isInitialized = useSelector(selectRoiDataIsInitialized(path))
  const isFulfilled = useSelector(selectRoiDataIsFulfilled(path))
  const error = useSelector(selectRoiDataError(path))
  const workspaceId = useSelector(selectCurrentWorkspaceId)

  const dispatch = useDispatch<AppDispatch>()
  useEffect(() => {
    if (workspaceId && !isInitialized) {
      dispatch(getRoiData({ path, workspaceId }))
    }
  }, [dispatch, isInitialized, path, workspaceId])
  if (isPending) {
    return <LinearProgress />
  } else if (error != null) {
    return <Typography color="error">{error}</Typography>
  } else if (isFulfilled) {
    return <RoiPlotImple />
  } else {
    return null
  }
})

const RoiPlotImple = memo(function RoiPlotImple() {
  const { itemId, filePath: path } = useContext(DisplayDataContext)
  const imageData = useSelector(selectRoiData(path), imageDataEqualtyFn)
  const meta = useSelector(selectRoiMeta(path))
  const width = useSelector(selectVisualizeItemWidth(itemId))
  const height = useSelector(selectVisualizeItemHeight(itemId))

  const colorscale: ColorType[] = createColormap({
    colormap: "jet",
    nshades: 10,
    format: "hex",
    alpha: 1,
  }).map((v, idx) => {
    return { rgb: v, offset: String(idx / 9) }
  })

  const data = useMemo(
    () => [
      {
        z: imageData,
        type: "heatmap",
        name: "roi",
        colorscale: colorscale.map((value) => {
          let offset: number = parseFloat(value.offset)
          const offsets: number[] = colorscale.map((v) => {
            return parseFloat(v.offset)
          })
          // plotlyは端[0.0, 1.0]がないとダメなので、その設定
          if (offset === Math.max(...offsets)) {
            offset = 1.0
          }
          if (offset === Math.min(...offsets)) {
            offset = 0.0
          }
          return [offset, value.rgb]
        }),
        hoverongaps: false,
        // zsmooth: zsmooth, // ['best', 'fast', false]
        zsmooth: false,
        showlegend: true,
        hovertemplate: "ROI: %{z}",
      },
    ],
    [imageData, colorscale],
  )

  const layout = useMemo(
    () => ({
      title: {
        text: meta?.title,
        x: 0.1,
      },
      width: width,
      height: height - 50,
      margin: {
        t: 30, // top
        l: 120, // left
        b: 30, // bottom
      },
      dragmode: "pan",
      xaxis: {
        title: meta?.xlabel,
        autorange: true,
        zeroline: false,
        autotick: true,
        ticks: "",
      },
      yaxis: {
        title: meta?.ylabel,
        autorange: "reversed",
        zeroline: false,
        autotick: true, // todo
        ticks: "",
      },
    }),
    [meta, width, height],
  )

  const saveFileName = useSelector(selectVisualizeSaveFilename(itemId))
  const saveFormat = useSelector(selectVisualizeSaveFormat(itemId))

  const config = {
    displayModeBar: true,
    // scrollZoom: true,
    responsive: true,
    toImageButtonOptions: {
      format: saveFormat,
      filename: saveFileName,
    },
  }
  return <PlotlyChart data={data} layout={layout} config={config} />
})

function imageDataEqualtyFn(
  a: number[][] | undefined,
  b: number[][] | undefined,
) {
  if (a != null && b != null) {
    return twoDimarrayEqualityFn(a, b)
  } else {
    return a === undefined && b === undefined
  }
}
