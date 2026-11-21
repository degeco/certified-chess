CXX := g++
CXXFLAGS := -O3 -std=c++17 -Wall -Wextra -Wpedantic -I../02-engine/src -I../04-tablebase/src
TB_CXXFLAGS := -O3 -std=c++17 -Wall -Wextra -I../02-engine/src -I../04-tablebase/src
ENGINE_LIB := ../02-engine/build/libmchess.a
TB_SRC_DIR := ../04-tablebase/src

SRC_DIR := src
BUILD_DIR := build
TEST_DIR := tests

HEADERS := $(SRC_DIR)/common.hpp $(SRC_DIR)/certificate.hpp $(SRC_DIR)/tb_probe.hpp $(SRC_DIR)/dfpn.hpp $(SRC_DIR)/draw_solver.hpp
CORE_SRCS := $(SRC_DIR)/certificate.cpp $(SRC_DIR)/tb_probe.cpp $(SRC_DIR)/dfpn.cpp $(SRC_DIR)/draw_solver.cpp
CORE_OBJS := $(patsubst $(SRC_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(CORE_SRCS))
TB_OBJS := $(BUILD_DIR)/tb_signature.o $(BUILD_DIR)/tb_indexer.o $(BUILD_DIR)/tb_tablebase.o

.PHONY: all test clean

all: msolve

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/tb_signature.o: $(TB_SRC_DIR)/signature.cpp $(TB_SRC_DIR)/signature.hpp | $(BUILD_DIR)
	$(CXX) $(TB_CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/tb_indexer.o: $(TB_SRC_DIR)/indexer.cpp $(TB_SRC_DIR)/indexer.hpp $(TB_SRC_DIR)/signature.hpp | $(BUILD_DIR)
	$(CXX) $(TB_CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/tb_tablebase.o: $(TB_SRC_DIR)/tablebase.cpp $(TB_SRC_DIR)/tablebase.hpp $(TB_SRC_DIR)/indexer.hpp $(TB_SRC_DIR)/signature.hpp | $(BUILD_DIR)
	$(CXX) $(TB_CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp $(HEADERS) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

msolve: $(CORE_OBJS) $(TB_OBJS) $(BUILD_DIR)/main.o $(ENGINE_LIB)
	$(CXX) $(CXXFLAGS) $(CORE_OBJS) $(TB_OBJS) $(BUILD_DIR)/main.o $(ENGINE_LIB) -o $@

$(BUILD_DIR)/main.o: $(SRC_DIR)/main.cpp $(HEADERS) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/test_solver: $(CORE_OBJS) $(TB_OBJS) $(TEST_DIR)/test_solver.cpp $(ENGINE_LIB) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(CORE_OBJS) $(TB_OBJS) $(TEST_DIR)/test_solver.cpp $(ENGINE_LIB) -o $@

test: msolve $(BUILD_DIR)/test_solver
	./$(BUILD_DIR)/test_solver
	python3 $(TEST_DIR)/verify_all.py

clean:
	rm -rf $(BUILD_DIR) msolve
