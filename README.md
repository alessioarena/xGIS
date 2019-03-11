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

## License

This software is available under the following license:
```
CSIRO Open Source Software Licence Agreement (variation of the BSD / MIT License)
Copyright (c) 2019, Commonwealth Scientific and Industrial Research Organisation (CSIRO) ABN 41 687 119 230.
All rights reserved. CSIRO is willing to grant you a licence to this arcpy_extender on the following terms, except where otherwise indicated for third party material.
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