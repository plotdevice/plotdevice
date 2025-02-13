PYTHON_VERSION = 3.10.5
FRAMEWORK_REPO = https://github.com/gregneagle/relocatable-python.git
BUILD_OPTS = --os-version=11 --python-version=$(PYTHON_VERSION) --upgrade-pip --pip-requirements=requirements.txt
BIN = ./Python.framework/Versions/Current/bin

# Use PIP_NO_CACHE_DIR from environment if set, otherwise empty
PIP_ENV = $(if $(PIP_NO_CACHE_DIR),PIP_NO_CACHE_DIR=1,)

all: Python.framework
	$(PIP_ENV) $(BIN)/pip3 install --upgrade ../..

Python.framework: relocatable-python
	PYTHONNOUSERSITE=1 $(PIP_ENV) python3 ./relocatable-python/make_relocatable_python_framework.py $(BUILD_OPTS)
	$(BIN)/python3 config.py ../../app/python.xcconfig

relocatable-python:
	git clone $(FRAMEWORK_REPO)

clean:
	rm -r Python.framework
