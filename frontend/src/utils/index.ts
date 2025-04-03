export function convertBytes(bytes: number) {
  if (!bytes) return ""
  const KB = 1000
  const MB = KB * 1000
  const GB = MB * 1000
  const TB = GB * 1000

  let result = bytes
  let unit = "Bytes"

  if (bytes >= TB) {
    result = bytes / TB
    unit = "TB"
  } else if (bytes >= GB) {
    result = bytes / GB
    unit = "GB"
  } else if (bytes >= MB) {
    result = bytes / MB
    unit = "MB"
  } else if (bytes >= KB) {
    result = bytes / KB
    unit = "KB"
  }
  if (bytes < GB) return `${Math.floor(result)} ${unit}`
  return `${Number(result.toFixed(2))} ${unit}`
}
