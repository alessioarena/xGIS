import os
import sys
import re
import logging
import subprocess
from distutils.spawn import find_executable
try:
    import arcpy
    arcpy.env.autoCancelling = False
except ImportError:
    pass
import ARClogger
module_logger = ARClogger.initialise_logger(to_file=False, force=False)


class Executor(object):
    cmd_line = False
    executable = False
    cwd = os.getcwd()
    _environ = os.environ.copy()
    logger = module_logger

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

    def _check_paths(self, dir, is_file=False, is_dir=False, is_executable=False):
        if (is_file + is_dir + is_executable) != 1:
            raise ValueError("Only one of 'is_file', 'is_folder' and 'is_executable' can be passed")
        else:
            if is_file:
                test = lambda x: os.path.isfile(x)  # noqa: E731
                test_str = 'file'
            elif is_dir:
                test = lambda x: os.path.isdir(x)  # noqa: E731
                test_str = 'directory'
            else:
                test = lambda x: os.path.isfile(x) and os.access(x, os.X_OK)  # noqa: E731
                test_str = 'executable'
        # testing both the 'local' path and the 'working directory' one
        for d in [os.path.abspath(dir), os.path.join(self.cwd, dir)]:
            if test(d):
                return d
        else:
            raise IOError("The argument '{0}' is not pointing to a valid {1}".format(dir, test_str))

    def set_executable(self, executable):
        """Method to set a new executable parameter

        Arguments:
        -----------
        executable : str, False or None
            path to executable
            if False, it will default to current python interpreter
            if None, it will expect the first item in cmd_line to be an executable(.exe) itself
        """
        # if we pass a value
        if isinstance(executable, (str, unicode)):
            self.logger.debug('input executable kwd: {0}'.format(executable))
            # test if exists and can be executed
            exe = self._check_paths(executable, is_executable=True)
            self.logger.debug('found matching executable: {0}'.format(exe))
            # assign
            self.executable = exe
        # if we don't want one (the script IS the executable)
        elif executable is None:
            self.executable = None
        # if we want the dafault one
        elif executable is False:
            try:
                # search for the one closest to the library os
                self.executable = self.find_py_exe(False)
            except RuntimeError:
                # if we don't find one, try using sys.executable (this fails in ArcMap)
                self.executable = sys.executable
        else:
            raise TypeError("The executable argument must be a string, None or False")

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
        # args must be a list
        if not isinstance(cmd_line, list):
            raise TypeError("The 'cmd_line' argument must be a list of strings")
        # in fact must be a list of strings
        if not all([isinstance(x, (str, unicode)) for x in cmd_line]):
            list_error = ', '.join(['{0}[{1}]'.format(str(a), type(a)) for a in cmd_line])
            raise TypeError("The 'cmd_line' argument must be a list of strings. You passed: {}".format(list_error))
        cmd_line = cmd_line[:]  # to copy the list
        script = cmd_line.pop(0)  # remove the first argument (script/executable) for testing
        try:
            # is this in any of the folders we know?
            script_path = self._check_paths(script, is_file=True)
            # it exists, and it is an executable itself, so we need to remove the attribute executable
            if script_path.endswith('.exe'):
                self.set_executable(None)
        except IOError:
            # We could not find it in the folders we know, so let's do a system-wide search
            script_path = find_executable(script)
            if script_path is None:
                raise TypeError('The first argument must be your script/executable. Could not resolve {0}'.format(script))
            # found it!
            if self.executable is not None:
                # this is to handle the case when we pass 'python.exe', but we specified one that is different than the one that find_executable returned
                if os.path.basename(self.executable) != os.path.basename(script_path):
                    self.set_executable(None)
                else:
                    # python.exe exists, but we want to use a different one
                    script_path = os.path.basename(script_path)

        # adding back the first item as an absolute path
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
            # check the path and assign it
            self.cwd = self._check_paths(cwd, is_dir=True)
        else:
            # default to current working directory
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
            # check the path
            external_libs = self._check_paths(external_libs, is_dir=True)
            # copy the environment
            self._environ = os.environ.copy()
            # now let's add the path_to_libraries that we know
            self._set_lib_path(external_libs)

        # multiple paths passed
        elif isinstance(external_libs, list) and all([isinstance(x, (str, unicode)) for x in external_libs]):
            external_libs_copy = external_libs[:]  # to make a copy
            external_libs = []
            for e_l in external_libs_copy:
                try:
                    external_libs.append(self._check_paths(e_l, is_dir=True))
                except IOError:
                    raise IOError("The 'external_libs' argument has at least one non-valid folder. Couldn't resolve {0}".format(e_l))

            self._environ = os.environ.copy()
            for p in external_libs[::-1]:
                self._set_lib_path(os.path.abspath(p))

        # no path passed, default to current environment
        elif external_libs is False:
            # default to a copy of the current environment
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
            # assigning the input logger
            self.logger = i_logger
        elif i_logger is None:
            # using the default one but muted for INFO, DEBUG and WARNING
            self.logger = module_logger
            self.logger.setLevel(logging.ERROR)
        elif i_logger is False:
            # using the default one
            self.logger = module_logger
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
        # head is the line header, like PATH or "working directory"
        # to_print is the list of info to print
        if isinstance(to_print, (str, unicode)):
            self.logger.info('   %-20s: %-20s' % (head, to_print))
        elif isinstance(to_print, list):
            # splitting them into multiple lines
            for s in to_print:
                self.logger.info('   %-20s: %-20s' % (head, s))
                # removing the line header after the first line
                head = ''

    def run(self):
        """Execute the task using the current configuration
        It returns a list of string obtained by scanning through the subprocess output stream.
        To have your result path returned in this way, please make sure to print a line matching this pattern: "RESULT: (.*)\\r\\n"
        e.g. INFO:root: 2018-03-06 12:00:00 blabla RESULT: C:/test_data/result_table.xls
        """
        # setting up some stuff to hide cmd windows if necessary
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        # set subprocess arguments
        if self.executable is None or self.cmd_line[0].endswith('.exe'):
            cmd_line = self.cmd_line
        else:
            cmd_line = [os.path.basename(self.executable)] + self.cmd_line
        # print execution parameters
        self.logger.info('Running ' + self.cmd_line[0] + ' externally')
        self.logger.info('   Working directory ' + str(self.cwd))
        self.logger.info('   Executable ' + str(self.executable))
        self.logger.info('   Arguments ' + ' '.join(cmd_line))

        # start the non-blocking subprocess
        run = subprocess.Popen(
            cmd_line,
            executable=self.executable,
            env=self._environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            cwd=self.cwd
        )

        try:
            # monitor the process in parallel, printing the output stream as it comes
            result = self._stream_handler(run)
        except KeyboardInterrupt:  # handle user cancellation
            run.kill()
            try:
                # restore the autoCancelling function in ArcGIS
                arcpy.env.autoCancelling = True
            except:
                pass
            raise
        return result

    def _stream_handler(self, popen):
        results = []
        # monitor and print output stream as it comes
        for l, r in self._print_stream(popen.stdout):
            self.logger.info('   {0}'.format(l))
            results.extend(r)
            try:
                # check if user cancelled in ArcGIS
                if arcpy.env.isCancelled:
                    self.logger.warning('Detected user cancellation')
                    raise KeyboardInterrupt
            except (NameError, AttributeError):
                pass

        # check the return code for abnormal termination
        if popen.returncode > 0:
            # if this is the case, print the error stream as well
            for l, _ in self._print_stream(popen.stderr):
                self.logger.error('   {0}'.format(l))

            # raise the error code
            raise subprocess.CalledProcessError(popen.returncode)
        else:
            # all good!
            self.logger.info('Execution completed!')

        try:
            arcpy.env.autoCancelling = True
        except:
            pass
        if len(results) > 0:
            return results
        return True

    @staticmethod
    def _print_stream(stream):
        # this is a non-blocking generator that monitors the stream till it reaches the end (end of execution)
        if stream:
            for line in iter(stream.readline, ""):
                result = re.findall('RESULT: ([^\r\n]*)', line)
                yield line, result
            stream.close()

    def _set_lib_path(self, extlib_path):
        _path = []
        _pythonpath = []

        if self._check_dir_path(extlib_path):
            # C://Tests/blabla/external_libs
            _path.extend(self._check_dir_path(extlib_path))  # CONDA PIP

            # C://Tests/blabla/external_libs/DLLs
            _pythonpath.extend(self._check_dir_path(os.path.join(extlib_path, 'DLLs')))  # CONDA
            # C://Tests/blabla/external_libs/bin
            _path.extend(self._check_dir_path(os.path.join(extlib_path, 'bin')))  # CONDA

            # C://Tests/blabla/external_libs/lib
            lib_path = self._check_dir_path(os.path.join(extlib_path, 'lib'), True)  # CONDA
            if lib_path:
                _pythonpath.append(lib_path)

                # C://Tests/blabla/external_libs/lib/site-packages
                _pythonpath.extend(self._check_dir_path(os.path.join(lib_path, 'site-packages')))  # CONDA PIP
                # C://Tests/blabla/external_libs/lib/lib-tk
                _pythonpath.extend(self._check_dir_path(os.path.join(lib_path, 'lib-tk')))  # CONDA
                # C://Tests/blabla/external_libs/lib/plat-win
                _pythonpath.extend(self._check_dir_path(os.path.join(lib_path, 'plat-win')))  # CONDA

            # C://Tests/blabla/external_libs/Library
            libos_path = self._check_dir_path(os.path.join(extlib_path, 'Library'), True)
            if libos_path:
                _path.append(libos_path)

                # C://Tests/blabla/external_libs/Library/bin
                _path.extend(self._check_dir_path(libos_path, 'bin'))  # CONDA
                # C://Tests/blabla/external_libs/Library/usr/bin
                _path.extend(self._check_dir_path(libos_path, 'usr' + os.sep + 'bin'))  # CONDA
                # C://Tests/blabla/external_libs/Library/mingw-w64/bin
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
            # C://Tests/blabla/external_libs/osgeo or
            # C://Tests/blabla/external_libs/site-packages/osgeo
            for gdal_path in [os.path.join(os.path.dirname(extlib_path), 'osgeo'), os.path.join(os.path.join(lib_path, 'site-packages'), 'osgeo')]:
                if os.path.isdir(gdal_path):
                    # C://Tests/blabla/external_libs/osgeo/gdalplugins or
                    # C://Tests/blabla/external_libs/site-packages/osgeo/gdalplugins
                    gdal_plugins = self._check_dir_path(os.path.join(gdal_path, 'gdalplugins'), True)
                    # C://Tests/blabla/external_libs/osgeo/gdal-data or
                    # C://Tests/blabla/external_libs/site-packages/osgeo/gdal-data
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
        os_path = os.__file__.split(os.sep)
        path = os_path[:-1]
        # to handle the drive in a cmd compatible way (C:// and not C:)
        for i, p in enumerate(os_path):
            if p.endswith(':'):
                path[i] = p + os.sep
        # loop through the directory from os to system dirve
        while len(path) > 0:
            py_exe_path = os.path.join(*path + exe)
            if os.path.isfile(py_exe_path):
                return py_exe_path
            path.pop(-1)
        raise RuntimeError('Could not find the python executable')
