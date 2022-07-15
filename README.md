PlotDevice
==========
PlotDevice is a Macintosh application used for computational graphic design. It 
provides an interactive Python environment where you can create two-dimensional 
graphics and output them in a variety of vector, bitmap, and animation formats. 
It is meant both as a sketch environment for exploring generative design and as
a general purpose graphics library for use in external Python programs.

PlotDevice scripts can create images from simple geometric primitives, text, and
external vector or bitmap images. Drawing commands provide a thin abstraction
over macOS's Quartz graphics engine, providing high-quality rendering
of 2D imagery and powerful compositing operations.

#### Requirements

The PlotDevice application requires macOS 11 or greater (either on Intel or Apple Silicon) 
and comes bundled with a Python 3.10 distribution. The module can be installed via `pip3` 
on Python versions ≥3.6 (including the interpreter from the Xcode 
[command line tools](https://developer.apple.com/download/all/?q=command%20line%20tools%20for%20xcode)
and those [installed through Homebrew](https://docs.brew.sh/Homebrew-and-Python)).

#### Latest changes (July 2022)

Over the years since the last release, progress in both macOS and Python itself led to quite
a bit of breakage. Some of the highlights of this maintenance release include:

###### New Features
- Runs natively on Intel and Apple Silicon and supports retina displays
- Python 3 support (including a bundled 3.10 installation in the app)
- images can now be exported in HEIC format and videos support H.265 (HEVC)
- SVG files can now be drawn to the canvas using the `image()` command (thanks to the magical [SwiftDraw](https://github.com/swhitty/SwiftDraw) library)
- image exports have a configurable `zoom` to create 2x/3x/etc ‘retina’ images
- revamped `var()` command for creating GUIs to modify values via sliders, buttons, toggles, etc.
- updated text editor with multiple tabs, new themes, and additional key-binding modes emulating Sublime Text and VS Code
- the module's command line interface is now accessible through `python3 -m plotdevice`
- the command line tool has a new `--install` option to download [PyPI](https://pypi.org) packages for use within the app
- document autosaving is now user-configurable 

###### Bugfixes
- exported images generated on retina machines now have the proper dimensions
- hex colors can now use lowercase letters
- automatic variables like `WIDTH` & `HEIGHT` correctly support the `/` operator
- the Color object's `.blend()` method is working again
- the `read()` command can now handle csv files with spaces in their header row names
- the `translate()` command now incorporates non-pixel grid units set via the `size()` command
- cmyk exports are working reliably for command line `--export` and via the `export(cmyk=True)` method
- arguments defined using the command line tool's `--args` options are now passed to the script's `sys.argv`

###### Misc. Improvements
- the command line tool can be exited via ctrl-c in addtion to being Quit from the menu bar
- simplified unicode handling (and improved support for normalization of user-provided strings)
- building the module now only requires Xcode command line tools—not a full Xcode.app installation
- the `text()` command will always treat its first argument as content (even if it's not a string) unless a `str`, `xml`, or `src` keyword argument is provided
- the mouse pointer is now visible in full-screen mode (and will auto-hide when inactive)

###### Unfortunate Casualties
- The NodeBox Libraries (`coreimage`, `colors`, and friends) would require quite a bit of attention to get working properly again. 
  A first pass can be found in the [`plotdevice-libs` repository](https://github.com/plotdevice/plotdevice-libs) but they're not
  ready for prime-time. If you're interested in contributing, this would be a terrific place to start!

Installation
------------

PlotDevice supports being built as either a full-fledged Cocoa application, or as
a standard Python module to be installed into a virtualenv alongside your source files.
In both cases it now includes a command line tool called [`plotdevice`](#running-scripts) allowing you to run
scripts and perform batch exports from the console.

#### Application builds

The application can be built in Xcode with the `PlotDevice.xcodeproj` project. It can also
be built from the command line by using `python3 setup.py app` (which uses Xcode) or 
`python3 setup.py py2app` (which uses setuptools). 

The resulting binary will appear in the `dist` subdirectory and can be moved to your
Applications folder or any other fixed directory. To install a symlink to the command
line tool, launch the app from its installed location and click the Install button in
the Preferences window.

Prebuilt application binaries can be downloaded from the [PlotDevice site](https://plotdevice.io).

#### Module builds

PlotDevice can also be built as a Python module, allowing you to rely on an external editor
and launch scripts from the command line (or from a ‘shebang’ line at the top of your
script invoking the `plotdevice` tool). To install the module and command line tool use
`python3 setup.py install`

Easier still, you can install the module directly from PyPI with a simple `pip3 install plotdevice`.
It's a good idea to install the `wheel` module first since it greatly speeds up installation of the
PyObjC libraries PlotDevice depends on.

#### Alternative Python Interpreters

When using [pyenv](https://github.com/pyenv/pyenv) (or compiling Python from source) you have the
option of building the interpreter as a **Framework**. This gives you access to a GUI interface for
running PlotDevice scripts via the `python3 -m plotdevice` command. Non-framework builds support the
command line's `--export` functionality and will open a viewer window, but will not show an icon in
the Dock or give you access to the menu bar.

To set up and run a script using a Framework build, do something along the lines of:
```console
env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.10.4
pyenv shell 3.10.4
pip3 install plotdevice
python3 -m plotdevice <script.pv>
``` 

#### Building from source

You can also clone the git repository and build PlotDevice as a module or application from scratch. 
Consult the [build instructions](https://github.com/plotdevice/plotdevice/discussions/59) for details.

Documentation
-------------

The [PlotDevice Manual](https://plotdevice.io/manual) provides extensive documentation of the
various drawing commands and features sample code for nearly all of them. In addition to a 
detailed Reference, the manual also contains a number of Tutorial chapters that explain 
PlotDevice's inner workings concept-by-concept. 

Beyond the core API, the Manual also collects documentation for the set of third-party Libraries 
that were written by the NodeBox community and ported to work with PlotDevice.

Running scripts
---------------

Once you have installed PlotDevice and added the `plotdevice` command to your shell's path,
it can be used to run scripts in a window or export graphics to file using one of the
supported image/video formats. The command itself is just a shorthand for running the module
directly via `python3 -m plotdevice` (which accepts all the same command line arguments).

#### Command line usage
```
plotdevice [-h] [-f] [-b] [-q] [--live] [--cmyk] [--virtualenv PATH] [--args [a [b ...]]]
           [--export FILE] [--frames N or M-N] [--fps N] [--rate N] [--loop [N]] [--install [PACKAGES ...]]
           file
```

> ##### Runtime arguments
> `-h`                  show the help message then quit  
> `-f`                  run full-screen  
> `-b`                  run PlotDevice in the background (i.e., leave focus in the active application)  
> `-q`                  run a PlotDevice script ‘quietly’ (without opening a window)  
> `--virtualenv PATH`   path to a virtualenv whose libraries you want to use (this should point to the top-level virtualenv directory)  
> `--args [a [b ...]]`  arguments to be passed to the script as sys.argv
>
> ##### External editor integration
> `-b`                  run PlotDevice in the background (i.e., don't switch apps when the script is run)  
> `--live`              re-render graphics each time the file is saved
>
> ##### Image/animation export
> `--export FILE`       a destination filename ending in `pdf`, `eps`, `png`, `tiff`, `jpg`, `heic`, `gif`, or `mov`  
> `--zoom PERCENT`      scale of the output image (100 = regular size) unless specified by a filename ending in @2x/@3x/etc
> `--cmyk`              convert colors to CMYK before generating images (colors will be RGB if omitted)
>
> ##### Animation options
> `--frames N or M-N`   number of frames to render or a range specifying the first and last frames (default `1-150`)  
> `--fps N`             frames per second in exported video (default `30`)  
> `--rate N`            video bitrate in megabits per second (default `1`)  
> `--loop [N]`          number of times to loop an exported animated gif (omit `N` to loop forever)
>
> ##### Installing Packages from [PyPI](https://pypi.org):
> `--install [packages ...]` Use `pip install` to download libraries into the  **~/Library/Application Support/PlotDevice** directory, making 
> them `import`-able in the application and by scripts run from the command line



#### Usage examples

```bash
# Run a script
plotdevice script.pv

# Run fullscreen
plotdevice -f script.pv

# Save script's output to pdf
plotdevice script.pv --export output.pdf

# Create an animated gif that loops every 2 seconds
plotdevice script.pv --export output.gif --frames 60 --fps 30 --loop

# Create a sequence of numbered png files – one for each frame in the animation
plotdevice script.pv --export output.png --frames 10

# Create a 5 second long H.265 video at 2 megabits/sec
plotdevice script.pv --export output.mov --frames 150 --rate 2.0

# Install some useful modules
plotdevice --install urllib3 jinja2 numpy
```


Using external libraries
------------------------

Since PlotDevice scripts are pure Python, the entirety of the
[stdlib](https://docs.python.org/3/library/) and [PyPI](https://pypi.python.org/pypi)
are available to you. In addition, a wide array of PlotDevice Libraries have been contributed
by the community to solve more visualization-specific problems.

#### Installing PlotDevice Libraries

‘[Libraries](https://plotdevice.io/tut/Libraries)’ are Python modules that have been
written specifically for PlotDevice. To install a Library, copy its folder to `~/Library/Application Support/PlotDevice` and then `import` it from your script.
Libraries can be installed individually or en masse using the archive
([35 MB](https://plotdevice.io/extras/plotdevice-libs.zip)) from the PlotDevice website.

#### Installing Python modules

The easiest way to use third-party modules from a PlotDevice script is to create a
[`virtualenv`](https://virtualenv.org) and use `pip3` to install your dependencies.
You can then launch your script with the `--virtualenv` option to add them to
the import path:

```bash
$ python3 -m venv env
$ source ./env/bin/activate
(env)$ pip3 install redis
(env)$ plotdevice script.pv --virtualenv ./env
```

If you're using PlotDevice as a module rather than an application, you have the option
of installing it directly into the virtualenv containing your script's other dependencies.
This places the `plotdevice` tool at a known location relative to your script and lets you
omit the `--virtualenv` option:

```bash
$ python3 -m venv env
$ source ./env/bin/activate
(env)$ pip3 install plotdevice
(env)$ pip3 install requests envoy bs4 # some other useful packages
(env)$ plotdevice script.pv # uses the tool found at ./env/bin/plotdevice
```

Using PlotDevice as a module
----------------------------

Though the `plotdevice` command provides a convenient way to launch scripts with the PlotDevice interpreter,
you may prefer to use the module's graphics context and export functions from within your own script (and running
whichever `python` binary your system or virtualenv provides). Importing the `plotdevice` module's contents
initializes your script's namespace with one identical to a script running with the app or command line tool.
For instance, the following will draw a few boxes:

```python
#!/usr/bin/env python3
from plotdevice import *
for x, y in grid(10,10,12,12):
    rect(x,y, 10,10)
```

You can then generate output files using the global `export` command. It takes a file path as an argument
and the format will be determined by the file extension (`pdf`, `eps`, `png`, `jpg`, `gif`, or `tiff`):

```python
export('~/Pictures/output.pdf')
```

If you plan to generate multiple images, be sure to call `clear()` to erase the canvas in between frames.
Depending on the task you may also want to reset the graphics state. Use one of:

```python
clear()    # erases the canvas
clear(all) # erases the canvas and resets colors, transforms, effects, etc.
```

If you would prefer to avoid `import *` and keep the PlotDevice API encapsulated in an object, create a 
`Context` and access its methods instead. For instance, the previous code snippets are equivalent to:

```python
#!/usr/bin/env python3
from plotdevice.context import Context

ctx = Context()
for x, y in ctx.grid(10,10,12,12):
    ctx.rect(x,y, 10,10)
ctx.export('~/Pictures/output.pdf')
ctx.clear()
```

##### The `export` context manager
The `export` function returns a [context manager](https://docs.python.org/2/reference/compound_stmts.html#the-with-statement)
that encapsulates this clear/draw/save cycle for both single images and animations. By enclosing
your drawing code in a `with` block, you can ensure that the correct sequence of `clear` and `export`
calls is generated automatically. For instance these two methods of generating a png are equivalent:

```python
from plotdevice import *

# export an image
clear(all)
... # (do some drawing)
export('output.png')

# export an image (with the context manager clearing and saving the canvas automatically)
with export('output.png'):
    ... # (do some drawing)
```

###### Animations
If you specify a filename ending in `mov` – or `gif` if you also pass a `loop` or `fps` argument – the `export` context manager will return a `Movie` object. Each time you call its `add` method, a new
frame with the contents of the canvas will be added to the end of the animation. Once you've added
the final frame, you must call `finish` to wait for the video encoder thread to complete its work.

As with the single-image version of the `export` call, you can use the `with` statement in your
code to tidy up some of the frame-drawing boilerplate. All three examples are equivalent (note the
use of a nested `with` statement in the final example):

```python
# export a 100-frame movie
movie = export('anim.mov', fps=50, bitrate=1.8)
for i in xrange(100):
    clear(all)  # erase the previous frame from the canvas
    ...         # (do some drawing)
    movie.add() # add the canvas to the movie
movie.finish()  # wait for i/o to complete
```
```python
# export a movie (with the context manager finishing the file when done)
with export('anim.mov', fps=50, bitrate=1.8) as movie:
    for i in xrange(100):
        clear(all)  # erase the previous frame from the canvas
        ...         # (do some drawing)
        movie.add() # add the canvas to the movie
```
```python
# export a movie (with the context manager finishing the file when done)
# let the movie.frame context manager call clear() and add() for us
with export('anim.mov', fps=50, bitrate=1.8) as movie:
    for i in xrange(100):
        with movie.frame:
            ... # draw the next frame
```

###### Multi-page PDFs
Creating PDF documents works the same way, letting you either manually `clear`, `add` and `finish`
the export or take advantage of the `with` statement to hide the repetitive bits. Note that PDF exports
use the `page` attribute rather than `frame`:

```python
# export a five-page pdf document
pdf = export('multipage.pdf')
for i in xrange(5):
    clear(all) # erase the previous page's graphics from the canvas
    ...        # (do some drawing)
    pdf.add()  # add the canvas to the pdf as a new page
pdf.finish()   # write the pdf document to disk
```
```python
# export a pdf document more succinctly
with export('multipage.pdf') as pdf:
    for i in xrange(5):
        with pdf.page:
            ... # draw the next page
```

###### Image sequences
If you're generating a series of images, `export` will automatically give them consecutive names
derived from the filename you pass as an argument. If the filename is a simple `"name.ext"` string,
the sequence number will be appended with four characters of padding (yielding `"name-0001.ext"`,
`"name-0002.ext"`, etc.). 

If the filename contains a number between curly braces (e.g., `"name-{4}.ext"`), that substring will be replaced with the sequence number and zero padded to the specified number of digits:

```python
# export a sequence of images to output-0001.png, output-0002.png, ...
#                                output-0099.png, output-0100.png
with export('output.png') as img:
    for i in xrange(100):
        with img.frame:
            ... # draw the next image in the sequence
```
```python
# export a sequence of images to 01-img.png, 02-img.png, ...
#                                99-img.png, 100-img.png
with export('{2}-img.png') as img:
    for i in xrange(100):
        with img.frame:
            ... # draw the next image in the sequence
```

Lineage
-------
PlotDevice was derived from [NodeBox](https://nodebox.net/code/index.php/Home)'s 1.9.7 release. Its current maintainer is
[Christian Swinehart](mailto:drafting@samizdat.co).

NodeBox is a BSD-licensed graphics environment written by [Frederik De Bleser](mailto:frederik@burocrazy.com).  
The NodeBox manual and example code are by [Tom De Smedt](mailto:tomdesmedt@organisms.be).

NodeBox is a fork of [DrawBot](https://drawbot.com) by [Just van Rossum](mailto:just@letterror.com).

License
-------

PlotDevice is released under the [MIT license](https://opensource.org/licenses/MIT). Use it as you see fit.

Contributing
------------
The PlotDevice source is available on GitHub: https://github.com/plotdevice/plotdevice
