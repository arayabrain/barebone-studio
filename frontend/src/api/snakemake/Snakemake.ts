import { BASE_URL } from "const/API"
import axios from "utils/axios"
import { ParamDTO } from "utils/param/ParamType"

export async function getSnakemakeParamsApi(): Promise<ParamDTO> {
  const response = await axios.get(`${BASE_URL}/snakemake`)
  return response.data
}
