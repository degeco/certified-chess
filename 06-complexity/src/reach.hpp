#pragma once

#include "common.hpp"
#include <chrono>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <string>
#include <vector>

namespace complexity {

struct Key16 {
    uint64_t w[2]{};
    bool operator==(const Key16& o) const { return w[0] == o.w[0] && w[1] == o.w[1]; }
    uint64_t hash() const { return splitmix64(w[0] ^ splitmix64(w[1])); }
};

struct Key24 {
    uint64_t w[3]{};
    bool operator==(const Key24& o) const {
        return w[0] == o.w[0] && w[1] == o.w[1] && w[2] == o.w[2];
    }
    uint64_t hash() const { return splitmix64(w[0] ^ splitmix64(w[1] ^ splitmix64(w[2]))); }
};

struct Key36 {
    uint32_t w[9]{};
    bool operator==(const Key36& o) const { return std::memcmp(w, o.w, sizeof(w)) == 0; }
    uint64_t hash() const {
        uint64_t a = (static_cast<uint64_t>(w[1]) << 32) | w[0];
        uint64_t b = (static_cast<uint64_t>(w[3]) << 32) | w[2];
        uint64_t c = (static_cast<uint64_t>(w[5]) << 32) | w[4];
        uint64_t d = (static_cast<uint64_t>(w[7]) << 32) | w[6];
        return splitmix64(a ^ splitmix64(b ^ splitmix64(c ^ splitmix64(d ^ w[8]))));
    }
};

template <typename KeyT>
inline void set_nibble(KeyT& k, int idx, uint8_t val) {
    if constexpr (std::is_same_v<KeyT, Key36>) {
        int word = idx >> 3;
        int shift = (idx & 7) * 4;
        k.w[word] |= (static_cast<uint32_t>(val) << shift);
    } else {
        int word = idx >> 4;
        int shift = (idx & 15) * 4;
        k.w[word] |= (static_cast<uint64_t>(val) << shift);
    }
}

template <typename KeyT>
inline uint8_t get_nibble(const KeyT& k, int idx) {
    if constexpr (std::is_same_v<KeyT, Key36>) {
        int word = idx >> 3;
        int shift = (idx & 7) * 4;
        return static_cast<uint8_t>((k.w[word] >> shift) & 0xFU);
    } else {
        int word = idx >> 4;
        int shift = (idx & 15) * 4;
        return static_cast<uint8_t>((k.w[word] >> shift) & 0xFU);
    }
}

template <typename KeyT>
inline KeyT pack_position(const mchess::Position& pos) {
    KeyT k{};
    int w = pos.width();
    int h = pos.height();
    for (int r = 0; r < h; ++r) {
        for (int f = 0; f < w; ++f) {
            mchess::Color c = mchess::WHITE;
            mchess::PieceType pt = pos.piece_at(mchess::make_sq(f, r), &c);
            uint8_t code = encode_cell(pt, c);
            if (code != 0) {
                set_nibble(k, r * w + f, code);
            }
        }
    }
    if constexpr (std::is_same_v<KeyT, Key36>) {
        uint32_t ep_enc = (pos.ep_square() == mchess::NO_SQ) ? 64U : static_cast<uint32_t>(pos.ep_square());
        uint32_t meta = static_cast<uint32_t>(pos.side_to_move()) |
                        (static_cast<uint32_t>(pos.castling_rights()) << 1) |
                        (ep_enc << 5);
        k.w[8] = meta;
    } else {
        int stm_bit = w * h * 4;
        if (pos.side_to_move() == mchess::BLACK) {
            k.w[stm_bit >> 6] |= (1ULL << (stm_bit & 63));
        }
    }
    return k;
}

template <typename KeyT>
inline bool unpack_position(const KeyT& k, int w, int h, mchess::Position& out) {
    uint8_t codes[64]{};
    int n = w * h;
    for (int i = 0; i < n; ++i) {
        codes[i] = get_nibble(k, i);
    }
    mchess::Color stm = mchess::WHITE;
    uint8_t castling = 0;
    int ep_sq = mchess::NO_SQ;
    if constexpr (std::is_same_v<KeyT, Key36>) {
        uint32_t meta = k.w[8];
        stm = (meta & 1U) ? mchess::BLACK : mchess::WHITE;
        castling = static_cast<uint8_t>((meta >> 1) & 0xFU);
        uint32_t ep_enc = (meta >> 5) & 0x7FU;
        ep_sq = (ep_enc == 64U) ? mchess::NO_SQ : static_cast<int>(ep_enc);
    } else {
        int stm_bit = n * 4;
        stm = ((k.w[stm_bit >> 6] >> (stm_bit & 63)) & 1ULL) ? mchess::BLACK : mchess::WHITE;
    }
    std::string fen = codes_to_fen(codes, w, h, stm, castling, ep_sq);
    return mchess::Position::parse(fen, out);
}

struct DepthStats {
    int depth = 0;
    uint64_t count = 0;
    uint64_t cumulative = 0;
    uint64_t checkmates = 0;
    uint64_t stalemates = 0;
    bool complete = true;
};

struct ReachResult {
    std::string start_fen;
    int width = 0;
    int height = 0;
    bool complete = false;
    int max_complete_depth = -1;
    std::string stop_reason;
    uint64_t total_positions = 0;
    uint64_t total_checkmates = 0;
    uint64_t total_stalemates = 0;
    uint64_t peak_mem_bytes = 0;
    double elapsed_sec = 0.0;
    std::vector<DepthStats> depths;
};

struct ReachOptions {
    uint64_t max_mem_bytes = 3500ULL * 1024ULL * 1024ULL; // 3500 MB (< 4 GB limit)
    double max_sec = 240.0;                               // 4 min (< 5 min limit)
    uint64_t max_nodes = std::numeric_limits<uint64_t>::max();
    int max_depth = 1000;
};

namespace detail {

template <typename KeyT>
class ChunkedBfsSet {
public:
    static constexpr size_t CHUNK_ELEMS = 262144; // 2^18 items per chunk (~4-9 MB)
    static constexpr uint32_t EMPTY = std::numeric_limits<uint32_t>::max();

