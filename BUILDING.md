# Building PlotDevice from Source

If you’re interested in unreleased code from the repository (or doing development work on the 
library/app itself), there are a few different ways to build it. 

## Requirements

- macOS 11+ and Xcode or the Xcode command line tools (`xcode-select --install`)
- A Python 3.9+ interpreter with wheel availability for `pyobjc-core==11.1`
  (i.e. not a brand-new Python release that predates PyObjC’s own support for it)


## Setting up Python

By default, macOS 12.3 and later only include a `python3` interpreter if you install Xcode (or its command line tools).
There are a few other ways to get a usable Python setup worth considering if you're interested in using
PlotDevice from the command line. A key feature distinguishing the different options is whether they 
install Python as a ‘framework’ or ‘stand-alone’:

> A **framework** Python installation allows PlotDevice to give you access to a GUI interface for
> running scripts via the `python3 -m plotdevice` command. **Stand-alone** Python is slightly more limited:
> it supports ‘headless’ use (via the command line tool’s [`--export`](#imageanimation-export) option) and 
> can open a window displaying your canvas, but it will not show an icon in the Dock or give you access to 
> commands in the menu bar.

### Xcode

The [Xcode command line tools](https://developer.apple.com/documentation/xcode/installing-the-command-line-tools/) provide a 
**framework** build of the (now somewhat long in the tooth) 3.9 release of Python. If you're okay running such an old interpreter, 
you can install the tools with the command:
```console
xcode-select --install
```

### Homebrew

The [Homebrew](https://docs.brew.sh/Homebrew-and-Python) package manager provides a **framework** build via its more up-to-date `python3` package. You can install it and run `plotdevice` with:
```console
brew install python3
```

### `pyenv`

The [pyenv](https://github.com/pyenv/pyenv) version manager lets you easily switch between multiple python versions on the same system. 
You can install a new **stand-alone** interpreter by specifying the version number:
```console
pyenv install 3.14.6
```

If you want a **framework** install, you need to pass a custom option via environment variables:
```console
env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.14.6
```

### `uv`

A newer alternative is [`uv`](https://docs.astral.sh/uv/), which uses its own prebuilt interpreters (but currently does not provide 
**framework** builds). If you're okay with the limitations of a **stand-alone** interpreter (see above), `uv` gives you a number of 
ways to  run PlotDevice.

Run a script without permanently installing `plotdevice`:
```console
uvx --from plotdevice plotdevice <script.pv>
```

Install `plotdevice` as a standalone CLI tool:
```console
uv tool install plotdevice
plotdevice <script.pv>
```

Add `plotdevice` as a dependency in a `uv`-managed project:
```console
uv python install 3.14
uv init myproject && cd myproject
uv add plotdevice
uv run plotdevice <script.pv>
```

## Local dev environment

`python3 make.py dev` sets up a self-contained virtualenv at `deps/local/<python-version>/` 
and ensures PlotDevice’s dependencies (including its native-code extensions) are installed.
Once this environment has been set up you can use `python3 -m plotdevice <script.pv>` or 
`app/plotdevice <script.pv>` to run scripts directly from the repo.

The dev environment is also useful for doing local builds of the app (since it has all the 
necessary dependencies pre-installed), so be sure to ‘activate’ it via the correct invocation 
for your shell before running one of the build commands:

```sh
source ./deps/local/<py-version>/bin/activate      # bash, zsh, etc.
source ./deps/local/<py-version>/bin/activate.fish # fish
source ./deps/local/<py-version>/bin/activate.csh  # tcsh
```

To stop using the dev environment and return to your global python interpreter run:
```sh
deactivate
```

## Application builds

The application can be built and debugged in Xcode with the `PlotDevice.xcodeproj` project.

The `make.py` script contains additional utilities for building **PlotDevice.app** (i.e., the full GUI application)
from the command line. If you have the full Xcode installed on your system, you can build the app 
(including its own embedded copy of Python) with:
```sh
python3 make.py app
```

Alternatively (if you only have the Xcode command line tools installed) you can use `py2app`, which can
be especially useful for quick, local tests:
```sh
python3 make.py py2app
```

The resulting binary will appear in the `dist` subdirectory and can be moved to your
Applications folder or any other fixed directory. To install a symlink to the command
line tool, launch the app from its installed location and click the Install button in
the Preferences window.

## Module builds

PlotDevice can also be built as a Python module, allowing you to rely on an external editor
and launch scripts from the command line (or from a ‘shebang’ line at the top of your
script invoking the `plotdevice` tool). 

The `plotdevice` Python module requires the compilation of native code in the `deps/extensions` directory
but can be installed like any other `pyproject.toml`-based package. From the repo root, type one of:
```sh
pip3 install .     # for a regular install
pip3 install -e .  # editable install, for dev work on plotdevice/*.py
```
You can run the test suite with:
```sh
python3 -m tests
```

Redistributable `sdists` and wheels can be built via:
```sh
python3 -m build --sdist
python3 -m build --wheel
```

## Utilities

The `make.py` script contains other subcommands that are primarily useful for packaging:
```sh
python3 make.py clean        # remove build artifacts
python3 make.py distclean    # also remove the embedded Python.framework and deps/local
python3 make.py icon         # regenerate app/Resources/Assets.car from app/art/PlotDevice-app.icon
python3 make.py dist         # build app (codesigned, notarized, and zipped) and update release.json
```

Note that `dist` requires a "Developer ID Application" signing identity and a `notarytool` keychain profile
named `AC_NOTARY`, and is intended for release builds only.
