import pandas as pd

from src.analysis.imbalance_index import compute_imbalance


def test_compute_imbalance_flags_top_quantile_as_vulnerable():
    df = pd.DataFrame(
        {
            "adm_dong_cd": ["A", "B", "C", "D", "E"],
            "living_pop_day": [100, 100, 100, 100, 1000],
            "living_pop_night": [100, 100, 100, 100, 1000],
            "parking_supply": [200, 200, 200, 200, 50],
        }
    )
    result = compute_imbalance(df)
    assert result.loc[result["adm_dong_cd"] == "E", "is_vulnerable"].iloc[0]
    assert not result.loc[result["adm_dong_cd"] == "A", "is_vulnerable"].iloc[0]
