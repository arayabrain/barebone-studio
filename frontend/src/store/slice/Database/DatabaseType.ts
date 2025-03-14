export const DATABASE_SLICE_NAME = "database"

export type OrderBy = "ASC" | "DESC" | ""

export type ImageUrls = {
  urls: string[]
  thumb_urls: string[]
  params: object
}

export type DatabaseType = {
  id: number
  fields: {
    brain_area?: string
    promoter?: string
    indicator?: string
    imaging_depth?: number
  }
  experiment_id?: string
  attributes?: object
  cell_image_urls: ImageUrls[]
  cell_image_url?: ImageUrls
  statistics?: {
    p_value_resp?: string
    p_value_sel?: string
    p_value_ori_resp?: string
    p_value_ori_sel?: string
    dir_vector_angle?: string
    ori_vector_angle?: string
    oi?: string
    di?: string
    dsi?: string
    osi?: string
    r_best_dir?: string
    dir_tuning_width?: string
    ori_tuning_width?: string
    sf_bandwidth?: string
    best_sf?: string
    sf_si?: string
  }
  graph_urls: ImageUrls[]
  share_type?: number
  publish_status?: number
  created_at: string
  updated_at: string
}

export type DatabaseDTO = {
  offset: number
  limit: number
  total: number
  header: {
    graph_titles: string[]
  }
  items: DatabaseType[]
}

export type ListShareDTO = {
  share_type: number
  users: ListShareUser[]
  groups: ListShareGroup[]
}

export type ListShareUser = {
  id: number
  name: string
  email: string
  created_at: string
  updated_at: string
}

export type ListShareGroup = {
  id: number
  name: string
  users_count: number
}

export type MultiShareType = {
  ids: number[]
  data: {
    share_type: number
    user_ids: number[]
    group_ids: number[]
  }
}

export type DatabaseParams = {
  [key: string]: number | string | string[] | undefined
}

export type FilterParams = {
  brain_areas: string[]
  imaging_depths: string[]
  promoters: string[]
  indicators: string[]
}
