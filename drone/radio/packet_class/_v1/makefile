# COMPILER, FLAGS, TARGET, AND DEPENDENCIES
CXX = g++
CXXFLAGS = -shared -fPIC -std=c++11
TARGET = packet.so
SOURCES = packet_wrap.cpp packet.h

# This is our default target . . . 
all: $(TARGET)

# Create our shared library (for Thermal.py)
$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $@ $^

# CLEAN THAT SHIT!
# (-f flag will avoid errors should the target not exist)
clean:
	rm -f $(TARGET)
