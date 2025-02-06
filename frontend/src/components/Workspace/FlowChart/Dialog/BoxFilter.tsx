import {
  ChangeEvent,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react"
import { shallowEqual, useDispatch, useSelector } from "react-redux"
import { useParams } from "react-router-dom"

import { enqueueSnackbar } from "notistack"

import styled from "@emotion/styled"
import { Box, Button, Input, InputProps } from "@mui/material"

import {
  DialogContext,
  useRoisSelected,
} from "components/Workspace/FlowChart/Dialog/DialogContext"
import { useBoxFilter } from "components/Workspace/FlowChart/Dialog/FilterContext"
import { STANDALONE_WORKSPACE_ID } from "const/Mode"
import { selectAlgorithmDataFilterParam } from "store/slice/AlgorithmNode/AlgorithmNodeSelectors"
import { TDim } from "store/slice/AlgorithmNode/AlgorithmNodeType"
import { runApplyFilter } from "store/slice/Pipeline/PipelineActions"
import { selectModeStandalone } from "store/slice/Standalone/StandaloneSeclector"
import { fetchWorkflow } from "store/slice/Workflow/WorkflowActions"
import { AppDispatch } from "store/store"

type InputDim = {
  title: string
  onChangeInput?: (value?: string) => void
  max?: number | null
  min?: number | null
  multiple?: boolean
} & InputProps

const InputDim = (props: InputDim) => {
  const { title, onChangeInput, max, multiple, min, ...p } = props
  const [value, setValue] = useState<string>(p.value as string)
  const [valuePassed, setValuePassed] = useState<string>(p.value as string)

  useEffect(() => {
    setValue(p.value as string)
    setValuePassed(p.value as string)
  }, [p.value])

  const validateValue = useCallback(
    (string: string, isBlur?: boolean) => {
      if (max) {
        return string
          .split(",")
          .map((e) => {
            const dims = e.split(":")
            if (!dims.filter(Boolean).length) return e
            const dim0 = dims[0]
            const dim1 = dims[1]
            if (max && dim0 && !dim1 && Number(dim0) >= max) {
              return `${max - 1}:`
            }
            if (min && dim0 && !dim1 && Number(dim0) <= min && isBlur)
              return `${min}:`
            if (dim0 && dim1) {
              let start = dim0
              if (max && Number(dim0) >= max) start = String(max - 1)
              else if (min && Number(dim0) <= min && isBlur) start = String(min)
              return `${start}:${Number(dim1) > max ? max : dim1}`
            }
            if (dim1 && !dim0 && isBlur) return `${min || 0}:${dim1}`
            if (isBlur && dim0 && !dim1) return `${dim0}:${max}`
            return e
          })
          .join(",")
      }
      return string
    },
    [max, min],
  )

  const onChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      let regex = /[^0-9,:]/g
      if (!multiple) regex = /[^0-9:]/g
      let value = event.target.value.replace(regex, "")
      let regexTest = /^(\d+:\d+)(,\d+:\d+)*$/
      if (!multiple) regexTest = /^(\d+:\d+)(\d+:\d+)*$/
      value = validateValue(value)
      if (regexTest.test(value) || !value) setValuePassed(value.trim())
      setValue(value.trim())
    },
    [multiple, validateValue],
  )

  const getError = useCallback(
    (string: string, stringPassed: string) => {
      if (string !== stringPassed) return "Invalid format"
      const values = stringPassed.split(",").filter(Boolean)
      if (values.length) {
        const errorEnd = values.find((v) => {
          const dim1 = v.split(":")[1]
          const dim0 = v.split(":")[0]
          return dim1 && Number(dim1) <= Number(dim0) ? dim0 : undefined
        })
        const errorStart = values.find((v) => {
          const dim0 = v.split(":")[0]
          return min && dim0 && Number(dim0) < Number(min) ? dim0 : undefined
        })
        if (errorStart) {
          return `The 'from' value must be <= ${min}`
        }
        if (errorEnd) {
          return `The 'to' value must be > ${errorEnd.split(":")[0]}`
        }
      }
      return null
    },
    [min],
  )

  const error = useMemo(
    () => getError(value, valuePassed),
    [getError, value, valuePassed],
  )

  const _onBlur = useCallback(() => {
    const newValue = validateValue(value, true)
    const isError = getError(newValue, newValue)
    if (isError && newValue) return
    setValue(newValue)
    setValuePassed(newValue)
    onChangeInput?.(newValue)
  }, [getError, onChangeInput, validateValue, value])

  return (
    <Box flex={1}>
      <Box mb={1}>{title}</Box>
      <InputStyled
        {...p}
        error={value !== valuePassed}
        value={value}
        onChange={onChange}
        onBlur={_onBlur}
        autoCapitalize="off"
        autoComplete="off"
      />
      <TextError>{error}</TextError>
    </Box>
  )
}

const InputStyled = styled(Input, {
  shouldForwardProp: (props) => props !== "error",
})<{ error?: boolean }>`
  input {
    text-align: center;
  }
  &::after {
    border-color: ${({ error }) => (error ? "#ff0000" : "#1976d2")};
  }
  margin-bottom: 2px;
  width: 100%;
`

const TextError = styled("div")`
  font-size: 12px;
  color: #ff0000;
  min-height: 15px;
`

