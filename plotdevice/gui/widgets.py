# encoding: utf-8
import os
from ..lib.cocoa import *
import objc

## classes instantiated by PlotDeviceDocument.xib & PlotDeviceScript.xib

class StatusView(NSView):
    spinner = IBOutlet()
    counter = IBOutlet()
    cancel = IBOutlet()

    def awakeFromNib(self):
        self.cancel.setHidden_(True)
        self._state = 'idle'
        self._finishing = False

        opts = (NSTrackingMouseEnteredAndExited | NSTrackingActiveInActiveApp);
        trackingArea = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(self.bounds(), opts, self, None)
        self.addTrackingArea_(trackingArea)

        self.cancel.cell().setHighlightsBy_(NSContentsCellMask)
        self.cancel.cell().setShowsStateBy_(NSContentsCellMask)
        self.counter.setHidden_(True)

    def beginRun(self):
        self._state = 'run'
        self.spinner.setIndeterminate_(True)
        self.spinner.startAnimation_(None)

    def endRun(self):
        self._state = 'idle'
        self.spinner.stopAnimation_(None)
        self.cancel.setHidden_(True)

    def beginExport(self):
        self._state = 'run'

        self.spinner.stopAnimation_(None)
        self.cancel.setHidden_(True)
        self.spinner.setIndeterminate_(False)
        self.spinner.setDoubleValue_(0)
        self.spinner.startAnimation_(None)

        self.counter.setHidden_(False)
        self.counter.setStringValue_("")

    def updateExport_total_(self, written, total):
        self.spinner.setMaxValue_(total)
        self.spinner.setDoubleValue_(written)
        msg = "Frame %i/%i"%(written, total) if written<total else u"Finishing…"
        self.counter.setStringValue_(msg)

    def finishExport(self):
        if self._state == 'run':
            self.cancel.setHidden_(True)
            self.spinner.setHidden_(False)
            self.spinner.stopAnimation_(None)
            self.spinner.setIndeterminate_(True)
            self.spinner.startAnimation_(None)
            self._state = 'finish'
            self.counter.setStringValue_("Finishing export")
            return True

    def endExport(self):
        self.spinner.setIndeterminate_(True)
        self.spinner.stopAnimation_(None)
        self.cancel.setHidden_(True)
        self.counter.setHidden_(True)
        self._state = 'idle'

    def mouseEntered_(self, e):
        if self._state == 'run':
            self.cancel.setHidden_(False)
            self.spinner.setHidden_(True)

    def mouseExited_(self, e):
        self.cancel.setHidden_(True)
        self.spinner.setHidden_(False)


