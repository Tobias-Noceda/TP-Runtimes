class Base[T]:
    pass


class Box[T](Base[T]):          # type parameter used in the base, as tp1's BoardManager
    def __init__(self, v: T):
        self.v = v
