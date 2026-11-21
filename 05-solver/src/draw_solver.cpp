#include "draw_solver.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <limits>
#include <queue>
#include <unordered_map>
#include <vector>

namespace msolve {

namespace {

constexpr int MATE_SCORE = 100000;
constexpr int MATE_THRESH = 90000;

// Exact-mate-aware shallow alpha-beta from `prover`'s perspective.
// Sound for detecting forced mates within `depth` plies (no speculative pruning).
int ab_eval(const Position& pos, Color prover, int depth, int alpha, int beta, uint64_t& nodes) {
    ++nodes;
    Move moves[MAX_MOVES];
    int nm = pos.legal_moves(moves);
    const bool is_max = (pos.side_to_move() == prover);

    if (nm == 0) {
        if (pos.in_check()) {
            return is_max ? (-MATE_SCORE - depth) : (MATE_SCORE + depth);
        }
        return 0; // stalemate is a draw (0 cp)
    }
    if (depth == 0) {
        return eval_position(pos, prover);
    }

    // Light move ordering for alpha-beta cutoffs
    int scores[MAX_MOVES];
    int order[MAX_MOVES];
    for (int i = 0; i < nm; ++i) {
        order[i] = i;
        scores[i] = move_order_score(pos, moves[i]);
    }
    std::sort(order, order + nm, [&](int a, int b) { return scores[a] > scores[b]; });

    if (is_max) {
        int best = -MATE_SCORE - 1000;
        for (int idx = 0; idx < nm; ++idx) {
            Position nxt = pos.make_move(moves[order[idx]]);
            int v = ab_eval(nxt, prover, depth - 1, alpha, beta, nodes);
            if (v > best) best = v;
            if (best > alpha) alpha = best;
            if (alpha >= beta) break;
        }
        return best;
    } else {
        int best = MATE_SCORE + 1000;
        for (int idx = 0; idx < nm; ++idx) {
            Position nxt = pos.make_move(moves[order[idx]]);
            int v = ab_eval(nxt, prover, depth - 1, alpha, beta, nodes);
            if (v < best) best = v;
            if (best < beta) beta = best;
            if (alpha >= beta) break;
        }
        return best;
    }
}

enum NodeStatus : uint8_t {
    ST_OPEN = 0,
    ST_HAS_MOVE = 1,
    ST_DISPROVED = 2,
    ST_PROVED_SAFE = 3
};

struct MoveChoice {
    Move move;
    bool disproved = false;
    bool replies_materialized = false;
    int score = 0;
    int eval = 0;
    std::vector<uint32_t> replies;
};

struct OrNode {
    Position pos;
    uint8_t status = ST_OPEN;
    int16_t chosen_idx = -1;
    int16_t depth = 0;
    int32_t eval = 0;
    bool expanded = false;
    bool refutation_checked = false;
    std::vector<MoveChoice> moves;
    std::vector<std::pair<uint32_t, int16_t>> parents;
};

class ClosedSetSearch {
public:
    ClosedSetSearch(const Position& root, Color prover, const SolveLimits& limits, Timer& timer, uint64_t& nodes)
        : root_(root), prover_(prover), limits_(limits), timer_(timer), nodes_(nodes),
          refute_solver_(std::max<size_t>(8, limits.tt_mb / 4)) {
        // Bound explicit graph size to stay strictly inside memory budget (~60% of tt_mb, min 10k, max 800k).
        size_t graph_bytes = (limits.tt_mb * 1024ULL * 1024ULL * 6ULL) / 10ULL;
        max_graph_nodes_ = std::clamp<size_t>(graph_bytes / 640ULL, 10000ULL, 800000ULL);
    }

