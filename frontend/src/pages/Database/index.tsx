import { Box, Button, IconButton, styled, TextField } from '@mui/material'
import { ChangeEvent, useEffect, useState } from 'react'
import DatabaseTableComponent from 'components/DatabaseTable'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import CloseIcon from '@mui/icons-material/Close'
import ImageView from 'components/ImageView'
import ModalDeleteAccount from 'components/ModalDeleteAccount'
import { onGet, onSort } from 'utils/database'

type PopupSearchProps = {
  onClose?: () => any
  onFilter?: (values: { [key: string]: string }) => any
  defaultValue?: { [key: string]: string }
}

export const PopupSearch = ({
  onClose,
  defaultValue = {},
  onFilter,
}: PopupSearchProps) => {
  const [values, setValues] = useState(defaultValue)

  const handleFilter = () => {
    onFilter?.(values)
    onClose?.()
  }

  const onChange = (
    event: ChangeEvent<HTMLTextAreaElement | HTMLInputElement>,
  ) => {
    setValues({ ...values, [event.target.name]: event.target.value })
  }

  return (
    <Popup>
      <PopupInner>
        <HeaderTitle>
          <span>Filter</span>
          <ButtonControl onClick={onClose}>
            <CloseIcon />
          </ButtonControl>
        </HeaderTitle>
        <InputSearch
          onChange={onChange}
          name={'session'}
          label="Session"
          variant="outlined"
        />
        <InputSearch
          onChange={onChange}
          name={'dataset'}
          label="Dataset"
          variant="outlined"
        />
        <InputSearch
          onChange={onChange}
          name={'type'}
          label="Type"
          variant="outlined"
        />
        <InputSearch
          onChange={onChange}
          name={'protocol'}
          label="Protocol"
          variant="outlined"
        />
        <Button variant="contained" onClick={handleFilter}>
          Filter
        </Button>
      </PopupInner>
    </Popup>
  )
}

export type Image = {
  id: number
  parent_id: number
  session_id: number
  label: string
  image: {
    id: number
    parent_id: number
    image_url: string
    attributes: { [key: string]: any }
  }
}

export type Viewer = {
  open: boolean
  url: string
  jsonData?: { [key: string]: any }
  id?: number
  session_id?: number
  parent_id?: number
}

export type DataDatabase = {
  id: number
  lab_name: string
  user_name: string
  sample_name: string
  subject: string
  recording_time: string
  sessions: {
    id: number
    parent_id: number
    label: string
    datatypes: {
      title: string
      images: Image[]
    }
  }[]
}

const dataImages = [
  {
    id: 1,
    lab_name: 'lab 1',
    user_name: 'hoge',
    sample_name: 'hoge',
    recording_time: '2018-03-10',
    type: 'TYPE_RATE',
    datatypes: 'anat',
    protocol: 'protocol 3',
    size: '6MB',
    sessions: 'sess 1',
    subject: 'sub 1',
    voxel_size: '8MB',
    image: {
      id: 0,
      parent_id: 0,
      image_url: '/lib/test0.nii',
      attributes: { file_name: 'image 0' },
    },
  },
  {
    id: 2,
    lab_name: 'lab 2',
    user_name: 'hoge 2',
    sessions: 'sess 2',
    subject: 'sub 2',
    datatypes: 'anat',
    sample_name: 'hoge 2',
    recording_time: '2019-03-10',
    type: 'TYPE_2',
    protocol: 'protocol 3',
    size: '7MB',
    voxel_size: '8MB',
    image: {
      id: 1,
      parent_id: 0,
      image_url: '/lib/test.nii',
      attributes: { file_name: 'image 1' },
    },
  },
  {
    id: 3,
    parent_id: 0,
    lab_name: 'lab 3',
    user_name: 'hoge 3',
    sample_name: 'hoge 3',
    recording_time: '2020-04-10',
    sessions: 'sess 3',
    subject: 'sub 3',
    datatypes: 'anat',
    protocol: 'protocol',
    size: '8MB',
    voxel_size: 'voxel_size',
    type: 'TYPE_RATE',
    image: {
      id: 1,
      parent_id: 0,
      image_url: '/lib/test1.nii',
      attributes: { file_name: 'image 2' },
    },
  },
  {
    id: 4,
    parent_id: 2,
    lab_name: 'lab 4',
    user_name: 'hoge 4',
    sample_name: 'hoge 4',
    recording_time: '2021-04-11',
    protocol: 'protocol',
    size: '9MB',
    sessions: 'sess 4',
    subject: 'sub 4',
    voxel_size: 'voxel_size',
    datatypes: 'anat',
    type: 'TYPE_RATE',
    image: {
      id: 0,
      parent_id: 0,
      image_url: '/lib/test2.nii',
      attributes: { file_name: 'image 3' },
    },
  },
  {
    id: 5,
    parent_id: 4,
    lab_name: 'lab 5',
    user_name: 'hoge 5',
    sample_name: 'hoge 5',
    recording_time: '2022-04-15',
    protocol: 'protocol',
    size: '1MB',
    sessions: 'sess 5',
    datatypes: 'anat',
    subject: 'sub 5',
    voxel_size: 'voxel_size',
    type: 'TYPE_RATE',
    image: {
      id: 1,
      parent_id: 0,
      image_url: '/lib/test3.nii',
      attributes: { file_name: 'image 4' },
    },
  },
]

