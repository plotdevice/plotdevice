import re
import os
import json
from AppKit import *
from Foundation import *
from subprocess import Popen, PIPE
from nodebox import bundle_path


def get_default(label):
    if not label.startswith('NS'):
        label = 'nodebox:%s'%label
    pref = NSUserDefaults.standardUserDefaults().objectForKey_(label)
    return pref

def set_default(label, value):
    if not label.startswith('NS'):
        label = 'nodebox:%s'%label    
    NSUserDefaults.standardUserDefaults().setObject_forKey_(value, label)

def defaultDefaults():
    return {
        "nodebox:remote-port": 9001,
        "nodebox:theme":"Blackboard",
        "nodebox:font-name":"Menlo",
        "nodebox:font-size":11,
    }
NSUserDefaults.standardUserDefaults().registerDefaults_(defaultDefaults())
THEMES = json.load(file(bundle_path('Contents/Resources/ui/themes.json')))
ERR_COL = NSColor.colorWithRed_green_blue_alpha_(167/255.0, 41/255.0, 34/255.0, 1.0)

def _hex_to_nscolor(hexclr):
    hexclr = hexclr.lstrip('#')
    r, g, b = [int(n, 16)/255.0 for n in (hexclr[0:2], hexclr[2:4], hexclr[4:6])]
    return NSColor.colorWithDeviceRed_green_blue_alpha_(r,g,b,1.0)

_editor_info = {}
def editor_info(name=None):
    if not _editor_info:
        info = dict(family=get_default('font-name'), px=get_default('font-size'))
        info.update(THEMES.get(get_default('theme')))
        info['colors'] = {k:_hex_to_nscolor(v) for k,v in info['colors'].items()}
        fm = NSFontManager.sharedFontManager()
        info['font'] = fm.fontWithFamily_traits_weight_size_(
            info['family'], 
            NSFixedPitchFontMask|NSUnboldFontMask|NSUnitalicFontMask,
            6,
            info['px']
        )
        _editor_info.clear()
        _editor_info.update(info)
    if name: 
        return _editor_info.get(name)
    return dict(_editor_info)

def possibleToolLocations():
    homebin = '%s/bin/nodebox'%os.environ['HOME']
    localbin = '/usr/local/bin/nodebox'
    locations = [homebin, localbin]

    # find the user's path by launching the same shell Terminal.app uses
    # and peeking at the $PATH
    term = NSUserDefaults.standardUserDefaults().persistentDomainForName_('com.apple.Terminal')
    if term:
        setting = term['Default Window Settings']
        shell = term['Window Settings'][setting]['CommandString']
        p = Popen([shell,"-l"], stdout=PIPE, stderr=PIPE, stdin=PIPE)
        out, err = p.communicate("echo $PATH")
        for path in out.strip().split(':'):
            path += '/nodebox'
            if '/sbin' in path: continue
            if path.startswith('/bin'): continue
            if path.startswith('/usr/bin'): continue
            if path in locations: continue
            locations.append(path)
    return locations



