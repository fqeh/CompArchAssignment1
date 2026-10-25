// Behavioral and independent-reference tests. Author: Ali Alfageeh.
#include <algorithm>
#include <array>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#include "branch.h"
#include "predictor.h"
#include "my_predictor.h"

#define CHECK(x) do { if (!(x)) throw std::runtime_error( \
    std::string(__func__) + ":" + std::to_string(__LINE__) + " " #x); } while (0)

static pm_update prediction(pm_predictor &p, unsigned int pc,
                            unsigned int flags = BR_CONDITIONAL) {
    branch_info b{pc, 0, flags};
    return *static_cast<pm_update *>(p.predict(b));
}
static pm_update step(pm_predictor &p, unsigned int pc, bool taken,
                      unsigned int flags = BR_CONDITIONAL) {
    pm_update u = prediction(p, pc, flags);
    p.update(&u, taken, 0);
    return u;
}
static pm_update keyed_step(pm_predictor &p, unsigned int hash, bool taken) {
    return step(p, hash ^ p.history(), taken);
}

static void initialization() {
    pm_predictor p;
    CHECK(p.history() == 0);
    for (unsigned int i = 0; i < 4096; ++i) CHECK(p.local_counter(i) == 1);
    for (unsigned int s = 0; s < 512; ++s)
        for (unsigned int w = 0; w < 2; ++w) CHECK(!p.global_entry(s,w).valid);
    CHECK(p.get_statistics().hits == 0 && p.get_statistics().misses == 0);
}
static void hash_partition() {
    pm_predictor p;
    auto u = prediction(p, 0xffffffffu);
    CHECK(u.index == 4095 && u.set == 511 && u.tag == 63);
    step(p, 0, true);
    u = prediction(p, 0x44);
    CHECK(u.index == 68 && u.set == 1 && u.tag == 5);
}
static void valid_bit_gate() {
    pm_predictor p;
    auto u = prediction(p, 0);
    CHECK(u.hit_way == -1 && !u.direction_prediction());
    CHECK(!p.global_entry(0,0).valid);  // Prediction does not allocate.
}
static void bimodal_fallback() {
    pm_predictor p;
    step(p, 0x100, true);
    auto u = prediction(p, 0x100);
    CHECK(u.hit_way == -1 && u.direction_prediction());
    CHECK(p.local_counter(0x100) == 2);
}
static void global_overrides_bimodal() {
    pm_predictor p;
    keyed_step(p, 0, true); // tag 0 becomes taken; history becomes 1.
    auto u = prediction(p, 1); // hash 0; bimodal[1] is still not taken.
    CHECK(p.local_counter(1) == 1 && u.hit_way == 0 && u.direction_prediction());
}
static void local_saturation() {
    pm_predictor p;
    for (int i = 0; i < 40; ++i) step(p, 100, true);
    CHECK(p.local_counter(100) == 3);
    for (int i = 0; i < 80; ++i) step(p, 100, false);
    CHECK(p.local_counter(100) == 0);
}
static void global_saturation() {
    pm_predictor p;
    for (int i = 0; i < 50; ++i) keyed_step(p, 0, true);
    CHECK(p.global_entry(0,0).counter == 3);
    for (int i = 0; i < 90; ++i) keyed_step(p, 0, false);
    CHECK(p.global_entry(0,0).counter == 0);
}
static void saved_indices() {
    pm_predictor p;
    step(p, 0, true);
    auto u = prediction(p, 0x7fc0); // pre-history 1 -> set511, tag1
    CHECK(u.set == 511 && u.tag == 1);
    p.update(&u, true, 0);
    CHECK(p.history() == 3);
    CHECK(p.global_entry(511,0).tag == 1);
    CHECK(p.local_counter(0xfc0) == 2);
}
static void invalid_way_first() {
    pm_predictor p;
    keyed_step(p, 1, false);
    keyed_step(p, 2, false);
    CHECK(p.global_entry(0,0).tag == 1 && p.global_entry(0,1).tag == 2);
    CHECK(p.get_statistics().replacements == 0);
}
static void lru_after_hit() {
    pm_predictor p;
    keyed_step(p, 1, false);
    keyed_step(p, 2, false);
    CHECK(p.next_victim(0) == 0);
    keyed_step(p, 1, false); // refresh way0, so evict way1 next.
    CHECK(p.next_victim(0) == 1);
    keyed_step(p, 3, false);
    CHECK(p.global_entry(0,0).tag == 1 && p.global_entry(0,1).tag == 3);
    CHECK(p.get_statistics().replacements == 1);
}
static void replacement_resets_confidence() {
    pm_predictor p;
    keyed_step(p, 1, true);
    keyed_step(p, 1, true); // counter reaches 3
    keyed_step(p, 2, false);
    keyed_step(p, 3, false); // replace tag1 with a not-taken outcome
    CHECK(p.global_entry(0,0).tag == 3 && p.global_entry(0,0).counter == 1);
}
static void history_mask() {
    pm_predictor p;
    for (int i = 0; i < 50; ++i) step(p, 0, true);
    CHECK(p.history() == 32767);
    step(p, 0, false);
    CHECK(p.history() == 32766);
    for (int i = 0; i < 15; ++i) step(p, 0, false);
    CHECK(p.history() == 0);
}
static void unconditional_bypass() {
    pm_predictor p;
    step(p, 0x80, true);
    const unsigned flags[] = {0, BR_CALL, BR_RETURN, BR_INDIRECT,
                              BR_CALL | BR_INDIRECT};
    for (auto f : flags) {
        auto u = step(p, 0x80, false, f);
        CHECK(u.direction_prediction() && !u.conditional);
        CHECK(p.history() == 1 && p.local_counter(0x80) == 2);
        CHECK(p.get_statistics().hits == 0 && p.get_statistics().misses == 1);
    }
    CHECK(p.global_entry(2,0).tag == 0 && p.global_entry(2,0).counter == 2);
}
static void combined_flags() {
    pm_predictor p;
    step(p, 0, true, BR_CONDITIONAL | BR_INDIRECT);
    CHECK(p.history() == 1 && p.get_statistics().misses == 1);
}
static void accounting_and_reset() {
    pm_predictor p;
    keyed_step(p, 1, false);
    keyed_step(p, 1, true);
    CHECK(p.get_statistics().hits == 1 && p.get_statistics().misses == 1);
    pm_predictor fresh;
    CHECK(fresh.history() == 0 && !fresh.global_entry(0,0).valid);
}

