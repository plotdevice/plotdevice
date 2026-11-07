REPO := https://github.com/swhitty/SwiftDraw.git
TAG := 0.21.0
SWIFT_BUILD := swift build --package-path SwiftDraw -c release --arch arm64 --arch x86_64
.PHONY: all clean distclean

all: SwiftDraw.o
	@:

# re-copy the glue & manifest on every build
SwiftDraw.o: SwiftDraw PDSVGImageRep.swift Package.swift.tmpl
	cp PDSVGImageRep.swift SwiftDraw/SwiftDraw
	cp Package.swift.tmpl SwiftDraw/Package.swift
	$(SWIFT_BUILD) --target SwiftDraw
	cp "$$($(SWIFT_BUILD) --show-bin-path)"/SwiftDraw*.o $@

SwiftDraw:
	git clone --depth 1 --branch $(TAG) $(REPO)
	rm -r SwiftDraw/CommandLine
	rm -r SwiftDraw/SwiftDrawTests
	rm -r SwiftDraw/Examples
	rm SwiftDraw/SwiftDraw/SVGView.swift
	rm -r SwiftDraw/*.*

# only distclean removes the SwiftDraw checkout
clean:
	rm -rf SwiftDraw/.build
	rm -f *.o

distclean: clean
	rm -rf SwiftDraw