# class defined in NodeBoxPreferences.xib
class NodeBoxPreferencesController(NSWindowController):
    themeMenu = objc.IBOutlet()
    fontMenu = objc.IBOutlet()
    fontSizeMenu = objc.IBOutlet()
    toolInstall = objc.IBOutlet()
    toolPath = objc.IBOutlet()
    toolRepair = objc.IBOutlet()
    toolInstallSheet = objc.IBOutlet()
    toolInstallMenu = objc.IBOutlet()
    toolPort = objc.IBOutlet()
    toolPortLabel = objc.IBOutlet()
    toolPortStepper = objc.IBOutlet()
    toolPortTimer = None

    def init(self):
        self = self.initWithWindowNibName_("NodeBoxPreferences")
        self.setWindowFrameAutosaveName_("NodeBoxPreferencesPanel")
        self.timer = None
        return self

    def awakeFromNib(self):
        self.toolPortStepper.setIntValue_(get_default('remote-port'))
        self.toolPort.setStringValue_(str(get_default('remote-port')))
        self.toolPort.setTextColor_(ERR_COL if not NSApp().delegate()._listener.active else NSColor.blackColor())
        self.checkTool()
        self.checkThemes()
        self.checkFonts()

    def validateMenuItem_(self, item):
        return item.title() not in ('Light', 'Dark')

    def windowDidBecomeMain_(self, notification):
        self.checkTool()
        self.checkFonts()

    def checkThemes(self):
        light = sorted([t for t,m in THEMES.items() if not m['dark']], reverse=True)
        dark = sorted([t for t,m in THEMES.items() if m['dark']], reverse=True)
        for theme in dark:
            self.themeMenu.insertItemWithTitle_atIndex_(theme, 3)
        for theme in light:
            self.themeMenu.insertItemWithTitle_atIndex_(theme, 1)
        for item in self.themeMenu.itemArray():
            item.setRepresentedObject_(THEMES.get(item.title()))

        selected = get_default('theme')
        if selected not in THEMES:
            selected = defaultDefaults()['nodebox:theme']

        self.themeMenu.selectItemWithTitle_(selected)

    @objc.IBAction
    def themeChanged_(self, sender):
        set_default('theme', sender.title())
        _editor_info.clear()
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_("ThemeChanged", None)

    def checkFonts(self):
        allmono = NSFontManager.sharedFontManager().availableFontNamesWithTraits_(NSFixedPitchFontMask)
        validmono = [fn for fn in allmono if NSFont.fontWithName_size_(fn, 12).mostCompatibleStringEncoding()==NSMacOSRomanStringEncoding]
        validmono = [fn for fn in validmono if 'emoji' not in fn.lower()]
        fonts = {NSFont.fontWithName_size_(fn, 12).familyName() for fn in validmono}
        
        fontname = get_default('font-name')
        self.fontMenu.removeAllItems()
        self.fontMenu.addItemsWithTitles_(sorted(fonts))
        if fontname not in fonts:
            fontname = fonts[0] # just in case the active font was uninstalled
            set_default('font-name', fontname)
        self.fontMenu.selectItemWithTitle_(fontname)
        for item in self.fontMenu.itemArray():
            item.setRepresentedObject_(item.title())

        fontsize = get_default('font-size')
        sizes =  [9, 10, 11, 12, 13, 14, 15, 16, 18, 21, 24, 36, 48, 60, 72]
        self.fontSizeMenu.removeAllItems()
        self.fontSizeMenu.addItemsWithTitles_(['%i pt'%s for s in sizes])
        self.fontSizeMenu.selectItemWithTitle_('%i pt'%fontsize)
        for item, size in zip(self.fontSizeMenu.itemArray(), sizes):
            item.setRepresentedObject_(size)

    @objc.IBAction
    def fontChanged_(self, sender):
        if sender is self.fontMenu:
            default = 'font-name'
        elif sender is self.fontSizeMenu:
            default = 'font-size'
        else:
            return
        item = sender.selectedItem()
        set_default(default, item.representedObject())
        _editor_info.clear()
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_("FontChanged", None)

    def checkTool(self):
        broken = []
        for path in possibleToolLocations():
            if os.path.islink(path):
                # if it's a symlink, make sure it points to this bundle
                tool_path = os.path.realpath(path)
                found = path
                valid = tool_path.startswith(bundle_path())
                if valid: break
                broken.append(path)
            if os.path.exists(path):
                # if it's a normal file, something went wrong
                broken.append(path)
        else:
            # didn't find any working symlinks in the $PATH
            found = broken[0] if broken else None
            valid = False

        self.toolInstall.setHidden_(found is not None)
        self.toolPath.setSelectable_(found is not None)
        # self.toolPath.setStringValue_(found.replace(os.environ['HOME'],'~') if found else '')
        self.toolPath.setStringValue_(found if found else '')
        self.toolPath.setTextColor_(ERR_COL if not valid else NSColor.blackColor())
        self.toolRepair.setHidden_(not (found and not valid) )
        self.toolPort.setHidden_(not valid)
        self.toolPortLabel.setHidden_(not valid)
        self.toolPortStepper.setHidden_(not valid)
        if valid: set_default('remote-port', get_default('remote-port'))

    @objc.IBAction
    def modifyPort_(self, sender):
        newport = sender.intValue()
        self.toolPort.setStringValue_(str(newport))

        if self.toolPortTimer:
            self.toolPortTimer.invalidate()
        self.toolPortTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(0.4, self, "switchPort:", None, False)

    def switchPort_(self, timer):
        newport = self.toolPortStepper.intValue()
        set_default('remote-port', newport)
        app = NSApp().delegate()
        app.listenOnPort_(newport)
        self.toolPort.setTextColor_(ERR_COL if not app._listener.active else NSColor.blackColor())
        self.toolPortTimer = None

    @objc.IBAction 
    def installTool_(self, sender):
        locs = [loc.replace(os.environ['HOME'],'~') for loc in possibleToolLocations()]
        self.toolInstallMenu.removeAllItems()
        self.toolInstallMenu.addItemsWithTitles_(locs)
        NSApp().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(self.toolInstallSheet, self.window(), self, None, 0)

    @objc.IBAction
    def finishInstallation_(self, sender):
        should_install = sender.tag()
        if should_install:
            console_py = bundle_path('Contents/SharedSupport/nodebox')
            pth = self.toolInstallMenu.selectedItem().title().replace('~',os.environ['HOME'])
            dirname = os.path.dirname(pth)
            try:
                if os.path.exists(pth) or os.path.islink(pth):
                    os.unlink(pth)
                elif not os.path.exists(dirname):
                    os.makedirs(dirname)
                os.symlink(console_py, pth)
            except OSError:
                Installer = objc.lookUpClass('Installer')
                Installer.createLink_(pth)
        self.checkTool()
        NSApp().endSheet_(self.toolInstallSheet)
        self.toolInstallSheet.orderOut_(self)

    # def windowWillClose_(self, notification):
    #     pass
