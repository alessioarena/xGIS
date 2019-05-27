import os
import sys
import logging
import subprocess
from shutil import rmtree
# initialise logger
logging.basicConfig(level=logging.INFO, format='%(levelname)8s   %(message)s')
logger = logging.getLogger(__name__)

# target = os.path.realpath('./external_libs')
# pkgs = ['pandas==0.23.4', 'numpy==1.15.2', 'scipy==1.1.0', 'scikit-image==0.14.0', 'sklearn', 'opencv-contrib-python==3.4.3.18', 'ptvsd==4.1.3', 'netCDF4==1.4.1', 'threddsclient==0.3.5']
# whls = ['gdal_ecw-2.2.3-cp27-none-win_amd64.whl', 'rasterio-1.0.12-cp27-cp27m-win_amd64.whl', 'pyproj-1.9.5.1-cp27-cp27m-win_amd64.whl']


# installer runtime object
class Installer(object):
    whls = False
    pkgs = False
    yaml = False
    target = './external_libs'

    # initialise and run
    def __init__(self, target=False, pkgs=False, whls=False, yaml=False):
        try:
            # Input checking
            if target:
                if isinstance(target, (str, unicode)):
                    self.target = target
                else:
                    raise TypeError("'target' must be a string")
            if not any([yaml, pkgs, whls]):
                raise RuntimeError("At least one of 'yaml, 'pkgs', 'whls' is required")
            else:
                self.whls = whls
                self.pkgs = pkgs
                self.yaml = yaml

            # Test if you have pip, and install if not
            # also safely import main from pip as self.pipmain
            self.test_pip()

            # loading the yaml file if passed
            if yaml and (not whls and not pkgs):
                self.load_yaml()
            else:
                raise NotImplementedError("Passing 'yaml' argument and any of 'pkgs' or 'whls' is not supported ")

            # testing the architecture against the wheels passed
            # also print warning if not using ArcGIS python environment
            self.test_architecture(self.whls)

            # check wether you have already all the required packages installed in the target folder
            # TODO to be checked wether captures all cases
            if os.path.exists(self.target):
                if self.test_environment():
                    answer = 'empty'
                    logger.info('Found a pre-existing {:s} folder. '.format(self.target))
                    while answer.lower() not in ['', 'y', 'n']:
                        answer = raw_input('   INPUT   Do you want to re-install external libraries? [y/n]: ')
                    if answer.lower() == 'n':
                        sys.exit()
                rmtree(self.target)

            # running the installation
            logger.info('target folder is ' + self.target)
            try:
                self.install_whls()
                self.install_pkgs()
            except Exception:
                # clean up if something went wrong
                if os.path.isdir(self.target):
                    rmtree(self.target)
                raise
        except Exception:
            logger.exception('Installation failed with the following exception')


    # method to test the architecture
    @staticmethod
    def test_architecture(whls=False):
        # check if you are running a ArcGIS python and warn if it is not the case
        if 'arcgis' not in sys.executable.lower():
            logging.warning('You are not using the ArcGIS python interpreter. Please be mindful that libraries installed in this way may not be compatible with ArcGIS')
        # we are running a 32bit python
        if sys.maxsize == 2147483647:
            # if whls are for 64bit, raise an error
            if whls and any(['amd64' in x for x in whls]):
                raise RuntimeError('Detected Python 32bit, but you provided 64 bit wheels. Please run this script with the 64bit Python interpreter')
        # we are running a 64bit python
        elif sys.maxsize == 9223372036854775807:
            # if whls are for 32bit, raise an error
            if whls and any(['win32' in x for x in whls]):
                raise RuntimeError('Detected Python 64bit, but you provided 32 bit wheels. Please run this script with the 32bit Python interpreter')
        # failed to detect the architecture
        else:
            raise RuntimeError('Could not understand your python architecture.')


    # method to test if you have pip with the chosen python interpreter
    def test_pip(self):
        # some arcgis version doesn't have pip installed
        try:
            import pip  # noqa:F401
        # you do not have pip
        except ImportError:
            logger.info('Could not find a pip version associated with this python executable. Retrieving and installing the latest version...')
            import getpip
            # retrieve pip
            getpip.main()
            # all good, but you need to restart this process
            logger.info('Pip 9.0.1 succesfully installed. Please rerun this script')
            sys.exit()

        return


    # load the yaml file
    def load_yaml(self):
        # input check
        if not isinstance(self.yaml, (str, unicode)) or not os.path.isfile(self.yaml):
            raise IOError('could not understand or find the yaml file. Please make sure to pass the correct path as a string')

        # load the yaml library if you have it, or install it and load it
        try:
            import yaml
        except ImportError:
            cmd_line = ['-q', 'pyyaml']
            self._installer(cmd_line)
            import yaml

        # load the yaml file
        try:
            requirements = yaml.load(open(self.yaml, 'r'))
        except:
            logger.exception('Could not load the yaml file. The error is:')
        # populate the pkgs and whls attributes
        if isinstance(requirements, dict):
            self.pkgs = requirements['pkgs'] if 'pkgs' in requirements.keys() else False
            self.whls = requirements['whls'] if 'whls' in requirements.keys() else False

        # just print stuff
        logger.info('Loaded yaml file with following configurations:')
        logger.info(' pkgs: {0}'.format(str(self.pkgs)))
        logger.info(' whls: {0}'.format(str(self.whls)))

        # if we do not have anything to install at this point, raise an error
        if not self.pkgs and not self.whls:
            raise ValueError("The requirements file is not structured properly. Please make sure to use the following structure:\npkgs:\n  - 'numpy'\n  - 'scipy==1.1.0'\nwhls:\n  - 'gdal_ecw-2.2.3-cp27-none-win_amd64.whl'\n")
        return


    # test the installed libraries
    def test_environment(self):
        import sys
        import pkgutil
        # divert the path to the locally installed libraries
        backup = sys.path
        sys.path = [self.target]  # + sys.path
        # get the content of the target folder
        dirs = os.listdir(self.target)
        check = []
        # for every package we need to install
        for p in self.pkgs:
            p = p.split('==')[0]
            # try to import it
            import_test = bool(pkgutil.find_loader(p))
            p = p.replace('-', '_')
            # and try to match it with any folder
            search_test = any([d.startswith(p) for d in dirs])
            # for example, if we want to install scikit-learn, this will fail on import even if it is installed
            # in fact, you do
            #   import sklearn
            # and not
            #   import scikit-learn
            # however the folder will be there
            check.append(import_test or search_test)
        # revert to previous PATH
        sys.path = backup
        # return wheter all libraries are there
        return all(check)


    # method to install python packages using pip
    def install_pkgs(self):
        if self.pkgs and len(self.pkgs) > 0:
            cmd_line = ['-q', '--disable-pip-version-check', '--target'] + [self.target] + self.pkgs
            self._installer(cmd_line)


    # method to install wheels using pip
    def install_whls(self):
        if self.whls and len(self.whls) > 0:
            cmd_line = ['-q', '--disable-pip-version-check', '--prefix=' + self.target] + self.whls
            self._installer(cmd_line)


    # general method to run the installation
    @staticmethod
    def _installer(cmd_line):
        # prepend the python call
        if not cmd_line[:4] == ['python', '-m', 'pip', 'install']:
            cmd_line = ['python', '-m', 'pip', 'install'] + cmd_line
        logger.info('executing ' + ' '.join(cmd_line))
        # run the subprocess
        installer = subprocess.Popen(
            args=cmd_line,
            shell=False,
            executable=sys.executable,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        # wait for it to complete
        installer.wait()
        # something went wrong
        if installer.returncode != 0:
            raise RuntimeError(str(installer.stderr.read()))

        return


# command line interface
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Utility to install dependencies locally')
    parser.add_argument('--target', type=str, default='external_libs', help='Folder name to use as target location for the installation')
    parser.add_argument('--whls', type=str, nargs='+', default=False, help='list of wheels name to install')
    parser.add_argument('--pkgs', type=str, nargs='+', default=False, help='list of package name to install')
    parser.add_argument('--yaml', type=str, default=False, help='path to yaml file containing requirements to install')
    args = parser.parse_args()

    Installer(target=args.target, whls=args.whls, pkgs=args.pkgs, yaml=args.yaml)
