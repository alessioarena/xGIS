"""Logging utilities and cross-compatibility for logging facilities across native python, ArcGIS, QGIS and xGIS
"""


import sys
import os
import re
import operator
import threading
import warnings
import datetime
import logging
import time
import numpy as np
from functools import partial
# python 2/3 compatibility
try:
    basestring
    unicode
except NameError:
    basestring = (str, bytes)
    unicode = str


def _stream_write(msg, stream):
    stream.write(msg + '\n')
    stream.flush()

#setting up the support of xGIS
try:
    os.environ['xGIS_child']
    log_info = lambda msg: _stream_write(msg, sys.stdout)
    log_warning = lambda msg: _stream_write(msg, sys.stdout)
    log_error = lambda msg: _stream_write(msg, sys.stderr)
    environment = 'xgis'
    format = '%(message)s'
except KeyError:
    format = '%(asctime)-15s %(message)s'

# setting up the support for ArcGIS redirection
try:
    from arcpy import AddMessage, AddWarning, AddError
    log_info = AddMessage
    log_warning = AddWarning
    log_error = AddError
    environment = 'arcgis'
except ImportError:
    pass

# setting up the support for QGIS redirection
try:
    from qgis.core import QgsMessageLog, Qgis
    log_info = lambda msg: QgsMessageLog.logMessage(msg, level=Qgis.Info)
    log_warning = lambda msg: QgsMessageLog.logMessage(msg, level=Qgis.Warning)
    log_error = lambda msg: QgsMessageLog.logMessage(msg, level=Qgis.Critical)
    environment = 'qgis'
except ImportError:
    pass

# fallback redirection method
try:
    log_info
except NameError:
    log_info = lambda msg: _stream_write(msg, sys.stdout)
    log_warning = lambda msg: _stream_write(msg, sys.stdout)
    log_error = lambda msg: _stream_write(msg, sys.stderr)
    environment = 'python'


class ProgressBar(object):
    completed_items = 0
    start_time = None
    last_update = None
    _completion_time = []
    elapsed_str = ""
    max_items = None

    @property
    def completion_time(self):
        return np.mean(self._completion_time)
    @completion_time.setter
    def completion_time(self, new):
        self._completion_time.append(new)
        if len(self._completion_time) > 200:
            self._completion_time = self._completion_time[-200:]

    def __init__(self, max_items=None, bar_length=50, completed_items=None, message=None):
        self._completion_time = []
        self.max_items = max_items
        self.bar_length = bar_length
        self.update(completed_items, message)
        self.start_time = time.time()

    def update(self, completed_items=None, message=None, elapsed=True):
        
        if completed_items is not None:
            if self.max_items is None:
                raise RuntimeError('Cannot update progress if max_items is not known')
            if completed_items == self.completed_items:
                return
            if elapsed is True and self.last_update is not None:
                self.calculate_elapsed(completed_items)
            else:
                self.elapsed_str = ""
            self.completed_items = completed_items
            self.last_update = time.time()
        self.message = message
        self._writer()

    def calculate_elapsed(self, completed_items):
        last_completed = self.completed_items
        now_completed = completed_items
        last_update = self.last_update
        now_update = time.time()
        remaining_items = self.max_items - completed_items

        progress = now_completed - last_completed
        time_past = now_update -last_update

        remaining_seconds = remaining_items * (time_past / progress)
        self.completion_time = now_update + remaining_seconds
        remaining_seconds = self.completion_time - now_update

        self.elapsed_str = "| elapsed time: " + self._print_time(remaining_seconds)

    @staticmethod
    def _print_time(seconds):
        elapsed = ""
        hours = seconds // 3600
        if hours > 0:
            elapsed += '{:>2.0f}h '.format(hours)
            seconds -= hours * 3600
        minutes = seconds // 60
        if minutes > 0:
            elapsed += '{:>2.0f}m '.format(minutes)
            seconds -= minutes * 60
        elapsed += '{:2.1f}s '.format(seconds)

        return elapsed


    def close(self):
        self.completed_items = self.max_items
        self.message = None
        runtime = time.time() - self.start_time
        self.elapsed_str = "| completed in " + self._print_time(runtime)
        self._writer()
        sys.stdout.write('\n')

    def _writer(self):
        try:
            completed_perc = min(1, max(0, self.completed_items / self.max_items))
            completed_items = self.completed_items
            max_items = self.max_items
        except TypeError:
            completed_perc = 0.0
            completed_items = '--'
            max_items = '--'         
        if self.message is not None:
            bar = ' ' + self.message
        else:
            current = round((completed_perc)*self.bar_length)
            left = self.bar_length - current
            bar = '='*current + ' '*left
        sys.stdout.write('\r{1: >.1%} [{0:{width}s}] | {2}/{3} {elapsed:30s}'.format(bar, completed_perc, completed_items, max_items, width=self.bar_length, elapsed=self.elapsed_str))


