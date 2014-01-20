import os
from PyObjCTools import AppHelper
from Foundation import *
from AppKit import *
import objc

from nodebox import graphics
from nodebox import __MAGIC as MAGICVAR

class ValueLadder:

    view = None
    visible = False
    value = None
    origValue = None
    dirty = False
    type = None
    negative = False
    unary = False
    add = False

    def __init__(self, textView, value, clickPos, screenPoint, viewPoint):
        self.textView = textView
        self.value = value
        self.origValue = value
        self.type = type(value)
        self.clickPos = clickPos
        self.origX, self.origY = screenPoint
        self.x, self.y = screenPoint
        self.viewPoint = viewPoint
        (x,y),(self.width,self.height) = self.textView.bounds()
        self.originalString = self.textView.string()
        self.backgroundColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.4,0.4,0.4,1.0)
        self.strokeColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.1,0.1,0.1, 1.0)
        self.textColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(1.,1.,1.,1.)
        paraStyle = NSMutableParagraphStyle.alloc().init()
        paraStyle.setAlignment_(NSCenterTextAlignment)
        font = NSFont.fontWithName_size_("Monaco", 10)
        self.textAttributes = {NSForegroundColorAttributeName:self.textColor,NSParagraphStyleAttributeName:paraStyle,NSFontAttributeName:font}

        # To speed things up, the code is compiled only once. 
        # The number is replaced with a magic variable, that is set in the 
        # namespace when executing the code.
        begin,end = self.clickPos
        self.patchedSource = self.originalString[:begin] + MAGICVAR + self.originalString[end:]


        #ast = parse(self.patchedSource + "\n\n")
        #self._checkSigns(ast)
        success, output = self.textView.document._boxedRun(self._parseAndCompile)
        if success:
            self.show()
        else:
            self.textView.document._flushOutput(output)

    def _parseAndCompile(self):
        from compiler import parse
        ast = parse(self.patchedSource.encode('ascii', 'replace') + "\n\n")
        self._checkSigns(ast)
        self.textView.document._compileScript(self.patchedSource)

    def _checkSigns(self, node):
        """Recursively check for special sign cases.
        
        The following cases are special:
        - Substraction. When you select the last part of a substraction 
          (e.g. the 5 of "10-5"), it might happen that you drag the number to
          a positive value. In that case, the result should be "10+5".
        - Unary substraction. Values like "-5" should have their sign removed 
          when you drag them to a positive value.
        - Addition. When you select the last part of an addition 
          (e.g. the 5 of "10+5"), and drag the number to a negative value, 
          the result should be "10-5".
          
        This algorithm checks for these cases. It tries to find the magic var, 
        and then checks the parent node to see if it is one of these cases, 
        then sets the appropriate state variables in the object.
        
        This algorithm is recursive. Because we have to differ between a 
        "direct hit" (meaning the current child was the right one) and a 
        "problem resolved" (meaning the algorithm found the node, did its
        work and now needs to bail out), we have three return codes:
        - -1: nothing was found in this node and its child nodes.
        -  1: direct hit. The child you just searched contains the magicvar.
              check the current node to see if it is one of the special cases.
        -  0: bail out. Somewhere, a child contained the magicvar, and we
              acted upon it. Now leave this algorithm as soon as possible.
        """

        from compiler.ast import Sub, UnarySub, Add

        # Check whether I am the correct node
        try:
            if node.name == MAGICVAR:
                return 1 # If i am, return the "direct hit" code.
        except AttributeError:
            pass

        # We keep an index to see what child we are checking. This 
        # is important for binary operations, were we are only interested
        # in the second part. ("a-10" has to change to "a+10", 
        # but "10-a" shouldn't change to "+10-a")
        index = 0
        # Recursively check my children
        for child in node.getChildNodes():
            retVal = self._checkSigns(child)
            # Direct hit. The child I just searched contains the magicvar.
            # Check whether this node is one of the special cases.
            if retVal == 1:
                # Unary substitution.
                if isinstance(node, UnarySub):
                    self.negative = True
                    self.unary = True
                # Binary substitution. Only the second child is of importance.
                elif isinstance(node, Sub) and index == 1:
                    self.negative = True
                # Binary addition. Only the second child is of importance.
                elif isinstance(node, Add) and index == 1:
                    self.add = True
                # Return the "bail out" code, whether we found some
                # special case or not. There can only be one magicvar in the
                # code, so once that is found we can stop looking.
                return 0
            # If the child returns a bail out code, we leave this routine
            # without checking the other children, passing along the
            # bail out code.
            elif retVal == 0:
                return 0 # Nothing more needs to be done.

            # Next child.
            index += 1

        # We searched all children, but couldn't find any magicvars. 
        return -1

    def show(self):
        self.visible = True
        self.textView.setNeedsDisplay_(True)
        NSCursor.hide()

    def hide(self):
        """Hide the ValueLadder and update the code.
        
        Updating the code means we have to replace the current value with
        the new value, and account for any special cases."""

        self.visible = False
        begin,end = self.clickPos

        # Potentionally change the sign on the number.
        # The following cases are valid:
        # - A subtraction where the value turned positive "random(5-8)" --> "random(5+8)"
        # - A unary subtraction where the value turned positive "random(-5)" --> "random(5)"
        #   Note that the sign dissapears here.
        # - An addition where the second part turns negative "random(5+8)" --> "random(5-8)"
        # Note that the code replaces the sign on the place where it was, leaving the code intact.

        # Case 1: Negative numbers where the new value is negative as well.
        # This means the numbers turn positive.
        if self.negative and self.value < 0:
            # Find the minus sign.
            i = begin - 1
            notFound = True
            while True:
                if self.originalString[i] == '-':
                    if self.unary: # Unary subtractions will have the sign removed.
                        # Re-create the string: the spaces between the value and the '-' + the value
                        value = self.originalString[i+1:begin] + str(abs(self.value))
                    else: # Binary subtractions get a '+'                        
                        value = '+' + self.originalString[i+1:begin] + str(abs(self.value))
                    range = (i,end-i)
                    break
                i -= 1
        # Case 2: Additions (only additions where we are the second part
        # interests us, this is checked already on startup)
        elif self.add and self.value < 0:
            # Find the plus sign.
            i = begin - 1
            notFound = True
            while True:
                if self.originalString[i] == '+':
                    # Re-create the string: 
                    # - a '+' (instead of the minus)
                    # - the spaces between the '-' and the constant
                    # - the constant itself                    
                    value = '-' + self.originalString[i+1:begin] + str(abs(self.value))
                    range = (i,end-i)
                    break
                i -= 1
        # Otherwise, it's a normal case. Note that here also, positive numbers
        # can turn negative, but no existing signs have to be changed.        
        else:
            value = str(self.value)
            range = (begin, end-begin)

        # The following textView methods make sure that an undo operation
        # is registered, so users can undo their drag.
        self.textView.shouldChangeTextInRange_replacementString_(range, value)
        self.textView.textStorage().replaceCharactersInRange_withString_(range, value)
        self.textView.didChangeText()
        self.textView.setNeedsDisplay_(True)
        self.textView.document.currentView.direct = False
        NSCursor.unhide()

    def draw(self):
        mx,my=self.viewPoint

        x = mx-20
        w = 80
        h = 20
        h2 = h*2

        context = NSGraphicsContext.currentContext()
        aa = context.shouldAntialias()
        context.setShouldAntialias_(False)
        r = ((mx-w/2,my+12),(w,h))
        NSBezierPath.setDefaultLineWidth_(0)
        self.backgroundColor.set()
        NSBezierPath.fillRect_(r)
        self.strokeColor.set()
        NSBezierPath.strokeRect_(r)

        # A standard value just displays the value that you have been dragging.
        if not self.negative:
            v = str(self.value)
        # When the value is negative, we don't display a double negative,
        # but a positive.
        elif self.value < 0:
            v = str(abs(self.value))
        # When the value is positive, we have to add a minus sign.
        else:
            v = "-" + str(self.value)

        NSString.drawInRect_withAttributes_(v, ((mx-w/2,my+14),(w,h2)), self.textAttributes)
        context.setShouldAntialias_(aa)

    def mouseDragged_(self, event):
        mod = event.modifierFlags()
        newX, newY = NSEvent.mouseLocation()
        deltaX = newX-self.x
        delta = deltaX
        if self.negative:
            delta = -delta
        if mod & NSAlternateKeyMask:
            delta /= 100.0
        elif mod & NSShiftKeyMask:
            delta *= 10.0
        self.value = self.type(self.value + delta)
        self.x, self.y = newX, newY
        self.dirty = True
        self.textView.setNeedsDisplay_(True)
        self.textView.document.magicvar = self.value
        self.textView.document.currentView.direct = True
        # self.textView.document.runScriptFast()
        self.textView.document.runScript()


