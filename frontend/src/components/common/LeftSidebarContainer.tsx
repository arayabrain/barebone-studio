import { FC, ReactNode } from "react"

import { Box } from "@mui/material"
import { grey } from "@mui/material/colors"

import { ResizableSidebar } from "components/common/ResizebleSidebar"
import { DRAWER_WIDTH, CONTENT_HEIGHT } from "const/Layout"

interface LeftSidebarContainerProps {
  children: ReactNode
}

export const LeftSidebarContainer: FC<LeftSidebarContainerProps> = ({
  children,
}) => {
  return (
    <Box
      minWidth={DRAWER_WIDTH}
      overflow="auto"
      marginRight={3}
      borderRight={1}
      borderColor={grey[300]}
      sx={{
        height: CONTENT_HEIGHT,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <ResizableSidebar>{children}</ResizableSidebar>
    </Box>
  )
}
