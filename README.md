# VectorSmith

Desktop viewer for RF Touchstone files (`.s1p`-`.s4p`) built with **scikit-rf**, **matplotlib**, and **PyQt6**.

## Features

- Open multiple Touchstone files and overlay traces
- Plot magnitude, phase, Smith chart, VSWR, impedance magnitude, real/imag impedance, and group delay
- Time-domain reflectometry (TDR) impedance vs time for reflection traces
  - 50 ohm default normalization for single-ended traces
  - 100 ohm default normalization for mixed-mode/differential traces
  - Configurable window, zero padding, sample count, DC extrapolation, time range, and velocity factor
- Mixed-mode parameters (SDD11, SDD21, SCD21, SCC22, etc.)
  - Native mixed-mode Touchstone files (port modes D/C)
  - Convert single-ended files via **Port pairing** + `se2gmm`
- Delta comparison overlays against a selected visible reference file
- Metadata panel with Z0, frequency span, port modes, frequency step, and comments
- Drag-and-drop files onto the file list
- Frequency/time marker readouts for all visible files
- Save/load VectorSmith workspace JSON files
- Export current plot to PNG, SVG, or PDF
- Export current trace data or marker readouts to CSV
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

## Marker Tool

1. Open the **Marker** dock from the View menu.
2. Enable the marker and set the frequency/time manually or click the plot.
3. Frequency-domain plots report values in GHz.
4. TDR plots report impedance at time in ns.

## Mixed-Mode Usage

1. Open a 4-port or higher even-port Touchstone file.
2. Set **Domain** to **Mixed-mode**.
3. For single-ended data, click **Port pairing...** to set differential groups (`p`) and renumber map.
4. Pick a trace such as `SDD11` or `SCD21`.
5. Enable **Keysight GMM reorder** if your file uses Keysight True Mode submatrix layout.

## TDR Usage

1. Select a reflection trace such as `S11`, `S22`, or `SDD11`.
2. Choose **TDR Z(t)** from the Plot dropdown.
3. Open **TDR Settings...** to adjust normalization, windowing, padding, sample count, DC extrapolation, or time range.
4. Enable the marker to read impedance at a specific time.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Project Layout

- `src/vectorsmith/loader.py` - Touchstone I/O
- `src/vectorsmith/mixed_mode.py` - SDD/SDC/SCD/SCC conversion and trace lists
- `src/vectorsmith/compare.py` - frequency alignment
- `src/vectorsmith/rf_trace.py` - RF trace and TDR calculations
- `src/vectorsmith/plots.py` - matplotlib rendering
- `src/vectorsmith/workspace.py` - workspace JSON persistence
- `src/vectorsmith/exports.py` - CSV export helpers
- `src/vectorsmith/ui/` - PyQt6 main window and docks
