import React, { useEffect, useState } from "react"

import { useSnackbar } from "notistack"

import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Storage as StorageIcon,
  Warning as WarningIcon,
} from "@mui/icons-material"
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  CircularProgress,
  Collapse,
  IconButton,
  LinearProgress,
  Typography,
} from "@mui/material"

import {
  getMyStorageAlertApi,
  getMyStorageUsageApi,
  refreshStorageUsageApi,
  StorageAlert as StorageAlertType,
  StorageUsage,
} from "api/storage/StorageAlerts"

interface StorageAlertProps {
  showUsageDetails?: boolean
  compact?: boolean
  onClose?: () => void
}

const StorageAlert: React.FC<StorageAlertProps> = ({
  showUsageDetails = false,
  compact = false,
  onClose,
}) => {
  const { enqueueSnackbar } = useSnackbar()
  const [alert, setAlert] = useState<StorageAlertType | null>(null)
  const [usage, setUsage] = useState<StorageUsage | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  const fetchStorageAlert = async () => {
    try {
      setLoading(true)
      const alertResponse = await getMyStorageAlertApi()

      if (alertResponse.has_alert && alertResponse.alert) {
        setAlert(alertResponse.alert)
      } else {
        setAlert(null)
      }

      if (showUsageDetails) {
        const usageResponse = await getMyStorageUsageApi()
        setUsage(usageResponse)
      }
    } catch (error) {
      console.error("Failed to fetch storage alert:", error)
      // Silently fail for storage alerts to not disrupt the main UI
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    try {
      setRefreshing(true)
      await refreshStorageUsageApi()
      await fetchStorageAlert()
      enqueueSnackbar("Storage usage refreshed", { variant: "success" })
    } catch (error) {
      console.error("Failed to refresh storage:", error)
      enqueueSnackbar("Failed to refresh storage usage", { variant: "error" })
    } finally {
      setRefreshing(false)
    }
  }

  const handleDismiss = () => {
    setDismissed(true)
    onClose?.()
  }

  useEffect(() => {
    fetchStorageAlert()
  }, [showUsageDetails])

  if (loading) {
    return compact ? null : (
      <Box display="flex" alignItems="center" gap={1} p={1}>
        <CircularProgress size={16} />
        <Typography variant="caption">Checking storage...</Typography>
      </Box>
    )
  }

  if (dismissed || (!alert && !showUsageDetails)) {
    return null
  }

  const getSeverity = (alertLevel: string) => {
    switch (alertLevel) {
      case "danger":
        return "error"
      case "critical":
        return "error"
      case "warning":
        return "warning"
      default:
        return "info"
    }
  }

  const getProgressColor = (percentage: number) => {
    if (percentage >= 100) return "error"
    if (percentage >= 90) return "warning"
    return "primary"
  }

  if (compact && alert) {
    return (
      <Collapse in={!dismissed}>
        <Alert
          severity={getSeverity(alert.alert_level)}
          action={
            <Box display="flex" alignItems="center" gap={0.5}>
              <IconButton
                size="small"
                onClick={handleRefresh}
                disabled={refreshing}
              >
                {refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
              </IconButton>
              <IconButton size="small" onClick={handleDismiss}>
                <CloseIcon />
              </IconButton>
            </Box>
          }
        >
          <AlertTitle>
            <Box display="flex" alignItems="center" gap={1}>
              <StorageIcon fontSize="small" />
              Storage{" "}
              {alert.alert_level === "danger" ? "Quota Exceeded" : "Alert"}
            </Box>
          </AlertTitle>
          {alert.message}
        </Alert>
      </Collapse>
    )
  }

  return (
    <Box>
      {alert && (
        <Collapse in={!dismissed}>
          <Alert
            severity={getSeverity(alert.alert_level)}
            action={
              <IconButton size="small" onClick={handleDismiss}>
                <CloseIcon />
              </IconButton>
            }
            sx={{ mb: 2 }}
          >
            <AlertTitle>
              <Box display="flex" alignItems="center" gap={1}>
                <StorageIcon />
                Storage{" "}
                {alert.alert_level === "danger" ? "Quota Exceeded" : "Alert"}
              </Box>
            </AlertTitle>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {alert.message}
            </Typography>

            <Box display="flex" alignItems="center" gap={2} mt={1}>
              <LinearProgress
                variant="determinate"
                value={Math.min(alert.usage_percentage, 100)}
                color={getProgressColor(alert.usage_percentage)}
                sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
              />
              <Typography variant="caption" fontWeight="bold">
                {alert.usage_percentage.toFixed(1)}%
              </Typography>
            </Box>

            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              mt={1}
            >
              <Typography variant="caption" color="text.secondary">
                {alert.usage_bytes > 0
                  ? `${(alert.usage_bytes / (1024 * 1024 * 1024)).toFixed(2)} GB used of ${(alert.quota_bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
                  : "Calculating usage..."}
              </Typography>
              <Button
                size="small"
                startIcon={
                  refreshing ? <CircularProgress size={16} /> : <RefreshIcon />
                }
                onClick={handleRefresh}
                disabled={refreshing}
              >
                Refresh
              </Button>
            </Box>
          </Alert>
        </Collapse>
      )}

      {showUsageDetails && usage && (
        <Box
          sx={{
            border: 1,
            borderColor: "divider",
            borderRadius: 1,
            p: 2,
            mt: alert ? 0 : 2,
          }}
        >
          <Box
            display="flex"
            alignItems="center"
            justifyContent="space-between"
            mb={2}
          >
            <Typography variant="h6" display="flex" alignItems="center" gap={1}>
              <StorageIcon />
              Storage Usage
            </Typography>
            <Button
              size="small"
              startIcon={
                refreshing ? <CircularProgress size={16} /> : <RefreshIcon />
              }
              onClick={handleRefresh}
              disabled={refreshing}
            >
              Refresh
            </Button>
          </Box>

          {usage.quota_bytes ? (
            <>
              <Box display="flex" alignItems="center" gap={2} mb={2}>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(usage.usage_percentage || 0, 100)}
                  color={getProgressColor(usage.usage_percentage || 0)}
                  sx={{ flexGrow: 1, height: 12, borderRadius: 6 }}
                />
                <Typography variant="body2" fontWeight="bold" minWidth="60px">
                  {usage.usage_percentage?.toFixed(1) || "0.0"}%
                </Typography>
              </Box>

              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2" color="text.secondary">
                  Used: {usage.usage_formatted}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Total: {usage.quota_formatted}
                </Typography>
              </Box>

              {usage.alert_level && (
                <Box display="flex" alignItems="center" gap={1} mt={2}>
                  <WarningIcon
                    color={usage.alert_level === "danger" ? "error" : "warning"}
                    fontSize="small"
                  />
                  <Typography
                    variant="caption"
                    color={usage.alert_level === "danger" ? "error" : "warning"}
                  >
                    Storage usage is{" "}
                    {usage.alert_level === "danger" ? "over quota" : "high"}
                  </Typography>
                </Box>
              )}
            </>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {usage.usage_formatted} used (no quota limit set)
            </Typography>
          )}
        </Box>
      )}
    </Box>
  )
}

export default StorageAlert
