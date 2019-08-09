import os
import sys
import logging
import subprocess
import pkgutil
import pkg_resources as pkg_r
import site
from shutil import rmtree
# initialise logger
logging.basicConfig(level=logging.INFO, format='%(levelname)8s   %(message)s')
logging.captureWarnings(True)
logger = logging.getLogger(__name__)

# for python 2 and python 3 compatibility
try:
    # python 2
    basestring
    raw_input
except NameError:
    # python 3
    basestring = (str, bytes)
    raw_input = input

# target = os.path.realpath('./external_libs')
# pkgs = ['pandas==0.23.4', 'numpy==1.15.2', 'scipy==1.1.0', 'scikit-image==0.14.0', 'sklearn', 'opencv-contrib-python==3.4.3.18', 'ptvsd==4.1.3', 'netCDF4==1.4.1', 'threddsclient==0.3.5']
# whls = ['gdal_ecw-2.2.3-cp27-none-win_amd64.whl', 'rasterio-1.0.12-cp27-cp27m-win_amd64.whl', 'pyproj-1.9.5.1-cp27-cp27m-win_amd64.whl']


# installer runtime object
class Installer(object):
    whls = False
    pkgs = False
    yaml = False
    target = './external_libs'
    lib_folder = './external_libs/Python27/site-packages'
    supported_version_cmp = ['===', '~=', '!=', '==', '<=', '>=', '<', '>']

    # initialise and run
    def __init__(self, target=False, pkgs=False, whls=False, yaml=False, dry_run=False):
        try:
            # Input checking
            if target:
                if isinstance(target, basestring):
                    self.target = target
                    self.lib_folder = os.path.join(os.path.abspath(self.target), 'Python{0}{1}{2}site-packages'.format(sys.version_info[0], sys.version_info[1], os.sep))
                    logger.info('Target folder is ' + self.lib_folder)
                else:
                    raise TypeError("'target' must be a string")
            if not any([yaml, pkgs, whls]):
                raise RuntimeError("At least one of 'yaml, 'pkgs', 'whls' is required")
            else:
                self.whls = whls
                self.pkgs = pkgs
                self.yaml = yaml
            if not isinstance(dry_run, bool):
                raise TypeError('The argument "dry_run" must be a boolean')
            else:
                self.dry_run = dry_run

            # Test if you have pip, and install if not
            # also safely import main from pip as self.pipmain
            self.test_pip()

            # loading the yaml file if passed
            if yaml and not (whls or pkgs):
                self.load_yaml()
            elif yaml:
                raise NotImplementedError("Passing 'yaml' argument and any of 'pkgs' or 'whls' is not supported ")

            # testing the architecture against the wheels passed
            # also print warning if not using ArcGIS python environment
            self.test_architecture(self.whls)

            # check wether you have already all the required packages installed in the target folder
            # TODO to be checked wether captures all cases
            if os.path.exists(self.target):
                logger.info('Checking whether requirements are already satisfied')
                if self.test_environment():
                    logger.info('Found all required packages')
                    answer = 'empty'
                    # logger.info('Found a pre-existing {:s} folder. '.format(self.target))
                    while answer.lower() not in ['', 'y', 'n']:
                        answer = raw_input('   INPUT   Do you want to re-install external libraries? [y/n]: ')
                    if answer.lower() == 'n':
                        sys.exit()
                else:
                    logger.info('Some of the required packages are missing')
                if not self.dry_run:
                    rmtree(self.target, ignore_errors=True)

            # running the installation
            logger.info('***** Running the installation *****')
            try:
                self.install_whls()
                self.install_pkgs()
            except Exception:
                # clean up if something went wrong
                if os.path.isdir(self.target):
                    rmtree(self.target, ignore_errors=True)
                raise
        except Exception:
            logger.exception('Installation failed with the following exception')
            sys.exit(1)  # making sure that we carry over the error outside python

    @staticmethod
    def test_architecture(whls=False):
        # method to test the architecture
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

    def test_pip(self):
        # method to test if you have pip with the chosen python interpreter
        # some arcgis version doesn't have pip installed
        try:
            import pip  # noqa:F401
        # you do not have pip
        except ImportError:
            logger.info('Could not find a pip version associated with this python executable. Retrieving and installing the latest version...')
            getpip_path = os.path.join(os.path.dirname(__file__), 'getpip.py')
            self._installer(['python', getpip_path], force=True)
            # making sure that we keep the current PYTHONUSERBASE path in our path
            site.addsitedir(site.USER_BASE)
            # import getpip
            # # retrieve pip
            # getpip.main()
            # all good, but you need to restart this process

            logger.warning('Pip 9.0.1 succesfully installed. You may have to rerun this script in order to have it working properly')
            # sys.exit()
            # import pip

        return

    def load_yaml(self):
        # load the yaml file
        # input check
        if not isinstance(self.yaml, basestring) or not os.path.isfile(self.yaml):
            raise IOError('could not understand or find the yaml file. Please make sure to pass the correct path as a string')

        # load the yaml library if you have it, or install it and load it
        if not bool(pkgutil.find_loader('yaml')):
            cmd_line = ['-q', 'pyyaml']
            self._installer(cmd_line, target=os.path.abspath(self.target))
            # add the new path to load yaml
            site.addsitedir(os.path.join(os.path.abspath(self.target), 'Python{0}{1}{2}site-packages'.format(sys.version_info[0], sys.version_info[1], os.sep)))

        try:
            import yaml
        except ImportError:
            raise RuntimeError('Could not load the Pyyaml package. Please check that the module is correctly installed in one of ' + str(sys.path))

        # load the yaml file
        try:
            requirements = yaml.load(open(self.yaml, 'r'), Loader=yaml.FullLoader)
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

    def test_environment(self):
        # test the installed libraries

        # find the right path to look at
        if os.path.isdir(self.lib_folder):
            path = self.lib_folder
        elif os.path.isdir(self.target):
            path = self.target
        else:
            return False

        # find available distros in specified path
        self.avail_modules = {}
        distros = pkg_r.find_distributions(path)
        for d in distros:
            self.avail_modules[d.key] = d.version

        check = []
        # for every package we need to install
        pkgs = self.pkgs if self.pkgs else []
        for p in pkgs:
            # stop if multiple conditions are specified
            if ',' in p:
                raise NotImplementedError('Multiple version conditions not supported. Use abc==0.5.* instead. Encountered with "{0}"'.format(p))
            # loop through every supported comparison operator
            for c in self.supported_version_cmp:
                # split info
                split = p.split(c)
                # if the split was succesful
                if len(split) == 2:
                    n = split[0].lower()
                    v = split[1]
                    break
            # if no split was succesful, assume p has no specific requirements
            else:
                n = p.lower()
                v = None
                c = None

            check.append(self.check_module_availability(n, c, v))

        whls = self.whls if self.whls else []
        for p in whls:
            split = p.split('-')
            if len(split) >= 2:
                n = split[0].lower().replace('_', '-')
                v = split[1]
                c = '=='
            else:
                raise RuntimeError('Could not understand distribution information of wheel {0}'.format(p))
            check.append(self.check_module_availability(n, c, v))

        return all(check)

    def check_module_availability(self, name, condition, version):
        # check if module is available
        isAvail = name in self.avail_modules.keys()
        # if available, time to check the version
        if isAvail:

            # if the target version is not defined, we are already happy
            if version is not None:

                # if we don't have a reference version, conservatively reinstall and complain
                ref_v = self.avail_modules[name]
                if ref_v is None:
                    logger.warning('Found already installed module {0} but could not check its version'.format(name))
                    isAvail = False
                # otherwise, check the version conditions
                else:
                    isAvail = condition in self._compare_versions(ref_v, version)

        logger.debug('{0} {1} {2} available: {3}'.format(name, condition, version, isAvail))
        return isAvail


    @ staticmethod
    def _compare_versions(v_ref, v_target):
        if not isinstance(v_ref, basestring) or not isinstance(v_target, basestring):
            raise TypeError('arguments must be strings')
        # split version info like 1.2.3.4 into ['1', '2', '3', '4']
        v_ref = v_ref.split('.')
        v_target = v_target.split('.')
        l_target = len(v_target)
        l_ref = len(v_ref)

        # make sure that we can compare till the end even if subversions are not specified. zero padding it
        if l_ref > l_target:
            v_target = v_target + ['0'] * (l_ref - l_target)
        elif l_ref < l_target:
            v_ref = v_ref + ['0'] * (l_target - l_ref)

        # this will flag the compatible '~=' condition
        compatible = []
        # iterate through subversions
        for r, t in zip(v_ref, v_target):
            try:
                # try to convert to integer
                r = int(r)
                t = int(t)
            except ValueError:
                # if fails we have a string
                # matching multiple distros (or not if we didn't pass a first subversion test)
                # e.g   1.2 == 1.* and 1.2 ~= 1.*, but 1.2 != *
                if t == '*':
                    return ['==', '~='] if compatible else ['!=']
                # strict string equality
                elif r == t:
                    return ['===', '==']
                # or not
                else:
                    return ['!=']
            # reference is newer
            # e.g.   1.2.3 > 1.2.2
            if r > t:
                return ['>', '>=', '!='] + compatible
            # reference is older
            # e.g.   1.2.3 < 1.2.4
            elif r < t:
                return ['<', '<=', '!='] + compatible
            # we passed at least one test
            compatible = ['~=']
        # reference is the same
        # e.g.   1.2.3 == 1.2.3 and 1.2.0 == 1.2
        return ['==', '<=', '>='] + compatible

    def install_pkgs(self):
        # method to install python packages using pip
        if self.pkgs and len(self.pkgs) > 0:
            cmd_line = ['-q', '--disable-pip-version-check'] + self.pkgs
            # cmd_line = ['-q', '--disable-pip-version-check', '--no-cache-dir', '--target'] + [self.target] + self.pkgs
            self._installer(cmd_line, target=os.path.abspath(self.target), dry_run=self.dry_run)

    def install_whls(self):
        # method to install wheels using pip
        if self.whls and len(self.whls) > 0:
            # cmd_line = ['-q', '--disable-pip-version-check', '--prefix=' + self.target] + self.whls
            cmd_line = ['-q', '--disable-pip-version-check'] + self.whls
            self._installer(cmd_line, target=os.path.abspath(self.target), dry_run=self.dry_run)

    @staticmethod
    def _installer(cmd_line, target=False, force=False, dry_run=False):
        # general method to run the installation
        # prepend the python call
        if not force and not cmd_line[:4] == ['python', '-m', 'pip', 'install']:
            cmd_line = ['python', '-m', 'pip', 'install'] + cmd_line
        if target:
            environ = os.environ.copy()
            environ['PYTHONUSERBASE'] = target
            cmd_line = cmd_line + ['--user']
        else:
            environ = os.environ.copy()
        logger.info('executing ' + ' '.join(cmd_line))
        # run the subprocess
        if not dry_run:
            installer = subprocess.Popen(
                args=cmd_line,
                shell=False,
                env=environ,
                executable=sys.executable,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd()
            )
            # wait for it to complete
            installer.wait()
            # something went wrong
            if installer.returncode > 0:
                raise RuntimeError(str(installer.stderr.read()))

        return


# command line interface
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Utility to install dependencies locally')
    parser.add_argument('-t', '--target', type=str, default='external_libs', help='Folder name to use as target location for the installation')
    parser.add_argument('-w', '--whls', type=str, nargs='+', default=False, help='list of wheels name to install')
    parser.add_argument('-p', '--pkgs', type=str, nargs='+', default=False, help='list of package name to install')
    parser.add_argument('-y', '--yaml', type=str, default=False, help='path to yaml file containing requirements to install')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False, help='dry run only')
    args = parser.parse_args()

    if args.dry_run:
        logger.level = logging.DEBUG
    Installer(target=args.target, whls=args.whls, pkgs=args.pkgs, yaml=args.yaml, dry_run=args.dry_run)
