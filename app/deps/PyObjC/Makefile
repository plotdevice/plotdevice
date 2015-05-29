# dependencies to be fetched
VENV_VERSION = 13.0.1
VENV_SRC = virtualenv-$(VENV_VERSION).tar.gz
VENV_URL = https://pypi.python.org/packages/source/v/virtualenv/$(VENV_SRC)

OBJC_VERSION = 3.0.4
OBJC_SRC = wheelhouse-pyobjc-$(OBJC_VERSION).tar.gz
OBJC_URL = http://plotdevice.io/$(OBJC_SRC)

# paths
ENV = build/env
WHEELHOUSE = build/wheelhouse
SITEDIR = build/lib/PyObjC

# commands
CURL = @curl -L --progress-bar
PYTHON ?= /usr/bin/python
VIRTUALENV = build/virtualenv-$(VENV_VERSION)/virtualenv.py
PIP = $(ENV)/bin/pip --isolated

# ---------------------------------------------------------------------------------------- #

# create the sitedir at build/lib/PyObjC using the wheelhouse tarfile
# (whether downloaded from plotdevice.io or built locally using `make wheels`)
all: $(SITEDIR)

# delete generated files
clean:
	rm -rf build

# delete generated files *and* cached archives
distclean:
	rm -rf build $(VENV_SRC) $(OBJC_SRC)

# retrieve the current PyObjC sources from PyPI and build wheels from them. the resulting
# wheelhouse dir is then tar'd up and will be used in subsequent `make all` runs
wheels: clean $(ENV)
	$(PIP) install pyobjc-core==$(OBJC_VERSION)
	$(PIP) wheel pyobjc==$(OBJC_VERSION) -w ${WHEELHOUSE}
	tar czf $(OBJC_SRC) -C build wheelhouse
	$(MAKE) clean

# ---------------------------------------------------------------------------------------- #

# fetch the current version of virtualenv (which we mostly use for its copy of pip)
$(VENV_SRC):
	@echo $(VENV_URL)
	$(CURL) $(VENV_URL) -o $@

# fetch the cached wheelhouse archive from plotdevice.io
$(OBJC_SRC):
	@echo $(OBJC_URL)
	$(CURL) $(OBJC_URL) -o $@

# unpack the virtualenv sdist in the build dir
$(VIRTUALENV): | $(VENV_SRC)
	@mkdir -p build
	tar xzf $(VENV_SRC) -C build

# unpack the archived wheels in the build dir
$(WHEELHOUSE): | $(OBJC_SRC)
	@mkdir -p build
	tar xzf $(OBJC_SRC) -C build

# create a virtual environment at build/env
$(ENV): $(VIRTUALENV)
	$(PYTHON) $(VIRTUALENV) -q $@

# create a sitedir from the contents of build/wheelhouse
$(SITEDIR): | $(WHEELHOUSE) $(ENV)
	$(PIP) -q install --target=$@ --no-index --find-links=$(WHEELHOUSE) pyobjc
