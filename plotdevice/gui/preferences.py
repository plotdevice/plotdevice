import re
import os
import json
import objc
from io import open
from subprocess import Popen, PIPE

from ..lib.cocoa import *
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
        "plotdevice:theme":"Solarized Dark",
        "plotdevice:bindings":"mac",
        "plotdevice:font-name":"Menlo",
        "plotdevice:font-size":11,
    }
NSUserDefaults.standardUserDefaults().registerDefaults_(defaultDefaults())
ERR_COL = NSColor.colorWithRed_green_blue_alpha_(167/255.0, 41/255.0, 34/255.0, 1.0)
OK_COL = NSColor.colorWithRed_green_blue_alpha_(60/255.0, 60/255.0, 60/255.0, 1.0)
THEMES = None # to be filled in as needed

def _hex_to_nscolor(hexclr):
    hexclr = hexclr.lstrip('#')
    r, g, b, a = [int(n, 16)/255.0 for n in (hexclr[0:2], hexclr[2:4], hexclr[4:6], hexclr[6:8])]
    return NSColor.colorWithDeviceRed_green_blue_alpha_(r,g,b,a)

_editor_info = {}
def editor_info(name=None):
    if not _editor_info:
        global THEMES
        if THEMES is None:
            THEMES = json.load(open(bundle_path(rsrc='ui/themes.json')))
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

    # find the user's login shell
    out, _ = Popen(['dscl','.','-read','/Users/'+os.environ['USER'],'UserShell'], stdout=PIPE).communicate()
    shell = out.replace('UserShell:','').strip()

    # try launching a shell to extract the user's path
    if shell:
        out, _ = Popen([shell,"-l"], stdout=PIPE, stderr=PIPE, stdin=PIPE).communicate("echo $PATH")
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
    themeMenu = IBOutlet()
    bindingsMenu = IBOutlet()
    fontMenu = IBOutlet()
    fontSizeMenu = IBOutlet()
    toolPath = IBOutlet()
    toolAction = IBOutlet()
    toolBoilerplate = IBOutlet()
    toolInstallSheet = IBOutlet()
    toolInstallMenu = IBOutlet()
    updateDaily = IBOutlet()
    updateNow = IBOutlet()

    def init(self):
        self = self.initWithWindowNibName_("PlotDevicePreferences")
        self.setWindowFrameAutosaveName_("PlotDevicePreferencesPanel")
        return self

    def awakeFromNib(self):
        self.window().setRestorable_(True)
        self.checkTool()
        self.checkThemes()
        self.checkFonts()
        self.checkBindings()
        self.checkUpdater()

    def _notify(self, notification):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(notification, None)

    def validateMenuItem_(self, item):
        return item.title() not in ('Light', 'Dark')

    def windowDidBecomeMain_(self, notification):
        self.checkTool()
        self.checkFonts()

    def checkUpdater(self):
        sparkle_path = bundle_path(fmwk='Sparkle')
        if os.path.exists(sparkle_path):
            # if this is a sparkle build, hook the ui elements up to the sharedUpdater
            objc.loadBundle('Sparkle', globals(), bundle_path=sparkle_path)
            sparkle = objc.lookUpClass('SUUpdater').sharedUpdater()
            self.updateDaily.bind_toObject_withKeyPath_options_('value', sparkle, "automaticallyChecksForUpdates", None)
            self.updateNow.setTarget_(sparkle)
            self.updateNow.setAction_("checkForUpdates:")
        else:
            # otherwise hide the Software Update box and resize the window
            updater_box = self.updateNow.superview().superview()
            updater_box.setHidden_(True)
            frame = self.window().frame()
            frame.size.height -= 52
            self.window().setFrame_display_(frame, True)

    def checkBindings(self):
        style = get_default('bindings')
        tag = ['mac','emacs','vim']
        self.bindingsMenu.selectItemWithTag_(tag.index(style))

    @IBAction
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

    @IBAction
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

    @IBAction
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
        found, valid, action = self._tool

        self.toolAction.setTitle_(action.title())
        self.toolPath.setSelectable_(found is not None)
        self.toolPath.setStringValue_(found if found else '')
        self.toolPath.setTextColor_(OK_COL if valid else ERR_COL)
        self.toolBoilerplate.setHidden_(found is not None)
        self.toolPath.setHidden_(found is None)

    @property
    def _tool(self):
        broken = []
        for path in possibleToolLocations():
            if os.path.islink(path):
                # if it's a symlink, make sure it points to this bundle
                tool_path = os.path.realpath(path)
                found = path
                valid = tool_path.startswith(bundle_path())
                if valid:
                    action = 'reveal'
                    break
                broken.append(path)
            if os.path.exists(path):
                # if it's a normal file, something went wrong
                broken.append(path)
        else:
            # didn't find any working symlinks in the $PATH
            found = broken[0] if broken else None
            valid = False
            action = 'install' if not found else 'repair'

        return found, valid, action

    @IBAction
    def toolChanged_(self, sender):
        found, _, action = self._tool

        if action == 'reveal':
            os.system('open --reveal "%s"'%found)
        elif action in ('install', 'repair'):
            locs = [loc.replace(os.environ['HOME'],'~') for loc in possibleToolLocations()]
            self.toolInstallMenu.removeAllItems()
            self.toolInstallMenu.addItemsWithTitles_(locs)
            NSApp().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(self.toolInstallSheet, self.window(), self, None, 0)

    @IBAction
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
