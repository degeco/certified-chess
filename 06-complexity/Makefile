CXX      := g++
CXXFLAGS := -O2 -std=c++17 -Wall -Wextra -I../02-engine/src
LIBMCHESS := ../02-engine/build/libmchess.a

BIN_DIR := bin

.PHONY: all test estimates reach-mini4x4 reach-mini4x5 reach-mini5x5 reach-6x6 reach-std8 clean

all: $(BIN_DIR)/reach $(BIN_DIR)/estimate $(BIN_DIR)/validate

$(BIN_DIR):
	mkdir -p $@

$(BIN_DIR)/reach: src/reach.cpp src/reach.hpp src/common.hpp $(LIBMCHESS) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< $(LIBMCHESS) -o $@

$(BIN_DIR)/estimate: src/estimate.cpp src/estimate.hpp src/common.hpp $(LIBMCHESS) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< $(LIBMCHESS) -o $@

$(BIN_DIR)/validate: src/validate.cpp src/reach.hpp src/estimate.hpp src/common.hpp $(LIBMCHESS) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< $(LIBMCHESS) -o $@

test: $(BIN_DIR)/validate
	./$(BIN_DIR)/validate

estimates: all
	python3 scripts/run_all.py --mode estimate

reach-mini4x4: $(BIN_DIR)/reach
	./$(BIN_DIR)/reach mini4x4 --max-mem-mb 3500 --max-sec 180

reach-mini4x5: $(BIN_DIR)/reach
	./$(BIN_DIR)/reach mini4x5 --max-mem-mb 3500 --max-sec 180

reach-mini5x5: $(BIN_DIR)/reach
	./$(BIN_DIR)/reach mini5x5 --max-mem-mb 3500 --max-sec 180

reach-6x6: $(BIN_DIR)/reach
	./$(BIN_DIR)/reach losalamos6x6 --max-mem-mb 3500 --max-sec 180

reach-std8: $(BIN_DIR)/reach
	./$(BIN_DIR)/reach std8 --max-mem-mb 3500 --max-sec 180

clean:
	rm -rf $(BIN_DIR)
