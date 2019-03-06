# arcpy_extender
Facility to enable external executions in arcpy and extend its capabilites

This library is composed of two parts:
 - setup_external_libs, and executable or importable script that takes care of setting up your python dependencies
 - the module itself, centered around core.py. This enables the use of Executer, a python class that takes care of setting and executing your process subcall
 
The Executor will allow you to use external python scripts (having conflicting dependencies with arcpy), as well as other languages (like R) and generally anything that can be executed.
This will:
 - search and resolve your script/executable
 - search and resolve your executable to use when calling your script
 - copy your environment and add any path you pass with the external_libs argument to your PATH in this copy. This environment will be then passed to your subcall
 - monitor your stdout, stderr and return code, raising RuntimeError when the call exits unexpectedly
 - monitor your stdout for certain keyword to interpret as results to load back
