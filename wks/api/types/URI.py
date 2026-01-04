from dataclasses import dataclass


@dataclass(frozen=True)
class URI:
    """Strongly typed URI value object.

    Ensures that any instance holds a valid URI string (containing '://').
    """

    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise TypeError("URI value must be a string")
        if "://" not in self.value:
            raise ValueError(f"Invalid URI format (missing scheme): {self.value}")

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"URI('{self.value}')"
