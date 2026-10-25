// trace.h
// This file declares functions and a struct for reading trace files.

// Resolve the Unix commands for gzip, bzip2, and plain files through PATH
// so the trace reader works across systems with different install paths.

#define ZCAT            "gzip -dc"
#define BZCAT           "bzip2 -dc"
#define CAT             "cat"

struct trace {
	bool	taken;
	unsigned int target;
	branch_info bi;
};

void init_trace (char *);
trace *read_trace (void);
void end_trace (void);