from plotdevice.context import NUMBER, TEXT, BOOLEAN, BUTTON
SMALL_FONT = NSFont.systemFontOfSize_(NSFont.smallSystemFontSize())
MINI_FONT = NSFont.systemFontOfSize_(NSFont.systemFontSizeForControlSize_(NSMiniControlSize))
class DashboardController(NSObject):
    script = IBOutlet()
    panel = IBOutlet()

    def clearInterface(self):
        for s in list(self.panel.contentView().subviews()):
            s.removeFromSuperview()

    def numberChanged_(self, sender):
        var = self.script.vm.vars[sender.tag()]
        var.value = sender.floatValue()
        self.script.runScript()

    def textChanged_(self, sender):
        var = self.script.vm.vars[sender.tag()]
        var.value = sender.stringValue()
        self.script.runScript()

    def booleanChanged_(self, sender):
        var = self.script.vm.vars[sender.tag()]
        if sender.state() == NSOnState:
            var.value = True
        else:
            var.value = False
        self.script.runScript()

    def buttonClicked_(self, sender):
        print "out of service"
        # var = self.script.vm.vars[sender.tag()]
        # self.script.vm.call(var.name)
        # self.script.runScript()

    def buildInterface(self, vars):
        self.vars = vars
        self.clearInterface()
        if len(self.vars) > 0:
            self.panel.orderFront_(None)
        else:
            self.panel.orderOut_(None)
            return

        # Set the title of the parameter panel to the title of the window
        self.panel.setTitle_(self.script.window().title())

        (px,py),(pw,ph) = self.panel.frame()
        # Height of the window. Each element has a height of 21.
        # The extra "fluff" is 38 pixels.
        ph = len(self.vars) * 21 + 54
        # Start of first element
        # First element is the height minus the fluff.
        y = ph - 49
        cnt = 0
        for v in self.vars:
            if v.type == NUMBER:
                self._addLabel(v, y, cnt)
                self._addSlider(v, y, cnt)
            elif v.type == TEXT:
                self._addLabel(v, y, cnt)
                self._addTextField(v, y, cnt)
            elif v.type == BOOLEAN:
                self._addSwitch(v, y, cnt)
            elif v.type == BUTTON:
                self._addButton(v, y, cnt)
            y -= 21
            cnt += 1
        self.panel.setFrame_display_animate_( ((px,py),(pw,ph)), True, True )

    def _addLabel(self, v, y, cnt):
        control = NSTextField.alloc().init()
        control.setFrame_(((0,y),(100,13)))
        control.setStringValue_(v.name + ":")
        control.setAlignment_(NSRightTextAlignment)
        control.setEditable_(False)
        control.setBordered_(False)
        control.setDrawsBackground_(False)
        control.setFont_(SMALL_FONT)
        control.setTextColor_(NSColor.whiteColor())
        self.panel.contentView().addSubview_(control)

    def _addSlider(self, v, y, cnt):
        control = NSSlider.alloc().init()
        control.setMaxValue_(v.max)
        control.setMinValue_(v.min)
        control.setFloatValue_(v.value)
        control.setFrame_(((108,y-1),(172,13)))
        control.cell().setControlSize_(NSMiniControlSize)
        control.cell().setControlTint_(NSGraphiteControlTint)
        control.setContinuous_(True)
        control.setTarget_(self)
        control.setTag_(cnt)
        control.setAction_(objc.selector(self.numberChanged_, signature="v@:@@"))
        self.panel.contentView().addSubview_(control)

    def _addTextField(self, v, y, cnt):
        control = NSTextField.alloc().init()
        control.setStringValue_(v.value)
        control.setFrame_(((108,y-2),(172,15)))
        control.cell().setControlSize_(NSMiniControlSize)
        control.cell().setControlTint_(NSGraphiteControlTint)
        control.setFont_(MINI_FONT)
        control.setTarget_(self)
        control.setTag_(cnt)
        control.setAction_(objc.selector(self.textChanged_, signature="v@:@@"))
        self.panel.contentView().addSubview_(control)

    def _addSwitch(self, v, y, cnt):
        control = NSButton.alloc().init()
        control.setButtonType_(NSSwitchButton)
        if v.value:
            control.setState_(NSOnState)
        else:
            control.setState_(NSOffState)
        control.setFrame_(((108,y-2),(172,16)))
        control.setTitle_(v.name)
        control.setFont_(SMALL_FONT)
        control.cell().setControlSize_(NSSmallControlSize)
        control.cell().setControlTint_(NSGraphiteControlTint)
        control.setTarget_(self)
        control.setTag_(cnt)
        switchTitle = NSMutableAttributedString.alloc().initWithAttributedString_(control.attributedTitle())
        switchTitle.addAttribute_value_range_(NSForegroundColorAttributeName,
                                              NSColor.whiteColor(),
                                              (0, switchTitle.length()))
        control.setAttributedTitle_(switchTitle)
        control.setAction_(objc.selector(self.booleanChanged_, signature="v@:@@"))
        self.panel.contentView().addSubview_(control)

    def _addButton(self, v, y, cnt):
        control = NSButton.alloc().init()
        control.setFrame_(((108, y-2),(172,16)))
        control.setTitle_(v.name)
        control.setBezelStyle_(1)
        control.setFont_(SMALL_FONT)
        control.cell().setControlSize_(NSMiniControlSize)
        control.cell().setControlTint_(NSGraphiteControlTint)
        control.setTarget_(self)
        control.setTag_(cnt)
        control.setAction_(objc.selector(self.buttonClicked_, signature="v@:@@"))
        self.panel.contentView().addSubview_(control)

