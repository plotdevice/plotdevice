#!/bin/sh
# Builds the NodeBox Mac OS X application (and optionally its distribution formats).

VERSION=$(grep __version__ nodebox/__init__.py | egrep -o '\d\.\d\.\d')
TOP=`pwd`
RSRC="$TOP/dist/NodeBox.app/Contents/Resources"
SITE_PKGS="$RSRC/lib/python2.7/site-packages"

# Remove dist and build
python setup.py clean

# Build the application.
python setup.py py2app --no-strip --semi-standalone

# Do some py2app `configuration'
mkdir $SITE_PKGS
cd $SITE_PKGS
unzip -q ../site-packages.zip
rm ../site-packages.zip
mkdir $RSRC/python
ln -s ../lib/python2.7/site-packages/nodebox $RSRC/python/nodebox
cd $TOP
ditto nodebox $SITE_PKGS/nodebox

if [ "$1" = "dist" ]; then
  # Make a staging area for the disk image
  mkdir -p dist/NodeBox/NodeBox
  cd dist/NodeBox/NodeBox

  # Copy the current NodeBox application.
  cp -R -p ../../NodeBox.app .

  # Copy changes and readme
  cp ../../../CHANGES.md Changes.txt
  cp ../../../README.md Readme.txt

  # Copy examples
  cp -R ../../../examples Examples
  chmod 755 Examples/*/*

  # Make DMG
  cd ../..
  hdiutil create NodeBox-$VERSION.dmg -srcfolder NodeBox
  hdiutil internet-enable NodeBox-$VERSION.dmg

  # Make Zip
  zip -r NodeBox-$VERSION.zip NodeBox

  # clean up
  rm -r NodeBox
fi

cd $TOP

echo "done building ./dist/NodeBox.app"

