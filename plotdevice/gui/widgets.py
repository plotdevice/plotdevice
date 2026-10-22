# encoding: utf-8
import os, re
import time
from collections import OrderedDict
from ..lib.cocoa import *
from math import floor, ceil
import objc
from . import set_timeout

BURST = 0.25  # seconds between edits that make them a burst (and of quiet that ends one)

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
        msg = "Frame {:,}/{:,}".format(written, total) if written<total else "Finishing…"
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

    def showFPS_(self, fps):
        if self._state == 'idle':
            self.counter.setStringValue_("%.0f fps" % fps)
            self.counter.setHidden_(False)

    def hideFPS(self):
        if self._state == 'idle':
            self.counter.setHidden_(True)

    def mouseEntered_(self, e):
        if self._state == 'run':
            self.cancel.setHidden_(False)
            self.spinner.setHidden_(True)

    def mouseExited_(self, e):
        self.cancel.setHidden_(True)
        self.spinner.setHidden_(False)


from ..context import NUMBER, TEXT, BOOLEAN, BUTTON
SMALL_FONT = NSFont.systemFontOfSize_(NSFont.smallSystemFontSize())
MINI_FONT = NSFont.systemFontOfSize_(NSFont.systemFontSizeForControlSize_(NSMiniControlSize))

class DashboardSwitch(NSSwitch):
    def acceptsFirstMouse_(self, e):
        return True

class DashboardRow(NSView):

    def initWithVariable_forDelegate_(self, var, delegate):
        self.initWithFrame_(((0,-999), (200, 30)))
        self.setAutoresizingMask_(NSViewWidthSizable)

        label = NSTextField.alloc().init()
        if var.label is not None:
            label.setStringValue_(var.label)
        label.setAlignment_(NSRightTextAlignment)
        label.setEditable_(False)
        label.setBordered_(False)
        label.setDrawsBackground_(False)
        label.setFont_(SMALL_FONT)
        label.sizeToFit()
        self.addSubview_(label)

        if var.type is TEXT:
            control = NSTextField.alloc().init()
            control.setStringValue_(var.value)
            control.cell().setControlSize_(NSSmallControlSize)
            control.setFont_(SMALL_FONT)
            control.setTarget_(self)
            control.setAutoresizingMask_(NSViewWidthSizable)
            control.setDelegate_(self)
            self.addSubview_(control)

        elif var.type is BOOLEAN:
            control = DashboardSwitch.alloc().init()
            control.setState_(NSOnState if var.value else NSOffState)
            control.setControlSize_(NSSmallControlSize)
            control.sizeToFit()
            control.setFont_(SMALL_FONT)
            control.setTarget_(self)
            control.setAction_(objc.selector(self.booleanChanged_, signature=b"v@:@@"))
            self.addSubview_(control)

        elif var.type is NUMBER:
            control = NSSlider.alloc().init()
            control.setMaxValue_(var.max)
            control.setMinValue_(var.min)
            control.setFloatValue_(var.value)
            control.cell().setControlSize_(NSSmallControlSize)
            control.setContinuous_(True)
            control.setTarget_(self)
            control.setAutoresizingMask_(NSViewWidthSizable)
            control.setAction_(objc.selector(self.numberChanged_, signature=b"v@:@@"))
            self.addSubview_(control)

            num = NSTextField.alloc().init()
            num.setBordered_(False)
            num.setEditable_(False)
            num.setAutoresizingMask_(NSViewMinXMargin)
            num.setSelectable_(True)
            num.setDrawsBackground_(False)
            num.setFont_(SMALL_FONT)

            # measure all the possible values to decide on the text-field width
            num_w = self._num_w(var.min, var.max, var.step)
            num.setStringValue_(self._fmt(var.value))
            num.setFrameSize_((num_w, 18))
            self.addSubview_(num)
            self.step = var.step
            self.num = num

        elif var.type is BUTTON:
            control = NSButton.alloc().init()
            control.setTitle_(var.value)
            control.setBezelStyle_(1)
            control.setFont_(SMALL_FONT)
            control.cell().setControlSize_(NSSmallControlSize)
            control.setTarget_(self)
            control.sizeToFit()
            control.setBezelColor_(getattr(var.color, '_rgb', None))
            control.setAction_(objc.selector(self.buttonClicked_, signature=b"v@:@@"))
            self.addSubview_(control)

        self.name = var.name
        self.type = var.type
        self.label = label
        self.control = control
        self.button_w = control.frame().size.width if var.type is BUTTON else 0
        self.num_w = num_w if var.type is NUMBER else 0
        self.label_w = label.frame().size.width
        self.delegate = delegate
        return self

    @objc.python_method
    def _fmt(self, num):
        s = "{:,.3f}".format(num)
        s = re.sub(r'\.0+$', '', s)
        return re.sub(r'(\.[^0])+0*$', r'\1', s)

    @objc.python_method
    def _num_w(self, lo, hi, step):
        num_w = 0
        inc = step if step else (hi - lo) / 97
        num = NSTextField.alloc().init()
        num.setFont_(SMALL_FONT)
        for i in range(1+ceil((hi - lo) / inc)):
            n = min(hi, lo + i*inc)
            s = self._fmt(n)
            num.setStringValue_(s)
            num.sizeToFit()
            num_w = max(num_w, num.frame().size.width)
        return num_w

    @objc.python_method
    def roundOff(self):
        if self.step:
            rounded = self.step * floor((self.control.floatValue() + self.step/2) / self.step)
            self.control.cell().setFloatValue_(rounded)
        self.num.setStringValue_(self._fmt(self.control.floatValue()))

    @objc.python_method
    def updateConfig(self, var):
        label = self.label
        control = self.control
        label.setStringValue_(var.label or '')
        label.sizeToFit()
        self.label_w = label.frame().size.width

        if var.type is NUMBER:
            control.setMaxValue_(var.max)
            control.setMinValue_(var.min)
            self.step = var.step
            self.num_w = self._num_w(var.min, var.max, var.step)
            self.roundOff()

        elif var.type is BUTTON:
            control.setTitle_(var.value)
            self.button_w = control.frame().size.width
            control.setBezelColor_(getattr(var.color, '_rgb', None))

    @objc.python_method
    def updateLayout(self, indent, width, row_width, offset):
        self.setFrame_(((0,  offset), (row_width, 30)))
        self.label.setFrame_(((10, 0), (indent-15, 18)))
        if self.type is TEXT:
            self.control.setFrame_(((indent, 3),(width - indent, 18)))
        elif self.type is BOOLEAN:
            self.control.setFrameOrigin_((indent, 0))
        elif self.type is NUMBER:
            self.control.setFrame_(((indent, 1), (width - indent, 18)))
            self.num.setFrameOrigin_((width + 5, 0))
        elif self.type is BUTTON:
            self.control.setFrameOrigin_((indent-5, -5))

    def numberChanged_(self, sender):
        self.roundOff()
        if self.delegate:
            self.delegate.setVariable_to_(self.name, sender.floatValue())

    def controlTextDidChange_(self, note):
        if self.delegate:
            sender = note.object()
            self.delegate.setVariable_to_(self.name, sender.stringValue())

    def booleanChanged_(self, sender):
        if self.delegate:
            self.delegate.setVariable_to_(self.name, sender.state() == NSOnState)

    def buttonClicked_(self, sender):
        if self.delegate:
            self.delegate.callHandler_(self.name)

