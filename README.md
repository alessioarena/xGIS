# xGIS (cross GIS)
This module was developed to facilitate the integration of custom code into GIS software like ArcGIS and QGIS.

The implementation of this solution gravitates around the default Python modules `os` and `subprocess`. Thanks to their functionalities, xGIS is capable of creating and manage new child processes (where the execution of the custom code will happen) while existing within the mapping software Python environment (to maintain connection with the software and its graphic interface).
<p align="center">
  <img src="docs/xgis_process_dependencies.png" width="500">
</p>

As the execution of the custom code happens in a brand new child process, xGIS can run softwre written in any language provided that resources to run it are available and accessible. Conversely, xGIS is Python module and can be imported and used in both Python 2 and 3.

This library comes with much more than the Python importable resources, and is in fact a full development framework to assist you designing, developing and deploying your custom mapping software extension. 
Those are:
- _Executor_ Python object (within the importable xGIS resources). This is a highly automated object that can create and manage the child process, while handling the connection between child process and graphic interface
- _setup_external_libs.py_ script (and _scripts_) to help you installing additional Python resources required to run your custom code. This is necessary to avoid the corruption of ArcGIS/QGIS Python environments
- _build_installer.py_ script (and _build_utils_) to assist you in creating a Windows installer for your extension.

## Requirements
The only real requirement is to enable in your custom code a command line interface. Compiled languages generally have this by design, while other languages like R can be set up using third party libraries (e.g. `argparse` in Python).

You will also need to develop the graphic interface in ArcGIS and QGIS. This can be done easily using their libraries `arcpy` and `pyqgis`, and in the case of QGIS by using QtDesigner. An ArcGIS example is provided in the `example` folder


## Executor: Hello World!
To print `hello world` in Python you can run the command `python -c 'print("hello world!")'`.
Similarly, in xGIS you can do:
```python
>>> import xgis
>>> exe = xgis.Executor(['python.exe', '-c', 'print("hello world!")'])
>>> exe.run()
15:56:57        Running python.exe externally
15:56:57           Working directory 'C:\Temp\********'
15:56:57           Executable 'C:\Python27\ArcGISx6410.5\python.exe'
15:56:57           Arguments python.exe -c print("hello world!")
15:56:57           ***** SubProcess Started *****
15:56:58           hello world!
15:56:58           ***** SubProcess Completed *****
```
## Executor: Usage
However, most of the time you want to have control on what to execute and how. Those parameters can be easily controlledin the Executore by doing: 
```python
# defining arguments for the custom code
>>> args = ['sklearn_script.py', 'input.csv', '--outname', 'out.csv']
# defining the folder location where the custom code dependencies are installed
>>> external_libs = '../../project_folder/external_libs/'
# defining a specific executable to use (for Python it will be the interpreter)
>>> py_exe = 'C:/Python27/ArcGISx6410.5/python.exe'
# initialise the Executor object
>>> exe = xgis.Executor(args, external_libs=external_libs, executable=py_exe)
# print the current settings 
>>> exe.info()
Current settings are:
  executable          : 'C:\Python27\ArcGISx6410.5\python.exe'  # Our specified python interpreter
  working directory   : 'C:\xxxx\xxxx_xxxx\xxxx'
  arguments           : 'C:\xxxx\xxxx_xxxx\xxxx\sklearn_script.py'  # Fully resolved script path
                      : 'input.csv'
                      : '--outname'
                      : 'out.csv'
  PATH                : 'C:\xxxx\project_folder\external_libs\lib\site-packages\osgeo'  # Detected gdal, it will add GDAL_PATH and GDAL_DRIVER_PATH as well
                      : 'C:\xxxx\project_folder\external_libs\lib\site-packages\osgeo\gdal-data'
                      : 'C:\xxxx\project_folder\external_libs\lib\site-packages\osgeo\gdalplugins'
                      : 'C:\xxxx\project_folder\external_libs'  # Fully resolved external_libs path
                      : 'C:\xxxx\project_folder\external_libs\lib'
                      : 'C:\xxxx\project_folder\external_libs\lib\site-packages'
                      : 'C:\ProgramData\DockerDesktop\version-bin'
                      : 'C:\Program Files\Docker\Docker\Resources\bin'
                      : 'C:\Windows\system32'
                      : 'C:\Windows'
  PYTHONPATH          : 'C:\xxxx\project_folder\external_libs'
                      : 'C:\xxxx\project_folder\external_libs\lib'
                      : 'C:\xxxx\project_folder\external_libs\lib\site-packages'
  GDAL_DRIVER_PATH    : 'C:\xxxx\project_folder\external_libs\lib\site-packages\osgeo\gdalplugins'
  GDAL_DATA           : 'C:\xxxx\project_folder\external_libs\lib\site-packages\osgeo\gdal-data'
# run
>>> result = exe.run()
Running 'C:\xxxx\xxxx_xxxx\xxxx\sklearn_script.py' externally
   Working directory 'C:\xxxx\xxxx_xxxx\xxxx'
   Executable 'C:\Python27\ArcGISx6410.5\python.exe'
   Arguments 'C:\Python27\ArcGISx6410.5\python.exe C:\xxxx\xxxx_xxxx\xxxx\sklearn_script.py input.csv --outname out.csv'
   loading data from input.csv
   preprocessing the data
   training the GAUSSIAN_MIXTURE model
   perform prediction
   RESULT: out.csv  # the stream handler will search for this pattern and return them
>>> print(result)
['out.csv']
```

