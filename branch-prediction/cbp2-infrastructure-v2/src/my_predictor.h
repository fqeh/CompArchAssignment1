// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

#ifndef MY_PREDICTOR_H
#define MY_PREDICTOR_H

#include <cstring>

class gshare_update : public branch_update {
public:
	unsigned int index;
};

class gshare_predictor : public branch_predictor {
public:
        enum { HISTORY_LENGTH = 15, TABLE_BITS = 15 };
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
        unsigned int index;      // bimodal index at prediction time
        unsigned int set_index;  // global set at prediction time
        unsigned int tag;
        int way;                 // -1 for a global miss
        bool conditional;
};

class pm_predictor : public branch_predictor {
public:
        enum {
            BIMODAL_BITS = 12, SET_BITS = 9, TAG_BITS = 6,
            HISTORY_LENGTH = SET_BITS + TAG_BITS, WAYS = 2
        };
        struct global_entry {
            unsigned char tag;
            unsigned char counter;
            bool valid;
        };

        pm_update u;
        unsigned int history;
        unsigned char bimodal[1 << BIMODAL_BITS];
        global_entry global[1 << SET_BITS][WAYS];
        unsigned char lru[1 << SET_BITS]; // next victim when both ways are valid

        pm_predictor (void) : history(0) {
            std::memset(bimodal, 1, sizeof(bimodal)); // weakly not taken
            std::memset(lru, 0, sizeof(lru));
            for (unsigned int set = 0; set < (1u << SET_BITS); ++set) {
                for (int way = 0; way < WAYS; ++way) {
                    global[set][way].tag = 0;
                    global[set][way].counter = 1;
                    global[set][way].valid = false;
                }
            }
        }

        branch_update *predict (branch_info & b) override {
            u.conditional = (b.br_flags & BR_CONDITIONAL) != 0;
            u.way = -1;
            u.direction_prediction (true);
            u.target_prediction (0); // target prediction is outside this assignment
            if (!u.conditional) return &u;

            u.index = b.address & ((1u << BIMODAL_BITS) - 1);
            const unsigned int hash = (b.address ^ history)
                                      & ((1u << HISTORY_LENGTH) - 1);
            u.set_index = hash >> TAG_BITS;
            u.tag = hash & ((1u << TAG_BITS) - 1);
            for (int way = 0; way < WAYS; ++way) {
                const global_entry &entry = global[u.set_index][way];
                if (entry.valid && entry.tag == u.tag) {
                    u.way = way;
                    break;
                }
            }
            const unsigned char counter = u.way >= 0
                ? global[u.set_index][u.way].counter : bimodal[u.index];
            u.direction_prediction(counter >= 2);
            return &u;
        }

        static void train(unsigned char &counter, bool taken) {
            if (taken) {
                if (counter < 3) ++counter;
            } else {
                if (counter > 0) --counter;
            }
        }

        void update (branch_update *update, bool taken, unsigned int) override {
            pm_update &prediction = *static_cast<pm_update *>(update);
            if (!prediction.conditional) return;

            train(bimodal[prediction.index], taken);
            int way = prediction.way;
            if (way < 0) {
                way = lru[prediction.set_index];
                for (int candidate = 0; candidate < WAYS; ++candidate) {
                    if (!global[prediction.set_index][candidate].valid) {
                        way = candidate;
                        break;
                    }
                }
                global_entry &entry = global[prediction.set_index][way];
                entry.valid = true;
                entry.tag = static_cast<unsigned char>(prediction.tag);
                // Appendix B trains the selected slot's existing counter,
                // including when that slot is allocated to a different tag.
            }
            train(global[prediction.set_index][way].counter, taken);
            lru[prediction.set_index] = static_cast<unsigned char>(1 - way);
            history = ((history << 1) | static_cast<unsigned int>(taken))
                      & ((1u << HISTORY_LENGTH) - 1);
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

#endif


