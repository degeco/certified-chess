#include "dfpn.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <queue>
#include <unordered_set>

namespace msolve {

namespace {
constexpr int MAX_DFPN_DEPTH = 240;
constexpr int NO_CYCLE = 1000000;
} // namespace

uint64_t DfpnSolver::isqrt64(uint64_t n) {
    if (n <= 1ULL) return n;
    uint64_t x = static_cast<uint64_t>(std::sqrt(static_cast<long double>(n)));
    while ((x + 1ULL) <= n / (x + 1ULL)) ++x;
    while (x > n / x) --x;
    return x;
}

uint64_t DfpnSolver::dag_aggregate(uint64_t sum, uint64_t max_v, uint32_t k_pos) const {
    if (sum >= INF || max_v >= INF) return INF;
    if (k_pos == 0 || max_v == 0) return 0;
    if (k_pos == 1) return max_v;

    uint64_t rem = (sum > max_v) ? (sum - max_v) : 0ULL;
    switch (limits_.dag_mode) {
        case DagMode::SUM:
        case DagMode::SNDA:
            return std::min(sum, MAX_FINITE);
        case DagMode::SQRT:
            return sat_add(max_v, isqrt64(rem));
        case DagMode::DAMPED:
            return sat_add(max_v, rem >> 2);
        case DagMode::MAX_PLUS:
            return sat_add(max_v, static_cast<uint64_t>(k_pos - 1));
    }
    return std::min(sum, MAX_FINITE);
}

uint64_t DfpnSolver::dag_child_threshold(uint64_t th,
                                         uint64_t best_v,
                                         uint64_t max_other,
                                         uint64_t sum_other,
                                         uint32_t k_pos_other) const {
    if (th >= INF) return INF;
    if (k_pos_other == 0) return std::max<uint64_t>(best_v + 1ULL, th);

    uint64_t x = th;
    switch (limits_.dag_mode) {
        case DagMode::SUM:
        case DagMode::SNDA: {
            x = sat_sub(th, sum_other);
            break;
        }
        case DagMode::MAX_PLUS: {
            x = sat_sub(th, static_cast<uint64_t>(k_pos_other));
            break;
        }
        case DagMode::DAMPED: {
            uint64_t rem_other = (sum_other > max_other) ? (sum_other - max_other) : 0ULL;
            x = std::max(max_other, sat_sub(th, sum_other >> 2));
            if (th > max_other) {
                uint64_t delta = th - max_other;
                if (delta <= (INF >> 3)) {
                    uint64_t need = delta << 2;
                    if (need > rem_other) {
                        uint64_t x_low = need - rem_other;
                        if (x_low < max_other) {
                            x = x_low;
                        }
                    }
                }
            }
            break;
        }
        case DagMode::SQRT: {
            uint64_t rem_other = (sum_other > max_other) ? (sum_other - max_other) : 0ULL;
            uint64_t sq_s = isqrt64(sum_other);
            x = std::max(max_other, sat_sub(th, sq_s));
            if (th > max_other) {
                uint64_t delta = th - max_other;
                if (delta < (1ULL << 31)) {
                    uint64_t need = delta * delta;
                    if (need > rem_other) {
                        uint64_t x_low = need - rem_other;
                        if (x_low < max_other) {
                            x = x_low;
                        }
                    }
                }
            }
            break;
        }
    }

    if (x <= best_v) x = best_v + 1ULL;
    if (x > th) x = th;
    return x;
}

DfpnSolver::DfpnSolver(size_t tt_mb, const TablebaseProbe* tb) : tb_probe_(tb) {
    if (tt_mb < 1) tt_mb = 1;
    if (tt_mb > 3072) tt_mb = 3072;
    size_t bytes = tt_mb * 1024ULL * 1024ULL;
    size_t target_buckets = bytes / sizeof(TTBucket);
    size_t nb = 1024;
    while ((nb << 1) <= target_buckets) {
        nb <<= 1;
    }
    tt_.assign(nb, TTBucket{});
    tt_mask_ = nb - 1;
    // Cap proof move cache proportionally (~15% of tt_mb, min 50k entries, max 2M entries)
    max_proof_moves_ = std::clamp<size_t>((tt_mb * 1024ULL * 1024ULL) / 160ULL, 50000ULL, 2000000ULL);
}

void DfpnSolver::clear() {
    std::fill(tt_.begin(), tt_.end(), TTBucket{});
    proof_moves_.clear();
    disproof_moves_.clear();
}

const DfpnSolver::TTEntry* DfpnSolver::tt_lookup(uint64_t hash) const {
    uint64_t k = norm_key(hash);
    const TTBucket& b = tt_[hash & tt_mask_];
    for (int i = 0; i < 4; ++i) {
        if (b.slots[i].key == k) {
            return &b.slots[i];
        }
    }
    return nullptr;
}

void DfpnSolver::tt_store(uint64_t hash, uint64_t pn, uint64_t dn,
                          uint32_t pn_sig, uint32_t dn_sig,
                          uint16_t best_move, uint16_t rank, uint32_t work) {
    uint64_t k = norm_key(hash);
    TTBucket& b = tt_[hash & tt_mask_];
    const bool new_solved = (pn == 0 || dn == 0);

    // 1. Update existing entry if present.
    for (int i = 0; i < 4; ++i) {
        TTEntry& e = b.slots[i];
        if (e.key == k) {
            bool old_solved = (e.pn == 0 || e.dn == 0);
            if (old_solved && !new_solved) {
                return; // never downgrade solved entry to unsolved
            }
            if (e.pn == 0 && pn == 0) {
                if (rank > 0 && (e.rank == 0 || rank < e.rank)) {
                    e.rank = rank;
                    if (best_move) e.best_move = best_move;
                } else if (!e.best_move && best_move) {
                    e.best_move = best_move;
                }
                e.work = std::max(e.work, work);
                return;
            }
            e.pn = pn;
            e.dn = dn;
            if (pn_sig) e.pn_sig = pn_sig;
            if (dn_sig) e.dn_sig = dn_sig;
            if (best_move) e.best_move = best_move;
            if (rank) e.rank = rank;
            e.work = std::max(e.work, work);
            return;
        }
    }

    // 2. Empty slot?
    for (int i = 0; i < 4; ++i) {
        if (b.slots[i].key == 0) {
            b.slots[i] = TTEntry{k, pn, dn, pn_sig, dn_sig, best_move, rank, work};
            return;
        }
    }

    // 3. Replacement policy:
    // Slots 0..2 prefer keeping solved and high-work entries; slot 3 is scratch fallback.
    int victim = -1;
    uint32_t min_work = std::numeric_limits<uint32_t>::max();

    if (!new_solved) {
        for (int i = 0; i < 4; ++i) {
            const TTEntry& e = b.slots[i];
            if (e.pn > 0 && e.dn > 0 && e.work < min_work) {
                min_work = e.work;
                victim = i;
            }
        }
        if (victim < 0) {
            victim = 3;
            for (int i = 0; i < 4; ++i) {
                if (b.slots[i].dn == 0) {
                    victim = i;
                    break;
                }
            }
        }
    } else {
        for (int i = 0; i < 4; ++i) {
            const TTEntry& e = b.slots[i];
            if (e.pn > 0 && e.dn > 0 && e.work < min_work) {
                min_work = e.work;
                victim = i;
            }
        }
        if (victim < 0) {
            for (int i = 0; i < 4; ++i) {
                const TTEntry& e = b.slots[i];
                if (e.dn == 0 && e.work < min_work) {
                    min_work = e.work;
                    victim = i;
                }
            }
            if (victim < 0) {
                for (int i = 0; i < 4; ++i) {
                    if (b.slots[i].work < min_work) {
                        min_work = b.slots[i].work;
                        victim = i;
                    }
                }
            }
        }
    }

    if (victim < 0) victim = 3;
    b.slots[victim] = TTEntry{k, pn, dn, pn_sig, dn_sig, best_move, rank, work};
}

bool DfpnSolver::check_limits() {
    if (aborted_) return true;
    if (nodes_ >= limits_.max_nodes) {
        aborted_ = true;
        return true;
    }
    if ((nodes_ & 2047ULL) == 0) {
        if (timer_.elapsed() >= limits_.max_seconds) {
            aborted_ = true;
            return true;
        }
    }
    return false;
}

int DfpnSolver::find_on_path(const Position& pos) const {
    uint64_t h = pos.hash();
    if (path_bloom_[h & 2047ULL] == 0) return -1;
    for (int i = static_cast<int>(path_hash_.size()) - 1; i >= 0; --i) {
        if (path_hash_[i] == h && path_pos_[i] == pos) {
            return i;
        }
    }
    return -1;
}

bool DfpnSolver::probe_tb_for_win(const Position& pos,
                                  uint64_t& out_pn,
                                  uint64_t& out_dn,
                                  uint16_t& out_rank) {
    if (!tb_probe_ || !tb_probe_->is_loaded()) return false;
    tb::WDL wdl = tb::WDL_UNKNOWN;
    uint16_t dtm = 0;
    if (!tb_probe_->probe(pos, wdl, dtm)) return false;

    ++tb_hits_;
    const bool is_or = (pos.side_to_move() == prover_);
    if (is_or) {
        if (wdl == tb::WDL_WIN) {
            out_pn = 0;
            out_dn = INF;
            out_rank = static_cast<uint16_t>((dtm + 1U) / 2U);
            return true;
        }
        // WDL_DRAW or WDL_LOSS => prover cannot force a win!
        out_pn = INF;
        out_dn = 0;
        out_rank = 0;
        return true;
    } else {
        if (wdl == tb::WDL_LOSS) {
            // Opponent loses => prover wins!
            out_pn = 0;
            out_dn = INF;
            out_rank = static_cast<uint16_t>(dtm / 2U);
            return true;
        }
        // Opponent draws or wins => prover cannot force a win!
        out_pn = INF;
        out_dn = 0;
        out_rank = 0;
        return true;
    }
}

DfpnSolver::MidResult DfpnSolver::mid(const Position& pos, uint64_t thpn, uint64_t thdn, int depth) {
    MidResult res;
    if (check_limits()) {
        return res;
    }
    ++nodes_;
    uint64_t start_nodes = nodes_;

    // 1. Exact endgame tablebase probe (before TT so we never pollute TT with TB positions).
    {
        uint64_t tpn = 0, tdn = 0;
        uint16_t trk = 0;
        if (probe_tb_for_win(pos, tpn, tdn, trk)) {
            res.pn = tpn;
            res.dn = tdn;
            res.rank = trk;
            res.min_cycle_depth = NO_CYCLE;
            return res;
        }
    }

    // 2. Check external safe cycle targets (used only during draw-cert extraction fallback).
    if (safe_cycle_targets_ && pos.side_to_move() != prover_) {
        auto it = safe_cycle_targets_->find(pos.hash());
        if (it != safe_cycle_targets_->end()) {
            for (const Position& sp : it->second) {
                if (sp == pos) {
                    res.pn = INF;
                    res.dn = 0;
                    res.min_cycle_depth = 0;
                    return res;
                }
            }
        }
    }

    // 3. Check TT for already solved or threshold-exceeding entry.
    uint16_t tt_hint_move = 0;
    if (const TTEntry* te = tt_lookup(pos.hash())) {
        tt_hint_move = te->best_move;
        if (te->pn == 0 || te->dn == 0 || te->pn >= thpn || te->dn >= thdn) {
            res.pn = te->pn;
            res.dn = te->dn;
            res.pn_sig = te->pn_sig ? te->pn_sig : hash_sig(pos.hash());
            res.dn_sig = te->dn_sig ? te->dn_sig : hash_sig(pos.hash());
            res.best_move = te->best_move;
            res.rank = te->rank;
            res.min_cycle_depth = NO_CYCLE;
            return res;
        }
    }

    if (depth >= MAX_DFPN_DEPTH) {
        res.pn = INF;
        res.dn = 0;
        res.min_cycle_depth = -1;
        return res;
    }

    Move moves[MAX_MOVES];
    int nm = pos.legal_moves(moves);
    const bool is_or = (pos.side_to_move() == prover_);

    // Terminal positions
    if (nm == 0) {
        if (is_or) {
            tt_store(pos.hash(), INF, 0, 0, 0, 0, 0, 1);
            res.pn = INF;
            res.dn = 0;
            return res;
        } else {
            if (pos.in_check()) {
                tt_store(pos.hash(), 0, INF, 0, 0, 0, 0, 1);
                res.pn = 0;
                res.dn = INF;
                res.rank = 0;
                return res;
            } else {
                tt_store(pos.hash(), INF, 0, 0, 0, 0, 0, 1);
                res.pn = INF;
                res.dn = 0;
                return res;
            }
        }
    }

    // Generate all children once in heap arena and check immediate 1-ply terminal/TB wins/disproofs.
    size_t base = child_arena_.size();
    child_arena_.resize(base + static_cast<size_t>(nm));
    struct ArenaGuard {
        std::vector<ChildInfo>& arena;
        size_t sz;
        ~ArenaGuard() { arena.resize(sz); }
    } arena_guard{child_arena_, base};

    Move tmp_buf[MAX_MOVES];
    Move hint_mv{};
    if (tt_hint_move) hint_mv = unpack_move(tt_hint_move);

    for (int i = 0; i < nm; ++i) {
        ChildInfo& ci = child_arena_[base + i];
        ci.move = moves[i];
        ci.pos = pos.make_move(moves[i]);
        ci.rank = 0;
        ci.cyc_depth = NO_CYCLE;
        ci.order_score = move_order_score(pos, moves[i]);
        if (tt_hint_move && moves[i] == hint_mv) ci.order_score += 5000;

        const Position& cp = ci.pos;
        uint32_t csig = hash_sig(cp.hash());
        ci.pn_sig = csig;
        ci.dn_sig = csig;

        // Check tablebase on child immediately (resolves captures into <=4pc in 0 extra nodes!).
        {
            uint64_t tpn = 0, tdn = 0;
            uint16_t trk = 0;
            if (probe_tb_for_win(cp, tpn, tdn, trk)) {
                if (is_or && tpn == 0) {
                    uint16_t pm = pack_move(moves[i]);
                    uint16_t rk = static_cast<uint16_t>(std::min<uint32_t>(65534U, trk + 1U));
                    tt_store(pos.hash(), 0, INF, 0, 0, pm, rk, 1);
                    if (proof_moves_.size() < max_proof_moves_) {
                        proof_moves_[pos.hash()] = pm;
                    }
                    res.pn = 0;
                    res.dn = INF;
                    res.best_move = pm;
                    res.rank = rk;
                    res.min_cycle_depth = NO_CYCLE;
                    return res;
                }
                if (!is_or && tdn == 0) {
                    uint16_t dm = pack_move(moves[i]);
                    tt_store(pos.hash(), INF, 0, 0, 0, dm, 0, 1);
                    if (disproof_moves_.size() < max_proof_moves_) {
                        disproof_moves_[pos.hash()] = dm;
                    }
                    res.pn = INF;
                    res.dn = 0;
                    res.best_move = dm;
                    res.min_cycle_depth = NO_CYCLE;
                    return res;
                }
                ci.pn = tpn;
                ci.dn = tdn;
                ci.rank = trk;
                continue;
            }
        }

        const bool gives_check = cp.in_check();
        if (gives_check) ci.order_score += 2000;

        if (gives_check) {
            int cdeg = cp.legal_moves(tmp_buf);
            if (cdeg == 0) {
                if (is_or) {
                    uint16_t pm = pack_move(moves[i]);
                    tt_store(pos.hash(), 0, INF, 0, 0, pm, 1, 1);
                    if (proof_moves_.size() < max_proof_moves_) {
                        proof_moves_[pos.hash()] = pm;
                    }
                    res.pn = 0;
                    res.dn = INF;
                    res.best_move = pm;
                    res.rank = 1;
                    res.min_cycle_depth = NO_CYCLE;
                    return res;
                } else {
                    uint16_t dm = pack_move(moves[i]);
                    tt_store(pos.hash(), INF, 0, 0, 0, dm, 0, 1);
                    if (disproof_moves_.size() < max_proof_moves_) {
                        disproof_moves_[pos.hash()] = dm;
                    }
                    res.pn = INF;
                    res.dn = 0;
                    res.best_move = dm;
                    res.min_cycle_depth = NO_CYCLE;
                    return res;
                }
            }
            int cd = find_on_path(cp);
            if (cd >= 0) {
                ci.pn = INF;
                ci.dn = 0;
                ci.cyc_depth = cd;
            } else if (const TTEntry* cte = tt_lookup(cp.hash())) {
                ci.pn = cte->pn;
                ci.dn = cte->dn;
                ci.pn_sig = cte->pn_sig ? cte->pn_sig : csig;
                ci.dn_sig = cte->dn_sig ? cte->dn_sig : csig;
                ci.rank = cte->rank;
            } else {
                if (is_or) {
                    ci.pn = static_cast<uint64_t>(cdeg);
                    ci.dn = 1;
                } else {
                    ci.pn = 1;
                    ci.dn = static_cast<uint64_t>(cdeg);
                }
            }
        } else {
            int cd = find_on_path(cp);
            if (cd >= 0) {
                ci.pn = INF;
                ci.dn = 0;
                ci.cyc_depth = cd;
            } else if (const TTEntry* cte = tt_lookup(cp.hash())) {
                ci.pn = cte->pn;
                ci.dn = cte->dn;
                ci.pn_sig = cte->pn_sig ? cte->pn_sig : csig;
                ci.dn_sig = cte->dn_sig ? cte->dn_sig : csig;
                ci.rank = cte->rank;
            } else {
                int ev = eval_position(cp, prover_);
                if (is_or) {
                    if (ev >= 400)       { ci.pn = 2; ci.dn = 3; }
                    else if (ev <= -400) { ci.pn = 6; ci.dn = 1; }
                    else                 { ci.pn = 3; ci.dn = 1; }
                } else {
                    if (ev >= 400)       { ci.pn = 1; ci.dn = 4; }
                    else if (ev <= -400) { ci.pn = 3; ci.dn = 1; }
                    else                 { ci.pn = 1; ci.dn = 2; }
                }
            }
        }
    }

    // Order children descending by tactical order_score for better tie-breaking.
    std::sort(child_arena_.begin() + base, child_arena_.begin() + base + nm,
              [](const ChildInfo& a, const ChildInfo& b) {
                  return a.order_score > b.order_score;
              });

    // Push current position onto active path stack.
    uint64_t my_hash = pos.hash();
    uint32_t my_self_sig = hash_sig(my_hash);
    path_pos_.push_back(pos);
    path_hash_.push_back(my_hash);
    path_bloom_[my_hash & 2047ULL]++;

    uint64_t my_pn = 1;
    uint64_t my_dn = 1;
    uint32_t my_pn_sig = my_self_sig;
    uint32_t my_dn_sig = my_self_sig;
    int best_idx = 0;
    int best_dn_idx = 0;
    int sub_min_cyc = NO_CYCLE;

    uint32_t grp_sig[MAX_MOVES];
    uint64_t grp_max[MAX_MOVES];

    while (true) {
        if (is_or) {
            my_pn = INF;
            uint64_t sum_dn = 0;
            uint64_t max_dn = 0;
            uint32_t k_pos_dn = 0;
            uint64_t pn2 = INF;
            best_idx = 0;
            int max_dn_idx = 0;
            sub_min_cyc = NO_CYCLE;
            int ngrp = 0;

            for (int i = 0; i < nm; ++i) {
                const ChildInfo& ci = child_arena_[base + i];
                uint64_t cpn = ci.pn;
                uint64_t cdn = ci.dn;
                if (cdn > 0) {
                    if (limits_.dag_mode == DagMode::SNDA) {
                        uint32_t s = ci.dn_sig;
                        int g = 0;
                        for (; g < ngrp; ++g) {
                            if (grp_sig[g] == s) break;
                        }
                        if (g == ngrp) {
                            grp_sig[ngrp] = s;
                            grp_max[ngrp] = cdn;
                            ++ngrp;
                        } else if (cdn > grp_max[g]) {
                            grp_max[g] = cdn;
                        }
                    } else {
                        sum_dn = sat_add(sum_dn, cdn);
                    }
                    if (cdn > max_dn) {
                        max_dn = cdn;
                        max_dn_idx = i;
                    }
                    ++k_pos_dn;
                }
                if (cpn < my_pn) {
                    pn2 = my_pn;
                    my_pn = cpn;
                    best_idx = i;
                } else if (cpn < pn2) {
                    pn2 = cpn;
                }
                if (ci.cyc_depth < sub_min_cyc) {
                    sub_min_cyc = ci.cyc_depth;
                }
            }

            if (my_pn == 0) {
                my_dn = INF;
                sub_min_cyc = NO_CYCLE;
            } else if (k_pos_dn == 0) {
                my_dn = 0;
                my_pn = INF;
            } else if (limits_.dag_mode == DagMode::SNDA) {
                uint64_t s = 0;
                for (int g = 0; g < ngrp; ++g) s = sat_add(s, grp_max[g]);
                my_dn = s;
                my_pn_sig = child_arena_[base + best_idx].pn_sig;
                my_dn_sig = child_arena_[base + max_dn_idx].dn_sig;
            } else {
                my_dn = dag_aggregate(sum_dn, max_dn, k_pos_dn);
            }

            if (aborted_ || my_pn >= thpn || my_dn >= thdn) {
                break;
            }

            uint64_t pn2_scaled = (pn2 >= MAX_FINITE) ? INF : thresh_add(pn2, std::max<uint64_t>(1ULL, pn2 >> 2));
            uint64_t c_thpn = std::min(thpn, pn2_scaled);
            if (c_thpn <= child_arena_[base + best_idx].pn) {
                c_thpn = std::min<uint64_t>(thpn, child_arena_[base + best_idx].pn + 1ULL);
            }

            uint64_t c_thdn = INF;
            if (thdn < INF) {
                if (limits_.dag_mode == DagMode::SNDA) {
                    uint32_t bsig = child_arena_[base + best_idx].dn_sig;
                    uint64_t sum_other_groups = 0;
                    for (int g = 0; g < ngrp; ++g) {
                        if (grp_sig[g] != bsig) {
                            sum_other_groups = sat_add(sum_other_groups, grp_max[g]);
                        }
                    }
                    c_thdn = std::max<uint64_t>(child_arena_[base + best_idx].dn + 1ULL,
                                                sat_sub(thdn, sum_other_groups));
                    if (c_thdn > thdn) c_thdn = thdn;
                } else {
                    uint64_t max_other = 0;
                    uint64_t sum_other = 0;
                    uint32_t k_pos_other = 0;
                    for (int i = 0; i < nm; ++i) {
                        if (i == best_idx) continue;
                        uint64_t cdn = child_arena_[base + i].dn;
                        if (cdn > 0) {
                            sum_other = sat_add(sum_other, cdn);
                            if (cdn > max_other) max_other = cdn;
                            ++k_pos_other;
                        }
                    }
                    c_thdn = dag_child_threshold(
                        thdn, child_arena_[base + best_idx].dn, max_other, sum_other, k_pos_other);
                }
            }

            Position next_pos = child_arena_[base + best_idx].pos;
            MidResult cr = mid(next_pos, c_thpn, c_thdn, depth + 1);
            child_arena_[base + best_idx].pn = cr.pn;
            child_arena_[base + best_idx].dn = cr.dn;
            child_arena_[base + best_idx].pn_sig = cr.pn_sig ? cr.pn_sig : hash_sig(next_pos.hash());
            child_arena_[base + best_idx].dn_sig = cr.dn_sig ? cr.dn_sig : hash_sig(next_pos.hash());
            child_arena_[base + best_idx].rank = cr.rank;
            child_arena_[base + best_idx].cyc_depth = cr.min_cycle_depth;
        } else {
            uint64_t sum_pn = 0;
            uint64_t max_pn = 0;
            uint32_t k_pos_pn = 0;
            my_dn = INF;
            uint64_t dn2 = INF;
            best_idx = 0;
            int max_pn_idx = 0;
            int best_disproof_cyc = -2;
            best_dn_idx = 0;
            int ngrp = 0;

            for (int i = 0; i < nm; ++i) {
                const ChildInfo& ci = child_arena_[base + i];
                uint64_t cpn = ci.pn;
                uint64_t cdn = ci.dn;
                if (cpn > 0) {
                    if (limits_.dag_mode == DagMode::SNDA) {
                        uint32_t s = ci.pn_sig;
                        int g = 0;
                        for (; g < ngrp; ++g) {
                            if (grp_sig[g] == s) break;
                        }
                        if (g == ngrp) {
                            grp_sig[ngrp] = s;
                            grp_max[ngrp] = cpn;
                            ++ngrp;
                        } else if (cpn > grp_max[g]) {
                            grp_max[g] = cpn;
                        }
                    } else {
                        sum_pn = sat_add(sum_pn, cpn);
                    }
                    if (cpn > max_pn) {
                        max_pn = cpn;
                        max_pn_idx = i;
                    }
                    ++k_pos_pn;
                }
                if (cdn < my_dn) {
                    dn2 = my_dn;
                    my_dn = cdn;
                    best_idx = i;
                } else if (cdn < dn2) {
                    dn2 = cdn;
                }
                if (cdn == 0 && ci.cyc_depth > best_disproof_cyc) {
                    best_disproof_cyc = ci.cyc_depth;
                    best_dn_idx = i;
                }
            }

            if (my_dn == 0) {
                my_pn = INF;
                sub_min_cyc = (best_disproof_cyc >= -1) ? best_disproof_cyc : NO_CYCLE;
            } else if (k_pos_pn == 0) {
                my_pn = 0;
                my_dn = INF;
                sub_min_cyc = NO_CYCLE;
            } else if (limits_.dag_mode == DagMode::SNDA) {
                uint64_t s = 0;
                for (int g = 0; g < ngrp; ++g) s = sat_add(s, grp_max[g]);
                my_pn = s;
                my_dn_sig = child_arena_[base + best_idx].dn_sig;
                my_pn_sig = child_arena_[base + max_pn_idx].pn_sig;
                sub_min_cyc = NO_CYCLE;
            } else {
                my_pn = dag_aggregate(sum_pn, max_pn, k_pos_pn);
                sub_min_cyc = NO_CYCLE;
            }

            if (aborted_ || my_pn >= thpn || my_dn >= thdn) {
                break;
            }

            uint64_t dn2_scaled = (dn2 >= MAX_FINITE) ? INF : thresh_add(dn2, std::max<uint64_t>(1ULL, dn2 >> 2));
            uint64_t c_thdn = std::min(thdn, dn2_scaled);
            if (c_thdn <= child_arena_[base + best_idx].dn) {
                c_thdn = std::min<uint64_t>(thdn, child_arena_[base + best_idx].dn + 1ULL);
            }

            uint64_t c_thpn = INF;
            if (thpn < INF) {
                if (limits_.dag_mode == DagMode::SNDA) {
                    uint32_t bsig = child_arena_[base + best_idx].pn_sig;
                    uint64_t sum_other_groups = 0;
                    for (int g = 0; g < ngrp; ++g) {
                        if (grp_sig[g] != bsig) {
                            sum_other_groups = sat_add(sum_other_groups, grp_max[g]);
                        }
                    }
                    c_thpn = std::max<uint64_t>(child_arena_[base + best_idx].pn + 1ULL,
                                                sat_sub(thpn, sum_other_groups));
                    if (c_thpn > thpn) c_thpn = thpn;
                } else {
                    uint64_t max_other = 0;
                    uint64_t sum_other = 0;
                    uint32_t k_pos_other = 0;
                    for (int i = 0; i < nm; ++i) {
                        if (i == best_idx) continue;
                        uint64_t cpn = child_arena_[base + i].pn;
                        if (cpn > 0) {
                            sum_other = sat_add(sum_other, cpn);
                            if (cpn > max_other) max_other = cpn;
                            ++k_pos_other;
                        }
                    }
                    c_thpn = dag_child_threshold(
                        thpn, child_arena_[base + best_idx].pn, max_other, sum_other, k_pos_other);
                }
            }

            Position next_pos = child_arena_[base + best_idx].pos;
            MidResult cr = mid(next_pos, c_thpn, c_thdn, depth + 1);
            child_arena_[base + best_idx].pn = cr.pn;
            child_arena_[base + best_idx].dn = cr.dn;
            child_arena_[base + best_idx].pn_sig = cr.pn_sig ? cr.pn_sig : hash_sig(next_pos.hash());
            child_arena_[base + best_idx].dn_sig = cr.dn_sig ? cr.dn_sig : hash_sig(next_pos.hash());
            child_arena_[base + best_idx].rank = cr.rank;
            child_arena_[base + best_idx].cyc_depth = cr.min_cycle_depth;
        }
    }

    // Pop path stack.
    path_bloom_[my_hash & 2047ULL]--;
    path_hash_.pop_back();
    path_pos_.pop_back();

    if (depth == 0 && limits_.verbose) {
        std::cerr << "[dfpn root] total_nodes=" << nodes_
                  << " tb_hits=" << tb_hits_
                  << " dag=" << dag_mode_to_string(limits_.dag_mode)
                  << " my_pn=" << my_pn << " my_dn=" << my_dn << "\n";
        for (int i = 0; i < nm; ++i) {
            const ChildInfo& ci = child_arena_[base + i];
            std::cerr << "  " << ci.move.to_string()
                      << " pn=" << ci.pn << " dn=" << ci.dn
                      << " cyc=" << ci.cyc_depth
                      << " fen=\"" << ci.pos.to_fen() << "\"\n";
        }
    }

    uint32_t work = static_cast<uint32_t>(std::min<uint64_t>(nodes_ - start_nodes + 1, 0xFFFFFFFFULL));

    res.pn = my_pn;
    res.dn = my_dn;
    res.pn_sig = my_pn_sig;
    res.dn_sig = my_dn_sig;
    res.min_cycle_depth = sub_min_cyc;

    if (my_pn == 0) {
        if (is_or) {
            uint16_t pm = pack_move(child_arena_[base + best_idx].move);
            uint16_t rk = static_cast<uint16_t>(std::min<uint32_t>(65534U, child_arena_[base + best_idx].rank + 1U));
            res.best_move = pm;
            res.rank = rk;
            tt_store(my_hash, 0, INF, 0, 0, pm, rk, work);
            if (proof_moves_.size() < max_proof_moves_) {
                proof_moves_[my_hash] = pm;
            }
        } else {
            uint16_t max_rk = 0;
            for (int i = 0; i < nm; ++i) {
                if (child_arena_[base + i].rank > max_rk) max_rk = child_arena_[base + i].rank;
            }
            res.rank = max_rk;
            tt_store(my_hash, 0, INF, 0, 0, 0, max_rk, work);
        }
    } else if (my_dn == 0) {
        uint16_t dm = 0;
        if (!is_or) {
            dm = pack_move(child_arena_[base + best_dn_idx].move);
            res.best_move = dm;
            if (!aborted_ && sub_min_cyc >= 0 && disproof_moves_.size() < max_proof_moves_) {
                disproof_moves_[my_hash] = dm;
            }
        }
        if (!aborted_ && !safe_cycle_targets_ && sub_min_cyc >= depth) {
            tt_store(my_hash, INF, 0, 0, 0, dm, 0, work);
            res.min_cycle_depth = NO_CYCLE;
        }
    } else if (!aborted_) {
        uint16_t bm = pack_move(child_arena_[base + best_idx].move);
        tt_store(my_hash, my_pn, my_dn, my_pn_sig, my_dn_sig, bm, 0, work);
    }

    return res;
}

bool DfpnSolver::extract_or(const Position& pos,
                            Certificate& cert,
                            std::unordered_map<std::string, uint32_t>& done_rank,
                            std::unordered_map<std::string, bool>& visiting,
                            uint32_t& out_rank,
                            int depth) {
    if (depth > MAX_DFPN_DEPTH + 100) return false;
    std::string fen = pos.to_fen();
    auto it_done = done_rank.find(fen);
    if (it_done != done_rank.end()) {
        out_rank = it_done->second;
        return true;
    }
    if (visiting[fen]) {
        return false;
    }

    Move moves[MAX_MOVES];
    int nm = pos.legal_moves(moves);
    if (nm == 0) return false;

    // Shortcut 1: immediate mate-in-1!
    for (int i = 0; i < nm; ++i) {
        Position q = pos.make_move(moves[i]);
        if (q.in_check() && !q.has_legal_moves()) {
            CertEntry e;
            e.pos = pos;
            e.fen = fen;
            e.move = moves[i];
            e.rank = 1;
            cert.entries[fen] = std::move(e);
            done_rank[fen] = 1;
            out_rank = 1;
            return true;
        }
    }

    auto try_move = [&](Move m) -> bool {
        Position q = pos.make_move(m);
        Move rbuf[MAX_MOVES];
        int nr = q.legal_moves(rbuf);
        if (nr == 0) {
            if (!q.in_check()) return false;
            CertEntry e;
            e.pos = pos;
            e.fen = fen;
            e.move = m;
            e.rank = 1;
            cert.entries[fen] = std::move(e);
            done_rank[fen] = 1;
            out_rank = 1;
            return true;
        }

        visiting[fen] = true;
        uint32_t max_cr = 0;
        bool ok = true;
        for (int j = 0; j < nr; ++j) {
            Position qr = q.make_move(rbuf[j]);
            uint32_t cr = 0;
            if (!extract_or(qr, cert, done_rank, visiting, cr, depth + 1)) {
                ok = false;
                break;
            }
            if (cr > max_cr) max_cr = cr;
        }
        visiting.erase(fen);

        if (ok) {
            uint32_t rk = max_cr + 1;
            CertEntry e;
            e.pos = pos;
            e.fen = fen;
            e.move = m;
            e.rank = rk;
            cert.entries[fen] = std::move(e);
            done_rank[fen] = rk;
            out_rank = rk;
            return true;
        }
        return false;
    };

    // Shortcut 2: direct tablebase splice when `pos` is a TB win!
    if (tb_probe_ && tb_probe_->is_loaded()) {
        tb::WDL wdl = tb::WDL_UNKNOWN;
        uint16_t dtm = 0;
        if (tb_probe_->probe(pos, wdl, dtm) && wdl == tb::WDL_WIN) {
            Move tb_mv{};
            if (tb_probe_->pick_win_move(pos, dtm, tb_mv)) {
                if (try_move(tb_mv)) return true;
            }
        }
    }

    // Build candidate move list: proof_cache move first, then TT best_move, then TB-winning moves, then TT-proved children.
    std::vector<Move> candidates;
    auto add_unique = [&](Move m) {
        if (std::find(candidates.begin(), candidates.end(), m) == candidates.end()) {
            candidates.push_back(m);
        }
    };
    auto add_if_legal = [&](uint16_t packed) {
        if (!packed) return;
        Move m = unpack_move(packed);
        for (int i = 0; i < nm; ++i) {
            if (moves[i] == m) {
                add_unique(m);
                return;
            }
        }
    };

    auto pm_it = proof_moves_.find(pos.hash());
    if (pm_it != proof_moves_.end()) {
        add_if_legal(pm_it->second);
    }
    if (const TTEntry* te = tt_lookup(pos.hash())) {
        if (te->pn == 0) add_if_legal(te->best_move);
    }
    // Check moves leading directly into a TB win (e.g. 5pc -> 4pc capture!)
    if (tb_probe_ && tb_probe_->is_loaded()) {
        for (int i = 0; i < nm; ++i) {
            Position q = pos.make_move(moves[i]);
            tb::WDL qw = tb::WDL_UNKNOWN;
            uint16_t qd = 0;
            if (tb_probe_->probe(q, qw, qd) && qw == tb::WDL_LOSS) {
                add_unique(moves[i]);
            }
        }
    }
    for (int i = 0; i < nm; ++i) {
        Position q = pos.make_move(moves[i]);
        if (const TTEntry* cte = tt_lookup(q.hash())) {
            if (cte->pn == 0) {
                add_unique(moves[i]);
            }
        }
    }

    for (Move m : candidates) {
        if (try_move(m)) return true;
    }

    // Fallback: TT entry may have been evicted under memory pressure. Re-solve `pos`!
    if (!check_limits()) {
        path_pos_.clear();
        path_hash_.clear();
        std::memset(path_bloom_, 0, sizeof(path_bloom_));
        MidResult rr = mid(pos, INF, INF, 0);
        if (rr.pn == 0 && rr.best_move) {
            Move m = unpack_move(rr.best_move);
            for (int i = 0; i < nm; ++i) {
                if (moves[i] == m) {
                    if (try_move(m)) return true;
                    break;
                }
            }
        }
    }

    return false;
}

bool DfpnSolver::extract_certificate(const Position& root, Certificate& cert) {
    cert.claim = Claim{ClaimKind::WIN, prover_};
    cert.root = root;
    cert.root_fen = root.to_fen();
    cert.entries.clear();

    std::unordered_map<std::string, uint32_t> done_rank;
    std::unordered_map<std::string, bool> visiting;

    if (root.side_to_move() == prover_) {
        uint32_t rk = 0;
        if (!extract_or(root, cert, done_rank, visiting, rk, 0)) {
            return false;
        }
    } else {
        Move rbuf[MAX_MOVES];
        int nr = root.legal_moves(rbuf);
        if (nr == 0) {
            return root.in_check();
        }
        for (int i = 0; i < nr; ++i) {
            Position rp = root.make_move(rbuf[i]);
            uint32_t rk = 0;
            if (!extract_or(rp, cert, done_rank, visiting, rk, 0)) {
                return false;
            }
        }
    }

    std::string err;
    return cert.verify(&err);
}

SolveStatus DfpnSolver::solve_win(const Position& root,
                                  Color prover,
                                  const SolveLimits& limits,
                                  Certificate* cert_out,
                                  SolveStats* stats_out) {
    prover_ = prover;
    limits_ = limits;
    timer_ = Timer{};
    nodes_ = 0;
    tb_hits_ = 0;
    aborted_ = false;
    path_pos_.clear();
    path_hash_.clear();
    std::memset(path_bloom_, 0, sizeof(path_bloom_));

    MidResult res = mid(root, INF, INF, 0);

    SolveStatus status = SolveStatus::LIMIT;
    if (res.pn == 0) {
        status = SolveStatus::PROVED;
    } else if (res.dn == 0 && !aborted_ && res.min_cycle_depth >= 0) {
        status = SolveStatus::DISPROVED;
    } else {
        status = SolveStatus::LIMIT;
    }

    SolveStats st;
    st.nodes = nodes_;
    st.tb_hits = tb_hits_;

    if (status == SolveStatus::PROVED && cert_out != nullptr) {
        if (!extract_certificate(root, *cert_out)) {
            status = SolveStatus::LIMIT;
            st.note = "proof extraction incomplete within limits";
        } else {
            st.raw_entries = cert_out->size();
            st.pruned_entries = st.raw_entries;
            st.min_entries = st.raw_entries;
            if (limits.minimize) {
                cert_out->minimize(&st.raw_entries, &st.pruned_entries, &st.min_entries);
            }
            st.max_rank = cert_out->max_rank();
            std::string verr;
            if (!cert_out->verify(&verr)) {
                status = SolveStatus::ERROR;
                st.note = "internal cert verify failed: " + verr;
            }
        }
    }

    st.nodes = nodes_;
    st.tb_hits = tb_hits_;
    st.seconds = timer_.elapsed();
    if (stats_out) *stats_out = st;
    return status;
}

bool DfpnSolver::extract_draw_certificate(const Position& root, Color defender, Certificate& cert) {
    cert.claim = Claim{ClaimKind::ATLEAST_DRAW, defender};
    cert.root = root;
    cert.root_fen = root.to_fen();
    cert.entries.clear();

    constexpr size_t MAX_DRAW_CERT_ENTRIES = 1500000;
    std::unordered_set<std::string> seen;
    std::unordered_map<uint64_t, std::vector<Position>> safe_targets;
    std::queue<Position> q;

    auto enqueue_defender = [&](const Position& p) -> bool {
        if (!p.has_legal_moves()) {
            return !p.in_check();
        }
        std::string f = p.to_fen();
        if (seen.insert(f).second) {
            if (seen.size() > MAX_DRAW_CERT_ENTRIES) return false;
            safe_targets[p.hash()].push_back(p);
            q.push(p);
        }
        return true;
    };

    if (root.side_to_move() == defender) {
        if (!enqueue_defender(root)) return false;
    } else {
        Move rbuf[MAX_MOVES];
        int nr = root.legal_moves(rbuf);
        for (int i = 0; i < nr; ++i) {
            if (!enqueue_defender(root.make_move(rbuf[i]))) return false;
        }
    }

    Move mbuf[MAX_MOVES];
    Move rbuf[MAX_MOVES];

    auto move_is_safe_hint = [&](const Position& p, Move m) -> bool {
        Position qp = p.make_move(m);
        if (tb_probe_ && tb_probe_->is_loaded()) {
            tb::WDL qw = tb::WDL_UNKNOWN;
            uint16_t qd = 0;
            if (tb_probe_->probe(qp, qw, qd)) {
                return qw != tb::WDL_WIN; // opponent (~defender) does NOT win!
            }
        }
        int nr = qp.legal_moves(rbuf);
        for (int j = 0; j < nr; ++j) {
            Position qr = qp.make_move(rbuf[j]);
            if (!qr.has_legal_moves() && qr.in_check()) return false;
            if (const TTEntry* te = tt_lookup(qr.hash())) {
                if (te->pn == 0) return false;
            }
        }
        return true;
    };

    while (!q.empty()) {
        if (check_limits()) return false;
        Position p = q.front();
        q.pop();

        int nm = p.legal_moves(mbuf);
        if (nm == 0) {
            if (p.in_check()) return false;
            continue;
        }

        Move chosen{};
        bool found = false;

        // Priority 1: immediate opponent checkmate or stalemate (0 replies!)
        for (int i = 0; i < nm; ++i) {
            Position qp = p.make_move(mbuf[i]);
            if (!qp.has_legal_moves()) {
                chosen = mbuf[i];
                found = true;
                break;
            }
        }

        // Priority 2: all non-stalemate replies already in `seen` (closes immediately!)
        if (!found) {
            for (int i = 0; i < nm; ++i) {
                Position qp = p.make_move(mbuf[i]);
                int nr = qp.legal_moves(rbuf);
                bool all_in = true;
                for (int j = 0; j < nr; ++j) {
                    Position qr = qp.make_move(rbuf[j]);
                    if (!qr.has_legal_moves()) {
                        if (qr.in_check()) { all_in = false; break; }
                        continue;
                    }
                    if (seen.find(qr.to_fen()) == seen.end()) {
                        all_in = false;
                        break;
                    }
                }
                if (all_in) {
                    chosen = mbuf[i];
                    found = true;
                    break;
                }
            }
        }

        // Priority 2.5: direct tablebase splice if `p` is in a loaded tablebase!
        if (!found && tb_probe_ && tb_probe_->is_loaded()) {
            tb::WDL pw = tb::WDL_UNKNOWN;
            uint16_t pd = 0;
            if (tb_probe_->probe(p, pw, pd)) {
                if (pw == tb::WDL_WIN && tb_probe_->pick_win_move(p, pd, chosen)) {
                    found = true;
                } else if (pw == tb::WDL_DRAW && tb_probe_->pick_draw_move(p, &seen, chosen)) {
                    found = true;
                }
            }
        }

        // Priority 3: recorded disproof move from TT or disproof_moves_
        auto try_packed = [&](uint16_t packed) -> bool {
            if (!packed) return false;
            Move m = unpack_move(packed);
            for (int i = 0; i < nm; ++i) {
                if (mbuf[i] == m && move_is_safe_hint(p, m)) {
                    chosen = m;
                    return true;
                }
            }
            return false;
        };

        if (!found) {
            if (const TTEntry* te = tt_lookup(p.hash())) {
                if (te->dn == 0 && try_packed(te->best_move)) found = true;
            }
        }
        if (!found) {
            auto it = disproof_moves_.find(p.hash());
            if (it != disproof_moves_.end() && try_packed(it->second)) found = true;
        }

        // Priority 3.5: any move leading directly into a TB draw or TB loss for opponent!
        if (!found && tb_probe_ && tb_probe_->is_loaded()) {
            for (int i = 0; i < nm; ++i) {
                Position qp = p.make_move(mbuf[i]);
                tb::WDL qw = tb::WDL_UNKNOWN;
                uint16_t qd = 0;
                if (tb_probe_->probe(qp, qw, qd) && (qw == tb::WDL_LOSS || qw == tb::WDL_DRAW)) {
                    chosen = mbuf[i];
                    found = true;
                    break;
                }
            }
        }

        // Priority 4: any legal move whose child has dn == 0 in TT
        if (!found) {
            for (int i = 0; i < nm; ++i) {
                Position qp = p.make_move(mbuf[i]);
                if (const TTEntry* cte = tt_lookup(qp.hash())) {
                    if (cte->dn == 0 && move_is_safe_hint(p, mbuf[i])) {
                        chosen = mbuf[i];
                        found = true;
                        break;
                    }
                }
            }
        }

        // Priority 5: fallback re-solve `p` with `safe_targets` as known-safe cycle targets!
        if (!found) {
            path_pos_.clear();
            path_hash_.clear();
            std::memset(path_bloom_, 0, sizeof(path_bloom_));
            safe_cycle_targets_ = &safe_targets;
            auto& bucket = safe_targets[p.hash()];
            bool removed = false;
            for (size_t k = 0; k < bucket.size(); ++k) {
                if (bucket[k] == p) {
                    removed = true;
                    bucket.erase(bucket.begin() + static_cast<ptrdiff_t>(k));
                    break;
                }
            }
            MidResult rr = mid(p, INF, INF, 0);
            if (removed) {
                bucket.push_back(p);
            }
            safe_cycle_targets_ = nullptr;

            if (rr.dn == 0 && !aborted_ && rr.min_cycle_depth >= 0 && try_packed(rr.best_move)) {
                found = true;
            }
        }

        if (!found) return false;

        std::string fen = p.to_fen();
        CertEntry ce;
        ce.pos = p;
        ce.fen = fen;
        ce.move = chosen;
        ce.rank = 0;
        cert.entries[fen] = std::move(ce);

        Position qp = p.make_move(chosen);
        int nr = qp.legal_moves(rbuf);
        for (int j = 0; j < nr; ++j) {
            if (!enqueue_defender(qp.make_move(rbuf[j]))) return false;
        }
    }

    std::string verr;
    return cert.verify(&verr);
}

SolveStatus DfpnSolver::solve_draw_via_disproof(const Position& root,
                                                Color defender,
                                                const SolveLimits& limits,
                                                Certificate* cert_out,
                                                SolveStats* stats_out) {
    prover_ = ~defender;
    limits_ = limits;
    timer_ = Timer{};
    nodes_ = 0;
    tb_hits_ = 0;
    aborted_ = false;
    safe_cycle_targets_ = nullptr;
    path_pos_.clear();
    path_hash_.clear();
    std::memset(path_bloom_, 0, sizeof(path_bloom_));

    MidResult res = mid(root, INF, INF, 0);

    SolveStatus status = SolveStatus::LIMIT;
    SolveStats st;

    if (res.pn == 0) {
        status = SolveStatus::DISPROVED;
        st.note = "disproved via WIN " + std::string(1, (~defender) == WHITE ? 'w' : 'b');
    } else if (res.dn == 0 && !aborted_ && res.min_cycle_depth >= 0) {
        if (cert_out != nullptr) {
            if (!extract_draw_certificate(root, defender, *cert_out)) {
                status = SolveStatus::LIMIT;
                st.note = "WIN ~prover disproved, but draw certificate extraction hit limit/cap";
            } else {
                status = SolveStatus::PROVED;
                st.raw_entries = cert_out->size();
                st.pruned_entries = st.raw_entries;
                st.min_entries = st.raw_entries;
                if (limits.minimize) {
                    cert_out->minimize(&st.raw_entries, &st.pruned_entries, &st.min_entries);
                }
                st.max_rank = 0;
                std::string verr;
                if (!cert_out->verify(&verr)) {
                    status = SolveStatus::ERROR;
                    st.note = "internal draw cert verify failed: " + verr;
                } else {
                    st.note = "proved via df-pn disproof witness";
                }
            }
        } else {
            status = SolveStatus::PROVED;
        }
    } else {
        status = SolveStatus::LIMIT;
    }

    st.nodes = nodes_;
    st.tb_hits = tb_hits_;
    st.seconds = timer_.elapsed();
    if (stats_out) *stats_out = st;
    return status;
}

} // namespace msolve
