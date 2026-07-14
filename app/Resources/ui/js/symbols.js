// symbol name -> documentation URL.
var PLOTDEVICE_SYMBOL_DOCS = {
    // Canvas
    size: "https://plotdevice.io/ref/Canvas#size()",
    speed: "https://plotdevice.io/ref/Canvas#speed()",
    background: "https://plotdevice.io/ref/Canvas#background()",
    geometry: "https://plotdevice.io/ref/Canvas#geometry()",
    export: "https://plotdevice.io/ref/Canvas#export()",
    plot: "https://plotdevice.io/ref/Canvas#plot()",
    clear: "https://plotdevice.io/ref/Canvas#clear()",
    outputmode: "https://plotdevice.io/ref/Canvas#outputmode()",
    ximport: "https://plotdevice.io/ref/Canvas#ximport()",
    halt: "https://plotdevice.io/ref/Canvas#halt()",

    // Line & Color
    color: "https://plotdevice.io/ref/Line+Color#color()",
    stroke: "https://plotdevice.io/ref/Line+Color#stroke()",
    fill: "https://plotdevice.io/ref/Line+Color#fill()",
    pen: "https://plotdevice.io/ref/Line+Color#pen()",
    capstyle: "https://plotdevice.io/ref/Line+Color#capstyle()",
    colormode: "https://plotdevice.io/ref/Line+Color#colormode()",
    joinstyle: "https://plotdevice.io/ref/Line+Color#joinstyle()",
    nofill: "https://plotdevice.io/ref/Line+Color#nofill()",
    nostroke: "https://plotdevice.io/ref/Line+Color#nostroke()",
    strokewidth: "https://plotdevice.io/ref/Line+Color#strokewidth()",

    // Primitives
    poly: "https://plotdevice.io/ref/Primitives#poly()",
    rect: "https://plotdevice.io/ref/Primitives#rect()",
    arc: "https://plotdevice.io/ref/Primitives#arc()",
    oval: "https://plotdevice.io/ref/Primitives#oval()",
    line: "https://plotdevice.io/ref/Primitives#line()",
    image: "https://plotdevice.io/ref/Primitives#image()",
    text: "https://plotdevice.io/ref/Primitives#text()",
    arrow: "https://plotdevice.io/ref/Primitives#arrow()",
    star: "https://plotdevice.io/ref/Primitives#star()",

    // Drawing
    bezier: "https://plotdevice.io/ref/Drawing#bezier()",
    moveto: "https://plotdevice.io/ref/Drawing#moveto()",
    lineto: "https://plotdevice.io/ref/Drawing#lineto()",
    arcto: "https://plotdevice.io/ref/Drawing#arcto()",
    curveto: "https://plotdevice.io/ref/Drawing#curveto()",
    autoclosepath: "https://plotdevice.io/ref/Drawing#autoclosepath()",
    beginpath: "https://plotdevice.io/ref/Drawing#beginpath()",
    drawpath: "https://plotdevice.io/ref/Drawing#drawpath()",
    endpath: "https://plotdevice.io/ref/Drawing#endpath()",
    findpath: "https://plotdevice.io/ref/Drawing#findpath()",

    // Transform
    transform: "https://plotdevice.io/ref/Transform#transform()",
    translate: "https://plotdevice.io/ref/Transform#translate()",
    rotate: "https://plotdevice.io/ref/Transform#rotate()",
    scale: "https://plotdevice.io/ref/Transform#scale()",
    skew: "https://plotdevice.io/ref/Transform#skew()",
    reset: "https://plotdevice.io/ref/Transform#reset()",
    pop: "https://plotdevice.io/ref/Transform#pop()",
    push: "https://plotdevice.io/ref/Transform#push()",

    // Compositing
    alpha: "https://plotdevice.io/ref/Compositing#alpha()",
    blend: "https://plotdevice.io/ref/Compositing#blend()",
    shadow: "https://plotdevice.io/ref/Compositing#shadow()",
    clip: "https://plotdevice.io/ref/Compositing#clip()",
    mask: "https://plotdevice.io/ref/Compositing#mask()",
    noshadow: "https://plotdevice.io/ref/Compositing#noshadow()",
    beginclip: "https://plotdevice.io/ref/Compositing#beginclip()",
    endclip: "https://plotdevice.io/ref/Compositing#endclip()",

    // Typography
    font: "https://plotdevice.io/ref/Typography#font()",
    layout: "https://plotdevice.io/ref/Typography#layout()",
    stylesheet: "https://plotdevice.io/ref/Typography#stylesheet()",
    paginate: "https://plotdevice.io/ref/Typography#paginate()",
    textpath: "https://plotdevice.io/ref/Typography#textpath()",
    align: "https://plotdevice.io/ref/Typography#align()",
    fontsize: "https://plotdevice.io/ref/Typography#fontsize()",
    lineheight: "https://plotdevice.io/ref/Typography#lineheight()",
    textheight: "https://plotdevice.io/ref/Typography#textheight()",
    textmetrics: "https://plotdevice.io/ref/Typography#textmetrics()",
    textwidth: "https://plotdevice.io/ref/Typography#textwidth()",

    // Misc (Utility & Entropy)
    read: "https://plotdevice.io/ref/Misc#read()",
    measure: "https://plotdevice.io/ref/Misc#measure()",
    files: "https://plotdevice.io/ref/Misc#files()",
    fonts: "https://plotdevice.io/ref/Misc#fonts()",
    var: "https://plotdevice.io/ref/Misc#var()",
    imagesize: "https://plotdevice.io/ref/Misc#imagesize()",
    open: "https://plotdevice.io/ref/Misc#open()",
    random: "https://plotdevice.io/ref/Misc#random()",
    choice: "https://plotdevice.io/ref/Misc#choice()",
    shuffled: "https://plotdevice.io/ref/Misc#shuffled()",
    ordered: "https://plotdevice.io/ref/Misc#ordered()",
    grid: "https://plotdevice.io/ref/Misc#grid()",
    autotext: "https://plotdevice.io/ref/Misc#autotext()",

    // Objects: Drawing
    Bezier: "https://plotdevice.io/ref/Drawing#Bezier",
    Curve: "https://plotdevice.io/ref/Drawing#Curve",
    Image: "https://plotdevice.io/ref/Drawing#Image",
    Context: "https://plotdevice.io/ref/Drawing#Context",

    // Objects: Line & Color
    Color: "https://plotdevice.io/ref/Line+Color#Color",
    Gradient: "https://plotdevice.io/ref/Line+Color#Gradient",
    Shadow: "https://plotdevice.io/ref/Line+Color#Shadow",

    // Objects: Transform
    Point: "https://plotdevice.io/ref/Transform#Point",
    Size: "https://plotdevice.io/ref/Transform#Size",
    Region: "https://plotdevice.io/ref/Transform#Region",
    Transform: "https://plotdevice.io/ref/Transform#Transform",

    // Objects: Typography
    Text: "https://plotdevice.io/ref/Typography#Text",
    TextBlock: "https://plotdevice.io/ref/Typography#TextBlock",
    TextFragment: "https://plotdevice.io/ref/Typography#TextFragment",
    Font: "https://plotdevice.io/ref/Typography#Font",
    Family: "https://plotdevice.io/ref/Typography#Family",

    // Constants
    px: "https://plotdevice.io/ref/Misc#constants",
    pica: "https://plotdevice.io/ref/Misc#constants",
    inch: "https://plotdevice.io/ref/Misc#constants",
    cm: "https://plotdevice.io/ref/Misc#constants",
    mm: "https://plotdevice.io/ref/Misc#constants",
    pi: "https://plotdevice.io/ref/Misc#constants",
    tau: "https://plotdevice.io/ref/Misc#constants",
    RGB: "https://plotdevice.io/ref/Misc#constants",
    HSV: "https://plotdevice.io/ref/Misc#constants",
    CMYK: "https://plotdevice.io/ref/Misc#constants",
    CENTER: "https://plotdevice.io/ref/Misc#constants",
    CORNER: "https://plotdevice.io/ref/Misc#constants",
    DEGREES: "https://plotdevice.io/ref/Misc#constants",
    RADIANS: "https://plotdevice.io/ref/Misc#constants",
    PERCENT: "https://plotdevice.io/ref/Misc#constants",
    LEFT: "https://plotdevice.io/ref/Misc#constants",
    RIGHT: "https://plotdevice.io/ref/Misc#constants",
    JUSTIFY: "https://plotdevice.io/ref/Misc#constants",
    MOVETO: "https://plotdevice.io/ref/Misc#constants",
    LINETO: "https://plotdevice.io/ref/Misc#constants",
    CURVETO: "https://plotdevice.io/ref/Misc#constants",
    CLOSE: "https://plotdevice.io/ref/Misc#constants",
    MITER: "https://plotdevice.io/ref/Misc#constants",
    ROUND: "https://plotdevice.io/ref/Misc#constants",
    BEVEL: "https://plotdevice.io/ref/Misc#constants",
    BUTT: "https://plotdevice.io/ref/Misc#constants",
    SQUARE: "https://plotdevice.io/ref/Misc#constants",
    NORMAL: "https://plotdevice.io/ref/Misc#constants",
    FORTYFIVE: "https://plotdevice.io/ref/Misc#constants",
    NUMBER: "https://plotdevice.io/ref/Misc#constants",
    TEXT: "https://plotdevice.io/ref/Misc#constants",
    BOOLEAN: "https://plotdevice.io/ref/Misc#constants",
    BUTTON: "https://plotdevice.io/ref/Misc#constants",
    WIDTH: "https://plotdevice.io/ref/Misc#constants",
    HEIGHT: "https://plotdevice.io/ref/Misc#constants",
    FRAME: "https://plotdevice.io/ref/Misc#constants",
    PAGENUM: "https://plotdevice.io/ref/Misc#constants",
    MOUSEX: "https://plotdevice.io/ref/Misc#constants",
    MOUSEY: "https://plotdevice.io/ref/Misc#constants",
    mousedown: "https://plotdevice.io/ref/Misc#constants",
    KEY_UP: "https://plotdevice.io/ref/Misc#constants",
    KEY_DOWN: "https://plotdevice.io/ref/Misc#constants",
    KEY_LEFT: "https://plotdevice.io/ref/Misc#constants",
    KEY_RIGHT: "https://plotdevice.io/ref/Misc#constants",
    KEY_BACKSPACE: "https://plotdevice.io/ref/Misc#constants",
    KEY_TAB: "https://plotdevice.io/ref/Misc#constants",
    KEY_ESC: "https://plotdevice.io/ref/Misc#constants",

    // Dictionaries
    adict: "https://plotdevice.io/ref/Misc#dictionaries",
    ddict: "https://plotdevice.io/ref/Misc#dictionaries",
    odict: "https://plotdevice.io/ref/Misc#dictionaries",
}

