def bundle_path(subpath=None, rsrc=None, fmwk=None):
    """Find the path to the main NSBundle (or an optional subpath within it)"""
    from os.path import join
    from Foundation import NSBundle
    bundle = NSBundle.mainBundle().bundlePath()
    if rsrc:
      return join(bundle, "Contents", "Resources", rsrc)
    if fmwk:
      return join(bundle, "Contents", "Frameworks", '%s.framework' % fmwk)
    if subpath:
        return join(bundle, subpath)
    return bundle

import os, sys
from Foundation import NSTimer, NSRunLoop, NSRunLoopCommonModes
from AppKit import (NSApplication, NSDate, NSEventMaskAny,
                    NSEventMaskMouseMoved, NSEventMaskMouseEntered, NSEventMaskMouseExited,
                    NSEventMaskCursorUpdate, NSEventMaskPeriodic, NSEventMaskAppKitDefined,
                    NSEventMaskSystemDefined, NSEventMaskApplicationDefined)
from Quartz import CACurrentMediaTime

FRAMELOG = bool(os.environ.get('PLOTDEVICE_FRAMELOG'))

def set_timeout(target, sel, delay, info=None, repeat=False):
    timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(delay, target, sel, info, repeat)
    NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)
    return timer

def next_tick(target, sel):
    timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(0, target, sel, None, False)
    NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)

