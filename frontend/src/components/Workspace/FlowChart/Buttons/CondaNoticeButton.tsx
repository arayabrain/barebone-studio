import { memo, useState } from "react"
import { useDispatch, useSelector } from "react-redux"

import { enqueueSnackbar } from "notistack"

import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined"
import { Typography } from "@mui/material"
import IconButton from "@mui/material/IconButton"

import { ConfirmDialog } from "components/common/ConfirmDialog"
import { getExperiments } from "store/slice/Experiments/ExperimentsActions"
import { run } from "store/slice/Pipeline/PipelineActions"
import { useIsRunDisabled } from "store/slice/Pipeline/PipelineHook"
import { selectRunPostData } from "store/slice/Run/RunSelectors"
import { reset } from "store/slice/VisualizeItem/VisualizeItemSlice"
import {
  importSampleData,
  reproduceWorkflow,
} from "store/slice/Workflow/WorkflowActions"
import { selectCurrentWorkspaceId } from "store/slice/Workspace/WorkspaceSelector"
import { AppDispatch, store } from "store/store"

interface CondaNoticeButtonProps {
  name: string
  condaName: string
}

export const CondaNoticeButton = memo(function CondaNoticeButton({
  name,
  condaName,
}: CondaNoticeButtonProps) {
  const [open, setOpen] = useState(false)
  const openDialog = () => {
    setOpen(true)
  }

  const dispatch = useDispatch<AppDispatch>()
  const workspaceId = useSelector(selectCurrentWorkspaceId) || -1
  const category = "maintenance"

  const runDisabled = useIsRunDisabled()

  const handleOk = async (condaName: string) => {
    // Import create-conda-env workflow
    await dispatch(importSampleData({ workspaceId, category }))
      .unwrap()
      .then(() => {
        // *Here, success snackbar display is off.
        dispatch(reset())
        dispatch(getExperiments())
      })
      .catch(() => {
        enqueueSnackbar("Failed to import import", { variant: "error" })
        return // break on error
      })

    // Reproduce create-conda-env workflow
    const uid = `setup_conda_${condaName}`
    await dispatch(reproduceWorkflow({ workspaceId, uid }))
      .unwrap()
      .then(() => {
        // *Here, success snackbar display is off.
        dispatch(reset())
      })
      .catch(() => {
        enqueueSnackbar("Failed to reproduce", { variant: "error" })
        return // break on error
      })

    // RUN reproduced workflow.
    // * Simulate RunButtons.handleClick (call PipelineHook.useRunPipeline.handleRunPipeline)
    const runPostData = selectRunPostData(store.getState())
    await dispatch(
      run({ runPostData: { name, ...runPostData, forceRunList: [] } }),
    )
      .unwrap()
      .catch(() => {
        enqueueSnackbar("Failed to Run workflow", { variant: "error" })
      })
  }

  return (
    <>
      <IconButton
        style={{ padding: 2 }}
        color="warning"
        size="small"
        disabled={runDisabled}
        onClick={openDialog}
      >
        <InfoOutlinedIcon />
      </IconButton>
      <Typography
        variant="inherit"
        style={{
          textOverflow: "ellipsis",
          overflow: "visible",
          width: "8rem",
          display: "inline-block",
        }}
      >
        {name}
      </Typography>

      <ConfirmDialog
        open={open}
        setOpen={setOpen}
        onConfirm={() => handleOk(condaName)}
        title="Conda Environment Verification"
        content={
          <>
            <p>
              Conda environment <strong>&quot;{condaName}&quot;</strong> does
              not exist. Create an environment?
            </p>
            <p style={{ display: "flex", alignItems: "center" }}>
              <InfoOutlinedIcon
                style={{
                  marginRight: 8,
                }}
                color="info"
                fontSize="medium"
              />
              Start Conda environment creation workflow. Current workflow will
              be cleared.
            </p>
          </>
        }
        confirmLabel="Start Create"
        iconType="info"
      />
    </>
  )
})
