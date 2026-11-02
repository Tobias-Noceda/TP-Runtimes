from typing import Generic, TypeVar

T = TypeVar("T")


class Base(Generic[T]):
    pass


class Child(Base[int]):
    pass
