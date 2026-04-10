import {
  createBatchStructuredFileNode,
  BatchFileNodeConfig,
} from "components/Workspace/FlowChart/FlowChartNode/BatchInputNode/BatchBaseStructuredFileNode"
import { FILE_TYPE_SET } from "config/fileTypes.config"
import {
  selectInputNodeMatlabPath,
  selectMatlabLikeInputNodeSelectedFilePath,
} from "store/slice/InputNode/InputNodeSelectors"
import { setInputNodeMatlabPath } from "store/slice/InputNode/InputNodeSlice"
import { getMatlabTree } from "store/slice/Matlab/MatlabAction"
import {
  selectMatlabIsLoading,
  selectMatlabNodes,
} from "store/slice/Matlab/MatlabSelectors"

const batchMatlabConfig: BatchFileNodeConfig = {
  fileType: FILE_TYPE_SET.BATCH_MATLAB,
  handleId: "matlab",
  handleType: "MatlabData",
  treeKeyPrefix: "matlabtree",
  selectFilePath: selectMatlabLikeInputNodeSelectedFilePath,
  selectStructurePath: selectInputNodeMatlabPath,
  setStructurePath: setInputNodeMatlabPath,
  getTree: getMatlabTree,
  selectTree: selectMatlabNodes,
  selectIsLoading: selectMatlabIsLoading,
}

export const BatchMatlabFileNode =
  createBatchStructuredFileNode(batchMatlabConfig)
