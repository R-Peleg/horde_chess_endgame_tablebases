import chess
import itertools
from chess.variant import HordeBoard
import time
import csv
from immutable_horde_board import ImmutableHordeBoard

# Final known position value
class PositionValue(object):
    def __init__(self, winning_side, distance_to_zero):
        self.winning_side = winning_side
        self.distance_to_zero = distance_to_zero

    def __str__(self):
        return '{0} wins with {1} DTZ'.format(chess.COLOR_NAMES[self.winning_side], self.distance_to_zero)


class KingOnlyPositionGenerator(object):
    def generate_position_maps(self):
        for i in chess.SQUARES:
            yield {
                i: chess.Piece(chess.KING, chess.BLACK)
            }

class KingVSPiecePositionGenerator(object):
    def __init__(self, white_piece):
        self.white_piece = white_piece

    def generate_position_maps(self):
        for i, j in itertools.permutations(chess.SQUARES, 2):
            if self.white_piece == chess.PAWN and chess.square_rank(j) == 8:
                continue # Pawn in 8th rank is already promoted
            yield {
                i: chess.Piece(chess.KING, chess.BLACK),
                j: chess.Piece(self.white_piece, chess.WHITE)
            }

    def __str__(self):
        return "king vs {0}".format(chess.PIECE_NAMES[self.white_piece])

class KingVSTwoPiecesPositionGenerator(object):
    def __init__(self, white_piece1, white_piece2):
        self.white_piece1 = white_piece1
        self.white_piece2 = white_piece2

    def generate_position_maps(self):
        # TODO: Avoid duplicates when piece1 and piece2 are the same
        for i, j, k in itertools.permutations(chess.SQUARES, 3):
            if self.white_piece1 == chess.PAWN and chess.square_rank(j) == 8:
                continue # Pawn in 8th rank is already promoted
            if self.white_piece2 == chess.PAWN and chess.square_rank(k) == 8:
                continue # Pawn in 8th rank is already promoted
            if self.white_piece1 == self.white_piece2:
                # Same piece, avoid repetitions
                if j > k:
                    continue
            yield {
                i: chess.Piece(chess.KING, chess.BLACK),
                j: chess.Piece(self.white_piece1, chess.WHITE),
                k: chess.Piece(self.white_piece2, chess.WHITE)
            }
    
    def __str__(self):
        return "king vs {0} and {1}".format(chess.PIECE_NAMES[self.white_piece1], chess.PIECE_NAMES[self.white_piece2])

def positions_for_maps(maps):
    for position_dict in maps:
        board = HordeBoard.empty()
        board.set_piece_map(position_dict)
        for t in chess.COLORS:
            board.turn = t
            if board.is_valid():
                yield ImmutableHordeBoard(board)

def main():

    generators = [
        KingOnlyPositionGenerator(),
        KingVSPiecePositionGenerator(chess.QUEEN),
        KingVSPiecePositionGenerator(chess.ROOK),
        KingVSPiecePositionGenerator(chess.BISHOP),
        KingVSPiecePositionGenerator(chess.KNIGHT),
        KingVSPiecePositionGenerator(chess.PAWN),

        KingVSTwoPiecesPositionGenerator(chess.QUEEN, chess.QUEEN),
        KingVSTwoPiecesPositionGenerator(chess.QUEEN, chess.PAWN),
        KingVSTwoPiecesPositionGenerator(chess.PAWN, chess.PAWN),
    ]

    endgame_table = { }
    try:
        for generator in generators:
            # Mark checkmates
            print("Marking checkmates for endgame: {0}".format(generator))
            start = time.time()
            for b in positions_for_maps(generator.generate_position_maps()):
                if b.board.is_checkmate():
                    endgame_table[b] = PositionValue(chess.WHITE, 0)
                elif b.board.turn == chess.WHITE and b.board.is_variant_loss():
                    endgame_table[b] = PositionValue(chess.BLACK, 0)

            print('After marking checkmates: {0} positions, in {1}s'.format(len(endgame_table), time.time() - start))

            # Retrogade forced checkmates
            print("Applying back analysis")
            for iteration_number in range(50):
                iteration_start = time.time()
                db_changed_in_iteration = False
                for b in positions_for_maps(generator.generate_position_maps()):
                    if b in endgame_table:
                        # Already in DB, no need to re-calculate
                        # TODO: this can mess up with DTZ calculation. Remove?
                        continue

                    board = b.board.copy(stack=False)
                    if board.is_game_over():
                        continue

                    min_distance_to_win = 9999
                    max_distance_to_lose = -1
                    can_win = False
                    is_forced_loss = True
                    b_turn = board.turn
                    for m in board.legal_moves:
                        is_zeroing = board.is_zeroing(m)
                        board.push(m)
                        next_move_result: PositionValue = endgame_table.get(ImmutableHordeBoard(board))
                        if next_move_result is None:
                            # No definite result
                            is_forced_loss = False
                        # TODO: zero DTZ on pawn moves
                        elif next_move_result.winning_side == b_turn:
                            is_forced_loss = False
                            can_win = True
                            if is_zeroing:
                                min_distance_to_win = 0
                                board.pop()
                                break
                            min_distance_to_win = min(min_distance_to_win, next_move_result.distance_to_zero)
                        else:
                            if not is_zeroing:
                                max_distance_to_lose = max(max_distance_to_lose, next_move_result.distance_to_zero)
                        board.pop()
                    if can_win:
                        endgame_table[b] = PositionValue(b_turn, min_distance_to_win + 1)
                        db_changed_in_iteration = True
                    elif is_forced_loss:
                        endgame_table[b] = PositionValue(not b_turn, max_distance_to_lose + 1)
                        db_changed_in_iteration = True
                print('Iteration {0}: {1} positions (took {2}s)'.format(
                    iteration_number + 1, len(endgame_table), time.time() - iteration_start))
                if not db_changed_in_iteration:
                    break
    except KeyboardInterrupt:
        print('Interrupted, showing results')

    for b in itertools.islice(endgame_table, 0, 1000000, 5000):
        print(b)
        print(endgame_table[b])
        print()

    with open('endgame_db.csv', 'w') as f:
        writer = csv.writer(f)
        for position, result in endgame_table.items():
            writer.writerow([
                position.board.fen(),
                chess.COLOR_NAMES[result.winning_side],
                result.distance_to_zero
            ])

if __name__ == "__main__":
    main()
