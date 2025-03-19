(debugging)=
Debugging
=================
This section describes the various debugging methods included in OptiNiSt.

## 1. Conda environment debugging

<p align="center">
<img width="300px" src="../_static/other/maintenance_folder.png" alt="Maintenance folder" />
</p>

<p align="center">
<img width="300px" src="../_static/other/maintenance_popup.png" alt="Conda env creation popup" />
</p>


## 2. Console log

## 3. IPython notebooks

OptiNiSt provides several ipynb notebooks in the **notebooks** folder: caiman.ipynb, suite2p.ipynb, lccd.ipynb. These may be used for assessing where in the code an error is occuring. This can be useful when the Conda environment loads, however, somewhere in the ROI detection or plotting an error occurs. 

### Parameter conversion notebook
In the upgrade to OptiNiSt version 2, the parameter input structure was reorganised. Workflows created in  OptiNiSt version 1 and reproduced in version 2, as well as [workflow.yaml](ImportWorkflowYaml) produced and saved in version 1 and imported in version 2, will not work.

To reproduce a version 1 Workflow, a conversion script is provided, in the form of a IPython notebook. Follow this procedure:
1. Download workflow from Record tab
2. Open notebooks/yaml-converter.ipynb
3. Setup environment following instructions at the top of yaml-converter.ipynb
4. Convert files using the section at the bottom of yaml-converter.ipynb
```python
input_file = ".yaml"
output_file = ".yaml" # any name you want
convert_workflow_file(input_file, output_file)
```

## 4. OptiNiSt wiki FAQ

For responses to common error messages, check the [OptiNiSt Wiki FAQ](https://github.com/oist/optinist/wiki/FAQ) page, and existing issues on [OptiNiSt git](https://github.com/oist/optinist/issues). Please create an new issue describing anything not covered on these pages.
