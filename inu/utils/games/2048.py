import random

class game2048(object):
    def __init__(self, x=4, y=4):
        self.board = None
        self.x = x
        self.y = y

    
    def main(self):
        self.board = self.creating_board(self.x, self.y)
        self.board = self.add_number(self.board)

    def turn(self):
        if self.game_over():
            return 'Game Over'
        self.direction()
        self.board = self.add_number(self.board)

    def creating_board(self, x=4, y=4):
        """
        creating board x * y filled with None

        Parameters
        ----------
        x = x fields in achsis x
        y = y fields in achsis y
        """
        game_board = []
        for _ in range(0,y):
            row = [None for _ in range(x)]
            game_board.append(row)
        return game_board, x, y
    
    def add_number(self, board):
        numbers = [1,1,1,1,2,2,4]
        number = random.choice(numbers)
        # add the number to a = None field
        while True:
            row = random.randrange(0, int(self.y -1))
            cell = random.randrange(0, int(self.x - 1))
            if board[row][cell] == None:
                board[row][cell] = number
                break
        return board

    def game_over(self):
        for row in self.board:
            for cell in row:
                if cell == None:
                    return False
        return True

    def direction(self, direction):
        if direction == 'right':
            for row in self.board:

                def add_numbers_in_row_to_right(row, i):
                    if i == len(row - 1) or not row[i]:
                        i -= 1
                        add_numbers_in_row_to_right(row, i)
                        return
                    elif row[i] == row[i + 1]:
                        row.pop[i + 1]
                        row[i] = int(row[i]) * 2
                        row.insert(0, None)
                        if i > 1:
                            i -= 2
                        elif i == 1:
                            
                        if i <= self.x:
                            add_numbers_in_row_to_right(row, i)
                            return
                    elif i > 0:
                        i -= 1
                        add_numbers_in_row_to_right(row, i)
                    return
                add_numbers_in_row_to_right(row, i = 0)
        elif 

                    

            


        