# interpretter info gathered from $PYTHON environment variable
PYTHON ?= python3
PY_VERSION = $(shell $(PYTHON) -c 'import sys; print("py%i%i"%sys.version_info[:2])')

# dependencies to be fetched
HTTP_MODULES = requests cachecontrol lockfile

OBJC_VERSION = 8.5
OBJC_SRC = pyobjc-$(OBJC_VERSION)-$(PY_VERSION).tar.gz
OBJC_URL = http://plotdevice.io/wheelhouse/$(OBJC_SRC)

# paths
BUILD = build
ENV = $(BUILD)/env
WHEELHOUSE = $(BUILD)/wheelhouse
PYOBJC = $(BUILD)/lib/PyObjC
DSTROOT ?= $(BUILD)/HTTP
HTTP = $(DSTROOT)/$(firstword $(HTTP_MODULES))

# commands
CURL = @curl -L --progress-bar -f
# VIRTUALENV = $(BUILD)/virtualenv-$(VENV_VERSION)/virtualenv.py
PIP = $(ENV)/bin/pip3 --isolated

# ---------------------------------------------------------------------------------------- #

# create the sitedir at build/lib/PyObjC using the wheelhouse tarfile
# (whether downloaded from plotdevice.io or built locally using `make wheels`)
all, pyobjc: $(PYOBJC)

# install the http libs in $DSTROOT
http: $(HTTP)

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

# ---------------------------------------------------------------------------------------- #

# fetch the cached wheelhouse archive from plotdevice.io (or build it if necessary)
$(OBJC_SRC):
	@echo $(OBJC_URL)
	-$(CURL) $(OBJC_URL) -o $@ || $(MAKE) wheels

# unpack the archived wheels in the build dir
$(WHEELHOUSE): $(OBJC_SRC)
	@mkdir -p $(BUILD)
	tar xzf $(OBJC_SRC) -C $(BUILD)
	touch $@

# create a virtual environment at build/env
$(ENV):
	$(PYTHON) -m venv $@
	$(PIP) install --upgrade pip

# create a sitedir from the contents of build/wheelhouse
$(PYOBJC): $(WHEELHOUSE) $(ENV)
	$(PIP) install --target=$@ --no-index --find-links=$(WHEELHOUSE) "pyobjc"

# fetch the current versions of our helper modules
$(HTTP): $(ENV)
	$(PIP) install --target=$(DSTROOT) $(HTTP_MODULES)
	rm -rf $(DSTROOT)/*.dist-info