    SolveStatus run(Certificate* cert_out, SolveStats& st) {
        // 1. Initialize root targets.
        if (root_.side_to_move() == prover_) {
            if (!root_.has_legal_moves()) {
                if (root_.in_check()) return SolveStatus::DISPROVED;
                // Prover stalemate at root -> valid 0-entry ATLEAST_DRAW certificate!
                if (cert_out) {
                    cert_out->claim = Claim{ClaimKind::ATLEAST_DRAW, prover_};
                    cert_out->root = root_;
                    cert_out->root_fen = root_.to_fen();
                    cert_out->entries.clear();
                }
                st.raw_entries = st.pruned_entries = st.min_entries = 0;
                return SolveStatus::PROVED;
            }
            uint32_t rid = get_or_create(root_, 0);
            root_targets_.push_back(rid);
        } else {
            Move rbuf[MAX_MOVES];
            int nr = root_.legal_moves(rbuf);
            if (nr == 0) {
                // Opponent has no moves (mate or stalemate) -> 0-entry ATLEAST_DRAW!
                if (cert_out) {
                    cert_out->claim = Claim{ClaimKind::ATLEAST_DRAW, prover_};
                    cert_out->root = root_;
                    cert_out->root_fen = root_.to_fen();
                    cert_out->entries.clear();
                }
                st.raw_entries = st.pruned_entries = st.min_entries = 0;
                return SolveStatus::PROVED;
            }
            for (int i = 0; i < nr; ++i) {
                Position rp = root_.make_move(rbuf[i]);
                if (!rp.has_legal_moves()) {
                    if (rp.in_check()) {
                        return SolveStatus::DISPROVED; // Opponent mates immediately!
                    }
                    continue; // prover stalemate is covered without entry!
                }
                uint32_t id = get_or_create(rp, 0);
                if (std::find(root_targets_.begin(), root_targets_.end(), id) == root_targets_.end()) {
                    root_targets_.push_back(id);
                }
            }
            if (root_targets_.empty()) {
                // Every opponent reply stalemates prover!
                if (cert_out) {
                    cert_out->claim = Claim{ClaimKind::ATLEAST_DRAW, prover_};
                    cert_out->root = root_;
                    cert_out->root_fen = root_.to_fen();
                    cert_out->entries.clear();
                }
                st.raw_entries = st.pruned_entries = st.min_entries = 0;
                return SolveStatus::PROVED;
            }
        }

        recompute_active_and_frontier();
        uint64_t expansions = 0;

        while (true) {
            if (hit_limit()) {
                return SolveStatus::LIMIT;
            }

            if (root_disproved()) {
                return SolveStatus::DISPROVED;
            }

            while (dirty_active_ && !root_disproved()) {
                dirty_active_ = false;
                recompute_active_and_frontier();
            }

            // Pick best frontier node to expand (skip stale entries not in active or no longer OPEN).
            uint32_t u = UINT32_MAX;
            while (!frontier_pq_.empty()) {
                auto top = frontier_pq_.top();
                frontier_pq_.pop();
                uint32_t cand = top.second;
                if (cand < active_stamp_.size() &&
                    active_stamp_[cand] == cur_stamp_ &&
                    or_nodes_[cand].status == ST_OPEN) {
                    u = cand;
                    break;
                }
            }

            if (u == UINT32_MAX) {
                // Frontier appears empty -> verify exact closure with a fresh BFS!
                recompute_active_and_frontier();
                if (root_disproved()) return SolveStatus::DISPROVED;
                if (frontier_pq_.empty()) {
                    // CLOSED SET FOUND!
                    return extract_and_finish(cert_out, st);
                }
                continue;
            }

            if (or_nodes_.size() >= max_graph_nodes_) {
                st.note = "closed-set graph memory cap reached";
                return SolveStatus::LIMIT;
            }

            expand_node(u);
            ++expansions;

            // Periodic shortcut-collapse pass: see if any active node with open descendants
            // now has an alternative move whose replies ALL land in already-expanded active nodes!
            if ((expansions & 511ULL) == 0 && !dirty_active_) {
                if (try_shortcut_collapse()) {
                    dirty_active_ = true;
                }
            }
        }
    }

private:
    bool hit_limit() const {
        if (nodes_ >= limits_.max_nodes) return true;
        if (timer_.elapsed() >= limits_.max_seconds) return true;
        return false;
    }

