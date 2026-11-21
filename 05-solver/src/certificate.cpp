#include "certificate.hpp"

#include <algorithm>
#include <fstream>
#include <queue>
#include <sstream>
#include <unordered_set>

namespace msolve {

bool Certificate::verify(std::string* err) const {
    auto fail = [&](const std::string& msg) {
        if (err) *err = msg;
        return false;
    };

    if (root_fen != root.to_fen()) {
        return fail("root_fen is not canonical");
    }

    // Check root condition
    if (root.side_to_move() == claim.prover) {
        if (entries.find(root_fen) == entries.end()) {
            if (!(claim.kind == ClaimKind::ATLEAST_DRAW && is_prover_stalemate(root, claim.prover))) {
                return fail("root position missing from entries");
            }
        }
    } else {
        Move replies[MAX_MOVES];
        int n = root.legal_moves(replies);
        if (claim.kind == ClaimKind::WIN && n == 0) {
            if (!root.in_check()) {
                return fail("opponent stalemated at root in WIN cert");
            }
        }
        for (int i = 0; i < n; ++i) {
            Position rp = root.make_move(replies[i]);
            std::string rfen = rp.to_fen();
            if (entries.find(rfen) == entries.end()) {
                if (!(claim.kind == ClaimKind::ATLEAST_DRAW && is_prover_stalemate(rp, claim.prover))) {
                    return fail("root reply missing: " + replies[i].to_string() + " -> " + rfen);
                }
            }
        }
    }

    // Check every entry
    Move buf[MAX_MOVES];
    for (const auto& kv : entries) {
        const std::string& fen = kv.first;
        const CertEntry& e = kv.second;
        if (e.fen != fen || e.pos.to_fen() != fen) {
            return fail("non-canonical entry FEN: " + fen);
        }
        if (e.pos.width() != root.width() || e.pos.height() != root.height()) {
            return fail("board size mismatch at " + fen);
        }
        if (e.pos.side_to_move() != claim.prover) {
            return fail("wrong stm at " + fen);
        }
        if (claim.kind == ClaimKind::ATLEAST_DRAW && e.rank != 0) {
            return fail("nonzero rank in ATLEAST_DRAW at " + fen);
        }

        // Verify move legality
        int nm = e.pos.legal_moves(buf);
        bool legal = false;
        for (int i = 0; i < nm; ++i) {
            if (buf[i] == e.move) {
                legal = true;
                break;
            }
        }
        if (!legal) {
            return fail("illegal move " + e.move.to_string() + " at " + fen);
        }

        Position q = e.pos.make_move(e.move);
        int nr = q.legal_moves(buf);
        if (claim.kind == ClaimKind::WIN) {
            if (nr == 0) {
                if (!q.in_check()) {
                    return fail("move leads to stalemate in WIN cert at " + fen);
                }
            } else {
                for (int i = 0; i < nr; ++i) {
                    Position qr = q.make_move(buf[i]);
                    std::string qrfen = qr.to_fen();
                    auto it = entries.find(qrfen);
                    if (it == entries.end()) {
                        return fail("missing reply " + buf[i].to_string() + " -> " + qrfen + " from " + fen);
                    }
                    if (!(it->second.rank < e.rank)) {
                        return fail("rank not strictly decreasing at " + fen + " -> " + qrfen);
                    }
                }
            }
        } else {
            for (int i = 0; i < nr; ++i) {
                Position qr = q.make_move(buf[i]);
                std::string qrfen = qr.to_fen();
                if (entries.find(qrfen) == entries.end() && !is_prover_stalemate(qr, claim.prover)) {
                    return fail("uncovered reply " + buf[i].to_string() + " -> " + qrfen + " from " + fen);
                }
            }
        }
    }
    return true;
}

bool Certificate::write_to_file(const std::string& path, std::string* err) const {
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        if (err) *err = "cannot open output file: " + path;
        return false;
    }

