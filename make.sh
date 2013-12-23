#!/bin/sh
# Builds the NodeBox Mac OS X application (and optionally its distribution formats).

TOP=`pwd`
VERSION=$(python -c 'import nodebox; print nodebox.__version__')
RSRC="$TOP/dist/NodeBox.app/Contents/Resources"
SITE_PKGS="$RSRC/lib/python2.7/site-packages"

clean () {
    # Remove dist, build, and libs/.../build
    python setup.py clean
}

build () {
    # Build the application.
    python setup.py py2app

    # Do some py2app `configuration'
    mkdir $SITE_PKGS
    cd $SITE_PKGS
    unzip -q ../site-packages.zip
    rm ../site-packages.zip
    mkdir $RSRC/python
    ln -s ../lib/python2.7/site-packages/nodebox $RSRC/python/nodebox
    cp -p ../lib-dynload/*.so $RSRC/python
    cd $TOP
    ditto nodebox $SITE_PKGS/nodebox
    ditto examples $RSRC/examples
    mkdir $RSRC/English.lproj
    mv $RSRC/*.nib $RSRC/English.lproj/
    mv $RSRC/NodeBox\ Help $RSRC/English.lproj/NodeBox\ Help
    rmdir $RSRC/../Frameworks
    echo "done building NodeBox.app in ./dist"
}

dist () {
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

