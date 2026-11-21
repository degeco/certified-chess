CXX := g++
CXXFLAGS := -O3 -std=c++17 -Wall -Wextra -Wpedantic -I../02-engine/src
ENGINE_LIB := ../02-engine/build/libmchess.a

SRC_DIR := src
BUILD_DIR := build
TEST_DIR := tests

CORE_SRCS := $(SRC_DIR)/certificate.cpp $(SRC_DIR)/dfpn.cpp $(SRC_DIR)/draw_solver.cpp
CORE_OBJS := $(patsubst $(SRC_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(CORE_SRCS))

.PHONY: all test clean

all: msolve

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp $(SRC_DIR)/common.hpp $(SRC_DIR)/certificate.hpp $(SRC_DIR)/dfpn.hpp $(SRC_DIR)/draw_solver.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

msolve: $(CORE_OBJS) $(BUILD_DIR)/main.o $(ENGINE_LIB)
	$(CXX) $(CXXFLAGS) $(CORE_OBJS) $(BUILD_DIR)/main.o $(ENGINE_LIB) -o $@

$(BUILD_DIR)/main.o: $(SRC_DIR)/main.cpp $(SRC_DIR)/common.hpp $(SRC_DIR)/certificate.hpp $(SRC_DIR)/dfpn.hpp $(SRC_DIR)/draw_solver.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/test_solver: $(CORE_OBJS) $(TEST_DIR)/test_solver.cpp $(ENGINE_LIB) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CORE_OBJS) $(TEST_DIR)/test_solver.cpp $(ENGINE_LIB) -o $@

test: msolve $(BUILD_DIR)/test_solver
	./$(BUILD_DIR)/test_solver
	python3 $(TEST_DIR)/verify_all.py

clean:
	rm -rf $(BUILD_DIR) msolve
