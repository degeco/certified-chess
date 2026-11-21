CXX      := g++
CXXFLAGS := -O2 -std=c++17 -Wall -Wextra -pthread

ENGINE_DIR := ../02-engine
ENGINE_INC := -I$(ENGINE_DIR)/src
ENGINE_LIB := $(ENGINE_DIR)/build/libmchess.a

SRC_DIR   := src
BUILD_DIR := build
BIN_DIR   := bin
TEST_DIR  := tests

LIB_SRCS  := $(SRC_DIR)/signature.cpp $(SRC_DIR)/indexer.cpp $(SRC_DIR)/tablebase.cpp
LIB_OBJS  := $(BUILD_DIR)/signature.o $(BUILD_DIR)/indexer.o $(BUILD_DIR)/tablebase.o

TARGET    := $(BIN_DIR)/tbgen
TEST_BIN  := $(BUILD_DIR)/test_tbgen

.PHONY: all test clean

all: $(TARGET)

$(BUILD_DIR) $(BIN_DIR):
	mkdir -p $@

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp $(SRC_DIR)/*.hpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(ENGINE_INC) -c $< -o $@

$(TARGET): $(BUILD_DIR)/main.o $(LIB_OBJS) $(ENGINE_LIB) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $(BUILD_DIR)/main.o $(LIB_OBJS) $(ENGINE_LIB) -o $@

$(TEST_BIN): $(TEST_DIR)/test_tbgen.cpp $(LIB_OBJS) $(ENGINE_LIB) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(ENGINE_INC) -I$(SRC_DIR) $< $(LIB_OBJS) $(ENGINE_LIB) -o $@

test: $(TEST_BIN) $(TARGET)
	./$(TEST_BIN)

clean:
	rm -rf $(BUILD_DIR) $(BIN_DIR)
