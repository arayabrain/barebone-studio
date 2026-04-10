import {
  createBatchStructuredFileNode,
  BatchFileNodeConfig,
} from "components/Workspace/FlowChart/FlowChartNode/BatchInputNode/BatchBaseStructuredFileNode"
import { FILE_TYPE_SET } from "config/fileTypes.config"
import { getHDF5Tree } from "store/slice/HDF5/HDF5Action"
import {
  selectHDF5IsLoading,
  selectHDF5Nodes,
} from "store/slice/HDF5/HDF5Selectors"
import {
  selectHdf5LikeInputNodeSelectedFilePath,
  selectInputNodeHDF5Path,
} from "store/slice/InputNode/InputNodeSelectors"
import { setInputNodeHDF5Path } from "store/slice/InputNode/InputNodeSlice"

const batchHdf5Config: BatchFileNodeConfig = {
  fileType: FILE_TYPE_SET.BATCH_HDF5,
  handleId: "hdf5",
  handleType: "HDF5Data",
  treeKeyPrefix: "hdf5tree",
  selectFilePath: selectHdf5LikeInputNodeSelectedFilePath,
  selectStructurePath: selectInputNodeHDF5Path,
  setStructurePath: setInputNodeHDF5Path,
  getTree: getHDF5Tree,
  selectTree: selectHDF5Nodes,
  selectIsLoading: selectHDF5IsLoading,
}

export const BatchHDF5FileNode = createBatchStructuredFileNode(batchHdf5Config)
