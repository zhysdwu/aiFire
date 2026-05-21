def clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))