    bool root_disproved() const {
        for (uint32_t r : root_targets_) {
            if (or_nodes_[r].status == ST_DISPROVED) return true;
        }
        return false;
    }

    int32_t lookup_id(const Position& pos) const {
        auto it = hash_buckets_.find(pos.hash());
        if (it == hash_buckets_.end()) return -1;
        for (uint32_t id : it->second) {
            if (or_nodes_[id].pos == pos) return static_cast<int32_t>(id);
        }
        return -1;
    }

    uint32_t get_or_create(const Position& pos, int16_t depth) {
        int32_t existing = lookup_id(pos);
        if (existing >= 0) {
            if (depth < or_nodes_[existing].depth) {
                or_nodes_[existing].depth = depth;
            }
            return static_cast<uint32_t>(existing);
        }
        uint32_t id = static_cast<uint32_t>(or_nodes_.size());
        OrNode node;
        node.pos = pos;
        node.depth = depth;
        node.eval = eval_position(pos, prover_);
        or_nodes_.push_back(std::move(node));
        hash_buckets_[pos.hash()].push_back(id);
        if (active_stamp_.size() < or_nodes_.size()) {
            active_stamp_.resize(or_nodes_.size(), 0);
        }
        return id;
    }

    void push_frontier(uint32_t id) {
        // Smaller priority key pops first:
        // Prioritize dangerous (low eval) AND shallow (small depth) nodes!
        int key = or_nodes_[id].eval + static_cast<int>(or_nodes_[id].depth) * 70;
        if (or_nodes_[id].pos.in_check()) key -= 150;
        frontier_pq_.push({key, id});
    }

    void recompute_active_and_frontier() {
        ++cur_stamp_;
        if (active_stamp_.size() < or_nodes_.size()) {
            active_stamp_.resize(or_nodes_.size(), 0);
        }
        frontier_pq_ = {};
        active_list_.clear();

        std::queue<uint32_t> q;
        for (uint32_t r : root_targets_) {
            if (or_nodes_[r].status == ST_DISPROVED) return;
            if (active_stamp_[r] != cur_stamp_) {
                active_stamp_[r] = cur_stamp_;
                active_list_.push_back(r);
                q.push(r);
            }
        }
        while (!q.empty()) {
            uint32_t u = q.front();
            q.pop();
            OrNode& node = or_nodes_[u];
            if (node.status == ST_OPEN) {
                push_frontier(u);
            } else if (node.status == ST_HAS_MOVE) {
                const MoveChoice& mc = node.moves[node.chosen_idx];
                for (uint32_t v : mc.replies) {
                    if (or_nodes_[v].status == ST_DISPROVED) {
                        // Should already have been propagated, ensure consistency
                        propagate_disproved(v);
                        return;
                    }
                    if (active_stamp_[v] != cur_stamp_) {
                        active_stamp_[v] = cur_stamp_;
                        active_list_.push_back(v);
                        q.push(v);
                    }
                }
            }
        }
    }

    bool is_active(uint32_t id) const {
        return id < active_stamp_.size() && active_stamp_[id] == cur_stamp_;
    }

