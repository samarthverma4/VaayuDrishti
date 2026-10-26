# VaayuDrishti

**Atmospheric intelligence, made actionable.** VaayuDrishti turns ECMWF ensemble forecasts into
cyclone tracks, uncertainty, cross-cycle stability, district-level exposure and CAP advisory
drafts for India, and shows how well past forecasts did against observed best tracks.

> Experimental decision-support guidance. Not an official IMD warning. VaayuDrishti interprets
> existing forecasts; it does not replace IMD, NCMRWF or ECMWF and never sends alerts.

## What works today

| Feature | Status | Data |
|---|---|---|
| Historical replay: Dana (Oct 2024), Fengal (Nov 2024), Remal (May 2024), Montha (Oct 2025), Shakhti (Oct 2025) | Working | ECMWF IFS ENS, 51 members, 5-7 daily cycles each |
| Current forecast: latest 00 UTC run, closed-low detection and tracking, all-India rainfall probabilities | Working | ECMWF IFS ENS (25 Oct 2026 run at time of writing) |
| Per-member cyclone tracker, ensemble mean, spread, 80% envelope, strike probability, landfall | Working | |
| Forecast Time Ribbon (keyboard, playback, landfall markers) | Working | |
| Ensemble Constellation (consensus / members / uncertainty) | Working | |
| Forecast Stability Lens (swipe two cycles at the same valid time, stability signature, landfall across cycles) | Working | |
| District Risk Matrix and district panel (IMD rain thresholds, track within 120 km) | Working | 735 districts (LGD 2021) |
| Track verification vs IBTrACS (error by lead with n, landfall position and timing) | Working | IBTrACS v04r01, RSMC New Delhi |
| CAP 1.2 draft export, validated against the OASIS schema | Working | |
| GeoJSON / CSV export, shareable URLs | Working | |
| Biparjoy, Michaung (2023) | Best track only; Biparjoy also shows one TIGGE MSLP analysis (12 Jun 2023 00 UTC, isobars and model low vs best track) | Ensemble needs the full TIGGE download (loader implemented, see below) |
| EFI-proxy / SOT and the Extremeness Profile | Formulas implemented and tested; not wired to data | Needs ERA5 climate (CDS account) |
| Rainfall verification vs IMD (MAE, bias, POD, FAR, CSI, Brier, FSS by lead day) | Working | IMD Pune 0.25° gridded daily rainfall, 2023-2025 |
| NEPS-G, IMD GEFS, AIFS ENS comparison | Not built | TIGGE account / AIFS open-data ingest |
| Spherical GNN, diffusion downscaling, physics loss | Roadmap only | |

Every number in the UI is computed from the data listed; nothing is hard-coded or simulated.
Panels without data say "Not yet evaluated" and why.

