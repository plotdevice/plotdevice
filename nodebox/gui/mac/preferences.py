from AppKit import *
from Foundation import *

def get_default(label, packed=False):
    if not label.startswith('NS'):
        label = 'nodebox:%s'%label
    pref = NSUserDefaults.standardUserDefaults().objectForKey_(label)
    return pref if not packed else unpackAttrs(pref)

def set_default(label, value, packed=False):
    if not label.startswith('NS'):
        label = 'nodebox:%s'%label    
    value = value if not packed else packAttrs(value)
    NSUserDefaults.standardUserDefaults().setObject_forKey_(value, label)

FG_COLOR = NSForegroundColorAttributeName
BG_COLOR = NSBackgroundColorAttributeName
from pprint import pformat
def unpackAttrs(d):
    unpacked = {}
    for key, value in d.items():
        if key == NSFontAttributeName:
            value = NSFont.fontWithName_size_(value['name'], value['size'])
        elif key in (FG_COLOR, BG_COLOR):
            r, g, b, a = map(float, value.split())
            value = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a)
        elif isinstance(value, (dict, NSDictionary)):
            value = unpackAttrs(value)
        unpacked[key] = value
    return unpacked

def packAttrs(d):
    packed = {}
    for key, value in d.items():
        if key == NSFontAttributeName:
            value = {"name": value.fontName(), "size": value.pointSize()}
        elif key in (FG_COLOR, BG_COLOR):
            channels = value.colorUsingColorSpaceName_(NSCalibratedRGBColorSpace).getRed_green_blue_alpha_(None, None, None, None)
            value = " ".join(map(str, channels))
            packed = {key:value}
            break
        elif isinstance(value, (dict, NSDictionary)):
            value = packAttrs(value)
        packed[key] = value
    return packed

def getBasicTextAttributes():
    return get_default("text-attributes", packed=True)

from pprint import pprint,pformat
def getSyntaxTextAttributes():
    syntax = {}
    basic = get_default("text-attributes", packed=True)
    for fontname,attrs in get_default("text-colors", packed=True).items():
        syntax[fontname] = dict(attrs.items()+basic.items())
    return syntax

def setBasicTextAttributes(basicAttrs):
    if basicAttrs != getBasicTextAttributes():
        set_default("text-attributes", basicAttrs, packed=True)
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_("PyDETextFontChanged", None)

def setSyntaxTextAttributes(syntaxAttrs):
    if syntaxAttrs != getSyntaxTextAttributes():
        # print "changed from",pformat(getSyntaxTextAttributes())
        # print "to",pformat(syntaxAttrs)

        set_default("text-colors", syntaxAttrs, packed=True)
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_("PyDETextFontChanged", None)

def setTextFont(font):
    basicAttrs = getBasicTextAttributes()
    syntaxAttrs = getSyntaxTextAttributes()
    basicAttrs[NSFontAttributeName] = font
    for v in syntaxAttrs.values():
        v[NSFontAttributeName] = font
    setBasicTextAttributes(basicAttrs)
    setSyntaxTextAttributes(syntaxAttrs)

