CXX      := g++
CXXFLAGS := -O2 -std=c++17 -Wall -Wextra

SRC_DIR   := src
BUILD_DIR := build
BIN_DIR   := bin
TEST_DIR  := tests

LIB_SRCS  := $(SRC_DIR)/attacks.cpp $(SRC_DIR)/position.cpp
LIB_OBJS  := $(BUILD_DIR)/attacks.o $(BUILD_DIR)/position.o
LIB_A     := $(BUILD_DIR)/libmchess.a

CLI_OBJ   := $(BUILD_DIR)/main.o
TARGET    := $(BIN_DIR)/mchess
TEST_BIN  := $(BUILD_DIR)/test_mchess

.PHONY: all test clean

all: $(TARGET)

$(BUILD_DIR) $(BIN_DIR):
	mkdir -p $@

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -c $< -o $@

$(LIB_A): $(LIB_OBJS)
	ar rcs $@ $^

$(TARGET): $(CLI_OBJ) $(LIB_A) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $(CLI_OBJ) $(LIB_A) -o $@

$(TEST_BIN): $(TEST_DIR)/test_main.cpp $(LIB_A) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) $< $(LIB_A) -o $@

test: $(TEST_BIN) $(TARGET)
	./$(TEST_BIN)

clean:
	rm -rf $(BUILD_DIR) $(BIN_DIR)
