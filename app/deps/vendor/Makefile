# interpretter info gathered from $PYTHON environment variable
PYTHON ?= /usr/bin/python
PY_VERSION = $(shell $(PYTHON) -c 'import sys; print("py%i%i"%sys.version_info[:2])')

# dependencies to be fetched
HTTP_MODULES = requests cachecontrol

VENV_VERSION = 13.0.3
VENV_SRC = virtualenv-$(VENV_VERSION).tar.gz
VENV_URL = https://pypi.python.org/packages/source/v/virtualenv/$(VENV_SRC)

OBJC_VERSION = 3.0.4
OBJC_SRC = pyobjc-$(OBJC_VERSION)-$(PY_VERSION).tar.gz
OBJC_URL = http://plotdevice.io/wheelhouse/$(OBJC_SRC)

# paths
BUILD = build
ENV = $(BUILD)/env
WHEELHOUSE = $(BUILD)/wheelhouse
PYOBJC = $(BUILD)/lib/PyObjC
DSTROOT ?= $(BUILD)/HTTP

# commands
CURL = @curl -L --progress-bar -f
VIRTUALENV = $(BUILD)/virtualenv-$(VENV_VERSION)/virtualenv.py
PIP = $(ENV)/bin/pip --isolated

# ---------------------------------------------------------------------------------------- #

# create the sitedir at build/lib/PyObjC using the wheelhouse tarfile
# (whether downloaded from plotdevice.io or built locally using `make wheels`)
all, pyobjc: $(PYOBJC)

# delete generated files
clean:
	rm -rf $(BUILD)

# delete generated files *and* cached archives
distclean:
	rm -rf $(BUILD) $(VENV_SRC) $(OBJC_SRC)

# retrieve the current PyObjC sources from PyPI and build wheels from them. the resulting
# wheelhouse dir is then tar'd up and will be used in subsequent `make all` runs
wheels: clean $(ENV)
	$(PIP) install "pyobjc-core"==$(OBJC_VERSION)
	$(PIP) wheel "pyobjc"==$(OBJC_VERSION) -w ${WHEELHOUSE}
	tar czfv $(OBJC_SRC) -C $(BUILD) $(notdir ${WHEELHOUSE})

# fetch the current versions of our helper modules
http: $(ENV)
	$(ENV)/bin/pip -q install --target=$(DSTROOT) $(HTTP_MODULES)
	rm -rf $(DSTROOT)/*.dist-info

# ---------------------------------------------------------------------------------------- #

# fetch the current version of virtualenv (which we mostly use for its copy of pip)
$(VENV_SRC):
	@echo $(VENV_URL)
	$(CURL) $(VENV_URL) -o $@

# fetch the cached wheelhouse archive from plotdevice.io (or build it if necessary)
$(OBJC_SRC):
	@echo $(OBJC_URL)
	-$(CURL) $(OBJC_URL) -o $@ || $(MAKE) wheels

# unpack the virtualenv sdist in the build dir
$(VIRTUALENV): | $(VENV_SRC)
	@mkdir -p $(BUILD)
	tar xzf $(VENV_SRC) -C $(BUILD)

# unpack the archived wheels in the build dir
$(WHEELHOUSE): | $(OBJC_SRC)
	@mkdir -p $(BUILD)
	tar xzf $(OBJC_SRC) -C $(BUILD)

# create a virtual environment at build/env
$(ENV): $(VIRTUALENV)
	$(PYTHON) $(VIRTUALENV) -q $@

# create a sitedir from the contents of build/wheelhouse
$(PYOBJC): $(WHEELHOUSE) $(ENV)
	$(PIP) -q install --target=$@ --no-index --find-links=$(WHEELHOUSE) "pyobjc"
