#from PyObjCTools import NibClassBuilder, AppHelper
from PyObjCTools import AppHelper
from AppKit import *
import objc

from nodebox import graphics

SMALL_FONT = NSFont.systemFontOfSize_(NSFont.smallSystemFontSize())
MINI_FONT = NSFont.systemFontOfSize_(NSFont.systemFontSizeForControlSize_(NSMiniControlSize))

# class defined in NodeBoxDocument.xib
class DashboardController(NSObject):
    document = objc.IBOutlet()
    documentWindow = objc.IBOutlet()
    panel = objc.IBOutlet()

    def clearInterface(self):
        for s in list(self.panel.contentView().subviews()):
            s.removeFromSuperview()

    def numberChanged_(self, sender):
        var = self.document.vars[sender.tag()]
        var.value = sender.floatValue()
        self.document.runScript(compile=False, newSeed=False)

    def textChanged_(self, sender):
        var = self.document.vars[sender.tag()]
        var.value = sender.stringValue()
        self.document.runScript(compile=False, newSeed=False)

    def booleanChanged_(self, sender):
        var = self.document.vars[sender.tag()]
        if sender.state() == NSOnState:
            var.value = True
        else:
            var.value = False
        self.document.runScript(compile=False, newSeed=False)
        
    def buttonClicked_(self, sender):
        var = self.document.vars[sender.tag()]
        self.document.fastRun(self.document.namespace[var.name], newSeed=True)
        #self.document.runFunction_(var.name)

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
