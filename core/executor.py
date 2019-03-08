import os
import re
import logging
import subprocess
from distutils.spawn import find_executable
logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s: %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class Executor(object):
    cmd_line = False
    executable = False
    cwd = os.getcwd()
    _environ = os.environ.copy()
    logger = logging.getLogger(__name__)

    def __init__(self, cmd_line, executable=False, external_libs=False, cwd=False, logger=False):
        """Initialize the Executor object setting the parameters for the subprocess call

        Arguments:
        -----------
        cmd_line : list of str
            list of strings that will be converted to the command line to run.
            the first item must be the script or exe file
        executable : str, optional (default : False)\n
            path to executable to use. This will default to current python interpreter
            if None, than the first item of cmd_line must be an executable (exe) itself
        external_libs : str or list of str, optional (default : False)\n
            path(s) to external libs folder
            the actual path(s) will be added to the PATH variable for the subprocess call
            other common subfolders (e.g. 'lib', 'bin') may be added if they exists
        cwd : str, optional (default : os.getcwd())
            path to working directory to use for the subprocess call
        logger : logging.Logger, optional (default : False)
            logging.Logger to use for stream handling.
            If False, it will default to an internal logging.Logger
            If None, logging will be disabled for anything but ERROR and CRITICAL levels

        Returns:
        -----------
        out : Executor instance
            Object containing settings (and methods to change them) for the subprocess call. Use Executor.run() to run the task
        """
        # test and set the working directory
        self.set_cwd(cwd)
        # test and set executable, defaulting to python interpreter
        self.set_executable(executable)
        # test and set the command line arguments, adding the executable
        self.set_cmd_line(cmd_line)
        # test and set the external_libs folder
        self.set_external_libs(external_libs)
        # set the logger
        self.set_logger(logger)

    def set_executable(self, executable):
        """Method to set a new executable parameter

        Arguments:
        -----------
        executable : str, False or None
            path to executable
            if False, it will default to current python interpreter
            if None, it will expect the first item in cmd_line to be an executable(.exe) itself
        """
        if executable:
            if not isinstance(executable, (str, unicode)):
                raise TypeError("The 'executable' argument must be a string")
            self.logger.debug('input executable kwd: {0}'.format(executable))
            for exe in [os.path.abspath(executable), os.path.join(self.cwd, executable)]:
                if os.path.isfile(exe) and os.access(exe, os.X_OK):
                    self.logger.debug('found matching executable: {0}'.format(exe))
                    break
            else:
                raise IOError("The 'executable' argument is not pointing to a valid executable program")
            self.executable = exe
        elif executable is None:
            # for .exe
            self.executable = None
        else:
            self.executable = self.find_py_exe(False)

    def set_cmd_line(self, cmd_line):
        """Method to set a new cmd_line parameter

        Arguments:
        -----------
        cmd_line : list of str
            arguments to be converted to command line call
            every item will be threated as a single argument (be mindful of that!)
            the first item will be checked, and it is expected to be a script or your executable.
            In this last case it will trigger a set_executable(None)
        """
        if not isinstance(cmd_line, list):
            raise TypeError("The 'cmd_line' argument must be a list of strings")
        if not all([isinstance(x, (str, unicode)) for x in cmd_line]):
            list_error = ', '.join(['{0}[{1}]'.format(str(a), type(a)) for a in cmd_line])
            raise TypeError("The 'cmd_line' argument must be a list of strings. You passed: {}".format(list_error))
        cmd_line = cmd_line[:]
        script = cmd_line.pop(0)
        for script_path in [os.path.abspath(script), os.path.join(self.cwd, script)]:
            if os.path.isfile(script_path):
                if script_path.endswith('.exe'):
                    self.set_executable(None)
                break
        else:
            if find_executable(script) is not None:
                script_path = find_executable(script)
                if self.executable is not None:
                    if os.path.basename(self.executable) != os.path.basename(script_path):
                        self.set_executable(None)
                    else:
                        script_path = os.path.basename(script_path)
            else:
                raise TypeError('The first argument must be your script/executable. Could not resolve {0}'.format(script))
        self.cmd_line = [script_path] + cmd_line

    def set_cwd(self, cwd):
        """Method to set a new cwd parameter

        Arguments:
        -----------
        cwd : str
            path to new working directory.
            It will be passed to the subprocess call, so make sure that your arguments are specified relatively to this path
        """
        if cwd:
            if not isinstance(cwd, (str, unicode)):
                raise TypeError("the 'cwd' argument must a string")
            if not os.path.isdir(cwd):
                raise IOError("The 'cwd' argument is not a valid directory")
            self.cwd = cwd
        else:
            self.cwd = os.getcwd()

    def set_external_libs(self, external_libs):
        """Method to create a new environment to be passed to the subprocess call

        Arguments:
        -----------
        external_libs : str or list of str
            path(s) to folder containing your libraries.
            Those paths will be prepended to your PATH environmental variable, so will have priority over other locations
            The method will recursively descend this location, searching for specific subfolder (like path/lib/site-packages or path/bin).
            If those are found, they will be added to your PATH
            This script will also generate/modify your PYTHONPATH
        """
        # one path passed
        if isinstance(external_libs, (str, unicode)):
            if not os.path.isdir(external_libs):
                raise IOError("The 'external_libs' argument is not a valid folder")
            self._environ = os.environ.copy()
            self._set_lib_path(os.path.abspath(external_libs))

        # multiple paths passed
        elif isinstance(external_libs, list) and all([isinstance(x, (str, unicode)) for x in external_libs]):
            if not all([os.path.isdir(x) for x in external_libs]):
                raise IOError("The 'external_libs' argument has at least one non-valid folder")
            self._environ = os.environ.copy()
            for p in external_libs[::-1]:
                self._set_lib_path(os.path.abspath(p))

        # no path passed, default to current environment
        elif external_libs is False:
            self._environ = os.environ.copy()
        else:
            raise TypeError("The 'external_libs' argument must be a string or list of strings")

    def set_logger(self, i_logger):
        """Method to set up the Logger used by the object
        
        Arguments:
        -----------
        i_logger : logging.Logger
            Logger to use for stream handling
            if False, it will default to a default internal Logger
            if None, DEBUG, INFO and WARNING will be suppressed, allowing only ERROR and CRITICAL
        """
        if isinstance(i_logger, logging.Logger):
            self.logger = i_logger
        elif i_logger is None:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.ERROR)
        elif i_logger is False:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)

        else:
            raise TypeError("The argument 'logger' must be a Logger object, None or False")

    def info(self):
        """Method to print all parameters
        """
        self.logger.info('Current settings are:')
        self._info_printer('executable', str(self.executable))
        self._info_printer('working directory', str(self.cwd))
        self._info_printer('arguments', self.cmd_line)
        self._info_printer('PATH', self._environ['PATH'].split(';'))
        try:
            self._info_printer('PYTHONPATH', self._environ['PYTHONPATH'].split(';'))
        except KeyError:
            pass
        try:
            self._info_printer('GDAL_DRIVER_PATH', self._environ['GDAL_DRIVER_PATH'].split(';'))
        except KeyError:
            pass
        try:
            self._info_printer('GDAL_DATA', self._environ['GDAL_DATA'].split(';'))
        except KeyError:
            pass

    def _info_printer(self, head, to_print):
        if isinstance(to_print, (str, unicode)):
            self.logger.info('   %-20s: %-20s' % (head, to_print))
        elif isinstance(to_print, list):
            for s in to_print:
                self.logger.info('   %-20s: %-20s' % (head, s))
                head = ''

    def run(self):
        """Execute the task using the current configuration
        It returns a list of string obtained by scanning through the subprocess output stream.
        To have your result path returned in this way, please make sure to print a line matching this pattern: "RESULT: (.*)\\r\\n"
        e.g. INFO:root: 2018-03-06 12:00:00 blabla RESULT: C:/test_data/result_table.xls
        """
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        if self.executable is None or self.cmd_line[0].endswith('.exe'):
            cmd_line = self.cmd_line
        else:
            cmd_line = [os.path.basename(self.executable)] + self.cmd_line
        self.logger.info('Running ' + self.cmd_line[0] + ' externally')
        self.logger.info('   Working directory ' + str(self.cwd))
        self.logger.info('   Executable ' + str(self.executable))
        self.logger.info('   Arguments ' + ' '.join(cmd_line))

        run = subprocess.Popen(
            cmd_line,
            executable=self.executable,
            env=self._environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            cwd=self.cwd
        )

        result = self._stream_handler(run)

        return result

    def _stream_handler(self, popen):
        o, e = popen.communicate()
        results = []

        if popen.returncode > 0:
            if e:
                if o:
                    self.logger.info(' ' * 3 + o.replace('\n', '\n' + ' ' * 3))
                self.logger.error(' ' * 3 + e.replace('\n', '\n' + ' ' * 3))
            raise RuntimeError('Execution could not be completed return code was ' + str(popen.returncode))
        if o:
            self.logger.info(' ' * 3 + o.replace('\n', '\n' + ' ' * 3))
            results = re.findall('RESULT: ([^\r\n]*)', o)
        self.logger.info('Execution completed!')

        if len(results) > 0:
            return results
        return True

    def _set_lib_path(self, extlib_path):
        _path = []
        _pythonpath = []

        if self._check_dir_path(extlib_path):
            _path.extend(self._check_dir_path(extlib_path))  # CONDA PIP

            _pythonpath.extend(self._check_dir_path(os.path.join(extlib_path, 'DLLs')))  # CONDA
            _path.extend(self._check_dir_path(os.path.join(extlib_path, 'bin')))  # CONDA

            lib_path = self._check_dir_path(os.path.join(extlib_path, 'lib'), True)  # CONDA
            if lib_path:
                _pythonpath.append(lib_path)

                _pythonpath.extend(self._check_dir_path(os.path.join(lib_path, 'site-packages')))  # CONDA PIP
                _pythonpath.extend(self._check_dir_path(os.path.join(lib_path, 'lib-tk')))  # CONDA
                _pythonpath.extend(self._check_dir_path(os.path.join(lib_path, 'plat-win')))  # CONDA

            libos_path = self._check_dir_path(os.path.join(extlib_path, 'Library'), True)
            if libos_path:
                _path.append(libos_path)

                _path.extend(self._check_dir_path(libos_path, 'bin'))  # CONDA
                _path.extend(self._check_dir_path(libos_path, 'usr' + os.sep + 'bin'))  # CONDA
                _path.extend(self._check_dir_path(libos_path, 'mingw-w64' + os.sep + 'bin'))  # CONDA

            self.logger.debug('PATH: {0}'.format(str(_path)))
            self.logger.debug('PYTHONPATH: {0}'.format(str(_pythonpath)))
            # special case for pip
            if len(_pythonpath) == 2 and _pythonpath[0] == lib_path:
                _path.extend(_pythonpath)
                _pythonpath = _path

            try:
                self._environ['PATH'] = ';'.join(_path + [self._environ['PATH']]).encode('utf8')
            except KeyError:
                self._environ['PATH'] = ';'.join(_path).encode('utf8')
            try:
                self._environ['PYTHONPATH'] = ';'.join(_pythonpath + [self._environ['PYTHONPATH']]).encode('utf8')
            except KeyError:
                self._environ['PYTHONPATH'] = ';'.join(_pythonpath).encode('utf8')

            # special case for GDAL
            for gdal_path in [os.path.join(os.path.dirname(extlib_path), 'osgeo'), os.path.join(os.path.join(lib_path, 'site-packages'), 'osgeo')]:
                if os.path.isdir(gdal_path):
                    gdal_plugins = self._check_dir_path(os.path.join(gdal_path, 'gdalplugins'), True)
                    gdal_data = self._check_dir_path(os.path.join(gdal_path, 'gdal-data'), True)
                    self._environ['PATH'] = ';'.join([gdal_path, gdal_data, gdal_plugins, self._environ['PATH']]).encode('utf8')
                    self._environ['GDAL_DRIVER_PATH'] = gdal_plugins.encode('utf8')
                    self._environ['GDAL_DATA'] = gdal_data.encode('utf8')
                    break

        else:
            raise IOError('The path {0} could not be found'.format(str(extlib_path)))

    @staticmethod
    def _check_dir_path(p, str=False):
        if os.path.isdir(p):
            if str:
                return p
            return [p]
        else:
            if str:
                return ''
            return []

    @staticmethod
    def find_py_exe(w_exe=False):
        """Utility to find the python or pythonw executable in the ArcGIS environment.

        This is generally achieved by calling sys.executable, but when using ArcMap this variable is assigned to ArcMap.exe
        This tool will import os, then use the os.__file__ variable and walk up its path to find the python.exe

        Arguments:
        -----------
        w_exe : bool
            Return pythonw.exe instead of python.exe (default: False)

        Returns:
        -----------
        out : str
            full path of python executable
        """
        if w_exe:
            exe = ['pythonw.exe']
        else:
            exe = ['python.exe']
        path = []
        for fld in os.__file__.split(os.sep):
            path.append(fld)
            if path[-1].endswith(':'):  # To handle drives, e.g. C:
                path.append(os.sep)
            py_exe_path = os.path.join(*(path + exe))
            if os.path.isfile(py_exe_path):
                return py_exe_path
        raise RuntimeError('Could not find the python executable')
