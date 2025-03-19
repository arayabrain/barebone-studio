import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react"
import { useDispatch, useSelector } from "react-redux"
import { useSearchParams } from "react-router-dom"

import CheckCircleIcon from "@mui/icons-material/CheckCircle"
import { Box, Input, styled, Tooltip } from "@mui/material"
import {
  DataGrid,
  GridColDef,
  GridFilterInputValueProps,
  GridFilterItem,
  GridFilterModel,
  GridSortDirection,
  GridSortItem,
  GridSortModel,
} from "@mui/x-data-grid"

import { WAITING_TIME } from "@types"
import DialogImage from "components/common/DialogImage"
import Loading from "components/common/Loading"
import PaginationCustom from "components/common/PaginationCustom"
import SelectFilter from "components/common/SelectFilter"
import { SpanCustom } from "components/Database/DatabaseExperiments"
import {
  getCellsDatabase,
  getCellsPublicDatabase,
  getOptionsFilter,
} from "store/slice/Database/DatabaseActions"
import { TypeData } from "store/slice/Database/DatabaseSlice"
import {
  DATABASE_SLICE_NAME,
  DatabaseType,
  FilterParams,
  ImageUrls,
} from "store/slice/Database/DatabaseType"
import { AppDispatch, RootState } from "store/store"

type CellProps = {
  user?: unknown
}

let timeout: NodeJS.Timeout | undefined = undefined

const LIST_FILTER_IS = [
  "publish_status",
  "brain_area",
  "promoter",
  "indicator",
  "imaging_depth",
]