export const defaultDatabase = [
  {
    id: 0,
    lab_name: 'lab 1',
    user_name: 'hoge',
    sample_name: 'hoge',
    recording_time: '2017-03-10',
  },
  {
    id: 1,
    lab_name: 'lab 4',
    user_name: 'hoge 4',
    sample_name: 'hoge 4',
    recording_time: '2018-03-10',
  },
  {
    id: 2,
    lab_name: 'lab 5',
    user_name: 'hoge 5',
    sample_name: 'hoge 5',
    recording_time: '2019-03-10',
  },
  {
    id: 3,
    lab_name: 'lab 2',
    user_name: 'hoge 2',
    sample_name: 'hoge 2',
    recording_time: '2020-03-10',
    sessions: [
      {
        id: 0,
        parent_id: 3,
        sessions: 'session 1',
        subject: '1 subject 6',
        datatypes: {
          title: 'anat',
          images: [
            {
              id: 0,
              parent_id: 3,
              session_id: 0,
              protocol: 'protocol',
              size: '5MB',
              voxel_size: 'voxel_size',
              type: 'TYPE_RATE',
              image: {
                id: 0,
                image_url: '/lib/test0.nii',
                attributes: {
                  file_name: 'image 0',
                },
              },
            },
            {
              id: 1,
              parent_id: 3,
              session_id: 0,
              protocol: 'protocol',
              size: '5MB',
              voxel_size: 'voxel_size',
              type: 'TYPE_RATE',
              image: {
                id: 1,
                image_url: '/lib/test.nii',
                attributes: {
                  file_name: 'image 1',
                },
              },
            },
          ],
        },
      },
      {
        id: 1,
        parent_id: 3,
        sessions: 'session 3',
        subject: '2 subject 5',
        datatypes: {
          title: 'anat',
          images: [
            {
              id: 2,
              parent_id: 3,
              session_id: 1,
              protocol: 'protocol',
              size: '5MB',
              voxel_size: 'voxel_size',
              type: 'TYPE_RATE',
              image: {
                id: 2,
                image_url: '/lib/test1.nii',
                attributes: {
                  file_name: 'image 2',
                },
              },
            },
            {
              id: 3,
              parent_id: 3,
              session_id: 1,
              protocol: 'protocol',
              size: '5MB',
              voxel_size: 'voxel_size',
              type: '3_TYPE_RATE',
              image: {
                id: 3,
                image_url: '/lib/test2.nii',
                attributes: {
                  file_name: 'image 3',
                },
              },
            },
            {
              id: 4,
              parent_id: 3,
              session_id: 1,
              protocol: 'protocol',
              size: '5MB',
              voxel_size: 'voxel_size',
              type: 'TYPE_RATE',
              image: {
                id: 4,
                image_url: '/lib/test3.nii',
                attributes: {
                  file_name: 'image 4',
                },
              },
            },
          ],
        },
      },
    ],
  },
  {
    id: 4,
    lab_name: 'lab 2',
    user_name: 'hoge 2',
    sample_name: 'hoge 2',
    recording_time: '2021-03-10',
    sessions: [
      {
        id: 2,
        parent_id: 4,
        sessions: 'session 4',
        subject: '3 subject 2',
        datatypes: {
          title: 'anat',
          images: [
            {
              id: 5,
              parent_id: 4,
              session_id: 2,
              protocol: 'protocol',
              size: '5MB',
              voxel_size: 'voxel_size',
              type: 'TYPE_RATE',
              image: {
                id: 0,
                image_url: '/lib/test4.nii',
                attributes: {
                  file_name: 'image 5',
                },
              },
            },
          ],
        },
      },
    ],
  },
]

