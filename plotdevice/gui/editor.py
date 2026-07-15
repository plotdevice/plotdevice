# encoding: utf-8
import os
import re
import json
import objc
from objc import super
from time import time
from ..lib.cocoa import *
from plotdevice.gui.preferences import get_default, editor_info, dev_extras
from plotdevice.gui import bundle_path, set_timeout

__all__ = ['EditorView', 'OutputTextView']

def args(*jsargs):
    return ', '.join([json.dumps(v, ensure_ascii=False) for v in jsargs])

def menu_index_of(menu, identifier):
    # NSMenu has no indexOfItemWithIdentifier_ in this AppKit/PyObjC version; search manually
    for i, item in enumerate(menu.itemArray()):
        if item.identifier() == identifier:
            return i
    return -1

class DraggyWebView(WKWebView):
    def draggingEntered_(self, sender):
        pb = sender.draggingPasteboard()
        options = { NSPasteboardURLReadingFileURLsOnlyKey:True,
                    NSPasteboardURLReadingContentsConformToTypesKey:NSImage.imageTypes() }
        urls = pb.readObjectsForClasses_options_([NSURL], options)
        strs = pb.readObjectsForClasses_options_([NSString], {})
        rewrite = "\n".join(['"%s"'%u.path() for u in urls] + strs) + "\n"
        pb.declareTypes_owner_([NSStringPboardType], self)
        pb.setString_forType_(rewrite, NSStringPboardType)
        # don't consult super: WKWebView's drag negotiation round-trips to the web
        # process and can veto the rewritten pasteboard
        return NSDragOperationCopy

    def draggingUpdated_(self, sender):
        return NSDragOperationCopy

    def prepareForDragOperation_(self, sender):
        return True

    def performDragOperation_(self, sender):
        pb = sender.draggingPasteboard()
        txt = pb.readObjectsForClasses_options_([NSString], None)
        if txt:
            nc = NSNotificationCenter.defaultCenter()
            nc.postNotificationName_object_userInfo_('DropOperation', self, txt[0])
            sender.setAnimatesToDestination_(True)
            return True
        return False

    def willOpenMenu_withEvent_(self, menu, event):
        # omit everything from context menu except Cut/Copy/Paste (+ Inspect Element)
        keep = ('WKMenuItemIdentifierCut', 'WKMenuItemIdentifierCopy',
                'WKMenuItemIdentifierPaste', 'WKMenuItemIdentifierInspectElement')
        for item in list(menu.itemArray()):
            if item.identifier() not in keep:
                menu.removeItem_(item)

        # read _doc_target to get the tokens currently targeted by the mouse and caret
        # then choose which one to offer a View Docs menu item for based on the event type
        targets = getattr(self.owner, '_doc_target', None) or {}
        target = targets.get('caret' if event.type() == NSEventTypeKeyDown else 'mouse')
        if target:
            idx = menu_index_of(menu, 'WKMenuItemIdentifierInspectElement')
            idx = idx if idx >= 0 else menu.numberOfItems()
            if menu.numberOfItems() > 0:
                menu.insertItem_atIndex_(NSMenuItem.separatorItem(), idx)
                idx += 1
            prefix = u"View Documentation: "
            suffix = "()" if target['url'].endswith('()') else ""
            title = prefix + target['word'] + suffix
            base_font = NSFont.menuFontOfSize_(0)
            mono_font = NSFont.monospacedSystemFontOfSize_weight_(base_font.pointSize(), -0.8)
            attr_title = NSMutableAttributedString.alloc().initWithString_attributes_(title, {"NSFont":base_font})
            attr_title.addAttribute_value_range_("NSFont", mono_font, (len(prefix), len(target['word'] + suffix)))
            doc = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "viewDocumentation:", "")
            doc.setAttributedTitle_(attr_title)
            doc.setTarget_(self)
            doc.setRepresentedObject_(target['url'])
            menu.insertItem_atIndex_(doc, idx)

        inspect = menu_index_of(menu, 'WKMenuItemIdentifierInspectElement')
        if inspect >= 0:
            menu.insertItem_atIndex_(NSMenuItem.separatorItem(), inspect)

    def viewDocumentation_(self, sender):
        self.owner.openDoc(sender.representedObject())