class DashboardController(NSObject):
    script = IBOutlet()
    panel = IBOutlet()

    def awakeFromNib(self):
        self.panel.contentView().setFlipped_(True)
        self.panel.contentView().setMaterial_(NSVisualEffectMaterialHUDWindow)
        self.rows = OrderedDict()
        self.positioned = False
        self.editing = False  # whether edits are arriving in a burst (as while dragging a slider)
        self._lastEdit, self._settle = 0, None

    def shutdown(self):
        if self._settle is not None:
            self._settle.invalidate()
        self.panel.close()
        for row in self.rows.values():
            row.delegate = None
            if row.type is TEXT:
                row.control.setDelegate_(None)

    def setVariable_to_(self, name, val):
        var = self.script.vm.params[name]
        var.value = val
        animating = self.script.animationTimer is not None
        exporting = self.script.vm.session is not None
        if not animating and not exporting:
            now = time.perf_counter()
            self.editing = self.editing or now - self._lastEdit < BURST
            self._lastEdit = now
            if self._settle is not None:
                self._settle.invalidate()
            self._settle = set_timeout(self, 'settle:', BURST)
            self.script.runScript()

    def settle_(self, timer):
        self._settle = None
        if self.editing:
            self.editing = False
            self.script.graphicsView.liveEnded()

    def callHandler_(self, name):
        var = self.script.vm.params[name]
        result = self.script.vm.call(var.name)
        self.script.echo(result.output)
        if result.ok:
            self.script.currentView.render(self.script.vm.canvas, onerror=self.script._renderCrashed)


    @objc.python_method
    def updateInterface(self):
        params = self.script.vm.params
        for name, widget in self.rows.items():
            if name not in params:
                widget.removeFromSuperview()
                self.script.vm.namespace.pop(name)

        new_rows = OrderedDict()
        for name, var in params.items():
            try:
                new_rows[name] = self.rows[name]
                new_rows[name].updateConfig(var)
            except KeyError:
                new_rows[name] = DashboardRow.alloc().initWithVariable_forDelegate_(var, self)
                self.panel.contentView().addSubview_(new_rows[name])
        self.rows = new_rows

        if not self.rows:
            self.panel.orderOut_(None)
        else:
            # Set the title of the parameter panel to the title of the window
            self.panel.setTitle_(self.script.window().title())

            # recalculate the layout
            (pOrigin, pSize) = self.panel.frame()
            label_w = max([v.label_w for v in self.rows.values()])
            button_w = max([v.button_w for v in self.rows.values()])
            num_w = max([v.num_w for v in self.rows.values()])
            ph = len(self.rows) * 30 + 30
            pw = label_w + 15 + max(button_w, 200) + num_w
            col = label_w + 15

            self.panel.setMinSize_( (pw, ph))
            self.panel.setMaxSize_( (pw * 5, ph))

            needs_resize = pSize.width < pw or pSize.height != ph
            pw = max(pw, pSize.width)

            if not self.positioned:
                win = self.script.window().frame()
                screen = self.script.window().screen().visibleFrame()
                if win.origin.x + win.size.width + pw < screen.size.width:
                    pOrigin = (win.origin.x + win.size.width, win.origin.y + win.size.height - ph - 38)
                elif win.origin.x - pw > 0:
                    pOrigin = (win.origin.x - pw, win.origin.y + win.size.height - ph - 38)
                else:
                    pOrigin = (win.origin.x + win.size.width - pw - 15, win.origin.y + 15)
                self.panel.setFrame_display_animate_( (pOrigin, (pw,ph)), True, True )
                self.positioned = True

            elif needs_resize:
                pOrigin.y -= ph-pSize.height
                self.panel.setFrame_display_animate_( (pOrigin, (pw,ph)), True, True )

            # reposition the elements of each row to fit the new panel size and row contents
            for idx, v in enumerate(self.rows.values()):
                v.updateLayout(col, pw - 10 - num_w, pw, idx*30)

            self.panel.orderFront_(None)



