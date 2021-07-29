import os
import sys
import re
import winreg
import logging

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
    Tool_Parameter_State = {}

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
        cls.Tool_Parameter_State[tool] = stored_parameters
        cls.logger.info("*" * len(intro))
    # this method is used to get the parameters from the dictionary and use them as default for the GUI
    @classmethod
    def retrieve_parameters(cls, tool, parameter_list):
        if tool not in cls.Tool_Parameter_State.keys():
            return
        intro = "** Retrieving " + tool + " parameters **"
        cls.logger.info(intro)
        stored_parameters = cls.Tool_Parameter_State[tool]
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
            cls.logger.info(value)
            cls.set_user_env(key, value)

    @classmethod
    def manage_parameters(cls, update_parms_func):
        def do_manage(tool, parameters):

            if all([ not p.hasBeenValidated for p in parameters]):
                cls.retrieve_parameters(tool.__class__.__name__, parameters)
            else:
                update_parms_func(tool, parameters)

            # this is executed when you press the RUN button
            if all([p.hasBeenValidated for p in parameters]):
                cls.store_parameters(tool.__class__.__name__, parameters)
            return 
        return do_manage

    @classmethod
    def manage_execution(cls, execute_func):
        def do_manage(tool, parameters, messages):
            cls.logger.info('Running ' + cls.pckg_name__ + ' version ' + cls.version__ + ' released on ' + str(cls.release_date__))
            vc = cls.check_version()
            if vc:
                cls.logger.warning('You are running an old toolbox version. A newer one ({0}) is available for download at {1}'.format('.'.join(vc), cls.toolbox_repository__))
            cls.logger.info('__Starting ' + tool.__class__.__name__ + '__')

            outname = execute_func(tool, parameters, messages)
            if outname and parameters[-1].direction == 'Output':
                arcpy.SetParameter(len(parameters) - 1, outname)
            return
        return do_manage


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
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Environment")
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
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Environment")
        try:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        finally:
            winreg.CloseKey(key)

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
    def get_outname(source, suffix, optional_ext, dirpath=False, extract_basename_root=False):
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

        return os.path.normpath(''.join([dirpath, basename, suffix, optional_ext]))