    explicit ChunkedBfsSet(uint64_t max_mem_bytes) : max_mem_bytes_(max_mem_bytes) {
        size_t init_cap = 1 << 14;
        table_.assign(init_cap, EMPTY);
        mask_ = init_cap - 1;
        update_peak();
    }

    size_t size() const { return size_; }
    uint64_t peak_mem_bytes() const { return peak_mem_bytes_; }

    uint64_t current_mem_bytes() const {
        return chunks_.size() * (CHUNK_ELEMS * sizeof(KeyT)) +
               table_.size() * sizeof(uint32_t);
    }

    const KeyT& operator[](size_t idx) const {
        return (*chunks_[idx / CHUNK_ELEMS])[idx % CHUNK_ELEMS];
    }

    // Returns 1 if inserted, 0 if duplicate, -1 if memory limit would be exceeded.
    int insert(const KeyT& key) {
        uint64_t h = key.hash();
        size_t pos = static_cast<size_t>(h) & mask_;
        while (true) {
            uint32_t idx = table_[pos];
            if (idx == EMPTY) break;
            if ((*this)[idx] == key) return 0;
            pos = (pos + 1) & mask_;
        }

        // Check if we need to rehash before inserting.
        if ((size_ + 1) * 100ULL >= table_.size() * 68ULL) {
            if (!rehash(table_.size() * 2)) return -1;
            // Re-find empty slot after rehash.
            pos = static_cast<size_t>(h) & mask_;
            while (table_[pos] != EMPTY) {
                pos = (pos + 1) & mask_;
            }
        }

        // Check if we need a new chunk.
        size_t chunk_idx = size_ / CHUNK_ELEMS;
        if (chunk_idx >= chunks_.size()) {
            uint64_t projected = current_mem_bytes() + CHUNK_ELEMS * sizeof(KeyT);
            if (projected > max_mem_bytes_) return -1;
            chunks_.push_back(std::make_unique<std::array<KeyT, CHUNK_ELEMS>>());
            update_peak();
        }

        uint32_t new_idx = static_cast<uint32_t>(size_);
        (*chunks_[chunk_idx])[size_ % CHUNK_ELEMS] = key;
        table_[pos] = new_idx;
        ++size_;
        return 1;
    }

private:
    bool rehash(size_t new_cap) {
        // Account for both old and new tables being live simultaneously during rehash.
        uint64_t new_table_bytes = new_cap * sizeof(uint32_t);
        if (current_mem_bytes() + new_table_bytes > max_mem_bytes_) {
            return false;
        }
        std::vector<uint32_t> new_table(new_cap, EMPTY);
        size_t new_mask = new_cap - 1;
        for (size_t i = 0; i < size_; ++i) {
            size_t p = static_cast<size_t>((*this)[i].hash()) & new_mask;
            while (new_table[p] != EMPTY) {
                p = (p + 1) & new_mask;
            }
            new_table[p] = static_cast<uint32_t>(i);
        }
        uint64_t peak_during = current_mem_bytes() + new_table_bytes;
        if (peak_during > peak_mem_bytes_) peak_mem_bytes_ = peak_during;
        table_.swap(new_table);
        mask_ = new_mask;
        return true;
    }

    void update_peak() {
        uint64_t cur = current_mem_bytes();
        if (cur > peak_mem_bytes_) peak_mem_bytes_ = cur;
    }