# class defined in AskString.xib
class AskStringWindowController(NSWindowController):
    questionLabel = objc.IBOutlet()
    textField = objc.IBOutlet()

    def __new__(cls, question, resultCallback, default="", parentWindow=None):
        self = cls.alloc().initWithWindowNibName_("AskString")
        self.question = question
        self.resultCallback = resultCallback
        self.default = default
        self.parentWindow = parentWindow
        if self.parentWindow is None:
            self.window().setFrameUsingName_("AskStringPanel")
            self.setWindowFrameAutosaveName_("AskStringPanel")
            self.showWindow_(self)
        else:
            NSApp().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
                self.window(), self.parentWindow, None, None, 0)
        self.retain()
        return self

    def windowWillClose_(self, notification):
        self.autorelease()

    def awakeFromNib(self):
        self.questionLabel.setStringValue_(self.question)
        self.textField.setStringValue_(self.default)

    def done(self):
        if self.parentWindow is None:
            self.close()
        else:
            sheet = self.window()
            NSApp().endSheet_(sheet)
            sheet.orderOut_(self)

    def ok_(self, sender):
        value = self.textField.stringValue()
        self.done()
        self.resultCallback(value)

    def cancel_(self, sender):
        self.done()
        self.resultCallback(None)

def AskString(question, resultCallback, default="", parentWindow=None):
    AskStringWindowController(question, resultCallback, default, parentWindow)


