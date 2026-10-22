REPO := https://github.com/swhitty/SwiftDraw.git
TAG := 0.21.0
.PHONY: all clean distclean

all: SwiftDraw.o
	@:

SwiftDraw.o: SwiftDraw PDSVGImageRep.swift Package.swift.tmpl
	cp PDSVGImageRep.swift SwiftDraw/SwiftDraw
	cp Package.swift.tmpl SwiftDraw/Package.swift
	cd SwiftDraw && swift build -c release --target SwiftDraw --arch arm64 --arch x86_64
	cp SwiftDraw/.build/apple/Products/Release/SwiftDraw*.o $@

SwiftDraw:
	git clone --depth 1 --branch $(TAG) $(REPO)
	rm -r SwiftDraw/CommandLine
	rm -r SwiftDraw/SwiftDrawTests
	rm -r SwiftDraw/Examples
	rm SwiftDraw/SwiftDraw/SVGView.swift
	rm -r SwiftDraw/*.*

clean:
	rm -rf SwiftDraw/.build
	rm -f *.o

distclean: clean
	rm -rf SwiftDraw