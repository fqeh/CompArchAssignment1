#include <stdio.h>
#include <stdlib.h>
#include "branch.h"
#include "predictor.h"
#include "my_predictor.h"

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #condition); \
    exit(1); } } while (0)

static branch_info branch(unsigned int address, unsigned int flags = BR_CONDITIONAL) {
    branch_info b = {address, OP_JNZ, flags};
    return b;
}

static pm_update *predict(pm_predictor &p, unsigned int address) {
    branch_info b = branch(address);
    return static_cast<pm_update *>(p.predict(b));
}

static bool step(pm_predictor &p, unsigned int address, bool taken) {
    pm_update *u = predict(p, address);
    bool result = u->direction_prediction();
    p.update(u, taken, 0);
    return result;
}

static void cold_start_and_fallback() {
    pm_predictor p;
    CHECK(p.history == 0);
    for (unsigned int i = 0; i < pm_predictor::BIMODAL_SIZE; ++i)
        CHECK(p.bimodal[i] == 1);
    for (unsigned int i = 0; i < pm_predictor::GLOBAL_SETS; ++i)
        for (unsigned int w = 0; w < pm_predictor::GLOBAL_WAYS; ++w)
            CHECK(!p.global[i][w].valid);
    CHECK(predict(p, 0)->hit_way == -1); // tag zero is not a cold hit
    CHECK(!predict(p, 0)->direction_prediction());
    p.bimodal[0] = 3;
    CHECK(predict(p, 0)->direction_prediction());
    CHECK(p.history == 0); // predictions alone must not train state
    CHECK(!p.global[0][0].valid);
}

static void address_and_history_indexing() {
    pm_predictor p;
    p.history = 0x1234;
    pm_update *u = predict(p, 0xABCDEF01u);
    // Low address bits are EF01; EF01 xor 1234 = FD35; low 15 = 7D35.
    CHECK(u->bimodal_index == 0xF01);
    CHECK(u->global_index == 0x1F4);
    CHECK(u->tag == 0x35);
    p.history = 0;
    u = predict(p, 0xFFFFFFFFu);
    CHECK(u->bimodal_index == 4095);
    CHECK(u->global_index == 511);
    CHECK(u->tag == 63);
    // Adjacent byte addresses must remain distinct.
    CHECK(predict(p, 1)->bimodal_index == 1);
    CHECK(predict(p, 2)->bimodal_index == 2);
}

static void counter_transitions_and_global_priority() {
    const unsigned char expected[2][4] = {{0, 0, 1, 2}, {1, 2, 3, 3}};
    for (int way = 0; way < 2; ++way) {
        for (unsigned int taken = 0; taken < 2; ++taken) {
            for (unsigned int value = 0; value < 4; ++value) {
                pm_predictor p;
                p.bimodal[5] = 3 - value; // deliberately disagree
                p.global[0][way].valid = true;
                p.global[0][way].tag = 5;
                p.global[0][way].counter = value;
                pm_update *u = predict(p, 5);
                CHECK(u->hit_way == way);
                CHECK(u->direction_prediction() == (value >= 2));
                CHECK(p.global[0][way].counter == value);
                p.update(u, taken != 0, 0);
                CHECK(p.global[0][way].counter == expected[taken][value]);
                CHECK(p.bimodal[5] == expected[taken][3 - value]);
                CHECK(p.next_victim[0] == 1 - way);
            }
        }
    }
}

