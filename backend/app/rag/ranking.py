"""Combine content and heading cosine scores; neither score is a probability."""


def metadata_text(title: str, locator: str) -> str:
    return title + ". " + locator.split("|", 1)[0].strip()


def blend_score(content_score: float, heading_score: float, weight: float) -> float:
    if not 0 <= weight <= 1:
        raise ValueError("Metadata weight must be between 0 and 1")
    return (1 - weight) * content_score + weight * heading_score
