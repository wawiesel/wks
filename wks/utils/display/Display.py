"""Abstract base class for display implementations."""

from abc import ABC, abstractmethod
from typing import Any


class Display(ABC):
    """Abstract base for CLI and MCP display implementations."""

    @abstractmethod
    def status(self, message: str, **kwargs) -> None:
        """Display a status message.

        Args:
            message: Status text to display
            kwargs: Implementation-specific options
        """
        pass

    @abstractmethod
    def success(self, message: str, **kwargs) -> None:
        """Display a success message.

        Args:
            message: Success text
            kwargs: Implementation-specific options (e.g., data for MCP)
        """
        pass

    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        """Display an error message.

        Args:
            message: Error text
            kwargs: Implementation-specific options (e.g., details for MCP)
        """
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        """Display a warning message.

        Args:
            message: Warning text
            kwargs: Implementation-specific options
        """
        pass

    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        """Display an informational message.

        Args:
            message: Info text
            kwargs: Implementation-specific options
        """
        pass

    @abstractmethod
    def progress_start(self, total: int, description: str = "", **kwargs) -> Any:
        """Start a progress bar/indicator.

        Args:
            total: Total number of items
            description: Description of operation
            kwargs: Implementation-specific options

        Returns:
            Progress handle/context for updates
        """
        pass

    @abstractmethod
    def progress_update(self, handle: Any, advance: int = 1, **kwargs) -> None:
        """Update progress.

        Args:
            handle: Progress handle from progress_start
            advance: Number of items to advance
            kwargs: Implementation-specific options (description update, etc.)
        """
        pass

    @abstractmethod
    def progress_finish(self, handle: Any, **kwargs) -> None:
        """Finish/close progress indicator.

        Args:
            handle: Progress handle from progress_start
            kwargs: Implementation-specific options
        """
        pass

    @abstractmethod
    def spinner_start(self, description: str = "", **kwargs) -> Any:
        """Start a spinner for indeterminate operations.

        Args:
            description: Description of operation
            kwargs: Implementation-specific options

        Returns:
            Spinner handle/context for updates
        """
        pass

    @abstractmethod
    def spinner_update(self, handle: Any, description: str, **kwargs) -> None:
        """Update spinner description.

        Args:
            handle: Spinner handle from spinner_start
            description: New description
            kwargs: Implementation-specific options
        """
        pass

    @abstractmethod
    def spinner_finish(self, handle: Any, message: str = "", **kwargs) -> None:
        """Finish/stop spinner.

        Args:
            handle: Spinner handle from spinner_start
            message: Final message to display
            kwargs: Implementation-specific options
        """
        pass

    @abstractmethod
    def json_output(self, data: Any, **kwargs) -> None:
        """Output structured data (for MCP, this is the main output method).

        Args:
            data: Data to output
            kwargs: Implementation-specific options (indent, etc.)
        """
        pass