    // Materialize replies for move choice `mc` of node `u` and wire parent back-pointers.
    // Returns false if any reply is already DISPROVED (caller must reject move).
    bool materialize_move(uint32_t u, int16_t midx) {
        MoveChoice& mc = or_nodes_[u].moves[midx];
        if (mc.disproved) return false;

        if (!mc.replies_materialized) {
            Position q = or_nodes_[u].pos.make_move(mc.move);
            Move rbuf[MAX_MOVES];
            int nr = q.legal_moves(rbuf);
            int16_t child_depth = static_cast<int16_t>(or_nodes_[u].depth + 1);
            mc.replies.clear();
            mc.replies.reserve(static_cast<size_t>(nr));
            for (int i = 0; i < nr; ++i) {
                Position qr = q.make_move(rbuf[i]);
                if (!qr.has_legal_moves()) {
                    if (qr.in_check()) {
                        mc.disproved = true;
                        mc.replies.clear();
                        return false;
                    }
                    continue; // prover stalemate: covered!
                }
                uint32_t cid = get_or_create(qr, child_depth);
                if (or_nodes_[cid].status == ST_DISPROVED) {
                    mc.disproved = true;
                    mc.replies.clear();
                    return false;
                }
                if (std::find(mc.replies.begin(), mc.replies.end(), cid) == mc.replies.end()) {
                    mc.replies.push_back(cid);
                }
            }
            for (uint32_t cid : mc.replies) {
                or_nodes_[cid].parents.push_back({u, midx});
            }
            mc.replies_materialized = true;
        } else {
            for (uint32_t cid : mc.replies) {
                if (or_nodes_[cid].status == ST_DISPROVED) {
                    mc.disproved = true;
                    return false;
                }
            }
        }
        return true;
    }

    // Select next best non-disproved move for `u`. Returns false if none remain.
    bool select_best_move(uint32_t u) {
        OrNode& node = or_nodes_[u];
        for (int16_t i = 0; i < static_cast<int16_t>(node.moves.size()); ++i) {
            if (node.moves[i].disproved) continue;
            if (materialize_move(u, i)) {
                node.chosen_idx = i;
                node.status = ST_HAS_MOVE;
                return true;
            }
        }
        node.chosen_idx = -1;
        return false;
    }

    void propagate_disproved(uint32_t start_u) {
        std::queue<uint32_t> q;
        if (or_nodes_[start_u].status != ST_DISPROVED) {
            or_nodes_[start_u].status = ST_DISPROVED;
            or_nodes_[start_u].chosen_idx = -1;
        }
        q.push(start_u);
        dirty_active_ = true;

        while (!q.empty()) {
            uint32_t v = q.front();
            q.pop();
            // Copy parents because select_best_move may grow or_nodes_
            auto parents = or_nodes_[v].parents;
            for (auto [p, midx] : parents) {
                if (or_nodes_[p].status == ST_DISPROVED) continue;
                or_nodes_[p].moves[midx].disproved = true;
                if (or_nodes_[p].chosen_idx == midx) {
                    if (!select_best_move(p)) {
                        or_nodes_[p].status = ST_DISPROVED;
                        q.push(p);
                    }
                }
            }
        }
    }

    // Mini df-pn refutation check: does opponent (`~prover_`) have a quick forced mate from `pos`?
    bool quick_opponent_mate_check(const Position& pos, uint64_t node_budget) {
        SolveLimits sub;
        sub.max_nodes = std::min<uint64_t>(node_budget, (limits_.max_nodes > nodes_) ? (limits_.max_nodes - nodes_) : uint64_t{1});
        double rem_sec = std::max(0.01, limits_.max_seconds - timer_.elapsed());
        sub.max_seconds = std::min(0.25, rem_sec);
        sub.minimize = false;
        SolveStats sst;
        SolveStatus rs = refute_solver_.solve_win(pos, ~prover_, sub, nullptr, &sst);
        nodes_ += sst.nodes;
        return (rs == SolveStatus::PROVED);
    }

