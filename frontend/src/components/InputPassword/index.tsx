import { Box, styled, Typography } from '@mui/material'
import { Input } from 'components/common/Input'
import { FC, useState } from 'react'
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff'
import VisibilityIcon from '@mui/icons-material/Visibility'

const style: object = {
  position: 'absolute',
  right: 5,
  top: 8,
  fontSize: 20,
  cursor: 'pointer',
  color: 'rgba(0,0,0,0.6)',
}

const InputPassword: FC<any> = (props) => {
  const [type, setType] = useState('password')

  const onShow = () => {
    setType('text')
  }

  const onHidden = () => {
    setType('password')
  }

  return (
    <Box sx={{ position: 'relative' }}>
      <Input {...props} type={type} />
      {type === 'password' ? (
        <VisibilityIcon style={style} onClick={onShow} />
      ) : (
        <VisibilityOffIcon style={style} onClick={onHidden} />
      )}
      <TextError>{props.error}</TextError>
    </Box>
  )
}

const TextError = styled(Typography)({
  fontSize: 12,
  minHeight: 18,
  color: 'red',
  lineHeight: '14px',
  marginTop: -14,
  wordBreak: 'break-word',
})

export default InputPassword