    uint64_t max_mem_bytes_;
    std::vector<std::unique_ptr<std::array<KeyT, CHUNK_ELEMS>>> chunks_;
    std::vector<uint32_t> table_;
    size_t mask_ = 0;
    size_t size_ = 0;
    uint64_t peak_mem_bytes_ = 0;
};

template <typename KeyT>
ReachResult run_reach_typed(const mchess::Position& root, const std::string& start_fen,
                            const ReachOptions& opts) {
    using clock = std::chrono::steady_clock;
    auto t0 = clock::now();

    ReachResult res;
    res.start_fen = start_fen;
    res.width = root.width();
    res.height = root.height();

    ChunkedBfsSet<KeyT> visited(opts.max_mem_bytes);
    KeyT rk = pack_position<KeyT>(root);
    if (visited.insert(rk) != 1) {
        res.stop_reason = "memory_limit";
        return res;
    }

    size_t level_start = 0;
    size_t level_end = 1;
    int depth = 0;
    mchess::Move move_buf[mchess::MAX_MOVES];

    while (level_start < level_end) {
        if (depth >= opts.max_depth) {
            DepthStats ds;
            ds.depth = depth;
            ds.count = level_end - level_start;
            ds.cumulative = level_end;
            ds.complete = true;
            res.depths.push_back(ds);
            res.max_complete_depth = depth;
            res.stop_reason = "depth_limit";
            break;
        }

        uint64_t level_checkmates = 0;
        uint64_t level_stalemates = 0;
        bool stopped = false;

        for (size_t idx = level_start; idx < level_end; ++idx) {
            if ((idx & 4095ULL) == 0ULL) {
                double elapsed = std::chrono::duration<double>(clock::now() - t0).count();
                if (elapsed >= opts.max_sec) {
                    res.stop_reason = "time_limit";
                    stopped = true;
                    break;
                }
            }

            mchess::Position pos;
            if (!unpack_position(visited[idx], res.width, res.height, pos)) {
                res.stop_reason = "internal_unpack_error";
                stopped = true;
                break;
            }

            int n = pos.legal_moves(move_buf);
            if (n == 0) {
                if (pos.in_check()) ++level_checkmates;
                else ++level_stalemates;
                continue;
            }

            for (int i = 0; i < n; ++i) {
                if (visited.size() >= opts.max_nodes) {
                    res.stop_reason = "node_limit";
                    stopped = true;
                    break;
                }
                mchess::Position next = pos.make_move(move_buf[i]);
                KeyT nk = pack_position<KeyT>(next);
                int ins = visited.insert(nk);
                if (ins < 0) {
                    res.stop_reason = "memory_limit";
                    stopped = true;
                    break;
                }
            }
            if (stopped) break;
        }

        // Depth `depth` itself has all its nodes discovered; what may stop is expanding
        // depth `depth` to discover depth `depth + 1`.
        DepthStats ds;
        ds.depth = depth;
        ds.count = level_end - level_start;
        ds.cumulative = level_end;
        ds.checkmates = stopped ? 0 : level_checkmates;
        ds.stalemates = stopped ? 0 : level_stalemates;
        ds.complete = true;
        res.depths.push_back(ds);
        res.max_complete_depth = depth;

        if (!stopped) {
            res.total_checkmates += level_checkmates;
            res.total_stalemates += level_stalemates;
        } else {
            // Also record partially discovered nodes at depth + 1 if any.
            if (visited.size() > level_end) {
                DepthStats pds;
                pds.depth = depth + 1;
                pds.count = visited.size() - level_end;
                pds.cumulative = visited.size();
                pds.complete = false;
                res.depths.push_back(pds);
            }
            break;
        }

        level_start = level_end;
        level_end = visited.size();
        ++depth;
    }

    if (res.stop_reason.empty()) {
        res.complete = true;
        res.stop_reason = "complete";
    }
    res.total_positions = visited.size();
    res.peak_mem_bytes = visited.peak_mem_bytes();
    res.elapsed_sec = std::chrono::duration<double>(clock::now() - t0).count();
    return res;
}

} // namespace detail

inline ReachResult run_reach(const std::string& start_fen, const ReachOptions& opts) {
    auto root = mchess::Position::from_fen(start_fen);
    if (!root) {
        ReachResult err;
        err.start_fen = start_fen;
        err.stop_reason = "invalid_fen";
        return err;
    }
    std::string canon = root->to_fen();
    int sqs = root->width() * root->height();
    if (!root->is_8x8() && sqs <= 31) {
        return detail::run_reach_typed<Key16>(*root, canon, opts);
    } else if (!root->is_8x8() && sqs <= 47) {
        return detail::run_reach_typed<Key24>(*root, canon, opts);
    } else {
        return detail::run_reach_typed<Key36>(*root, canon, opts);
    }
}

} // namespace complexity
