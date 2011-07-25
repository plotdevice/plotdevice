import objc
from Foundation import *
from AppKit import *

class ProgressBarController(NSWindowController):
    messageField = objc.IBOutlet()
    progressBar = objc.IBOutlet()
    
    def init(self):
        NSBundle.loadNibNamed_owner_("ProgressBarSheet", self)
        return self

    def begin(self, message, maxval):
        self.value = 0
        self.message = message
        self.maxval = maxval
        self.progressBar.setMaxValue_(self.maxval)
        self.messageField.cell().setTitle_(self.message)
        parentWindow = NSApp().keyWindow()
        NSApp().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(self.window(), parentWindow, self, None, 0)
        
    def inc(self):
        self.value += 1
        self.progressBar.setDoubleValue_(self.value)
        date = NSDate.dateWithTimeIntervalSinceNow_(0.01)
        NSRunLoop.currentRunLoop().acceptInputForMode_beforeDate_(NSDefaultRunLoopMode, date)
        
    def end(self):
        NSApp().endSheet_(self.window())
        self.window().orderOut_(self)
        