// trace.h
// This file declares functions and a struct for reading trace files.

// these #define the Unix commands for decompressing gzip, bzip2, and
// plain files. The commands are located using the system PATH.

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