const columns = (
  user?: boolean,
  loading: boolean = false,
  options?: FilterParams,
) => [
  {
    field: "experiment_id",
    headerName: "Experiment ID",
    filterOperators: [
      {
        label: "Contains",
        value: "contains",
        InputComponent: ({ applyValue, item }: GridFilterInputValueProps) => {
          return (
            <Input
              autoFocus={!loading}
              sx={{ paddingTop: "16px" }}
              defaultValue={item.value || ""}
              onChange={(e) => {
                if (timeout) clearTimeout(timeout)
                timeout = setTimeout(() => {
                  applyValue({ ...item, value: e.target.value })
                }, WAITING_TIME)
              }}
            />
          )
        },
      },
    ],
    type: "string",
    width: 160,
    renderCell: (params: { row: DatabaseType }) => params.row?.experiment_id,
  },
  user && {
    field: "published",
    headerName: "Published",
    renderCell: (params: { row: DatabaseType }) =>
      params.row.publish_status ? <CheckCircleIcon color={"success"} /> : null,
    valueOptions: ["Published", "No_Published"],
    type: "singleSelect",
    width: 120,
  },
  {
    field: "id",
    headerName: "Cell ID",
    width: 120,
    filterable: false,
    renderCell: (params: { value: number }) => params.value,
  },
  {
    field: "brain_area",
    headerName: "Brain area",
    width: 120,
    filterOperators: [
      {
        label: "Is any of",
        value: "isAnyOf",
        InputComponent: ({ applyValue, item }: GridFilterInputValueProps) => {
          if (!options) return null
          return (
            <SelectFilter
              options={options?.brain_areas}
              loading={loading}
              applyValue={applyValue}
              item={item}
              timeout={timeout}
            />
          )
        },
      },
    ],
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.fields?.brain_area}>
          <SpanCustom>{params.row.fields?.brain_area ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "promoter",
    headerName: "Promoter",
    width: 120,
    filterOperators: [
      {
        label: "Is any of",
        value: "isAnyOf",
        InputComponent: ({ applyValue, item }: GridFilterInputValueProps) => {
          if (!options) return null
          return (
            <SelectFilter
              options={options?.promoters}
              loading={loading}
              applyValue={applyValue}
              item={item}
              timeout={timeout}
            />
          )
        },
      },
    ],
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.fields?.promoter}>
          <SpanCustom>{params.row.fields?.promoter ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "indicator",
    headerName: "Indicator",
    width: 120,
    filterOperators: [
      {
        label: "Is any of",
        value: "isAnyOf",
        InputComponent: ({ applyValue, item }: GridFilterInputValueProps) => {
          if (!options) return null
          return (
            <SelectFilter
              options={options?.indicators}
              loading={loading}
              applyValue={applyValue}
              item={item}
              timeout={timeout}
            />
          )
        },
      },
    ],
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.fields?.indicator}>
          <SpanCustom>{params.row.fields?.indicator ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "imaging_depth",
    headerName: "Imaging depth",
    width: 120,
    filterOperators: [
      {
        label: "Is any of",
        value: "isAnyOf",
        InputComponent: ({ applyValue, item }: GridFilterInputValueProps) => {
          if (!options) return null
          return (
            <SelectFilter
              options={options?.imaging_depths}
              loading={loading}
              applyValue={applyValue}
              item={item}
              timeout={timeout}
            />
          )
        },
      },
    ],
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.fields?.imaging_depth}>
          <SpanCustom>{params.row.fields?.imaging_depth ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
]

const statistics = () => [
  {
    field: "p_value_resp",
    headerName: "p_value_resp",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.p_value_resp}>
          <SpanCustom>{params.row.statistics?.p_value_resp ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "p_value_sel",
    headerName: "p_value_sel",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.p_value_sel}>
          <SpanCustom>{params.row.statistics?.p_value_sel ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "p_value_ori_resp",
    headerName: "p_value_ori_resp",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.p_value_ori_resp}>
          <SpanCustom>
            {params.row.statistics?.p_value_ori_resp ?? "NA"}
          </SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "p_value_ori_sel",
    headerName: "p_value_ori_sel",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.p_value_ori_sel}>
          <SpanCustom>
            {params.row.statistics?.p_value_ori_sel ?? "NA"}
          </SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "dir_vector_angle",
    headerName: "dir_vector_angle",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.dir_vector_angle}>
          <SpanCustom>
            {params.row.statistics?.dir_vector_angle ?? "NA"}
          </SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "ori_vector_angle",
    headerName: "ori_vector_angle",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.ori_vector_angle}>
          <SpanCustom>
            {params.row.statistics?.ori_vector_angle ?? "NA"}
          </SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "di",
    headerName: "di",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.di}>
          <SpanCustom>{params.row.statistics?.di ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "oi",
    headerName: "oi",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.oi}>
          <SpanCustom>{params.row.statistics?.oi ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "dsi",
    headerName: "dsi",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.dsi}>
          <SpanCustom>{params.row.statistics?.dsi ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "osi",
    headerName: "osi",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.osi}>
          <SpanCustom>{params.row.statistics?.osi ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "r_best_dir",
    headerName: "r_best_dir",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.r_best_dir}>
          <SpanCustom>{params.row.statistics?.r_best_dir ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "dir_tuning_width",
    headerName: "dir_tuning_width",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.dir_tuning_width}>
          <SpanCustom>
            {params.row.statistics?.dir_tuning_width ?? "NA"}
          </SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "ori_tuning_width",
    headerName: "ori_tuning_width",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.ori_tuning_width}>
          <SpanCustom>
            {params.row.statistics?.ori_tuning_width ?? "NA"}
          </SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "sf_bandwidth",
    headerName: "SF Bandwidth",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.sf_bandwidth}>
          <SpanCustom>{params.row.statistics?.sf_bandwidth ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "best_sf",
    headerName: "Best SF",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.best_sf}>
          <SpanCustom>{params.row.statistics?.best_sf ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
  {
    field: "sf_si",
    headerName: "SF Selectivity",
    filterable: false,
    sortable: false,
    width: 120,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Tooltip title={params.row.statistics?.sf_si}>
          <SpanCustom>{params.row.statistics?.sf_si ?? "NA"}</SpanCustom>
        </Tooltip>
      )
    },
  },
]

