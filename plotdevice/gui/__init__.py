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

import sys, time, queue, threading
from Foundation import NSTimer, NSRunLoop, NSRunLoopCommonModes
from PyObjCTools import AppHelper
from .. import free_threaded
from ..util import autorelease
from AppKit import (NSApplication, NSDate, NSEventMaskAny,
                    NSEventMaskMouseMoved, NSEventMaskMouseEntered, NSEventMaskMouseExited,
                    NSEventMaskCursorUpdate, NSEventMaskPeriodic, NSEventMaskAppKitDefined,
                    NSEventMaskSystemDefined, NSEventMaskApplicationDefined)
from Quartz import CACurrentMediaTime

def set_timeout(target, sel, delay, info=None, repeat=False):
    timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(delay, target, sel, info, repeat)
    NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)
    return timer

def next_tick(target, sel):
    timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(0, target, sel, None, False)
    NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)

class FrameClock:
    """Triggers a selector at a target FPS, synced to the display"""

    MIN_IDLE = 0.001 # run-loop time between overruns

    # input worth holding a late frame for
    INPUT = NSEventMaskAny & ~(NSEventMaskMouseMoved | NSEventMaskMouseEntered | NSEventMaskMouseExited
                              | NSEventMaskCursorUpdate | NSEventMaskPeriodic | NSEventMaskAppKitDefined
                              | NSEventMaskSystemDefined | NSEventMaskApplicationDefined)

    def __init__(self, view, target, sel, fps):
        self._link = self._timer = self._restart = self._restart_at = None
        self._target, self._sel = target, sel
        self._rate = float(fps)
        self._period = 1.0 / fps
        self._credit = 1.0       # frames owed, starting at one
        self._tick = None        # when credit was last updated
        self._refresh = 1.0 / 60 # display refresh (measured below)
        self._started = None     # when the in-flight draw began
        self._last = None        # when the last draw finished
        self._gap = None         # smoothed time between frames
        self._due = None         # next due time, for NSTimer
        if view is not None and hasattr(view, 'displayLinkWithTarget_selector_'):
            # should_draw() downsamples vblanks
            link = view.displayLinkWithTarget_selector_(target, sel)
            link.addToRunLoop_forMode_(NSRunLoop.mainRunLoop(), NSRunLoopCommonModes)
            self._link = link
        else:
            self._timer = set_timeout(target, sel, self._period, repeat=True)

    def should_draw(self, delivered=False):
        """True when a frame is due and the run loop has had its turn"""
        now = CACurrentMediaTime()
        if not self.isValid():
            return False # paused or stopped
        if self._started is not None:
            return False # re-entered mid-frame
        fired = self._restart is not None and now >= self._restart_at - 1e-5
        if fired:
            self._restart = None # forget the expired restart timer
        if self._link is None:
            # within a quarter period, for jitter
            if self._due is not None and now < self._due - 0.25 * self._period:
                return False
            # the next is due a period later
            scheduled = now if self._due is None else self._due
            self._due = max(scheduled, now - self._period) + self._period
            self._started = now
            return True
        t = self._link.timestamp()
        vblank = self._link.targetTimestamp() - t
        if vblank > 0:
            self._refresh = vblank

        # frames owed, by the clock
        if self._tick is not None:
            self._credit += self._rate * (now - self._tick)
        self._tick = now

        # a frame is due on the vblank closest to when it's owed, not the first one after
        slack = 0.0 if delivered else 0.5 * min(1.0, self._rate * self._refresh)
        if self._credit < 1.0 - slack:
            return False
        if self._last is not None and now < self._last + self.MIN_IDLE - 1e-5:
            # due, but let the run loop breathe first
            self._schedule_restart(now, self._last + self.MIN_IDLE)
            return False
        if self._gap is not None and self._gap > self._period and self._input_pending():
            # let lagging frames yield to input
            self._schedule_restart(now, now + self.MIN_IDLE)
            return False
        if self._restart is not None:
            # a vblank beat a pending restart to the punch
            self._restart.invalidate()
            self._restart = None
        self._credit = min(self._credit - 1.0, 1.0)
        self._started = now
        return True

    def _schedule_restart(self, now, at):
        if self._restart is None:
            self._restart_at = at
            self._restart = set_timeout(self._target, self._sel, max(0.0, at - now))

    def _input_pending(self):
        """Whether the user has keyboard/mouse events waiting in the queue"""
        app = NSApplication.sharedApplication()
        probe = app.nextEventMatchingMask_untilDate_inMode_dequeue_(self.INPUT, NSDate.distantPast(), 'PlotDeviceFrameClockPeek', False)
        return probe is not None

    def frame_done(self):
        """Fold the finished draw into the pacing stats"""
        now = CACurrentMediaTime()
        ema = lambda old, new: new if old is None else old + 0.2 * (new - old)
        drew = None if self._started is None else now - self._started
        if self._last is not None:
            self._gap = ema(self._gap, now - self._last)
        self._last = now
        self._started = None

        if self._link is not None and drew is not None and drew >= self._period:
            self._schedule_restart(now, now + self.MIN_IDLE)

    @property
    def period(self):
        """The time between frames at the requested fps"""
        return self._period

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

