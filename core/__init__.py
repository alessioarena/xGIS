from ._version import __version__
from .executor import Executor, ExternalExecutionError
from . import log_utils
import os, sys

version = __version__
version_info = tuple([int(v) for v in __version__.split('.')])

name = 'xgis'

embedded_python_path = os.path.join(os.path.dirname(__file__), 'python_embedded{0}python.exe'.format(os.sep))

if os.path.isfile(embedded_python_path):
    pass
else:
    embedded_python_path = False