# context manager to change temporarily the log level of a logging.Logger by using the with statement
class LogToLevel(object):
    """Context manager for logging.Logger
    This will safely change the logging level using the with statement, and return the original logging level on exit

    Arguments:
    -----------
    logger : logging.Logger
        logger to temporarily modify
    level : int or logging.level
        logging level to use within the context, as defined below
        logging.NOTSET or 0,
        logging.DEBUG or 10,
        logging.INFO or 20,
        logging.WARNING or 30,
        logging.ERROR or 40,
        logging.CRITICAL or 50

    Returns:
    -----------
    out : logging.Logger
        same instance of the input logging.Logger

    Example:
    -----------
        import logging
        import arclogger
        logger = arclogger.logger

        logger.info('you should see this message')
        logger.debug('you are not going to see this message')
        with LogToLevel(logger, logging.DEBUG) as logger:
            logger.debug('Now this will appear')
        logger.debug('this is again not displayed')
    """
    logger = None
    internal_level = None
    external_level = None
    # alternative values         0             10            20               30             40                50
    valid_levels = [logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

    # initialise the context manager, save the current logging level and the one you want
    def __init__(self, logger, level):
        if not isinstance(logger, logging.Logger):
            raise TypeError('The argument logger must be a valid logging.Logger')
        if not isinstance(level, int) or level not in self.valid_levels:
            raise ValueError('the argument level must be a valid logging level. Accepted values are {0}'.format(self.valid_levels))
        self.logger = logger
        self.external_level = self.logger.level
        self.internal_level = level

    # apply the context by setting temporarily the target logging level
    def __enter__(self):
        self.logger.setLevel(self.internal_level)
        return self.logger

    # get out of the context by resetting to the original logging level
    def __exit__(self, *args):
        self.logger.setLevel(self.external_level)


# general class to apply a operator condition as a logging.Level filter
class ConditionalFilter(logging.Filter):
    """Class derived from logging.Filter with an updated filter method to define a general approach to conditional filtering

    Arguments:
    -----------
    level : int or logging.Level
        reference logging level
    condition : operator
        operator.eq or similar to create a logging filter relative to the reference logging level

    Returns:
    -----------
    out : logging.Filter
    """
    def __init__(self, level, condition):
        self.level = level
        if callable(condition) and (condition.__module__ == 'operator' or condition.__module__ == '_operator'):
            self.condition = condition
        else:
            raise TypeError('condition must be a callable object from the operator module')

    def filter(self, record):
        # This is using whatever condition you pass and coparing the two codes. e.g. record.levelno > self.level if condition = operator.gt
        return self.condition(record.levelno, self.level)


# handler to redirect NOTSET, DEBUG and INFO level to arcpy.AddMessage
class GISMessageHandler(logging.Handler):
    def __init__(self):
        self.filters = [ConditionalFilter(logging.INFO, operator.le)]  # handling logging.debug and logging.info
        self.level = logging.DEBUG
        self._name = None
        self.formatter = logging.Formatter(fmt=format, datefmt='%H:%M:%S')
        self.lock = threading.RLock()

    def emit(self, message):
        log_entry = self.format(message)
        # log_entry = 'LINE' + log_entry
        if not log_entry.strip():  # to handle empty lines
            return
        log_entry = re.sub('\n(?!$)', '\n' + ' ' * 16, log_entry)
        log_entry = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', log_entry)  # to handle multiline with empty lines
        log_entry = re.sub(r'(?:\r\n|\r|\n)$', '', log_entry)
        log_info(log_entry)
        return


# handler to redirect WARNING level to arcpy.AddWarning
class GISWarningHandler(logging.Handler):
    def __init__(self):
        self.filters = [ConditionalFilter(logging.WARN, operator.eq)]  # handling logging.warning
        self.level = logging.WARN
        self._name = None
        self.formatter = logging.Formatter(fmt= '%(levelname)s '+format, datefmt='%H:%M:%S')
        self.lock = threading.RLock()

    def emit(self, message):
        log_entry = self.format(message)
        if not log_entry.strip():
            return
        log_entry = re.sub('\n(?!$)', '\n' + ' ' * 16, log_entry)
        log_entry = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', log_entry)  # to handle multiline with empty lines
        log_entry = re.sub(r'(?:\r\n|\r|\n)$', '', log_entry)  # to suppress the last new line (will be appended by the function to emit the message)
        log_warning(log_entry)
        # warnings is too messy
        # warnings.warn(log_entry + '\n')  # This is not retrieved by ArcMAP, but handled properly by python
        return


# handler to redirect ERROR and CRITICAL level to arcpy.AddError
# please note that ArcMAP will exit once the first call to arcpy.AddError is finished
# however you can pass a multiline string to it
class GISErrorHandler(logging.Handler):
    def __init__(self):
        self.filters = [ConditionalFilter(logging.ERROR, operator.ge)]  # handling logging.error, logging.critical and logging.exception
        self.level = logging.ERROR
        self._name = None
        self.formatter = logging.Formatter(fmt=format, datefmt='%H:%M:%S')
        self.lock = threading.RLock()

    def emit(self, message):
        log_entry = self.format(message)
        if not log_entry.strip():
            return
        log_entry = re.sub('\n(?!$)', '\n' + ' ' * 16, log_entry)
        log_entry = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', log_entry)  # to handle multiline with empty lines
        log_entry = re.sub(r'(?:\r\n|\r|\n)$', '', log_entry)  # to suppress the last new line (will be appended by the function to emit the message)
        log_error(log_entry)
        # sys.exit(1)  # Kill the process


# handler for log file
class ARCFileHandler(logging.FileHandler):
    # safe emit method with fallback
    def emit(self, message):
        try:
            msg = self.format(message)
            # if the line is empty, return
            if not msg.strip():
                return
            # otherwise, re-format it
            msg = msg.replace('\n', '\n' + ' ' * 16)  # to handle multiline. This will offset any line after the first to print empty space belog the LEVEL: HH:MM:SS of the first line
            msg = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', msg)  # to handle multiline with empty lines
            msg = re.sub(r'(?:\r\n|\r|\n)$', '', msg)  # to handle multiline with multiple line ends
            # msg = msg.replace('\r', '')  # To remove extra carriage returns, assuming that end of line will be \r\n
            stream = self.stream
            fs = "%s\n"
            if not logging._unicode:  # if no unicode support...
                stream.write(fs % msg)
            else:
                try:
                    if (isinstance(msg, unicode) and getattr(stream, 'encoding', None)):
                        ufs = u'%s\n'
                        try:
                            stream.write(ufs % msg)
                        except UnicodeEncodeError:
                            # Printing to terminals sometimes fails. For example,
                            # with an encoding of 'cp1251', the above write will
                            # work if written to a stream opened or wrapped by
                            # the codecs module, but fail when writing to a
                            # terminal even when the codepage is set to cp1251.
                            # An extra encoding step seems to be needed.
                            stream.write((ufs % msg).encode(stream.encoding))
                    else:
                        stream.write(fs % msg)
                except UnicodeError:
                    stream.write(fs % msg.encode("UTF-8"))
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(message)


# method to initialise the module logger, or another one passed with the first argument
def initialise_logger(i_logger=False, to_file=False, force=True, level=logging.INFO):
    """method to initialise a new logger, or re-initialise an already existing one

    Arguments:
    -----------
    i_logger : logging.Logger or False
        logger to initialise. If False, it will use the logger defined within this module (arclogger.logger)
        This can be easily retrieved later on even from a different module
    to_file : bool or str, optional (default : False)\n
        if False, no log will be saved on disk
        if True, a log file will be saved in your user home directory under ArcLogger_logs/ArcLogger_[date].log
        if str, this needs to be:
        - a path to a directory
            [path/to/dir]/ArcLogger_[user]_[date].log
        - a filename
            ./[filename]_[date].logs
        - a rootname
            ~/[root]_logs/[root]_[user]_[date].logs
    force : bool, optional (default : False)\n
        to force reinitialisation of this logger. It will delete any handler associated with this logger
    level : logging.Level, optional (default : logging.INFO)\n
        logging level to use for the logger

    Returns:
    -----------
    out : logging.Logger
    """
    # retrieve the module logger if needed
    if i_logger is False:
        i_logger = logger
    # or use the input one
    elif not isinstance(i_logger, logging.Logger):
        raise TypeError("The argument 'i_logger' must be a logging.Logger or False")

    # if the logger does not have any handler, initialise it
    if len(i_logger.handlers) == 0:
        # if we want to log to disk
        i_logger.setLevel(level)
        if to_file is True or isinstance(to_file, basestring):
            filename = _get_log_filename(to_file)
            i_logger = _log_to_file(i_logger, filename, level)

        # initialise the logger with the other handlers
        i_logger.addHandler(GISMessageHandler())
        i_logger.addHandler(GISErrorHandler())
        i_logger.addHandler(GISWarningHandler())
        i_logger.setLevel(level)
        warnings.showwarning = partial(_showwarning, i_logger)

    # the logger was already initialised
    else:
        # do we want to re-initialise it?
        if force:
            # then remove all the current handlers
            while len(i_logger.handlers) > 0:
                h = i_logger.handlers[0]
                i_logger.removeHandler(h)
            # and call again this method with the clean  logger
            i_logger = initialise_logger(i_logger=i_logger, to_file=to_file, force=False, level=level)
        else:
            log_warning("The logger is already initialised. Please rerun this function with force=True")
    i_logger.environment = environment
    i_logger.info("Logging environment is {0}".format(logger.environment))
    return i_logger


# internal method to initialise the log file
def _log_to_file(i_logger, filename, level):
    # open the file for the first time in this session
    with open(filename, mode='a+') as log:
        # if we are running a background geoprocessing
        if sys.executable.endswith('RuntimeLocalServer.exe'):
            timestamp = datetime.datetime.today().strftime("%H:%M:%S")
            log.write('{:8s}: {:15s} Initializing background geoprocessing\n'.format('INFO', timestamp))
        # if we are running from a front end process
        else:
            timestamp = datetime.datetime.today().strftime("%Y-%m-%d %H:%M")
            log.write('********************************************************\n')
            log.write('* Logging started on {0:16} in {1:8s} mode *\n'.format(timestamp, logging.getLevelName(level)))
            log.write('********************************************************\n')

    # hook the log file to the file handler
    handler = ARCFileHandler(filename, mode='a+')
    handler.setFormatter(logging.Formatter(fmt='%(levelname)-8s: %(asctime)-15s %(message)s', datefmt='%H:%M:%S'))
    i_logger.addHandler(handler)
    return i_logger


# internal method to interpret the to_file argument
def _get_log_filename(to_file):
    # default path
    home = os.path.expanduser("~")
    default_path = os.path.join(home, 'ArcLogger_logs')

    # default filename
    username = os.path.split(home)[-1]
    date_str = datetime.datetime.today().strftime("%Y%m%d")
    default_filename = '_'.join(['ArcLogger', username, date_str]) + '.log'

    if to_file is True:
        # we want to use the defaults
        path = default_path
        filename = default_filename
    elif isinstance(to_file, basestring):
        path = os.path.dirname(to_file)
        basename, ext = os.path.splitext(os.path.basename(to_file))
        # we are passing only a string to prepend to the defaults, e.g. PlannedBurnsToolbox
        if path == ext == '':
            path = os.path.join(home, '_'.join([basename, 'logs']))
            filename = '_'.join([basename, username, date_str]) + '.log'
        # we are passing a filename only because we want the log to be in the working directory
        elif path == '':
            path = os.getcwd()
            filename = '_'.join([basename, date_str]) + ext
        # we are passing only a path ()
        elif ext == '':
            path = os.path.join(os.path.abspath(path), basename)
            filename = default_filename
    else:
        raise TypeError('The argument must be True or a string')

    # if the folder does not exist, make it
    if not os.path.isdir(path) and not path == '':
        os.makedirs(path)
    # return path_to_file
    return os.path.join(path, filename)


def _showwarning(logger, message, category, filename, lineno, file=None, line=None):
    """
    Implementation of showwarnings which redirects to logging, which will first
    check to see if the file parameter is None. If a file is specified, it will
    delegate to the original warnings implementation of showwarning. Otherwise,
    it will call warnings.formatwarning and will log the resulting string to a
    warnings logger named "py.warnings" with level logging.WARNING.
    """
    # if file is not None:
    #     if _warnings_showwarning is not None:
    #         _warnings_showwarning(message, category, filename, lineno, file, line)
    s = warnings.formatwarning(message, category, filename, lineno, None)
    logger.warning("%s", s)

def silence_logger(func):
    def run_func(*args, **kwargs):
        with LogToLevel(logger, 30):
            out = func(*args, **kwargs)
        return out
    return run_func


# this is to pin the logger associated with this module, and retrieve it later
logger = logging.getLogger('xGIS/log_utils')
logging.captureWarnings(True)
if len(logger.handlers) == 0:
    initialise_logger()

