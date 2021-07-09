import os
import shutil
import sys
import logging
import subprocess
import pkgutil
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
    pythonhome = False
    python_version = 'Python{0}{1}'.format(sys.version_info[0], sys.version_info[1])
    target = os.path.abspath('./external_libs')
    lib_folder = os.path.abspath('./external_libs/{0}/site-packages'.format(python_version))
    path = []
    supported_version_cmp = ['===', '~=', '!=', '==', '<=', '>=', '<', '>']

    # initialise and run
    def __init__(self, target=False, pkgs=False, whls=False, yaml=False, dry_run=False, pythonhome=False):
        logger.info('Building environment for {0} located in {1}'.format(self.python_version, os.path.dirname(os.path.dirname(os.__file__))))
        try:
            # Input checking
            if target:
                if isinstance(target, basestring):
                    self.target = target
                    self.lib_folder = os.path.join(os.path.abspath(self.target), '{0}{1}site-packages'.format(self.python_version, os.sep))
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

            self._override_path()

            if pythonhome and os.path.isdir(pythonhome):
                self.pythonhome = pythonhome
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
            self.test_architecture()

            # find the specified wheels
            self.find_wheels()

            # check wether you have already all the required packages installed in the target folder
            # if os.path.exists(self.target) and (len(os.listdir(self.lib_folder)) > (len(self.whls) + len(self.pkgs))):
            if os.path.exists(self.target):
                logger.info('Checking whether requirements are already satisfied')
                test, missing = self.test_environment()
                if test:
                    logger.info('Found all required packages')
                    answer = 'empty'
                    while answer.lower() not in ['', 'y', 'n']:
                        answer = raw_input('   INPUT   Do you want to re-install those libraries? [y/n]: ')
                    if answer.lower() == 'n':
                        sys.exit()
                else:
                    logger.info('Some of the required packages are missing: {0}'.format(','.join(missing)))
                if not self.dry_run:
                    rmtree(self.target, ignore_errors=True)

            # running the installation
            logger.info('***** Running the installation *****')
            try:
                self.install()
                # self.install_whls()
                # self.install_pkgs()
            except Exception:
                # clean up if something went wrong
                if os.path.isdir(self.target):
                    rmtree(self.target, ignore_errors=True)
                raise
        except Exception:
            logger.exception('Installation failed with the following exception')
            sys.exit(1)  # making sure that we carry over the error outside python


    def _override_path(self):

        python_path = os.path.dirname(sys.executable)

        # check for pth file in python folder
        # this stops from being able to modify PATH using evironmental variables
        for root, dirs, files in os.walk(python_path):
            for f in files:
                if f.endswith('_pth'):
                    pth_moved = f + 'bkp'
                    pth_file = os.path.join(root, f)

                    logger.warning('Found a pth file in you local installation. This is not compatible with xGIS and will be renamed to ' + pth_moved)
                    shutil.move(pth_file, os.path.join(root, pth_moved))
                    # to_add = False
                    # with open(pth_file, 'r') as fl:
                    #     for line in fl.readlines():
                    #         if line == 'import site':
                    #             break
                    #     else:
                    #         to_add=True
                    # if to_add:
                    #     with open(pth_file, 'a') as fl:
                    #         fl.write('import site') # this fixes the environmental lock

        self.path.append(python_path)
        self.path.append(os.path.join(python_path, 'Lib{0}site-packages'.format(os.sep)))
        self.path.append(os.path.join(python_path, 'Scripts'))
        self.path.append(os.path.join(python_path, 'bin'))
        self.path.append(os.path.join(python_path, 'include'))

        logger.debug('self.path is: {0}'.format(self.path))
        if 'PYTHONPATH' not in os.environ:
            pythonpath = [self.path[0]]
        else:
            pythonpath = os.environ['PYTHONPATH'].split(';')
        for p in reversed(self.path):
            if p not in pythonpath:
                pythonpath.insert(0, p)

        os.environ['PYTHONPATH'] = ';'.join(pythonpath)

        logger.debug('updated path is: {0}'.format(os.environ['PYTHONPATH']))

    def find_wheels(self):
        # find the location of specified wheels
        wheels = []
        path = os.path.abspath('.')
        if self.yaml:
            alt_path = os.path.dirname(os.path.abspath(self.yaml))
            if alt_path == path:
                alt_path = None
            else:
                path = '{0} and {1}'.format(path, alt_path)
        else:
            alt_path = None
        logger.debug('Checking for requested wheels in {0}'.format(path))
        for w in self.whls:
            if os.path.isfile(w):
                logger.debug('{0} was found'.format(w))
                wheels.append(w)
            else:
                if alt_path is not None:
                    w_alt = os.path.join(alt_path, w)
                    if os.path.isfile(w_alt):
                        logger.debug('{0} was found'.format(w_alt))
                        wheels.append(w_alt)
                else:
                    logger.debug('{0} was NOT found'.format(w))
                    raise IOError('Could not find the specified wheel {0}. Please place it in the curret directory or beside the requirements file'.format(w))
        self.whls = wheels

    def test_architecture(self):
        # method to test the architecture
        # check if you are running a ArcGIS python and warn if it is not the case
        if 'arcgis' not in sys.executable.lower():
            logging.warning('You are not using the ArcGIS python interpreter. Please be mindful that libraries installed in this way may not be compatible with ArcGIS')
        # we are running a 32bit python
        if sys.maxsize == 2147483647:
            logger.debug('Detected a 32bit interpreter')
            # if whls are for 64bit, raise an error
            if self.whls and any(['amd64' in x for x in self.whls]):
                raise RuntimeError('Detected Python 32bit, but you provided 64 bit wheels. Please run this script with the 64bit Python interpreter')
        # we are running a 64bit python
        elif sys.maxsize == 9223372036854775807:
            logger.debug('Detected a 64bit interpreter')
            # if whls are for 32bit, raise an error
            if self.whls and any(['win32' in x for x in self.whls]):
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
            self._installer(['python', getpip_path])

            # # making sure that we keep the current PYTHONUSERBASE path in our path
            # site.addsitedir(os.path.join(os.path.abspath(self.target), '{0}{1}site-packages'.format(self.python_version, os.sep)))
            site.addsitedir(os.path.join(os.path.dirname(sys.executable), 'Lib{0}site-packages'.format(os.sep)))

            # logger.warning('Pip succesfully installed. You may have to rerun this script in order to have it working properly')

        return

    def load_yaml(self):
        # load the yaml file
        # input check
        if not isinstance(self.yaml, basestring) or not os.path.isfile(self.yaml):
            raise IOError('could not understand or find the yaml file. Please make sure to pass the correct path as a string')

        # load the yaml library if you have it, or install it and load it
        if not bool(pkgutil.find_loader('yaml')):
            cmd_line = ['pyyaml']
            self._installer(cmd_line)
            # add the new path to load yaml
            site.addsitedir(os.path.join(os.path.abspath(self.target), '{0}{1}site-packages'.format(self.python_version, os.sep)))
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

    def _find_distros(self, path):
        # load the pkg_resources library if you have it, or install it and load it
        
        if not bool(pkgutil.find_loader('pkg_resources')):
            cmd_line = ['-q', 'pkg_resources']
            self._installer(cmd_line)
            # add the new path to load pkg_resources
            site.addsitedir(os.path.join(os.path.abspath(self.target), '{0}{1}site-packages'.format(self.python_version, os.sep)))
        try:
            import pkg_resources as pkg_r
        except ImportError:
            raise RuntimeError('Could not load the pkg_resources package. Please check that the module is correctly installed in one of ' + str(sys.path))
        return pkg_r.find_distributions(path)


    def test_environment(self):
        # test the installed libraries

        # find the right path to look at
        if os.path.isdir(self.lib_folder):
            path = self.lib_folder
        elif os.path.isdir(self.target):
            path = self.target
        else:
            return False

        logger.debug('looking into {0} for libraries'.format(path))
        # find available distros in specified path
        self.avail_modules = {}
        distros = self._find_distros(path)
        for d in distros:
            self.avail_modules[d.key] = d.version

        logger.debug('Found those modules: {0}'.format(self.avail_modules))

        check = []
        missing = []
        # for every package we need to install
        pkgs = self.pkgs if self.pkgs else []
        logger.debug('Checking packages:{0}'.format(pkgs))
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
                    n = split[0].lower()  # name
                    v = split[1]  # version
                    break
            # if no split was succesful, assume p has no specific requirements
            else:
                n = p.lower()
                v = None
                c = None

            if self.check_module_availability(n, c, v):
                check.append(True)
                self.pkgs.remove(p)
            else:
                check.append(False)
                missing.append(p)

        whls = self.whls if self.whls else []
        logger.debug('Checking wheels:{0}'.format(whls))
        for p in whls:
            split = p.split('-')
            if len(split) >= 2:
                n = split[0].lower().replace('_', '-')
                v = split[1]
                c = '=='
            else:
                raise RuntimeError('Could not understand distribution information of wheel {0}'.format(p))
            if self.check_module_availability(n, c, v):
                check.append(True)
            else:
                check.append(False)
                missing.append(p)

        return all(check), missing

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

    def install(self):
        cmd_line = ['--disable-pip-version-check']
        if self.pkgs and len(self.pkgs) > 0:
            cmd_line += self.pkgs
        if self.whls and len(self.whls) > 0:
            cmd_line += self.whls
        self._installer(cmd_line)

    def install_pkgs(self):
        # method to install python packages using pip
        if self.pkgs and len(self.pkgs) > 0:
            cmd_line = ['--disable-pip-version-check'] + self.pkgs
            # cmd_line = ['-q', '--disable-pip-version-check', '--no-cache-dir', '--target'] + [self.target] + self.pkgs
            self._installer(cmd_line)

    def install_whls(self):
        # method to install wheels using pip
        if self.whls and len(self.whls) > 0:
            # cmd_line = ['-q', '--disable-pip-version-check', '--prefix=' + self.target] + self.whls
            cmd_line = ['--disable-pip-version-check'] + self.whls
            self._installer(cmd_line)

    def _installer(self, cmd_line):
        # general method to run the installation
        # prepend the python call
        logger.debug(cmd_line)
        if not cmd_line[-1].endswith('.py') and not cmd_line[:4] == ['python', '-m', 'pip', 'install']:
            cmd_line = ['python', '-m', 'pip', 'install'] + cmd_line
        if self.target:
            environ = os.environ.copy()
            environ['PYTHONUSERBASE'] = self.target
            # dealing with PYTHONHOME
            if self.pythonhome:
                environ['PYTHONHOME'] = self.pythonhome
            # special case for qgis
            elif 'qgis' in sys.executable.lower():
                pythonhome = os.path.dirname(os.path.dirname(sys.executable))
                pythonhome = os.path.join(pythonhome, 'apps' + os.sep + self.python_version)
                environ['PYTHONHOME'] = pythonhome
            
            # TODO review this case
            else:
                try:
                    del environ['PYTHONHOME']
                except KeyError:
                    pass
            
            if not cmd_line[-1].endswith('.py'):
                cmd_line = cmd_line + ['--user', '--upgrade', '--force-reinstall']
        else:
            environ = os.environ.copy()
        
        logger.debug(environ)
        logger.info('executing ' + ' '.join(cmd_line))
        # run the subprocess
        if not self.dry_run:
            installer = subprocess.Popen(
                args=cmd_line,
                shell=False,
                env=environ,
                executable=sys.executable,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=os.getcwd()
            )

            while True:
                nextline = installer.stdout.readline().decode("utf-8").replace('\n', '')
                if nextline == '' and installer.poll() is not None:
                    break
                if nextline != '':
                    logger.debug(nextline)
            installer.poll()
                # wait for it to complete
            # something went wrong
            if installer.returncode > 0:
                raise RuntimeError(str(installer.stdout.read()))

        return

