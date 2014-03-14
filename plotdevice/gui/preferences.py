import re
import os
import json
from AppKit import *
from Foundation import *
from subprocess import Popen, PIPE
from plotdevice.gui import bundle_path, set_timeout

def get_default(label):
    if not re.match(r'^(NS|Web)', label):
        label = 'plotdevice:%s'%label
    pref = NSUserDefaults.standardUserDefaults().objectForKey_(label)
    return pref

def set_default(label, value):
    if not re.match(r'^(NS|Web)', label):
        label = 'plotdevice:%s'%label
    NSUserDefaults.standardUserDefaults().setObject_forKey_(value, label)
    NSUserDefaults.standardUserDefaults().synchronize()

def defaultDefaults():
    return {
        "WebKitDeveloperExtras":True,
        "plotdevice:remote-port": 9001,
        "plotdevice:theme":"Blackboard",
        "plotdevice:bindings":"mac",
        "plotdevice:font-name":"Menlo",
        "plotdevice:font-size":11,
    }
NSUserDefaults.standardUserDefaults().registerDefaults_(defaultDefaults())
THEMES = json.load(file(bundle_path(rsrc='ui/themes.json')))
ERR_COL = NSColor.colorWithRed_green_blue_alpha_(167/255.0, 41/255.0, 34/255.0, 1.0)
OK_COL = NSColor.colorWithRed_green_blue_alpha_(60/255.0, 60/255.0, 60/255.0, 1.0)

def _hex_to_nscolor(hexclr):
    hexclr = hexclr.lstrip('#')
    r, g, b, a = [int(n, 16)/255.0 for n in (hexclr[0:2], hexclr[2:4], hexclr[4:6], hexclr[6:8])]
    return NSColor.colorWithDeviceRed_green_blue_alpha_(r,g,b,a)

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
    homebin = '%s/bin/plotdevice'%os.environ['HOME']
    localbin = '/usr/local/bin/plotdevice'
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
            path += '/plotdevice'
            if '/sbin' in path: continue
            if path.startswith('/bin'): continue
            if path.startswith('/usr/bin'): continue
            if path in locations: continue
            locations.append(path)
    return locations



# class defined in PlotDevicePreferences.xib
class PlotDevicePreferencesController(NSWindowController):
    themeMenu = objc.IBOutlet()
    bindingsMenu = objc.IBOutlet()
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
        self = self.initWithWindowNibName_("PlotDevicePreferences")
        self.setWindowFrameAutosaveName_("PlotDevicePreferencesPanel")
        self.timer = None
        return self

    def awakeFromNib(self):
        self.toolPortStepper.setIntValue_(get_default('remote-port'))
        self.toolPort.setStringValue_(str(get_default('remote-port')))
        self.toolPort.setTextColor_(ERR_COL if not NSApp().delegate()._listener.active else OK_COL)
        self.checkTool()
        self.checkThemes()
        self.checkFonts()
        self.checkBindings()

    def _notify(self, notification):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(notification, None)

    def validateMenuItem_(self, item):
        return item.title() not in ('Light', 'Dark')

    def windowDidBecomeMain_(self, notification):
        self.checkTool()
        self.checkFonts()

    def checkBindings(self):
        style = get_default('bindings')
        tag = ['mac','emacs','vim']
        self.bindingsMenu.selectItemWithTag_(tag.index(style))

    @objc.IBAction
    def bindingsChanged_(self, sender):
        style = ['mac','emacs','vim'][sender.selectedItem().tag()]
        set_default('bindings', style)
        self._notify('BindingsChanged')

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
            selected = defaultDefaults()['plotdevice:theme']

        self.themeMenu.selectItemWithTitle_(selected)

    @objc.IBAction
    def themeChanged_(self, sender):
        set_default('theme', sender.title())
        _editor_info.clear()
        self._notify("ThemeChanged")

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
        self._notify("FontChanged")

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
        self.toolPath.setTextColor_(ERR_COL if not valid else OK_COL)
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
        self.toolPortTimer = set_timeout(self, "switchPort:", 0.4)

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
            console_py = bundle_path('Contents/SharedSupport/plotdevice')
            pth = self.toolInstallMenu.selectedItem().title().replace('~',os.environ['HOME'])
            dirname = os.path.dirname(pth)
            try:
                if os.path.exists(pth) or os.path.islink(pth):
                    os.unlink(pth)
                elif not os.path.exists(dirname):
                    os.makedirs(dirname)
                os.symlink(console_py, pth)
            except OSError:
                SysAdmin = objc.lookUpClass('SysAdmin')
                SysAdmin.createSymlink_(pth)
        self.checkTool()
        NSApp().endSheet_(self.toolInstallSheet)
        self.toolInstallSheet.orderOut_(self)

    # def windowWillClose_(self, notification):
    #     pass
