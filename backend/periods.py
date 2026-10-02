from datetime import date, timedelta


def add_months(value: date, months: int) -> date:
    ordinal = value.year * 12 + value.month - 1 + months
    return date(ordinal // 12, ordinal % 12 + 1, 1)


def period_bounds(year, period_type="ACADEMIC_YEAR", period=1):
    lengths = {"MONTHLY": 1, "QUARTERLY": 3, "HALF_YEARLY": 6, "ACADEMIC_YEAR": 12}
    if period_type not in lengths:
        raise ValueError("Unknown period type")
    months = lengths[period_type]
    if not 1 <= period <= 12 // months:
        raise ValueError("Period number is out of range")
    start = add_months(year.start_date, (period - 1) * months)
    return start, min(add_months(start, months) - timedelta(days=1), year.end_date)


def period_options(year, period_type):
    count = {"MONTHLY": 12, "QUARTERLY": 4, "HALF_YEARLY": 2, "ACADEMIC_YEAR": 1}.get(period_type)
    if count is None:
        raise ValueError("Unknown period type")
    result = []
    for i in range(1, count + 1):
        start, end = period_bounds(year, period_type, i)
        label = start.strftime("%B %Y") if period_type == "MONTHLY" else {"QUARTERLY": "Q", "HALF_YEARLY": "H", "ACADEMIC_YEAR": "AY "}[period_type] + (year.name if count == 1 else str(i))
        result.append({"value": i, "label": label, "start_date": start, "end_date": end})
    return result
