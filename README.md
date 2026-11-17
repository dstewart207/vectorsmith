# VectorSmith

Desktop viewer for RF Touchstone files (`.s1p`-`.s4p`) built with **scikit-rf**, **matplotlib**, and **PyQt6**.

## Features

- Open multiple Touchstone files and overlay traces
- **Multi-trace overlay** — plot several parameters at once (e.g. S11+S21, SDD11+SCD21)
- Plot magnitude, phase, Smith chart, VSWR, impedance magnitude, real/imag impedance, and group delay
- Time-domain reflectometry (TDR) impedance vs time for reflection traces
  - 50 ohm default normalization for single-ended traces
  - 100 ohm default normalization for mixed-mode/differential traces
  - Configurable window, zero padding, sample count, DC extrapolation, time range, and velocity factor
  - On-plot TDR markers plus peak/step discontinuity find
- Mixed-mode parameters (SDD11, SDD21, SCD21, SCC22, etc.)
  - Native mixed-mode Touchstone files (port modes D/C)
  - Convert single-ended files via **Port pairing** + `se2gmm`
- **Multi-marker** tools with Δf/Δy readout, min/max search, and −3 dB bandwidth
- Delta comparison overlays against a selected visible reference file
- **Network QA** — passivity, reciprocity, and causality checks
- Metadata panel with Z0, frequency span, port modes, frequency step, and comments
- Drag-and-drop files onto the file list
- Frequency/time marker readouts for all visible files
- Save/load VectorSmith workspace JSON files
- Export current plot to PNG, SVG, or PDF
- Export current trace data or marker readouts to CSV
- **Export Touchstone** — write SE→mixed-mode and/or Z0-renormalized `.sNp` files
- Persistent window layout, graph settings, TDR settings, theme, and last-used directory

## Install

From the project directory, install into whichever Python you use to run the app:

```powershell
python -m pip install -e .
```

Optional: use a virtual environment instead:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

Use the same Python you installed with:

```powershell
python -m vectorsmith
```

Or, if `Scripts` is on your PATH:

```powershell
vectorsmith
```

With the project venv:

```powershell
.\.venv\Scripts\python.exe -m vectorsmith
```

## Multi-Trace Overlay

1. Use the **Traces** button in the plot toolbar.
2. Check multiple parameters (for example `S11` and `S21`, or `SDD11` and `SCD21`).
3. Multi-trace series use distinct colors (single file) or linestyles (multi-file).

## Marker Tool

1. Open the **Marker** dock from the View menu.
2. Enable markers, then **Add** more markers as needed.
3. Set frequency/time manually, click/drag on the plot, or use search:
   - **Min** / **Max** — place a marker at the extrema of the active trace
   - **−3 dB BW** — place markers at the −3 dB crossings (Mag dB plots)
   - **TDR peak** / **TDR step** — find impedance discontinuities on TDR plots
4. When two or more markers are enabled, the dock shows Δx / Δy between the first two.
5. Frequency-domain plots report values in GHz; TDR plots report impedance at time in ns.

## Mixed-Mode Usage

1. Open a 4-port or higher even-port Touchstone file.
2. Set **Domain** to **Mixed-mode**.
3. For single-ended data, click **Port pairing...** to set differential groups (`p`) and renumber map.
4. Pick traces such as `SDD11` or `SCD21` (multi-select supported).
5. Enable **Keysight GMM reorder** if your file uses Keysight True Mode submatrix layout.

## TDR Usage

1. Select one or more reflection traces such as `S11`, `S22`, or `SDD11`.
2. Choose **TDR Z(t)** from the Plot dropdown.
3. Open **TDR Settings...** to adjust normalization, windowing, padding, sample count, DC extrapolation, or time range.
4. Enable markers to read impedance at specific times; use **TDR peak** / **TDR step** to locate discontinuities.

## Export Touchstone

1. Select a file in the file list.
2. Choose **File → Export Touchstone...**
3. Pick single-ended or mixed-mode domain, optional Z0 renormalization, and Keysight reorder.
4. Save the `.sNp` file for use in ADS, HFSS, or other tools.

## Network QA

1. Select a file in the file list.
2. Choose **Tools → Network QA...**
3. Review passivity, reciprocity, and causality metrics for the currently selected domain (SE or MM).

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Project Layout

- `src/vectorsmith/loader.py` - Touchstone I/O
- `src/vectorsmith/mixed_mode.py` - SDD/SDC/SCD/SCC conversion and trace lists
- `src/vectorsmith/compare.py` - frequency alignment
- `src/vectorsmith/rf_trace.py` - RF trace and TDR calculations
- `src/vectorsmith/marker.py` - marker interpolation and search helpers
- `src/vectorsmith/qa.py` - passivity / reciprocity / causality checks
- `src/vectorsmith/plots.py` - matplotlib rendering
- `src/vectorsmith/workspace.py` - workspace JSON persistence
- `src/vectorsmith/exports.py` - CSV and Touchstone export helpers
- `src/vectorsmith/ui/` - PyQt6 main window and docks
