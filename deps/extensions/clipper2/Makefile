CXX := clang++
ARCHES := -arch arm64 -arch x86_64
CXXFLAGS := -std=c++17 -O2 $(ARCHES) -Ivendor

.PHONY: all clean
all: clipper.engine.o bridge.o

clipper.engine.o: vendor/clipper.engine.cpp vendor/clipper2/clipper.core.h vendor/clipper2/clipper.engine.h vendor/clipper2/clipper.h
	$(CXX) $(CXXFLAGS) -c vendor/clipper.engine.cpp -o $@

bridge.o: bridge.cpp bridge.h vendor/clipper2/clipper.core.h vendor/clipper2/clipper.engine.h
	$(CXX) $(CXXFLAGS) -c bridge.cpp -o $@

clean:
	rm -f *.o
