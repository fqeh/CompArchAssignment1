// Assignment implementation author: Ali Alfageeh.
// Supplied gshare and extra-credit skeleton retained with their provenance.
#ifndef ALI_ALFAGEEH_MY_PREDICTOR_H
#define ALI_ALFAGEEH_MY_PREDICTOR_H
#include <cstring>

// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

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

	void update (branch_update *u, bool taken, unsigned int /*target*/) {
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
// Assignment implementation author: Ali Alfageeh.
// Included by my_predictor.h after the supplied gshare implementation.

class pm_update : public branch_update {
public:
    unsigned int index = 0;       // Bimodal index saved at prediction time.
    unsigned int set = 0;
    unsigned int tag = 0;
    int hit_way = -1;
    bool conditional = false;
};

class pm_predictor : public branch_predictor {
public:
    static constexpr unsigned int BIMODAL_BITS = 12;
    static constexpr unsigned int GLOBAL_SET_BITS = 9;
    static constexpr unsigned int GLOBAL_TAG_BITS = 6;
    static constexpr unsigned int HISTORY_BITS = 15;
    static constexpr unsigned int WAYS = 2;
    static constexpr unsigned int BIMODAL_SIZE = 1u << BIMODAL_BITS;
    static constexpr unsigned int GLOBAL_SETS = 1u << GLOBAL_SET_BITS;
    static constexpr unsigned int HISTORY_MASK = (1u << HISTORY_BITS) - 1;
    static constexpr unsigned int TAG_MASK = (1u << GLOBAL_TAG_BITS) - 1;

    struct entry {
        bool valid = false;
        unsigned char tag = 0;
        unsigned char counter = 1;
    };

    struct statistics {
        unsigned long long hits = 0;
        unsigned long long misses = 0;
        unsigned long long replacements = 0;
    };

private:
    pm_update u;
    unsigned int ghr = 0;
    unsigned char bimodal[BIMODAL_SIZE];
    entry global[GLOBAL_SETS][WAYS];
    unsigned char lru[GLOBAL_SETS] = {};
    statistics stats;

    static void train(unsigned char &counter, bool taken) {
        if (taken) {
            if (counter < 3) ++counter;
        } else {
            if (counter > 0) --counter;
        }
    }

public:
    pm_predictor() {
        // Weakly not taken; global entries start invalid; GHR starts at zero.
        for (unsigned int i = 0; i < BIMODAL_SIZE; ++i) bimodal[i] = 1;
    }

    branch_update *predict(branch_info &b) override {
        u = pm_update{};
        u.conditional = (b.br_flags & BR_CONDITIONAL) != 0;
        u.direction_prediction(true);
        u.target_prediction(0);  // Target prediction is outside this assignment.
        if (!u.conditional) return &u;

        u.index = b.address & (BIMODAL_SIZE - 1);
        const unsigned int hash = (b.address ^ ghr) & HISTORY_MASK;
        u.set = hash >> GLOBAL_TAG_BITS;  // HASH[14:6]
        u.tag = hash & TAG_MASK;         // HASH[5:0]
        u.direction_prediction(bimodal[u.index] >= 2);
        for (unsigned int way = 0; way < WAYS; ++way) {
            const entry &e = global[u.set][way];
            if (e.valid && e.tag == u.tag) {
                u.hit_way = static_cast<int>(way);
                u.direction_prediction(e.counter >= 2);
                break;
            }
        }
        return &u;
    }

    void update(branch_update *update, bool taken, unsigned int) override {
        const pm_update &saved = *static_cast<pm_update *>(update);
        if (!saved.conditional) return;

        // Train using the indices from BEFORE this branch changes the GHR.
        train(bimodal[saved.index], taken);
        unsigned int way;
        if (saved.hit_way >= 0) {
            ++stats.hits;
            way = static_cast<unsigned int>(saved.hit_way);
            train(global[saved.set][way].counter, taken);
        } else {
            ++stats.misses;
            // Prefer unused ways; otherwise evict the least recently used way.
            for (way = 0; way < WAYS; ++way)
                if (!global[saved.set][way].valid) break;
            if (way == WAYS) {
                way = lru[saved.set];
                ++stats.replacements;
            }
            entry &e = global[saved.set][way];
            e.valid = true;
            e.tag = static_cast<unsigned char>(saved.tag);
            // A new tag must not inherit the evicted branch's confidence.
            e.counter = taken ? 2 : 1;
        }
        lru[saved.set] = static_cast<unsigned char>(1u - way);
        ghr = ((ghr << 1) | static_cast<unsigned int>(taken)) & HISTORY_MASK;
    }

    // Read-only inspection supports the step-through example and unit tests.
    unsigned int history() const { return ghr; }
    unsigned int local_counter(unsigned int i) const { return bimodal[i]; }
    const entry &global_entry(unsigned int set, unsigned int way) const {
        return global[set][way];
    }
    unsigned int next_victim(unsigned int set) const { return lru[set]; }
    const statistics &get_statistics() const { return stats; }
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

        branch_update *predict (branch_info &) {
            u.direction_prediction (true);
            u.target_prediction (0);
            return &u;
        }

        void update (branch_update *, bool, unsigned int) {
        }

};



#endif