static void allocation_and_replacement() {
    pm_predictor p;
    // All not-taken outcomes keep GHR zero; addresses 1,2,3 share a set.
    CHECK(!step(p, 1, false));
    CHECK(p.global[0][0].valid && p.global[0][0].tag == 1);
    CHECK(p.global[0][0].counter == 1);
    step(p, 2, false);
    CHECK(p.global[0][1].valid && p.global[0][1].tag == 2);
    CHECK(p.next_victim[0] == 0);
    step(p, 1, false); // refresh way 0; way 1 is now least recently used
    CHECK(p.next_victim[0] == 1);
    p.global[0][1].counter = 3;
    step(p, 3, false);
    CHECK(p.global[0][0].tag == 1); // recent entry survives
    CHECK(p.global[0][1].tag == 3);
    CHECK(p.global[0][1].counter == 1); // victim's strong T is discarded
    CHECK(predict(p, 2)->hit_way == -1);
    CHECK(predict(p, 1)->hit_way == 0);
    CHECK(predict(p, 3)->hit_way == 1);

    // Prefer an invalid way even when the LRU bit points at a valid way.
    p.global[0][0].valid = false;
    p.next_victim[0] = 1;
    step(p, 4, true);
    CHECK(p.global[0][0].tag == 4 && p.global[0][0].counter == 2);
    CHECK(p.global[0][1].tag == 3);
}

static void saved_index_and_history_shift() {
    pm_predictor p;
    p.history = 0x1234;
    pm_update *u = predict(p, 0x1234); // XOR is zero before update
    CHECK(u->global_index == 0 && u->tag == 0);
    p.update(u, true, 0xDEADBEEF);
    CHECK(p.global[0][0].valid && p.global[0][0].tag == 0);
    CHECK(p.global[0][0].counter == 2);
    CHECK(p.bimodal[0x234] == 2);
    CHECK(p.history == 0x2469);
    p.history = 0x7FFF;
    step(p, 0, true);
    CHECK(p.history == 0x7FFF);
    step(p, 0, false);
    CHECK(p.history == 0x7FFE);
}

static void unconditional_branches_do_not_train() {
    pm_predictor p;
    step(p, 0x123, true);
    pm_predictor before = p;
    const unsigned int flags[] = {0, BR_CALL, BR_RETURN, BR_INDIRECT,
                                 BR_CALL | BR_INDIRECT};
    for (unsigned int i = 0; i < sizeof(flags) / sizeof(flags[0]); ++i) {
        branch_info b = branch(0x123, flags[i]);
        pm_update *u = static_cast<pm_update *>(p.predict(b));
        CHECK(!u->conditional && u->hit_way == -1);
        CHECK(u->direction_prediction());
        p.update(u, true, 0x200);
    }
    CHECK(p.history == before.history);
    for (unsigned int i = 0; i < pm_predictor::BIMODAL_SIZE; ++i)
        CHECK(p.bimodal[i] == before.bimodal[i]);
    for (unsigned int i = 0; i < pm_predictor::GLOBAL_SETS; ++i) {
        CHECK(p.next_victim[i] == before.next_victim[i]);
        for (unsigned int w = 0; w < pm_predictor::GLOBAL_WAYS; ++w) {
            CHECK(p.global[i][w].valid == before.global[i][w].valid);
            CHECK(p.global[i][w].tag == before.global[i][w].tag);
            CHECK(p.global[i][w].counter == before.global[i][w].counter);
        }
    }
    branch_info conditional = branch(0x123, BR_CONDITIONAL | BR_INDIRECT);
    CHECK(static_cast<pm_update *>(p.predict(conditional))->conditional);
}

static void learns_repeating_patterns() {
    pm_predictor taken, not_taken, alternating;
    for (unsigned int i = 0; i < 512; ++i) {
        const bool alternating_outcome = (i % 2) != 0;
        bool a = step(taken, 0x200, true);
        bool b = step(not_taken, 0x200, false);
        bool c = step(alternating, 0x200, alternating_outcome);
        if (i >= 64) {
            CHECK(a);
            CHECK(!b);
            CHECK(c == alternating_outcome);
        }
    }
}

int main() {
    cold_start_and_fallback();
    address_and_history_indexing();
    counter_transitions_and_global_priority();
    allocation_and_replacement();
    saved_index_and_history_shift();
    unconditional_branches_do_not_train();
    learns_repeating_patterns();
    puts("PASS: 7 predictor test groups");
    return 0;
}
