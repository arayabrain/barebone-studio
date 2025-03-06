import { Dispatch, FC, SetStateAction, JSX, SyntheticEvent } from "react"

import { HelpOutline } from "@mui/icons-material"
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded"
import {
  Button,
  Dialog,
  DialogContent,
  DialogActions,
  DialogTitle,
  Grid,
} from "@mui/material"

export interface ConfirmDialogProps {
  open: boolean
  setOpen?: Dispatch<SetStateAction<boolean>>
  onCancel?: (
    event: SyntheticEvent | Event,
    reason?: "backdropClick" | "escapeKeyDown",
  ) => void
  onConfirm?: () => void
  title?: string
  cancelTitle?: string
  content: string | JSX.Element
  confirmLabel?: string
  iconType?: "warning" | "info"
  confirmButtonColor?:
    | "inherit"
    | "primary"
    | "secondary"
    | "success"
    | "error"
    | "info"
    | "warning"
}

export const ConfirmDialog: FC<ConfirmDialogProps> = ({
  open,
  setOpen,
  onCancel,
  onConfirm,
  title,
  cancelTitle,
  content,
  confirmLabel,
  iconType,
  confirmButtonColor = "primary",
}) => {
  const dataTestId = confirmLabel
    ? `${confirmLabel}-confirm-button`
    : "ok-button"

  const handleClose = (
    event: SyntheticEvent | Event,
    reason?: "backdropClick" | "escapeKeyDown",
  ) => {
    onCancel && onCancel(event, reason)
    setOpen && setOpen(false)
  }

  const handleConfirm = () => {
    onConfirm && onConfirm()
    setOpen && setOpen(false)
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      sx={{
        "& .MuiDialog-container": {
          "& .MuiPaper-root": {
            minWidth: "300px",
            wordWrap: "break-word",
          },
        },
      }}
    >
      {title && <DialogTitle>{title}</DialogTitle>}
      <DialogContent>
        {iconType ? (
          <DialogContentWithIcon content={content} iconType={iconType} />
        ) : (
          content
        )}
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={handleClose}>
          {cancelTitle ?? "cancel"}
        </Button>
        <Button
          variant="contained"
          onClick={handleConfirm}
          data-testid={dataTestId}
          color={confirmButtonColor}
        >
          {confirmLabel ?? "ok"}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

const DialogContentWithIcon: FC<
  Pick<ConfirmDialogProps, "content" | "iconType">
> = ({ content, iconType }) => {
  return (
    <Grid container alignItems="center">
      <Grid item xs={2} container justifyContent="center">
        {iconType === "warning" ? (
          <WarningAmberRoundedIcon color="warning" fontSize="large" />
        ) : (
          <HelpOutline color="info" fontSize="large" />
        )}
      </Grid>
      <Grid item xs={10}>
        {content}
      </Grid>
    </Grid>
  )
}