    void expand_node(uint32_t u) {
        ++nodes_;
        // Copy pos because get_or_create may reallocate or_nodes_
        Position pos = or_nodes_[u].pos;

        Move mbuf[MAX_MOVES];
        int nm = pos.legal_moves(mbuf);
        if (nm == 0) {
            if (pos.in_check()) {
                propagate_disproved(u);
            } else {
                or_nodes_[u].status = ST_PROVED_SAFE;
            }
            return;
        }

        // If position looks tactically dangerous (negative eval or in check), run a tiny df-pn
        // refutation check to catch forced opponent mates early before expanding!
        if (!or_nodes_[u].refutation_checked &&
            (or_nodes_[u].eval <= -250 || (pos.in_check() && or_nodes_[u].depth >= 2))) {
            or_nodes_[u].refutation_checked = true;
            if (quick_opponent_mate_check(pos, 1200)) {
                propagate_disproved(u);
                return;
            }
        }

        // Evaluate every legal move at `u`.
        std::vector<MoveChoice> choices;
        choices.reserve(static_cast<size_t>(nm));
        Move rbuf[MAX_MOVES];

        for (int i = 0; i < nm; ++i) {
            Move m = mbuf[i];
            Position q = pos.make_move(m);
            int nr = q.legal_moves(rbuf);

            // Immediate opponent checkmate or stalemate -> closes branch with 0 children!
            if (nr == 0) {
                MoveChoice mc;
                mc.move = m;
                mc.replies_materialized = true;
                mc.score = 2000000;
                mc.eval = q.in_check() ? MATE_SCORE : 0;
                choices.clear();
                choices.push_back(std::move(mc));
                break;
            }

            bool bad = false;
            int in_active = 0;
            int in_known = 0;
            int new_cnt = 0;
            int stale_cnt = 0;

            for (int j = 0; j < nr; ++j) {
                Position qr = q.make_move(rbuf[j]);
                if (!qr.has_legal_moves()) {
                    if (qr.in_check()) {
                        bad = true; // opponent mates in 1!
                        break;
                    }
                    ++stale_cnt;
                    continue;
                }
                int32_t cid = lookup_id(qr);
                if (cid >= 0) {
                    if (or_nodes_[cid].status == ST_DISPROVED) {
                        bad = true;
                        break;
                    }
                    if (is_active(static_cast<uint32_t>(cid)) || or_nodes_[cid].status == ST_PROVED_SAFE) {
                        ++in_active;
                    } else {
                        ++in_known;
                        ++new_cnt;
                    }
                } else {
                    ++new_cnt;
                }
            }
            if (bad) continue;

            // Depth-2 exact alpha-beta on q (checks mate-in-2 against prover + tactical material safety).
            // Only do depth-2 when branching is small or medium; depth-1 on huge 8x8 moves.
            int ab_depth = (pos.width() * pos.height() <= 25) ? 2 : 1;
            int ev = ab_eval(q, prover_, ab_depth, -MATE_SCORE - 100, MATE_SCORE + 100, nodes_);
            if (ev <= -MATE_THRESH) {
                // Exact alpha-beta proved opponent has a forced mate!
                continue;
            }

            MoveChoice mc;
            mc.move = m;
            mc.eval = ev;
            if (new_cnt == 0) {
                // Total closure into active_set / prover-stalemate!
                mc.score = 1000000 + ev + stale_cnt * 100;
            } else {
                // Balance tactical safety, low frontier growth, and merging into active_set.
                int score = ev;
                score -= new_cnt * 130;
                score += in_active * 100;
                score += in_known * 25;
                score += stale_cnt * 120;
                if (q.in_check()) score += 120;
                // Strongly penalize moves that look tactically losing
                if (ev < -350) score -= (-350 - ev) * 2;
                mc.score = score;
            }
            choices.push_back(std::move(mc));
        }

        if (choices.empty()) {
            propagate_disproved(u);
            return;
        }

        std::sort(choices.begin(), choices.end(), [](const MoveChoice& a, const MoveChoice& b) {
            return a.score > b.score;
        });

        or_nodes_[u].moves = std::move(choices);
        or_nodes_[u].expanded = true;

        if (!select_best_move(u)) {
            propagate_disproved(u);
            return;
        }

        // Add newly reached children of chosen move to active_set & frontier incrementally.
        int16_t cidx = or_nodes_[u].chosen_idx;
        auto replies = or_nodes_[u].moves[cidx].replies;
        for (uint32_t cid : replies) {
            if (!is_active(cid)) {
                active_stamp_[cid] = cur_stamp_;
                active_list_.push_back(cid);
                if (or_nodes_[cid].status == ST_OPEN) {
                    push_frontier(cid);
                } else if (or_nodes_[cid].status == ST_HAS_MOVE) {
                    // Re-entered a previously expanded inactive node; its descendants need active mark.
                    dirty_active_ = true;
                }
            }
        }
    }

