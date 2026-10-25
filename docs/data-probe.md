# Data probe (measured 26 Oct 2026)

Measured on a MacBook (Apple M5, 16 GB RAM) over a home connection, fetching from the
dynamical.org ECMWF IFS ENS archive (anonymous S3, us-west-2).

| Item | Value |
|---|---|
| Runs fetched | 29 (28 case-study cycles + the 25 Oct 2026 00 UTC run) |
| Fetch time per run (4 variables, event region) | mean 34 s, max 50 s |
| Fetch time, whole domain 0-35° N, 55-100° E | 35 s |
| Local cache per run (event region, T+0 to T+240) | 87-161 MB |
| Local cache, whole domain run | 304 MB |
| Total cache | 3.9 GB |
| Artifacts for 5 events + latest run | 136 MB |
| Full build (tracking, fields, districts, verification) | 80 s |
| Members per run | 51 (control + 50 perturbed), read from the `ensemble_member` dimension |
| Grid | 0.25° regular lat/lon |
| Leads | 0-144 h every 3 h, 150-240 h every 6 h (65 steps kept of 85) |
| Variables used | MSLP, 10 m u/v, precipitation rate |
| Missing | No 850 hPa winds or vorticity in the archive; precipitation is NaN at T+0 (rate over the previous step) |

## Still unmeasured

- TIGGE retrieval size and queue time for Biparjoy and Michaung (needs a registered ECMWF account).
- Archived grid and member count of 2023 NEPS-G fields in TIGGE.
- Whether ECMWF's new 0.1° open data includes the ensemble stream.
