#!/bin/sh
# Builds the NodeBox Mac OS X distribution folder.

# Remove dist and build
rm -rf dist build

# First, make the help files.
cd ../helpsrc
python makehelp.py

# Now build the application.
cd ../src
python macsetup.py py2app

# Now make a distro directory that will contain all the files.
mkdir -p dist/NodeBox
cd dist/NodeBox
mv ../NodeBox.app .
cp ../../Changes.txt .
cp ../../ReadMe.txt .
svn export http://dev.nodebox.net/svn/nodebox/trunk/examples/ Examples

# Zip the distro.
cd ../
zip -r NodeBox-latest.zip NodeBox

# All done.
cd ../