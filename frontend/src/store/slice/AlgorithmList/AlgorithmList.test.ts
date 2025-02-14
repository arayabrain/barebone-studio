import { expect, describe, test } from "@jest/globals"

import { getAlgoList } from "store/slice/AlgorithmList/AlgorithmListActions"
import reducer, {
  initialState,
} from "store/slice/AlgorithmList/AlgorithmListSlice"
import { AlgorithmListType } from "store/slice/AlgorithmList/AlgorithmListType"

describe("getAlgoList", () => {
  test(getAlgoList.fulfilled.type, () => {
    expect(
      reducer(initialState, {
        type: getAlgoList.fulfilled.type,
        payload: mockPayload,
        meta: {
          requestId: "jch5KyN83_x3ZtGQssSnJ",
          requestStatus: "fulfilled",
        },
      }),
    ).toEqual(expectState)
  })
  const mockPayload = {
    caiman: {
      children: {
        caiman_mc: {
          args: [{ name: "image", type: "ImageData", isNone: false }],
          returns: [{ name: "mc_images", type: "ImageData" }],
          parameter: "caiman_mc.yaml",
          path: "caiman/caiman_mc",
          conda_name: "caiman",
          conda_env_exists: true,
        },
        caiman_cnmf: {
          args: [{ name: "images", type: "ImageData", isNone: false }],
          returns: [
            { name: "fluorescence", type: "FluoData" },
            { name: "iscell", type: "IscellData" },
          ],
          parameter: "caiman_cnmf.yaml",
          path: "caiman/caiman_cnmf",
          conda_name: "caiman",
          conda_env_exists: true,
        },
      },
    },
    suite2p: {
      children: {
        suite2p_file_convert: {
          args: [{ name: "image", type: "ImageData", isNone: false }],
          returns: [{ name: "ops", type: "Suite2pData" }],
          parameter: null,
          path: "suite2p/suite2p_file_convert",
          conda_name: "suite2p",
          conda_env_exists: true,
        },
        suite2p_registration: {
          args: [{ name: "ops", type: "Suite2pData", isNone: false }],
          returns: [{ name: "ops", type: "Suite2pData" }],
          parameter: null,
          path: "suite2p/suite2p_registration",
          conda_name: "suite2p",
          conda_env_exists: true,
        },
        suite2p_roi: {
          args: [{ name: "ops", type: "Suite2pData", isNone: false }],
          returns: [
            { name: "ops", type: "Suite2pData" },
            { name: "fluorescence", type: "FluoData" },
            { name: "iscell", type: "IscellData" },
          ],
          parameter: null,
          path: "suite2p/suite2p_roi",
          conda_name: "suite2p",
          conda_env_exists: true,
        },
        suite2p_spike_deconv: {
          args: [{ name: "ops", type: "Suite2pData", isNone: false }],
          returns: [
            { name: "ops", type: "Suite2pData" },
            { name: "spks", type: "FluoData" },
          ],
          parameter: null,
          path: "suite2p/suite2p_spike_deconv",
          conda_name: "suite2p",
          conda_env_exists: true,
        },
      },
    },
    dummy: {
      children: {
        dummy_image2image: {
          args: [{ name: "image", type: "ImageData", isNone: false }],
          returns: [{ name: "image2image", type: "ImageData" }],
          parameter: null,
          path: "dummy/dummy_image2image",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2time: {
          args: [{ name: "image", type: "ImageData", isNone: false }],
          returns: [{ name: "image2time", type: "TimeSeriesData" }],
          parameter: null,
          path: "dummy/dummy_image2time",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2heat: {
          args: [{ name: "image", type: "ImageData", isNone: false }],
          returns: [{ name: "image2heat", type: "HeatMapData" }],
          parameter: null,
          path: "dummy/dummy_image2heat",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_time2time: {
          args: [{ name: "timeseries", type: "TimeSeriesData", isNone: false }],
          returns: [{ name: "time2time", type: "TimeSeriesData" }],
          parameter: null,
          path: "dummy/dummy_time2time",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2image8time: {
          args: [{ name: "image1", type: "ImageData", isNone: false }],
          returns: [
            { name: "image", type: "ImageData" },
            { name: "timeseries", type: "TimeSeriesData" },
          ],
          parameter: null,
          path: "dummy/dummy_image2image8time",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_keyerror: {
          args: [{ name: "image", type: "ImageData", isNone: false }],
          returns: [],
          parameter: null,
          path: "dummy/dummy_keyerror",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_typeerror: {
          args: [{ name: "image", type: "str", isNone: false }],
          returns: [],
          parameter: null,
          path: "dummy/dummy_typeerror",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2time8iscell: {
          args: [{ name: "image1", type: "ImageData", isNone: false }],
          returns: [
            { name: "timeseries", type: "TimeSeriesData" },
            { name: "iscell", type: "IscellData" },
          ],
          parameter: null,
          path: "dummy/dummy_image2time8iscell",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2roi: {
          args: [{ name: "image1", type: "ImageData", isNone: false }],
          returns: [{ name: "roi", type: "RoiData" }],
          parameter: null,
          path: "dummy/dummy_image2roi",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2image8roi: {
          args: [{ name: "image1", type: "ImageData", isNone: false }],
          returns: [
            { name: "image", type: "ImageData" },
            { name: "roi", type: "RoiData" },
          ],
          parameter: null,
          path: "dummy/dummy_image2image8roi",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2image8roi8time8heat: {
          args: [{ name: "image1", type: "ImageData", isNone: false }],
          returns: [
            { name: "image", type: "ImageData" },
            { name: "roi", type: "RoiData" },
            { name: "timeseries", type: "TimeSeriesData" },
            { name: "heat", type: "HeatMapData" },
          ],
          parameter: null,
          path: "dummy/dummy_image2image8roi8time8heat",
          conda_name: "dummy",
          conda_env_exists: true,
        },
        dummy_image2scatter: {
          args: [{ name: "image", type: "ImageData", isNone: false }],
          returns: [{ name: "scatter", type: "ScatterData" }],
          parameter: null,
          path: "dummy/dummy_image2scatter",
          conda_name: "dummy",
          conda_env_exists: true,
        },
      },
    },
    optinist: {
      children: {
        basic_neural_analysis: {
          children: {
            eta: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                {
                  name: "behaviors_data",
                  type: "BehaviorData",
                  isNone: false,
                },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [{ name: "mean", type: "TimeSeriesData" }],
              parameter: null,
              path: "optinist/basic_neural_analysis/eta",
              conda_name: "optinist",
              conda_env_exists: true,
            },
            cell_grouping: {
              args: [
                {
                  name: "neural_data",
                  type: "TimeSeriesData",
                  isNone: false,
                },
              ],
              returns: [],
              parameter: null,
              path: "optinist/basic_neural_analysis/cell_grouping",
              conda_name: "optinist",
              conda_env_exists: true,
            },
          },
        },
        dimension_reduction: {
          children: {
            cca: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                {
                  name: "behaviors_data",
                  type: "BehaviorData",
                  isNone: false,
                },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/dimension_reduction/cca",
              conda_name: "optinist",
              conda_env_exists: true,
            },
            pca: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/dimension_reduction/pca",
              conda_name: "optinist",
              conda_env_exists: true,
            },
            tsne: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/dimension_reduction/tsne",
              conda_name: "optinist",
              conda_env_exists: true,
            },
          },
        },
        neural_population_analysis: {
          children: {
            correlation: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/neural_population_analysis/correlation",
              conda_name: "optinist",
              conda_env_exists: true,
            },
            cross_correlation: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/neural_population_analysis/cross_correlation",
              conda_name: "optinist",
              conda_env_exists: true,
            },
            granger: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/neural_population_analysis/granger",
              conda_name: "optinist",
              conda_env_exists: true,
            },
          },
        },
        neural_decoding: {
          children: {
            glm: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                {
                  name: "behaviors_data",
                  type: "BehaviorData",
                  isNone: false,
                },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/neural_decoding/glm",
              conda_name: "optinist",
              conda_env_exists: true,
            },
            lda: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                {
                  name: "behaviors_data",
                  type: "BehaviorData",
                  isNone: false,
                },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/neural_decoding/lda",
              conda_name: "optinist",
              conda_env_exists: true,
            },
            svm: {
              args: [
                { name: "neural_data", type: "FluoData", isNone: false },
                {
                  name: "behaviors_data",
                  type: "BehaviorData",
                  isNone: false,
                },
                { name: "iscell", type: "IscellData", isNone: true },
              ],
              returns: [],
              parameter: null,
              path: "optinist/neural_decoding/svm",
              conda_name: "optinist",
              conda_env_exists: true,
            },
          },
        },
      },
    },
  }
  const expectState: AlgorithmListType = {
    isLatest: true,
    tree: {
      caiman: {
        type: "parent",
        children: {
          caiman_mc: {
            type: "child",
            functionPath: "caiman/caiman_mc",
            args: [{ name: "image", type: "ImageData", isNone: false }],
            returns: [{ name: "mc_images", type: "ImageData" }],
            condaName: "caiman",
            condaEnvExists: true,
          },
          caiman_cnmf: {
            type: "child",
            functionPath: "caiman/caiman_cnmf",
            args: [{ name: "images", type: "ImageData", isNone: false }],
            returns: [
              { name: "fluorescence", type: "FluoData" },
              { name: "iscell", type: "IscellData" },
            ],
            condaName: "caiman",
            condaEnvExists: true,
          },
        },
      },
      suite2p: {
        type: "parent",
        children: {
          suite2p_file_convert: {
            type: "child",
            functionPath: "suite2p/suite2p_file_convert",
            args: [{ name: "image", type: "ImageData", isNone: false }],
            returns: [{ name: "ops", type: "Suite2pData" }],
            condaName: "suite2p",
            condaEnvExists: true,
          },
          suite2p_registration: {
            type: "child",
            functionPath: "suite2p/suite2p_registration",
            args: [{ name: "ops", type: "Suite2pData", isNone: false }],
            returns: [{ name: "ops", type: "Suite2pData" }],
            condaName: "suite2p",
            condaEnvExists: true,
          },
          suite2p_roi: {
            type: "child",
            functionPath: "suite2p/suite2p_roi",
            args: [{ name: "ops", type: "Suite2pData", isNone: false }],
            returns: [
              { name: "ops", type: "Suite2pData" },
              { name: "fluorescence", type: "FluoData" },
              { name: "iscell", type: "IscellData" },
            ],
            condaName: "suite2p",
            condaEnvExists: true,
          },
          suite2p_spike_deconv: {
            type: "child",
            functionPath: "suite2p/suite2p_spike_deconv",
            args: [{ name: "ops", type: "Suite2pData", isNone: false }],
            returns: [
              { name: "ops", type: "Suite2pData" },
              { name: "spks", type: "FluoData" },
            ],
            condaName: "suite2p",
            condaEnvExists: true,
          },
        },
      },
      dummy: {
        type: "parent",
        children: {
          dummy_image2image: {
            type: "child",
            functionPath: "dummy/dummy_image2image",
            args: [{ name: "image", type: "ImageData", isNone: false }],
            returns: [{ name: "image2image", type: "ImageData" }],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2time: {
            type: "child",
            functionPath: "dummy/dummy_image2time",
            args: [{ name: "image", type: "ImageData", isNone: false }],
            returns: [{ name: "image2time", type: "TimeSeriesData" }],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2heat: {
            type: "child",
            functionPath: "dummy/dummy_image2heat",
            args: [{ name: "image", type: "ImageData", isNone: false }],
            returns: [{ name: "image2heat", type: "HeatMapData" }],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_time2time: {
            type: "child",
            functionPath: "dummy/dummy_time2time",
            args: [
              { name: "timeseries", type: "TimeSeriesData", isNone: false },
            ],
            returns: [{ name: "time2time", type: "TimeSeriesData" }],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2image8time: {
            type: "child",
            functionPath: "dummy/dummy_image2image8time",
            args: [{ name: "image1", type: "ImageData", isNone: false }],
            returns: [
              { name: "image", type: "ImageData" },
              { name: "timeseries", type: "TimeSeriesData" },
            ],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_keyerror: {
            type: "child",
            functionPath: "dummy/dummy_keyerror",
            args: [{ name: "image", type: "ImageData", isNone: false }],
            returns: [],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_typeerror: {
            type: "child",
            functionPath: "dummy/dummy_typeerror",
            args: [{ name: "image", type: "str", isNone: false }],
            returns: [],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2time8iscell: {
            type: "child",
            functionPath: "dummy/dummy_image2time8iscell",
            args: [{ name: "image1", type: "ImageData", isNone: false }],
            returns: [
              { name: "timeseries", type: "TimeSeriesData" },
              { name: "iscell", type: "IscellData" },
            ],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2roi: {
            type: "child",
            functionPath: "dummy/dummy_image2roi",
            args: [{ name: "image1", type: "ImageData", isNone: false }],
            returns: [{ name: "roi", type: "RoiData" }],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2image8roi: {
            type: "child",
            functionPath: "dummy/dummy_image2image8roi",
            args: [{ name: "image1", type: "ImageData", isNone: false }],
            returns: [
              { name: "image", type: "ImageData" },
              { name: "roi", type: "RoiData" },
            ],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2image8roi8time8heat: {
            type: "child",
            functionPath: "dummy/dummy_image2image8roi8time8heat",
            args: [{ name: "image1", type: "ImageData", isNone: false }],
            returns: [
              { name: "image", type: "ImageData" },
              { name: "roi", type: "RoiData" },
              { name: "timeseries", type: "TimeSeriesData" },
              { name: "heat", type: "HeatMapData" },
            ],
            condaName: "dummy",
            condaEnvExists: true,
          },
          dummy_image2scatter: {
            type: "child",
            functionPath: "dummy/dummy_image2scatter",
            args: [{ name: "image", type: "ImageData", isNone: false }],
            returns: [{ name: "scatter", type: "ScatterData" }],
            condaName: "dummy",
            condaEnvExists: true,
          },
        },
      },
      optinist: {
        type: "parent",
        children: {
          basic_neural_analysis: {
            type: "parent",
            children: {
              eta: {
                type: "child",
                functionPath: "optinist/basic_neural_analysis/eta",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  {
                    name: "behaviors_data",
                    type: "BehaviorData",
                    isNone: false,
                  },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [{ name: "mean", type: "TimeSeriesData" }],
                condaName: "optinist",
                condaEnvExists: true,
              },
              cell_grouping: {
                type: "child",
                functionPath: "optinist/basic_neural_analysis/cell_grouping",
                args: [
                  {
                    name: "neural_data",
                    type: "TimeSeriesData",
                    isNone: false,
                  },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
            },
          },
          dimension_reduction: {
            type: "parent",
            children: {
              cca: {
                type: "child",
                functionPath: "optinist/dimension_reduction/cca",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  {
                    name: "behaviors_data",
                    type: "BehaviorData",
                    isNone: false,
                  },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
              pca: {
                type: "child",
                functionPath: "optinist/dimension_reduction/pca",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
              tsne: {
                type: "child",
                functionPath: "optinist/dimension_reduction/tsne",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
            },
          },
          neural_population_analysis: {
            type: "parent",
            children: {
              correlation: {
                type: "child",
                functionPath: "optinist/neural_population_analysis/correlation",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
              cross_correlation: {
                type: "child",
                functionPath:
                  "optinist/neural_population_analysis/cross_correlation",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
              granger: {
                type: "child",
                functionPath: "optinist/neural_population_analysis/granger",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
            },
          },
          neural_decoding: {
            type: "parent",
            children: {
              glm: {
                type: "child",
                functionPath: "optinist/neural_decoding/glm",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  {
                    name: "behaviors_data",
                    type: "BehaviorData",
                    isNone: false,
                  },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
              lda: {
                type: "child",
                functionPath: "optinist/neural_decoding/lda",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  {
                    name: "behaviors_data",
                    type: "BehaviorData",
                    isNone: false,
                  },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
              svm: {
                type: "child",
                functionPath: "optinist/neural_decoding/svm",
                args: [
                  { name: "neural_data", type: "FluoData", isNone: false },
                  {
                    name: "behaviors_data",
                    type: "BehaviorData",
                    isNone: false,
                  },
                  { name: "iscell", type: "IscellData", isNone: true },
                ],
                returns: [],
                condaName: "optinist",
                condaEnvExists: true,
              },
            },
          },
        },
      },
    },
  }
})