const DatabaseCells = ({ user }: CellProps) => {
  const type: keyof TypeData = user ? "private" : "public"

  const {
    data: dataCells,
    loading,
    filterParams,
  } = useSelector((state: RootState) => ({
    data: state[DATABASE_SLICE_NAME].data[type],
    loading: state[DATABASE_SLICE_NAME].loading,
    filterParams: state[DATABASE_SLICE_NAME].filterParams,
  }))

  const [newParams, setNewParams] = useState(
    window.location.search.replace("?", ""),
  )
  const [dataDialog, setDataDialog] = useState<{
    type: string
    data?: string | string[]
    expId?: string
    cellId?: number
    nameCol?: string
  }>({
    type: "",
    data: undefined,
  })
  const [fieldFilter, setFieldFilter] = useState("")
  const [valueFilter, setValueFilter] = useState<string | string[]>("")

  const [searchParams, setParams] = useSearchParams()
  const dispatch = useDispatch<AppDispatch>()

  const id = searchParams.get("id")
  const offset = searchParams.get("offset")
  const limit = searchParams.get("limit") || 50
  const sort = searchParams.getAll("sort")

  const dataParams = useMemo(() => {
    return {
      exp_id: Number(id) || undefined,
      sort:
        sort.length > 0
          ? [sort[0]?.replace("published", "publish_status"), sort[1]]
          : [],
      limit: Number(limit) || 50,
      offset: Number(offset) || 0,
    }
    //eslint-disable-next-line
  }, [offset, limit, JSON.stringify(sort), id])

  const dataParamsFilter = useMemo(
    () => ({
      experiment_id: searchParams.get("experiment_id") || undefined,
      publish_status: searchParams.get("published") || undefined,
      brain_area: searchParams.getAll("brain_area") || undefined,
      promoter: searchParams.getAll("promoter") || undefined,
      indicator: searchParams.getAll("indicator") || undefined,
      imaging_depth: searchParams.getAll("imaging_depth") || undefined,
    }),
    [searchParams],
  )

  const [model, setModel] = useState<{
    filter: GridFilterModel
    sort: GridSortModel
  }>({
    filter: {
      items: [
        {
          field:
            Object.keys(dataParamsFilter)
              .find(
                (key) => dataParamsFilter[key as keyof typeof dataParamsFilter],
              )
              ?.replace("publish_status", "published") || "",
          operator: LIST_FILTER_IS.includes(
            Object.keys(dataParamsFilter).find(
              (key) => dataParamsFilter[key as keyof typeof dataParamsFilter],
            ) || "publish_status",
          )
            ? "isAnyOf"
            : "contains",
          value: Object.values(dataParamsFilter).find((value) => value) || null,
        },
      ],
    },
    sort: [
      {
        field: dataParams.sort[0]?.replace("publish_status", "published") || "",
        sort: dataParams.sort[1] as GridSortDirection,
      },
    ],
  })

  const pagiFilter = useCallback(
    (page?: number) => {
      return `limit=${limit}&offset=${
        page ? Number(limit) * (page - 1) : offset || dataCells.offset
      }`
    },
    //eslint-disable-next-line
    [limit, offset, JSON.stringify(dataCells), dataCells.offset],
  )

  const fetchApi = () => {
    const api = !user ? getCellsPublicDatabase : getCellsDatabase
    let newPublish: number | undefined
    if (!dataParamsFilter.publish_status) newPublish = undefined
    else {
      if (dataParamsFilter.publish_status === "Published") newPublish = 1
      else newPublish = 0
    }
    dispatch(
      api({ ...dataParamsFilter, publish_status: newPublish, ...dataParams }),
    )
  }

  useEffect(() => {
    const key = Object.keys(dataParamsFilter).find((key) => {
      const value = dataParamsFilter[key as keyof typeof dataParamsFilter]
      return (
        (!Array.isArray(value) && value) ||
        (Array.isArray(value) && value.length)
      )
    }) as keyof typeof dataParamsFilter
    if (key) {
      setFieldFilter(key)
      setValueFilter(dataParamsFilter[key] as string[])
    }
    // eslint-disable-next-line
  }, [])

  useEffect(() => {
    if (
      Object.keys(dataParamsFilter).every(
        (key) => !dataParamsFilter[key as keyof typeof dataParamsFilter],
      )
    ) {
      return
    }
    if (!fieldFilter?.trim()?.length) return
    setModel({
      filter: {
        items: [
          {
            field: fieldFilter?.replace("publish_status", "published") || "",
            operator: LIST_FILTER_IS.includes(fieldFilter || "publish_status")
              ? "isAnyOf"
              : "contains",
            value: valueFilter || null,
          },
        ],
      },
      sort: [
        {
          field:
            dataParams.sort[0]?.replace("publish_status", "published") || "",
          sort: dataParams.sort[1] as GridSortDirection,
        },
      ],
    })
    //eslint-disable-next-line
  }, [dataParams, dataParamsFilter, fieldFilter, valueFilter])

  useEffect(() => {
    let param = newParams
    if (newParams[0] === "&") param = newParams.slice(1, param.length)
    if (param === window.location.search.replace("?", "")) return
    setParams(param.replaceAll("+", "%2B"))
    //eslint-disable-next-line
  }, [newParams])

  useEffect(() => {
    if (newParams && newParams !== window.location.search.replace("?", "")) {
      setNewParams(window.location.search.replace("?", ""))
    }
    //eslint-disable-next-line
  }, [searchParams])

  useEffect(() => {
    dispatch(getOptionsFilter())
    //eslint-disable-next-line
  }, [])

  useEffect(() => {
    fetchApi()
    //eslint-disable-next-line
  }, [JSON.stringify(dataParams), user, JSON.stringify(dataParamsFilter)])

  const handleOpenDialog = (
    data: ImageUrls[] | ImageUrls,
    expId?: string,
    cellId?: number,
    graphTitle?: string,
  ) => {
    let newData: string[] = []
    if (Array.isArray(data)) {
      newData = data.flatMap((d) => d.urls || [])
    } else if (data && data.urls) {
      newData = Array.isArray(data.urls) ? data.urls : [data.urls]
    }
    setDataDialog({
      type: "image",
      data: newData,
      expId: expId,
      cellId: cellId,
      nameCol: graphTitle,
    })
  }

  const handleCloseDialog = () => {
    setDataDialog({ type: "", data: undefined })
  }

  const getParamsData = () => {
    const dataFilter = Object.keys(dataParamsFilter)
      .filter((key) => {
        const value = dataParamsFilter[key as keyof typeof dataParamsFilter]
        if (Array.isArray(value)) {
          return !!value[0]
        }
        return value
      })
      .map((key) => {
        const value = dataParamsFilter[key as keyof typeof dataParamsFilter]
        if (Array.isArray(value)) {
          return value.map((item) => `${key}=${item}`).join("&")
        }
        return `${key}=${
          dataParamsFilter[key as keyof typeof dataParamsFilter]
        }`
      })
      .join("&")
      .replaceAll("publish_status", "published")
    return dataFilter
  }

  const handlePage = (e: ChangeEvent<unknown>, page: number) => {
    if (!dataCells) return
    const filter = getParamsData()
    const param = `${filter}${
      dataParams.sort[0]
        ? `${filter ? "&" : ""}sort=${dataParams.sort[0]}&sort=${
            dataParams.sort[1]
          }`
        : ""
    }&${pagiFilter(page)}`
    setNewParams(param)
  }

  const handleSort = useCallback(
    (rowSelectionModel: GridSortModel) => {
      setModel({
        ...model,
        sort: rowSelectionModel,
      })
      let param
      const filter = getParamsData()
      if (!rowSelectionModel[0]) {
        param =
          filter || dataParams.sort[0] || offset
            ? `${filter ? `${filter}&` : ""}${pagiFilter()}`
            : ""
        setNewParams(param)
        return
      }
      param = `${filter}${
        rowSelectionModel[0]
          ? `${filter ? "&" : ""}sort=${rowSelectionModel[0].field?.replaceAll(
              "publish_status",
              "published",
            )}&sort=${rowSelectionModel[0].sort}&`
          : ""
      }${pagiFilter()}`
      setNewParams(param)
    },
    //eslint-disable-next-line
    [pagiFilter, model],
  )

  const handleFilter = (modelFilter: GridFilterModel) => {
    if (modelFilter.items.length === 0) {
      const data = Object.keys(dataParamsFilter).filter((key) => {
        const value = dataParamsFilter[key as keyof typeof dataParamsFilter]
        if (Array.isArray(value) && value.length === 0) {
          return false
        }
        return !!value
      })
      setModel({
        ...model,
        filter: {
          items: [
            {
              field: data[0],
              operator: "isAnyOf",
              value:
                dataParamsFilter[data[0] as keyof typeof dataParamsFilter] ||
                "",
            },
          ],
        },
      })
      return
    }
    setModel({
      ...model,
      filter: modelFilter,
    })
    setFieldFilter(modelFilter.items[0]?.field)
    setValueFilter(modelFilter.items[0]?.value)
    let filter = ""
    if (modelFilter.items[0]?.value) {
      filter = modelFilter.items
        .filter((item) => item.value)
        .map((item: GridFilterItem) => {
          if (Array.isArray(item.value)) {
            return item.value.map((value) => `${item.field}=${value}`).join("&")
          }
          return `${item.field}=${item?.value}`
        })[0]
        .replace("publish_status", "published")
    }
    const { sort } = dataParams
    const param =
      sort[0] || filter || offset
        ? `${filter}${
            sort[0] ? `${filter ? "&" : ""}sort=${sort[0]}&sort=${sort[1]}` : ""
          }&${pagiFilter()}`
        : ""
    setNewParams(param.replace("publish_status", "published"))
  }

  const handleLimit = (event: ChangeEvent<HTMLSelectElement>) => {
    if (!dataCells) return
    let filter = ""
    filter = Object.keys(dataParamsFilter)
      .filter((key) => dataParamsFilter[key as keyof typeof dataParamsFilter])
      .map((key) => {
        const value = dataParamsFilter[key as keyof typeof dataParamsFilter]
        if (Array.isArray(value)) {
          return value.map((item) => `${key}=${item}`).join("&")
        }
        return `${key}=${
          dataParamsFilter[key as keyof typeof dataParamsFilter]
        }`
      })
      .join("&")
      .replace("publish_status", "published")
    const { sort } = dataParams
    const param = `${filter}${
      sort[0] ? `${filter ? "&" : ""}sort=${sort[0]}&sort=${sort[1]}` : ""
    }&limit=${Number(event.target.value)}&offset=0`
    setNewParams(param)
  }

  const getColumns = useMemo(() => {
    return (dataCells.header?.graph_titles || []).map((graphTitle, index) => ({
      field: `graph_urls.${index}`,
      headerName: graphTitle,
      filterable: false,
      sortable: false,
      renderCell: (params: { row: DatabaseType }) => {
        const { row } = params
        const { graph_urls } = row
        const graph_url = graph_urls[index]
        if (!graph_url) return null
        if (!graph_url.thumb_urls || graph_url.thumb_urls.length === 0) {
          // eslint-disable-next-line no-console
          console.log(`No thumbnail URLs to display for ${graphTitle}`)
          return null
        }
        return (
          <Box
            sx={{ display: "flex", cursor: "pointer" }}
            onClick={() =>
              handleOpenDialog(
                graph_url,
                params.row.experiment_id,
                params.row.id,
                graphTitle,
              )
            }
          >
            <img
              src={graph_url?.thumb_urls?.[0] || ""}
              alt={""}
              width={"100%"}
              height={"100%"}
            />
          </Box>
        )
      },
      width: 160,
    }))
  }, [dataCells.header?.graph_titles])

  const columnsTable = [
    ...columns(!!user, loading, filterParams),
    ...getColumns,
    ...statistics(),
  ].filter(Boolean) as GridColDef[]

  return (
    <DatabaseExperimentsWrapper>
      <DataGrid
        columns={[...columnsTable]}
        rows={dataCells?.items || []}
        rowHeight={128}
        hideFooter={true}
        filterMode={"server"}
        sortingMode={"server"}
        onSortModelChange={handleSort}
        filterModel={model.filter}
        sortModel={model.sort as GridSortItem[]}
        onFilterModelChange={handleFilter}
      />
      {dataCells?.items.length > 0 ? (
        <PaginationCustom
          data={dataCells}
          handlePage={handlePage}
          handleLimit={handleLimit}
          limit={Number(limit)}
        />
      ) : null}
      <DialogImage
        open={dataDialog.type === "image"}
        data={dataDialog.data}
        nameCol={dataDialog.nameCol}
        expId={dataDialog.expId}
        cellId={dataDialog.cellId}
        handleCloseDialog={handleCloseDialog}
      />
      <Loading loading={loading} />
    </DatabaseExperimentsWrapper>
  )
}

const DatabaseExperimentsWrapper = styled(Box)(() => ({
  width: "100%",
  height: "calc(100vh - 250px)",
}))

export default DatabaseCells
