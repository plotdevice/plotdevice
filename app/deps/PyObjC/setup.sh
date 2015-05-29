#!/bin/bash
#
# Create a sitedir-style directory with an installed PyObjC distribution
#  - if the build/wheelhouse directory doesn't exist, pre-built copies will
#    be fetched from the website
#  - running rebuild.sh prior to setup will generate a fresh set of wheels from
#    the current source distribution on PyPI and fill the wheelhouse subdir
#  - the subsequent call to setup.sh will populate the sitedir using these
#    fresh copies
#  - the interpreter will be /usr/bin/python by defualt, but an alternate path
#    can be specified as the first command line arg when invoking the script
#
set -e

TOP=$(dirname "$0")
PYTHON=${1:-/usr/bin/python}
BUILD_DIR="${TOP}/build"
DEST_DIR="${BUILD_DIR}/lib/PyObjC"

VENV_VERSION="13.0.1"
VENV_PKG="virtualenv-${VENV_VERSION}"
VENV_TAR="${TOP}/${VENV_PKG}.tar.gz"
VENV_URL="https://pypi.python.org/packages/source/v/virtualenv/${VENV_PKG}.tar.gz"
VENV_DIR="${BUILD_DIR}/${VENV_PKG}"

PYOBJC_VERSION="3.0.4"
PYOBJC_PKG="wheelhouse-pyobjc-${PYOBJC_VERSION}"
PYOBJC_TAR="${TOP}/${PYOBJC_PKG}.tar.gz"
PYOBJC_URL="http://plotdevice.io/${PYOBJC_PKG}.tar.gz"
PYOBJC_DIR="${BUILD_DIR}/wheelhouse"

ENV="${BUILD_DIR}/env"
PIP="${ENV}/bin/pip -q --isolated"
VIRTUALENV="${PYTHON} ${VENV_DIR}/virtualenv.py -q"

#--

mkdir -p "${BUILD_DIR}"

# fetch/unpack the tarball of wheels
if [ ! -d "$PYOBJC_DIR" ]; then
  if [ ! -f "$PYOBJC_TAR" ]; then
    echo "${PYOBJC_URL}"
    curl -L -# "${PYOBJC_URL}" -o "${PYOBJC_TAR}"
  fi
  tar xzf "${PYOBJC_TAR}" -C "${BUILD_DIR}"
fi

# grab a copy of virtualenv to help with the installation
if [ ! -d "$VENV_DIR" ]; then
  if [ ! -f "${VENV_TAR}" ]; then
    echo "${VENV_URL}"
    curl -L -# "${VENV_URL}" -o "${VENV_TAR}"
  fi
  tar xzf "${VENV_TAR}" -C "${BUILD_DIR}"
fi

# create a temporary env that we'll only use for its pip command
if [ ! -d "${ENV}" ]; then
  echo "Setting up staging area..."
  $VIRTUALENV "${ENV}"
fi

# use our local pip to unpack the wheels into a subdirectory
if [ ! -d "$DEST_DIR" ]; then
  echo "Unpacking ${PYOBJC_PKG}..."
  $PIP install --target="${DEST_DIR}" --no-index --find-links="${PYOBJC_DIR}" pyobjc
fi

#--