class EditorView(NSView):
    document = IBOutlet()
    jumpPanel = IBOutlet()
    jumpLine = IBOutlet()

    # WebKit mgmt

    def awakeFromNib(self):
        config = WKWebViewConfiguration.alloc().init()
        dev = dev_extras() # whether to enable Inspect Element menu
        config.preferences().setValue_forKey_(dev, 'developerExtrasEnabled')
        ucc = config.userContentController()
        ucc.addScriptMessageHandler_name_(self, 'app')
        shim = WKUserScript.alloc().initWithSource_injectionTime_forMainFrameOnly_(
          # forward any app.<fn>() call as a message to the 'app' script-message handler
          """window.app = new Proxy({}, {
              get: (_, fn) => (...args) => window.webkit.messageHandlers.app.postMessage({fn:String(fn), args:args})
          });""", WKUserScriptInjectionTimeAtDocumentStart, True)
        ucc.addUserScript_(shim)

        self.webview = DraggyWebView.alloc().initWithFrame_configuration_(self.bounds(), config)
        self.webview.owner = self
        if dev and self.webview.respondsToSelector_('setInspectable:'):
            self.webview.setInspectable_(True)
        self.webview.setValue_forKey_(False, 'drawsBackground')
        self.webview.setNavigationDelegate_(self)
        self.addSubview_(self.webview)

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "themeChanged", "ThemeChanged", None)
        nc.addObserver_selector_name_object_(self, "fontChanged", "FontChanged", None)
        nc.addObserver_selector_name_object_(self, "bindingsChanged", "BindingsChanged", None)
        nc.addObserver_selector_name_object_(self, "insertDroppedFiles:", "DropOperation", self.webview)
        self._edits = 0
        self._last_source = ''
        self._refresh()

        mm=NSApp().mainMenu()
        self._doers = mm.itemWithTitle_('Edit').submenu().itemArray()[1:3]
        self._undo_mgr = None

    def drawRect_(self, rect):
        # the webview is transparent, so draw the theme background here
        bgcolor = editor_info('colors')['background']
        bgcolor.setFill()
        NSRectFillUsingOperation(rect, NSCompositeCopy)
        super(EditorView, self).drawRect_(rect)

    @objc.python_method
    def _refresh(self):
        # (re)load the editor page, queueing up prefs & source to be applied once it
        # signals readiness (see webView_didFinishNavigation_)
        self._loading = True
        self._queue = []
        self.webview.setHidden_(True)
        self.themeChanged()
        self.fontChanged()
        self.bindingsChanged()
        self._set_source(self._last_source)
        html = bundle_path(rsrc='ui/editor.html')
        ui_dir = NSURL.fileURLWithPath_isDirectory_(os.path.dirname(html), True)
        self.webview.loadFileURL_allowingReadAccessToURL_(NSURL.fileURLWithPath_(html), ui_dir)

    def _ready(self):
        # js editor has been loaded and is ready to receive queued prefs & source
        self._loading = False
        for op in self._queue:
            self.webview.evaluateJavaScript_completionHandler_(op, None)
        self._queue = []
        self.webview.setHidden_(False)
        self.setNeedsDisplay_(True)

    def _cleanup(self):
        # break the retain cycle through the WKUserContentController (it holds its
        # message handlers strongly)
        self.webview.configuration().userContentController().removeScriptMessageHandlerForName_('app')
        self.webview.setNavigationDelegate_(None)
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)
        self._doers = self._undo_mgr = self.jumpPanel = self.jumpLine = None

    def webView_didFinishNavigation_(self, sender, nav):
        # called after DOMContentLoaded
        self._ready()

    def webViewWebContentProcessDidTerminate_(self, sender):
        # try to restore if the webkit subprocess crashes
        self._refresh()

    def userContentController_didReceiveScriptMessage_(self, ucc, msg):
        body = msg.body()
        fn, fnargs = body['fn'], list(body.get('args', []))
        if fn in ('sync_edits', 'flash_menu', 'setSearchPasteboard', 'cancelRun', 'loadPrefs', 'openDoc', 'setDocTarget'):
            getattr(self, fn)(*fnargs)

    def resizeSubviewsWithOldSize_(self, oldSize):
        self.resizeWebview()

    def resizeWebview(self):
        self.webview.setFrame_(self.bounds())

    def insertDroppedFiles_(self, note):
        self.js('editor.insert', args(note.userInfo()))

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

    @objc.python_method
    def _get_source(self):
        # return the copy of the source relayed by the last sync_edits call from js
        return self._last_source
    @objc.python_method
    def _set_source(self, src):
        self._last_source = src
        self.js('editor.source', args(src))
    source = property(_get_source, _set_source)

    @objc.python_method
    def with_source(self, callback):
        """Read the editor buffer asynchronously, then invoke callback(src)"""
        if self._loading: # webview not ready: use the shadow copy
            return callback(self._last_source)
        def done(value, error):
            if value is not None:
                self._last_source = value
            callback(self._last_source)
        self.webview.evaluateJavaScript_completionHandler_('editor.source();', done)

    def fontChanged(self, note=None):
        info = editor_info()
        self.js('editor.font', args(info['family'], info['px']))

    def themeChanged(self, note=None):
        info = editor_info()
        self.js('editor.theme', args(info['module']))
        self.setNeedsDisplay_(True)

    def bindingsChanged(self, note=None):
        self.js('editor.bindings', args(get_default('bindings')))

    def focus(self):
        if self.window():
            self.window().makeFirstResponder_(self.webview)
        self.js('editor.focus')

    def blur(self):
        self.js('editor.blur')

    def clearErrors(self):
        self.js('editor.mark', args(None))

    @objc.python_method
    def report(self, crashed, script):
        if not crashed:
            self.js('editor.mark', args(None))
        else:
            exc, traceback = crashed
            err_lines = [line-1 for fn, line, env, src in reversed(traceback) if fn==script]
            self.js('editor.mark', args("\n".join(exc), err_lines))

    @objc.python_method
    def js(self, cmd, args=''):
        op = '%s(%s);'%(cmd,args)
        if self._loading:
            self._queue.append(op)
        else:
            self.webview.evaluateJavaScript_completionHandler_(op, None)

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
        actions = {1:'find', 2:'findnext', 3:'findprevious', 4:'replace', 7:'setneedle'}
        self.js('editor.exec', args(actions[sender.tag()]))

    # JS-initiated actions

    @IBAction
    def undoAction_(self, sender):
        undoredo = ['editor.undo', 'editor.redo']
        self.js(undoredo[sender.tag()])

    def loadPrefs(self):
       NSApp().delegate().showPreferencesPanel_(self)

    @objc.python_method
    def openDoc(self, url):
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

    @objc.python_method
    def setDocTarget(self, target):
        self._doc_target = target

    def cancelRun(self):
        # catch command-period even when the editor is first responder
        mm=NSApp().mainMenu()
        menu = mm.itemWithTitle_("Python")
        menu.submenu().performActionForItemAtIndex_(3)

    @objc.python_method
    def sync_edits(self, count, source=None):
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

        # cache the editor's contents for use by the synchronous .source property
        if isinstance(source, str):
            self._last_source = source

    def syncUndoState_(self, count):
        pass # this would be useful if only it got called for redo as well as undo...

    @objc.python_method
    def setSearchPasteboard(self, query):
        if not query: return

        pb = NSPasteboard.pasteboardWithName_(NSFindPboard)
        pb.declareTypes_owner_([NSStringPboardType],None)
        pb.setString_forType_(query, NSStringPboardType)
        self.flash_menu("Edit")

    @objc.python_method
    def flash_menu(self, menuname):
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

    @objc.python_method
    def append(self, txt, stream='message'):
        if not txt: return
        defer_endl = txt.endswith('\n')
        txt = ("\n" if self.endl else "") + (txt[:-1 if defer_endl else None])
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

    @objc.python_method
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
