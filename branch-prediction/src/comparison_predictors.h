// Comparison predictors for the report. Author: Ali Alfageeh.
#ifndef ALI_ALFAGEEH_COMPARISON_PREDICTORS_H
#define ALI_ALFAGEEH_COMPARISON_PREDICTORS_H

// Exact direction behavior of the original pm_predictor skeleton.
class always_taken_predictor : public branch_predictor {
    branch_update u;
public:
    branch_update *predict(branch_info &) override {
        u.direction_prediction(true);
        u.target_prediction(0);
        return &u;
    }
};

// Same bimodal size, initialization and training as the hybrid's fallback.
class bimodal_predictor : public branch_predictor {
    branch_update u;
    unsigned char counters[4096];
    unsigned int index = 0;
    bool conditional = false;
public:
    bimodal_predictor() {
        for (unsigned int i = 0; i < 4096; ++i) counters[i] = 1;
    }
    branch_update *predict(branch_info &b) override {
        conditional = (b.br_flags & BR_CONDITIONAL) != 0;
        index = b.address & 4095;
        u.direction_prediction(!conditional || counters[index] >= 2);
        u.target_prediction(0);
        return &u;
    }
    void update(branch_update *, bool taken, unsigned int) override {
        if (!conditional) return;
        unsigned char &c = counters[index];
        if (taken) { if (c < 3) ++c; }
        else { if (c > 0) --c; }
    }
};
#endif
