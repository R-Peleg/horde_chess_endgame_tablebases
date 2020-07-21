from chess.variant import HordeBoard

class ImmutableHordeBoard(object):
    # TODO: improve performance, use symmetry
    def __init__(self, b: HordeBoard):
        self._board = b.copy(stack=False)
        self._board.clear_stack()
        self._board.halfmove_clock = 0
        self._board.fullmove_number = 0 

    def __hash__(self):
        return hash(self._board.fen())

    def __eq__(self, other):
        if isinstance(other, HordeBoard):
            return self._board == other
        elif isinstance(other, ImmutableHordeBoard):
            return self._board == other._board
        else:
            return False
    
    @property
    def board(self):
        return self._board

    def __str__(self):
        return str(self._board)

    def __repr__(self):
        return repr(self._board)