from ..context import RGB, CMYK
from ..gfx.colors import P3, SRGB, _PRESS_LABELS, _FORMAT_COLORS, _FORMAT_DEFAULTS, _installed_presses, _printer_profiles
from ..lib.io import MovieExportSession

SECTION_HEADERS = hasattr(NSMenuItem, 'sectionHeaderWithTitle_')

def fill_sections(menu, sections, action=None):
    menu.removeAllItems()
    for header, items in sections:
        if header and SECTION_HEADERS:
            menu.addItem_(NSMenuItem.sectionHeaderWithTitle_(header))
        elif menu.numberOfItems():
            menu.addItem_(NSMenuItem.separatorItem())
        for title, value in items:
            item = menu.addItemWithTitle_action_keyEquivalent_(title, None, '')
            if isinstance(value, list):
                item.setSubmenu_(NSMenu.alloc().initWithTitle_(title))
                fill_sections(item.submenu(), [(None, value)], action)
            else:
                item.setRepresentedObject_(value)
                item.setAction_(action)

def press_items():
    return [(label, press) for press, label in _PRESS_LABELS.items()] + _installed_presses()

class ProofColorsMenu(NSObject):

    def menuNeedsUpdate_(self, menu):
        win = NSApp().mainWindow()
        screen = win.screen() if win else NSScreen.mainScreen()
        printers, unnamed = {}, []
        for printer, desc, path in _printer_profiles():
            if printer:
                printers.setdefault(printer, []).append((desc, ('printer', path)))
            else:
                unnamed.append((desc, ('printer', path)))
        presses = [(title, ('press', press)) for title, press in press_items()]
        fill_sections(menu, [(None, [(screen.localizedName(), None), ('sRGB', ('rgb', SRGB))]),
                             ('Prepress', presses),
                             ('Printers', sorted(printers.items()) + unnamed)], 'proofColors:')