# class defined in NodeBoxDocument.xib
SMALL_FONT = NSFont.systemFontOfSize_(NSFont.smallSystemFontSize())
MINI_FONT = NSFont.systemFontOfSize_(NSFont.systemFontSizeForControlSize_(NSMiniControlSize))
class DashboardController(NSObject):
    document = objc.IBOutlet()
    documentWindow = objc.IBOutlet()
    panel = objc.IBOutlet()

    def clearInterface(self):
        for s in list(self.panel.contentView().subviews()):
            s.removeFromSuperview()

    def numberChanged_(self, sender):
        var = self.document.vm.vars[sender.tag()]
        var.value = sender.floatValue()
        self.document.runScript()

    def textChanged_(self, sender):
        var = self.document.vm.vars[sender.tag()]
        var.value = sender.stringValue()
        self.document.runScript()

    def booleanChanged_(self, sender):
        var = self.document.vm.vars[sender.tag()]
        if sender.state() == NSOnState:
            var.value = True
        else:
            var.value = False
        self.document.runScript()
        
    def buttonClicked_(self, sender):
        var = self.document.vm.vars[sender.tag()]
        self.document.fastRun(var.name)

    def buildInterface(self, vars):
        self.vars = vars
        self.clearInterface()
        if len(self.vars) > 0:
            self.panel.orderFront_(None)
        else:
            self.panel.orderOut_(None)
            return

        # Set the title of the parameter panel to the title of the window
        self.panel.setTitle_(self.documentWindow.title())

        (px,py),(pw,ph) = self.panel.frame()
        # Height of the window. Each element has a height of 21.
        # The extra "fluff" is 38 pixels.
        ph = len(self.vars) * 21 + 54
        # Start of first element
        # First element is the height minus the fluff.
        y = ph - 49
        cnt = 0
        for v in self.vars:
            if v.type == graphics.NUMBER:
                self._addLabel(v, y, cnt)
                self._addSlider(v, y, cnt)
            elif v.type == graphics.TEXT:
                self._addLabel(v, y, cnt)
                self._addTextField(v, y, cnt)
            elif v.type == graphics.BOOLEAN:
                self._addSwitch(v, y, cnt)
            elif v.type == graphics.BUTTON:
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


