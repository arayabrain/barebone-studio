import { memo, useContext } from "react"

import TerminalIcon from "@mui/icons-material/Terminal"
import { IconButton, Tooltip } from "@mui/material"

import { DialogContext } from "components/Workspace/FlowChart/Dialog/DialogContext"

export const LogsButton = memo(function LogsButton() {
  const { onOpenLogs } = useContext(DialogContext)
  return (
    <Tooltip title="Logs">
      <IconButton onClick={() => onOpenLogs(true)} color={"primary"}>
        <TerminalIcon style={{ fontSize: 26 }} />
      </IconButton>
    </Tooltip>
  )
})
