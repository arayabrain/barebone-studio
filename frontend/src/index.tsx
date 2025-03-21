import { Provider } from "react-redux"

import { createRoot } from "react-dom/client"

import "index.css"

import { ThemeProvider } from "@mui/material/styles"

import App from "App"
import reportWebVitals from "reportWebVitals"
import { store } from "store/store"
import { theme } from "Theme"

const root = createRoot(document.getElementById("root")!)

root.render(
  <Provider store={store}>
    <ThemeProvider theme={theme}>
      <App />
    </ThemeProvider>
  </Provider>,
)

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals()
