import { memo, SyntheticEvent, useState, useCallback } from "react"
import { useDispatch, useSelector } from "react-redux"

import { enqueueSnackbar } from "notistack"

import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined"
import { Typography } from "@mui/material"
import IconButton from "@mui/material/IconButton"
import Tooltip from "@mui/material/Tooltip"

import { ConfirmDialog } from "components/common/ConfirmDialog"
import { AlgorithmChild } from "store/slice/AlgorithmList/AlgorithmListType"
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
  node: AlgorithmChild
  onSkipClick: (
    event: SyntheticEvent | Event,
    reason?: "backdropClick" | "escapeKeyDown",
  ) => void
}

export const CondaNoticeButton = memo(function CondaNoticeButton({
  name,
  node,
  onSkipClick,
}: CondaNoticeButtonProps) {
  const condaName = node.condaName

  const [open, setOpen] = useState(false)

  const openDialog = useCallback(() => {
    setOpen(true)
  }, [])

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
    const newName = `setup_conda_${condaName}`
    const runPostData = selectRunPostData(store.getState())
    await dispatch(
      run({ runPostData: { name: newName, ...runPostData, forceRunList: [] } }),
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
        color="default"
        size="small"
        disabled={runDisabled}
        onClick={openDialog}
      >
        <InfoOutlinedIcon />
      </IconButton>
      <Tooltip title={name} placement="right-start">
        <Typography
          variant="inherit"
          style={{
            display: "inline-block",
          }}
        >
          {name}
        </Typography>
      </Tooltip>

      <ConfirmDialog
        open={open}
        setOpen={setOpen}
        onCancel={onSkipClick}
        onConfirm={() => handleOk(condaName)}
        cancelTitle="Skip"
        title="Conda Environment Verification"
        content={
          <>
            <p>
              Conda environment <strong>&quot;{condaName}&quot;</strong> not
              found.
            </p>

            <p style={{ display: "flex", alignItems: "center" }}>
              <InfoOutlinedIcon
                style={{
                  marginRight: 8,
                }}
                color="info"
                fontSize="small"
              />
              Create environment beforehand for easier troubleshooting, or skip
              to auto-create environment using RUN.
            </p>
            <p style={{ display: "flex", alignItems: "center" }}>
              <InfoOutlinedIcon
                style={{
                  marginRight: 8,
                }}
                color="info"
                fontSize="small"
              />
              Creating now will clear the current workflow.
            </p>
          </>
        }
        confirmLabel="Create env"
        iconType="info"
      />
    </>
  )
})
