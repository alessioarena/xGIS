import sys
import os
import re
import operator
import threading
import warnings
import datetime
try:
    from arcpy import AddMessage, AddWarning, AddError
except ImportError:
    pass
import logging
# reload(logging)  # This is to reset the ROOT logger in case you call this module twice
logging.captureWarnings(True)
logger = logging.getLogger(__name__)


class LogToLevel(object):
    logger = None
    internal_level = None
    external_level = None
    valid_levels = [logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

    def __init__(self, logger, level):
        if not isinstance(logger, logging.Logger):
            raise TypeError('The argument logger must be a valid logging.Logger')
        if not isinstance(level, int) or level not in self.valid_levels:
            raise ValueError('the argument level must be a valid logging level. Accepted values are {0}'.format(self.valid_levels))
        self.logger = logger
        self.external_level = self.logger.level
        self.internal_level = level

    def __enter__(self):
        self.logger.level = self.internal_level
        return self.logger

    def __exit__(self, *args):
        self.logger.level = self.external_level


class ConditionalFilter(logging.Filter):
    def __init__(self, level, condition):
        self.level = level
        if callable(condition) and condition.__module__ == 'operator':
            self.condition = condition
        else:
            raise TypeError('condition must be a callable object from the operator module')

    def filter(self, record):
        # This is using whatever condition you pass and coparing the two codes. e.g. record.levelno > self.level if condition = operator.gt
        return self.condition(record.levelno, self.level)


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
            warnings.warn(log_entry + '\n')  # This is not retrieved by ArcMAP, but handled properly by python
        return


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


class ARCFileHandler(logging.FileHandler):
    def emit(self, message):
        try:
            msg = self.format(message)
            if not msg.strip():
                return
            msg = msg.replace('\n', '\n' + ' ' * 16)
            msg = re.sub(r'(?:(?:\r\n|\r|\n)\s*)+', '\r\n', msg)  # to handle multiline with empty lines
            msg = re.sub(r'(?:\r\n|\r|\n)$', '', msg)
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


def initialise_logger(i_logger=False, to_file=False, force=True, level=logging.INFO):
    if i_logger is False:
        i_logger = logger
    elif not isinstance(i_logger, logging.Logger):
        raise TypeError("The argument 'i_logger' must be a logging.Logger or False")

    if len(i_logger.handlers) == 0:
        if to_file:
            home = os.path.expanduser("~")
            path = os.path.join(home, 'PlannedBurnsToolbox_logs')
            if not os.path.isdir(path):
                os.mkdir(path)
            username = os.path.split(home)[-1]
            date_str = datetime.datetime.today().strftime("%Y%m%d")
            filename = '_'.join(['PlannedBurnsToolbox', username, date_str]) + '.log'
            filename = os.path.join(path, filename)
            i_logger = _log_to_file(i_logger, filename, level)
        i_logger.addHandler(ARCMessageHandler())
        i_logger.addHandler(ARCErrorHandler())
        i_logger.addHandler(ARCWarningHandler())
        i_logger.setLevel(level)
    else:
        if force:
            for h in i_logger.handlers:  # resetting to empty if has handlers
                i_logger.removeHandler(h)
            i_logger = initialise_logger(i_logger=i_logger, to_file=to_file, force=False, level=level)

    return i_logger


def _log_to_file(i_logger, filename, level):
    with open(filename, mode='a+') as log:
        if sys.executable.endswith('RuntimeLocalServer.exe'):
            timestamp = datetime.datetime.today().strftime("%H:%M:%S")
            log.write('{:8s}: {:15s} Initializing background geoprocessing\n'.format('INFO', timestamp))
        else:
            timestamp = datetime.datetime.today().strftime("%Y-%m-%d %H:%M")
            log.write('********************************************************\n')
            log.write('* Logging started on {0:16} in {1:8s} mode *\n'.format(timestamp, logging.getLevelName(level)))
            log.write('********************************************************\n')

    handler = ARCFileHandler(filename, mode='a+')
    handler.setFormatter(logging.Formatter(fmt='%(levelname)-8s: %(asctime)-15s %(message)s', datefmt='%H:%M:%S'))
    i_logger.addHandler(handler)
    return i_logger