    // Periodic shortcut pass: for active nodes whose current chosen move still has an OPEN reply,
    // check if any other non-disproved move has ALL replies in already-expanded active nodes!
    bool try_shortcut_collapse() {
        bool changed = false;
        Move rbuf[MAX_MOVES];
        for (uint32_t u : active_list_) {
            if (or_nodes_[u].status != ST_HAS_MOVE) continue;
            int16_t cur = or_nodes_[u].chosen_idx;
            bool cur_has_open = false;
            for (uint32_t v : or_nodes_[u].moves[cur].replies) {
                if (or_nodes_[v].status == ST_OPEN) {
                    cur_has_open = true;
                    break;
                }
            }
            if (!cur_has_open) continue;

            Position pos = or_nodes_[u].pos;
            for (int16_t i = 0; i < static_cast<int16_t>(or_nodes_[u].moves.size()); ++i) {
                if (i == cur || or_nodes_[u].moves[i].disproved) continue;
                Position q = pos.make_move(or_nodes_[u].moves[i].move);
                int nr = q.legal_moves(rbuf);
                bool all_closed_active = true;
                for (int j = 0; j < nr; ++j) {
                    Position qr = q.make_move(rbuf[j]);
                    if (!qr.has_legal_moves()) {
                        if (qr.in_check()) {
                            all_closed_active = false;
                            break;
                        }
                        continue; // prover stalemate
                    }
                    int32_t cid = lookup_id(qr);
                    if (cid < 0 || !is_active(static_cast<uint32_t>(cid)) ||
                        or_nodes_[cid].status == ST_OPEN ||
                        or_nodes_[cid].status == ST_DISPROVED) {
                        all_closed_active = false;
                        break;
                    }
                }
                if (all_closed_active) {
                    if (materialize_move(u, i)) {
                        or_nodes_[u].chosen_idx = i;
                        changed = true;
                        break;
                    }
                }
            }
        }
        return changed;
    }

    SolveStatus extract_and_finish(Certificate* cert_out, SolveStats& st) {
        if (!cert_out) {
            st.raw_entries = active_list_.size();
            st.pruned_entries = active_list_.size();
            st.min_entries = active_list_.size();
            return SolveStatus::PROVED;
        }

        cert_out->claim = Claim{ClaimKind::ATLEAST_DRAW, prover_};
        cert_out->root = root_;
        cert_out->root_fen = root_.to_fen();
        cert_out->entries.clear();

        // Include ALL expanded HAS_MOVE nodes that have closed replies (or just all active_list_).
        // Actually, active_list_ is the raw closed set found by the search before minimisation;
        // also include any extra already-expanded HAS_MOVE nodes? No — in a valid raw certificate
        // every entry in the file must be valid (SPEC section 4 verifies EVERY entry).
        // active_list_ is guaranteed 100% closed!
        for (uint32_t u : active_list_) {
            const OrNode& node = or_nodes_[u];
            if (node.status == ST_PROVED_SAFE) continue; // prover stalemate needs no entry
            if (node.status != ST_HAS_MOVE || node.chosen_idx < 0) {
                st.note = "internal error: non-closed active node";
                return SolveStatus::ERROR;
            }
            CertEntry e;
            e.pos = node.pos;
            e.fen = node.pos.to_fen();
            e.move = node.moves[node.chosen_idx].move;
            e.rank = 0;
            cert_out->entries[e.fen] = std::move(e);
        }

        st.raw_entries = cert_out->size();
        st.pruned_entries = st.raw_entries;
        st.min_entries = st.raw_entries;

        std::string verr;
        if (!cert_out->verify(&verr)) {
            st.note = "raw draw cert verify failed: " + verr;
            return SolveStatus::ERROR;
        }

        if (limits_.minimize) {
            cert_out->minimize(&st.raw_entries, &st.pruned_entries, &st.min_entries);
            if (!cert_out->verify(&verr)) {
                st.note = "minimized draw cert verify failed: " + verr;
                return SolveStatus::ERROR;
            }
        }
        st.max_rank = 0;
        return SolveStatus::PROVED;
    }

