export function convertBytes(bytes: number) {
  if (!bytes) return bytes
  const KB = 1024
  const MB = KB * 1024
  const GB = MB * 1024
  const TB = GB * 1024

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

  return `${result.toFixed(2)} ${unit}`
}
