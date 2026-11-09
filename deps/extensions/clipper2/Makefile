CXX := clang++
ARCHES := -arch arm64 -arch x86_64
CXXFLAGS := -std=c++17 -O2 $(ARCHES) -mmacosx-version-min=11.0 -Ivendor

.PHONY: all clean
all: clipper.engine.o clipper.offset.o bridge.o

clipper.engine.o: Makefile vendor/clipper.engine.cpp vendor/clipper2/clipper.core.h vendor/clipper2/clipper.engine.h vendor/clipper2/clipper.h
	$(CXX) $(CXXFLAGS) -c vendor/clipper.engine.cpp -o $@

clipper.offset.o: Makefile vendor/clipper.offset.cpp vendor/clipper2/clipper.h vendor/clipper2/clipper.offset.h
	$(CXX) $(CXXFLAGS) -c vendor/clipper.offset.cpp -o $@

bridge.o: Makefile bridge.cpp bridge.h vendor/clipper2/clipper.core.h vendor/clipper2/clipper.engine.h vendor/clipper2/clipper.h
	$(CXX) $(CXXFLAGS) -c bridge.cpp -o $@

clean:
	rm -f *.o
