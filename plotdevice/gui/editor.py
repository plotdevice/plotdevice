# encoding: utf-8
import os
import re
import json
import cgi
from io import open
from objc import super
from pprint import pprint
from time import time
from bisect import bisect
from ..lib.cocoa import *
from plotdevice.gui.preferences import get_default, editor_info
from plotdevice.gui import bundle_path, set_timeout

__all__ = ['EditorView', 'OutputTextView']

def args(*jsargs):
    return ', '.join([json.dumps(v, ensure_ascii=False) for v in jsargs])

class DraggyWebView(WebView):
    def initWithFrame_(self, rect):
        return self.initWithFrame_frameName_groupName_(rect, None, None)

    def draggingEntered_(self, sender):
        pb = sender.draggingPasteboard()
        options = { NSPasteboardURLReadingFileURLsOnlyKey:True,
                    NSPasteboardURLReadingContentsConformToTypesKey:NSImage.imageTypes() }
        urls = pb.readObjectsForClasses_options_([NSURL], options)
        strs = pb.readObjectsForClasses_options_([NSString], {})
        rewrite = u"\n".join([u'"%s"'%u.path() for u in urls] + strs) + u"\n"
        pb.declareTypes_owner_([NSStringPboardType], self)
        pb.setString_forType_(rewrite, NSStringPboardType)
        return super(DraggyWebView, self).draggingEntered_(sender)

    def performDragOperation_(self, sender):
        pb = sender.draggingPasteboard()
        txt = pb.readObjectsForClasses_options_([NSString], None)
        if txt:
            nc = NSNotificationCenter.defaultCenter()
            nc.postNotificationName_object_userInfo_('DropOperation', self, txt[0])
            sender.setAnimatesToDestination_(True)
            return True
        return False

    def shouldCloseWithWindow(self):
        return True

