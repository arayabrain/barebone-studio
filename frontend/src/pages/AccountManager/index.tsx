import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import {ChangeEvent, useCallback, useEffect, useMemo, useState, MouseEvent} from "react";
import {Box, Button, Dialog, DialogActions, DialogTitle, Input, styled, Tooltip} from "@mui/material";
import {useDispatch, useSelector} from "react-redux";
import {isAdmin, selectCurrentUser, selectListUser, selectLoading} from "../../store/slice/User/UserSelector";
import {useNavigate, useSearchParams} from "react-router-dom";
import {deleteUser, createUser, getListUser, updateUser} from "../../store/slice/User/UserActions";
import Loading from "../../components/common/Loading";
import {AddUserDTO, UserDTO} from "../../api/users/UsersApiDTO";
import {ROLE, WAITING_TIME} from "../../@types";
import {DataGrid, GridFilterModel, GridSortDirection, GridSortItem, GridSortModel} from "@mui/x-data-grid";
import {regexEmail, regexIgnoreS, regexPassword} from "../../const/Auth";
import InputError from "../../components/common/InputError";
import {SelectChangeEvent} from "@mui/material/Select";
import SelectError from "../../components/common/SelectError";
import PaginationCustom from "../../components/common/PaginationCustom";
import {useSnackbar, VariantType} from "notistack";
import {getGroupsManager} from "../../store/slice/GroupManager/GroupActions";
import {selectGroupManager} from "../../store/slice/GroupManager/GroupManagerSelectors";
import {ItemGroupManage} from "../../store/slice/GroupManager/GroupManagerType";

let timeout: NodeJS.Timeout | undefined = undefined

export type FormDataType = {
  id?: string
  uid?: string
  email?: string
  password?: string
  role_id?: string
  name?: string
  confirmPassword?: string
  group_ids?: string[] | number[] | string
}

type ModalComponentProps = {
  onSubmitEdit: (
    id: number | string | undefined,
    data: FormDataType,
  ) => void
  setOpenModal: (v: boolean) => void
  dataEdit?: FormDataType
}

type PopupType = {
  open: boolean
  handleClose: () => void
  handleOkDel: () => void
  name?: string
}

const initState = {
  email: '',
  password: '',
  role_id: '',
  name: '',
  confirmPassword: '',
  group_ids: []
}

