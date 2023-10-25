import {Box, Checkbox, Input, styled} from '@mui/material'
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ContentPasteSearchIcon from '@mui/icons-material/ContentPasteSearch'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogContentText from '@mui/material/DialogContentText'
import DialogImage from '../common/DialogImage'
import SwitchCustom from '../common/SwitchCustom'
import {
  GridFilterModel,
  GridSortDirection,
  GridSortModel,
  DataGrid,
  GridEventListener,
  GridSortItem,
} from '@mui/x-data-grid'
import GroupsIcon from '@mui/icons-material/Groups'
import DomainIcon from '@mui/icons-material/Domain'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import {
  DatabaseType,
  DATABASE_SLICE_NAME,
  ImageUrls,
} from '../../store/slice/Database/DatabaseType'
import { useSelector, useDispatch } from 'react-redux'
import { RootState } from '../../store/store'
import {
  getExperimentsDatabase,
  getExperimentsPublicDatabase,
  getListShare,
  postPublish,
  postPublishAll,
} from '../../store/slice/Database/DatabaseActions'
import Loading from 'components/common/Loading'
import { TypeData } from 'store/slice/Database/DatabaseSlice'
import { UserDTO } from 'api/users/UsersApiDTO'
import { isAdminOrManager } from 'store/slice/User/UserSelector'
import {SHARE, WAITING_TIME} from '@types'
import PaginationCustom from '../common/PaginationCustom'
import PublicIcon from '@mui/icons-material/Public'
import PublicOffIcon from '@mui/icons-material/PublicOff'
import GroupAddIcon from '@mui/icons-material/GroupAdd'
import PopupConfirm from "../common/PopupConfirm"
import PopupShareGroup from "../PopupShareGroup";

export type Data = {
  id: number
  fields: {
    brain_area?: string
    cre_driver?: string
    reporter_line?: string
    imaging_depth?: number
  }
  experiment_id: string
  attributes: string
  cell_image_urls: string[]
  graph_urls: string[]
  share_type: number
  publish_status: number
  created_time: string
  updated_time: string
}

type PopupAttributesProps = {
  data?: string | string[]
  open: boolean
  handleClose: () => void
  role?: boolean
  handleChangeAttributes: (e: any) => void
  exp_id?: string
}

type DatabaseProps = {
  user?: UserDTO
  cellPath: string
  handleRowClick?: GridEventListener<'rowClick'>
  readonly?: boolean
}

let timeout: NodeJS.Timeout | undefined = undefined