// Independent model: each set is an MRU-to-LRU vector of tag/counter pairs.
// It has no physical ways or next-victim bits and uses division/remainder.
static void randomized_reference() {
    struct RefEntry { unsigned tag, counter; };
    std::array<unsigned,4096> local;
    local.fill(1);
    std::array<std::vector<RefEntry>,512> sets;
    unsigned history = 0;
    unsigned long long hits = 0, misses = 0, replacements = 0;
    std::mt19937 random(20261025);
    pm_predictor p;
    for (unsigned n = 0; n < 250000; ++n) {
        unsigned pc = random();
        if (n % 2 == 0) pc = ((random() % 8) * 64 + random() % 4) ^ history;
        const bool conditional = random() % 11 != 0;
        const bool taken = random() % 2;
        const unsigned hash = (pc ^ history) % 32768;
        auto &set = sets[hash / 64];
        const unsigned tag = hash % 64, index = pc % 4096;
        int pos = -1;
        for (unsigned j=0; j<set.size(); ++j)
            if (set[j].tag == tag) pos = static_cast<int>(j);
        bool expected = true;
        if (conditional) expected = (pos < 0 ? local[index] : set[pos].counter) >= 2;
        auto u = prediction(p, pc, conditional ? BR_CONDITIONAL : BR_CALL);
        CHECK(u.direction_prediction() == expected);
        if (conditional) CHECK((u.hit_way >= 0) == (pos >= 0));
        p.update(&u, taken, 0);
        if (conditional) {
            local[index] = taken ? std::min(3u,local[index]+1) :
                                   (local[index] ? local[index]-1 : 0);
            RefEntry e{tag, taken ? 2u : 1u};
            if (pos >= 0) {
                ++hits;
                e = set[pos];
                e.counter = taken ? std::min(3u,e.counter+1) :
                                    (e.counter ? e.counter-1 : 0);
                set.erase(set.begin()+pos);
            } else {
                ++misses;
                if (set.size() == 2) { set.pop_back(); ++replacements; }
            }
            set.insert(set.begin(),e);
            history = (history * 2 + taken) % 32768;
            CHECK(p.local_counter(index) == local[index]);
            for (const auto &r : set) {
                bool found = false;
                for (unsigned w=0; w<2; ++w) {
                    const auto &actual = p.global_entry(hash/64,w);
                    if (actual.valid && actual.tag == r.tag) {
                        CHECK(actual.counter == r.counter);
                        found = true;
                    }
                }
                CHECK(found);
            }
            if (set.size() == 2)
                CHECK(p.global_entry(hash/64,p.next_victim(hash/64)).tag == set.back().tag);
        }
        CHECK(p.history() == history);
    }
    CHECK(p.get_statistics().hits == hits && p.get_statistics().misses == misses);
    CHECK(p.get_statistics().replacements == replacements);
}

int main() {
    const std::vector<std::pair<std::string,std::function<void()>>> tests = {
        {"initialization",initialization},{"hash_partition",hash_partition},
        {"valid_bit_gate",valid_bit_gate},{"bimodal_fallback",bimodal_fallback},
        {"global_overrides_bimodal",global_overrides_bimodal},
        {"local_saturation",local_saturation},{"global_saturation",global_saturation},
        {"saved_indices",saved_indices},{"invalid_way_first",invalid_way_first},
        {"lru_after_hit",lru_after_hit},
        {"replacement_resets_confidence",replacement_resets_confidence},
        {"history_mask",history_mask},{"unconditional_bypass",unconditional_bypass},
        {"combined_flags",combined_flags},{"accounting_and_reset",accounting_and_reset},
        {"randomized_reference_250000_events",randomized_reference}
    };
    try {
        for (const auto &t : tests) { t.second(); std::cout << "PASS " << t.first << '\n'; }
    } catch (const std::exception &e) {
        std::cerr << "FAIL " << e.what() << '\n'; return 1;
    }
    std::cout << tests.size() << " / " << tests.size() << " tests passed\n";
    std::cout << "sizeof(pm_predictor) = " << sizeof(pm_predictor) << " bytes\n";
}