## Run it

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
uv venv --python 3.12 && uv pip install -r pyproject.toml --extra dev
python -m pipeline.geo              # boundaries + CAP schema (about 25 MB)
python -m pipeline.fetch            # ECMWF ENS for the case studies (about 3.5 GB, 15 min)
python -m pipeline.fetch --latest   # newest 00 UTC run over India
python -m pipeline.fetch_imd        # IMD 0.25° gridded rainfall for the case-study years (about 25 MB a year)
python -m pipeline.build            # tracks, fields, districts, verification (about 80 s)
```

Then either run the built app:

```bash
cd frontend && npm ci && npm run build && cd ..
uvicorn backend.app.main:app --port 8000      # open http://localhost:8000
```

or develop with hot reload: `uvicorn backend.app.main:app --port 8000` plus `cd frontend && npm run dev` (http://localhost:5180).

Docker (artifacts mounted, not baked in):

```bash
docker build -t vaayudrishti . && docker run -p 8000:8000 -v "$PWD/artifacts:/app/artifacts" -v "$PWD/data:/app/data" vaayudrishti
```

The demo runs fully offline once `artifacts/` exists: the map style, fonts and the MapLibre worker are all local.

### Loading TIGGE data (Biparjoy, Michaung, NEPS-G)

1. Register at the [ECMWF Data Store](https://ecds.ecmwf.int), open the [TIGGE dataset](https://ecds.ecmwf.int/datasets/tigge-forecasts?tab=download) and accept its licence (bottom of the Download tab).
2. Put your personal access token in `~/.cdsapirc` (or `~/.ecdsapirc` if `~/.cdsapirc` already serves the Climate Data Store):
   ```
   url: https://ecds.ecmwf.int/api
   key: <PERSONAL-ACCESS-TOKEN>
   ```
3. Install the GRIB tools: `uv pip install cfgrib eccodes eccodeslib cdsapi`.
4. `python -m pipeline.fetch_tigge --probe` sends one tiny request to test access. `python -m pipeline.fetch_tigge --dry-run` prints the six requests (ECMWF control and perturbed forecasts,
   MSLP, 10 m wind, total precipitation, T+0 to T+240 every 6 h, 00 UTC on each cycle date, event region only).
   `python -m pipeline.fetch_tigge` submits them; ECDS queues them, so allow minutes to hours.
5. `python -m pipeline.build biparjoy-2023 michaung-2023`.

Any control-forecast MSLP field at T+0 under `data/raw/tigge/` (for example the `--probe` file) whose time falls inside an event's best track is also built as a snapshot: isobars plus the model low against IBTrACS, served at `/api/v1/events/{id}/snapshots` with the file's SHA-256 and GRIB keys. The source file is only read.

For NCMRWF NEPS-G use `--origin ncmrwf` (stored separately as `ncmrwf_*.grib`; the comparison view is not built yet).

NCMRWF and IMD data from TIGGE are CC BY-NC 4.0: non-commercial use only.

## Architecture

```
ECMWF ENS archive (Icechunk/Zarr, S3) ─┐
IBTrACS NI (CSV) ──────────────────────┤  pipeline/  (offline, Python)
Natural Earth + geoBoundaries ─────────┘   fetch → track → ensemble → fields → districts → verify → artifacts/
                                                                                          │
                              backend/ (FastAPI, read-only over artifacts/, CAP drafts) ◄──┘
                                                │  /api/v1/*
                              frontend/ (React, MapLibre, TanStack Query, Zustand)
```

- `pipeline/definitions.py`: IMD categories and thresholds, EFI, SOT, strike radius, great-circle maths. The only place they are defined.
- `pipeline/track/cyclone.py`: per-member MSLP-minimum tracker with a closed-low check, seeded at the observed position.
- `pipeline/ensemble.py`: mean track, spread, envelope, landfall, strike probability.
- `pipeline/districts.py`: district aggregation (probability that any cell in the district crosses an IMD threshold; track within 120 km).
- `pipeline/verify.py` (tracks) and `pipeline/rain_verify.py` (rain vs IMD: only IMD days whose 03-03 UTC window matches forecast steps exactly, land cells within 300 km of the observed storm), `pipeline/compare.py`, `pipeline/cap.py`.
- `data/sources.yaml`: source registry (grid, members, licence, who verified each fact and when). Rendered in the Models page.
- API docs: http://localhost:8000/api/v1/docs.

## Results on the case studies (from the built artifacts)

Dana, 22 Oct 2024 00 UTC cycle (2.5 days before landfall): ensemble-mean landfall 56 km from the observed point,
2.6 h early, 49 of 51 members landfalling. Montha, 26 Oct 2025 cycle: median landfall within minutes of the observed time.
Per-event track errors by lead are on the Verification page with sample sizes. These are case studies of a handful
of cycles, not skill statistics.

## Tests

```bash
pytest                                     # 42 tests: definitions, tracker on synthetic storms, API contracts, CAP schema
cd frontend && npx playwright test         # browser smoke tests (needs the dev server and API running)
node frontend/scripts/shots.mjs docs/figures   # screenshots of every view
```

## Licences

- ECMWF IFS ENS open data: CC BY 4.0 (ECMWF Terms of Use), archive by dynamical.org.
- IBTrACS: NOAA NCEI, public domain.
- IMD gridded rainfall: India Meteorological Department, Pune (Pai et al. 2014, MAUSAM 65); free download for research.
- Natural Earth (India point-of-view boundaries): public domain.
- geoBoundaries IND ADM1 (CC BY 2.5 IN, DataMeet / ECI) and ADM2 (ODbL 1.0, lgdirectory.gov.in).
- TIGGE: CC BY 4.0 (ECMWF) and CC BY-NC 4.0 (NCMRWF, IMD).
- Fonts: Space Grotesk, Inter, IBM Plex Mono (SIL OFL).

## AI assistance

This project was built with AI assistance. Claude Code (Anthropic) wrote most of the code in `pipeline/`, `backend/`
and `frontend/`, the tests and this README, working from the team's research dossier and design brief; it also
checked the dataset facts in `data/sources.yaml` against provider pages. ChatGPT was used earlier by the team for a
dataset review. The team chose the case studies, reviewed the outputs and is responsible for the submission.
