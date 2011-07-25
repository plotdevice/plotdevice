from AppKit import *
from Foundation import *
from PyDETextView import getBasicTextAttributes, getSyntaxTextAttributes
from PyDETextView import setTextFont, setBasicTextAttributes, setSyntaxTextAttributes

# class defined in NodeBoxPreferences.xib
class NodeBoxPreferencesController(NSWindowController):
    commentsColorWell = objc.IBOutlet()
    fontPreview = objc.IBOutlet()
    funcClassColorWell = objc.IBOutlet()
    keywordsColorWell = objc.IBOutlet()
    stringsColorWell = objc.IBOutlet()

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

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "textFontChanged:", "PyDETextFontChanged", None)

    def windowWillClose_(self, notification):
        fm = NSFontManager.sharedFontManager()
        fp = fm.fontPanel_(False)
        if fp is not None:
            fp.setDelegate_(None)
            fp.close()

    @objc.IBAction
    def updateColors_(self, sender):
        if self.timer is not None:
            self.timer.invalidate()
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0, self, "timeToUpdateTheColors:", None, False)

    def timeToUpdateTheColors_(self, sender):
        syntaxAttrs = getSyntaxTextAttributes()
        syntaxAttrs["string"][NSForegroundColorAttributeName] = self.stringsColorWell.color()
        syntaxAttrs["keyword"][NSForegroundColorAttributeName] = self.keywordsColorWell.color()
        syntaxAttrs["identifier"][NSForegroundColorAttributeName] = self.funcClassColorWell.color()
        syntaxAttrs["comment"][NSForegroundColorAttributeName] = self.commentsColorWell.color()
        setSyntaxTextAttributes(syntaxAttrs)

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

    def textFontChanged_(self, notification):
        basicAttrs = getBasicTextAttributes()
        font = basicAttrs[NSFontAttributeName]
        self.fontPreview.setFont_(font)
        size = font.pointSize()
        if size == int(size):
            size = int(size)
        s = u"%s %s" % (font.displayName(), size)
        self.fontPreview.setStringValue_(s)