## Executor: Advanced functionalities
The Executor object handles automatically most of the set up, but gives you control and visibility over most of it.
This object offers the following attributes and methods:
```python
Executor.executable     # Executable used to run the command line passed (e.g. python.exe)
Executor.cmd_line       # command line arguments (e.g. ['script.py', '--test_file', 'input.csv'])
Executor.cwd            # working directory to use
Executor.host           # for future support of QGIS and other
Executor._environ       # os.environ to use when running the subprocess call
Executor.logger         # logging Logger used by the Executor to report on the subprocess call


Executor.set_executable()
Executor.set_cmd_line()
Executor.set_cwd()
Executor.set_external_libs()
Executor.set_logger()
Executor.info()         # print current settings
Executor.run()          # run the subprocess call

ExternalExecutionError  # error raised when the execution fails. It exposes the errno exit code reported by the subprocess
```

## Executor: User Experience Integration
The Executore handles most of the user experience integration including:
- integration with graphic interface
- logging facility
- user cancellation
- background processing
- output loading

The entire output stream generated by the custom code is redirected to the mapping software graphic interface by using a custom logger. This is implemented in the `log_utils` importable submodule (accessible as `xgis.log_utils`). This logger can be customised as any other `logging` logger if required.
The Executor will also monitor for the specific pattern `RESULT:`. Anything following this pattern will be captured and returned upon successful process completion. This can be used to pass to the parent process simple information like full path of results on disk.


## Setup_external_libs: usage
This repository provides you a convenient script to help you installing Python custom code dependencies.
This can be as easy as:
```bash
>>> python.exe ./Scripts/setup_external_libs.py --pkgs numpy matplotlib==3.1.1 pandas>=0.23.4 --whls geopandas-0.5.0-py2.py3-none-any.whl
```
It also supports the definition of a requirements file in the yaml format (to not interfere with the widely used Anaconda requirements.txt system)
This file can be defined as follow
```yaml
pkgs:
  - 'numpy'
  - 'matplotlib==3.1.1'
  - 'pandas>=0.23.4'
whls:
  - 'geopandas-0.5.0-py2.py3-none-any.whl'
```

and used as follow:
```bash
>>> python.exe ./Scripts/setup_external_libs.py --yaml requirements.yaml
```

You can also specify the folder location to locally store this separate environment (default to ./external_libs)
```bash
>>> python.exe ./Scripts/setup_external_libs.py --target ./myenv
```

## Build_installer: usage
The build_utils folder comes with resources to help you package your entension in an installable self-extracting archive.
This is an effective way to deploy your code, and is integrated with `setup_external_libs` for Python tools.
Build parameters can be set up using the build_config.yaml file:
```yaml
# General info
name: TOOLBOX_NAME
version: 0.8

# Package build options
build_folder: # ['', path/relative/to/root] # path to use for the build (temporary files)
installer_script: setup.bat # ['', path/relative/to/root, 'setup.bat'] # script to run after the extraction. if None the post extraction task will be skipped

# setup.bat options
ArcGIS_support: True # [True, False]
QGIS_support: True # [True, False]
Python_version: 2  # ['', 2, 3] # for backend scripts
splash_screen: Welcome.html # ['', path/relative/to/root/.html] # If specified will open the given html upon successful installation

# Folders (and files) to include.
include_data: # list of files and folders to include
  # default values for most projects
  .: # to include the entire root folder
  xgis:
    core: # to include specific files in a folder
      - __init__.py
      - _version.py
      - executor.py
      - log_utils.py
    scripts:
      - setup_external_libs.py
      - getpip.py
  # here add you additional packages

# Folders (and files) to exclude. If the folder in not in include_data it will not have effect
exclude_data:
  # default values for most projects
  .:
    - .gitignore
    - .gitmodules
  # here add your files to exclude

# folders to be remapped. Paths are relative to the root folder. If the folder is not in include_data it will not have effect
remap_folders:
  # default values for most projects
  xgis:
    core: xgis\
    scripts: .\
  # here add your folders to remap
```