export const columns = (rowClick: Function, setOpenDelete: Function) => [
  { title: 'Lab', name: 'lab_name', filter: true, width: 100 },
  { title: 'User', name: 'user_name', filter: true },
  { title: 'Date', name: 'recording_time', filter: true },
  { title: 'Subject', name: 'subject', filter: true },
  {
    title: 'Session',
    name: 'sessions',
    child: 'label',
    filter: true,
    width: 100,
  },
  {
    title: 'Dataset',
    name: 'datatypes',
    filter: true,
    width: 100,
  },
  { title: 'Type', name: 'type', filter: true },
  { title: 'Protocol', name: 'protocol', filter: true },
  { title: 'Size', name: 'size', filter: true },
  { title: 'Voxel size', name: 'voxel_size', filter: true },
  {
    title: '',
    name: 'action',
    render: (data: any) => {
      if (!data?.image) return null
      return (
        <BoxButton>
          <ButtonControl
            aria-label="Example"
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
              rowClick?.(data)
            }}
          >
            <EditIcon fontSize="small" color={'inherit'} />
          </ButtonControl>
          <ButtonControl
            aria-label="Example"
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
              setOpenDelete?.(true)
            }}
          >
            <DeleteIcon fontSize="small" sx={{ color: 'red' }} />
          </ButtonControl>
        </BoxButton>
      )
    },
  },
]

