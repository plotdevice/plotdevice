__all__ = ["AskString"]

import objc
from Foundation import *
from AppKit import *

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