class EditorView(NSView):
    jumpPanel = IBOutlet()
    jumpLine = IBOutlet()

    # WebKit mgmt

    def awakeFromNib(self):
        self.webview = DraggyWebView.alloc().initWithFrame_(self.bounds())
        self.webview.setAllowsUndo_(False)
        self.webview.setFrameLoadDelegate_(self)
        self.webview.setUIDelegate_(self)
        self.addSubview_(self.webview)
        self.webview.setHidden_(True)

        html = bundle_path(rsrc='ui/editor.html')
        ui = open(html, encoding='utf-8').read()
        baseurl = NSURL.fileURLWithPath_(os.path.dirname(html))
        self.webview.mainFrame().loadHTMLString_baseURL_(ui, baseurl)

        # set a theme-derived background for the webview's clipview
        docview = self.webview.mainFrame().frameView().documentView()
        clipview = docview.superview()
        scrollview = clipview.superview()
        if clipview is not None:
            bgcolor = editor_info('colors')['background']
            clipview.setDrawsBackground_(True)
            clipview.setBackgroundColor_(bgcolor)
            scrollview.setVerticalScrollElasticity_(1)
            scrollview.setScrollerKnobStyle_(2)

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "themeChanged", "ThemeChanged", None)
        nc.addObserver_selector_name_object_(self, "fontChanged", "FontChanged", None)
        nc.addObserver_selector_name_object_(self, "bindingsChanged", "BindingsChanged", None)
        nc.addObserver_selector_name_object_(self, "insertDroppedFiles:", "DropOperation", self.webview)
        self._wakeup = set_timeout(self, '_jostle', .05, repeat=True)
        self._queue = []
        self._edits = 0
        self.themeChanged()
        self.fontChanged()
        self.bindingsChanged()

        mm=NSApp().mainMenu()
        self._doers = mm.itemWithTitle_('Edit').submenu().itemArray()[1:3]
        self._undo_mgr = None

    def drawRect_(self, rect):
        if self._wakeup:
            # try to minimize the f.o.u.c. while the webview starts up
            bgcolor = editor_info('colors')['background']
            bgcolor.setFill()
            NSRectFillUsingOperation(rect, NSCompositeCopy)
        super(EditorView, self).drawRect_(rect)


    def _jostle(self):
        awoke = self.webview.stringByEvaluatingJavaScriptFromString_('window.editor && window.editor.ready')
        if awoke:
            for op in self._queue:
                self.webview.stringByEvaluatingJavaScriptFromString_(op)
            self._wakeup.invalidate()
            self._wakeup = None
            self._queue = None
            self.webview.setHidden_(False)

    def _cleanup(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)
        self._doers = self._undo_mgr = self.jumpPanel = self.jumpLine = None

    # def webView_didFinishLoadForFrame_(self, sender, frame):
    def webView_didClearWindowObject_forFrame_(self, sender, win, frame):
        self.webview.windowScriptObject().setValue_forKey_(self,'app')

    def webView_contextMenuItemsForElement_defaultMenuItems_(self, sender, elt, menu):
        items = [
            NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(u"Cut", "cut:", ""),
            NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(u"Copy", "copy:", ""),
            NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(u"Paste", "paste:", ""),
            NSMenuItem.separatorItem(),
        ]

        # once a doc viewer exists, add a lookup-ref menu item pointing to it:
        # word = self.js('editor.selected')
        # _ns = ['curveto', 'TEXT', 'BezierPath', ...]
        # def ref_url(proc):
        #     if proc in _ns:
        #         return proc
        # if ref_url(word):
        #     doc = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(u"Documentation for ‘%s()’"%word, "copy:", "")
        #     sep = NSMenuItem.separatorItem()
        #     items.insert(0, sep)
        #     items.insert(0, doc)
        return items + [it for it in menu if it.title()=='Inspect Element']

    def resizeSubviewsWithOldSize_(self, oldSize):
        self.resizeWebview()

    def resizeWebview(self):
        self.webview.setFrame_(self.bounds())

    def insertDroppedFiles_(self, note):
        self.js('editor.insert', args(note.userInfo()))

    def isSelectorExcludedFromWebScript_(self, sel):
        return False

    def windowDidResignKey_(self, note):
        if note.object() is self.jumpPanel:
            self.jumpPanel.orderOut_(self)

    def validateMenuItem_(self, item):
        # we're the delegate for the Edit menu
        if item.title=='Undo':
            return self._undo_mgr.canUndo()
        elif item.title=='Redo':
            return self._undo_mgr.canRedo()
        return True

    def updateTrackingAreas(self):
        # keep a single tracking area (with our whole bounds) up to date
        for area in self.trackingAreas():
            self.removeTrackingArea_(area)

        opts = (NSTrackingMouseEnteredAndExited | NSTrackingActiveInActiveApp);
        area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(self.bounds(), opts, self, None)
        self.addTrackingArea_(area)

    def mouseExited_(self, e):
        # use the tracking area to restore the cursor when it leaves the bounds.
        # works around a bug where either ace.js or the WebView was leaving the
        # I-beam cursor active on-exit
        NSCursor.arrowCursor().set()

    # App-initiated actions

    def _get_source(self):
        return self.webview.stringByEvaluatingJavaScriptFromString_('editor.source();')
    def _set_source(self, src):
        self.js(u'editor.source', args(src))
    source = property(_get_source, _set_source)

    def fontChanged(self, note=None):
        info = editor_info()
        self.js('editor.font', args(info['family'], info['px']))

    def themeChanged(self, note=None):
        info = editor_info()
        clipview = self.webview.mainFrame().frameView().documentView().superview()
        clipview.setBackgroundColor_(info['colors']['background'])
        self.js('editor.theme', args(info['module']))

    def bindingsChanged(self, note=None):
        self.js('editor.bindings', args(get_default('bindings')))

    def focus(self):
        self.js('editor.focus')

    def blur(self):
        self.js('editor.blur')

    def clearErrors(self):
        self.js('editor.mark', args(None))

    def report(self, crashed, script):
        if not crashed:
            self.js('editor.mark', args(None))
        else:
            exc, traceback = crashed
            err_lines = [line-1 for fn, line, env, src in reversed(traceback) if fn==script]
            self.js('editor.mark', args("\n".join(exc), err_lines))

    def js(self, cmd, args=''):
        op = '%s(%s);'%(cmd,args)
        if self._wakeup:
            self._queue.append(op)
        else:
            return self.webview.stringByEvaluatingJavaScriptFromString_(op)

    # Menubar actions

    @IBAction
    def editorAction_(self, sender):
        # map the tags in the nib's menu items to ace.js commandnames
        cmds = [None, 'selectline', 'centerselection', 'splitIntoLines', 'addCursorAbove', 'addCursorBelow',
                      'selectMoreAfter', 'selectMoreBefore', 'blockindent', 'blockoutdent', 'movelinesup',
                      'movelinesdown', 'togglecomment', 'modifyNumberUp','modifyNumberDown']
        self.js('editor.exec', args(cmds[sender.tag()]))

    @IBAction
    def jumpToLine_(self, sender):
        # place the panel in the middle of the editor's rect and display it
        e_frame = self.frame()
        p_frame = self.jumpPanel.frame()
        w_frame = self.window().frame()
        e_frame.origin.x = w_frame.origin.x + (w_frame.size.width - e_frame.size.width)
        e_frame.origin.y = w_frame.origin.y + (w_frame.size.height - e_frame.size.height) - 22
        p_frame.origin.x = int(e_frame.origin.x + (e_frame.size.width-p_frame.size.width)/2.0)
        p_frame.origin.y = int(e_frame.origin.y + (e_frame.size.height-p_frame.size.height)/2.0)
        self.jumpLine.setStringValue_('')
        self.jumpPanel.setFrame_display_(p_frame, False)
        self.jumpPanel.makeKeyAndOrderFront_(self)

    @IBAction
    def performJump_(self, sender):
        # if triggered by the ok button, jump to the line. otherwise just hide the panel if sender.tag():
        if sender.tag():
            try:
                line_str = re.sub(r'[^\d\.]', '', self.jumpLine.stringValue())
                line = round(float(line_str))
                self.js('editor.jump', args(line))
            except ValueError:
                pass # ignore non-integer input
        self.jumpPanel.orderOut_(self)

    @IBAction
    def aceAutocomplete_(self, sender):
        cmd = ['startAutocomplete', 'expandSnippet'][sender.tag()]
        self.js('editor.exec', args(cmd))

    @IBAction
    def aceWrapLines_(self, sender):
        newstate = NSOnState if sender.state()==NSOffState else NSOffState
        sender.setState_(newstate)
        self.js('editor.wrap', args(newstate==NSOnState))

    @IBAction
    def aceInvisibles_(self, sender):
        newstate = NSOnState if sender.state()==NSOffState else NSOffState
        sender.setState_(newstate)
        self.js('editor.invisibles', args(newstate==NSOnState))

    @IBAction
    def performFindAction_(self, sender):
        actions = {1:'find', 2:'findnext', 3:'findprevious', 7:'setneedle'}
        self.js('editor.exec', args(actions[sender.tag()]))

    # JS-initiated actions

    @IBAction
    def undoAction_(self, sender):
        undoredo = ['editor.undo', 'editor.redo']
        self.js(undoredo[sender.tag()])

    def loadPrefs(self):
       NSApp().delegate().showPreferencesPanel_(self)

    def cancelRun(self):
        # catch command-period even when the editor is first responder
        mm=NSApp().mainMenu()
        menu = mm.itemWithTitle_("Python")
        menu.submenu().performActionForItemAtIndex_(3)

    def edits(self, count):
        # inform the undo manager of the changes
        um = self._undo_mgr
        c = int(count)
        while self._edits < c:
            um.prepareWithInvocationTarget_(self).syncUndoState_(self._edits)
            self._edits+=1
        while self._edits > c:
            self._edits-=1
            um.undo()

        # update the undo/redo menus items
        for item, can in zip(self._doers, (um.canUndo(), um.canRedo())):
            item.setEnabled_(can)

    def syncUndoState_(self, count):
        pass # this would be useful if only it got called for redo as well as undo...

    def setSearchPasteboard(self, query):
        if not query: return

        pb = NSPasteboard.pasteboardWithName_(NSFindPboard)
        pb.declareTypes_owner_([NSStringPboardType],None)
        pb.setString_forType_(query, NSStringPboardType)
        self.flash("Edit")

    def flash(self, menuname):
        # when a menu item's key command was entered in the editor, flash the menu
        # bar to give a hint of where the command lives
        mm=NSApp().mainMenu()
        menu = mm.itemWithTitle_(menuname)
        menu.submenu().performActionForItemAtIndex_(0)