class ExportSheet(NSObject):
    # the document whose doExportAsImage and doExportAsMovie methods will be called
    document = objc.IBOutlet()

    # Image export settings
    imageAccessory = objc.IBOutlet()
    imageFormat = objc.IBOutlet()
    imagePageCount = objc.IBOutlet()

    # Movie export settings
    movieAccessory = objc.IBOutlet()
    movieFormat = objc.IBOutlet()
    movieFrames = objc.IBOutlet()
    movieFps = objc.IBOutlet()
    movieLoop = objc.IBOutlet()
    movieBitrate = objc.IBOutlet()

    def awakeFromNib(self):
        self.formats = dict(image=('pdf', 'eps', 'png', 'tiff', 'jpg', 'gif'), movie=('mov', 'gif'))
        self.movie = dict(format='mov', first=1, last=150, fps=30, bitrate=1, loop=0)
        self.image = dict(format='pdf', first=1, last=1)
        self.cwd = None

    def beginExport(self, kind):
        # configure the accessory controls 
        if kind=='image':
            format = self.image['format']
            accessory = self.imageAccessory
            format_idx = self.formats['image'].index(self.image['format'])
            self.imageFormat.selectItemAtIndex_(format_idx)
            self.imagePageCount.setIntValue_(self.image['last'])

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
        path = self.document.fileName()
        if path:
            dirName, fileName = os.path.split(path)
            fileName, ext = os.path.splitext(fileName)
            fileName += "." + format
        else:
            dirName, fileName = None, "Untitled.%s"%format

        # If a file was already exported, use that folder as the default.
        if self.cwd is not None:
            dirName = self.cwd

        # create the sheet
        exportPanel = NSSavePanel.savePanel()
        exportPanel.setNameFieldLabel_("Export To:")
        exportPanel.setPrompt_("Export")
        exportPanel.setCanSelectHiddenExtension_(True)
        exportPanel.setShowsTagField_(False)
        exportPanel.setAllowedFileTypes_(self.formats[kind])
        exportPanel.setRequiredFileType_(format)
        exportPanel.setAccessoryView_(accessory)
        
        # present the dialog
        callback = "exportPanelDidEnd:returnCode:contextInfo:"
        context = 0 if kind=='image' else 1
        exportPanel.beginSheetForDirectory_file_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            dirName, fileName, NSApp().mainWindow(), self, callback, context
        )

    def exportPanelDidEnd_returnCode_contextInfo_(self, panel, returnCode, context):
        if not returnCode: return

        kind = 'movie' if context else 'image'
        fname = panel.filename()
        self.cwd = os.path.split(fname)[0] # Save the directory we exported to.
        if kind=='image':
            opts = dict(format=panel.requiredFileType(), 
                        first=1,
                        last=self.imagePageCount.intValue())

        elif kind=='movie':
            format_idx = self.movieFormat.indexOfSelectedItem()
            opts = dict(format=panel.requiredFileType(), 
                        first=1,
                        last=self.movieFrames.intValue(),
                        fps=self.movieFps.floatValue(),
                        loop=-1 if self.movieLoop.state()==NSOnState else 0,
                        bitrate=self.movieBitrate.selectedItem().tag() )

        setattr(self, kind, dict(opts))
        panel.close()
        panel.setAccessoryView_(None)
        self.document.exportConfig(kind, fname, opts)

    @objc.IBAction
    def imageFormatChanged_(self, sender):
        panel = sender.window()
        format = self.formats['image'][sender.indexOfSelectedItem()]
        panel.setRequiredFileType_(format)

    @objc.IBAction
    def movieFormatChanged_(self, sender):
        panel = sender.window()
        format = self.formats['movie'][sender.indexOfSelectedItem()]
        panel.setRequiredFileType_(format)
        is_gif = format==gif
        self.movieLoop.setState_(NSOnState if is_gif else NSOffState)
        self.movieLoop.setEnabled_(is_gif)
        self.movieBitrate.setEnabled_(not is_gif)

