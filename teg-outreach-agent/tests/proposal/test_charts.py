from app.domain.schemas import SectorFitRow
from app.proposal import charts


def _no_unsafe(svg: str):
    assert svg.lstrip().startswith("<svg")
    assert "<script" not in svg
    assert "http" not in svg


def test_growth_bar():
    svg = charts.growth_bar((8000, 15000), (125, 250))
    _no_unsafe(svg)
    assert ("15,000" in svg) or ("15000" in svg)
    assert "250" in svg


def test_industry_mix_bars():
    svg = charts.industry_mix_bars(["Manufacturing", "Healthcare", "Fintech"])
    _no_unsafe(svg)
    assert "Manufacturing" in svg and "Healthcare" in svg
    assert "illustrative" in svg.lower()


def test_funnel():
    svg = charts.funnel(charts.DEFAULT_FUNNEL_STEPS)
    _no_unsafe(svg)
    assert "15,000" in svg or "15000" in svg


def test_sector_peer_stat():
    svg = charts.sector_peer_stat("Fintech", 4)
    _no_unsafe(svg)
    assert ">4<" in svg or "4</text>" in svg
    assert "Fintech" in svg


def test_sector_fit_bars_4_and_6_rows_and_clamp():
    for n in (4, 6):
        rows = [SectorFitRow(lever=f"Lever {i}", weight=(i % 5) + 1) for i in range(n)]
        svg = charts.sector_fit_bars(rows)
        _no_unsafe(svg)
        assert svg.count("<rect") >= n
    svg = charts.sector_fit_bars([SectorFitRow(lever="X", weight=9)])
    _no_unsafe(svg)
