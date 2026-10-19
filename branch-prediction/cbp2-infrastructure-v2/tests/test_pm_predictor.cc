// Focused checks for the assignment's bimodal/global direction predictor.
#include <cassert>
#include <cstring>
#include <iostream>
#include "../src/branch.h"
#include "../src/predictor.h"
#include "../src/my_predictor.h"

static branch_info branch(unsigned int address, unsigned int flags = BR_CONDITIONAL) {
    branch_info b = {address, OP_JNZ, flags};
    return b;
}

// Keep the hash fixed when isolating counter and replacement behavior.
static bool step_at_history_zero(pm_predictor &p, unsigned int address, bool taken) {
    p.history = 0;
    branch_info b = branch(address);
    branch_update *prediction = p.predict(b);
    const bool result = prediction->direction_prediction();
    p.update(prediction, taken, 0);
    return result;
}

static void test_initial_state_and_hash() {
    pm_predictor p;
    assert(p.history == 0);
    for (unsigned int i = 0; i < 4096; ++i) assert(p.bimodal[i] == 1);
    for (unsigned int set = 0; set < 512; ++set) {
        assert(p.lru[set] == 0);
        for (int way = 0; way < 2; ++way) {
            assert(!p.global[set][way].valid);
            assert(p.global[set][way].counter == 1);
        }
    }

    // 0xa235 XOR 0x1234 = 0xb001; low 15 bits = 0x3001.
    // The high nine hash bits select set 192, and the low six form tag 1.
    p.history = 0x1234;
    branch_info b = branch(0xa235);
    assert(!p.predict(b)->direction_prediction());
    assert(p.u.index == 0x235);
    assert(p.u.set_index == 192);
    assert(p.u.tag == 1);
    assert(p.u.way == -1);
    assert(p.history == 0x1234); // Prediction alone does not shift history.
    assert(!p.global[192][0].valid); // Allocation occurs on update.
}

static void test_fallback_and_second_way_priority() {
    pm_predictor p;
    branch_info b = branch(0x122); // History zero: set 4, tag 34.
    p.bimodal[0x122] = 3;
    p.global[4][0].tag = 34; // An invalid matching tag must not be a hit.
    p.global[4][0].counter = 0;
    assert(p.predict(b)->direction_prediction());
    assert(p.u.way == -1);

    p.global[4][0].valid = true;
    p.global[4][0].tag = 35;
    p.global[4][1].valid = true;
    p.global[4][1].tag = 34;
    p.global[4][1].counter = 0;
    assert(!p.predict(b)->direction_prediction());
    assert(p.u.way == 1);
    p.global[4][1].counter = 3;
    p.bimodal[0x122] = 0;
    assert(p.predict(b)->direction_prediction());

    p.update(&p.u, false, 0);
    assert(p.global[4][1].counter == 2);
    assert(p.global[4][0].counter == 0);
    assert(p.bimodal[0x122] == 0);
    assert(p.lru[4] == 0);
}

static void test_counter_transitions_and_saturation() {
    pm_predictor p;
    assert(!step_at_history_zero(p, 0x100, true)); // 1 -> 2
    assert(p.bimodal[0x100] == 2 && p.global[4][0].counter == 2);
    assert(step_at_history_zero(p, 0x100, true)); // 2 -> 3
    assert(step_at_history_zero(p, 0x100, true)); // Saturate at 3.
    assert(p.bimodal[0x100] == 3 && p.global[4][0].counter == 3);
    assert(step_at_history_zero(p, 0x100, false)); // 3 -> 2
    assert(step_at_history_zero(p, 0x100, false)); // 2 -> 1
    assert(!step_at_history_zero(p, 0x100, false)); // 1 -> 0
    assert(!step_at_history_zero(p, 0x100, false)); // Saturate at 0.
    assert(p.bimodal[0x100] == 0 && p.global[4][0].counter == 0);
}

