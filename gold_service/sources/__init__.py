from gold_service.sources.base import PRICE_COLUMNS, PriceSource
from gold_service.sources.csv_source import CSVPriceSource


def build_source(settings) -> PriceSource:
    """설정값(PRICE_SOURCE)으로 PriceSource 구현체를 고른다."""
    if settings.price_source == "csv":
        return CSVPriceSource(
            settings.price_csv_path,
            date_col=settings.price_csv_date_col,
            close_col=settings.price_csv_close_col,
        )
    raise ValueError(f"지원하지 않는 PRICE_SOURCE: {settings.price_source!r}")


__all__ = ["PRICE_COLUMNS", "PriceSource", "CSVPriceSource", "build_source"]
