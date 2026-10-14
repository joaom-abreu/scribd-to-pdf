from collections.abc import Callable

ShouldCancel = Callable[[], bool]


def never_cancel() -> bool:
    return False


def raise_if_cancelled(should_cancel: ShouldCancel, message: str) -> None:
    if should_cancel():
        raise InterruptedError(message)
