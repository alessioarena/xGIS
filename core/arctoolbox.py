import os
import sys
import re
import winreg
import logging
import json

try:
    import arcpy
except Exception:
    raise ImportError('Could not find the arcpy module. Are you running this toolbox from ArcGIS?')

class ArcToolbox(object):
    logger = None
    label = 'xGIS ArcToolbox'
    alias = "Toolbox to perform an external execution"
    tools = []
    toolbox_version_file__ = ''
    version__ = ''
    # ToolParameterState = {}

    # stored_parameters_file = os.path.join(os.path.expanduser("~"), 'xGISparameters.txt')
    def __init__(self):
        self.label
        self.alias
        self.tools

        self.version__
        self.pckg_name__
        self.release_date.__
        self.toolbox_version_file__
        self.toolbox_repository__

        self.logger

    def __delete__(self):
        self.del_user_env()

    # this method is used to memorize runtime parameters in an internal dictionary
    @classmethod
    def store_parameters(cls, tool, parameter_list):
        intro = "** Storing " + tool + " parameters **"
        cls.logger.info(intro)
        stored_parameters = []
        for index, parameter in enumerate(parameter_list):
            # discard output parameters to avoid layer locking
            if parameter.direction == "Output":
                stored_parameters.append([None, True])
                cls.logger.info("Skipping {0}".format(parameter.name))
            else:
                try:
                    stored_parameters.append([parameter.values, parameter.enabled])
                except AttributeError:
                    stored_parameters.append([parameter.valueAsText, parameter.enabled])
                try:
                    cls.logger.info("  {0}: {1} {2}".format(parameter.name, parameter.valueAsText, type(parameter.value)))
                except UnicodeEncodeError:
                    cls.logger.info("  {0}: {1} {2}".format(parameter.name, parameter.valueAsText.encode('utf-8'), type(parameter.value)))
        cls.ToolParameterState[tool] = stored_parameters
        cls.logger.info("*" * len(intro))
    # this method is used to get the parameters from the dictionary and use them as default for the GUI
    @classmethod
    def retrieve_parameters(cls, tool, parameter_list):
        if tool not in cls.ToolParameterState.keys():
            return
        intro = "** Retrieving " + tool + " parameters **"
        cls.logger.info(intro)
        stored_parameters = cls.ToolParameterState[tool]
        for index, parameter in enumerate(parameter_list):
            if stored_parameters[index] is not None:
                parameter.value = stored_parameters[index][0]
                parameter.enabled = stored_parameters[index][1]
                try:
                    cls.logger.info("  {0}: {1}".format(parameter.name, parameter.valueAsText))
                except UnicodeEncodeError:
                    cls.logger.info("  {0}: {1}".format(parameter.name, parameter.valueAsText.encode('utf-8')))
        cls.logger.info("*" * len(intro))
    # this does retrieving and storing of output paths as environmental variables.
    # this is required because the GUI and background geoprocessing are not shared memory

    @classmethod
    def manage_output(cls, key, value=False):
        if value is False:
            value = cls.get_user_env(key)
            if value is not None and os.path.isfile(value):
                return value
            else:
                return None
        else:
            cls.set_user_env(key, value)


    @classmethod
    def manage_parameters(cls, input_store_key=None):
        # this is a factory
        def manage_parameters_decorator(update_parms_func):
            if update_parms_func.__name__ != 'updateParameters':
                raise ValueError("this decorator can be used only for the 'updateParameters' method")
            def do_manage(tool, parameters):
                if all([ not p.hasBeenValidated for p in parameters]):
                    cls.logger.info("retrieve previous output")
                    if input_store_key is not None:
                        input_parms = []
                        if isinstance(input_store_key, (str, unicode)):
                            in_keys = [input_store_key]
                        else:
                            in_keys = input_store_key
                        if isinstance(in_keys, list):
                            for n, k in enumerate(in_keys):
                                p = cls.manage_output(k)
                                input_parms.append(p)
                                parameters[n].value = p
                        elif isinstance(in_keys, dict) and all([isinstance(k, int) for k in in_keys.keys()]) and all([isinstance(v, str) for v in in_keys.values()]):
                            for k, v in in_keys.items():
                                p = cls.manage_output(v)
                                input_parms.append(p)
                                parameters[k].value = p
                        else:
                            raise TypeError("Could not manage parameters. input_store_key is expected to be a str, list of str or dict of int:str")
                    # if input_store_key is None or all([p is None for p in input_parms]):
                    #     cls.retrieve_parameters(tool.__class__.__name__, parameters)
                    else:
                        cls.logger.info("No previous parameter to load, fresh start")
                update_parms_func(tool, parameters)

                # this is executed when you press the RUN button
                # if all([p.hasBeenValidated for p in parameters]):
                #     cls.store_parameters(tool.__class__.__name__, parameters)
                return 
            return do_manage
        return manage_parameters_decorator

    @classmethod
    def manage_execution(cls, output_store_key=None):
        def manage_execution_decorator(func):
            if func.__name__ != 'execute':
                raise ValueError("this decorator can be used only for the 'execute' method")
            def do_manage(tool, parameters, messages):
                cls.logger.info('Running ' + cls.pckg_name__ + ' version ' + cls.version__ + ' released on ' + str(cls.release_date__))
                vc = cls.check_version()
                if vc:
                    cls.logger.warning('You are running an old toolbox version. A newer one ({0}) is available for download at {1}'.format('.'.join(vc), cls.toolbox_repository__))
                cls.logger.info('__Starting ' + tool.__class__.__name__ + '__')

                output = func(tool, parameters, messages)
                if output and parameters[-1].direction == 'Output':
                    arcpy.SetParameter(len(parameters) - 1, output)

                if output_store_key is not None:
                    if isinstance(output_store_key, str):
                        out_keys = [output_store_key]
                    else:
                        out_keys = output_store_key #BUG if overwriting the same variable it complains about being undefined (probably gets lost in this function scope?!)
                    if not isinstance(output, (list, tuple)):
                        output = [output]
                    if isinstance(out_keys, list):
                        if len(out_keys) != len(output):
                            raise RuntimeError("Could not manage output. Expected {0} output but received {1}".format(len(out_keys), len(output)))
                        else:
                            for o, k in zip(output, out_keys):
                                cls.manage_output(k, o)
                return
            return do_manage
        return manage_execution_decorator

    @classmethod
    def manage_required_parameters(cls, control_parameter_idx=None, required_indices=[]):
        def manage_required_parameters_decorator(func):
            if func.__name__ != 'updateMessages':
                raise ValueError("this decorator can be used only for the 'updateMessages' method")
            def do_manage(tool, parameters):
                if not isinstance(control_parameter_idx, int) or control_parameter_idx>len(parameters) or control_parameter_idx < 0:
                    raise TypeError("Control_parameter must be a valid parameter index ")
                control_parameter = parameters[control_parameter_idx]
                try:
                    control_options = control_parameter.filter.list
                    if len(control_options) == 0:
                        raise AttributeError
                except AttributeError:
                    if control_parameter.datatype == 'GPBoolean':
                        control_options = [True, False]
                    else:
                        raise ValueError("Control_parameter must have a value filter set or being Boolean")

                if not isinstance(required_indices, (list, tuple)) or any([not isinstance(l, (list, tuple)) for l in required_indices]):
                    raise TypeError("required_indices must be a list of lists")
                
                if len(control_options) != len(required_indices):
                    raise ValueError("number of options in the control_parameter and number of list of required parameters must be the same")

                for control, required in zip(control_options, required_indices):
                    if control_parameter.value == control:
                        for r in required:
                            if not parameters[r].altered or not parameters[r].value:
                                parameters[r].setIDMessage("ERROR", 735, parameters[r].displayName)
                func(tool, parameters)
                return
            return do_manage
        return manage_required_parameters_decorator


    @classmethod
    def check_version(cls):
        import requests
        try:
            text = requests.get(cls.toolbox_version_file__).text
            version = re.match('Latest Version: ([0-9.]*)', text).group(1)
        except Exception:
            version = False
        if version:
            version = version.split('.')
            tool_version = cls.version__.split('.')
            for o, n in zip(tool_version, version):
                if int(o) < int(n):
                    break
            else:
                version = False
        return version

    @staticmethod
    def get_user_env(name):
        """Utility to retrieve Windows environmental variables

        Arguments:
        -----------
        name : str
            variable name

        Returns:
        -----------
        out : str
            variable value
        """
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"xGIS", 0, winreg.KEY_READ)
        try:
            return winreg.QueryValueEx(key, name)[0]
        except WindowsError:
            return None
        finally:
            winreg.CloseKey(key)

    @staticmethod
    def set_user_env(name, value):
        """Utility to create and assign a value to a Windows environmental variable

        Arguments:
        -----------
        name : str
            variable name
        value : str
            variable value
        """
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"xGIS", 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        finally:
            winreg.CloseKey(key)

    @staticmethod
    def del_user_env(name=None):
        try:
            if name is None:
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, r"xGIS", winreg.KEY_ALL_ACCESS, 0)
            else:
                key = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, r"xGIS", 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, name)
        except WindowsError:
            pass

    @staticmethod
    def parameter_has_been_modified(param):
        if param.value and not param.hasBeenValidated:
            return True
        else:
            return False



    @staticmethod
    def parse_multivalues(param):
        if param.multiValue is False:
            raise TypeError("The parameter provided is not a multiValue")
        values = param.valueAsText.split(';')
        if param.datatype == 'String':
            for n, v in enumerate(values):
                if v.startswith("'"):
                    v = v[1:]
                if v.endswith("'"):
                    v = v[:-1]
                values[n] = v
        elif param.datatype == 'Double':
            values = [float(v) for v in values]
        elif param.datatype == 'Long':
            values = [int(v) for v in values]
        else:
            raise NotImplementedError("parameter datatype {0} is not supported".format(param.datatype))
        return values

    @staticmethod
    def list_feature_fields(value, exclude=[]):
        path = str(value)
        exclude += ['Shape', 'FID', 'ID']
        if path.endswith('xls') or path.endswith('xlsx'):
            import xlrd
            sheet = xlrd.open_workbook(path).sheet_by_index(0)
            if sheet.ncols == 0:
                raise ValueError("the Excel file appears to be empty. Detected 0 columns")
            cols = [sheet.cell(0, i).value for i in range(sheet.ncols)]
            cols = [c for c in cols if c not in exclude + ['', None]]
            cols = [c.encode('ascii', 'replace') for c in cols]
            if len(cols) == 0:
                raise ValueError("Excel file incorrectly formatted. Please make sure that the first column contains column headers with no gaps")
            return cols
        elif path.endswith('csv'):
            import csv
            with open(path, 'r') as f:
                reader = csv.reader(f)
                cols = list(next(reader))
            cols = [c for c in cols if c not in exclude + ['', None]]
            return cols
        else:
            return [str(x.name) for x in arcpy.ListFields(value) if not x.name in exclude]

    @staticmethod
    def list_unique_field_values(table, field):
        with arcpy.da.SearchCursor(table, [field]) as cursor:
            return sorted({row[0] for row in cursor})

    @staticmethod
    def get_outname(source, suffix, optional_ext, dirpath=False, extract_basename_root=False, overwrite=False):
        """Absolute dirpath to save the output.
        The directory is retrieved from source
        if source has a name following part1_part2_part3, part1 will be preserved as prefix
        Alternatively the entire source basename will be used

        suffix will be appended to the basename
        Finally, optional_ext will be used as extension if necessary (e.g. if you are not saving it in a geodatabase)

        Arguments:
        -----------
        source : Parameter or Parameter.value
            source object/value
        suffix : str
            suffix to use for the output name
        optional_ext : str
            file extension to use in case you are not saving in a geodatabase (gdb)
        dirpath : str, false or None, optional (default : False)
            absolute directory path to prepend to the output name
            if str, then check if exists and use it
            if False, use the source location
            if None, use the current workspace (ArcMap home directory)
        extract_basename_root : bool, optional (default : True)
            if True it will split the basename using '_' and keep only the initial part

        Returns:
        -----------
        out : str
            absolute dirpath for the output file
        """

        try:
            try:
                # try to convert the input to Describe object
                meta = arcpy.Describe(source)
            except:
                # if cannot perform the Describe operation we assume it is already a Describe bj
                meta = source

            # _ = meta.file  # BUG This should make sure that the attribute is updated before calling it. Sometimes this changes while running!
            if re.match('^.*\.[a-z]{2,4}$', meta.file) is None:
                # the path is for a image band (not a real path)
                meta_path = os.path.dirname(meta.catalogPath)
            else:
                # the path is for a image file
                meta_path = meta.catalogPath
        except (NameError, AttributeError):
            # to be able to use this outside the ArcGIS environment
            meta_path = source

        basename = os.path.splitext(re.sub('[-!@#$%^&()]', '_', os.path.basename(meta_path)))[0]
        if extract_basename_root:
            basename = basename.split('_')[0]

        name_suffix = basename.split('_')[-1]
        if suffix!= '' and name_suffix.startswith(suffix):
            basename = '_'.join(basename.split('_')[:-1])

        # dealing with path
        if dirpath is False:
            # the user wants to save in the same location of the input file
            dirpath = os.path.dirname(meta_path)
        elif dirpath is None:
            # the user wants to save it in the default workspace
            try:
                dirpath = arcpy.env.workspace
            except:
                # also, to be able to use it outside ArcGIS
                dirpath = os.getcwd()
        elif os.path.exists(dirpath) or '.gdb' in dirpath:
            # the user defined a custom dirpath
            pass
        else:
            raise IOError('The argument dirpath does not exist, or could not be understood')
        if dirpath is not None and dirpath != '' and not dirpath.endswith(os.sep):
            dirpath = dirpath + os.sep

        if suffix != '' and not suffix.startswith('_'):
            suffix = '_' + suffix

        if '.gdb' in dirpath or optional_ext == '':
            optional_ext = ''
        elif not optional_ext.startswith('.'):
            optional_ext = '.' + optional_ext

        if overwrite:
            return os.path.normpath(''.join([dirpath, basename, suffix, optional_ext]))
        else:
            count = 0

            while True:
                path = os.path.normpath(''.join([dirpath, basename, suffix] + ['' if count == 0 else str(count)] + [optional_ext]))
                if os.path.exists(path):
                    count += 1
                else:
                    break
            return path
