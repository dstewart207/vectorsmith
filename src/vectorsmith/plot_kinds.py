"""Plot type enumeration (shared across plotting and marker modules)."""

from enum import Enum


class PlotKind(Enum):
    MAG_DB = "mag_db"
    PHASE_DEG = "phase_deg"
    SMITH = "smith"
    VSWR = "vswr"
    INPUT_Z = "input_z"
    RETURN_LOSS_DB = "return_loss_db"
    INSERTION_LOSS_DB = "insertion_loss_db"
    GROUP_DELAY_NS = "group_delay_ns"
    REAL_Z = "real_z"
    IMAG_Z = "imag_z"
    TDR_IMPEDANCE = "tdr_impedance"
