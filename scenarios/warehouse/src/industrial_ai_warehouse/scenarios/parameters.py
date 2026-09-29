"""Warehouse scenario parameters (docs/scenario-spec.md §3).

Pure configuration: names, types, defaults and valid ranges. This module knows nothing about
strategies or the inventory model; plugins read the parameters they apply and report the rest.
"""

from pydantic import BaseModel, ConfigDict, Field


class WarehouseScenarioParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Demand (applied by the synthetic demand generator)
    demand_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)
    """Scales the expected demand level."""
    seasonality_multiplier: float = Field(default=1.0, ge=0.0, le=3.0)
    """Scales the seasonal amplitude around 1 (0 = flat)."""
    noise_scale: float = Field(default=1.0, ge=0.0, le=3.0)
    """Scales demand dispersion."""
    shock_multiplier: float = Field(default=1.0, ge=0.0, le=10.0)
    """Demand factor inside the shock window."""
    shock_start_day: int = Field(default=0, ge=0)
    """Shock window start, days from the horizon start."""
    shock_duration_days: int = Field(default=0, ge=0)
    """Shock window length; 0 = no shock."""

    # Supply (applied by the inventory simulation)
    lead_time_delta: int = Field(default=0, ge=-30, le=60)
    """Days added to the supplier mean lead time (result floored at 1)."""
    disruption_start_day: int = Field(default=0, ge=0)
    """Disruption window start, days from the horizon start."""
    disruption_duration_days: int = Field(default=0, ge=0)
    """Disruption window length; 0 = from the start day to the horizon end."""
    supply_capacity_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    """Fraction of each order the supplier ships inside the disruption window."""
    planner_aware: bool = False
    """Whether strategies see the adjusted mean lead time."""