// symbol name -> array of example usage lines (from each ref page's "Syntax" section).
var PLOTDEVICE_SYMBOL_USAGE = {
    // Canvas
    size: [`size(width, height, unit=px)`],
    speed: [`speed(fps)`],
    background: [
        `background(r, g, b, a=1.0)`,
        `background(h, s, b, a=1.0)`,
        `background(c, m, y, k, a=1.0)`,
        `background(k, a=1.0)`,
        `background(color)`,
        `background(None) # transparent backdrop`,
        `background(*colors, angle, steps=[0,1]) # axial gradient`,
        `background(*colors, steps=[0,1], center=[0,0]) # radial gradient`
    ],
    geometry: [`geometry(units)`],
    export: [
        `... # draw to the canvas`,
        `export("spool.pdf", cmyk=False)`,
        `... # draw at retina-quality to the canvas`,
        `export("spool.png", zoom=2)`,
        `with export("movie.mov", fps=30, bitrate=1.0):`,
        `    ... # draw movie frames`,
        `with export("anim.gif", fps=30, loop=0):`,
        `    ... # draw gif frames`
    ],
    plot: [`plot(grob)`],
    clear: [
        `clear()       # erase the canvas`,
        `clear(all)    # erase the canvas and reset drawing state`,
        `clear(*grobs) # remove specific objects from the canvas`
    ],
    outputmode: [`outputmode(mode)`],
    ximport: [`libname = ximport("libname")`],
    halt: [`halt()`],

    // Line & Color
    color: [
        `color(mode=RGB, range=1.0) # the default color mode and range`,
        `color(range=255)           # use 0-255 component values rather than 0–1`,
        `color(HSV)                 # color-related commands will expect HSV values`,
        `color(r, g, b, a=1)    # RGB mode`,
        `color(h, s, v, a=1)    # HSV mode`,
        `color(c, m, y, k, a=1) # CMYK mode`,
        `color(v, a=1)`
    ],
    stroke: [
        `stroke(r, g, b, a=1.0)`,
        `stroke(h, s, v, a=1.0)`,
        `stroke(c, m, y, k, a=1.0)`,
        `stroke(v, a=1.0)`,
        `stroke(color)`
    ],
    fill: [
        `fill(r, g, b, a=1.0)`,
        `fill(h, s, v, a=1.0)`,
        `fill(c, m, y, k, a=1.0)`,
        `fill(v, a=1.0)`,
        `fill(color)`,
        `fill(*colors, angle, steps=[0,1]) # axial gradient`,
        `fill(*colors, steps=[0,1], center=[0,0]) # radial gradient`
    ],
    pen: [`pen(nib, join=MITER, cap=BUTT, dash=None)`],
    capstyle: [`capstyle(style)`],
    colormode: [`colormode(mode, range=1.0)`],
    joinstyle: [`joinstyle(style)`],
    nofill: [`nofill()`],
    nostroke: [`nostroke()`],
    strokewidth: [`strokewidth(width)`],

    // Primitives
    poly: [`poly(self, x, y, radius, sides=4, points=None, plot=True, **style)`],
    rect: [`rect(x, y, width, height, roundness=0.0, radius=None, plot=True, **style)`],
    arc: [`arc(x, y, radius, range=None, ccw=False, close=False, plot=True, **style)`],
    oval: [`oval(x, y, width, height, plot=True, **style)`],
    line: [`line(x1, y1, x2, y2, plot=True)`],
    image: [
        `image(src, x, y, width=None, height=None, plot=True, **style)`,
        `image(x, y, width=None, height=None, src="path-or-url", plot=True, **style)`,
        `image(x, y, width=None, height=None, data="bytes-or-base64", plot=True, **style)`
    ],
    text: [
        `text(str, x, y, width=None, height=None, outline=False, plot=True, **options)`,
        `text(x, y, width=None, height=None, str="", **options)`,
        `text(x, y, width=None, height=None, xml="", **options)`,
        `text(x, y, width=None, height=None, src="<path or url>", **options)`
    ],
    arrow: [`arrow(x, y, width, type=NORMAL, plot=True, **style)`],
    star: [`star(x, y, points=20, outer=100, inner=50, plot=True, **style)`],

    // Drawing
    bezier: [
        `bezier(points=[], smooth=False, **opts)`,
        `bezier(path, **opts)`,
        `with bezier(x=0, y=0, **opts) as path:`,
        `    ... # drawing commands like moveto(), lineto(), arcto(), or curveto()`
    ],
    moveto: [`moveto(x, y)`],
    lineto: [`lineto(x, y, close=False)`],
    arcto: [
        `arcto(x, y, ccw=False, close=False)`,
        `arcto(cx, cy, x, y, radius, close=False)`
    ],
    curveto: [`curveto(h1x, h1y, h2x, h2y, x, y, close=False)`],
    autoclosepath: [`autoclosepath(close=True)`],
    beginpath: [`beginpath(x=None, y=None)`],
    drawpath: [`drawpath(path)`],
    endpath: [`endpath(draw=True)`],
    findpath: [`findpath(list, curvature=1.0)`],

    // Transform
    transform: [
        `transform(mode)`,
        `transform(matrix=[m11, m21, m12, m22, tX, tY])`,
        `with transform(mode=None, matrix=None):`,
        `    ... # drawing & transformation commands`,
        `with transform(CORNER):`,
        `    translate(100,20)`,
        `    line(0,0, 40,0)`,
        `oldmode = CENTER`,
        `transform(CORNER)`,
        `push()`,
        `translate(100,20)`,
        `line(0,0, 40,0)`,
        `pop()`,
        `transform(oldmode)`,
        `fill(0.2)`,
        `fontsize(14)`,
        `rotate(90)`,
        `text("one", 40, 80)`,
        ``,
        `with transform():`,
        `    rotate(-90)`,
        `    text("two", 40, 40)`,
        ``,
        `text("three", 50, 80)`
    ],
    translate: [`translate(x, y)`],
    rotate: [
        `rotate(amount) # amount to rotate (in default unit)`,
        `rotate(percent=0.5) # 0 ... 1.0`,
        `rotate(degrees=180) # 0 ... 360`,
        `rotate(radians=pi)  # 0 ... 2*pi (a.k.a. tau)`
    ],
    scale: [`scale(x, y=None)`],
    skew: [`skew(x, y=None)`],
    reset: [`reset()`],
    pop: [`pop()`],
    push: [`push()`],

    // Compositing
    alpha: [`alpha(opacity)`],
    blend: [`blend(mode)`],
    shadow: [`shadow(color, blur=10, offset=(5,5))`],
    clip: [`with clip(stencil, channel="alpha"):`],
    mask: [`with mask(stencil, channel="alpha"):`],
    noshadow: [`noshadow()`],
    beginclip: [`beginclip(path)`],
    endclip: [`endclip()`],

    // Typography
    font: [`font(family, weight, size, italic=False, **options)`],
    layout: [`layout(**options)`],
    stylesheet: [
        `stylesheet("name", *font, **options) # define a style`,
        `stylesheet("name") # retrieve a preexisting style`,
        `stylesheet("name", None) # undefine a style`
    ],
    paginate: [
        `paginate(str, x, y, width, height, **options)`,
        `paginate(x, y, width, height, str="", **options)`,
        `paginate(x, y, width, height, xml="", **options)`,
        `paginate(x, y, width, height, src="<path or url>", **options)`,
        `paginate(Text, folio=1, verso=None)`
    ],
    textpath: [`textpath(txt, x, y, width=None, height=1000000, **options)`],
    align: [`align(style=LEFT)`],
    fontsize: [`fontsize(size)`],
    lineheight: [`lineheight(height=None)`],
    textheight: [`textheight(txt, width=None, **options)`],
    textmetrics: [`textmetrics(txt, width=None)`],
    textwidth: [`textwidth(txt, width=None)`],

    // Misc (Utility & Entropy)
    read: [`read(path, format=None, encoding='utf-8', cols=None, dict=dict)`],
    measure: [
        `measure(grob)`,
        `measure(image="path", width=None, height=None)`,
        `measure("text", width=None, height=None, **fontstyle)`
    ],
    files: [`files(pattern, case=True)`],
    fonts: [`fonts(like=None, western=True)`],
    var: [
        `var(name, NUMBER, value=50, min=0, max=100, step=None, label=None)`,
        `var(name, TEXT, value, label=None)`,
        `var(name, BOOLEAN, value, label=None)`,
        `var(name, BUTTON, value, color=None, label=None)`
    ],
    imagesize: [`imagesize(path)`],
    open: [`open(path).read()`],
    random: [`random(v1=None, v2=None)`],
    choice: [`choice(sequence)`],
    shuffled: [`shuffled(sequence)`],
    ordered: [`ordered(list, *names, reverse=False)`],
    grid: [`grid(cols, rows, colsize=1, rowsize=1)`],
    autotext: [`autotext()`],

    // Objects: Drawing
    Bezier: [`Bezier()`],
    Curve: [`Curve()`],
    Context: [`Context()`],

    // Objects: Line & Color
    Color: [`Color()`],
    Gradient: [`Gradient(*colors, steps=[0,1], angle=0)`],
    Shadow: [`Shadow(color, blur=10, offset=(5,5))`],

    // Objects: Transform
    Point: [`Point(x, y)`],
    Size: [`Size(width, height)`],
    Region: [
        `Region(x, y, w, h)`,
        `Region(Point, Size)`
    ],
    Transform: [`Transform()`],

    // Objects: Typography
    Text: [
        `Text(str, x, y, width=None, height=None, **options)`,
        `Text(x, y, width=None, height=None, str="", **options)`,
        `Text(x, y, width=None, height=None, xml="", **options)`,
        `Text(x, y, width=None, height=None, src="<path or url>", **options)`
    ],
    Font: [`Font(family, weight, size, italic=False, **options)`],
    Family: [`Family(famname)`],
}