class RenderJob:
    """A job submitted to a FrameQueue"""

    def __init__(self, queue):
        self._queue = queue
        self._generation = queue._generation
        self._delivered = False
        self.elapsed = None # how long its work took

    @property
    def cancelled(self):
        """Whether the queue's cancel() has dropped it"""
        return self._generation <= self._queue._cancelled

    @property
    def pending(self):
        """Whether it's neither delivered nor cancelled"""
        return not self._delivered and not self.cancelled

class FrameQueue:
    """Renders a window's committed Frames on the render thread"""

    # if the GIL is disabled, allow drawing and rendering to overlap
    DEPTH = 2 if free_threaded and not sys._is_gil_enabled() else 1

    def __init__(self):
        self._jobs = queue.Queue()
        self._generation = 0 # from the latest submission
        self._cancelled = 0  # dropped up to this generation
        self._pending = 0    # not yet delivered
        self._thread = threading.Thread(target=self._loop, daemon=True, name='frame-queue')
        self._thread.start()

    @property
    def idle(self):
        """Whether every job submitted has been delivered"""
        return self._pending == 0

    @property
    def ready(self):
        """Whether another frame fits in the pipeline"""
        return self._pending < self.DEPTH

    def submit(self, work, deliver):
        """Queue work for the render thread and return its RenderJob"""
        self._generation += 1
        self._pending += 1
        job = RenderJob(self)
        self._jobs.put((job, work, deliver))
        return job

    def cancel(self):
        """Drop every job submitted so far"""
        self._cancelled = self._generation

    def shutdown(self):
        """Cancel outstanding work and end the thread"""
        self.cancel()
        self._jobs.put(None)
        self._thread.join(1.0)

    def _loop(self):
        while True:
            with autorelease():
                item = self._jobs.get()
                if item is None:
                    return
                job, work, deliver = item
                cancelled = lambda: job.cancelled
                result = err = None
                if not cancelled():
                    try:
                        started = time.perf_counter()
                        result = work(cancelled)
                        job.elapsed = time.perf_counter() - started
                    except Exception as e:
                        err = e
                AppHelper.callAfter(self._deliver, job, deliver, result, err)
                del item, job, work, deliver, result, err, cancelled

    def _deliver(self, job, deliver, result, err):
        self._pending -= 1
        if not job.cancelled:
            deliver(result, err)
        job._delivered = True

from .document import PlotDeviceDocument, PythonScriptDocument, ScriptController
from .app import PlotDeviceAppDelegate
from .views import CenteringClipView, GraphicsView, FullscreenView
from .widgets import StatusView, DashboardController, ExportSheet
