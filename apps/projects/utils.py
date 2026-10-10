from decimal import Decimal


def format_inr(value, symbol="₹"):
    """
    Format a numeric or Decimal value using Indian numbering system
    with optional currency symbol prefix (default: '₹') and two decimal places.

    Examples:
        format_inr(1000) -> '₹1,000.00'
        format_inr(25500) -> '₹25,500.00'
        format_inr(125000) -> '₹1,25,000.00'
        format_inr(1250000) -> '₹12,50,000.00'
        format_inr(12500000) -> '₹1,25,00,000.00'
        format_inr(45000000) -> '₹4,50,00,000.00'
        format_inr(2940) -> '₹2,940.00'
        format_inr(1140) -> '₹1,140.00'
    """
    if value is None or value == "":
        return f"{symbol}0.00"
    try:
        val = Decimal(str(value))
    except Exception:
        return f"{symbol}0.00"

    is_negative = val < 0
    val = abs(val)

    # Format strictly to 2 decimal places
    s = f"{val:.2f}"
    int_part, dec_part = s.split(".")

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted_int = ",".join(groups) + "," + last3

    res = f"{symbol}{formatted_int}.{dec_part}"
    if is_negative:
        res = f"-{res}"
    return res
