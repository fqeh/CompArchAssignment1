// Evaluate all predictors on the same decoded stream, with fresh state per run.
#include <stdio.h>
#include <string.h>
#include "branch.h"
#include "trace.h"
#include "predictor.h"
#include "my_predictor.h"

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <trace-file>\n", argv[0]);
        return 1;
    }
    FILE *input = fopen(argv[1], "rb");
    if (!input) { perror(argv[1]); return 1; }
    fclose(input);

    pm_predictor hybrid;
    gshare_predictor gshare;
    unsigned char bimodal[pm_predictor::BIMODAL_SIZE];
    memset(bimodal, 1, sizeof(bimodal));
    unsigned long long conditional = 0, always_misses = 0, bimodal_misses = 0,
                       gshare_misses = 0, hybrid_misses = 0, global_hits = 0;
    init_trace(argv[1]);
    while (trace *t = read_trace()) {
        branch_update *h = hybrid.predict(t->bi);
        branch_update *g = gshare.predict(t->bi);
        if (t->bi.br_flags & BR_CONDITIONAL) {
            ++conditional;
            always_misses += !t->taken;
            hybrid_misses += h->direction_prediction() != t->taken;
            gshare_misses += g->direction_prediction() != t->taken;
            global_hits += static_cast<pm_update *>(h)->hit_way >= 0;
            unsigned char &counter = bimodal[t->bi.address & (sizeof(bimodal) - 1)];
            bimodal_misses += (counter >= 2) != t->taken;
            if (t->taken) { if (counter < 3) ++counter; }
            else { if (counter > 0) --counter; }
        }
        hybrid.update(h, t->taken, t->target);
        gshare.update(g, t->taken, t->target);
    }
    end_trace();
    puts("conditional_branches,always_taken_misses,bimodal_misses,gshare_misses,hybrid_misses,global_hits");
    printf("%llu,%llu,%llu,%llu,%llu,%llu\n", conditional, always_misses,
           bimodal_misses, gshare_misses, hybrid_misses, global_hits);
    return 0;
}
