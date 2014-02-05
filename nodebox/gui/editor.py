# encoding: utf-8
import os
import re
import objc
import json
from time import time
from bisect import bisect
from Foundation import *
from AppKit import *
from WebKit import *
from nodebox.gui.preferences import getBasicTextAttributes, getSyntaxTextAttributes
from nodebox.gui.preferences import setTextFont, FG_COLOR, BG_COLOR
from nodebox.util.PyFontify import fontify
from nodebox.gui.widgets import ValueLadder
from nodebox.gui.app import set_timeout
from nodebox import bundle_path

class EditorView(NSView):
    document = objc.IBOutlet()

    def awakeFromNib(self):
        print "EditorView", self.document
        self.webview = WebView.alloc().init()
        self.webview.setFrameLoadDelegate_(self)
        self._queue = []
        self._wakeup = None

        self.addSubview_(self.webview)
        html = bundle_path('Contents/Resources/editor/ui.html')
        ui = file(html).read().decode('utf-8')
        baseurl = NSURL.fileURLWithPath_(os.path.dirname(html))
        self.webview.mainFrame().loadHTMLString_baseURL_(ui, baseurl)

    def _get_source(self):
        return self.webview.stringByEvaluatingJavaScriptFromString_('editor.source();')
    def _set_source(self, src):
        # print u'editor.source("%s")'%src
        self.js(u'editor.source(%s)'%json.dumps(src, ensure_ascii=False))

    source = property(_get_source, _set_source)

    def resizeSubviewsWithOldSize_(self, oldSize):
        self.resizeWebview()

    def resizeWebview(self):
        self.webview.setFrame_(self.bounds())

    def focus(self):
        self.js('editor.focus();')

    def js(self, cmds):
        if not isinstance(cmds, (list,tuple)):
            cmds = [cmds]
        self._queue.extend(cmds)
        if not self._wakeup:
            self._wakeup = set_timeout(self, '_execute', 0.2)

    def _execute(self):
        if self.webview.isLoading():
            self._wakeup = set_timeout(self, '_execute', 0.2)
        else:
            for op in self._queue:
                self.webview.stringByEvaluatingJavaScriptFromString_(op)
            self._queue = []



class OutputTextView(NSTextView):
    endl = False
    scroll_lock = True

    def awakeFromNib(self):
        self.ts = self.textStorage()
        self.colorize()
        self.setTextContainerInset_( (0,4) ) # a pinch of top-margin
        self.setUsesFindBar_(True)

        # use a FindBar rather than FindPanel
        self._finder = NSTextFinder.alloc().init()
        self._finder.setClient_(self)
        self._finder.setFindBarContainer_(self.enclosingScrollView())
        self._findTimer = None
        self.setUsesFindBar_(True)

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "textFontChanged:", "PyDETextFontChanged", None)

    def textFontChanged_(self, font):
        self.setFont_(getBasicTextAttributes()[NSFontAttributeName])
        self.colorize()

    def canBecomeKeyView(self):
        return False

    def colorize(self):
        attrs = getSyntaxTextAttributes()
        pageColor = attrs['page'][BG_COLOR]
        plainColor = attrs['plain'][FG_COLOR]
        self.setBackgroundColor_(pageColor)
        # self.setDrawsBackground_(True)

        self.setTypingAttributes_(attrs['plain'])
        self.setSelectedTextAttributes_(attrs['selection'])

    def _attrs(self, stream=None):
        attrs = getSyntaxTextAttributes()
        attrs.update({
            'message':attrs['plain'],
            'info':dict(attrs['plain'])
        })
        attrs['info'][FG_COLOR] = attrs['plain'][FG_COLOR].colorWithAlphaComponent_(0.5)
        for s,a in attrs.items():
            a.update({"stream":s})
        if stream:
            return attrs.get(stream)
        return attrs

    def changeColor_(self, clr):
        pass # ignore system color panel

    def append(self, txt, stream='message'):
        if not txt: return
        defer_endl = txt.endswith(u'\n')
        txt = (u"\n" if self.endl else u"") + (txt[:-1 if defer_endl else None])
        atxt = NSAttributedString.alloc().initWithString_attributes_(txt, self._attrs(stream))
        self.ts.beginEditing()
        self.ts.appendAttributedString_(atxt)
        self.ts.endEditing()
        self.scrollRangeToVisible_(NSMakeRange(self.ts.length()-1, 0))
        self.endl = defer_endl
        self.setNeedsDisplay_(True)

    def clear(self, timestamp=False):
        self.endl = False
        self.ts.replaceCharactersInRange_withString_((0,self.ts.length()), "")
        self._begin = time()
        if timestamp:
            locale = NSUserDefaults.standardUserDefaults().dictionaryRepresentation()
            timestamp = NSDate.date().descriptionWithCalendarFormat_timeZone_locale_("%Y-%m-%d %H:%M:%S", None, locale)
            self.append(timestamp+"\n", 'info')

    def report(self, crashed, frames):
        if not hasattr(self, '_begin'):
            return
        val = time() - self._begin

        # print "ran for", (time() - self._begin), "then", ("crashed" if crashed else "exited cleanly")
        if crashed or (frames==None and val < 0.333):
            return
        hrs = val // 3600 
        val = val - (hrs * 3600)
        mins = val // 60
        secs = val - (mins * 60) 
        dur = ''           
        if hrs:
            dur = '%ih%i\'%1.1f"' % (hrs, mins, secs)
        else:
            dur = '%i\'%1.1f"' % (mins, secs)

        msg = "%i frame%s"%(frames, '' if frames==1 else 's') if frames else "rendered"
        outcome = "%s in %s\n"%(msg, dur)
        self.append(outcome, 'info')

    def performFindPanelAction_(self, sender):
        # same timer-based hack as PyDETextView.performFindPanelAction_
        # what could be the problem? something in the tab-ordering of the
        # views? or is the containing splitview getting involved?
        super(OutputTextView, self).performFindPanelAction_(sender)
        if self._findTimer:
            self._findTimer.invalidate()
        self._findEditor = self.window().firstResponder().superview().superview()
        self._findTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.05, self, "stillFinding:", None, True)

    def stillFinding_(self, note):
        active = self._findEditor.superview().superview() is not None
        if not active:
            self.window().makeFirstResponder_(self)
            self._findTimer.invalidate()
            self._findTimer = None

    def __del__(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, "PyDETextFontChanged", None)

