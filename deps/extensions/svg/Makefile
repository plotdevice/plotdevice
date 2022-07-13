REPO := https://github.com/swhitty/SwiftDraw.git
TAG := 0.9.3
.PHONY: all

all: SwiftDraw.o
	@:

SwiftDraw.o: SwiftDraw
	cd SwiftDraw && swift build -c release --target SwiftDraw --arch arm64 --arch x86_64
	cp SwiftDraw/.build/apple/Products/Release/SwiftDraw.o .

SwiftDraw:
	git clone --depth 1 --branch $(TAG) $(REPO)
	rm -r SwiftDraw/CommandLine
	rm -r SwiftDraw/SwiftDrawTests
	rm -r SwiftDraw/Examples
	rm SwiftDraw/*.*

	cp NSImage+PlotDevice.swift SwiftDraw/SwiftDraw
	cp Package.swift SwiftDraw/

clean:
	rm -rf SwiftDraw
	rm -f *.o