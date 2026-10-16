PYTHON_VERSION = 3.14.6
PYTHON_PKG = $(or $(TMPDIR:/=),/tmp)/python-$(PYTHON_VERSION)-macos11.pkg
BIN = ./Python.framework/Versions/Current/bin
BIN_T = ./PythonT.framework/Versions/Current/bin

# removed from each framework, relative to its Versions/Current
UNUSED_FILES = lib/python3.*/test lib/python3.*/lib-dynload/_test* lib/python3.*/lib-dynload/_ctypes_test* lib/python3.*/lib-dynload/xx* \
	lib/python3.*/tkinter lib/python3.*/lib-dynload/_tkinter* lib/python3.*/idlelib lib/python3.*/turtledemo bin/idle3* \
	Frameworks/Tcl.framework Frameworks/Tk.framework share/doc

# Use PIP_NO_CACHE_DIR from environment if set, otherwise empty
PIP_ENV = $(if $(PIP_NO_CACHE_DIR),PIP_NO_CACHE_DIR=1,)

# Use the framework's headers (otherwise clang defaults to looking in /Library/Frameworks/Python.framework)
PIP_INCLUDES = $(shell $(BIN)/python3-config --includes)
PIP_INCLUDES_T = $(shell $(BIN_T)/python3t-config --includes)

all: Python.framework PythonT.framework
	$(PIP_ENV) CFLAGS="$(PIP_INCLUDES)" $(BIN)/pip3 install --upgrade ../..
	$(PIP_ENV) CFLAGS="$(PIP_INCLUDES_T)" $(BIN_T)/pip3 install --upgrade ../..
	python3 relocate.py Python.framework
	python3 relocate.py PythonT.framework

$(PYTHON_PKG):
	curl --fail -o $@.download https://www.python.org/ftp/python/$(PYTHON_VERSION)/$(notdir $@)
	mv $@.download $@

# free-threaded and vanilla python use different binary names
Python.framework: PY = python3
PythonT.framework: PY = python3t

PythonT.framework: Python.framework

Python.framework PythonT.framework: %.framework:
	$(MAKE) $(PYTHON_PKG)
	pkgutil --expand $(PYTHON_PKG) $@.pkg
	ditto -xz $@.pkg/$*_Framework.pkg/Payload $@
	rm -rf $@.pkg
	python3 relocate.py $@
	PYTHONNOUSERSITE=1 $@/Versions/Current/bin/$(PY) -s -m ensurepip
	PYTHONNOUSERSITE=1 $(PIP_ENV) $@/Versions/Current/bin/$(PY) -s -m pip install --upgrade pip
	PYTHONNOUSERSITE=1 $(PIP_ENV) CFLAGS="$$($@/Versions/Current/bin/$(PY)-config --includes)" $@/Versions/Current/bin/$(PY) -s -m pip install -r requirements.txt
	find $@ -type d \( -name PyObjCTest -o -name \*.dSYM \) -prune -exec rm -rf {} +
	cd $@/Versions/Current && rm -rf $(UNUSED_FILES)

clean:
	rm -rf Python.framework PythonT.framework *.framework.pkg
