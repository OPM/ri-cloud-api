import datetime

def timestamp_utc_ms_to_iso_str(timestamp_utc_ms: int, always_include_milliseconds: bool = True) -> str:
    """
    Convert integer timestamp in milliseconds UTC to ISO 8601 string
    The returned string will always be one of these formats:
      YYYY-MM-DDTHH:MM:SS.fffZ
      YYYY-MM-DDTHH:MM:SSZ
    """
    dt_obj = datetime.datetime.fromtimestamp(timestamp_utc_ms / 1000, tz=datetime.timezone.utc)

    # Include milliseconds only if present or forced by flag
    if dt_obj.microsecond != 0 or always_include_milliseconds:
        isostr = dt_obj.isoformat(timespec="milliseconds")
    else:
        isostr = dt_obj.isoformat()

    # Since dt_obj has time zone, isoformat() always returns string with UTC offset, which for UTC will be: "+00:00"
    # Replace with Z which is the convention we use
    isostr = isostr.replace("+00:00", "Z")

    return isostr

def iso_str_to_date_str(iso_str: str) -> str:
    """
    Extract the date portion from an ISO 8601 string

    Handles formats like:
      '2018-01-01T00:00:00'
      '2018-01-01T00:00:00.000Z'
      '2018-01-01T00:00:00Z'
      '2018-01-01'

    Returns: 'YYYY-MM-DD'
    """
    # Split on 'T' and take the date portion
    return iso_str.split("T")[0]
