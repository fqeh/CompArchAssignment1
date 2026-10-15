// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

#ifndef MY_PREDICTOR_H
#define MY_PREDICTOR_H

#include <string.h>

class gshare_update : public branch_update {
public:
	unsigned int index;
};

class gshare_predictor : public branch_predictor {
public:
#define HISTORY_LENGTH	15
#define TABLE_BITS	15
	gshare_update u;
	branch_info bi;
	unsigned int history;
	unsigned char tab[1<<TABLE_BITS];

	gshare_predictor (void) : history(0) { 
		memset (tab, 0, sizeof (tab));
	}

	branch_update *predict (branch_info & b) {
		bi = b;
		if (b.br_flags & BR_CONDITIONAL) {
			u.index = 
				  (history << (TABLE_BITS - HISTORY_LENGTH)) 
				^ (b.address & ((1<<TABLE_BITS)-1));
			u.direction_prediction (tab[u.index] >> 1);
		} else {
			u.direction_prediction (true);
		}
		u.target_prediction (0);
		return &u;
	}

	void update (branch_update *u, bool taken, unsigned int target) {
		if (bi.br_flags & BR_CONDITIONAL) {
			unsigned char *c = &tab[((gshare_update*)u)->index];
			if (taken) {
				if (*c < 3) (*c)++;
			} else {
				if (*c > 0) (*c)--;
			}
			history <<= 1;
			history |= taken;
			history &= (1<<HISTORY_LENGTH)-1;
		}
	}
};

//
// Pentium M hybrid branch predictors
// This class implements a simple hybrid branch predictor based on the Pentium M branch outcome prediction units. 
// Instead of implementing the complete Pentium M branch outcome predictors, the class below implements a hybrid 
// predictor that combines a bimodal predictor and a global predictor. 
class pm_update : public branch_update {
public:
        bool conditional;
        unsigned int bimodal_index;
        unsigned int global_index;
        unsigned int tag;
        int hit_way;

        pm_update () : conditional(false), bimodal_index(0),
            global_index(0), tag(0), hit_way(-1) {}
};

class pm_predictor : public branch_predictor {
public:
        // Assignment diagram: 4096 bimodal counters; 512 global sets,
        // six-bit tags. Two ways are explicitly allowed by the handout.
        enum {
            BIMODAL_SIZE = 4096,
            GLOBAL_SETS = 512,
            GLOBAL_WAYS = 2,
            TAG_BITS = 6,
            HISTORY_BITS = 15,
            HISTORY_MASK = (1u << HISTORY_BITS) - 1
        };

        struct global_entry {
            bool valid;
            unsigned char tag;
            unsigned char counter;
        };

        pm_update u;
        unsigned int history;
        unsigned char bimodal[BIMODAL_SIZE];
        global_entry global[GLOBAL_SETS][GLOBAL_WAYS];
        // With two ways, one bit per set identifies the LRU victim.
        unsigned char next_victim[GLOBAL_SETS];

        pm_predictor (void) : history(0) {
            memset(bimodal, 1, sizeof(bimodal)); // weakly not taken
            memset(next_victim, 0, sizeof(next_victim));
            for (unsigned int set = 0; set < GLOBAL_SETS; ++set) {
                for (unsigned int way = 0; way < GLOBAL_WAYS; ++way) {
                    global[set][way].valid = false;
                    global[set][way].tag = 0;
                    global[set][way].counter = 1;
                }
            }
        }

        branch_update *predict (branch_info & b) {
            // The simulator immediately calls update() before predict()
            // for the next branch, so one saved update record is enough.
            u.conditional = (b.br_flags & BR_CONDITIONAL) != 0;
            u.hit_way = -1;
            u.direction_prediction (true);
            u.target_prediction (0); // target prediction is out of scope

            if (!u.conditional) return &u;

            u.bimodal_index = b.address & (BIMODAL_SIZE - 1);
            // Gshare-style XOR replaces the optional Pentium M PIR/hash.
            // Preserve byte-address bits: x86 branches need not be aligned.
            unsigned int hash = (b.address ^ history) & HISTORY_MASK;
            u.global_index = hash >> TAG_BITS; // HASH[14:6]
            u.tag = hash & ((1u << TAG_BITS) - 1); // HASH[5:0]
            u.direction_prediction(bimodal[u.bimodal_index] >= 2);

            for (int way = 0; way < GLOBAL_WAYS; ++way) {
                const global_entry &entry = global[u.global_index][way];
                if (entry.valid && entry.tag == u.tag) {
                    u.hit_way = way;
                    u.direction_prediction(entry.counter >= 2);
                    break; // a global hit overrides the bimodal prediction
                }
            }
            return &u;
        }

        void update (branch_update *record, bool taken, unsigned int) {
            const pm_update *saved = static_cast<pm_update *>(record);
            if (!saved->conditional) return;

            train(bimodal[saved->bimodal_index], taken);

            // Use the index/tag saved before the outcome enters history.
            int way = saved->hit_way;
            if (way >= 0) {
                train(global[saved->global_index][way].counter, taken);
            } else {
                // Allocate on every global miss; prefer an unused entry.
                way = next_victim[saved->global_index];
                for (int candidate = 0; candidate < GLOBAL_WAYS; ++candidate) {
                    if (!global[saved->global_index][candidate].valid) {
                        way = candidate;
                        break;
                    }
                }
                global_entry &entry = global[saved->global_index][way];
                entry.valid = true;
                entry.tag = static_cast<unsigned char>(saved->tag);
                // Do not carry a replaced branch's counter into a new tag.
                entry.counter = taken ? 2 : 1;
            }
            next_victim[saved->global_index] = 1 - way;
            history = ((history << 1) | (taken ? 1u : 0u)) & HISTORY_MASK;
        }

private:
        static void train (unsigned char &counter, bool taken) {
            if (taken) {
                if (counter < 3) ++counter;
            } else {
                if (counter > 0) --counter;
            }
        }
};

//
// Complete Pentium M branch predictors for extra credit
// This class implements the complete Pentium M branch prediction units. 
// It implements both branch target prediction and branch outcome predicton. 
class cpm_update : public branch_update {
public:
        unsigned int index;
};

class cpm_predictor : public branch_predictor {
public:
        cpm_update u;

        cpm_predictor (void) {
        }

        branch_update *predict (branch_info & b) {
            u.direction_prediction (true);
            u.target_prediction (0);
            return &u;
        }

        void update (branch_update *u, bool taken, unsigned int target) {
        }

};

#endif // MY_PREDICTOR_H


