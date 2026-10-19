// predict.cc
// This file contains the main function.  The program accepts a single 
// parameter: the name of a trace file.  It drives the branch predictor
// simulation by reading the trace file and feeding the traces one at a time
// to the branch predictor.

#include <stdio.h>
#include <stdlib.h>
#include <string.h> // in case you want to use e.g. memset
#include <assert.h>

#include "branch.h"
#include "trace.h"
#include "predictor.h"
#include "my_predictor.h"

int main (int argc, char *argv[]) {

	// The optional statistics flag exposes exact counts for the report.

	if (argc < 2 || argc > 3 || (argc == 3 && strcmp(argv[2], "--stats") != 0)) {
		fprintf (stderr, "Usage: %s <trace-file> [--stats]\n", argv[0]);
		exit (1);
	}

	// open the trace file for reading

	init_trace (argv[1]);

	// initialize competitor's branch prediction code

	branch_predictor *p = new pm_predictor ();

	// some statistics to keep, currently just for conditional branches

	long long int conditional = 0, dmiss = 0;

	// keep looping until end of file

	for (;;) {

		// get a trace

		trace *t = read_trace ();

		// NULL means end of file

		if (!t) break;

		// send this trace to the competitor's code for prediction

		branch_update *u = p->predict (t->bi);

		// collect statistics for a conditional branch trace

		if (t->bi.br_flags & BR_CONDITIONAL) {
			++conditional;

			// count a direction misprediction

			dmiss += u->direction_prediction () != t->taken;

		}

		// update competitor's state

		p->update (u, t->taken, t->target);
	}

	// done reading traces

	end_trace ();

	// give final mispredictions per kilo-instruction and exit.
	// each trace represents exactly 100 million instructions.

	if (argc == 3) {
		printf("Conditional branches: %lld\nDirection misses: %lld\n", conditional, dmiss);
	}
	printf ("%0.3f MPKI\n", 1000.0 * (dmiss / 1e8));
	delete p;
	exit (0);
}
