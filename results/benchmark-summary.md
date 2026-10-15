# Benchmark results

MPKI = conditional direction mispredictions per 1,000 instructions. Lower is better.

| Benchmark | Always taken | Bimodal | Gshare | Hybrid | Global hit rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| 164.gzip | 70.025 | 15.030 | 12.473 | 12.617 | 83.06% |
| 175.vpr | 85.312 | 14.671 | 13.415 | 14.337 | 56.09% |
| 176.gcc | 86.071 | 19.347 | 11.254 | 15.298 | 54.43% |
| 181.mcf | 102.497 | 33.245 | 15.837 | 17.680 | 77.42% |
| 186.crafty | 48.651 | 13.075 | 5.837 | 8.464 | 56.55% |
| 197.parser | 78.421 | 15.417 | 10.008 | 10.357 | 80.06% |
| 201.compress | 76.983 | 9.356 | 7.831 | 8.199 | 87.68% |
| 202.jess | 92.343 | 8.809 | 1.562 | 1.750 | 92.36% |
| 205.raytrace | 109.506 | 3.806 | 2.756 | 3.421 | 62.95% |
| 209.db | 91.451 | 6.480 | 3.909 | 4.613 | 86.70% |
| 213.javac | 109.644 | 3.181 | 2.267 | 2.638 | 60.98% |
| 222.mpegaudio | 110.339 | 3.154 | 2.188 | 2.604 | 61.23% |
| 227.mtrt | 112.022 | 3.706 | 2.657 | 3.268 | 66.69% |
| 228.jack | 77.958 | 7.691 | 3.033 | 3.946 | 75.30% |
| 252.eon | 24.226 | 9.405 | 1.807 | 3.139 | 76.86% |
| 253.perlbmk | 66.833 | 5.955 | 2.554 | 4.700 | 72.93% |
| 254.gap | 75.950 | 9.675 | 3.926 | 4.797 | 87.01% |
| 255.vortex | 70.524 | 1.916 | 1.222 | 1.239 | 83.95% |
| 256.bzip2 | 178.257 | 0.112 | 0.094 | 0.076 | 99.62% |
| 300.twolf | 59.221 | 21.942 | 21.489 | 22.046 | 32.68% |
| **Average / aggregate** | 86.312 | 10.299 | 6.306 | 7.260 | 74.02% |

Each trace represents 100,000,000 instructions. The final MPKI values are
arithmetic means because all traces have equal instruction counts. The final
global hit rate is weighted by the number of conditional branches.

All hybrid MPKI values were checked against the separate assignment driver.
Exact miss counts and trace SHA-256 checksums are in `benchmark.csv`.
