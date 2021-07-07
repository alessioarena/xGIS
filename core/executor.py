import os
import sys
import re
import logging
import subprocess
from queue import Queue, Empty
from threading import Thread
from distutils.spawn import find_executable
from time import sleep
from . import embedded_python_path  #this is to support embedded python, will be False if none is found
try:
    import arcpy # noqa
except ImportError:
    pass

try:
    import qgis # noqa
except ImportError:
    pass
from . import log_utils
module_logger = log_utils.logger

# for python 2 and python 3 compatibility
try:
    # python 2
    basestring
except NameError:
    # python 3
    basestring = (str, bytes)


class ExternalExecutionError(Exception):
    # custom error for abnormal process termination
    def __init__(self, message, errno=1):
        super(ExternalExecutionError, self).__init__(message)
        self.errno = errno


# to support Qgis background task system
if 'qgis' in locals():
    from qgis.core import QgsApplication, QgsTask, QgsVectorLayer, QgsRasterLayer
    from qgis.utils import iface

    # this is a modified QgsTask that supports subprocess execution
    class QgsExecutorTask(QgsTask):
        iface = iface
        def __init__(self, description, popen_args, stream_handler, logger, post_task_function=False):
            super().__init__(description, QgsTask.CanCancel)
            if not isinstance(popen_args, dict):
                raise TypeError('popen_args must be a dictionary')
            self.popen_args = popen_args
            self.stream_handler = stream_handler
            self.logger = logger
            self.exception = None
            self.output = []
            self.post_task_function = post_task_function

        def run(self):

            popen = subprocess.Popen(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **self.popen_args
            )

            self.logger.info('   ***** SubProcess Started *****')
            try:
                result = self.stream_handler(popen, self.logger, self.isCanceled)
            except KeyboardInterrupt:
                popen.kill()
                self.logger.info('   ***** SubProcess Killed *****')
                return False
            except Exception as exception:
                self.exception = exception
                return False

            if not isinstance(result, list):
                self.output = []
            else:
                self.output = result

            return True

        def finished(self, result):
            if result:
                self.logger.info('Task succesfully Completed')
                if self.post_task_function:
                    output = self.post_task_function(self.output)
                else:
                    output = self.output

                # if I can detect a QGIS graphic interface
                for r in output:
                    if os.path.exists(r):
                        name = os.path.basename(r)
                        self.logger.info('Trying to load the result: {0}'.format(r))
                        layer = QgsVectorLayer(r, name)
                        if layer.isValid():
                            self.iface.addVectorLayer(r, name, 'ogr')
                        else:
                            layer = QgsRasterLayer(r)
                            if layer.isValid():
                                self.iface.addRasterLayer(r, name)

            else:
                if self.exception:
                    try:
                        raise self.exception
                    except Exception:
                        self.logger.exception("Task failed with the following error")
                else:
                    self.logger.warning('Task cancelled or finished unexpectedly')


