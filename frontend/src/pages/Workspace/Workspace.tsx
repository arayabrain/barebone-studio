import React from "react"
import { useSelector } from "react-redux"

import { Box } from "@mui/material"
import { styled } from "@mui/material/styles"

import Experiment from "components/Workspace/Experiment/Experiment"
import FlowChart from "components/Workspace/FlowChart/FlowChart"
import Visualize from "components/Workspace/Visualize/Visualize"
import { useRunPipeline } from "store/slice/Pipeline/PipelineHook"
import { selectActiveTab } from "store/slice/Workspace/WorkspaceSelector"

const Workspace: React.FC = () => {
  const runPipeline = useRunPipeline() // タブ切り替えによって結果取得処理が止まってしまうのを回避するため、タブの親レイヤーで呼び出している
  const activeTab = useSelector(selectActiveTab)

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
  children?: React.ReactNode
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
