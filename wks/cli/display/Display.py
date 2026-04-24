from abc import ABC, abstractmethod
from typing import Any


class Display(ABC):
    @abstractmethod
    def status(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def success(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        pass

    @abstractmethod
    def progress_start(self, total: int, description: str = "", **kwargs) -> Any:
        pass

    @abstractmethod
    def progress_update(self, handle: Any, advance: int = 1, **kwargs) -> None:
        pass

    @abstractmethod
    def progress_finish(self, handle: Any, **kwargs) -> None:
        pass

    @abstractmethod
    def spinner_start(self, description: str = "", **kwargs) -> Any:
        pass

    @abstractmethod
    def spinner_update(self, handle: Any, description: str, **kwargs) -> None:
        pass

    @abstractmethod
    def spinner_finish(self, handle: Any, message: str = "", **kwargs) -> None:
        pass

    @abstractmethod
    def json_output(self, data: Any, **kwargs) -> None:
        pass