class ExportSheet(NSObject):
    # the script whose doExportAsImage and doExportAsMovie methods will be called
    script = IBOutlet()

    # Image export settings
    imageAccessory = IBOutlet()
    imageFormat = IBOutlet()
    imageZoom = IBOutlet()
    imagePageCount = IBOutlet()
    imagePagination = IBOutlet()
    imageColors = IBOutlet()

    # Movie export settings
    movieAccessory = IBOutlet()
    movieFormat = IBOutlet()
    movieFrames = IBOutlet()
    movieFps = IBOutlet()
    movieLoop = IBOutlet()
    movieBitrate = IBOutlet()
    movieZoom = IBOutlet()
    movieColors = IBOutlet()

    def awakeFromNib(self):
        self.formats = dict(image=(0, 'pdf', 0,0, 'png', 'jpg', 'heic', 'tiff', 'gif', 0,0, 'pdf', 'eps'), movie=('mov', 'mov', 'mov', 'gif'))
        self.codecs = ('hevc', 'h264', 'prores', None) # the movie formats' codecs
        self.movie = dict(format='mov', first=1, last=150, fps=30, bitrate=None, loop=0, codec='hevc', zoom=1.0, colors=P3)
        self.image = dict(format='pdf', zoom=1.0, first=1, last=1, colors=P3, single=True)
        self.last = None
        self.canvasSize = None # (w, h) the script last ran with, to preview the automatic bitrate
        self.movieFps.setDelegate_(self)

    @objc.python_method
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
            self.fillColors(self.imageColors, self.image['colors'])

        elif kind=='movie':
            format = self.movie['format']
            accessory = self.movieAccessory
            format_idx = self.codecs.index(self.movie['codec'])
            should_loop = self.movie['format']=='gif' and self.movie['loop']==-1
            self.movieFrames.setIntValue_(self.movie['last'])
            self.movieFps.setIntValue_(self.movie['fps'])
            self.movieFormat.selectItemAtIndex_(format_idx)
            self.movieLoop.setState_(NSOnState if should_loop else NSOffState)
            self.movieLoop.setEnabled_(format=='gif')
            self.movieBitrate.setEnabled_(self.movie['codec'] in ('hevc', 'h264'))
            self.movieBitrate.selectItemWithTag_(self.movie['bitrate'] or 0)
            self.fillColors(self.movieColors, self.movie['colors'])
            self.canvasSize = None
            if self.script.vm.ran:
                w, h = self.script.vm.canvas.pagesize
                self.canvasSize = (int(w), int(h))
            self.updateBitrate()

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
            fileName, ext = os.path.splitext(fileName)

        # create the sheet
        exportPanel = NSSavePanel.savePanel()
        exportPanel.setNameFieldLabel_("Export To:")
        exportPanel.setPrompt_("Export")
        exportPanel.setCanSelectHiddenExtension_(True)
        exportPanel.setShowsTagField_(False)
        exportPanel.setAllowedFileTypes_([format])
        exportPanel.setAccessoryView_(accessory)
        self.exportPanel = exportPanel

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

    exportPanelDidEnd_returnCode_contextInfo_ = objc.selector(
        exportPanelDidEnd_returnCode_contextInfo_, signature=b'v@:@q^v')

    def movieState(self, key=None):
        fmts = self.formats['movie']
        fmt_idx = self.movieFormat.indexOfSelectedItem()
        state = dict(format = fmts[fmt_idx],
                     first=1,
                     last=self.movieFrames.intValue(),
                     fps=self.movieFps.floatValue(),
                     loop=-1 if self.movieLoop.state()==NSOnState else 0,
                     bitrate=self.movieBitrate.selectedItem().tag() or None,
                     codec=self.codecs[fmt_idx],
                     colors=self.movieColors.selectedItem().representedObject(),
                     zoom=self.movie['zoom'] )
        if key:
            return state[key]
        return state

    def imageState(self, key=None):
        fmts = self.formats['image']
        fmt_idx = self.imageFormat.indexOfSelectedItem()
        state = dict(format=fmts[fmt_idx],
                     zoom=self.image['zoom'],
                     first=1,
                     colors=self.imageColors.selectedItem().representedObject(),
                     single=fmt_idx==1,
                     last=self.imagePageCount.intValue())
        if key:
            return state[key]
        return state

    def updatePagination(self):
        label = 'Pages:' if self.imageState('single') else 'Files:'
        self.imagePagination.setStringValue_(label)

    def updateBitrate(self):
        automatic = 'Automatic'
        fps = self.movieFps.floatValue()
        if self.canvasSize is not None and fps > 0:
            w, h = [int(dim * self.movie['zoom']) for dim in self.canvasSize]
            automatic += ' (%i Mbit/s)' % MovieExportSession.auto_bitrate(w, h, fps)
        self.movieBitrate.menu().itemWithTag_(0).setTitle_(automatic)
        self.movieBitrate.synchronizeTitleAndSelectedItem()

    def controlTextDidChange_(self, note):
        if note.object() == self.movieFps:
            self.updateBitrate()

    @objc.python_method
    def proofed(self, proof):
        kind, value = proof or (None, None)
        self.image['colors'] = value if kind in ('press', 'rgb') else P3
        self.movie['colors'] = value if kind == 'rgb' else P3

    @objc.python_method
    def fillColors(self, popup, colors):
        installed = _installed_presses()
        bundled = [(label, press) for press, label in _PRESS_LABELS.items()]
        cmyk = [('Generic CMYK', CMYK)] + bundled + ([None] + installed if installed else [])
        popup.removeAllItems()
        for header, items in [('RGB', [('Display P3', P3), ('sRGB', SRGB)]), ('CMYK', cmyk)]:
            if SECTION_HEADERS:
                popup.menu().addItem_(NSMenuItem.sectionHeaderWithTitle_(header))
            elif popup.numberOfItems():
                popup.menu().addItem_(NSMenuItem.separatorItem())
            for entry in items:
                if entry is None:
                    popup.menu().addItem_(NSMenuItem.separatorItem())
                    continue
                title, value = entry
                popup.addItemWithTitle_(title)
                popup.lastItem().setRepresentedObject_(value)
        popup.selectItemAtIndex_(popup.indexOfItemWithRepresentedObject_(colors))
        self.updateColors(popup)

    @objc.python_method
    def updateColors(self, popup):
        if popup is self.imageColors:
            format = self.formats['image'][self.imageFormat.indexOfSelectedItem()]
        else:
            format = self.formats['movie'][self.movieFormat.indexOfSelectedItem()]
        allowed = _FORMAT_COLORS[format]
        holds_cmyk = CMYK in allowed
        for idx, item in enumerate(popup.itemArray()):
            colors = item.representedObject()
            if colors is None:
                item.setHidden_(idx > 0 and not holds_cmyk)
            elif colors in (P3, SRGB):
                item.setEnabled_(colors in allowed or 'rgb' in allowed)
            else:
                item.setHidden_(not holds_cmyk)
        chosen = popup.selectedItem()
        if chosen is None or chosen.isHidden() or not chosen.isEnabled():
            default = _FORMAT_DEFAULTS.get(format, P3)
            popup.selectItemAtIndex_(popup.indexOfItemWithRepresentedObject_(default))

    @IBAction
    def imageFormatChanged_(self, sender):
        format = self.formats['image'][sender.indexOfSelectedItem()]
        self.exportPanel.setAllowedFileTypes_([format])
        self.updateColors(self.imageColors)
        self.updatePagination()

    @IBAction
    def imageZoomStepped_(self, sender):
        step = sender.intValue()
        sender.setIntValue_(0)

        self.imageZoomChanged_(None) # reflect any editing in text field
        pct = self.image['zoom'] * 100

        if step > 0:
            pct = 100 * ceil((pct + 1) / 100)
        elif step < 0:
            pct = 100 * floor((pct - 1) / 100)

        if 0 < pct < 10000:
            self.image['zoom'] = pct / 100
            self.imageZoom.setStringValue_("%i%%" % pct)

    @IBAction
    def imageZoomChanged_(self, sender):
        pct = self.imageZoom.intValue()
        if pct > 0:
            self.image['zoom'] = pct / 100
        else:
            pct = self.image['zoom'] * 100
        self.imageZoom.setStringValue_("%i%%" % pct)

    @IBAction
    def movieZoomStepped_(self, sender):
        step = sender.intValue()
        sender.setIntValue_(0)

        self.movieZoomChanged_(None) # reflect any editing in text field
        pct = self.movie['zoom'] * 100

        if step > 0:
            pct = 100 * ceil((pct + 1) / 100)
        elif step < 0:
            pct = 100 * floor((pct - 1) / 100)

        if 0 < pct < 10000:
            self.movie['zoom'] = pct / 100
            self.movieZoom.setStringValue_("%i%%" % pct)
        self.updateBitrate()

    @IBAction
    def movieZoomChanged_(self, sender):
        pct = self.movieZoom.intValue()
        if pct > 0:
            self.movie['zoom'] = pct / 100
        else:
            pct = self.movie['zoom'] * 100
        self.movieZoom.setStringValue_("%i%%" % pct)
        self.updateBitrate()

    @IBAction
    def movieFormatChanged_(self, sender):
        format = self.formats['movie'][sender.indexOfSelectedItem()]
        self.exportPanel.setAllowedFileTypes_([format])
        is_gif = format=='gif'
        self.movieLoop.setState_(NSOnState if is_gif else NSOffState)
        self.movieLoop.setEnabled_(is_gif)
        self.movieBitrate.setEnabled_(self.codecs[sender.indexOfSelectedItem()] in ('hevc', 'h264'))
        self.updateColors(self.movieColors)