static void test_invalid_preference_and_lru_replacement() {
    pm_predictor p;
    // Both tags map to set 4. The second fill must use its invalid way,
    // even when the victim bit points at the occupied first way.
    step_at_history_zero(p, 0x100, false);
    p.lru[4] = 0;
    step_at_history_zero(p, 0x101, false);
    assert(p.global[4][0].valid && p.global[4][0].tag == 0);
    assert(p.global[4][1].valid && p.global[4][1].tag == 1);
    assert(p.lru[4] == 0);

    step_at_history_zero(p, 0x100, false); // Refresh way 0, making way 1 LRU.
    assert(p.lru[4] == 1);
    step_at_history_zero(p, 0x102, true); // Third tag evicts way 1.
    assert(p.global[4][0].tag == 0);
    assert(p.global[4][1].tag == 2);
    // Appendix B trains the victim's existing counter (0 -> 1).
    assert(p.global[4][1].counter == 1);
    assert(p.lru[4] == 0);
    p.history = 0;
    branch_info newest = branch(0x102);
    assert(!p.predict(newest)->direction_prediction());
    assert(p.u.way == 1);
    branch_info evicted = branch(0x101);
    p.predict(evicted);
    assert(p.u.way == -1);
}

static void test_saved_prediction_context() {
    pm_predictor p;
    p.history = 0x1234;
    branch_info b = branch(0xa235);
    pm_update saved = *static_cast<pm_update *>(p.predict(b));
    // Update must train the address/history selected at prediction time.
    p.history = 0;
    branch_info another = branch(0x33, BR_CALL);
    p.predict(another);
    p.update(&saved, true, 0);
    assert(p.bimodal[0x235] == 2);
    assert(p.bimodal[0x33] == 1);
    assert(p.global[192][0].valid);
    assert(p.global[192][0].tag == 1);
    assert(p.global[192][0].counter == 2);
    assert(p.history == 1);
}

static void test_history_width_and_order() {
    pm_predictor p;
    branch_info b = branch(0x100);
    p.history = 0x6001;
    p.update(p.predict(b), true, 0);
    assert(p.history == 0x4003);
    p.update(p.predict(b), false, 0);
    assert(p.history == 0x0006);
    for (int i = 0; i < 15; ++i) p.update(p.predict(b), true, 0);
    assert(p.history == 0x7fff);
    p.update(p.predict(b), true, 0);
    assert(p.history == 0x7fff);
    for (int i = 0; i < 15; ++i) p.update(p.predict(b), false, 0);
    assert(p.history == 0);
}

static void test_nonconditional_isolation() {
    pm_predictor p;
    step_at_history_zero(p, 0x100, true);
    unsigned char saved_bimodal[sizeof(p.bimodal)];
    unsigned char saved_global[sizeof(p.global)];
    unsigned char saved_lru[sizeof(p.lru)];
    std::memcpy(saved_bimodal, p.bimodal, sizeof(p.bimodal));
    std::memcpy(saved_global, p.global, sizeof(p.global));
    std::memcpy(saved_lru, p.lru, sizeof(p.lru));
    const unsigned int history = p.history;
    const unsigned int flags[] = {0, BR_CALL, BR_RETURN, BR_INDIRECT};
    for (unsigned int flag : flags) {
        branch_info b = branch(0x12345678, flag);
        branch_update *prediction = p.predict(b);
        assert(prediction->direction_prediction());
        assert(!prediction->target_prediction());
        p.update(prediction, false, 0x99);
        assert(p.history == history);
        assert(std::memcmp(saved_bimodal, p.bimodal, sizeof(p.bimodal)) == 0);
        assert(std::memcmp(saved_global, p.global, sizeof(p.global)) == 0);
        assert(std::memcmp(saved_lru, p.lru, sizeof(p.lru)) == 0);
    }
}

int main() {
    test_initial_state_and_hash();
    test_fallback_and_second_way_priority();
    test_counter_transitions_and_saturation();
    test_invalid_preference_and_lru_replacement();
    test_saved_prediction_context();
    test_history_width_and_order();
    test_nonconditional_isolation();
    std::cout << "Pentium M direction predictor checks passed.\n";
}
