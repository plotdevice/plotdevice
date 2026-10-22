# Bundled press profiles

The CMYK printing conditions `export(colors=...)` can name with a constant (`_cc/cmyk-export.md`, "The five
bundled presses"). The build stores each one zlib-compressed in `plotdevice/rsrc/press/` as `<file>.zlib` (`setup.py`'s
`build_ext`, so a pip install, `make.py dev`, a py2app app's bundled module and `deps/frameworks`' installs get them),
the way PDFs embed them, so a press PDF's output intent is written with no compressing; decompressed they're these
files byte for byte, unaltered. The Xcode app keeps a single copy in `Contents/Resources/press/` instead: its "Move
Press Profiles" build phase moves them there from the frameworks it embeds (leaving `deps/frameworks` itself as it
is), and `rsrc_path()` finds them there. They never change: a newer profile for a condition gets a new constant and a new file.

| constant | value | file | condition | publisher | license | bytes |
|---|---|---|---|---|---|---|
| `GRACOL` | `gracol` | `GRACoL2013_CRPC6.icc` | GRACoL 2013, US premium coated sheetfed (CGATS.21 CRPC6) | Idealliance (© X-Rite) | [Idealliance](LICENSE-Idealliance.txt) | 3,462,308 |
| `GRACOL_UNCOATED` | `gracol_uncoated` | `GRACoL2013UNC_CRPC3.icc` | GRACoL 2013 uncoated (CGATS.21 CRPC3) | Idealliance (© X-Rite) | [Idealliance](LICENSE-Idealliance.txt) | 3,706,408 |
| `SWOP` | `swop` | `SWOP2013C3_CRPC5.icc` | SWOP 2013, US coated web (CGATS.21 CRPC5) | Idealliance (© X-Rite) | [Idealliance](LICENSE-Idealliance.txt) | 3,339,916 |
| `FOGRA39` | `fogra39` | `ISOcoated_v2_bas.icc` | ISO 12647-2 coated, FOGRA39 (basICColor's rendition) | basICColor GmbH | [zlib](LICENSE-basICColor.txt) | 1,052,608 |
| `FOGRA47` | `fogra47` | `PSO_Uncoated_ISO12647_bas.icc` | PSO uncoated, FOGRA47 (basICColor's rendition) | basICColor GmbH | [zlib](LICENSE-basICColor.txt) | 1,879,756 |

GRACoL and SWOP are trademarks of Idealliance (PRINTING United Alliance).

## SHA-256

```
4ebbfad6bc9cfc033fdafdd8ac5df8159208932cb16d9a6596d349ae7ab50443  GRACoL2013_CRPC6.icc
0c0d5b0893c6637244a1d47108e50046c7e570c296dcf639aaa04ce2f884265c  GRACoL2013UNC_CRPC3.icc
01123776855855378ed540228875458dfe88fca233a14d5b537800353c04faaf  SWOP2013C3_CRPC5.icc
7cdd1a643a1703fe62c30cd0cd2aba0fb01ae8d5a1ac985c8f8964ff73e4fae0  ISOcoated_v2_bas.icc
fb66b8ca8cb795575628e6fee8eee7b26e71084db882ef2b0b17329fa5127b49  PSO_Uncoated_ISO12647_bas.icc
```

Check with `shasum -a 256 -c` against the block above.

## Where they came from

Each file is byte-identical to the copy in a Debian package, which snapshot.debian.org serves by the package's
SHA-1 (both packages' SHA-1s checked against the downloads, 2026-10-21):

- **Idealliance's three**: `icc-profiles` 2.6 (Debian non-free), `/usr/share/color/icc/<file>`; package
  `icc-profiles_2.6_all.deb`, SHA-1 `20e52e4225bb270f8a0744ab766db3ffc996733f`,
  <https://snapshot.debian.org/file/20e52e4225bb270f8a0744ab766db3ffc996733f>. The publisher's own copies, from the
  ICC profile registry (<https://registry.color.org/profile-registry/profiles/GRACoL2013_CRPC6.icc> and so on; pages
  at <https://color.org/registry/GRACoL2013_CRPC6.xalter>), are byte-identical (all three, re-downloaded 2026-10-21).
- **basICColor's two**: `icc-profiles-free` 2.4 (Debian main), `/usr/share/color/icc/<file>`; package
  `icc-profiles-free_2.4_all.deb`, SHA-1 `22bb796b328597d710d5396d099a5f251cd05766`,
  <https://snapshot.debian.org/file/22bb796b328597d710d5396d099a5f251cd05766>; also at
  <https://sources.debian.org/data/main/i/icc-profiles-free/2.4/icc-profiles-basiccolor-printing2009/default_profiles/printing/ISOcoated_v2_bas.ICC>
  (and `PSO_Uncoated_ISO12647_bas.ICC`; both are named `.ICC` upstream and in Debian, and `.icc` here, as the other
  three are). basICColor's own site for them (colormanagement.org) is gone; a separate
  download of `ISOcoated_v2_bas` in the design session matched Debian's copy.

(Every URL above was re-fetched on 2026-10-21: the registry's and sources.debian.org's files are byte-identical to
these, both snapshot.debian.org packages have the SHA-1s their URLs name, and the five files inside them match.)

## Licenses

- **Idealliance** (`LICENSE-Idealliance.txt`): each profile's own copyright tag (`cprt`) reads, verbatim:
  "Copyright X-Rite, Inc. This profile is made available by IDEAlliance, with permission of X-Rite, Inc., and may be
  used, embedded, exchanged, included in commercial software and shared without restriction. It may not be altered
  without written permission of IDEAlliance except for single site use." (Debian's `copyright` file gives an older,
  generic wording for the whole IDEAlliance set, "may not be altered, or sold"; the 2013 files' own tag is the one
  above.) These files are distributed unaltered.
- **basICColor** (`LICENSE-basICColor.txt`): the zlib license, "Copyright (c) 2007-2010, basICColor GmbH", verbatim
  from the upstream `LICENSE-ZLIB-bICC` (<https://sources.debian.org/data/main/i/icc-profiles-free/2.4/icc-profiles-basiccolor-printing2009/default_profiles/printing/LICENSE-ZLIB-bICC>);
  basICColor moved "the default CMYK profiles, which can be found on www.colormanagement.org" to it in Karl Koch's
  announcement of 2010-09-01 (<https://lists.freedesktop.org/archives/openicc/2010q3/002218.html>). The files' own `cprt` tags still carry their
  original notices ("basICColor CMYKick v1.2 - Copyright (c) 2006-2007 Color Solutions, All Rights Reserved." in
  `ISOcoated_v2_bas`, "basICColor print v3.1.1 build 5969- Copyright (c) 2002-2009 basICColor GmbH, All Rights
  Reserved." in `PSO_Uncoated_ISO12647_bas`). These files are distributed unaltered.
