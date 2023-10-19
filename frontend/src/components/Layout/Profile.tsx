import { FC, useState, MouseEvent } from "react"
import { useDispatch } from "react-redux"
import { useNavigate } from "react-router-dom"

import AccountCircleIcon from "@mui/icons-material/AccountCircle"
import Logout from "@mui/icons-material/Logout"
import PortraitIcon from "@mui/icons-material/Portrait"
import { Menu, MenuItem } from "@mui/material"
import IconButton from "@mui/material/IconButton"


import { logout } from "store/slice/User/UserSlice"

const Profile: FC = () => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const handleMenu = (event: MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleCloseMenu = () => {
    setAnchorEl(null)
  }

  const onClickLogout = () => {
    setAnchorEl(null)
    dispatch(logout())
    navigate("/login")
  }

  const onClickAccount = () => {
    setAnchorEl(null)
    navigate("/console/account")
  }

  return (
    <>
      <IconButton
        color="inherit"
        aria-label="open profile menu"
        aria-haspopup="true"
        onClick={handleMenu}
      >
        <AccountCircleIcon />
      </IconButton>
      <Menu
        id="profile-menu"
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
        keepMounted
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
        open={Boolean(anchorEl)}
        onClose={handleCloseMenu}
      >
        <MenuItem onClick={onClickAccount}>
          <PortraitIcon /> Account Profile
        </MenuItem>
        <MenuItem onClick={onClickLogout}>
          <Logout />
          SIGN OUT
        </MenuItem>
      </Menu>
    </>
  )
}

export default Profile
