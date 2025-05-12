import { memo, useContext, useState } from "react"
import { useSelector, useDispatch } from "react-redux"

import { useSnackbar } from "notistack"

import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline"
import IconButton from "@mui/material/IconButton"

import DeleteConfirmModal from "components/common/DeleteConfirmModal"
import { ExperimentUidContext } from "components/Workspace/Experiment/ExperimentTable"
import { deleteExperimentByUid } from "store/slice/Experiments/ExperimentsActions"
import { selectExperimentName } from "store/slice/Experiments/ExperimentsSelectors"
import {
  selectPipelineLatestUid,
  selectPipelineIsStartedSuccess,
} from "store/slice/Pipeline/PipelineSelectors"
import { clearCurrentPipeline } from "store/slice/Pipeline/PipelineSlice"
import { AppDispatch, RootState } from "store/store"

export const DeleteButton = memo(function DeleteButton() {
  const dispatch = useDispatch<AppDispatch>()
  const currentPipelineUid = useSelector(selectPipelineLatestUid)
  const uid = useContext(ExperimentUidContext)
  const isRunning = useSelector((state: RootState) => {
    const currentUid = selectPipelineLatestUid(state)
    const isPending = selectPipelineIsStartedSuccess(state)
    return uid === currentUid && isPending
  })
  const name = useSelector(selectExperimentName(uid))
  const [open, setOpen] = useState(false)
  const { enqueueSnackbar } = useSnackbar()

  const openDialog = () => {
    setOpen(true)
  }
  const handleDelete = () => {
    setOpen(false)
    dispatch(deleteExperimentByUid(uid))
      .unwrap()
      .then(() => {
        // do nothing.
      })
      .catch(() => {
        enqueueSnackbar("Failed to delete", { variant: "error" })
      })
    uid === currentPipelineUid && dispatch(clearCurrentPipeline())
  }

  return (
    <>
      <IconButton
        onClick={openDialog}
        disabled={isRunning}
        color="error"
        data-testid="delete-button"
      >
        <DeleteOutlineIcon />
      </IconButton>
      <DeleteConfirmModal
        open={open}
        onClose={() => setOpen(false)}
        onSubmit={handleDelete}
        titleSubmit="Delete"
        description={`Do you want to delete ${name}? `}
        loading={false}
        iconType="warning"
      />
    </>
  )
})
