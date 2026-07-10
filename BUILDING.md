# Building PlotDevice from Source

If you’re interested in using the bleeding edge code from the repository (or doing development work on the 
library/app itself), there are a few different ways to build it. 

## Requirements

- macOS 11+ and Xcode or the Xcode command line tools (`xcode-select --install`)
- A Python 3.8+ interpreter with wheel availability for `pyobjc-core==11.1`
  (i.e. not a brand-new Python release that predates PyObjC’s own support for it)

## Local dev environment

`python3 make.py dev` sets up a self-contained virtualenv at `deps/local/<python-version>/` 
and ensures PlotDevice’s dependencies (including its native-code extensions) are installed.
Once this environment has been set up you can use `python3 -m plotdevice <script.pv>` or 
`app/plotdevice <script.pv>` to run scripts directly from the repo.

## Module builds

The `plotdevice` Python module depends on native code in the `deps/extensions` directory
but can be installed like any other `pyproject.toml`-based package. From the repo root, type one of:
```console
pip3 install .     # for a regular install
pip3 install -e .  # editable install, for dev work on plotdevice/*.py
```
You can run the test suite with:
```console
python3 -m tests
```

Redistributable `sdists` and wheels can be built via:
```console
python3 -m build --sdist
python3 -m build --wheel
```

## Application builds

The `make.py` script contains utilites for building **PlotDevice.app** (i.e., the full GUI application).
If you have the full Xcode installed on your system, you can build the app (including its own embedded copy
of Python) with:
```console
python3 make.py app
```

Alternatively (if you only have the Xcode command line tools installed) you can use `py2app`, which can
be especially useful for quick, local tests:
```console
python3 make.py py2app
```

## CI/Maintainer scripts

The `make.py` script contains other subcommands that are primarily useful for packaging:
```console
python3 make.py clean        # remove build artifacts
python3 make.py distclean    # also remove the embedded Python.framework and deps/local
python3 make.py dist         # build app (codesigned, notarized, and zipped) and update release.json
```

Note that `dist` requires a "Developer ID Application" signing identity and a `notarytool` keychain profile
named `AC_NOTARY`, and is intended for release builds only.