    // Deterministic ordering: descending rank, then canonical FEN.
    std::vector<const CertEntry*> ordered;
    ordered.reserve(entries.size());
    for (const auto& kv : entries) {
        ordered.push_back(&kv.second);
    }
    std::sort(ordered.begin(), ordered.end(), [](const CertEntry* a, const CertEntry* b) {
        if (a->rank != b->rank) return a->rank > b->rank;
        return a->fen < b->fen;
    });

    out << "#cert v1\n";
    out << "#claim " << claim.to_string() << "\n";
    out << "#root " << root_fen << "\n";
    for (const CertEntry* e : ordered) {
        out << e->fen << '\t' << e->move.to_string() << '\t' << e->rank << '\n';
    }
    if (!out.good()) {
        if (err) *err = "write error on " + path;
        return false;
    }
    return true;
}

void Certificate::convert_win_to_draw() {
    claim.kind = ClaimKind::ATLEAST_DRAW;
    for (auto& kv : entries) {
        kv.second.rank = 0;
    }
}

namespace {

// Indexed representation of the certificate entries for fast graph minimisation.
struct MinGraph {
    Claim claim;
    std::vector<CertEntry> nodes;
    std::unordered_map<std::string, int> fen_to_id;
    std::vector<int> root_ids;
    // For each node i, current outgoing children (entry IDs) under nodes[i].move.
    std::vector<std::vector<int>> adj;

    void build_adj_for(int id) {
        adj[id].clear();
        Position q = nodes[id].pos.make_move(nodes[id].move);
        Move buf[MAX_MOVES];
        int nr = q.legal_moves(buf);
        for (int i = 0; i < nr; ++i) {
            Position qr = q.make_move(buf[i]);
            auto it = fen_to_id.find(qr.to_fen());
            if (it != fen_to_id.end()) {
                adj[id].push_back(it->second);
            }
        }
        std::sort(adj[id].begin(), adj[id].end());
        adj[id].erase(std::unique(adj[id].begin(), adj[id].end()), adj[id].end());
    }

    // Compute reachability mask from root_ids.
    std::vector<uint8_t> compute_reachable(int& count_out) const {
        std::vector<uint8_t> vis(nodes.size(), 0);
        std::queue<int> q;
        count_out = 0;
        for (int r : root_ids) {
            if (!vis[r]) {
                vis[r] = 1;
                q.push(r);
                ++count_out;
            }
        }
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            for (int v : adj[u]) {
                if (!vis[v]) {
                    vis[v] = 1;
                    q.push(v);
                    ++count_out;
                }
            }
        }
        return vis;
    }

    // Check if `target` is reachable from any node in `starts` following current `adj`.
    bool can_reach(const std::vector<int>& starts, int target, const std::vector<uint8_t>& active) const {
        std::vector<uint8_t> vis(nodes.size(), 0);
        std::queue<int> q;
        for (int s : starts) {
            if (s == target) return true;
            if (active[s] && !vis[s]) {
                vis[s] = 1;
                q.push(s);
            }
        }
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            for (int v : adj[u]) {
                if (v == target) return true;
                if (active[v] && !vis[v]) {
                    vis[v] = 1;
                    q.push(v);
                }
            }
        }
        return false;
    }

    // Count reachable nodes from root_ids if node `mod_u` used `alt_children` instead of `adj[mod_u]`.
    int count_reachable_with_override(int mod_u, const std::vector<int>& alt_children) const {
        std::vector<uint8_t> vis(nodes.size(), 0);
        std::queue<int> q;
        int cnt = 0;
        for (int r : root_ids) {
            if (!vis[r]) {
                vis[r] = 1;
                q.push(r);
                ++cnt;
            }
        }
        while (!q.empty()) {
            int u = q.front();
            q.pop();
            const auto& nbrs = (u == mod_u) ? alt_children : adj[u];
            for (int v : nbrs) {
                if (!vis[v]) {
                    vis[v] = 1;
                    q.push(v);
                    ++cnt;
                }
            }
        }
        return cnt;
    }

    // Recompute exact minimal ranks for a WIN DAG via DFS postorder.
    void recompute_win_ranks(const std::vector<uint8_t>& active) {
        std::vector<uint32_t> rank(nodes.size(), 0);
        std::vector<uint8_t> state(nodes.size(), 0); // 0=unvis, 1=visiting, 2=done

        auto dfs = [&](auto&& self, int u) -> uint32_t {
            if (state[u] == 2) return rank[u];
            state[u] = 1;
            uint32_t max_child = 0;
            for (int v : adj[u]) {
                uint32_t r = self(self, v);
                if (r > max_child) max_child = r;
            }
            rank[u] = max_child + 1;
            state[u] = 2;
            return rank[u];
        };

        for (size_t i = 0; i < nodes.size(); ++i) {
            if (active[i]) {
                nodes[i].rank = dfs(dfs, static_cast<int>(i));
            }
        }
    }
};

} // namespace

