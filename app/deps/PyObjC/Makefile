# dependencies to be fetched
VENV_VERSION = 13.0.1
VENV_TAR = virtualenv-$(VENV_VERSION).tar.gz
VENV_URL = https://pypi.python.org/packages/source/v/virtualenv/virtualenv-$(VENV_VERSION).tar.gz
VENV_CMD = build/virtualenv-$(VENV_VERSION)/virtualenv.py

OBJC_VERSION = 3.0.4
OBJC_TAR = wheelhouse-pyobjc-$(OBJC_VERSION).tar.gz
OBJC_URL = http://plotdevice.io/wheelhouse-pyobjc-$(OBJC_VERSION).tar.gz

# paths
ENV = build/env
WHEELHOUSE = build/wheelhouse
SITEDIR = build/lib/PyObjC

# commands
PYTHON ?= /usr/bin/python
CURL = @curl -L --progress-bar
PIP = $(ENV)/bin/pip --isolated
VIRTUALENV = $(PYTHON) $(VENV_CMD) -q

# ---------------------------------------------------------------------------------------- #

# create the sitedir at build/lib/PyObjC using the wheelhouse tarfile
# (whether downloaded from plotdevie.io or build locally using `make pyobjc`)
all: $(SITEDIR)

# retrieve the current PyObjC sources from PyPI and build wheels from them. the resulting
# wheelhouse dir is then tarred up (and will be used in subsequent `make all` runs)
pyobjc: $(VENV_CMD)
	rm -rf $(ENV) $(WHEELHOUSE)

	$(VIRTUALENV) $(ENV)
	$(PIP) install pyobjc-core==$(OBJC_VERSION)
	$(PIP) wheel pyobjc==$(OBJC_VERSION) -w "${WHEELHOUSE}"

	tar czf wheelhouse-pyobjc-$(OBJC_VERSION).tar.gz -C build wheelhouse
	rm -rf build

# ---------------------------------------------------------------------------------------- #

# fetch the current version of virtualenv (which we mostly use for its copy of pip)
$(VENV_TAR):
	@echo $(VENV_URL)
	$(CURL) $(VENV_URL) -o $@

# unpack the virtualenv sdist in the build dir
$(VENV_CMD): | $(VENV_TAR)
	@mkdir -p build
	tar xzf $(VENV_TAR) -C build

# create a virtual environment at build/env
$(ENV): $(VENV_CMD)
	$(VIRTUALENV) $@

# fetch the cached wheelhouse archive from plotdevice.io
# (presuming it wasn't build locally via `make pyobjc`)
$(OBJC_TAR):
	@echo $(OBJC_URL)
	$(CURL) $(OBJC_URL) -o $@

# unpack the archived wheels in the build dir
$(WHEELHOUSE): | $(OBJC_TAR)
	@mkdir -p build
	tar xzf $(OBJC_TAR) -C build

# create a sitedir from the contents of build/wheelhouse
$(SITEDIR): | $(ENV) $(WHEELHOUSE)
	$(PIP) -q install --target=$@ --no-index --find-links=$(WHEELHOUSE) pyobjc
