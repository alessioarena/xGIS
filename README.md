# arcpy_extender
Facility to enable external executions in arcpy and extend its capabilites

This library is composed of two parts:
 - setup_external_libs, and executable or importable script that takes care of setting up your python dependencies
 - the module itself centered around Executer, a python class that takes care of resolving absolute paths, setting up your environment, executing your process subcall and managing your output and error streams
 
The Executor will allow you to use external python scripts (including those having conflicting dependencies with arcpy), as well as other languages (like R) and generally anything that can be executed in a shell.
This will:
 - search and resolve your script/executable
 - search and resolve your executable to use when calling your script
 - copy your environment and add any path you pass with the external_libs argument to your PATH. This environment will be then used in your subcall
 - monitor your stdout, stderr and return code, raising RuntimeError when the call exits unexpectedly
 - monitor your stdout for certain keyword to interpret as results to load back

## Example usage
Here is a short example on how to print hello word using this tool
```python
>>> import arcpy_extender
>>> exe = arcpy_extender.Executor(['python.exe', '-c', 'print("hello world!")'])
>>> exe.info()
Current settings are:
  executable          : None  # exe passed, so no need to specify a different executable
  working directory   : 'C:\xxxx\xxxx_xxxx\xxxx'
  arguments           : 'C:\Users\xxxxx\miniconda2_64\python.exe'  # Fully resolved python executable path
                      : '-c'
                      : 'print("hello world!")'
  PATH                : 'C:\ProgramData\DockerDesktop\version-bin'
                      : 'C:\Program Files\Docker\Docker\Resources\bin'
                      : 'C:\Windows\system32'
                      : 'C:\Windows'
>>> exe.run()
Running 'C:\Users\xxxxxx\miniconda2_64\python.exe' externally
   Working directory 'C:\xxxx\xxxx_xxxx\xxxx'
   Executable None
   Arguments 'C:\Users\xxxxxx\miniconda2_64\python.exe -c print("hello world!")'
   hello world!
```

The Executor object allows you to control your environment using a simple interface. For example:
```python
>>> args = ['sklearn_script.py', 'input.csv', '--outname', 'out.csv']
>>> external_libs = '../../project_folder/external_libs/'
>>> py_exe = 'C:/Python27/ArcGISx6410.5/python.exe'
>>> exe = arcpy_extender.Executor(args, external_libs=external_libs, executable=py_exe)
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
