import { RootState } from "store/store"

export const selectHDF5 = (state: RootState) => {
  if (state.hdf5 != null) {
    return state.hdf5
  } else {
    return undefined
  }
}

export const selectHDF5Nodes = () => (state: RootState) =>
  selectHDF5(state)?.tree

export const selectHDF5IsLoading = () => (state: RootState) =>
  selectHDF5(state)?.isLoading ?? false
