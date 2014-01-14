Changelog
=========

0.3 (2013-01-21)
------------------

- Added compatibility with Python 3. Note that Python 2.7 or better is
  now required.

- Fixed test suite on with 10.8. The event masks reported on this
  platform are non-trivial which is a change from previous versions.

0.2.8 (2012-06-09)
------------------

Bugfixes:

- Fix recursive snapshot.
  [thomasst]

- Use os.lstat instead of os.stat to correctly detect symlinks.
  [thomasst]

0.2.7 (2012-05-29)
------------------

- Added support for IN_ATTRIB.
  [thomasst]

0.2.6 (2012-03-17)
------------------

- Fixed compilation problem on newer platforms.
  [nsfmc]

0.2.5 (2012-02-01)
------------------

- Ignore files that don't exist while recursing.
  [bobveznat]

0.2.4 (2010-12-06)
------------------

- Prevent crashes on recursive folder delete and multiple folder add.
  [totolici].

0.2.3 (2010-07-27)
------------------

- Fixed broken release.

0.2.2 (2010-07-26)
------------------

- Python 2.4 compatibility [howitz]

- Fixed an issue where the addition of a new directory would crash the
  program when using file event monitoring [andymacp].

0.2.1 (2010-04-27)
------------------

- Fixed an import issue [andymacp].

0.2 (2010-04-26)
----------------

- Fixed issue where existing directories would be reported along with
  a newly created one [marcboeker].

- Added support for file event monitoring.

- Fixed reference counting bug which could result in a segmentation
  fault.

0.1 (2009-11-27)
----------------

- Initial public release.
