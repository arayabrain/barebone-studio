import { FC, ReactNode } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { Box, Button, styled } from "@mui/material"

const DatabaseWrapper: FC<{ children: ReactNode }> = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const handleClickExperiments = () => {
    navigate("/console/experiments")
  }
  const handleClickCells = () => {
    navigate("/console/cells")
  }

  return (
    <>
      <Box
        sx={{
          paddingTop: 2,
          paddingBottom: 5,
        }}
      >
        <Box>
          <NavButton
            variant="text"
            onClick={handleClickExperiments}
            disabled={location.pathname === "/console/experiments"}
          >
            Experiments
          </NavButton>
          /
          <NavButton
            variant="text"
            onClick={handleClickCells}
            disabled={location.pathname === "/console/cells"}
          >
            Cells
          </NavButton>
        </Box>
        <DataBaseContent>{children}</DataBaseContent>
      </Box>
    </>
  )
}

const NavButton = styled(Button)(({ theme }) => ({
  "&.Mui-disabled": {
    color: theme.palette.info.dark,
    fontWeight: "bold",
  },
}))

const DataBaseContent = styled(Box)(() => ({
  width: "94vw",
  margin: "auto",
  marginTop: 15,
}))

export default DatabaseWrapper