void Certificate::minimize(size_t* raw_size, size_t* pruned_size, size_t* final_size) {
    if (raw_size) *raw_size = entries.size();
    if (entries.empty()) {
        if (pruned_size) *pruned_size = 0;
        if (final_size) *final_size = 0;
        return;
    }

    MinGraph g;
    g.claim = claim;
    g.nodes.reserve(entries.size());
    for (const auto& kv : entries) {
        int id = static_cast<int>(g.nodes.size());
        g.fen_to_id[kv.first] = id;
        g.nodes.push_back(kv.second);
    }

    if (root.side_to_move() == claim.prover) {
        auto it = g.fen_to_id.find(root_fen);
        if (it != g.fen_to_id.end()) g.root_ids.push_back(it->second);
    } else {
        Move buf[MAX_MOVES];
        int nr = root.legal_moves(buf);
        for (int i = 0; i < nr; ++i) {
            Position rp = root.make_move(buf[i]);
            auto it = g.fen_to_id.find(rp.to_fen());
            if (it != g.fen_to_id.end()) g.root_ids.push_back(it->second);
        }
    }

    g.adj.resize(g.nodes.size());
    for (size_t i = 0; i < g.nodes.size(); ++i) {
        g.build_adj_for(static_cast<int>(i));
    }

    // Pass 1: Reachability pruning
    int active_count = 0;
    std::vector<uint8_t> active = g.compute_reachable(active_count);
    if (pruned_size) *pruned_size = static_cast<size_t>(active_count);

    // Pass 2: Iterative strategy rewriting to merge moves into existing active entries.
    // For moderate graphs (<= 3000 active nodes), test exact reachability reduction per candidate move.
    // For larger graphs, use fast local heuristic (prefer immediate leaves / subset-of-other-reachable / lower degree).
    const bool exact_mode = (active_count <= 3000);
    const int max_passes = exact_mode ? 8 : 3;

    Move mbuf[MAX_MOVES];
    Move rbuf[MAX_MOVES];

    for (int pass = 0; pass < max_passes; ++pass) {
        bool improved = false;

        // Compute in-degrees among active nodes for fast heuristic in large graphs.
        std::vector<int> indeg(g.nodes.size(), 0);
        for (int r : g.root_ids) {
            if (active[r]) indeg[r] += 1;
        }
        for (size_t u = 0; u < g.nodes.size(); ++u) {
            if (!active[u]) continue;
            for (int v : g.adj[u]) {
                if (active[v]) indeg[v] += 1;
            }
        }

        // Process active nodes (BFS order from root tends to collapse big subtrees early).
        std::vector<int> order;
        order.reserve(static_cast<size_t>(active_count));
        {
            std::vector<uint8_t> vis(g.nodes.size(), 0);
            std::queue<int> q;
            for (int r : g.root_ids) {
                if (active[r] && !vis[r]) {
                    vis[r] = 1;
                    q.push(r);
                }
            }
            while (!q.empty()) {
                int u = q.front();
                q.pop();
                order.push_back(u);
                for (int v : g.adj[u]) {
                    if (active[v] && !vis[v]) {
                        vis[v] = 1;
                        q.push(v);
                    }
                }
            }
        }

        for (int u : order) {
            if (!active[u]) continue; // may have become unreachable earlier in this pass
            // If current move already has 0 children (immediate mate / stalemate), cannot improve size.
            if (g.adj[u].empty()) continue;

            int nm = g.nodes[u].pos.legal_moves(mbuf);
            if (nm <= 1) continue;

            // Current exclusive children count (used in non-exact mode)
            int cur_excl = 0;
            for (int v : g.adj[u]) {
                if (indeg[v] <= 1) ++cur_excl;
            }

            Move best_m = g.nodes[u].move;
            std::vector<int> best_children = g.adj[u];
            int best_reach = active_count;
            int best_excl = cur_excl;
            size_t best_deg = g.adj[u].size();

            for (int i = 0; i < nm; ++i) {
                Move m = mbuf[i];
                if (m == g.nodes[u].move) continue;

                Position q = g.nodes[u].pos.make_move(m);
                int nr = q.legal_moves(rbuf);

                if (claim.kind == ClaimKind::WIN && nr == 0 && !q.in_check()) {
                    continue; // stalemate is invalid in WIN
                }

                bool all_covered = true;
                std::vector<int> cand_children;
                cand_children.reserve(static_cast<size_t>(nr));

                for (int j = 0; j < nr; ++j) {
                    Position qr = q.make_move(rbuf[j]);
                    auto it = g.fen_to_id.find(qr.to_fen());
                    if (it != g.fen_to_id.end() && active[it->second]) {
                        cand_children.push_back(it->second);
                    } else if (claim.kind == ClaimKind::ATLEAST_DRAW &&
                               is_prover_stalemate(qr, claim.prover)) {
                        // covered without entry
                    } else {
                        all_covered = false;
                        break;
                    }
                }
                if (!all_covered) continue;

                std::sort(cand_children.begin(), cand_children.end());
                cand_children.erase(std::unique(cand_children.begin(), cand_children.end()), cand_children.end());

                // For WIN, ensure no cycle is created!
                if (claim.kind == ClaimKind::WIN && !cand_children.empty()) {
                    if (g.can_reach(cand_children, u, active)) {
                        continue;
                    }
                }

                if (exact_mode) {
                    int new_reach = g.count_reachable_with_override(u, cand_children);
                    if (new_reach < best_reach ||
                        (new_reach == best_reach && cand_children.size() < best_deg)) {
                        best_reach = new_reach;
                        best_deg = cand_children.size();
                        best_m = m;
                        best_children = std::move(cand_children);
                    }
                } else {
                    // Fast heuristic for huge graphs: prefer fewer exclusive children (or immediate leaf!)
                    // Wait: a node v in cand_children might only have indeg == 1 if u was its sole parent before,
                    // otherwise if v was NOT in g.adj[u], its indeg >= 1 already means another node reaches it!
                    int cand_excl = 0;
                    for (int v : cand_children) {
                        bool was_child = std::binary_search(g.adj[u].begin(), g.adj[u].end(), v);
                        if (was_child && indeg[v] <= 1) ++cand_excl;
                    }
                    if (cand_children.empty() ||
                        cand_excl < best_excl ||
                        (cand_excl == best_excl && cand_children.size() < best_deg)) {
                        best_excl = cand_excl;
                        best_deg = cand_children.size();
                        best_m = m;
                        best_children = std::move(cand_children);
                    }
                }
            }

            if (best_m != g.nodes[u].move) {
                g.nodes[u].move = best_m;
                g.adj[u] = std::move(best_children);
                improved = true;
                if (exact_mode) {
                    active = g.compute_reachable(active_count);
                }
            }
        }

        if (!exact_mode && improved) {
            active = g.compute_reachable(active_count);
        }
        if (!improved) break;
    }

    // Recompute exact minimal ranks for WIN certificates.
    if (claim.kind == ClaimKind::WIN) {
        g.recompute_win_ranks(active);
    }

    // Rebuild entries map with only active nodes.
    entries.clear();
    for (size_t i = 0; i < g.nodes.size(); ++i) {
        if (active[i]) {
            if (claim.kind == ClaimKind::ATLEAST_DRAW) {
                g.nodes[i].rank = 0;
            }
            entries.emplace(g.nodes[i].fen, std::move(g.nodes[i]));
        }
    }

    if (final_size) *final_size = entries.size();
}

} // namespace msolve