const BoxFilter = ({ nodeId }: { nodeId: string }) => {
  const dispatch = useDispatch<AppDispatch>()
  const isStandalone = useSelector(selectModeStandalone)
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const _workspaceId = Number(workspaceId)

  const { onOpenFilterDialog } = useContext(DialogContext)
  const { maxDim, maxRoi } = useRoisSelected()
  const filterSelector = useSelector(
    selectAlgorithmDataFilterParam(nodeId),
    shallowEqual,
  )
  const { filterParam, setFilterParam } = useBoxFilter()

  const dataFilterParam = useMemo(() => {
    if (!filterParam) return undefined
    const { dim1, roi } = filterParam
    return { dim1: dim1?.filter(Boolean), roi: roi?.filter(Boolean) }
  }, [filterParam])

  const dimPlaceholder = useMemo(() => {
    const dims = filterSelector?.dim1
      ?.map((e) => [e.start, e.end].filter((e) => e || e === 0))
      ?.filter((e) => e.length)
    return dims?.map((e) => e.join(":"))?.toString()
  }, [filterSelector?.dim1])

  const roiPlaceholder = useMemo(() => {
    const rois = filterSelector?.roi
      ?.map((e) => [e.start, e.end].filter((e) => e || e === 0))
      ?.filter((e) => e.length)
    return rois?.map((e) => e.join(":"))?.toString()
    return 0
  }, [filterSelector?.roi])

  useEffect(() => {
    setFilterParam(filterSelector)
  }, [filterSelector, setFilterParam])

  const getData = useCallback(
    (value?: TDim[]) =>
      value
        ?.map((r) => {
          if (!isNaN(r.start!) && !isNaN(r.end!)) return `${r.start}:${r.end}`
          if (!isNaN(r.start!)) return r.start
          if (!isNaN(r.end!)) return r.end
          return ""
        })
        .toString(),
    [],
  )

  const { dim1, roi } = useMemo(() => {
    return {
      dim1: getData(dataFilterParam?.dim1),
      roi: getData(dataFilterParam?.roi),
    }
  }, [dataFilterParam, getData])

  const onChange = useCallback(
    (name: string, value?: string) => {
      const values = value?.split(",").map((v) => {
        if (!v) return ""
        const array = v.split(":")
        const dim: TDim = {}
        if (array[0]) dim.start = Number(array[0])
        if (array[1]) dim.end = Number(array[1])
        return dim
      })
      setFilterParam((pre) => ({ ...pre, [name]: values?.filter(Boolean) }))
    },
    [setFilterParam],
  )

  const isNotChange = useMemo(() => {
    return (
      !dim1?.length &&
      !roi?.length &&
      !filterSelector?.roi?.length &&
      !filterSelector?.dim1?.length
    )
  }, [
    dim1?.length,
    filterSelector?.dim1?.length,
    filterSelector?.roi?.length,
    roi?.length,
  ])

  const acceptFilter = useCallback(() => {
    onOpenFilterDialog("")
    if (isNotChange) return
    if (JSON.stringify(filterSelector) === JSON.stringify(filterParam)) {
      return
    }
    dispatch(runApplyFilter({ dataFilterParam, nodeId }))
      .unwrap()
      .then(() => {
        dispatch(
          fetchWorkflow(isStandalone ? STANDALONE_WORKSPACE_ID : _workspaceId),
        )
      })
      .catch(() => {
        enqueueSnackbar("Failed to Accept filter", { variant: "error" })
      })
  }, [
    dataFilterParam,
    dispatch,
    filterParam,
    filterSelector,
    isNotChange,
    isStandalone,
    nodeId,
    onOpenFilterDialog,
    _workspaceId,
  ])

  const resetFilter = useCallback(() => {
    onOpenFilterDialog("")
    dispatch(runApplyFilter({ dataFilterParam: undefined, nodeId }))
      .unwrap()
      .then(() => {
        dispatch(
          fetchWorkflow(isStandalone ? STANDALONE_WORKSPACE_ID : _workspaceId),
        )
      })
      .catch(() => {
        enqueueSnackbar("Failed to Reset filter", { variant: "error" })
      })
  }, [_workspaceId, dispatch, isStandalone, nodeId, onOpenFilterDialog])

  return (
    <Box display="flex" justifyContent="flex-end">
      <Box display="flex" alignItems="center" flexDirection="column">
        <Box display="flex" gap={2} textAlign="center" pt={2} width={500}>
          <InputDim
            title="ROI"
            name="roi"
            placeholder={roiPlaceholder || `0:${maxRoi}`}
            value={roi || ""}
            onChangeInput={(v) => onChange("roi", v)}
            multiple
            max={maxRoi}
          />
          <InputDim
            title="Time(Dim1)"
            name="dim1"
            placeholder={dimPlaceholder || `0:${maxDim}`}
            value={dim1 || ""}
            onChangeInput={(v) => onChange("dim1", v)}
            max={maxDim}
          />
        </Box>
        <Box mt={2} display="flex" gap={1}>
          <Button
            variant="outlined"
            size="small"
            style={{ width: 120 }}
            onClick={acceptFilter}
          >
            APPLY
          </Button>
          <Button
            color="error"
            variant="outlined"
            size="small"
            onClick={() => onOpenFilterDialog("")}
            style={{ width: 120 }}
          >
            CANCEL
          </Button>
          <Button
            variant="outlined"
            size="small"
            style={{ width: 120 }}
            onClick={resetFilter}
          >
            RESET
          </Button>
        </Box>
      </Box>
    </Box>
  )
}

export default BoxFilter
