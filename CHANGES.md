PlotDevice 1.0.0
-----------------

##### New Features
* Runs natively on Intel and Apple Silicon and supports retina displays
* Python 3 support (including a bundled 3.10 installation in the app)
* images can now be exported in HEIC format and videos support H.265 (HEVC)
* SVG files can be drawn to the canvas using the `image()` command (thanks to the magical [SwiftDraw](https://github.com/swhitty/SwiftDraw) library)
* image exports have a configurable `zoom` to create 2x/3x/etc ‘retina’ images
* revamped `var()` command for creating GUIs to modify values via sliders, buttons, toggles, etc.
* updated text editor with multiple tabs, new themes, and additional key-binding modes emulating Sublime Text and VS Code
* the module's command line interface is now accessible through `python3 -m plotdevice`
* the command line tool has a new `--install` option to download [PyPI](https://pypi.org) packages for use within the app
* document autosaving is now user-configurable 

##### Bugfixes
* exported images generated on retina machines now have the proper dimensions
* hex colors can now use lowercase letters
* automatic variables like `WIDTH` & `HEIGHT` correctly support the `/` operator
* the Color object's `.blend()` method is working again
* the `read()` command can now handle csv files with spaces in their header row names
* the `translate()` command now incorporates non-pixel grid units set via the `size()` command
* cmyk exports are working reliably for command line `--export` and via the `export(cmyk=True)` method
* arguments defined using the command line tool's `--args` options are now passed to the script's `sys.argv`

##### Misc. Improvements
* the command line tool can be exited via ctrl-c in addtion to being Quit from the menu bar
* simplified unicode handling (and improved support for normalization of user-provided strings)
* building the module now only requires Xcode command line tools—not a full Xcode.app installation
* the `text()` command will always treat its first argument as content (even if it's not a string) unless a `str`, `xml`, or `src` keyword argument is provided
* the mouse pointer is now visible in full-screen mode (and will auto-hide when inactive)

##### Unfortunate Casualties
* The NodeBox Libraries (`coreimage`, `colors`, and friends) would require quite a bit of attention to get working properly again. 
  A first pass can be found in the [`plotdevice-libs` repository](https://github.com/plotdevice/plotdevice-libs) but they're not
  ready for prime-time. If you're interested in contributing, this would be a terrific place to start!

PlotDevice 0.10.0
-----------------

##### CORE
* Much faster import times on 10.10+ thanks to a bundled copy of PyObjC 3.0.4
* Support for Python 3 and Homebrew builds of the interpreter
* Now using core animation layers to (hopefully) speed up graphics rendering
* `plot()` command can now override grob attributes like `x`, `y`, `width`, or `fill` when a
  new value is passed as a keyword arg
* HTTP is now handled by the requests module and caches responses locally
* Primitives can now accept Point, Size, and Region types as arguments
  (e.g., `rect(text("foo",20,20).bounds)`)
* `transform()` now accepts a `matrix` keyword arg to fully specify an affine transform

##### TYPOGRAPHY
* Enhanced `font()` command with support for OpenType/AAT features (currently
  supporting `lig`, `sc`, `osf`, `tab`, `vpos`, and `frac` args).
* New `layout()` command handles ‘paragraph styles’ including: `align`,
  `hyphenate`, `leading`, `spacing`, `indent`, and `margin` (replacing the
  `align()` and `lineheight()` commands).
* `text()` supports all `font()` and `layout()` keyword args for one-off styling
* `text()` can now read text from file paths or urls passed as its `src` keyword arg
* Letterspacing can now be set (in terms of thousandths of an em) via the
  `tracking` arg to font/text/stylesheet
* New `paginate()` command will break a long string into as many Text objects as
  necessary to fully lay out long runs of type
* New `Text.flow()` method will break long text runs into multiple columns
* New [Tutorial](http://plotdevice.io/tut/Typography) in the user manual documenting
  the changes

##### BUGFIXES
* Added 130+ unit tests (run them with `python setup.py test`)
* Fixes for `measure()`, `textpath()`, `Bezier.fit()`, and `read()` (which was crashing on
  URLs that didn't provide a Last-Modified header)
* `__file__` global variable now defined for .pv scripts
* The `Preferences` dialog box now works on systems with non-standard homedir locations


PlotDevice 0.9.4
----------------
* External scripts can use `from plotdevice import *` to create a drawing environment.
* Color commands now support gradients and image-based patterns
* Strokes can now be dashed lines of configurable segment lengths
* Added `pen()` command, incorporating `strokewidth()`, `joinstyle()`, and `capstyle()`
* The canvas `size()` can be set to non-pixel units (`cm`, `inch`, `pica`, etc.)
* Commands dealing with angles can be switched between radians & degrees with `geometry()`
* Added compositing support via the `blend()`, `alpha()`, and `shadow()` commands
* New utility methods: `fonts()`, `export()`, `read()`, `measure()`, `ordered()`, `shuffled()`
* Font styles can be set at the character level using the `stylesheet()` command
* The `font()` command accepts separate family and weight strings (not just PostScript Names)
* In addition to `rect()` and `oval()` you can now use `poly()` and `arc()`
* Grobs can be manually added/removed from the canvas with `plot()` and `clear()`
* New `halt()` command to "gracefully" bail out of an animation
* Libraries no longer require `ximport()` (since they now use `plotdevice.lib.register`)
* Quitting the app and re-launching will restore all open (auto-saved) documents
* Integrated the Sparkle framework for auto-updating of official builds
* Replaced the NSTextView-based editor with the much more capable ace.js
* Modernized document-window UI, keyboard shortcuts, and prefs panel
* Revised and extended User Manual

PlotDevice 0.9 (unreleased)
---------------------------
* Enhanced command line interface.
* Video export in H.264 or animated gif formats (with GCD-based i/o).
* Virtualenv support (for both installation of the module and running in-app with dependencies).
* Build system now works with Xcode or `py2app` for the application and `pip` for the module.
* A few more text colors are configurable in the preferences pane.
* Disabled scrollWheel and wheelDelta event data (to support ‘responsive scrolling’)
* Simplified bezier path API (including `with` statement support): `bezier()`, `clip()`
* Transformation commands all support the `with` statement
* Added support for external editors by reloading the source when changed.
* Example scripts are now embedded in the app and accessed from the menu bar
* Python 2.7, virtualenv support, and 64 bit extensions (now requires OS X 10.9+).

NodeBox 1.9.7
-------------
* Compatibility with Mac OS X 10.7 Lion (auto-saving! versions!).
* ellipse() is an alias for oval(). Path.ellipse() works as well.
* Support for Line cap and line join styles. Use joinstyle() with MITER, ROUND or BEVEL and capstyle() with BUTT, ROUND or SQUARE. Path.joinstyle = MITER and Path.capstyle = BUTT works as well.

NodeBox 1.9.6
-------------
* NSImage are no longer cached internally, which gave problems when rendering a large and small version of the same image.
* New, easier build system that includes all required NodeBox C extensions.

NodeBox 1.9.5
-------------
* Functions that need to run on NodeBox exit can be registered with the standard atexit module.

NodeBox 1.9.4
-------------
* You can now add a "stop" method in your animation, that gets executed when the animation is stopped.
* Full-screen scaling is corrected.
* Removed AppleScript support.

NodeBox 1.9.3
-------------
* Added the ability to zoom the canvas, even while running an animation.
* Boolean operations on paths: Use path.intersects(other) to check if two paths intersect.
  You can also use path.union(other), path.intersect(other), path.difference(other), path.xor(other)
  to get a new path with the boolean operation applied. Check out the SwissCheese example in the
  Advanced folder.
* Fit operation on paths that fits a path to the given boundaries:
    fit(self, x=None, y=None, width=None, height=None, stretch=False)
* Included psyco in the core build so the graph library is faster.
* Included numpy in the core (next to Numeric) for faster math.
* Jumping to a certain line number works.

NodeBox 1.9.2
-------------
* Color objects still worked in CMYK when used as a fill/stroke.
* Progress bar changed for Leopard compatibility.

NodeBox 1.9.1
-------------
* 1.9.0 was Intel only -- this is a Universal build.

NodeBox 1.9.0
-------------
* You can now export to PNG, JPEG, TIFF and GIF.
* Clipping works. There is a new ClippingPath, which you can also access directly.
* BezierPath and Text accepts keyword parameters for filling/stroking, so you can do:

    p = BezierPath(fill=(1, 0, 0), stroke=0, strokewidth=5)

* Colors are no longer calibrated in RGB color space. This gives correct results.
* Added new outputmode command that you can set to CMYK or RGB. All colors will adhere to the color mode.
* NodeBox is now packaged: DrawingPrimitives is obsoleted in favor of nodebox.graphics.
  This also means you can work directly with the context:

    from nodebox.graphics import Context
	ctx = Context()
	ctx.background(None) # Make transparent PNG
	ctx.size(300, 300)
	ctx.rect(0, 0, 100, 100, fill=(0.5, 0.1, 0.3))
	ctx.save("test.png") # Supported: PDF, PNG, TIFF, JPEG, GIF

* BezierPath, Image and Text objects support copying: path.copy() gives you a fresh copy you can transform.
* Text input now gets converted to unicode, which means you can do:

    text(None, 100, 100)

* BezierPath, Text and Image can be transformed after they are created:

    t = Text("hello", 100, 100)
    t.rotate(5)
    t.scale(0.2)

* You can save and clear the canvas at any time during execution:

    rect(0, 0, 100, 100)
    canvas.save('one-rect.tiff')
    rect(110, 0, 100, 100)
    canvas.save('two-rects.tiff')
    canvas.clear() # The canvas is now empty when drawn on-screen

* Access NodeBox from the command line for very simple scripts:

    from nodebox.console import make_movie
    make_movie('text(FRAME, 100, 100)', 'test.mov', 100)

* Fullscreen mode now has the correct mouse position, and is clipped correctly.
* QuickTime export uses QTKit.
* Errors while drawing now appear in the output view.
* "graphicsView" is no longer set in the namespace.
* Image.image, BezierPath.path and Transform.transform  are deprecated --
  use Image._nsImage, BezierPath._nsBezierPath and Transform._nsAffineTransform instead.

NodeBox 1.8.5
-------------
* Equals function checks for None
* BezierPath.points and bezier.points now also return the value at t=1.0.
* Added new examples: Interactivity/Drawing.py and Path/Spider.py.

NodeBox 1.8.4
-------------
* Fixed a bug in bezier.insert_point
* Fullscreen mode accepts key input. Mouse position is still flipped, though
* Stop command now removes the ValueLadder
* Fixed bug in ValueLadder where a source file with unicode characters would give an error.

NodeBox 1.8.3
-------------
* NodeBox is now a universal binary, including all of its libraries.
* You can now install python libraries in "/Users/<yourusername>/Library/Application Support/NodeBox". NodeBox will automatically create this directory when starting up.
* The bezier library is now an integral part of NodeBox.

NodeBox 1.8.2
-------------
* Direct view is turned of because it broke vector output.
* AppleScripting is back.

NodeBox 1.8.1
--------------
* The view now creates an image of the rendered canvas rather than rendering it each time on redraw.
  This speeds up scrolling significantly.
* Stop button works -- thanks to code from PyEdit
* Runs under PyObjC 1.4, which means Intel support.
* Panther support was dropped.

NodeBox 1.0rc7
--------------
* Added a button variable:

    var("dothething", BUTTON)

  If there is a method called "dothething" in your script, it will be called.
  The label on the button will be "dothething".

* Fixed "Copy As PDF" to place PDF images, Postscript images, and TIFF files.
  (thanks to Peter Lewis for pointing this out)
* Added AppleScript support for running and exporting scripts.

NodeBox 1.0rc6
--------------
* Fixed page numbering.
* Document properties removed from menu.
* Added global variable FRAME, which works in the same way as PAGENUM, but for animations.

NodeBox 1.0rc5
--------------
* Added QuickTime export. (thanks to Bob Ippolito)
* PDF export can now export animations too.
* Default values on var method now register, and booleans work.
* drawpath now works as it should, and accepts a list of points.
* Experimental fix for clipping code.

NodeBox 1.0rc4
--------------
* Uses a scene graph internally for speeding things up. All objects now have an inheritFromContext that copies all state out of the context and into the objects.
* Added animation. Adding a speed method indicates that the script is an animation. Animation scripts have a setup() method that does initial setup, and a draw() method that is called for each frame. You can use the throttle to change parameters while the animation is running.
* Removed document properties and variables. NodeBox doesn't touch the code anymore.
* Added measurements for centimeters, milimeters and inches. Just use 5*cm for 5 centimeters.
* All drawing commands are now methods of the Context object. This makes sure that canvases don't interfere with eachother. NOTE: This will have some problems when drawing from libraries. Most notably, "from DrawingPrimitives import *" doesn't work anymore. However, libraries that do drawing can be imported with ximport("mylibrary") to automatically gain access to the _ctx global that has all drawing methods.
* BezierPaths are no longer lists internally. They can still be accessed as a sequence, but the returned PathElements are not bound to the path. To manipulate the PathElements, iterate over the sequence, do the changes and use the BezierPath constructor with a list of PathElements as argument.

NodeBox 1.0rc3
--------------
* Paths returned from rect, oval, line, star, arrow, endpath and textpath now return an un-transformed path. Drawing the path does the transformation. This gives a proper value when asking the bounds() for a path. (bug #62)
* textpath ignores the align state when no width is given. (bug #63)
* New NodeBox icon.

NodeBox 1.0rc2
--------------
* Fixed PDF export. (One of the resource files still referred to DrawBot)

NodeBox 1.0rc1
--------------
* To avoid confusions, this DrawBot version was renamed to NodeBox.

Version 1.0rc1
--------------
* image command has a working w (width) and h (height) parameter, that constrain the bounds of the image to the given width and height.
* the image cache is now updated in the imagesize command. Previously, if the image was not in cache, imagesize would keep reloading it from disk. Also, caches are kept between runs and check the modification date on the file.
* All geometry commands (rect, oval, line, star, arrow, endpath) have a draw parameter that can be set to False. Each of them return the (transformed) path.
* Added beginclip and endclip. Beginclip takes a path to use as the clipping path.
* Added textpath command which returns a (transformed) path of the text. Works exactly as the standard text command. (using optional width and height)
* Fixed bug where having a last line with a tab character would fail the compile.
* Fixed interface and unicode problems on the variables panel. Default values can now be accented strings.
* Default color is now real black instead of DrawBot-black.
* Fixed bug where drawing text without width parameter, but with align set to center or right would not display text.
* Giving tuples as arguments to fill and stroke work again. (E.g. fill((1,0,0)) )
* Switched from bundlebuilder to py2app.
* Cleared up the confusion when using two controller panels: they now get the name of the document they're connected to.
* Fixed bug that displayed EPS files on a different position than bitmap files.
* Added roundness parameter to the rectangle function.
* The BezierPath object got a major overhaul: it now integrates nicely with the state model (using the transformedpath method) and is actually a list containing PathElement objects that contain a command, x and y coordinates and (optionally) control points.
* All 'w' and 'h' parameters were changed to 'width' and 'height' (image, strokewidth)
* All of the major state change commands return their state: font, fontsize, lineheight, align, colormode, fill, stroke, strokewidth, transform.
* Documentation is user-friendler and inside of the DrawBot application, so that it can be accessed through Apple's Help system.

Version 0.9b9
-------------
* ValueLadder now respects type of original value: if the original is an integer, the new value will be an integer as well.
* Fixed booleans in variables interface.
* Shift-dragging the value ladder now adds hundreths of a number instead of tenths.
* Fixed an obscure bug when using CMYK color objects to set the fill (they used the infamous "DrawBot-black" because the converted from the RGB system instead of CMYK)
* Turned of line highlighting on error because of bugs in PyDETextView.

Version 0.9b8
-------------
* Fixed textmetrics in all modes: both center- and corner-mode transforms, and outlined and 'real' fonts.
* You can now enter a width parameter for the textwidth command. (Looks silly, is sometimes handy)
* Added a visual interface for setting the size of the canvas. (Which is now just a function)
* Added sliders: elements that allow you to change pre-defined properties of your composition in real-time.
* Added a visual interface for changing sliders.
* Added a toolbar for access to all this visual goodness.
* Added the value ladder for "rapid-prototyping" a value. You really have to see it to believe it. Just command-click on any number in the code and drag right or left to increase or decrease its value. By going up or down the ladder, you change the size of the increments. As an alternative method, you can also hold the command key and use the mouse wheel to change a number (hold the option key as well for smaller increments, or the control key for larger increments)
* Syntax coloring for all DrawBot keywords.
* The colormode command now has an extra parameter "range", where you define the range of your colors. By default, this is set to 1.0, but you can set it to 255 so color ranges go from 0 to 255. (for Photoshop compatibility)
* Syntax errors and run-time errors highlight the line where the error has occurred.

Version 0.9b7
-------------
* Find works in source and message views.
* grid() function now has option shuffled that shuffles the order of the grid (good for overlaying elements in a grid)
* Fixed some errors in the color object.
* The size comment now takes floating point numbers. (E.g. "#size: 595.3 841.9")
* The export function now remembers the folder you last exported to.
* Fixed some errors in the Color object, notably with CMYK values
* Added __doc__ attribute to the namespace, that you can use to store values. The __doc__ attribute persists between runs, and is defined for each DrawBot document.

Version 0.9b6
-------------
* Reworked the Color object to make it compliant with the fill() commands. The initializer is pretty smart right now. Properties can be accessed using long or short names (e.g. mycolor.red or mycolor.r)
* textwidth() and textheight() command that measure the metrics of a single-line and multi-line string, respectively.
* text() command can take the optional 'height' parameter that sets the maximum height of the text block.
* text() command returns the text bounds. (In the same way as textmetrics() would do)
* size, width and height property for the Image object. You can use imagewidth() and imageheight() also.
* Fixed a bug where outlined text could not be stroked when the fill color was not set.
* The drawing region (DrawBotGraphicsView, a subclass of NSView) is acccessible using the graphicsView variable. This is only intented for hackers and will remain undocumented.
* Added the 'New with code' command which invokes OttoBot.

Version 0.9b5
-------------
* All colors in DrawBot are now converted to CMYK internally. (for certified PDF compliance)
* text() command can take the optional 'width' parameter, causing text to wrap in a block.
* align() command sets the alignment for blocks of text (LEFT, CENTER, RIGHT or JUSTIFY)
* Added multi-page export interface using the setAccessoryView for the export dialog box.
* Added shortcut for export command.
* Added much-improved examples folder, showing all the possibilities of DrawBot.
* "DrawBot Help" menu item opens a browser to http://drawbot.grafitron.com/manual/

Version 0.9b4
-------------
* Added colormode() command that switches between RGB, HSB and CMYK.
* Added star() and arrow() commands.
* Added autotext() command that uses the Kant Generator Pro to automatically generate text using a grammar file.
* The infamous grid() command.

Version 0.9b3
-------------
* Transformations now happen from the center of each object, not from the canvas' corner. However, this behaviour is switchable using the transform() command.
* Added skew() command.
* Added random() and choice() command. Random is pretty clever; choice is just an import from the random package.
* Added files() command that uses glob to display a list of files based on a search pattern.
* New icon! (thanks to Nico and Just)
* First release with actual documentation.

Version 0.9b2
-------------
* Flipped the canvas. Coordinates start from the top-left corner now. This required massive changes to transformations. Most notably, transformations are not directly set internally, but the resulting bezier paths of a drawing command are transformed when filling and/or stroking the object.

Version 0.9b1
-------------
* First release using direct commands and state machine. This means commands for drawing primitives, text and images, state modifiers such as fill() and stroke(), and transformation commands such as rotate(), scale(), push() and pop().

Version 0.9a1
-------------
* Just's first public release of DrawBot.