def _find_best_version(options, major=False, minor=False, bit=False):
    newer_version = {
        'major': 0,
        'minor': 0,
        'bit': 0,
        'path': None
    }

    for opt in options:
        if any([major, minor, bit]):
            if (not major or opt['major'] == major) and (not minor or opt['minor'] == minor) and (not bit or opt['bit'] == bit):
                pass
            else:
                continue
        if opt['major'] > newer_version['major']:
            newer_version = opt
        elif opt['major'] < newer_version['major']:
            continue
        else:
            if opt['minor'] > newer_version['minor']:
                newer_version = opt
            elif opt['minor'] < newer_version['minor']:
                continue
            else:
                if opt['bit'] > newer_version['bit']:
                    newer_version = opt
                elif opt['bit'] < newer_version['bit']:
                    continue
    return newer_version


def find_arcgis_env(major=False, minor=False, bit=False, python_version=False):
    import re
    import operator
    basepath = 'C:\\Python27'
    exes = []

    if python_version == 3:
        raise NotImplementedError("ArcGIS support is currently limited to ArcGIS Desktop. This offers only Python 2 environments")
    if os.path.isdir(basepath):
        for p in os.listdir(basepath):
            if 'arcgis' in p.lower():
                py_path = os.path.join(os.path.join(basepath, p), 'python.exe')
                if os.path.isfile(py_path):
                    info = re.search('.*ArcGIS(x64)?([0-9]*)\.([0-9]*)', p)
                    if info is None:
                        raise RuntimeError('Could not understand the ArcGIS version of: ' + p)
                    exe_info = {
                        'major': int(info.group(2)),
                        'minor': int(info.group(3)),
                        'bit': 32 if info.group(1) is None else 64,
                        'path' : py_path
                    }
                    exes.append(exe_info)
    return _find_best_version(exes, major, minor, bit)['path']


