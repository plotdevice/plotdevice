import re
import sys
from sysconfig import get_config_var
from datetime import datetime

# customize Xcode's libpython paths based on the Python.framework interpreter
config = """// Generated by app/deps/framework/config.py at {timestamp}
PYTHON_FRAMEWORK = $(PROJECT_DIR)/app/deps/framework/Python.framework
PYTHON = $(PYTHON_FRAMEWORK)/Versions/{py_version}/bin/python3
LIBRARY_SEARCH_PATHS = $(inherited) {py_lib}
HEADER_SEARCH_PATHS = $(inherited) {py_inc}
OTHER_LDFLAGS = $(inherited) -lpython{py_version}
GCC_PREPROCESSOR_DEFINITIONS = $(inherited) PYTHON_BIN="$(PYTHON)" PY3K=1""".format(
  timestamp = datetime.now(),
  py_version = get_config_var('py_version_short'),
  py_lib = re.sub(r'^.*/Python.framework', '$(PYTHON_FRAMEWORK)', get_config_var('LIBPL')),
  py_inc = re.sub(r'^.*/Python.framework', '$(PYTHON_FRAMEWORK)', get_config_var('INCLUDEPY'))
)

with open(sys.argv[1], 'w') as f:
  f.write(config)