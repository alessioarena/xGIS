import os
import arcpy
import xgis

class Toolbox(object):
    def __init__(self):
        self.label = "Example Toolbox"
        self.alias = "exampleToolbox"
        # List of tool classes associated with this toolbox
        self.tools = [AwesomeTool]


class AwesomeTool(object):
    def __init__(self):
        self.label = 'AwesomeTool'
        self.description = 'This tool will run an awesome script externally'
        self.canRunInBackground = True

    def getParameterInfo(self):
        # Define parameter definitions
        parameters = []

        params0 = arcpy.Parameter(
            displayName='Input Raster',
            name='in_raster',
            datatype='GPRasterLayer',  # This will source the loaded rasters, or give you the option to specify one from disk
            parameterType='Required')
        parameters.append(params0)

        params1 = arcpy.Parameter(
            displayName='Region of Interest',
            name='in_shp',
            datatype='GPFeatureLayer',  # Same deal, but for features (like shapefiles)
            parameterType='Optional')  # This parameter is optional
        parameters.append(params1)

        params2 = arcpy.Parameter(
            displayName='Output Name',
            name='out_name',
            datatype='GPString',  # simple string
            parameterType='Required')
        params2.value = os.path.join(os.path.expanduser('~'), 'output_raster.tif')  # This will be the default value
        parameters.append(params2)

        params3 = arcpy.Parameter(
            displayName='Algorithm to use',
            name='algorithm',
            datatype='GPString',
            parameterType='Required')
        params3.filter.list =  ['GAUSSIAN_MIXTURE', 'K_MEANS', 'SPECTRAL_CLUSTERING']  # to create a dropdown menu
        params3.value = 'K_MEANS'
        parameters.append(params3)

        params4 = arcpy.Parameter(
            displayName='Variables',
            name='vars',
            datatype='GPString',
            multiValue=True,  # To create a check list
            parameterType='Required')
        params4.filter.list = ['MEAN', 'MODE', 'MEDIAN', 'HISTOGRAM', 'TEXTURE']  # Values for the check list
        params4.value = ['MEAN', 'MODE']
        parameters.append(params4)

        params5 = arcpy.Parameter(
            displayName='Debug Mode',
            name='debug',
            datatype='GPBoolean',  # just a tick box
            parameterType='Required')
        params5.value = False
        parameters.append(params5)

        params6 = arcpy.Parameter(
            displayName='Result',
            name='result',
            datatype='DERasterDataset',
            parameterType='Derived',
            direction='Output')  # This parameter is hidden, and its value will be used at the end to automatically source and load the output raster
        parameters.append(params6)

        return parameters

    def isLicensed(self):  # optional
        return True

    def updateParameters(self, parameters):  # optional
        # this will automatically fill the output_path parameter using the same directory as the input
        # anything in this section will be run every time you modify one of the parameters
        if parameters[0].value and not parameters[0].hasBeenValidated:
            parameters[2].value = os.path.join(arcpy.Describe(parameters[0].value).path, 'output_raster.tif')
        return

    def updateMessages(self, parameters):  # optional
        # this will be run any time you modify a parameter
        # You can use specific methods to raise warnings or error in the graphic interface
        return

    def execute(self, parameters, messages):
        # Let's start building the list of arguments
        args = []
        args.append('awesome_script.py')

        # Mandatory arguments
        raster_path = arcpy.Describe(parameters[0].value).catalogPath
        args.append(raster_path)
        args.append(parameters[2].valueAsText)

        # optional arguments
        if parameters[1].value:
            roi_path = arcpy.Describe(parameters[1].value).catalogPath
            args.extend(['--roi', roi_path])
        args.extend(['--algorithm', parameters[3].valueAsText])
        args.extend(['--variables'] + str(parameters[4].valueAsText).split(';'))
        if parameters[5].value is not False:
            args.append(['--debug'])

        # let's run this!
        proc = xgis.Executor(args, external_libs='external_libs', cwd=os.path.dirname(__file__))
        proc.run()

        # if the output file exists, assign it to the output parameter (this is hidden in the GUI)
        # The output parameter will be automatically loaded back in ArcMap, and used in ModelBuilder and other ESRI tools
        if os.path.isfile(parameters[2].valueAsText):
            arcpy.SetParameter(len(parameters) - 1, parameters[2].valueAsText)
        else:
            raise RuntimeError('Could not find the output file')


