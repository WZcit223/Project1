"""Minimal server-side SVG line charts (no JavaScript chart library)."""

from dataclasses import dataclass
from datetime import date
from html import escape

PALETTE = ("#2563eb", "#d97706", "#059669", "#7c3aed", "#dc2626")


@dataclass(frozen=True)
class Series:
    name: str
    points: list[tuple[date, float]]


def line_chart(series: list[Series], title: str, width: int = 640, height: int = 220) -> str:
    """SVG markup: one polyline per series on shared axes, with a legend and min/max labels."""
    values = [v for s in series for _, v in s.points]
    days = [d for s in series for d, _ in s.points]
    if not values:
        return f'<p class="muted">{escape(title)}: no data</p>'
    left, right, top, bottom = 56, 12, 28, 28
    low, high = min(0.0, min(values)), max(values)
    span = (high - low) or 1.0
    first, last = min(days), max(days)
    total_days = max((last - first).days, 1)

    def x(day: date) -> float:
        return left + (width - left - right) * (day - first).days / total_days

    def y(value: float) -> float:
        return top + (height - top - bottom) * (1 - (value - low) / span)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}" '
        f'class="chart">',
        f'<text x="{left}" y="16" class="chart-title">{escape(title)}</text>',
        f'<line x1="{left}" y1="{y(low):.1f}" x2="{width - right}" y2="{y(low):.1f}" '
        'class="axis"/>',
        f'<text x="{left - 6}" y="{y(high) + 4:.1f}" class="tick" text-anchor="end">'
        f"{high:,.0f}</text>",
        f'<text x="{left - 6}" y="{y(low) + 4:.1f}" class="tick" text-anchor="end">'
        f"{low:,.0f}</text>",
        f'<text x="{left}" y="{height - 8}" class="tick">{first.isoformat()}</text>',
        f'<text x="{width - right}" y="{height - 8}" class="tick" text-anchor="end">'
        f"{last.isoformat()}</text>",
    ]
    for i, s in enumerate(series):
        colour = PALETTE[i % len(PALETTE)]
        coords = " ".join(f"{x(d):.1f},{y(v):.1f}" for d, v in s.points)
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="{colour}" stroke-width="1.6"/>'
        )
        parts.append(
            f'<text x="{width - right - 150}" y="{top + 14 * i}" class="legend" '
            f'fill="{colour}">■ {escape(s.name)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)