    Position root_;
    Color prover_;
    SolveLimits limits_;
    Timer& timer_;
    uint64_t& nodes_;
    DfpnSolver refute_solver_;
    size_t max_graph_nodes_ = 100000;

    std::deque<OrNode> or_nodes_;
    std::unordered_map<uint64_t, std::vector<uint32_t>> hash_buckets_;
    std::vector<uint32_t> root_targets_;

    std::vector<uint32_t> active_stamp_;
    uint32_t cur_stamp_ = 0;
    std::vector<uint32_t> active_list_;
    bool dirty_active_ = false;

    using PQItem = std::pair<int, uint32_t>;
    std::priority_queue<PQItem, std::vector<PQItem>, std::greater<PQItem>> frontier_pq_;
};

} // namespace

SolveStatus DrawSolver::solve_atleast_draw(const Position& root,
                                           Color prover,
                                           const SolveLimits& limits,
                                           Certificate* cert_out,
                                           SolveStats* stats_out) {
    Timer timer;
    uint64_t total_nodes = 0;
    SolveStats st;

    // Quick terminal checks at root before allocating anything.
    if (root.side_to_move() == prover) {
        if (!root.has_legal_moves()) {
            st.seconds = timer.elapsed();
            if (root.in_check()) {
                if (stats_out) *stats_out = st;
                return SolveStatus::DISPROVED;
            }
            if (cert_out) {
                cert_out->claim = Claim{ClaimKind::ATLEAST_DRAW, prover};
                cert_out->root = root;
                cert_out->root_fen = root.to_fen();
                cert_out->entries.clear();
            }
            if (stats_out) *stats_out = st;
            return SolveStatus::PROVED;
        }
    } else if (!root.has_legal_moves()) {
        st.seconds = timer.elapsed();
        if (cert_out) {
            cert_out->claim = Claim{ClaimKind::ATLEAST_DRAW, prover};
            cert_out->root = root;
            cert_out->root_fen = root.to_fen();
            cert_out->entries.clear();
        }
        if (stats_out) *stats_out = st;
        return SolveStatus::PROVED;
    }

    // Phase 1: Quick bounded df-pn probes for WIN <prover> and WIN <~prover>.
    // A forced mate for prover immediately proves ATLEAST_DRAW <prover>;
    // a forced mate for ~prover immediately disproves ATLEAST_DRAW <prover>!
    {
        size_t probe_tt = std::clamp<size_t>(limits.tt_mb / 4, 8, 64);
        DfpnSolver probe(probe_tt);

        SolveLimits p_lim = limits;
        p_lim.max_nodes = std::min<uint64_t>(limits.max_nodes / 10 + 1, 100000ULL);
        p_lim.max_seconds = std::min(limits.max_seconds * 0.08, 2.0);

        SolveStats pst;
        Certificate win_cert;
        SolveStatus ws = probe.solve_win(root, prover, p_lim, cert_out ? &win_cert : nullptr, &pst);
        total_nodes += pst.nodes;
        if (ws == SolveStatus::PROVED) {
            if (cert_out) {
                win_cert.convert_win_to_draw();
                if (limits.minimize) {
                    size_t r2 = 0, p2 = 0, f2 = 0;
                    win_cert.minimize(&r2, &p2, &f2);
                    st.raw_entries = pst.raw_entries;
                    st.pruned_entries = p2;
                    st.min_entries = f2;
                } else {
                    st.raw_entries = st.pruned_entries = st.min_entries = win_cert.size();
                }
                *cert_out = std::move(win_cert);
            }
            st.nodes = total_nodes;
            st.seconds = timer.elapsed();
            st.max_rank = 0;
            st.note = "proved via WIN " + std::string(1, prover == WHITE ? 'w' : 'b');
            if (stats_out) *stats_out = st;
            return SolveStatus::PROVED;
        }

        // Probe WIN <~prover> (if proved, ATLEAST_DRAW <prover> is DISPROVED!)
        if (timer.elapsed() < limits.max_seconds && total_nodes < limits.max_nodes) {
            probe.clear();
            SolveLimits o_lim = p_lim;
            o_lim.max_nodes = std::min(o_lim.max_nodes, limits.max_nodes - total_nodes);
            o_lim.max_seconds = std::min(o_lim.max_seconds, std::max(0.01, limits.max_seconds - timer.elapsed()));
            SolveStats ost;
            SolveStatus os = probe.solve_win(root, ~prover, o_lim, nullptr, &ost);
            total_nodes += ost.nodes;
            if (os == SolveStatus::PROVED) {
                st.nodes = total_nodes;
                st.seconds = timer.elapsed();
                st.note = "disproved via WIN " + std::string(1, (~prover) == WHITE ? 'w' : 'b');
                if (stats_out) *stats_out = st;
                return SolveStatus::DISPROVED;
            }
        }
    }

    // Phase 2: Closed-Set Invariant Search (quick budget for small/fortress draws).
    if (timer.elapsed() < limits.max_seconds && total_nodes < limits.max_nodes) {
        SolveLimits css_lim = limits;
        double rem_t = std::max(0.01, limits.max_seconds - timer.elapsed());
        uint64_t rem_n = limits.max_nodes - total_nodes;
        // Allocate up to 25% of remaining time (capped at 4s) so simple draws close tiny and fast,
        // while leaving the bulk of the budget for full df-pn disproof search on tactical positions.
        css_lim.max_seconds = std::min(rem_t * 0.25, 4.0);
        css_lim.max_nodes = std::min<uint64_t>(rem_n / 4 + 1, uint64_t{500000});
        Timer css_timer;
        uint64_t css_nodes = 0;
        ClosedSetSearch css(root, prover, css_lim, css_timer, css_nodes);
        SolveStatus cs = css.run(cert_out, st);
        total_nodes += css_nodes;
        if (cs == SolveStatus::PROVED || cs == SolveStatus::DISPROVED || cs == SolveStatus::ERROR) {
            st.nodes = total_nodes;
            st.seconds = timer.elapsed();
            if (cs == SolveStatus::PROVED && st.note.empty()) {
                st.note = "proved via closed-set invariant search";
            }
            if (stats_out) *stats_out = st;
            return cs;
        }
    }

    // Phase 3: Full-budget df-pn disproof witness search (runs df-pn on WIN <~prover> and
    // extracts a closed ATLEAST_DRAW <prover> certificate if WIN <~prover> is disproved).
    if (timer.elapsed() < limits.max_seconds && total_nodes < limits.max_nodes) {
        SolveLimits df_lim = limits;
        df_lim.max_seconds = std::max(0.01, limits.max_seconds - timer.elapsed());
        df_lim.max_nodes = limits.max_nodes - total_nodes;
        DfpnSolver df(limits.tt_mb);
        SolveStats dst;
        SolveStatus ds = df.solve_draw_via_disproof(root, prover, df_lim, cert_out, &dst);
        total_nodes += dst.nodes;
        dst.nodes = total_nodes;
        dst.seconds = timer.elapsed();
        if (stats_out) *stats_out = dst;
        return ds;
    }

    st.nodes = total_nodes;
    st.seconds = timer.elapsed();
    if (stats_out) *stats_out = st;
    return SolveStatus::LIMIT;
}

} // namespace msolve
