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

namespace {

bool parse_strict_rank(std::string_view s, uint32_t& out) {
    if (s.empty()) return false;
    if (s.size() > 1 && s[0] == '0') return false; // no leading zeros
    uint64_t v = 0;
    for (char c : s) {
        if (c < '0' || c > '9') return false;
        v = v * 10ULL + static_cast<uint64_t>(c - '0');
        if (v > 0xFFFFFFFFULL) return false;
    }
    out = static_cast<uint32_t>(v);
    return true;
}

} // namespace

bool Certificate::load_from_file(const std::string& path, Certificate& out, std::string* err) {
    auto fail = [&](const std::string& msg) {
        if (err) *err = path + ": " + msg;
        return false;
    };

    std::ifstream in(path, std::ios::binary);
    if (!in) return fail("cannot open file");

    std::string content((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (in.bad()) return fail("read error");

    // SPEC v1.2: carriage return anywhere makes the certificate invalid.
    if (content.find('\r') != std::string::npos) {
        return fail("carriage return (CR) found in file");
    }

    std::vector<std::string_view> lines;
    size_t pos = 0;
    while (pos < content.size()) {
        size_t nl = content.find('\n', pos);
        if (nl == std::string::npos) {
            lines.emplace_back(content.data() + pos, content.size() - pos);
            break;
        }
        lines.emplace_back(content.data() + pos, nl - pos);
        pos = nl + 1;
    }

    if (lines.size() < 3) return fail("missing header lines");
    if (lines[0] != "#cert v1") return fail("invalid header line 1 (expected '#cert v1')");

    // Line 2: #claim <WIN|ATLEAST_DRAW> <w|b>
    Claim cl;
    {
        std::string_view l2 = lines[1];
        if (l2 == "#claim WIN w") { cl = Claim{ClaimKind::WIN, WHITE}; }
        else if (l2 == "#claim WIN b") { cl = Claim{ClaimKind::WIN, BLACK}; }
        else if (l2 == "#claim ATLEAST_DRAW w") { cl = Claim{ClaimKind::ATLEAST_DRAW, WHITE}; }
        else if (l2 == "#claim ATLEAST_DRAW b") { cl = Claim{ClaimKind::ATLEAST_DRAW, BLACK}; }
        else return fail("invalid #claim header: " + std::string(l2));
    }

    // Line 3: #root <position string>
    std::string_view l3 = lines[2];
    if (l3.substr(0, 6) != "#root ") return fail("invalid #root header");
    std::string_view root_sv = l3.substr(6);
    Position root_pos;
    std::string perr;
    if (!Position::parse(root_sv, root_pos, &perr)) {
        return fail("invalid root position: " + perr);
    }
    std::string root_canon = root_pos.to_fen();
    if (root_canon != root_sv) {
        return fail("non-canonical root position");
    }

    Certificate cert;
    cert.claim = cl;
    cert.root = root_pos;
    cert.root_fen = root_canon;
    cert.entries.reserve(lines.size() > 3 ? (lines.size() - 3) : 0);

    for (size_t i = 3; i < lines.size(); ++i) {
        std::string_view line = lines[i];
        if (line.empty()) return fail("blank line at line " + std::to_string(i + 1));
        if (line[0] == '#') return fail("comment line in body at line " + std::to_string(i + 1));

        size_t t1 = line.find('\t');
        if (t1 == std::string_view::npos) return fail("missing tab at line " + std::to_string(i + 1));
        size_t t2 = line.find('\t', t1 + 1);
        if (t2 == std::string_view::npos) return fail("missing second tab at line " + std::to_string(i + 1));
        if (line.find('\t', t2 + 1) != std::string_view::npos) {
            return fail("extra tab at line " + std::to_string(i + 1));
        }

        std::string_view fen_sv = line.substr(0, t1);
        std::string_view mv_sv = line.substr(t1 + 1, t2 - (t1 + 1));
        std::string_view rk_sv = line.substr(t2 + 1);

        Position ep;
        if (!Position::parse(fen_sv, ep, &perr)) {
            return fail("invalid entry position at line " + std::to_string(i + 1) + ": " + perr);
        }
        std::string canon = ep.to_fen();
        if (canon != fen_sv) {
            return fail("non-canonical entry FEN at line " + std::to_string(i + 1));
        }
        if (ep.width() != root_pos.width() || ep.height() != root_pos.height()) {
            return fail("board size mismatch at line " + std::to_string(i + 1));
        }
        if (ep.side_to_move() != cl.prover) {
            return fail("wrong stm at line " + std::to_string(i + 1));
        }

        auto mv_opt = ep.parse_move(mv_sv);
        if (!mv_opt || mv_opt->to_string() != mv_sv) {
            return fail("illegal move '" + std::string(mv_sv) + "' at line " + std::to_string(i + 1));
        }

        uint32_t rk = 0;
        if (!parse_strict_rank(rk_sv, rk)) {
            return fail("invalid rank '" + std::string(rk_sv) + "' at line " + std::to_string(i + 1));
        }
        if (cl.kind == ClaimKind::ATLEAST_DRAW && rk != 0) {
            return fail("nonzero rank in ATLEAST_DRAW at line " + std::to_string(i + 1));
        }

        if (cert.entries.find(canon) != cert.entries.end()) {
            return fail("duplicate position at line " + std::to_string(i + 1));
        }

        CertEntry ce;
        ce.pos = ep;
        ce.fen = canon;
        ce.move = *mv_opt;
        ce.rank = rk;
        cert.entries.emplace(std::move(canon), std::move(ce));
    }

    out = std::move(cert);
    return true;
}

bool Certificate::recompute_win_ranks(std::string* err) {
    if (claim.kind != ClaimKind::WIN) return true;
    std::unordered_map<std::string, uint8_t> state; // 0=unvis, 1=visiting, 2=done
    state.reserve(entries.size());
    std::unordered_map<std::string, uint32_t> computed;
    computed.reserve(entries.size());

    bool has_cycle = false;
    std::string cycle_fen;
    Move rbuf[MAX_MOVES];

    auto dfs = [&](auto&& self, const std::string& fen) -> uint32_t {
        uint8_t st = state[fen];
        if (st == 2) return computed[fen];
        if (st == 1) {
            has_cycle = true;
            cycle_fen = fen;
            return 0;
        }
        state[fen] = 1;
        const CertEntry& e = entries.at(fen);
        Position q = e.pos.make_move(e.move);
        int nr = q.legal_moves(rbuf);
        uint32_t max_child = 0;
        for (int i = 0; i < nr; ++i) {
            Position qr = q.make_move(rbuf[i]);
            std::string qrfen = qr.to_fen();
            if (entries.find(qrfen) == entries.end()) {
                // Missing entry will be caught by verify(); return 0 here.
                continue;
            }
            uint32_t cr = self(self, qrfen);
            if (has_cycle) return 0;
            if (cr > max_child) max_child = cr;
        }
        uint32_t rk = max_child + 1;
        computed[fen] = rk;
        state[fen] = 2;
        return rk;
    };

    for (const auto& kv : entries) {
        if (state[kv.first] == 0) {
            dfs(dfs, kv.first);
            if (has_cycle) {
                if (err) *err = "cycle detected in WIN certificate at " + cycle_fen;
                return false;
            }
        }
    }

    for (auto& kv : entries) {
        kv.second.rank = computed[kv.first];
    }
    return true;
}

bool Certificate::merge(const Position& root,
                        const Claim& claim,
                        const std::vector<Certificate>& sub_certs,
                        const std::vector<std::pair<Position, Move>>& connecting_moves,
                        Certificate& out,
                        bool do_minimize,
                        size_t* raw_size,
                        size_t* pruned_size,
                        size_t* final_size,
                        std::string* err) {
    auto fail = [&](const std::string& msg) {
        if (err) *err = msg;
        return false;
    };

    Certificate merged;
    merged.claim = claim;
    merged.root = root;
    merged.root_fen = root.to_fen();

    // 1. Union all sub-certificate entries.
    // For WIN: keep strictly smaller rank on overlap (guaranteed acyclic by minimum-rank theorem).
    // For ATLEAST_DRAW: accept both ATLEAST_DRAW <prover> and WIN <prover> (ranks zeroed).
    for (size_t idx = 0; idx < sub_certs.size(); ++idx) {
        const Certificate& sc = sub_certs[idx];
        if (sc.root.width() != root.width() || sc.root.height() != root.height()) {
            return fail("sub-certificate #" + std::to_string(idx) + " board size mismatch");
        }
        if (sc.claim.prover != claim.prover) {
            return fail("sub-certificate #" + std::to_string(idx) + " prover color mismatch");
        }
        if (claim.kind == ClaimKind::WIN && sc.claim.kind != ClaimKind::WIN) {
            return fail("cannot merge ATLEAST_DRAW sub-certificate #" + std::to_string(idx) + " into WIN claim");
        }

        for (const auto& kv : sc.entries) {
            auto it = merged.entries.find(kv.first);
            if (it == merged.entries.end()) {
                CertEntry ce = kv.second;
                if (claim.kind == ClaimKind::ATLEAST_DRAW) ce.rank = 0;
                merged.entries.emplace(kv.first, std::move(ce));
            } else if (claim.kind == ClaimKind::WIN) {
                if (kv.second.rank < it->second.rank) {
                    it->second = kv.second;
                }
            }
        }
    }

    // 2. Insert/apply explicit connecting moves.
    Move lbuf[MAX_MOVES];
    for (const auto& pm : connecting_moves) {
        const Position& p = pm.first;
        Move m = pm.second;
        if (p.width() != root.width() || p.height() != root.height()) {
            return fail("connecting move board size mismatch at " + p.to_fen());
        }
        if (p.side_to_move() != claim.prover) {
            return fail("connecting move wrong side to move at " + p.to_fen());
        }
        int nm = p.legal_moves(lbuf);
        bool legal = false;
        for (int i = 0; i < nm; ++i) {
            if (lbuf[i] == m) { legal = true; break; }
        }
        if (!legal) {
            return fail("illegal connecting move " + m.to_string() + " at " + p.to_fen());
        }
        std::string fen = p.to_fen();
        CertEntry ce;
        ce.pos = p;
        ce.fen = fen;
        ce.move = m;
        ce.rank = (claim.kind == ClaimKind::WIN) ? 1U : 0U;
        merged.entries[fen] = std::move(ce);
    }

    // 3. Recompute exact WIN ranks (verifies acyclicity after connecting moves).
    if (claim.kind == ClaimKind::WIN) {
        std::string rerr;
        if (!merged.recompute_win_ranks(&rerr)) {
            return fail(rerr);
        }
    }

    // 4. Verify BEFORE minimizing (so missing replies from root or connecting moves report clearly).
    // Wait: prune unreachable entries only AFTER checking that root + all reachable entries are covered?
    // No! Every sub-cert is already valid on all its own entries, so the union + valid connecting moves
    // is ALREADY valid on all entries (even before pruning), as long as connecting moves' replies are covered!
    std::string verr;
    if (!merged.verify(&verr)) {
        return fail("merged certificate invalid: " + verr);
    }

    if (do_minimize) {
        merged.minimize(raw_size, pruned_size, final_size);
        if (!merged.verify(&verr)) {
            return fail("minimized merged certificate invalid: " + verr);
        }
    } else {
        if (raw_size) *raw_size = merged.size();
        if (pruned_size) *pruned_size = merged.size();
        if (final_size) *final_size = merged.size();
    }

    out = std::move(merged);
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
