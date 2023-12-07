import { FC, SyntheticEvent } from "react"
import { useDispatch, useSelector } from "react-redux"

import Tab from "@mui/material/Tab"
import Tabs from "@mui/material/Tabs"

import { selectActiveTab } from "store/slice/Workspace/WorkspaceSelector"
import { setActiveTab } from "store/slice/Workspace/WorkspaceSlice"

const WorkspaceTabs: FC = () => {
  const dispatch = useDispatch()
  const activeTab = useSelector(selectActiveTab)
  const handleChange = (event: SyntheticEvent, newValue: number) => {
    dispatch(setActiveTab(newValue))
  }

  return (
    <Tabs
      sx={{ width: "100%" }}
      value={activeTab}
      onChange={handleChange}
      centered
      textColor="primary"
    >
      <Tab label="Workflow" {...a11yProps(0)} />
      <Tab label="Visualize" {...a11yProps(1)} />
      <Tab label="Records" {...a11yProps(2)} />
    </Tabs>
  )
}

function a11yProps(index: number | string) {
  return {
    id: `simple-tab-${index}`,
    "aria-controls": `simple-tabpanel-${index}`,
  }
}

export default WorkspaceTabs
