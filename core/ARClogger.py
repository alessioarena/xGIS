import sys
import os
import re
import operator
import threading
import warnings
import datetime
# safe import the ArcGIS methods
try:
    from arcpy import AddMessage, AddWarning, AddError
except ImportError:
    pass
import logging
logging.captureWarnings(True)
# this is to pin the logger associated with this module, and retrieve it later
logger = logging.getLogger(__name__)


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
        self.logger.level = self.internal_level
        return self.logger

    # get out of the context by resetting to the original logging level
    def __exit__(self, *args):
        self.logger.level = self.external_level


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
        if callable(condition) and condition.__module__ == 'operator':
            self.condition = condition
        else:
            raise TypeError('condition must be a callable object from the operator module')

    def filter(self, record):
        # This is using whatever condition you pass and coparing the two codes. e.g. record.levelno > self.level if condition = operator.gt
        return self.condition(record.levelno, self.level)


# handler to redirect NOTSET, DEBUG and INFO level to arcpy.AddMessage
class ARCMessageHandler(logging.Handler):
    def __init__(self):
        self.filters = [ConditionalFilter(logging.INFO, operator.le)]  # handling logging.debug and logging.info
        self.level = 0
        self._name = None
        self.formatter = logging.Formatter(fmt='%(asctime)-15s %(message)s', datefmt='%H:%M:%S')
        self.lock = threading.RLock()

    def emit(self, message):
        log_entry = self.format(message)
        # log_entry = 'LINE' + log_entry
        if not log_entry.strip():  # to handle empty lines
            return
        log_entry = log_entry.replace('\n', '\n' + ' ' * 16)
        log_entry = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', log_entry)  # to handle multiline with empty lines
        log_entry = re.sub(r'(?:\r\n|\r|\n)$', '', log_entry)
        try:
            AddMessage(log_entry)  # this should print to stdout by default, but also retrieved by ArcMAP
        except NameError:
            sys.stdout.write(log_entry + '\n')  # Fallback if arcpy cannot be loaded
        return


# handler to redirect WARNING level to arcpy.AddWarning
class ARCWarningHandler(logging.Handler):
    def __init__(self):
        self.filters = [ConditionalFilter(logging.WARN, operator.eq)]  # handling logging.warning
        self.level = logging.WARN
        self._name = None
        self.formatter = logging.Formatter(fmt='%(asctime)-15s %(message)s', datefmt='%H:%M:%S')
        self.lock = threading.RLock()

    def emit(self, message):
        log_entry = self.format(message)
        if not log_entry.strip():
            return
        log_entry = log_entry.replace('\n', '\n' + ' ' * 16)  # This offsets multiline
        log_entry = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', log_entry)  # to handle multiline with empty lines
        log_entry = re.sub(r'(?:\r\n|\r|\n)$', '', log_entry)  # to suppress the last new line (will be appended by the function to emit the message)
        try:
            AddWarning(log_entry)  # Retrieved by ArcMAP, but only visualized differently
        except NameError:
            sys.stdout.write(log_entry + '\n')  # Fallback if arcpy cannot be loaded
            # warnings is too messy
            # warnings.warn(log_entry + '\n')  # This is not retrieved by ArcMAP, but handled properly by python
        return


# handler to redirect ERROR and CRITICAL level to arcpy.AddError
# please note that ArcMAP will exit once the first call to arcpy.AddError is finished
# however you can pass a multiline string to it
class ARCErrorHandler(logging.Handler):
    def __init__(self):
        self.filters = [ConditionalFilter(logging.ERROR, operator.ge)]  # handling logging.error, logging.critical and logging.exception
        self.level = logging.ERROR
        self._name = None
        self.formatter = logging.Formatter(fmt='%(asctime)-15s %(message)s', datefmt='%H:%M:%S')
        self.lock = threading.RLock()

    def emit(self, message):
        log_entry = self.format(message)
        if not log_entry.strip():
            return
        log_entry = log_entry.replace('\n', '\n' + ' ' * 16)  # This offsets multiline
        log_entry = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', log_entry)  # to handle multiline with empty lines
        log_entry = re.sub(r'(?:\r\n|\r|\n)$', '', log_entry)  # to suppress the last new line (will be appended by the function to emit the message)
        try:
            AddError(log_entry)  # Retrieved by ArcMAP and handled properly
        except NameError:
            sys.stderr.write(log_entry + '\n')
        sys.exit(1)  # Kill the process


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
        if to_file is True or isinstance(to_file, (str, unicode)):
            filename = _get_log_filename(to_file)
            i_logger = _log_to_file(i_logger, filename, level)

        # initialise the logger with the other handlers
        i_logger.addHandler(ARCMessageHandler())
        i_logger.addHandler(ARCErrorHandler())
        i_logger.addHandler(ARCWarningHandler())
        i_logger.setLevel(level)
    # the logger was already initialised
    else:
        # do we want to re-initialise it?
        if force:
            # then remove all the current handlers
            for h in i_logger.handlers:
                i_logger.removeHandler(h)
            # and call again this method with the clean  logger
            i_logger = initialise_logger(i_logger=i_logger, to_file=to_file, force=False, level=level)

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
    elif isinstance(to_file, (str, unicode)):
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