class FrameClock:

    LAG_WINDOW = 1.0  # seconds of sustained overrun before `lagging` trips
    MIN_IDLE = 0.001  # run-loop time guaranteed between frames when draws overrun the budget
    INPUT = NSEventMaskAny & ~(NSEventMaskMouseMoved | NSEventMaskMouseEntered | NSEventMaskMouseExited
                              | NSEventMaskCursorUpdate | NSEventMaskPeriodic | NSEventMaskAppKitDefined
                              | NSEventMaskSystemDefined | NSEventMaskApplicationDefined)

    def __init__(self, view, target, sel, fps):
        self._link = self._timer = self._restart = None
        self._target, self._sel = target, sel
        self._rate = float(fps)
        self._period = 1.0 / fps
        self._credit = 1.0        # frames owed (fractional); starts at one so the first vblank draws
        self._tick = None         # when the credit was last brought up to date
        self._refresh = 1.0 / 60  # display refresh interval; measured per-callback in should_draw()
        self._started = None      # when the in-flight draw actually began (callback time, not vblank)
        self._latency = 0.0       # how long after its vblank that callback ran
        self._last = None         # completion time of the most recent draw
        self._busy = None         # smoothed draw duration
        self._gap = None          # smoothed interval between completed frames
        self._lagged = None       # when the current stretch of over-budget frames began
        self._restarted = False   # whether the in-flight frame was started by the restart timer
        self._late = 0.0          # if so, how long after its due time the timer fired
        self._yielded = 0         # frames held back for the run loop to deliver queued input
        if view is not None and hasattr(view, 'displayLinkWithTarget_selector_'):
            link = view.displayLinkWithTarget_selector_(target, sel)
            link.addToRunLoop_forMode_(NSRunLoop.mainRunLoop(), NSRunLoopCommonModes)
            self._link = link
        else:
            self._timer = set_timeout(target, sel, self._period, repeat=True)

    def should_draw(self):
        now = CACurrentMediaTime()
        if not self.isValid():
            return False  # invalidated (paused or stopped): no frame is ever due again
        if self._started is not None:
            return False  # a frame is already in flight (re-entered from inside it)
        if self._link is None:
            self._started = now
            return True
        t = self._link.timestamp()
        vblank = self._link.targetTimestamp() - t
        if vblank > 0:
            self._refresh = vblank

        if self._tick is not None:
            self._credit += self._rate * (now - self._tick)
        self._tick = now

        if self._credit < 1.0 - 0.5 * min(1.0, self._rate * self._refresh):
            return False
        if self._last is not None and now < self._last + self.MIN_IDLE - 1e-5:
            self._schedule_restart(now, self._last + self.MIN_IDLE)
            return False
        if self._gap is not None and self._gap > self._period and self._input_pending():
            self._yielded += 1
            self._schedule_restart(now, now + self.MIN_IDLE)
            return False
        self._restarted = self._restart is not None
        if self._restarted:
            self._late = now - self._restart_at  # how long after its due time the timer fired
            self._restart.invalidate()
            self._restart = None
        self._credit = min(self._credit - 1.0, 1.0)
        self._started = now
        self._latency = now - t
        return True

    def _schedule_restart(self, now, at):
        if self._restart is None:
            self._restart_at = at
            self._restart = set_timeout(self._target, self._sel, max(0.0, at - now))

    def _input_pending(self):
        app = NSApplication.sharedApplication()
        probe = app.nextEventMatchingMask_untilDate_inMode_dequeue_(self.INPUT, NSDate.distantPast(), 'PlotDeviceFrameClockPeek', False)
        return probe is not None

    def frame_done(self):
        now = CACurrentMediaTime()
        ema = lambda old, new: new if old is None else old + 0.2 * (new - old)
        drew = None if self._started is None else now - self._started
        if drew is not None:
            self._busy = ema(self._busy, drew)
        if self._last is not None:
            self._gap = ema(self._gap, now - self._last)
        self._last = now
        self._started = None
        self._adapt(now)
        if self._link is not None and drew is not None and drew >= self._period:
            self._schedule_restart(now, now + self.MIN_IDLE)
        if FRAMELOG and drew is not None:
            self._framelog(now, drew)

    @property
    def fps(self):
        return 1.0 / self._gap if self._gap else 1.0 / self._period

    @property
    def lagging(self):
        return self._lagged is not None and CACurrentMediaTime() - self._lagged > self.LAG_WINDOW

    def _adapt(self, now):
        if self._gap is not None:
            if self._gap > self._period / 0.9:      # achieved < 90% of requested
                if self._lagged is None:
                    self._lagged = now
            elif self._gap <= self._period / 0.97:  # achieved >= 97% of requested
                self._lagged = None

    def _framelog(self, now, drew):
        log = self.__dict__.setdefault('_log', [])
        run, view = getattr(self, '_parts', (0.0, 0.0)) # set by ScriptController.invoke()
        prev = self.__dict__.get('_logged', now)
        log.append((self._latency, drew, now - prev, run, view, self._restarted, self._late if self._restarted else None))
        self._logged = now
        if len(log) < 60:
            return
        cols = list(zip(*log))
        ms = lambda vals: sum(vals) / len(vals) * 1e3 if vals else 0.0
        late = [l for l in cols[6] if l is not None]
        sys.stderr.write('frames %d | fps %.1f | refresh %.1f ms | frame %.1f ms (max %.1f) = draw %.1f + render %.1f | '
                         'over budget %d/%d | gap %.1f ms | restarted %d (timer late by %.1f ms, max %.1f) | '
                         'yielded for input %d | callback latency %.1f ms\n' % (
            len(log), self.fps, self._refresh * 1e3, ms(cols[1]), max(cols[1]) * 1e3, ms(cols[3]), ms(cols[4]),
            sum(1 for d in cols[1] if d > self._period), len(log), ms(cols[2][1:]),
            sum(cols[5]), ms(late), max(late) * 1e3 if late else 0.0, self._yielded, ms(cols[0])))
        sys.stderr.flush()
        self._yielded = 0
        del log[:]

    def isValid(self):
        return (self._link is not None) or bool(self._timer and self._timer.isValid())

    def invalidate(self):
        if self._restart is not None:
            self._restart.invalidate()
            self._restart = None
        if self._link is not None:
            self._link.invalidate()      # also removes it from the run loop
            self._link = None
        elif self._timer is not None:
            self._timer.invalidate()
            self._timer = None

from .document import PlotDeviceDocument, PythonScriptDocument, ScriptController
from .app import PlotDeviceAppDelegate
from .views import CenteringClipView, GraphicsView, FullscreenView
from .widgets import StatusView, DashboardController, ExportSheet
