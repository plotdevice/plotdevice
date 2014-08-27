PlotDevice
==========
PlotDevice is a Macintosh application used for computational graphic design. It provides an
interactive Python environment where you can create two-dimensional graphics
and output them in a variety of vector, bitmap, and animation formats. It is
meant both as a sketch environment for exploring generative design and as a
general purpose graphics library for use in external Python programs.

PlotDevice scripts can create images from simple geometric primitives, text, and
external vector or bitmap images. Drawing commands provide a thin abstraction
over Mac OS X's Quartz graphics engine, providing high-quality rendering
of 2D imagery and powerful compositing operations.

#### Derived from NodeBox

PlotDevice is a fork of the legacy [NodeBox 1](http://nodebox.net/code)
application with a number of updates taking advantage of recent OS features and
simplifying its build procedure. As a result it now happily runs on 64 bit systems,
uses Python 2.7, and makes use of the version of PyObjC provided by the system.
It requires a Macintosh running OS X 10.9 or greater.

#### Alternatives

Though Quartz is not by any means ‘slow’, its focus on rendering quality does
mean that if you're interested in doing realtime or interactive work you may
be better served by [NodeBox GL](http://www.cityinabottle.org/nodebox/). This
project's focus is on allowing your scripts to generate ‘camera ready’ graphics
and movies for use elsewhere. To that end it provides functionality to
efficiently export script output as vector documents (`pdf`,`eps`),
bitmap images (`png`,`gif`,`jpg`,`tiff`), or animations (`mov`,`gif`).

#### Latest changes (Aug 2014)

* Enhanced command line interface.
* Simplified api with broad support for the Python `with` statement
* New text editor with tab completion, syntax color themes, and emacs/vi bindings.
* Video export in H.264 or animated gif formats (with [GCD](http://en.wikipedia.org/wiki/Grand_Central_Dispatch)-based i/o).
* Core Graphics support for gradients, shadows, blend modes, and alpha channels
* Enhanced typography with inline styles and simpler font selection.
* Added support for external editors by reloading the source when changed.
* Build system now works with Xcode or `py2app` for the application and `pip` for the module.
* Virtualenv support (for both installation of the module and running scripts with dependencies).
* External scripts can use `from plotdevice import *` to create a drawing environment.
* Now uses the system's Python 2.7 interpreter.

Installation
------------

PlotDevice supports being built as either a full-fledged Cocoa application, or as
a standard Python module to be installed into a virtualenv alongside your source files.
In both cases it now includes a command line tool called [`plotdevice`](#running-scripts) allowing you to run
scripts and perform batch exports from the console.

#### Application builds

The application can be built in Xcode with the `PlotDevice.xcodeproj` project. It can also
be built from the command line by using `python setup.py app` (which uses Xcode) or 
`python setup.py py2app` (which uses setuptools). 

The resulting binary will appear in the `dist` subdirectory and can be moved to your
Applications folder or any other fixed directory. To install a symlink to the command
line tool, launch the app from its installed location and click the Install button in
the Preferences window.

Prebuilt application binaries can be downloaded from the [PlotDevice site](http://plotdevice.io).

#### Module builds

PlotDevice can also be built as a Python module, allowing you to rely on an external editor
and launch scripts from the command line (or from a ‘shebang’ line at the top of your
script invoking the `plotdevice` tool). To install the module and command line tool use
`python setup.py install`

Easier still, you can install the module directly from PyPI with a simple `pip install plotdevice`

Documentation
-------------

The [PlotDevice Manual](http://plotdevice.io/manual) provides extensive documentation of the
various drawing commands and features sample code for nearly all of them. In addition to a 
detailed Reference, the manual also contains a number of Tutorial chapters that explain 
PlotDevice's inner workings concept-by-concept. 

Beyond the core API, the Manual also collects documentation for the set of third-party Libraries 
that were written by the NodeBox community and ported to work with PlotDevice.

Running scripts
---------------

Once you have installed PlotDevice and added the `plotdevice` command to your shell's path,
it can be used to run scripts in a window or export graphics to file using one of the
supported image/video formats.

#### Command line usage

    plotdevice [-f] [-b] [--live] [--cmyk] [--virtualenv PATH] [--args [a [b ...]]]
               [--export FILE] [--frames N or M-N] [--fps N] [--rate N] [--loop [N]]
               file

> ##### Runtime arguments
> `-f`                  run full-screen  
> `--virtualenv PATH`   path to a virtualenv whose libraries you want to use (this should point to the top-level virtualenv directory)  
> `--args [a [b ...]]`  arguments to be passed to the script as sys.argv
>
> ##### External editor integration
> `-b`                  run PlotDevice in the background (i.e., don't switch apps when the script is run)  
> `--live`              re-render graphics each time the file is saved
>
> ##### Image/animation export
> `--export FILE`       a destination filename ending in `pdf`, `eps`, `png`, `tiff`, `jpg`, `gif`, or `mov`  
> `--cmyk`              convert colors to CMYK before generating images (colors will be RGB if omitted)
>
> ##### Animation options
> `--frames N or M-N`   number of frames to render or a range specifying the first and last frames (default `1-150`)  
> `--fps N`             frames per second in exported video (default `30`)  
> `--rate N`            video bitrate in megabits per second (default `1`)  
> `--loop [N]`          number of times to loop an exported animated gif (omit `N` to loop forever)


#### Usage examples

```sh
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

# Create a 5 second long H.264 video at 2 megabits/sec
plotdevice script.pv --export output.mov --frames 150 --rate 2.0
```


Using external libraries
------------------------

Since PlotDevice scripts are pure Python, the entirety of the
[stdlib](http://docs.python.org/2/library/) and [PyPI](https://pypi.python.org/pypi)
are avaliable to you. In addition, a wide array of PlotDevice Libraries have been contributed
by the community to solve more visualization-specific problems.

#### Installing PlotDevice Libraries

‘[Libraries](http://plotdevice.io/manual#lib)’ are Python modules that have been
written specifically for PlotDevice. To install a Library, copy its folder to `~/Library/Application Support/PlotDevice`
and then [`ximport`](http://nodebox.net/code/index.php/Libraries) it from your script.
Libraries can be installed individually or en masse using the archive
([35 MB](http://plotdevice.io/libs/plotdevice-libs.zip)) from the PlotDevice website.

#### Installing Python modules

The easiest way to use third-party modules from a PlotDevice script is to create a
[`virtualenv`](http://virtualenv.org) and use `pip` to install your dependencies.
You can then launch your script with the `--virtualenv` option to add them to
the import path:

```sh
$ virtualenv env
$ source ./env/bin/activate
(env)$ pip install redis
(env)$ plotdevice script.pv --virtualenv ./env
```

If you're using PlotDevice as a module rather than an application, you have the option
of installing it directly into the virtualenv containing your script's other dependencies.
This places the `plotdevice` tool at a known location relative to your script and lets you
omit the `--virtualenv` option:

```sh
$ virtualenv env
$ source ./env/bin/activate
(env)$ pip install plotdevice
(env)$ pip install requests envoy bs4 # some other useful packages
(env)$ plotdevice script.pv # uses the tool found at ./env/bin/plotdevice
```

Using PlotDevice as a module
-------------------------

Though the `plotdevice` command provides a convenient way to launch scripts with the PlotDevice interpreter,
you may prefer to use the module's graphics context and export functions from within your own script (and running
whichever `python` binary your system or virtualenv provides). Importing the `plotdevice` module's contents
initializes your script's namespace with one identical to a script running with the app or command line tool.
For instance, the following will draw a few boxes:

```py
#!/usr/bin/env python
from plotdevice.script import *
for x, y in grid(10,10,12,12):
    rect(x,y, 10,10)
```

You can then generate output files using the global `export` command. It takes a file path as an argument
and the format will be determined by the file extension (`pdf`, `eps`, `png`, `jpg`, `gif`, or `tiff`):

```py
export('~/Pictures/output.pdf')
```

If you plan to generate multiple images, be sure to call `clear()` to erase the canvas in between frames.
Depending on the task you may also want to reset the graphics state. Use one of:

```py
clear()    # erases the canvas
clear(all) # erases the canvas and resets colors, transforms, effects, etc.
```


##### The `export` context manager
The `export` function returns a [context manager](http://docs.python.org/2/reference/compound_stmts.html#the-with-statement)
that encapsulates this clear/draw/save cycle for both single images and animations. By enclosing
your drawing code in a `with` block, you can ensure that the correct sequence of `clear` and `export`
calls is generated automatically. For instance these two methods of generating a png are equivalent:

```py
from plotdevice.script import *

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

```py
# export a 100-frame movie
movie = export('anim.mov', fps=50, bitrate=1.8)
for i in xrange(100):
    clear(all)  # erase the previous frame from the canvas
    ...         # (do some drawing)
    movie.add() # add the canvas to the movie
movie.finish()  # wait for i/o to complete
```
```py
# export a movie (with the context manager finishing the file when done)
with export('anim.mov', fps=50, bitrate=1.8) as movie:
    for i in xrange(100):
        clear(all)  # erase the previous frame from the canvas
        ...         # (do some drawing)
        movie.add() # add the canvas to the movie
```
```py
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

```py
# export a five-page pdf document
pdf = export('multipage.pdf')
for i in xrange(5):
    clear(all) # erase the previous page's graphics from the canvas
    ...        # (do some drawing)
    pdf.add()  # add the canvas to the pdf as a new page
pdf.finish()   # write the pdf document to disk
```
```py
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

```py
# export a sequence of images to output-0001.png, output-0002.png, ...
#                                output-0099.png, output-0100.png
with export('output.png') as img:
    for i in xrange(100):
        with img.frame:
            ... # draw the next image in the sequence
```
```py
# export a sequence of images to 01-img.png, 02-img.png, ...
#                                99-img.png, 100-img.png
with export('{2}-img.png') as img:
    for i in xrange(100):
        with img.frame:
            ... # draw the next image in the sequence
```

Lineage
-------
PlotDevice was derived from [NodeBox](http://nodebox.net/code)'s 1.9.7 release. Its current maintainer is
[Chirstian Swinehart](mailto:drafting@samizdat.cc).

NodeBox is a BSD-licensed graphics environment written by [Frederik De Bleser](mailto:frederik@burocrazy.com).  
The NodeBox manual and example code are by [Tom De Smedt](mailto:tomdesmedt@organisms.be).

NodeBox is a fork of [DrawBot](http://drawbot.com) by [Just van Rossum](mailto:just@letterror.com).

License
-------

PlotDevice is released under the [MIT license](http://opensource.org/licenses/MIT). Use it as you see fit.

Contributing
------------
The PlotDevice source is available on GitHub: https://github.com/plotdevice/plotdevice
