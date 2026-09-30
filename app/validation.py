"""Shared input validation for every StudyBuddy tool. Raises ValidationError on bad input."""


class ValidationError(Exception):
    pass


def require_text(value, field, min_len=1, max_len=200):
    v = (str(value) if value is not None else "").strip()
    if len(v) < min_len:
        raise ValidationError(f"{field} khali nahi ho sakta.")
    if len(v) > max_len:
        raise ValidationError(f"{field} {max_len} characters se zyada lamba nahi ho sakta.")
    return v


def optional_text(value, field, max_len=200):
    if value is None:
        return None
    v = str(value).strip()
    if len(v) > max_len:
        raise ValidationError(f"{field} {max_len} characters se zyada lamba nahi ho sakta.")
    return v or None


def require_positive_int(value, field, max_value=None):
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} valid number hona chahiye.")
    if v <= 0:
        raise ValidationError(f"{field} positive hona chahiye.")
    if max_value is not None and v > max_value:
        raise ValidationError(f"{field} {max_value} se zyada nahi ho sakta.")
    return v
