import os
import sys
import json
try:
    import arcpy
except Exception:
    raise ImportError('Could not find the arcpy module. Are you running this toolbox from ArcGIS?')
import arcpy_extender
from arcpy_extender.core import ARClogger as log
logger = log.initialise_logger(to_file='ArcpyExtenderToolbox', force=True)


class Toolbox(object):
    def __init__(self):
        self.label = "Arcpy Extender"
        self.alias = "Toolbox to perform an external execution"
        # List of tool classes associated with this toolbox
        self.tools = [Extender]

    @staticmethod
    def store_parameters(parameters):
        logger.info('Saving parameters')
        stored_parameters = {}
        for p in parameters:
            if p.direction == "Output":
                stored_parameters[p.name] = None
                logger.info("Skipping {0}".format(p.name))
            else:
                stored_parameters[p.name] = p.valueAsText
                logger.info("  {0}: {1}".format(p.name, p.valueAsText))
        if stored_parameters != {}:
            with open('.arcpyparameters.txt', 'w+') as dump:
                dump.write(json.dumps(stored_parameters))

    @staticmethod
    def retrieve_parameters(parameters):
        if not os.path.isfile('.arcpyparameters.txt'):
            return parameters
        else:
            logger.info('Loading parameters')
            with open('.arcpyparameters.txt', 'r') as dump:
                stored_parameters = json.loads(dump.read())
            for p in parameters:
                if p.name in stored_parameters:
                    logger.info("  {0}: {1}".format(p.name, stored_parameters[p.name]))
                    p.value = stored_parameters[p.name]


class Extender(object):
    def __init__(self):
        self.label = 'Extender'
        self.description = 'Tool to perform an external execution'
        self.canRunInBackground = True

    def getParameterInfo(self):
        # Define parameter definitions
        parameters = []
        params0 = arcpy.Parameter(
            displayName='Script or executable to run externally',
            name='exe',
            datatype='DEFile',
            parameterType='Required')
        parameters.append(params0)

        params1 = arcpy.Parameter(
            displayName='Command line arguments',
            name='args',
            datatype='GPString',
            parameterType='Optional')
        parameters.append(params1)

        params2 = arcpy.Parameter(
            displayName='External libraries folder',
            name='ext_libs',
            datatype='DEWorkspace',
            parameterType='Optional')
        parameters.append(params2)

        params3 = arcpy.Parameter(
            displayName='Working directory',
            name='wd',
            datatype='DEWorkspace',
            parameterType='Optional')
        parameters.append(params3)

        params4 = arcpy.Parameter(
            displayName='Expected output path',
            name='out_path',
            datatype='GPString',
            parameterType='Optional')
        parameters.append(params4)

        params5 = arcpy.Parameter(
            displayName='out',
            name='out',
            datatype='DEFile',
            parameterType='Derived',
            direction='Output')
        parameters.append(params5)

        return parameters

    def isLicensed(self):  # optional
        return True

    def updateParameters(self, parameters):  # optional
        # if parameters[0].value is None:
        #     Toolbox.retrieve_parameters(parameters)

        # if all([p.hasBeenValidated for p in parameters]):
        #     # Logic to make sure that we don't pass the previous output file to avoid layer locking (PB-14)
        #     for p in parameters:
        #         if p.direction == "Output":
        #             p.value = None
        #     Toolbox.store_parameters(parameters)

        return

    def updateMessages(self, parameters):  # optional
        if parameters[0].value and not parameters[0].hasBeenValidated:
            if not os.access(parameters[0].valueAsText, os.X_OK):
                parameters[0].setErrorMessage('The selected file is not an executable')
        if parameters[1].value and not parameters[1].hasBeenValidated:
                parameters[1].setWarningMessage('The following string will be split to {0}. Please check that this is what you expect. Argument grouping can be achieved using quotes or brackets'.format(self.split_args(parameters[1].valueAsText)))
        if parameters[2].value and not parameters[2].hasBeenValidated:
            if not os.path.isdir(parameters[2].valueAsText):
                parameters[2].setErrorMessage('The selected path does not point to a valid directory')
        if parameters[3].value and not parameters[3].hasBeenValidated:
            if not os.path.isdir(parameters[3].valueAsText):
                parameters[3].setErrorMessage('The selected path does not point to a valid directory')
        return

    def execute(self, parameters, messages):
        exe = parameters[0].valueAsText
        args = self.split_args(parameters[1].valueAsText) if parameters[1].value else []
        ext_libs = parameters[2].valueAsText if parameters[2].value else False
        wd = parameters[3].valueAsText if parameters[3].value else False
        out = parameters[4].valueAsText if parameters[4].value else False

        cmd_line = [exe] + args

        try:
            logger.info('Initialising external executor')
            executor = arcpy_extender.Executor(cmd_line, external_libs=ext_libs, cwd=wd, logger=logger)
            logger.info('Performing the calculation')
            executor.run()
            if out:
                if not os.path.isfile(out):
                    raise RuntimeError('Could not find the expected output. Please check if the calculation completed successfully')
            logger.info(self.__class__.__name__ + ' succesfully completed')
            arcpy.SetParameter(len(parameters) - 1, out)
        except Exception:
            logger.exception(self.__class__.__name__ + ' failed with the following error')
            sys.exit(1)


    @staticmethod
    def split_args(args_string):
        args_string = str(args_string)
        begin_i = 0
        args = []
        quote_flag = False
        for i, c in enumerate(args_string):
            if c == ' ' and not quote_flag:
                if i - begin_i > 0:
                    args.append(args_string[begin_i:i])
                begin_i = i + 1
            elif c in ['"', "'", '(', ')', '[', ']', '{', '}']:
                quote_flag = not quote_flag
        if begin_i != len(args_string):
            args.append(args_string[begin_i:])
        return args
