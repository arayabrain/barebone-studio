import {
  createContext,
  Dispatch,
  PropsWithChildren,
  SetStateAction,
  useContext,
  useState,
} from "react"

import { TDataFilterParam } from "store/slice/AlgorithmNode/AlgorithmNodeType"

const BoxFilterContext = createContext<{
  filterParam?: TDataFilterParam
  setFilterParam: Dispatch<SetStateAction<TDataFilterParam | undefined>>
  setRoiPath: Dispatch<SetStateAction<string>>
  roiPath: string
}>({
  filterParam: undefined,
  setFilterParam: () => null,
  roiPath: "",
  setRoiPath: () => null,
})

export const useBoxFilter = () => useContext(BoxFilterContext)

export const BoxFilterProvider = ({ children }: PropsWithChildren) => {
  const [filterParam, setFilterParam] = useState<TDataFilterParam>()
  const [roiPath, setRoiPath] = useState<string>("")

  return (
    <BoxFilterContext.Provider
      value={{ filterParam, setFilterParam, roiPath, setRoiPath }}
    >
      {children}
    </BoxFilterContext.Provider>
  )
}
