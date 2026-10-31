from typing import Sequence, Tuple
from tp1.types.coords import Coords

# (PlayerCoords, [BoxCoords])
type SokobanBoardState = Tuple[Coords, Sequence[Coords]]
