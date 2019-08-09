from ._version import __version__
from .executor import Executor, ExternalExecutionError

version = __version__
version_info = tuple([int(v) for v in __version__.split('.')])

name = 'arcpy_extender'