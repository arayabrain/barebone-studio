import { stringify } from "qs"

import {
  AddUserDTO,
  UserDTO,
  ListUsersQueryDTO,
  UpdateUserDTO,
  UserListDTO,
} from "api/users/UsersApiDTO"
import axios from "utils/axios"

export const createUserApi = async (data: AddUserDTO): Promise<UserDTO> => {
  const response = await axios.post("/admin/users", data)
  return response.data
}

export const getUserApi = async (uid: string): Promise<UserDTO> => {
  const response = await axios.get(`/admin/users/${uid}`)
  return response.data
}

export const listUsersApi = async (
  data: ListUsersQueryDTO,
): Promise<UserListDTO> => {
  const paramsNew = stringify(data, { indices: false })
  const response = await axios.get(`/admin/users?${paramsNew}`)
  return response.data
}

export const updateUserApi = async (
  id: number,
  data: UpdateUserDTO,
): Promise<UserDTO> => {
  const response = await axios.put(`/admin/users/${id}`, data)
  return response.data
}

export const deleteUserApi = async (id: number): Promise<string> => {
  const response = await axios.delete(`/admin/users/${id}`)
  return response.data
}

export const getListUserSearchApi = async (data: {
  keyword: string | null
}): Promise<UserDTO[]> => {
  const response = await axios.get(
    `/users/search/share_users${
      data.keyword ? `?keyword=${data.keyword}` : ""
    }`,
  )
  return response.data
}

export const getListGroupSearchApi = async (data: {
  keyword: string | null
}): Promise<UserDTO[]> => {
  const response = await axios.get(
    `/group/search/share_groups${
      data.keyword ? `?keyword=${data.keyword}` : ""
    }`,
  )
  return response.data
}
