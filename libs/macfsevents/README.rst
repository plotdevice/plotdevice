.. contents::

Overview
========

.. role:: mod(emphasis)

:mod:`MacFSEvents` is a Python library that provides thread-safe
directory observation primitives using callbacks. It wraps the Mac OS
X ``FSEvents`` API in a C-extension.

Requirements:

- Mac OS X 10.5+ (Leopard)
- Python 2.7+

This software was written by Malthe Borch <mborch@gmail.com>. The
:mod:`pyfsevents` module by Nicolas Dumazet was used for reference.

Why?
----

At this time of writing there are four other libraries that integrate
with the ``FSEvents`` API:

**watchdog**:

  This library actually builds on the code in :mod:`MacFSEvents` (this
  project), but currently does not support Python 3 (though this
  should happen soon). It also includes shell utilities.

**pyobjc-framework-FSEvents**

  These use the PyObjC bridge infrastructure which most applications
  do not need.

**pyfsevents**

  Not thread-safe (API is not designed to support it).

**fsevents**

  Obsolete bindings to the socket API by John Sutherland.

The :mod:`MacFSEvents` library provides a clean API and has full test
coverage.

Note that :mod:`pyfsevents` has bindings to the file descriptor
observation primitives. This is not currently implemented by the
present library.

License
-------

Made available as-is under the BSD License.

Usage
=====

To observe a directory structure (recursively) under ``path``, we set
up an observer thread and schedule an event stream::

  from fsevents import Observer
  observer = Observer()
  observer.start()

  def callback(FileEvent):
      ...

  from fsevents import Stream
  stream = Stream(callback, path)
  observer.schedule(stream)

Streams can observe any number of paths; simply pass them as
positional arguments (or using the ``*`` operator)::

  stream = Stream(callback, *paths)

To start the observer in its own thread, use the ``start`` method::

  observer.starts()

To start the observer in the current thread, use the ``run`` method
(it will block the thread until stopped from another thread)::

  observer.run()

The callback function will be called when an event occurs. A
``FileEvent`` instance is passed to the callback and has 3 attributes:
``mask``, ``cookie`` and ``name``. ``name`` parameter contains the path
at which the event happened (may be a subdirectory) while ``mask``
parameter is the event mask [#]_.

To stop observation, simply unschedule the stream and stop the
observer::

  observer.unschedule(stream)
  observer.stop()

While the observer thread will automatically join your main thread at
this point, it doesn't hurt to be explicit about this::

  observer.join()

We often want to know about events on a file level; to receive file
events instead of path events, pass in ``file_events=True`` to the
stream constructor::

  def callback(event):
      ...

  stream = Stream(callback, path, file_events=True)

The event object mimick the file events of the ``inotify`` kernel
extension available in newer linux kernels. It has the following
attributes:

``mask``
   The mask field is a bitmask representing the event that occurred.

``cookie``
   The cookie field is a unique identifier linking together two related but separate events. It is used to link together an ``IN_MOVED_FROM`` and an ``IN_MOVED_TO`` event.

``name``
   The name field contains the name of the object to which the event occurred. This is the absolute filename.

Note that the logic to implement file events is implemented in Python;
a snapshot of the observed file system hierarchies is maintained and
used to monitor file events.

.. [#] See `FSEventStreamEventFlags <http://developer.apple.com/mac/library/documentation/Darwin/Reference/FSEvents_Ref/FSEvents_h/index.html#//apple_ref/c/tag/FSEventStreamEventFlags>`_ for a reference. To check for a particular mask, use the *bitwise and* operator ``&``.