def find_qgis_env(major=False, minor=False, bit=False, python_version=False):
    from distutils.spawn import find_executable
    import re
    qgis_path = find_executable('qgis-bin.exe')
    if qgis_path is not None:
        info = re.search('.*(x86)?.*QGIS\s([0-9]*)\.([0-9]*).*', qgis_path)
        if info is None:
            raise RuntimeError('Could not understand the QGIS version of: ' + qgis_path)

        exe_info = {
            'major': int(info.group(2)),
            'minor': int(info.group(3)),
            'bit': 64 if info.group(1) is None else 32,
            'path':None
        }
        if python_version == 2:
            py_path = os.path.join(os.path.dirname(qgis_path), 'python.exe')
        else:
            py_path = os.path.join(os.path.dirname(qgis_path), 'python3.exe')
        if os.path.isfile(py_path):
            exe_info['path'] = py_path

        return _find_best_version([exe_info], major, minor, bit)['path']


# command line interface
if __name__ == '__main__':
    import argparse

    utility_parser = argparse.ArgumentParser(add_help=False)
    utility_group = utility_parser.add_argument_group('Utilities')
    utility_group.add_argument('--find_arcgis_env', action='store_true', default=False, help='Finds and returns the path of the requested ArcGIS Python environment')
    utility_group.add_argument('--find_qgis_env', action='store_true', default=False, help='Finds and returns the path of the requested QGIS Python environment')
    utility_group.add_argument('--major', type=int, default=False, help='Major version of ArcGIS/QGIS to search')
    utility_group.add_argument('--minor', type=int, default=False, help='Minor version of ArcGIS/QGIS to search')
    utility_group.add_argument('--python_major', type=int, default=2, choices=[2,3], help='Major Python version of the ArcGIS/QGIS environment to search')
    utility_group.add_argument('--bit', type=int, choices = [32, 64], default=False, help='Architecture of ArcGIS/QGIS to search')


    parser = argparse.ArgumentParser(description='Utility to install dependencies locally', parents=[utility_parser])
    parser.add_argument('-t', '--target', type=str, default='external_libs', help='Folder name to use as target location for the installation')
    parser.add_argument('-w', '--whls', type=str, nargs='+', default=False, help='list of wheels name to install')
    parser.add_argument('-p', '--pkgs', type=str, nargs='+', default=False, help='list of package name to install')
    parser.add_argument('-y', '--yaml', type=str, default=False, help='path to yaml file containing requirements to install')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False, help='run the installation with logging level set to DEBUG output')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False, help='dry run only')
    parser.add_argument('--pythonhome', type=str, default=False, help='option to define a custom python home to allow full support for non default python installations')
    args = parser.parse_args()

    if args.find_arcgis_env:
        path = find_arcgis_env(args.major, args.minor, args.bit, args.python_major)
        if path:
            print(path)

    elif args.find_qgis_env:
        path = find_qgis_env(args.major, args.minor, args.bit, args.python_major)
        if path:
            print(path)

    else:
        if args.dry_run or args.verbose:
            logger.level = logging.DEBUG
            
        Installer(target=args.target, whls=args.whls, pkgs=args.pkgs, yaml=args.yaml, dry_run=args.dry_run, pythonhome=args.pythonhome)
