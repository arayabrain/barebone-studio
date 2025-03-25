import { FC, ReactNode, useEffect } from "react"
import { useSelector, useDispatch } from "react-redux"

import { Box } from "@mui/material"
import { styled } from "@mui/material/styles"

import Experiment from "components/Workspace/Experiment/Experiment"
import FlowChart from "components/Workspace/FlowChart/FlowChart"
import Visualize from "components/Workspace/Visualize/Visualize"
import { getExperiments } from "store/slice/Experiments/ExperimentsActions"
import { selectExperiments } from "store/slice/Experiments/ExperimentsSelectors"
import { useRunPipeline } from "store/slice/Pipeline/PipelineHook"
import {
  selectActiveTab,
  selectCurrentWorkspaceId,
} from "store/slice/Workspace/WorkspaceSelector"
import { AppDispatch } from "store/store"

const Workspace: FC = () => {
  const runPipeline = useRunPipeline() // タブ切り替えによって結果取得処理が止まってしまうのを回避するため、タブの親レイヤーで呼び出している
  const activeTab = useSelector(selectActiveTab)
  const dispatch = useDispatch<AppDispatch>()

  const workspaceId = useSelector(selectCurrentWorkspaceId)
  const experiments = useSelector(selectExperiments)

  useEffect(() => {
    if (!activeTab && workspaceId && experiments?.status !== "fulfilled") {
      dispatch(getExperiments())
    }
  }, [dispatch, activeTab, workspaceId, experiments?.status])

  return (
    <RootDiv>
      <TabPanel value={activeTab} index={0}>
        <FlowChart {...runPipeline} />
      </TabPanel>
      <TabPanel value={activeTab} index={1}>
        <Visualize />
      </TabPanel>
      <TabPanel value={activeTab} index={2}>
        <Experiment />
      </TabPanel>
    </RootDiv>
  )
}

const RootDiv = styled("div")(({ theme }) => ({
  flexGrow: 1,
  backgroundColor: theme.palette.background.paper,
  height: "100%",
}))

interface TabPanelProps {
  children?: ReactNode
  index: number
  value: number
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props

  return (
    <div
      style={{ height: "calc(100% - 58px)" }}
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ height: "100%" }}>{children}</Box>}
    </div>
  )
}

export default Workspace