const ModalComponent =
  ({
    onSubmitEdit,
    setOpenModal,
    dataEdit,
  }: ModalComponentProps) => {

  const dispatch = useDispatch()

  const listGroupData = useSelector(selectGroupManager)

  const [formData, setFormData] = useState<FormDataType>(
      dataEdit || initState,
  )
  const [isDisabled, setIsDisabled] = useState(false)
  const [errors, setErrors] = useState<{ [key: string]: string }>({ ...initState, group_ids: ''})
  const [listGroup, setListGroup] = useState<ItemGroupManage[]>([])
  const [optionsGroup, setOptionsGroup] = useState<{ name: string, id: number }[]>([])

  useEffect(() => {
    dispatch(getGroupsManager({
      offset: 0,
      limit: 50
    }))
    //eslint-disable-next-line
  }, [])

  useEffect(() => {
    setListGroup(listGroupData.items)
    //eslint-disable-next-line
  }, [JSON.stringify(listGroupData)])

  useEffect(() => {
    const newOptions = listGroup.map(item => ({ name: item.name, id: item.id}))
    setOptionsGroup(newOptions)
  }, [listGroup])

  const validateEmail = (value: string): string => {
    const error = validateField('email', 255, value)
    if (error) return error
    if (!regexEmail.test(value)) {
      return 'Invalid email format'
    }
    return ''
  }

  const validatePassword = (
      value: string,
      isConfirm: boolean = false,
      values?: FormDataType,
  ): string => {
    if (!value && !dataEdit?.uid) return 'This field is required'
    const errorLength = validateLength('password', 255, value)
    if (errorLength) {
      return errorLength
    }
    let datas = values || formData
    if (!regexPassword.test(value) && value) {
      return 'Your password must be at least 6 characters long and must contain at least one letter, number, and special character'
    }
    if(regexIgnoreS.test(value)){
      return 'Allowed special characters (!#$%&()*+,-./@_|)'
    }
    if (isConfirm && datas.password !== value && value) {
      return 'password is not match'
    }
    return ''
  }

  const validateField = (name: string, length: number, value?: string) => {
    if (!value) return 'This field is required'
    return validateLength(name, length, value)
  }

  const validateLength = (name: string, length: number, value?: string) => {
    if (value && value.length > length)
      return `The text may not be longer than ${length} characters`
    if (formData[name as keyof FormDataType]?.length && value && value.length > length) {
      return `The text may not be longer than ${length} characters`
    }
    return ''
  }

  const validateForm = (): { [key: string]: string } => {
    const errorName = validateField('name', 100, formData.name)
    const errorEmail = validateEmail(formData.email as string)
    const errorRole = validateField('role_id', 50, formData.role_id)
    const errorPassword = dataEdit?.id ? '' : validatePassword(formData.password as string)
    const errorConfirmPassword = dataEdit?.id ? '' : validatePassword(
      formData.confirmPassword as string,
      true,
    )
    return {
      email: errorEmail,
      password: errorPassword,
      confirmPassword: errorConfirmPassword,
      name: errorName,
      role_id: errorRole,
    }
  }

  const onChangeData = (
    e: ChangeEvent<HTMLTextAreaElement | HTMLInputElement> | SelectChangeEvent | ChangeEvent<{ value: unknown[], name: string }>,
    length: number,
  ) => {
    const { value, name } = e.target
    const newDatas = { ...formData, [name]: value }
    setFormData(newDatas)
    let error: string
    if(name === 'email') error = validateEmail(value as string)
    else error = validateField(name, length, value as string)
    let errorConfirm = errors.confirmPassword
    if (name.toLowerCase().includes('password')) {
      error = validatePassword(value as string, name === 'confirmPassword', newDatas)
      if (name !== 'confirmPassword' && formData.confirmPassword) {
        errorConfirm = validatePassword(
          newDatas.confirmPassword as string,
          true,
          newDatas,
        )
      }
    }
    setErrors({ ...errors, confirmPassword: errorConfirm, [name]: error })
  }

  const onSubmit = async (e: MouseEvent<HTMLButtonElement>) => {
    e.preventDefault()
    setIsDisabled(true)
    const newErrors = validateForm()
    if (Object.keys(newErrors).some((key) => !!newErrors[key])) {
      setErrors(newErrors)
      setIsDisabled(false)
      return
    }
    try {
      const newGroup = optionsGroup.map(option => {
        if((formData.group_ids as string[])?.includes(option.name)) return option.id
        return undefined
      })
      await onSubmitEdit(dataEdit?.id, { ...formData, group_ids: newGroup.filter(Boolean) as number[]})
      setOpenModal(false)
    } finally {
      setIsDisabled(false)
    }
  }
  const onCancel = () => {
    setOpenModal(false)
  }

  return (
    <Modal>
      <ModalBox>
        <form>
          <TitleModal>{dataEdit?.id ? 'Edit' : 'Add'} Account</TitleModal>
          <BoxData>
            <LabelModal>Name: </LabelModal>
            <InputError
              name="name"
              value={formData?.name || ''}
              onChange={(e) => onChangeData(e, 100)}
              onBlur={(e) => onChangeData(e, 100)}
              errorMessage={errors.name}
            />
            <LabelModal>Role: </LabelModal>
            <SelectError
              value={formData?.role_id || ''}
              options={Object.keys(ROLE).filter(key => !Number(key))}
              name="role_id"
              onChange={(e) => onChangeData(e, 50)}
              onBlur={(e) => onChangeData(e, 50)}
              errorMessage={errors.role_id}
            />
            <LabelModal>e-mail: </LabelModal>
            <InputError
              name="email"
              value={formData?.email || ''}
              onChange={(e) => onChangeData(e, 255)}
              onBlur={(e) => onChangeData(e, 255)}
              errorMessage={errors.email}
            />
            <LabelModal>Group: </LabelModal>
              <Tooltip title={(formData?.group_ids as string[])?.join(', ') || ''} placement="top">
                <Box display={'inline'}>
                  <SelectError
                    multiple={true}
                    value={(formData?.group_ids as string[]) || []}
                    options={optionsGroup.map(item => item.name)}
                    name="group_ids"
                    onChange={(e) => onChangeData(e, 50)}
                    onBlur={(e) => onChangeData(e, 50)}
                    errorMessage={errors.group_ids}
                  />
                </Box>
              </Tooltip>
            {!dataEdit?.id ? (
              <>
                <LabelModal>Password: </LabelModal>
                <InputError
                  name="password"
                  value={formData?.password || ''}
                  onChange={(e) => onChangeData(e, 255)}
                  onBlur={(e) => onChangeData(e, 255)}
                  type={'password'}
                  errorMessage={errors.password}
                />
                <LabelModal>Confirm Password: </LabelModal>
                <InputError
                  name="confirmPassword"
                  value={formData?.confirmPassword || ''}
                  onChange={(e) => onChangeData(e, 255)}
                  onBlur={(e) => onChangeData(e, 255)}
                  type={'password'}
                  errorMessage={errors.confirmPassword}
                />
              </>
            ) : null}
          </BoxData>
          <ButtonModal>
            <Button onClick={() => onCancel()}>Cancel</Button>
            <Button disabled={isDisabled} onClick={(e) => onSubmit(e)}>
              Ok
            </Button>
          </ButtonModal>
        </form>
      </ModalBox>
      {isDisabled ? <Loading /> : null}
    </Modal>
  )
}

