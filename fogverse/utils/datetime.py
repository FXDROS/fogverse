from datetime import datetime

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

def get_timestamp(utc=True):
    if utc:
        _date = datetime.utcnow()
    else:
        _date = datetime.now()
    return _date

def get_timestamp_str(date=None, utc=True, format=DATETIME_FORMAT):
    date = date or get_timestamp(utc=utc)
    return datetime.strftime(date, format)

def timestamp_to_datetime(timestamp, format=DATETIME_FORMAT):
    if isinstance(timestamp, bytes):
        timestamp = timestamp.decode()
    return datetime.strptime(timestamp, format)

def calc_datetime(start, end=None, format=DATETIME_FORMAT, decimals=2,
                  utc=True):
    if start is None: return -1
    if end is None:
        end = get_timestamp(utc=utc)
    elif isinstance(end, str):
        end = datetime.strptime(end, format)
    if isinstance(start, str):
        start = datetime.strptime(start, format)
    diff = (end - start).total_seconds()*1e3
    return round(diff, decimals)