const Database = () => {
  const [openPopup, setOpenPopup] = useState(false)
  const [viewer, setViewer] = useState<Viewer>({ open: false, url: '' })
  const [datasTable, setDatasTable] = useState<any[]>(defaultDatabase)
  const [openDelete, setOpenDelete] = useState(false)
  const [orderBy, setOrdeBy] = useState<'ASC' | 'DESC' | undefined>()
  const [columnSort, setColumnSort] = useState<string>('')
  const [type, setType] = useState<'tree' | 'list'>('tree')
  const [disabled, setDisabled] = useState({ left: false, right: false })

  const onCloseImageView = () => {
    setViewer({ open: false, url: '' })
  }

  useEffect(() => {
    if (type === 'tree') {
      setDatasTable(defaultDatabase)
    } else setDatasTable(dataImages)
  }, [type])

  const rowClick = (row: any) => {
    if (!row?.image?.image_url) return
    let datas: any[] = dataImages
    const view = {
      open: true,
      url: row.image.image_url,
      id: row.id,
      session_id: row.session_id,
      parent_id: row.parent_id,
      jsonData: row.image.attributes,
    }
    if (type === 'tree') {
      datas = defaultDatabase
      const checkNext = onGet(datas as any, view)
      const checkPre = onGet(
        JSON.parse(JSON.stringify(datas)).reverse() as any,
        view,
        true,
      )
      setDisabled({ left: !checkPre, right: !checkNext })
    } else {
      setDisabled({
        left: row.id === datas?.[0]?.id,
        right: row.id === datas?.[datas.length - 1]?.id,
      })
    }
    setViewer(view)
  }

  const handleCloseDelete = () => {
    setOpenDelete(false)
  }

  const onDelete = () => {
    setOpenDelete(false)
  }

  const handleSort = (orderKey: string) => {
    setColumnSort(orderKey)
    let typeOrder: 'ASC' | 'DESC' | undefined = undefined
    if (!orderBy || orderKey !== columnSort) {
      typeOrder = 'ASC'
    } else if (orderBy === 'ASC') {
      typeOrder = 'DESC'
    }
    setOrdeBy(typeOrder)
    if (!typeOrder) {
      if (type === 'tree') {
        setDatasTable(defaultDatabase)
      } else {
        setDatasTable(dataImages)
      }
      return
    }
    const { data } = onSort(
      type === 'tree' ? defaultDatabase : dataImages,
      typeOrder,
      type,
    )
    setDatasTable(data)
  }

  const onNext = () => {
    if (type === 'tree') {
      const imageNext = onGet(datasTable as any, viewer)
      rowClick(imageNext)
    } else {
      const findIndex = datasTable.findIndex((e) => e.id === viewer.id)
      rowClick(dataImages[findIndex + 1])
    }
  }

  const onPrevious = () => {
    if (type === 'tree') {
      const datas = JSON.parse(JSON.stringify(datasTable))
      const imageNext = onGet(datas.reverse() as any, viewer, true)
      rowClick(imageNext)
    } else {
      const findIndex = datasTable.findIndex((e) => e.id === viewer.id)
      rowClick(dataImages[findIndex - 1])
    }
  }

  return (
    <DatabaseWrapper>
      <ModalDeleteAccount
        titleSubmit="Delete Image"
        description={`Are you sure delete?\n`}
        onClose={handleCloseDelete}
        open={openDelete}
        onSubmit={onDelete}
      />
      <ProjectsTitle>
        <span>Database</span>
        <ButtonFilter
          onClick={() => setOpenPopup(true)}
          style={{ margin: '0 26px 0 0' }}
        >
          Filter
        </ButtonFilter>
      </ProjectsTitle>
      <BoxSelectTypeView>
        <Box
          onClick={() => setType('tree')}
          style={{
            marginRight: 4,
            fontWeight: type === 'tree' ? 700 : 500,
            cursor: 'pointer',
            color: type === 'tree' ? '' : '#4687f4',
          }}
        >
          Tree
        </Box>
        /
        <Box
          onClick={() => setType('list')}
          style={{
            marginLeft: 4,
            fontWeight: type === 'list' ? 700 : 500,
            cursor: 'pointer',
            color: type === 'list' ? '' : '#4687f4',
          }}
        >
          List
        </Box>
      </BoxSelectTypeView>
      {openPopup && <PopupSearch onClose={() => setOpenPopup(false)} />}
      <DatabaseTableComponent
        defaultExpand
        previewImage={type === 'list'}
        onSort={handleSort}
        rowClick={rowClick}
        orderKey={columnSort}
        orderBy={orderBy}
        data={datasTable}
        columns={columns(rowClick, setOpenDelete)}
      />
      <ImageView
        disabled={disabled}
        url={viewer.url}
        open={viewer.open}
        jsonData={viewer.jsonData}
        onClose={onCloseImageView}
        onNext={onNext}
        onPrevious={onPrevious}
      />
    </DatabaseWrapper>
  )
}

const DatabaseWrapper = styled(Box)(({ theme }) => ({
  width: '100%',
  padding: theme.spacing(2),
  overflow: 'auto',
}))

const HeaderTitle = styled('h1')(() => ({
  width: '100%',
  display: 'flex',
  justifyContent: 'space-between',
}))

const Popup = styled(Box)(() => ({
  position: 'fixed',
  top: 0,
  left: 0,
  width: '100%',
  height: '100vh',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  backgroundColor: '#cccccc80',
  zIndex: 9999,
}))

const PopupInner = styled(Box)(({ theme }) => ({
  padding: theme.spacing(2, 3),
  backgroundColor: '#fff',
  borderRadius: theme.spacing(1),
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(2),
}))

const InputSearch = styled(TextField)(() => ({
  minWidth: 250,
}))

const BoxButton = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'flex-end',
  gap: theme.spacing(1),
}))

const ButtonFilter = styled(Button)(({ theme }) => ({
  margin: theme.spacing(2, 0),
  minWidth: 80,
  paddingLeft: theme.spacing(2),
  paddingRight: theme.spacing(2),
  backgroundColor: '#283237 !important',
  color: '#ffffff',
}))

const ButtonControl = styled(IconButton)(({ theme }) => ({
  padding: theme.spacing(0, 1),
  width: 30,
  height: 30,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}))

const ProjectsTitle = styled('h1')(() => ({
  width: '100%',
  display: 'flex',
  justifyContent: 'space-between',
}))

const BoxSelectTypeView = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  marginBottom: 16,
})

export default Database