const PopupDelete = ({open, handleClose, handleOkDel, name}: PopupType) => {
  if(!open) return null
  return (
    <Box>
      <Dialog open={open} onClose={handleClose} sx={{ margin: 0 }}>
        <DialogTitle>Do you want delete User "{name}"?</DialogTitle>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button onClick={handleOkDel}>Ok</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

const AccountManager = () => {

  const dispatch = useDispatch()

  const navigate = useNavigate()

  const listUser = useSelector(selectListUser)
  const loading = useSelector(selectLoading)
  const user = useSelector(selectCurrentUser)
  const admin = useSelector(isAdmin)

  const [searchParams, setParams] = useSearchParams()

  const [openModal, setOpenModal] = useState(false)
  const [dataEdit, setDataEdit] = useState({})
  const [newParams, setNewParams] = useState(window.location.search.replace("?", ""))

  const limit = searchParams.get('limit') || 50
  const offset = searchParams.get('offset') || 0
  const name = searchParams.get('name') || undefined
  const email = searchParams.get('email') || undefined
  const sort = searchParams.getAll('sort') || []
  const [openDel, setOpenDel] = useState<{id?: number, name?: string, open: boolean}>()

  const filterParams = useMemo(() => {
    return {
      name: name,
      email: email
    }
  }, [name, email])

  const sortParams = useMemo(() => {
    return {
      sort: sort
    }
    //eslint-disable-next-line
  }, [JSON.stringify(sort)])

  const params = useMemo(() => {
    return {
      limit: Number(limit),
      offset: Number(offset)
    }
  }, [limit, offset])

  const [model, setModel] = useState<{filter: GridFilterModel, sort: any}>({
    filter : {
      items: [
        {
          field: Object.keys(filterParams).find(key => (filterParams as any)[key]) || '',
          operator: 'contains',
          value: Object.values(filterParams).find(value => value) || null,
        },
      ],
    },
    sort: [{
      field: sortParams.sort[0]?.replace('role', 'role_id') || '',
      sort: sortParams.sort[1] as GridSortDirection
    }]
  })

  const { enqueueSnackbar } = useSnackbar();

  const handleClickVariant = (variant: VariantType, mess: string) => {
    enqueueSnackbar(mess, { variant });
  };

  useEffect(() => {
    if(!admin) navigate('/console')
    //eslint-disable-next-line
  }, [JSON.stringify(admin)])

  useEffect(() => {
    if(Object.keys(filterParams).every(key => !(filterParams as any)[key])) return
    setModel({
      filter: {
        items: [
          {
            field: Object.keys(filterParams).find(key => (filterParams as any)[key]) || '' ,
            operator: 'contains',
            value: Object.values(filterParams).find(value => value) || null,
          },
        ],
      },
      sort: [{
        field: sortParams.sort[0]?.replace('role', 'role_id') || '',
        sort: sortParams.sort[1] as GridSortDirection
      }]
    })
    //eslint-disable-next-line
  }, [sortParams, filterParams])

  useEffect(() => {
    if(newParams && newParams !== window.location.search.replace("?", "")){
      setNewParams(window.location.search.replace("?", ""))
    }
    //eslint-disable-next-line
  }, [searchParams])

  useEffect(() => {
    if(newParams === window.location.search.replace("?", "")) return;
    setParams(newParams)
    //eslint-disable-next-line
  }, [newParams])

  useEffect(() => {
    dispatch(getListUser({...filterParams, ...sortParams, ...params}))
    //eslint-disable-next-line
  }, [limit, offset, email, name, JSON.stringify(sort)])

  const getParamsData = () => {
    const dataFilter = Object.keys(filterParams)
      .filter((key) => (filterParams as any)[key])
      .map((key) => `${key}=${(filterParams as any)[key]}`)
      .join('&')
    return dataFilter
  }

  const paramsManager = useCallback(
    (page?: number) => {
      return `limit=${limit}&offset=${
        page ? page - 1 : offset
      }`
    },
    [limit, offset],
  )

  const handleSort = useCallback(
    (rowSelectionModel: GridSortModel) => {
      setModel({
        ...model, sort: rowSelectionModel
      })
      let param
      const filter = getParamsData()
      if (!rowSelectionModel[0]) {
        param = filter || sortParams.sort[0] || offset ? `${filter ? `${filter}&` : ''}${paramsManager()}` : ''
      } else {
        param = `${filter}${rowSelectionModel[0] ? `${filter ? `&` : ''}sort=${rowSelectionModel[0].field.replace('_id', '')}&sort=${rowSelectionModel[0].sort}` : ''}&${paramsManager()}`
      }
      setNewParams(param)
      //eslint-disable-next-line
    }, [paramsManager, getParamsData, model])

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
    }
    const { sort } = sortParams
    const param = sort[0] || filter || offset ? `${filter}${sort[0] ? `${filter ? "&": ""}sort=${sort[0]}&sort=${sort[1]}` : ''}&${paramsManager()}` : ''
    setNewParams(param)
  }

  const handleOpenModal = () => {
    setOpenModal(true)
  }

  const handleEdit = (dataEdit: UserDTO) => {
    if(!dataEdit) return
    setOpenModal(true)
    setDataEdit({ ...dataEdit, group_ids: dataEdit.groups?.map(item => item.name)})
  }

  const onSubmitEdit = async (
    id: number | string | undefined,
    data: FormDataType,
  ) => {
    const {confirmPassword, role_id, group_ids, ...newData} = data
    let newRole
    switch (role_id) {
      case "ADMIN":
        newRole = ROLE.ADMIN;
        break;
      case "DATA_MANAGER":
        newRole = ROLE.DATA_MANAGER;
        break;
      case "OPERATOR":
        newRole = ROLE.OPERATOR;
        break;
      case "GUEST_OPERATOR":
        newRole = ROLE.GUEST_OPERATOR;
        break;
    }
    if (id !== undefined) {
      const data = await dispatch(updateUser(
        {
          id: id as number,
          data: {name: newData.name as string, email: newData.email as string, role_id: newRole, group_ids: group_ids as number[]},
          params: {...filterParams, ...sortParams, ...params}
        }))
        if((data as any).error) {
          if (!navigator.onLine) {
            handleClickVariant('error', 'Account update failed!')
            return
          }
          handleClickVariant('error', 'This email already exists!')
        }
        else {
          handleClickVariant('success', 'Your account has been edited successfully!')
        }
    } else {
      const data = await dispatch(createUser({
        data: {...newData, role_id: newRole, group_ids: group_ids} as AddUserDTO,
        params: {...filterParams, ...sortParams, ...params}
      }))
      if(!(data as any).error) {
        handleClickVariant('success', 'Your account has been created successfully!')
      }
        else {
        if (!navigator.onLine) {
          handleClickVariant('error', 'Account creation failed!')
          return
        }
        handleClickVariant('error', 'This email already exists!')
      }
    }
    return undefined
  }

  const handleOpenPopupDel = (id?: number, name?: string) => {
    if(!id) return
    setOpenDel({id: id, name: name, open: true})
  }

  const handleClosePopupDel = () => {
    setOpenDel({...openDel, open: false})
  }

  const handleOkDel = async () => {
    if(!openDel?.id || !openDel) return
    const data = await dispatch(deleteUser({
      id: openDel.id,
      params: {...filterParams, ...sortParams, ...params}
    }))
    if((data as any).error) {
      handleClickVariant('error', 'Delete user failed!')
    }
    else {
      handleClickVariant('success', 'Account deleted successfully!')
    }
    setOpenDel({...openDel, open: false})
  }

  const handleLimit = (event: ChangeEvent<HTMLSelectElement>) => {
    let filter = ''
    filter = Object.keys(filterParams).filter(key => (filterParams as any)[key])
      .map((item: any) => `${item}=${(filterParams as any)[item]}`)
      .join('&')
    const { sort } = sortParams
    const param = `${filter}${sort[0] ? `${filter ? '&' : ''}sort=${sort[0]}&sort=${sort[1]}` : ''}&limit=${Number(event.target.value)}&offset=0`
    setNewParams(param)
  }

  const handlePage = (event: ChangeEvent<unknown>, page: number) => {
    if(!listUser) return
    let filter = ''
    filter = Object.keys(filterParams).filter(key => (filterParams as any)[key])
      .map((item: any) => `${item}=${(filterParams as any)[item]}`)
      .join('&')
    const { sort } = sortParams
    const param = `${filter}${sort[0] ? `${filter ? '&' : ''}sort=${sort[0]}&sort=${sort[1]}` : ''}&limit=${listUser.limit}&offset=${(page - 1) * Number(limit)}`
    setNewParams(param)
  }

  const columns = [
    {
      headerName: 'ID',
      field: 'id',
      filterable: false,
      minWidth: 100,
      flex: 1
    },
    {
      headerName: 'Name',
      field: 'name',
      minWidth: 100,
      flex: 2,
      filterOperators: [
        {
          label: 'Contains',
          value: 'contains',
          InputComponent: ({applyValue, item}: any) => {
            return (
              <Input
                autoFocus={!loading}
                sx={{paddingTop: "16px"}}
                defaultValue={item.value || ''}
                onChange={(e) => {
                  if(timeout) clearTimeout(timeout)
                  timeout = setTimeout(() => {
                    applyValue({...item, value: e.target.value})
                  }, WAITING_TIME)
                }}
              />
            )
          }
        },
      ],
      type: "string",
    },
    {
      headerName: 'Role',
      field: 'role_id',
      filterable: false,
      minWidth: 100,
      flex: 1,
      renderCell: (params: {value: number}) => {
        let role
        switch (params.value) {
          case ROLE.ADMIN:
            role = "Admin";
            break;
          case ROLE.DATA_MANAGER:
            role = "Data Manager";
            break;
          case ROLE.OPERATOR:
            role = "Operator";
            break;
          case ROLE.GUEST_OPERATOR:
            role = "Guest Operator";
            break;
        }
        return (
          <span>{role}</span>
        )
      }
    },
    {
      headerName: 'Mail',
      field: 'email',
      minWidth: 100,
      flex: 2,
      filterOperators: [
        {
          label: 'Contains', value: 'contains',
          InputComponent: ({applyValue, item}: any) => {
            return (
              <Input
                autoFocus={!loading}
                sx={{paddingTop: "16px"}}
                defaultValue={item.value || ''}
                onChange={(e) => {
                  if(timeout) clearTimeout(timeout)
                  timeout = setTimeout(() => {
                    applyValue({...item, value: e.target.value})
                  }, WAITING_TIME)
                }}
              />
            )
          }
        },
      ],
      type: "string",
    },
    {
      headerName: 'Groups',
      field: 'groups',
      filterable: false,
      sortable: false,
      minWidth: 100,
      flex: 3,
      renderCell: (params: {row: UserDTO}) => {
        if(!params) return null
        return(
          <Tooltip title={params?.row?.groups?.map(item => item.name).join(', ') || ''} placement={'top'}>
            <div style={{ textOverflow: 'ellipsis', width: '100%', overflow: 'hidden' }}>{params?.row?.groups?.map(item => item.name).join(', ')}</div>
          </Tooltip>
        )
      },
      type: "string",
    },
    {
      headerName: '',
      field: 'action',
      sortable: false,
      filterable: false,
      minWidth: 100,
      flex: 1,
      renderCell: (params: {row: UserDTO}) => {
        const { id, role_id, name, email, groups } = params.row
        if(!id || !role_id || !name || !email) return null
        let role: any
        switch (role_id) {
          case ROLE.ADMIN:
            role = "ADMIN";
            break;
          case ROLE.DATA_MANAGER:
            role = "DATA_MANAGER";
            break;
          case ROLE.OPERATOR:
            role = "OPERATOR";
            break;
          case ROLE.GUEST_OPERATOR:
            role = "GUEST_OPERATOR";
            break;
        }

        return (
          <>
            <ALink
              sx={{ color: 'red' }}
              onClick={() => handleEdit({id, role_id: role, name, email, groups} as UserDTO)}
            >
              <EditIcon sx={{ color: 'black' }} />
            </ALink>
            {
              !(params.row?.id === user?.id) ?
              <ALink
                sx={{ ml: 1.25 }}
                onClick={() => handleOpenPopupDel(params.row?.id, params.row?.name)}
              >
                <DeleteIcon sx={{ color: 'red' }} />
              </ALink> : null
            }
          </>
        )
      },
    },
  ];

  return (
    <AccountManagerWrapper>
      <AccountManagerTitle>Group Manager</AccountManagerTitle>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 2,
          marginBottom: 2,
        }}
      >
        <Button 
          sx={{
            background: '#000000c4',
            '&:hover': { backgroundColor: '#00000090' },
          }}
          variant="contained"
          onClick={handleOpenModal}
        >
          Add
        </Button>
      </Box>
      <DataGrid
        sx={{ minHeight: 400, height: 'calc(100vh - 300px)'}}
        columns={columns as any}
        rows={listUser?.items || []}
        filterMode={'server'}
        sortingMode={'server'}
        hideFooter
        onSortModelChange={handleSort}
        filterModel={model.filter}
        sortModel={model.sort as GridSortItem[]}
        onFilterModelChange={handleFilter as any}
      />
      {
        listUser && listUser.items.length > 0 ?
          <PaginationCustom
            data={listUser}
            handlePage={handlePage}
            handleLimit={handleLimit}
            limit={Number(limit)}
          /> : null
      }
      <PopupDelete
        open={openDel?.open || false}
        handleClose={handleClosePopupDel}
        handleOkDel={handleOkDel}
        name={openDel?.name}
      />
      {
        openModal ?
          <ModalComponent
            onSubmitEdit={onSubmitEdit}
            setOpenModal={(flag) => {
              setOpenModal(flag)
              if (!flag) {
                setDataEdit({})
              }
            }}
            dataEdit={dataEdit}
          /> : null
      }
      {
        loading ? <Loading /> : null
      }
    </AccountManagerWrapper>
  )
}

