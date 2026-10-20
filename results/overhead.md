# Ledger bookkeeping overhead (in-memory, single process)

Python 3.13.16 on x86_64. Ledger logic only; no network or shared store.

| Budget chain depth | Median reserve+settle (µs) | p99 (µs) | Throughput, 8 threads (ops/s) |
|---|---|---|---|
| 2 levels (tenant + 1 run) | 3.1 | 9.0 | 26,282 |
| 4 levels (tenant + 3 runs) | 4.1 | 9.7 | 23,307 |
| 7 levels (tenant + 6 runs) | 5.5 | 10.9 | 22,889 |

A production gateway adds one round trip to a shared store per model call; that, not this logic, sets the real overhead.
