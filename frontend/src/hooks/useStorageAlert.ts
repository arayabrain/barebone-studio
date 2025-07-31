import { useEffect, useState, useCallback } from "react"

import { useSnackbar } from "notistack"

import { getMyStorageAlertApi, StorageAlert } from "api/storage/StorageAlerts"

interface UseStorageAlertReturn {
  alert: StorageAlert | null
  hasAlert: boolean
  loading: boolean
  checkStorageAlert: () => Promise<void>
}

interface UseStorageAlertOptions {
  autoCheck?: boolean
  checkInterval?: number // in milliseconds
  showSnackbar?: boolean
}

export const useStorageAlert = (
  options: UseStorageAlertOptions = {},
): UseStorageAlertReturn => {
  const {
    autoCheck = true,
    checkInterval = 5 * 60 * 1000, // 5 minutes default
    showSnackbar = false,
  } = options

  const { enqueueSnackbar } = useSnackbar()
  const [alert, setAlert] = useState<StorageAlert | null>(null)
  const [loading, setLoading] = useState(false)

  const checkStorageAlert = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getMyStorageAlertApi()

      if (response.has_alert && response.alert) {
        const newAlert = response.alert

        // Show snackbar notification if this is a new alert or severity increased
        if (
          showSnackbar &&
          (!alert || newAlert.alert_level !== alert.alert_level)
        ) {
          const severity =
            newAlert.alert_level === "danger" ? "error" : "warning"
          enqueueSnackbar(newAlert.message, {
            variant: severity,
            autoHideDuration: newAlert.alert_level === "danger" ? 10000 : 6000,
          })
        }

        setAlert(newAlert)
      } else {
        setAlert(null)
      }
    } catch (error) {
      console.error("Failed to check storage alert:", error)
      // Silently fail to not disrupt user experience
    } finally {
      setLoading(false)
    }
  }, [alert, showSnackbar, enqueueSnackbar])

  useEffect(() => {
    if (autoCheck) {
      // Initial check
      checkStorageAlert()

      // Set up interval for periodic checks
      const interval = setInterval(checkStorageAlert, checkInterval)

      return () => clearInterval(interval)
    }
    return () => {}
  }, [autoCheck, checkInterval, checkStorageAlert])

  return {
    alert,
    hasAlert: Boolean(alert),
    loading,
    checkStorageAlert,
  }
}