# class defined in NodeBoxPreferences.xib
class NodeBoxPreferencesController(NSWindowController):
    fontPreview = objc.IBOutlet()
    useCALayer = objc.IBOutlet()
    keepWindows = objc.IBOutlet()
    commentsColorWell = objc.IBOutlet()
    funcClassColorWell = objc.IBOutlet()
    keywordsColorWell = objc.IBOutlet()
    stringsColorWell = objc.IBOutlet()
    plainColorWell = objc.IBOutlet()
    errColorWell = objc.IBOutlet()
    pageColorWell = objc.IBOutlet()
    selectionColorWell = objc.IBOutlet()

    def init(self):
        self = self.initWithWindowNibName_("NodeBoxPreferences")
        self.setWindowFrameAutosaveName_("NodeBoxPreferencesPanel")
        self.timer = None
        return self

    def awakeFromNib(self):
        self.textFontChanged_(None)
        syntaxAttrs = getSyntaxTextAttributes()
        self.stringsColorWell.setColor_(syntaxAttrs["string"][FG_COLOR])
        self.keywordsColorWell.setColor_(syntaxAttrs["keyword"][FG_COLOR])
        self.funcClassColorWell.setColor_(syntaxAttrs["identifier"][FG_COLOR])
        self.commentsColorWell.setColor_(syntaxAttrs["comment"][FG_COLOR])
        self.plainColorWell.setColor_(syntaxAttrs["plain"][FG_COLOR])
        self.errColorWell.setColor_(syntaxAttrs["err"][FG_COLOR])
        self.pageColorWell.setColor_(syntaxAttrs["page"][BG_COLOR])
        self.selectionColorWell.setColor_(syntaxAttrs["selection"][BG_COLOR])
        self._wells = [self.commentsColorWell, self.funcClassColorWell, self.keywordsColorWell, self.stringsColorWell, self.plainColorWell, self.errColorWell, self.pageColorWell, self.selectionColorWell]

        self.useCALayer.setState_(NSOffState if get_default('use-ca-layer') else NSOnState)
        self.keepWindows.selectCellAtRow_column_(0, 0 if get_default('NSQuitAlwaysKeepsWindows') else 1)

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "textFontChanged:", "PyDETextFontChanged", None)
        nc.addObserver_selector_name_object_(self, "blur:", "NSWindowDidResignKeyNotification", None)

    def windowWillClose_(self, notification):
        fm = NSFontManager.sharedFontManager()
        fp = fm.fontPanel_(False)
        if fp is not None:
            fp.setDelegate_(None)
            fp.close()

    @objc.IBAction
    def updateLayerUsage_(self, sender):
        set_default('use-ca-layer', NSOffState==self.useCALayer.state())

    @objc.IBAction
    def updateOpenBehavior_(self, sender):
        set_default('NSQuitAlwaysKeepsWindows', 0==self.keepWindows.selectedColumn())

    @objc.IBAction
    def updateColors_(self, sender):
        if not self.timer:
            self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.2, self, "timeToUpdateTheColors:", None, True)

    def timeToUpdateTheColors_(self, sender):
        syntaxAttrs = getSyntaxTextAttributes()
        syntaxAttrs["string"][FG_COLOR] = self.stringsColorWell.color()
        syntaxAttrs["keyword"][FG_COLOR] = self.keywordsColorWell.color()
        syntaxAttrs["identifier"][FG_COLOR] = self.funcClassColorWell.color()
        syntaxAttrs["comment"][FG_COLOR] = self.commentsColorWell.color()
        syntaxAttrs["plain"][FG_COLOR] = self.plainColorWell.color()
        syntaxAttrs["err"][FG_COLOR] = self.errColorWell.color()
        syntaxAttrs["page"][BG_COLOR] = self.pageColorWell.color()
        syntaxAttrs["selection"][BG_COLOR] = self.selectionColorWell.color()
        setSyntaxTextAttributes(syntaxAttrs)
        active = [w for w in self._wells if w.isActive()]
        if not active:
            self.stopUpdating()

    def stopUpdating(self):
        if self.timer:
            self.timer.invalidate()
            self.timer = None

    @objc.IBAction
    def chooseFont_(self, sender):
        fm = NSFontManager.sharedFontManager()
        basicAttrs = get_default("text-attributes", packed=True)
        fm.setSelectedFont_isMultiple_(basicAttrs[NSFontAttributeName], False)
        fm.orderFrontFontPanel_(sender)
        fp = fm.fontPanel_(False)
        fp.setDelegate_(self)

    @objc.IBAction
    def changeFont_(self, sender):
        oldFont = get_default("text-attributes", packed=True)[NSFontAttributeName]
        newFont = sender.convertFont_(oldFont)
        if oldFont != newFont:
            setTextFont(newFont)
    
    def blur_(self, note):
        self.stopUpdating()
        for well in [w for w in self._wells if w.isActive()]:
            well.deactivate()
        NSColorPanel.sharedColorPanel().orderOut_(objc.nil)

    def textFontChanged_(self, notification):
        basicAttrs = get_default("text-attributes", packed=True)
        font = basicAttrs[NSFontAttributeName]
        self.fontPreview.setFont_(font)
        size = font.pointSize()
        if size == int(size):
            size = int(size)
        s = u"%s %s" % (font.displayName(), size)
        self.fontPreview.setStringValue_(s)

    def __del__(self):
        self.stopUpdating()
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, "PyDETextFontChanged", None)
        nc.removeObserver_name_object_(self, "NSWindowDidResignKeyNotification", None)


def defaultDefaults():
    _basicFont = NSFont.userFixedPitchFontOfSize_(11)
    _BASICATTRS = {NSFontAttributeName: _basicFont,
                   NSLigatureAttributeName: 0}
    _SYNTAXCOLORS = {
        # text colors
        "keyword": {FG_COLOR: NSColor.blueColor()},
        "identifier": {FG_COLOR: NSColor.redColor().shadowWithLevel_(0.2)},
        "string": {FG_COLOR: NSColor.magentaColor()},
        "comment": {FG_COLOR: NSColor.grayColor()},
        "plain": {FG_COLOR: NSColor.blackColor()},
        "err": {FG_COLOR: NSColor.colorWithRed_green_blue_alpha_(167/255.0, 41/255.0, 34/255.0, 1.0)},
        # background colors
        "page": {BG_COLOR: NSColor.whiteColor()},
        "selection": {BG_COLOR: NSColor.colorWithRed_green_blue_alpha_(175/255.0, 247/255.0, 1.0, 1.0)},
    }
    for key, value in _SYNTAXCOLORS.items():
        newVal = _BASICATTRS.copy()
        newVal.update(value)
        _SYNTAXCOLORS[key] = NSDictionary.dictionaryWithDictionary_(newVal)
    _BASICATTRS = NSDictionary.dictionaryWithDictionary_(_BASICATTRS)

    return {
        "NSQuitAlwaysKeepsWindows": True,
        "nodebox:use-ca-layer": True,
        "nodebox:text-attributes": packAttrs(_BASICATTRS),
        "nodebox:text-colors": packAttrs(_SYNTAXCOLORS),
    }
NSUserDefaults.standardUserDefaults().registerDefaults_(defaultDefaults())