const columns = (
  setListCheck: (value: number[]) => void,
  listCheck: number[],
  dataExperiments: DatabaseType[],
  checkBoxAll: boolean,
  setCheckBoxAll: (value: boolean) => void,
  handleOpenAttributes: (value: string) => void,
  handleOpenDialog: (value: ImageUrls[], exp_id?: string) => void,
  cellPath: string,
  navigate: (path: string) => void,
  user: boolean,
  readonly?: boolean,
  loading: boolean = false,
) => [
  {
    field: 'checkbox',
    renderHeader: () => (
      <Checkbox checked={checkBoxAll} onChange={(e: any) => {
        setCheckBoxAll(e.target.checked)
        if(!e.target.checked) setListCheck([])
        else {
          const newList = dataExperiments.map(item => item.id)
          setListCheck([...listCheck, ...newList.filter(item => !listCheck.includes(item))])
        }
      }}
      />
    ),
    sortable: false,
    filterable: false,
    width: 160,
    type: 'string',
    renderCell: (params: { row: DatabaseType }) => (
      <Checkbox
        checked={listCheck.includes(params.row.id)}
        onChange={(e: any) => {
        const newData = listCheck.filter(id => id !== params.row.id)
        if(!e.target.checked) {
          setCheckBoxAll(false)
          setListCheck(newData)
        }
          else setListCheck([...listCheck, params.row.id])
      }
      }/>
    )
  },
  {
    field: 'experiment_id',
    headerName: 'Experiment ID',
    width: 160,
    filterOperators: [
      {
        label: 'Contains',
        value: 'contains',
        InputComponent: ({ applyValue, item }: any) => {
          return (
            <Input
              autoFocus={!loading}
              sx={{ paddingTop: '16px' }}
              defaultValue={item.value || ''}
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
    type: 'string',
    renderCell: (params: { row: DatabaseType }) => params.row?.experiment_id,
  },
  user && {
    field: 'published',
    headerName: 'Published',
    renderCell: (params: { row: DatabaseType }) =>
      params.row.publish_status ? <CheckCircleIcon color={'success'} /> : null,
    valueOptions: ['Published', 'No_Published'],
    type: 'singleSelect',
    width: 120,
  },
  {
    field: 'brain_area',
    headerName: 'Brain area',
    renderCell: (params: { row: DatabaseType }) =>
      params.row.fields?.brain_area ?? 'NA',
    valueOptions: [1, 2, 3, 4, 5, 6, 7, 8],
    type: 'singleSelect',
    width: 120,
  },
  {
    field: 'cre_driver',
    headerName: 'Cre driver',
    width: 120,
    renderCell: (params: { row: DatabaseType }) =>
      params.row.fields?.cre_driver ?? 'NA',
  },
  {
    field: 'reporter_line',
    headerName: 'Reporter line',
    width: 120,
    renderCell: (params: { row: DatabaseType }) =>
      params.row.fields?.reporter_line ?? 'NA',
  },
  {
    field: 'imaging_depth',
    headerName: 'Imaging depth',
    width: 120,
    renderCell: (params: { row: DatabaseType }) =>
      params.row.fields?.imaging_depth ?? 'NA',
  },
  {
    field: 'attributes',
    headerName: 'Attributes',
    width: 120,
    filterable: false,
    sortable: false,
    renderCell: (params: { row: DatabaseType }) => (
      <Box
        sx={{ cursor: 'pointer' }}
        onClick={() =>
          handleOpenAttributes(JSON.stringify(params.row?.attributes))
        }
      >
        {JSON.stringify(params.row?.attributes)}
      </Box>
    ),
  },
  !readonly && {
    field: 'cells',
    headerName: 'Cells',
    width: 120,
    filterable: false,
    sortable: false,
    renderCell: (params: { row: DatabaseType }) => (
      <Box
        sx={{ cursor: 'pointer', color: 'dodgerblue' }}
        onClick={() =>
          navigate(`${cellPath}?experiment_id=${params.row?.experiment_id}`)
        }
      >
        <ContentPasteSearchIcon />
      </Box>
    ),
  },
  {
    field: 'cell_image_urls',
    headerName: 'Pixel Image',
    width: 160,
    filterable: false,
    sortable: false,
    renderCell: (params: { row: DatabaseType }) => {
      return (
        <Box
          sx={{
            cursor: 'pointer',
            display: 'flex',
          }}
          onClick={() => handleOpenDialog(params.row?.cell_image_urls)}
        >
          {params.row?.cell_image_urls?.length > 0 && (
            <img
              src={params.row?.cell_image_urls[0].thumb_url}
              alt={''}
              width={'100%'}
              height={'100%'}
            />
          )}
        </Box>
      )
    },
  },
]

const PopupAttributes = ({
  data,
  open,
  handleClose,
  role = false,
  handleChangeAttributes,
  exp_id,
}: PopupAttributesProps) => {
  useEffect(() => {
    const handleClosePopup = (event: any) => {
      if (event.key === 'Escape') {
        handleClose()
        return
      }
    }

    document.addEventListener('keydown', handleClosePopup)
    return () => {
      document.removeEventListener('keydown', handleClosePopup)
    }
    //eslint-disable-next-line
  }, [])

  return (
    <Box>
      <Dialog
        open={open}
        onClose={handleClose}
        aria-labelledby="draggable-dialog-title"
      >
        <DialogContent sx={{ minWidth: 400 }}>
          <DialogContentText>
            <Content
              readOnly={!role}
              value={data}
              onChange={handleChangeAttributes}
            />
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button autoFocus onClick={handleClose}>
            Close
          </Button>
          {role && <Button onClick={handleClose}>Save</Button>}
        </DialogActions>
      </Dialog>
    </Box>
  )
}
const DatabaseExperiments = ({
  user,
  cellPath,
  handleRowClick,
  readonly,
}: DatabaseProps) => {
  const type: keyof TypeData = user ? 'private' : 'public'
  const adminOrManager = useSelector(isAdminOrManager)
  const { data: dataExperiments, loading } = useSelector(
    (state: RootState) => ({
      data: state[DATABASE_SLICE_NAME].data[type],
      loading: state[DATABASE_SLICE_NAME].loading,
    }),
  )

  const [openPublishAll, setOpenPublishAll] = useState<{ title: string, open: boolean, type: 'on' | 'off'}>({
    title: '',
    open: false,
    type: 'on'
  })
  const [newParams, setNewParams] = useState(window.location.search.replace("?", ""))
  const [openShare, setOpenShare] = useState<{ open: boolean; id?: number }>({
    open: false,
  })
  const [listCheck, setListCheck] = useState<number[]>([])
  const [checkBoxAll, setCheckBoxAll] = useState(false)
  const [openShareGroup, setOpenShareGroup] = useState(false)
  const [dataDialog, setDataDialog] = useState<{
    type?: string
    data?: string | string[]
    expId?: string
    nameCol?: string
    shareType?: number
  }>({
    type: '',
    data: undefined,
  })

  const [searchParams, setParams] = useSearchParams()
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const offset = searchParams.get('offset')
  const limit = searchParams.get('limit') || 50
  const sort = searchParams.getAll('sort')

  const { dataShare } = useSelector((state: RootState) => ({
    dataShare: state[DATABASE_SLICE_NAME].listShare,
  }))

  const pagiFilter = useCallback(
    (page?: number) => {
      return `limit=${limit}&offset=${
        page ? Number(limit) * (page - 1) : offset || dataExperiments.offset
      }`
    },
    //eslint-disable-next-line
    [limit, offset, JSON.stringify(dataExperiments), dataExperiments.offset],
  )

  const dataParams = useMemo(() => {
    return {
      offset: Number(offset) || 0,
      limit: Number(limit) || 50,
      sort: [sort[0]?.replace('published', 'publish_status'), sort[1]] || [],
    }
    //eslint-disable-next-line
  }, [offset, limit, JSON.stringify(sort)])

  const dataParamsFilter = useMemo(
    () => ({
      experiment_id: searchParams.get('experiment_id') || undefined,
      publish_status: searchParams.get('published') || undefined,
      brain_area: searchParams.get('brain_area') || undefined,
      cre_driver: searchParams.get('cre_driver') || undefined,
      reporter_line: searchParams.get('reporter_line') || undefined,
      imaging_depth: Number(searchParams.get('imaging_depth')) || undefined,
    }),
    [searchParams],
  )

  const [model, setModel] = useState<{filter: GridFilterModel, sort: any}>({
    filter: {
      items: [
        {
          field: Object.keys(dataParamsFilter).find(key => (dataParamsFilter as any)[key])?.replace('publish_status', 'published') || '' ,
          operator: ['publish_status', 'brain_area'].includes(Object.keys(dataParamsFilter).find(key => (dataParamsFilter as any)[key]) || 'publish_status') ? 'is' : 'contains',
          value: Object.values(dataParamsFilter).find(value => value) || null,
        },
      ],
    },
    sort: [{
      field: dataParams.sort[0]?.replace('publish_status', 'published') || '',
      sort: dataParams.sort[1] as GridSortDirection
    }]
  })

  const fetchApi = () => {
    const api = !user ? getExperimentsPublicDatabase : getExperimentsDatabase
    let newPublish: number | undefined
    if (!dataParamsFilter.publish_status) newPublish = undefined
    else {
      if (dataParamsFilter.publish_status === 'Published') newPublish = 1
      else newPublish = 0
    }
    dispatch(
      api({ ...dataParamsFilter, publish_status: newPublish, ...dataParams }),
    )
  }

  useEffect(() => {
    if(Object.keys(dataParamsFilter).every(key => !(dataParamsFilter as any)[key])) return
    setModel({
      filter: {
        items: [
          {
            field: Object.keys(dataParamsFilter).find(key => (dataParamsFilter as any)[key])?.replace('publish_status', 'published') || '' ,
            operator: ['publish_status', 'brain_area'].includes(Object.keys(dataParamsFilter).find(key => (dataParamsFilter as any)[key]) || '') ? 'is' : 'contains',
            value: Object.values(dataParamsFilter).find(value => value) || null,
          },
        ],
      },
      sort: [{
        field: dataParams.sort[0]?.replace('publish_status', 'published') || '',
        sort: dataParams.sort[1] as GridSortDirection
      }]
    })
    //eslint-disable-next-line
  }, [dataParams, dataParamsFilter])

  useEffect(() => {
    let param = newParams
    if(newParams[0] === '&') param = newParams.slice(1, param.length)
    if(param === window.location.search.replace("?", "")) return;
    setParams(param)
    //eslint-disable-next-line
  }, [newParams])

  useEffect(() => {
    fetchApi()
    //eslint-disable-next-line
  }, [JSON.stringify(dataParams), user, JSON.stringify(dataParamsFilter)])

  useEffect(() => {
    if (!openShare.open || !openShare.id) return
    dispatch(getListShare({ id: openShare.id }))
    //eslint-disable-next-line
  }, [openShare])

  useEffect(() => {
    setCheckBoxAll(false)
  }, [offset, limit, JSON.stringify(dataParamsFilter)])

  const handleOpenDialog = (
    data: ImageUrls[] | ImageUrls,
    expId?: string,
    graphTitle?: string,
  ) => {
    let newData: string | string[] = []
    if (Array.isArray(data)) {
      newData = data.map((d) => d.url)
    } else newData = data.url
    setDataDialog({
      type: 'image',
      data: newData,
      expId: expId,
      nameCol: graphTitle,
    })
  }

  const handleCloseDialog = () => {
    setDataDialog({ type: '', data: undefined })
  }

  const handleOpenAttributes = (data: string) => {
    setDataDialog({ type: 'attribute', data })
  }

  const handleChangeAttributes = (event: any) => {
    setDataDialog((pre) => ({ ...pre, data: event.target.value }))
  }

  const handleOpenShare = (expId?: string, value?: number, id?: number) => {
    setDataDialog({ expId: expId, shareType: value })
    setOpenShare({ open: true, id: id })
  }

  const getParamsData = () => {
    const dataFilter = Object.keys(dataParamsFilter)
      .filter((key) => (dataParamsFilter as any)[key])
      .map((key) => `${key}=${(dataParamsFilter as any)[key]}`)
      .join('&')
      .replaceAll('publish_status', 'published')
    return dataFilter
  }

  const handlePage = (e: ChangeEvent<unknown>, page: number) => {
    const filter = getParamsData()
    const param = `${filter}${dataParams.sort[0]? `${filter ? '&' : ''}sort=${dataParams.sort[0]}&sort=${dataParams.sort[1]}` : ''}&${pagiFilter(page)}`
    setNewParams(param)
  }

  const handlePublish = async (id: number, status: 'on' | 'off') => {
    let newPublish: number | undefined
    if (!dataParamsFilter.publish_status) newPublish = undefined
    else {
      if (dataParamsFilter.publish_status === 'Published') newPublish = 1
      else newPublish = 0
    }
    await dispatch(
      postPublish({
        id,
        status,
        params: {
          ...dataParamsFilter,
          publish_status: newPublish,
          ...dataParams,
        },
      }),
    )
  }

  const handleSort = useCallback(
    (rowSelectionModel: GridSortModel) => {
      setModel({
        ...model, sort: rowSelectionModel
      })
      let param
      const filter = getParamsData()
      if (!rowSelectionModel[0]) {
        param = filter || dataParams.sort[0] || offset ? `${filter ? `${filter}&` : ''}${pagiFilter()}` : ''
      } else {
        param = `${filter}${rowSelectionModel[0] ? `${filter ? '&' : ''}sort=${rowSelectionModel[0].field?.replace('publish_status','published')}&sort=${rowSelectionModel[0].sort}` : ''}&${pagiFilter()}`
      }
      setNewParams(param.replace('publish_status', 'published'))
    },
    //eslint-disable-next-line
    [pagiFilter, model],
  )

  const handleFilter = (modelFilter: GridFilterModel) => {
    setModel({
      ...model, filter: modelFilter
    })
    let filter = ''
    if (!!modelFilter.items[0]?.value) {
      filter = modelFilter.items
        .filter((item) => item.value)
        .map((item: any) => `${item.field}=${item?.value}`)
        .join('&')
        ?.replace('publish_status', 'published')
    }
    const { sort } = dataParams
    const param = sort[0] || filter || offset ? `${filter}${sort[0] ? `${filter ? '&' : ''}sort=${sort[0]}&sort=${sort[1]}` : ''}&${pagiFilter()}` : ''
    setNewParams(param.replace('publish_status', 'published'))
  }

  const handleLimit = (event: ChangeEvent<HTMLSelectElement>) => {
    let filter = ''
    filter = Object.keys(dataParamsFilter)
      .filter((key) => (dataParamsFilter as any)[key])
      .map((item: any) => `${item}=${(dataParamsFilter as any)[item]}`)
      .join('&')
      .replace('publish_status', 'published')
    const { sort } = dataParams
    const param = `${filter}${sort[0] ? `${filter ? '&' : ''}sort=${sort[0]}&sort=${sort[1]}` : ''}&limit=${Number(event.target.value)}&offset=0`
    setNewParams(param)
  }

  const handlePublishCancel = () => {
    setOpenPublishAll({
      ...openPublishAll,
      open: false
    })
  }

  const handleOpenPublishAll = (title: string, type: 'on' | 'off') => {
    setOpenPublishAll({
      title: title,
      open: true,
      type: type
    })
  }

  const handlePublishOk = () => {
    setOpenPublishAll({
      ...openPublishAll,
      open: false
    })
    try {
      dispatch(postPublishAll({
        status: openPublishAll.type,
        params: {
          ...dataParamsFilter,
          ...dataParams,
        },
        listCheck
      }))
    }
    finally {

    }
  }

  const getColumns = useMemo(() => {
    return (dataExperiments.header?.graph_titles || []).map(
      (graphTitle, index) => ({
        field: `graph_urls.${index}`,
        headerName: graphTitle,
        sortable: false,
        filterable: false,
        renderCell: (params: { row: DatabaseType }) => {
          const { row } = params
          const { graph_urls } = row
          const graph_url = graph_urls[index]
          if (!graph_url) return null
          return (
            <Box
              sx={{ display: 'flex', cursor: 'pointer' }}
              onClick={() =>
                handleOpenDialog(graph_url, row.experiment_id, graphTitle)
              }
            >
              <img
                src={graph_url.thumb_url}
                alt={''}
                width={'100%'}
                height={'100%'}
              />
            </Box>
          )
        },
        width: 160,
      }),
    )
  }, [dataExperiments.header?.graph_titles])

  const ColumnPrivate = useMemo(() => {
    return [
      {
        field: 'share_type',
        headerName: 'Share',
        width: 120,
        sortable: false,
        filterable: false,
        renderCell: (params: { value: number; row: DatabaseType }) => {
          const { value, row } = params
          return (
            <Box
              sx={{ cursor: 'pointer', color: 'darkgray' }}
              onClick={() => handleOpenShare(row.experiment_id, value, row.id)}
            >
              {value === SHARE.ORGANIZATION ? (
                <DomainIcon color="primary" />
              ) : (
                <GroupsIcon
                  color={`${value === SHARE.NOSHARE ? 'inherit' : 'primary'}`}
                />
              )}
            </Box>
          )
        },
      },
      {
        field: 'publish_status',
        headerName: 'Publish',
        width: 120,
        sortable: false,
        filterable: false,
        renderCell: (params: { row: DatabaseType }) => (
          <Box
            sx={{ cursor: 'pointer' }}
            onClick={() =>
              handlePublish(
                params.row.id,
                params.row.publish_status ? 'off' : 'on',
              )
            }
          >
            <SwitchCustom value={!!params.row.publish_status} />
          </Box>
        ),
      },
    ]
    //eslint-disable-next-line
  }, [handlePublish])

  const columnsTable = [
    ...columns(
      setListCheck,
      listCheck,
      dataExperiments?.items,
      checkBoxAll,
      setCheckBoxAll,
      handleOpenAttributes,
      handleOpenDialog,
      cellPath,
      navigate,
      !!user,
      readonly,
      loading,
    ),
    ...getColumns,
  ].filter(Boolean) as any

  return (
    <DatabaseExperimentsWrapper>
      {
        user ?
          (<WrapperIcons>
              <GroupAddIcon
                sx={{ cursor: listCheck.length === 0 ? 'default !important' : 'pointer' }}
                onClick={() => listCheck.length !== 0 && setOpenShareGroup(true)}
              />
            {
              listCheck.length > 0 ? (
                <>
                  <PublicIcon onClick={() => handleOpenPublishAll(`Publish ${listCheck.length} records at once. Is this OK?`, 'on')} />
                  <PublicOffIcon onClick={() => handleOpenPublishAll(`Unpublish ${listCheck.length} records at once. Is this OK?`, 'off')} />
                </>
              ): null
            }
          </WrapperIcons>) : null
      }
      <DataGrid
        columns={
          adminOrManager && user && !readonly
            ? ([...columnsTable, ...ColumnPrivate] as any)
            : (columnsTable as any)
        }
        sortModel={model.sort as GridSortItem[]}
        rows={dataExperiments?.items || []}
        rowHeight={128}
        hideFooter={true}
        filterMode={'server'}
        sortingMode={'server'}
        onSortModelChange={handleSort}
        filterModel={model.filter}
        onFilterModelChange={handleFilter as any}
        onRowClick={handleRowClick}
        sx={{ height: 'calc(100% - 50px)'}}
      />
      {dataExperiments?.items.length > 0 ? (
        <PaginationCustom
          data={dataExperiments}
          handlePage={handlePage}
          handleLimit={handleLimit}
          limit={Number(limit)}
        />
      ) : null}
      <DialogImage
        open={dataDialog.type === 'image'}
        data={dataDialog.data}
        expId={dataDialog.expId}
        nameCol={dataDialog.nameCol}
        handleCloseDialog={handleCloseDialog}
      />
      <PopupAttributes
        handleChangeAttributes={handleChangeAttributes}
        data={dataDialog.data}
        open={dataDialog.type === 'attribute'}
        handleClose={handleCloseDialog}
        role={!!adminOrManager}
      />
      {loading ? <Loading /> : null}
      {openShare.open && openShare.id ? (
        <PopupShareGroup
          type={'share'}
          listCheck={listCheck}
          id={openShare.id}
          open={openShare.open}
          data={dataDialog as { expId: string; shareType: number }}
          usersShare={dataShare}
          handleClose={(isSubmit) => {
            if (isSubmit) fetchApi()
            setOpenShare({ ...openShare, open: false })
          }}
        />
      ) : null}
      {openShareGroup &&
        <PopupShareGroup
          type={'multiShare'}
          listCheck={listCheck}
          usersShare={dataShare}
          open={openShareGroup}
          data={dataDialog as { expId: string; shareType: number }}
          handleClose={() => setOpenShareGroup(false)}
          paramsUrl={{ ...dataParams, ...dataParamsFilter}}
        />
      }
      <PopupConfirm
        open={openPublishAll.open}
        title={openPublishAll.title}
        handleClose={handlePublishCancel}
        handleOk={handlePublishOk}
      />
    </DatabaseExperimentsWrapper>
  )
}

const DatabaseExperimentsWrapper = styled(Box)(() => ({
  width: '100%',
  height: 'calc(100vh - 250px)',
}))

const Content = styled('textarea')(() => ({
  width: 400,
  height: 'fit-content',
}))

const WrapperIcons = styled(Box)(() => ({
  display: 'flex',
  justifyContent: 'end',
  gap: 10,
  marginBottom: 10,
  'svg: hover': {
    cursor: 'pointer'
  }
}))

export default DatabaseExperiments