from ..context import RGB, CMYK
class ExportSheet(NSObject):
    # the script whose doExportAsImage and doExportAsMovie methods will be called
    script = IBOutlet()

    # Image export settings
    imageAccessory = IBOutlet()
    imageFormat = IBOutlet()
    imagePageCount = IBOutlet()
    imagePagination = IBOutlet()
    imageCMYK = IBOutlet()

    # Movie export settings
    movieAccessory = IBOutlet()
    movieFormat = IBOutlet()
    movieFrames = IBOutlet()
    movieFps = IBOutlet()
    movieLoop = IBOutlet()
    movieBitrate = IBOutlet()

    def awakeFromNib(self):
        self.formats = dict(image=(0, 'pdf', 0,0, 'png', 'jpg', 'tiff', 'gif', 0,0, 'pdf', 'eps'), movie=('mov', 'gif'))
        self.movie = dict(format='mov', first=1, last=150, fps=30, bitrate=1, loop=0)
        self.image = dict(format='pdf', first=1, last=1, cmyk=False, single=True)
        self.last = None


    def beginExport(self, kind):
        # configure the accessory controls
        if kind=='image':
            format = self.image['format']
            accessory = self.imageAccessory

            if self.image['single']:
                self.imageFormat.selectItemAtIndex_(1)
            else:
                format_idx = 2 + self.formats['image'][2:].index(self.image['format'])
                self.imageFormat.selectItemAtIndex_(format_idx)
            self.imagePageCount.setIntValue_(self.image['last'])

            self.updatePagination()
            self.updateColorMode()

        elif kind=='movie':
            format = self.movie['format']
            accessory = self.movieAccessory
            format_idx = self.formats['movie'].index(self.movie['format'])
            should_loop = self.movie['format']=='gif' and self.movie['loop']==-1
            self.movieFrames.setIntValue_(self.movie['last'])
            self.movieFps.setIntValue_(self.movie['fps'])
            self.movieFormat.selectItemAtIndex_(format_idx)
            self.movieLoop.setState_(NSOnState if should_loop else NSOffState)
            self.movieLoop.setEnabled_(format=='gif')
            self.movieBitrate.setEnabled_(format!='gif')
            self.movieBitrate.selectItemWithTag_(self.movie['bitrate'])

        # set the default filename and save dir
        # path = self.script.fileName()
        path = self.script.path
        if path:
            dirName, fileName = os.path.split(path)
            fileName, ext = os.path.splitext(fileName)
            fileName += "." + format
        else:
            dirName, fileName = None, "Untitled.%s"%format

        # If a file was already exported, use that folder/filename as the default.
        if self.last is not None:
            dirName, fileName = self.last

        # create the sheet
        exportPanel = NSSavePanel.savePanel()
        exportPanel.setNameFieldLabel_("Export To:")
        exportPanel.setPrompt_("Export")
        exportPanel.setCanSelectHiddenExtension_(True)
        exportPanel.setShowsTagField_(False)
        exportPanel.setAllowedFileTypes_(filter(None, self.formats[kind]))
        exportPanel.setRequiredFileType_(format)
        exportPanel.setAccessoryView_(accessory)

        # present the dialog
        callback = "exportPanelDidEnd:returnCode:contextInfo:"
        context = 0 if kind=='image' else 1
        exportPanel.beginSheetForDirectory_file_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            dirName, fileName, NSApp().mainWindow(), self, callback, context
        )

    def exportPanelDidEnd_returnCode_contextInfo_(self, panel, returnCode, context):
        fname = panel.filename()
        panel.close()
        panel.setAccessoryView_(None)

        # if the user clicked Save:
        if returnCode:
            if context:
                kind, opts = 'movie', self.movieState()
            else:
                kind, opts = 'image', self.imageState()
            setattr(self, kind, dict(opts))  # save the options for next time
            self.last = os.path.split(fname) # save the path we exported to
            self.script.exportInit(kind, fname, opts)

    def movieState(self, key=None):
        fmts = self.formats['movie']
        fmt_idx = self.movieFormat.indexOfSelectedItem()
        state = dict(format = fmts[fmt_idx],
                     # format=panel.requiredFileType(),
                     first=1,
                     last=self.movieFrames.intValue(),
                     fps=self.movieFps.floatValue(),
                     loop=-1 if self.movieLoop.state()==NSOnState else 0,
                     bitrate=self.movieBitrate.selectedItem().tag() )
        if key:
            return state[key]
        return state

    def imageState(self, key=None):
        fmts = self.formats['image']
        fmt_idx = self.imageFormat.indexOfSelectedItem()
        state = dict(format=fmts[fmt_idx],
                     first=1,
                     cmyk=self.imageCMYK.state()==NSOnState,
                     single=fmt_idx==1,
                     last=self.imagePageCount.intValue())
        if key:
            return state[key]
        return state

    def updatePagination(self):
        label = 'Pages:' if self.imageState('single') else 'Files:'
        self.imagePagination.setStringValue_(label)

    def updateColorMode(self):
        format = self.imageState('format')
        can_cmyk = format in ('pdf','eps','tiff')
        self.imageCMYK.setEnabled_(can_cmyk)
        if not can_cmyk:
            self.imageCMYK.setState_(NSOffState)

    @IBAction
    def imageFormatChanged_(self, sender):
        panel = sender.window()
        format = self.formats['image'][sender.indexOfSelectedItem()]
        panel.setRequiredFileType_(format)
        self.updateColorMode()
        self.updatePagination()

    @IBAction
    def movieFormatChanged_(self, sender):
        panel = sender.window()
        format = self.formats['movie'][sender.indexOfSelectedItem()]
        panel.setRequiredFileType_(format)
        is_gif = format=='gif'
        self.movieLoop.setState_(NSOnState if is_gif else NSOffState)
        self.movieLoop.setEnabled_(is_gif)
        self.movieBitrate.setEnabled_(not is_gif)

