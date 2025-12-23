"""WikiLink model (UNO: single model)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WikiLink:
    """A parsed wiki link from markdown."""

    line_number: int
    column_number: int
    is_embed: bool
    target: str
    alias: str
    raw_target: str

    @staticmethod
    def split_alias(target: str) -> tuple[str, str]:
        """Split target|alias into components.

        Handles both regular pipes (|) and escaped pipes (\\|) used in tables.
        """
        # Handle escaped pipe (\|) - common in markdown tables
        if "\\|" in target:
            core, alias = target.split("\\|", 1)
            return core.strip(), alias.strip()
        # Handle regular pipe
        if "|" in target:
            core, alias = target.split("|", 1)
            return core.strip(), alias.strip()
        return target.strip(), ""