## Mapping software support
Currently there is support for:
- ArcGIS Desktop 10.5 and above
- QGIS 3 and above

Further planned work will expand this list to include other software and versions. Contribution to this repository are highly encouraged

## License

This software is available under the following license:
```
CSIRO Open Source Software Licence Agreement (variation of the BSD / MIT License)
Copyright (c) 2019, Commonwealth Scientific and Industrial Research Organisation (CSIRO) ABN 41 687 119 230.
All rights reserved. CSIRO is willing to grant you a licence to this xGIS on the following terms, except where otherwise indicated for third party material.
Redistribution and use of this software in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name of CSIRO nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission of CSIRO.
EXCEPT AS EXPRESSLY STATED IN THIS AGREEMENT AND TO THE FULL EXTENT PERMITTED BY APPLICABLE LAW, THE SOFTWARE IS PROVIDED "AS-IS". CSIRO MAKES NO REPRESENTATIONS, WARRANTIES OR CONDITIONS OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY REPRESENTATIONS, WARRANTIES OR CONDITIONS REGARDING THE CONTENTS OR ACCURACY OF THE SOFTWARE, OR OF TITLE, MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, THE ABSENCE OF LATENT OR OTHER DEFECTS, OR THE PRESENCE OR ABSENCE OF ERRORS, WHETHER OR NOT DISCOVERABLE.
TO THE FULL EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL CSIRO BE LIABLE ON ANY LEGAL THEORY (INCLUDING, WITHOUT LIMITATION, IN AN ACTION FOR BREACH OF CONTRACT, NEGLIGENCE OR OTHERWISE) FOR ANY CLAIM, LOSS, DAMAGES OR OTHER LIABILITY HOWSOEVER INCURRED.  WITHOUT LIMITING THE SCOPE OF THE PREVIOUS SENTENCE THE EXCLUSION OF LIABILITY SHALL INCLUDE: LOSS OF PRODUCTION OR OPERATION TIME, LOSS, DAMAGE OR CORRUPTION OF DATA OR RECORDS; OR LOSS OF ANTICIPATED SAVINGS, OPPORTUNITY, REVENUE, PROFIT OR GOODWILL, OR OTHER ECONOMIC LOSS; OR ANY SPECIAL, INCIDENTAL, INDIRECT, CONSEQUENTIAL, PUNITIVE OR EXEMPLARY DAMAGES, ARISING OUT OF OR IN CONNECTION WITH THIS AGREEMENT, ACCESS OF THE SOFTWARE OR ANY OTHER DEALINGS WITH THE SOFTWARE, EVEN IF CSIRO HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH CLAIM, LOSS, DAMAGES OR OTHER LIABILITY.
APPLICABLE LEGISLATION SUCH AS THE AUSTRALIAN CONSUMER LAW MAY APPLY REPRESENTATIONS, WARRANTIES, OR CONDITIONS, OR IMPOSES OBLIGATIONS OR LIABILITY ON CSIRO THAT CANNOT BE EXCLUDED, RESTRICTED OR MODIFIED TO THE FULL EXTENT SET OUT IN THE EXPRESS TERMS OF THIS CLAUSE ABOVE "CONSUMER GUARANTEES".  TO THE EXTENT THAT SUCH CONSUMER GUARANTEES CONTINUE TO APPLY, THEN TO THE FULL EXTENT PERMITTED BY THE APPLICABLE LEGISLATION, THE LIABILITY OF CSIRO UNDER THE RELEVANT CONSUMER GUARANTEE IS LIMITED (WHERE PERMITTED AT CSIRO'S OPTION) TO ONE OF FOLLOWING REMEDIES OR SUBSTANTIALLY EQUIVALENT REMEDIES:
(a)               THE REPLACEMENT OF THE SOFTWARE, THE SUPPLY OF EQUIVALENT SOFTWARE, OR SUPPLYING RELEVANT SERVICES AGAIN;
(b)               THE REPAIR OF THE SOFTWARE;
(c)               THE PAYMENT OF THE COST OF REPLACING THE SOFTWARE, OF ACQUIRING EQUIVALENT SOFTWARE, HAVING THE RELEVANT SERVICES SUPPLIED AGAIN, OR HAVING THE SOFTWARE REPAIRED.
IN THIS CLAUSE, CSIRO INCLUDES ANY THIRD PARTY AUTHOR OR OWNER OF ANY PART OF THE SOFTWARE OR MATERIAL DISTRIBUTED WITH IT.  CSIRO MAY ENFORCE ANY RIGHTS ON BEHALF OF THE RELEVANT THIRD PARTY.
```