const AccountManagerWrapper = styled(Box)(({ theme }) => ({
  width: '80%',
  margin: theme.spacing(5, 'auto')
}))

const ALink = styled('a')({
  color: '#1677ff',
  textDecoration: 'none',
  cursor: 'pointer',
  userSelect: 'none',
})

const Modal = styled(Box)(({ theme }) => ({
  position: 'fixed',
  top: 0,
  left: 0,
  width: '100%',
  height: '100vh',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  backgroundColor: '#cccccc80',
}))

const ModalBox = styled(Box)(({ theme }) => ({
  width: 800,
  backgroundColor: 'white',
  border: '1px solid black',
}))

const TitleModal = styled(Box)(({ theme }) => ({
  fontSize: 25,
  margin: theme.spacing(5),
}))

const BoxData = styled(Box)(({ theme }) => ({
  marginTop: 35,
}))

const LabelModal = styled(Box)(({ theme }) => ({
  width: 300,
  display: 'inline-block',
  textAlign: 'end',
  marginRight: theme.spacing(0.5),
}))

const ButtonModal = styled(Box)(({ theme }) => ({
  button: {
    fontSize: 20,
  },
  display: 'flex',
  justifyContent: 'end',
  margin: theme.spacing(5),
}))

const AccountManagerTitle = styled('h1')(({ theme }) => ({}))

export default AccountManager
