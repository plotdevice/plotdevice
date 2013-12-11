from AppKit import *
from Foundation import *
from PyDETextView import getBasicTextAttributes, getSyntaxTextAttributes
from PyDETextView import setTextFont, setBasicTextAttributes, setSyntaxTextAttributes

# class defined in NodeBoxPreferences.xib
class NodeBoxPreferencesController(NSWindowController):
    fontPreview = objc.IBOutlet()
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
        syntaxAttrs = syntaxAttrs = getSyntaxTextAttributes()
        self.stringsColorWell.setColor_(syntaxAttrs["string"][NSForegroundColorAttributeName])
        self.keywordsColorWell.setColor_(syntaxAttrs["keyword"][NSForegroundColorAttributeName])
        self.funcClassColorWell.setColor_(syntaxAttrs["identifier"][NSForegroundColorAttributeName])
        self.commentsColorWell.setColor_(syntaxAttrs["comment"][NSForegroundColorAttributeName])
        self.plainColorWell.setColor_(syntaxAttrs["plain"][NSForegroundColorAttributeName])
        self.errColorWell.setColor_(syntaxAttrs["err"][NSForegroundColorAttributeName])
        self.pageColorWell.setColor_(syntaxAttrs["page"][NSBackgroundColorAttributeName])
        self.selectionColorWell.setColor_(syntaxAttrs["selection"][NSBackgroundColorAttributeName])
        self._wells = [self.commentsColorWell, self.funcClassColorWell, self.keywordsColorWell, self.stringsColorWell, self.plainColorWell, self.errColorWell, self.pageColorWell, self.selectionColorWell]

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
    def updateColors_(self, sender):
        if not self.timer:
            self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.2, self, "timeToUpdateTheColors:", None, True)

    def timeToUpdateTheColors_(self, sender):
        syntaxAttrs = getSyntaxTextAttributes()
        syntaxAttrs["string"][NSForegroundColorAttributeName] = self.stringsColorWell.color()
        syntaxAttrs["keyword"][NSForegroundColorAttributeName] = self.keywordsColorWell.color()
        syntaxAttrs["identifier"][NSForegroundColorAttributeName] = self.funcClassColorWell.color()
        syntaxAttrs["comment"][NSForegroundColorAttributeName] = self.commentsColorWell.color()
        syntaxAttrs["plain"][NSForegroundColorAttributeName] = self.plainColorWell.color()
        syntaxAttrs["err"][NSForegroundColorAttributeName] = self.errColorWell.color()
        syntaxAttrs["page"][NSBackgroundColorAttributeName] = self.pageColorWell.color()
        syntaxAttrs["selection"][NSBackgroundColorAttributeName] = self.selectionColorWell.color()
        setSyntaxTextAttributes(syntaxAttrs)
        active = [w for w in self._wells if w.isActive()]
        if not active:
            self.stopUpdating()

    def stopUpdating(self):
        if self.timer:
            self.timer.invalidate()
            self.timer = None
            NSLog("stopped")

    @objc.IBAction
    def chooseFont_(self, sender):
        fm = NSFontManager.sharedFontManager()
        basicAttrs = getBasicTextAttributes()
        fm.setSelectedFont_isMultiple_(basicAttrs[NSFontAttributeName], False)
        fm.orderFrontFontPanel_(sender)
        fp = fm.fontPanel_(False)
        fp.setDelegate_(self)

    @objc.IBAction
    def changeFont_(self, sender):
        oldFont = getBasicTextAttributes()[NSFontAttributeName]
        newFont = sender.convertFont_(oldFont)
        if oldFont != newFont:
            setTextFont(newFont)
    
    def blur_(self, note):
        self.stopUpdating()
        for well in [w for w in self._wells if w.isActive()]:
            well.deactivate()
        NSColorPanel.sharedColorPanel().orderOut_(objc.nil)

    def textFontChanged_(self, notification):
        basicAttrs = getBasicTextAttributes()
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
