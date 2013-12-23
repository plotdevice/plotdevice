#!/bin/sh
# Builds the NodeBox Mac OS X application (and optionally its distribution formats).

TOP=`pwd`
VERSION=$(python -c 'import nodebox; print nodebox.__version__')
RSRC="$TOP/dist/NodeBox.app/Contents/Resources"
BIN="$TOP/dist/NodeBox.app/Contents/SharedSupport"
SITE_PKGS="$RSRC/lib/python2.7/site-packages"

clean () {
    # Remove dist, build, and libs/.../build
    python setup.py clean
}

build () {
    # Build the application.
    python setup.py py2app

    # Do some py2app `configuration' to make the bundle layout more
    # like what xcode produces
    mkdir $SITE_PKGS
    cd $SITE_PKGS
    unzip -q ../site-packages.zip
    rm ../site-packages.zip

    cd $TOP
    ditto nodebox $SITE_PKGS/nodebox
    ditto examples $RSRC/examples
    mkdir -p $BIN
    cp -p boot/nodebox $BIN
    chmod 755 $BIN/nodebox

    cd $RSRC
    mkdir python
    ln -s ../lib/python2.7/site-packages/nodebox python/nodebox
    cp -p lib/python2.7/lib-dynload/*.so python

    rmdir ../Frameworks
    mkdir English.lproj
    mv *.nib "NodeBox Help" English.lproj/

    cd $TOP
    rm -r build
    echo "done building NodeBox.app in ./dist"
}

dist () {
    # Make a staging area for the disk image
    mkdir -p dist/NodeBox/NodeBox
    cd dist/NodeBox/NodeBox

    # Copy the current NodeBox application.
    ditto ../../NodeBox.app NodeBox.app

    # Copy changes and readme
    cp ../../../CHANGES.md Changes.txt
    cp ../../../README.md Readme.txt

    # Copy examples
    ditto ../../../examples Examples
    chmod 755 Examples/*/*.py

    # Make DMG
    cd ../..
    hdiutil create NodeBox-$VERSION.dmg -srcfolder NodeBox
    hdiutil internet-enable NodeBox-$VERSION.dmg

    # Make Zip
    zip -r NodeBox-$VERSION.zip NodeBox

    # clean up staging area
    rm -r NodeBox
    cd $TOP
    echo "done building NodeBox.app, NodeBox-$VERSION.zip, and NodeBox-$version.dmg in ./dist"
}


case $1 in
    "dist")
        clean; build; dist;;
    "clean") 
        clean;;
    *) 
        clean; build;;
esac