class Executor(object):
    cmd_line = False
    executable = False
    cwd = os.getcwd()
    _environ = os.environ.copy()
    logger = module_logger
    host = None
    post_task_function = False
    task_id = None

    # initialise
    def __init__(self, cmd_line, executable=False, external_libs=False, cwd=False, logger=False, post_task_function=False):
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
        post_task_function : callable, optional (default : False)
            Only for QGIS. This function will be called once the background task is finished.
            Input to this function will be a list of string as returned from the Executor.run function.
            Output of this function can be a list of strings representing path of files to load back in QGIS

        Returns:
        -----------
        out : Executor instance
            Object containing settings (and methods to change them) for the subprocess call. Use Executor.run() to run the task
        """

        # detect the host
        self.detect_host()
        # set the post_task_function as required
        self.set_post_task_function(post_task_function)
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




    # method to set the host attribute (currently only arcgis)
    def detect_host(self):
        try:
            arcpy
            self.host = 'arcgis'
        except NameError:
            pass

        try:
            qgis
            self.host = 'qgis'
        except NameError:
            pass

    # general internal method to check input path
    def _check_paths(self, dir, is_file=False, is_dir=False, is_executable=False):
        if (is_file + is_dir + is_executable) != 1:
            raise ValueError("Only one of 'is_file', 'is_folder' and 'is_executable' can be passed")
        else:
            # set the test function
            if is_file:
                test = lambda x: os.path.isfile(x)  # noqa: E731
                test_str = 'file'
            elif is_dir:
                test = lambda x: os.path.isdir(x)  # noqa: E731
                test_str = 'directory'
            else:
                test = lambda x: os.path.isfile(x) and os.access(x, os.X_OK)  # noqa: E731
                test_str = 'executable'
        # run the test function
        # testing both the 'local' path and the 'working directory' one
        for d in [os.path.abspath(dir), os.path.join(self.cwd, dir)]:
            if test(d):
                return d
        else:
            raise IOError("The argument '{0}' is not pointing to a valid {1}".format(dir, test_str))

    # method to set the post_task_function (QGIS only)
    def set_post_task_function(self, function):
        if function is False or self.host != 'qgis':
            pass
        else:
            if callable(function):
                self.post_task_function = function
            else:
                raise TypeError('The argument post_task_function must be a callable or False')

    # method to set the executable
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
        if isinstance(executable, basestring):
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
            if embedded_python_path:
                self.executable = embedded_python_path
            else:
                try:
                    # search for the one closest to the library os
                    self.executable = self.find_py_exe(False)
                except RuntimeError:
                    # if we don't find one, try using sys.executable (this fails in ArcMap)
                    self.executable = sys.executable
        else:
            raise TypeError("The executable argument must be a string, None or False")

        # deleting the PYTHONHOME variable to avoid it being prepended
        # as this is set up by the host, it may not match the execution service
        if 'python' in self.executable:
            try:
                del self._environ['PYTHONHOME']
            except KeyError:
                pass

    # method to set the list of command line arguments
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
        if not all([isinstance(x, basestring) for x in cmd_line]):
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

    # method to set the working directory
    def set_cwd(self, cwd):
        """Method to set a new cwd parameter

        Arguments:
        -----------
        cwd : str
            path to new working directory.
            It will be passed to the subprocess call, so make sure that your arguments are specified relatively to this path
        """
        if cwd:
            if not isinstance(cwd, basestring):
                raise TypeError("the 'cwd' argument must a string")
            # check the path and assign it
            self.cwd = self._check_paths(cwd, is_dir=True)
        else:
            # default to current working directory
            self.cwd = os.getcwd()

    # method to set the path and subpaths to directory containing a local installation of libraries
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
        if isinstance(external_libs, basestring):
            # check the path
            external_libs = self._check_paths(external_libs, is_dir=True)
            # copy the environment
            self._environ = os.environ.copy()
            # now let's add the path_to_libraries that we know
            self._set_lib_path(external_libs)

        # multiple paths passed
        elif isinstance(external_libs, list) and all([isinstance(x, basestring) for x in external_libs]):
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
        # set a flag for the child process
        # this needs to be done last
        self._environ['xGIS_child'] = "True"

    # method to set the logger that will handle streams at the host level
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

    # method to summarise attributes currently set for this instance
    def info(self):
        """Method to print all parameters
        """
        self.logger.info('Current settings are:')
        self._info_printer('executable', str(self.executable))
        self._info_printer('working directory', str(self.cwd))
        self._info_printer('arguments', self.cmd_line)
        self._info_printer('PATH', str(self._environ['PATH']).split(';'))
        try:
            self._info_printer('PYTHONPATH', str(self._environ['PYTHONPATH']).split(';'))
        except KeyError:
            pass
        try:
            self._info_printer('GDAL_DRIVER_PATH', str(self._environ['GDAL_DRIVER_PATH']).split(';'))
        except KeyError:
            pass
        try:
            self._info_printer('GDAL_DATA', str(self._environ['GDAL_DATA']).split(';'))
        except KeyError:
            pass

    # internal method to print the info
    def _info_printer(self, head, to_print):
        # head is the line header, like PATH or "working directory"
        # to_print is the list of info to print
        if isinstance(to_print, basestring):
            self.logger.info('   %-20s: %-20s' % (head, to_print))
        elif isinstance(to_print, list):
            # splitting them into multiple lines
            for s in to_print:
                self.logger.info('   %-20s: %-20s' % (head, s))
                # removing the line header after the first line
                head = ''

    # context manager used for the run method
    def _host_management(run_func):
        # This will help with temporary settings for the run depending on your host
        def do_context(self):
            try:
                if self.host == 'arcgis':
                    arcpy.env.autoCancelling = False
                    def cancel_test():
                        return arcpy.env.isCancelled
                else:
                    cancel_test = False
                result = run_func(self, cancel_test=cancel_test)
                return result
            finally:
                if self.host == 'arcgis':
                    arcpy.env.autoCancelling = True
        return do_context



    # core method
    @_host_management
    def run(self, cancel_test=False):
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

        popen_args = {
            'args': cmd_line,
            'executable': self.executable,
            'env': self._environ,
            'startupinfo': startupinfo,
            'cwd': self.cwd
        }

        if self.host == 'qgis':
            globals()['qgis_executor_task'] = QgsExecutorTask('QgsExecutorTask', popen_args, self._stream_handler, self.logger, post_task_function=self.post_task_function)
            self.task_id = QgsApplication.taskManager().addTask(globals()['qgis_executor_task'])

            if self.task_id == 0:
                raise RuntimeError('The background task could not be added')
            else:
                self.logger.info('Task {0} scheduled'.format(self.task_id))
        else:
            # start the non-blocking subprocess
            run = subprocess.Popen(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **popen_args
            )

            self.logger.info('   ***** SubProcess Started *****')
            try:
                # monitor the process in parallel, printing the output stream as it comes
                result = self._stream_handler(run, self.logger, cancel_test)
            except KeyboardInterrupt:  # handle user cancellation
                run.kill()
                self.logger.info('   ***** SubProcess Killed *****')
                raise
            return result



    # internal handler that monitors stdout, cancels the job following user request and print stderr as required
    def _stream_handler(self, popen, logger, cancel_test):
        results = []
        if not cancel_test:
            def cancel_test():
                return False
        # queue for asyncronous message parsing
        log_queue = Queue()
        # this thread will monitor the stdout of the external process and append messages to the queue
        producer_thread = Thread(target=self._print_stream, args=(popen.stdout, log_queue))
        producer_thread.setDaemon(True)
        producer_thread.start()
        while True:
            # try to retrieve a message from the queue, but if it is empty keep going
            try:
                l, r = log_queue.get_nowait()
                if bool(l):
                    logger.info('   {0}'.format(l))
                elif bool(r):
                    results.extend(r)
            except Empty:
                pass

            # test for user cancellation asyncronously
            if cancel_test():
                logger.warning('   Detected user cancellation')
                raise KeyboardInterrupt
            # the external executing is completed
            if popen.poll() is not None:
                break

        # check the return code for abnormal values
        if popen.returncode > 0:
            logger.warning('   ***** SubProcess Failed *****')
            # if this is the case, print the error stream as well
            for l, _ in Executor._print_stream(popen.stderr):
                if bool(l):
                    logger.warning('   {0}'.format(l))  # TODO ArcGIS exits after the first AddError is called. Need to find a solution to still print the entire traceback to stderr

            # raise the error code
            sys.tracebacklimit = 0
            raise ExternalExecutionError('External execution failed with exit code {0}'.format(popen.returncode), popen.returncode)
        else:
            # all good!
            logger.info('   ***** SubProcess Completed *****')
            logger.info('   ******* powered by xGIS ********')
            logger.info('   ******* check it out at ********')
            logger.info('  https://github.com/alessioarena/xGIS')

        if len(results) > 0:
            return results
        return True

    # internal printer generator used in _stream_handler
    @staticmethod
    def _print_stream(stream, log_queue=False):
        # this is a non-blocking generator that monitors the stream till it reaches the end (end of execution)
        if stream:

            # commpile an ad-hoc function to read lines from stream and convert them if necessary
            # this is to support Python 2 (returns strings i.e. "") and Python3 (returns byte i.e. b"")
            def _line_converter():
                line = stream.readline()
                if hasattr(line, 'decode'):
                    line = line.decode('utf-8')
                return line

            # if we have a queue, use that to pass the messages
            if log_queue is not False:
                for line in iter(_line_converter, ""):
                    result = re.findall('RESULT: ([^\r\n]*)', line)
                    if result:
                        log_queue.put(('', result))
                    else:
                        log_queue.put((line, ''))
            # otherwise we assume that the stream is now closed and we just need to read the lines
            # return an iterator to use with for loop
            else:
                return [(line, '') for line in iter(_line_converter, "")]


    # internal method to discover and set subpath for the external libraries. This will modify the environment copy
    def _set_lib_path(self, extlib_path):
        _path = []
        _pythonpath = []

        if self._check_dir_path(extlib_path):
            # C://Tests/blabla/external_libs
            _path.extend(self._check_dir_path(extlib_path))  # CONDA PIP
            # C://Tests/blabla/external_libs/Python27/site-packages
            for f in os.listdir(extlib_path):
                if f.startswith('Python'):
                    extlib_path_distro = os.path.join(extlib_path, f + os.sep + 'site-packages')
                    _pythonpath.extend(self._check_dir_path(extlib_path_distro))
                    _path.extend(self._check_dir_path(os.path.join(extlib_path, 'Scripts')))

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
                self._environ['PATH'] = ';'.join(_path + [self._environ['PATH']])#.encode('utf8')
            except KeyError:
                self._environ['PATH'] = ';'.join(_path)#.encode('utf8')
            try:
                self._environ['PYTHONPATH'] = ';'.join(_pythonpath + [self._environ['PYTHONPATH']])#.encode('utf8')
            except KeyError:
                self._environ['PYTHONPATH'] = ';'.join(_pythonpath)#.encode('utf8')

            # special case for GDAL
            # C://Tests/blabla/external_libs/osgeo or
            # C://Tests/blabla/external_libs/site-packages/osgeo
            gdal_optional_paths = [
                os.path.join(os.path.dirname(extlib_path), 'osgeo'),
                os.path.join(os.path.join(lib_path, 'site-packages'), 'osgeo'),
            ]
            # C://Tests/blabla/external_libs/Python27/site-packages/osgeo
            if extlib_path_distro:
                gdal_optional_paths.append(os.path.join(extlib_path_distro, 'osgeo'))
            for gdal_path in gdal_optional_paths:
                if os.path.isdir(gdal_path):
                    # C://Tests/blabla/external_libs/osgeo/gdalplugins or
                    # C://Tests/blabla/external_libs/site-packages/osgeo/gdalplugins
                    gdal_plugins = self._check_dir_path(os.path.join(gdal_path, 'gdalplugins'), True)
                    # C://Tests/blabla/external_libs/osgeo/gdal-data or
                    # C://Tests/blabla/external_libs/site-packages/osgeo/gdal-data
                    gdal_data = self._check_dir_path(os.path.join(gdal_path, 'gdal-data'), True)
                    self._environ['PATH'] = ';'.join([gdal_path, gdal_data, gdal_plugins, str(self._environ['PATH'])])#.encode('utf8')
                    self._environ['GDAL_DRIVER_PATH'] = gdal_plugins#.encode('utf8')
                    self._environ['GDAL_DATA'] = gdal_data#.encode('utf8')
                    break

        else:
            raise IOError('The path {0} could not be found'.format(str(extlib_path)))

    # internal method used by _set_lib_path to discover subfolders
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

    # general method to find the python executable associated with the running interpreter. sys.executable is modified by ArcMap
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

