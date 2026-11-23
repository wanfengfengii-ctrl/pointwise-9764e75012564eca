def summarize_day(rows):
    return {
        'row_count': len(rows),
        'total_litres': sum(row['litres'] for row in rows if not row['missing']),
    }
