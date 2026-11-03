__all__ = ["tl"]


def tl(value: float) -> str:
    """Turkish currency format: 1234.5 → '1.234,50 TL'."""
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " TL"
