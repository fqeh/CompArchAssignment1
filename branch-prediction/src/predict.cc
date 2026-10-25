// CBP2 trace driver; assignment extensions by Ali Alfageeh.
// Original infrastructure: Daniel A. Jimenez (see doc/index.html).
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include "branch.h"
#include "trace.h"
#include "predictor.h"
#include "my_predictor.h"
#include "comparison_predictors.h"

static int usage(const char *name) {
    std::fprintf(stderr,
        "Usage: %s TRACE [--predictor pm|bimodal|gshare|always_taken] "
        "[--json] [--instructions N]\n", name);
    return 1;
}

int main(int argc, char *argv[]) {
    if (argc < 2) return usage(argv[0]);
    std::string mode = "pm";
    bool json = false;
    unsigned long long instructions = 100000000;  // Supplied CBP2 traces.
    for (int i = 2; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--json") json = true;
        else if (arg == "--predictor" && i + 1 < argc) mode = argv[++i];
        else if (arg == "--instructions" && i + 1 < argc) {
            const char *value = argv[++i];
            char *end = nullptr;
            errno = 0;
            instructions = std::strtoull(value, &end, 10);
            if (errno || !*value || *value == '-' || *end || !instructions)
                return usage(argv[0]);
        } else return usage(argv[0]);
    }

    std::unique_ptr<branch_predictor> p;
    if (mode == "pm") p.reset(new pm_predictor());
    else if (mode == "bimodal") p.reset(new bimodal_predictor());
    else if (mode == "gshare") p.reset(new gshare_predictor());
    else if (mode == "always_taken") p.reset(new always_taken_predictor());
    else return usage(argv[0]);

    init_trace(argv[1]);
    unsigned long long branches = 0, conditional = 0, misses = 0;
    while (trace *t = read_trace()) {
        ++branches;
        branch_update *u = p->predict(t->bi);
        if (t->bi.br_flags & BR_CONDITIONAL) {
            ++conditional;
            misses += u->direction_prediction() != t->taken;
        }
        p->update(u, t->taken, t->target);
    }
    end_trace();

    const double mpki = 1000.0 * static_cast<double>(misses) / instructions;
    if (!json) {
        std::printf("%.3f MPKI\n", mpki);  // Preserve the original interface.
        return 0;
    }
    const double accuracy = conditional ?
        100.0 * (1.0 - static_cast<double>(misses) / conditional) : 0.0;
    pm_predictor::statistics stats;
    if (auto *pm = dynamic_cast<pm_predictor *>(p.get()))
        stats = pm->get_statistics();
    std::printf(
        "{\"predictor\":\"%s\",\"instructions\":%llu,"
        "\"branches\":%llu,\"conditional_branches\":%llu,"
        "\"direction_misses\":%llu,\"mpki\":%.8f,"
        "\"accuracy_percent\":%.8f,\"global_hits\":%llu,"
        "\"global_misses\":%llu,\"global_replacements\":%llu}\n",
        mode.c_str(), instructions, branches, conditional, misses, mpki,
        accuracy, stats.hits, stats.misses, stats.replacements);
    return 0;
}