class OutputTextView(NSTextView):
    # editor = IBOutlet()
    endl = False
    scroll_lock = True

    def awakeFromNib(self):
        self.ts = self.textStorage()
        self.colorize()
        self.setTextContainerInset_( (0,4) ) # a pinch of top-margin
        # self.textContainer().setWidthTracksTextView_(NO) # disable word-wrap
        # self.textContainer().setContainerSize_((10000000, 10000000))

        # use a FindBar rather than FindPanel
        self.setUsesFindBar_(True)
        self._finder = NSTextFinder.alloc().init()
        self._finder.setClient_(self)
        self._finder.setFindBarContainer_(self.enclosingScrollView())
        self._findTimer = None
        self.setUsesFindBar_(True)

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "themeChanged", "ThemeChanged", None)
        nc.addObserver_selector_name_object_(self, "fontChanged", "FontChanged", None)

    def _cleanup(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)

    def fontChanged(self, note=None):
        self.setFont_(editor_info('font'))
        self.colorize()

    def themeChanged(self, note=None):
        self.colorize()

    def canBecomeKeyView(self):
        return False

    def colorize(self):
        clr, font = editor_info('colors'), editor_info('font')
        self.setBackgroundColor_(clr['background'])
        self.setTypingAttributes_({"NSColor":clr['color'], "NSFont":font, "NSLigature":0})
        self.setSelectedTextAttributes_({"NSBackgroundColor":clr['selection']})
        scrollview = self.superview().superview()
        scrollview.setScrollerKnobStyle_(2 if editor_info('dark') else 1)

        # recolor previous contents
        attrs = self._attrs()
        self.ts.beginEditing()
        last = self.ts.length()
        cursor = 0
        while cursor < last:
            a, r = self.ts.attributesAtIndex_effectiveRange_(cursor, None)
            self.ts.setAttributes_range_(attrs[a['stream']],r)
            cursor = r.location+r.length
        self.ts.endEditing()


    def _attrs(self, stream=None):
        clr, font = editor_info('colors'), editor_info('font')
        basic_attrs = {"NSFont":font, "NSLigature":0}
        attrs = {
            'message':{"NSColor":clr['color']},
            'info':{"NSColor":clr['comment']},
            'err':{"NSColor":clr['error']}
        }
        for s,a in attrs.items():
            a.update(basic_attrs)
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
            del self._begin
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
        del self._begin

    @IBAction
    def performFindAction_(self, sender):
        # this is the renamed target of the Find... menu items (shared with EditorView)
        # just pass the event along to the real implementation
        self.performFindPanelAction_(sender)

    def performFindPanelAction_(self, sender):
        # frustrating bug:
        # when the find bar is dismissed with esc, the *other* textview becomes
        # first responder. the `solution' here is to monitor the find bar's field
        # editor and notice when it is detached from the view hierarchy. it then
        # re-sets itself as first responder
        super(OutputTextView, self).performFindPanelAction_(sender)
        if self._findTimer:
            self._findTimer.invalidate()
        self._findEditor = self.window().firstResponder().superview().superview()
        self._findTimer = set_timeout(self, 'stillFinding:', 0.05, repeat=True)

    def stillFinding_(self, note):
        active = self._findEditor.superview().superview() is not None
        if not active:
            self.window().makeFirstResponder_(self)
            self._findTimer.invalidate()
            self._findTimer = None

    def __del__(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)
        if self._findTimer:
            self._findTimer.invalidate()
