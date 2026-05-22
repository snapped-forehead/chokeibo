"""集計ロジック"""
from datetime import date, timedelta
import calendar


def _monday(d):
    return d - timedelta(days=d.weekday())


def get_periods(today=None):
    """各期間の開始日・終了日を返す"""
    t = today or date.today()
    last_monday = _monday(t)
    prev_monday = last_monday - timedelta(weeks=1)

    first_this_month = t.replace(day=1)
    first_last_month = (first_this_month - timedelta(days=1)).replace(day=1)
    last_last_month  = first_this_month - timedelta(days=1)

    return {
        '当日':  (t, t),
        '昨日':  (t - timedelta(days=1), t - timedelta(days=1)),
        '今週':  (last_monday, t),
        '先週':  (prev_monday, last_monday - timedelta(days=1)),
        '今月':  (first_this_month, t),
        '先月':  (first_last_month, last_last_month),
        '今年':  (t.replace(month=1, day=1), t),
    }


def aggregate(rows, start, end):
    """
    rows: [['YYYY/MM/DD', '科目', 金額文字列, '摘要', '登録日時'], ...]
    科目別集計 {'科目名': 合計金額} を返す
    """
    totals = {}
    for row in rows:
        if len(row) < 3:
            continue
        try:
            d = date.fromisoformat(row[0].replace('/', '-'))
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        category = row[1] if len(row) > 1 else ''
        try:
            amount = int(str(row[2]).replace(',', ''))
        except (ValueError, TypeError):
            continue
        totals[category] = totals.get(category, 0) + amount
    return totals


def build_summary(rows, today=None):
    """全期間の集計結果を返す"""
    periods = get_periods(today)
    result = {}
    for label, (start, end) in periods.items():
        result[label] = aggregate(rows, start, end)
    return result
