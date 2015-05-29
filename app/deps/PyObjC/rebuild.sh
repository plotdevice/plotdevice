#!/bin/bash
#
# Build a new set of wheels from the current PyObjC sources on PyPI
#  - creates a tarball called wheelhouse-pyobjc-VERSION.tar.gz for use by setup.py
#  - the tarball can also be moved to plotdevice.io for use in typical installs
#  - the interpreter will be /usr/bin/python by defualt, but an alternate path
#    can be specified as the first command line arg when invoking the script
#
set -e

TOP=$(dirname "$0")
PYTHON=${1:-/usr/bin/python}
BUILD_DIR="${TOP}/build"

VENV_VERSION="13.0.1"
VENV_PKG="virtualenv-${VENV_VERSION}"
VENV_TAR="${TOP}/${VENV_PKG}.tar.gz"
VENV_URL="https://pypi.python.org/packages/source/v/virtualenv/${VENV_PKG}.tar.gz"
VENV_DIR="${BUILD_DIR}/${VENV_PKG}"

ENV="${BUILD_DIR}/env"
PIP="${ENV}/bin/pip"
VIRTUALENV="${PYTHON} ${VENV_DIR}/virtualenv.py -q"
PYOBJC_DIR="${BUILD_DIR}/wheelhouse"

#--

mkdir -p "${BUILD_DIR}"

# grab a copy of virtualenv to help with the installation
if [ ! -d "$VENV_DIR" ]; then
  if [ ! -f "${VENV_TAR}" ]; then
    echo "${VENV_URL}"
    curl -L -# "${VENV_URL}" -o "${VENV_TAR}"
  fi
  tar xzf "${VENV_TAR}" -C "${BUILD_DIR}"
fi

# create a temporary env that we'll only use for its pip command
rm -rf "$ENV"
if [ ! -d "${ENV}" ]; then
  echo "Setting up staging area..."
  $VIRTUALENV "${ENV}"
fi

# build wheels from the PyPI version of PyObjC,
rm -rf "$PYOBJC_DIR"
$PIP install pyobjc-core
$PIP wheel pyobjc -w "${PYOBJC_DIR}"

# stow a tarball of the wheelhouse in case we want to move it to the server
PYOBJC_VERSION=`${ENV}/bin/python -c 'import objc; print objc.__version__'`
tar czvf "${TOP}/wheelhouse-pyobjc-${PYOBJC_VERSION}.tar.gz" -C "${BUILD_DIR}" wheelhouse

# wipe out the env so setup.sh doesn't get an unexpected pyobjc-core
rm -rf "${BUILD_DIR}"

#--
