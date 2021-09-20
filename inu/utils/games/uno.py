import math
import random
import re

class uno():
    def __init__(self, players: list, cards_per_player = 10):
        self.players = players
        self.cards_per_player = cards_per_player
        self.stack = []
        self.cast_off_stack = []
        self.clockwise = True
        self.hands = {}
        self.draw_cards = 0
        self.gameover = False
        self.winner = None
    
    def create_stack(self):
        numbers = [0,1,2,3,4,5,6,7,8,9]
        colors = ['red', 'green', 'blue', 'yellow']

        for color in colors:
            for _ in range(0,4):
                card = {'name':f'2+ | {color}',
                'color':[color],
                'number':[None],
                'usage':'draw_cards_2',
                'needs_color':False,}
                self.stack.append(card)   

                card = {'name':f'Reverse | {color}',
                'color':[color],
                'number':[None],
                'usage':'reverse',
                'needs_color':False,}
                self.stack.append(card)     

                card = {'name':f'Stop | {color}',
                'color':[color],
                'number':[None],
                'usage':'stop',
                'needs_color':False,}
                self.stack.append(card)    

            for number in numbers:
                if number == 0:
                    for _ in range(0,2):
                        card = {'name':f'{number} | {color}',
                        'color':[color],
                        'number':[number],
                        'usage':'normal',
                        'needs_color':False,}
                        
                else:
                    for _ in range(0,4):
                        card = {'name':f'{number} | {color}',
                        'color':[color],
                        'number':[number],
                        'usage':'normal',
                        'needs_color':False,}
                        
                self.stack.append(card)
        for _ in range(0,4):
            card = {'name':f'4+ | RGB',
            'color':[colors],
            'number':[None],
            'usage':'draw_cards_4',
            'needs_color':False,}
                  
            self.stack.append(card)   
            card = {'name':f'Color Changer | RGB',
            'color':[colors],
            'number':[None],
            'usage':'change_color',
            'needs_color':True,}
                 
            self.stack.append(card)   
        for _ in range(0,3):
            random.shuffle(self.stack)


    def create_cast_off_stack(self):
        while True:
            card = self.stack.pop(0)
            if card['usage'] == 'draw_cards_2':
                self.draw_cards += 2
                break
            elif card['usage'] == 'normal':
                break
            else:
                self.stack.append(card)
                continue
        self.cast_off_stack.append(card)

    
    def create_hands(self):
        for player in self.players:
            self.hands[player] = []
            for _ in range(0,self.cards_per_player):
                card = self.stack.pop(0)
                self.hands[player].append(card)


    def start_game(self):
        self.create_stack()
        self.create_cast_off_stack()
        self.create_hands()
        random.shuffle(self.players)

    
    def get_next_player(self):
        return self.players[0]


    def main(self, card = False, color = False):
        turn = self.players[0]
        if len(self.stack) > int(self.draw_cards + 5):
            self.create_stack()

        if card == False or card == None:
            if self.draw_cards == 0:
                self.draw_cards = 1
            for _ in range(0,self.draw_cards):
                card2 = self.stack.pop(0)
                self.hands[turn].append(card2)
            self.__prepare(color=color, turn=turn, card=card)
            self.draw_cards = 0
            return True, f'You drawed a card:\n\n{card2["name"]}'

        #look for missing values
        top_card = self.cast_off_stack[-1]
        if card['usage'] == 'draw_cards_4' and color == False:
            return False, f'You have to choose a Color. Choose again!'
        if card['usage'] == 'change_color' and color == False:
            return False, f'You have to choose a Color. Choose again!'
        if color == False or color == None:
            color = card['color']

        # add to stack with logic
        if card['usage'] == 'draw_cards_4':
            self.draw_cards += 4
            self.__prepare(color=color, turn=turn, card=card)
            return True, False
        elif top_card['usage'] in ['draw_cards_4','draw_cards_2'] and self.draw_cards != 0:
            if card['usage'] == 'draw_cards_2':
                self.draw_cards += 2
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'reverse':
                self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'stop':
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}.'
            elif card['usage'] == 'change_color':
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            elif card['usage'] == 'normal':
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            else:
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

        elif top_card['usage'] in ['reverse'] and self.draw_cards > 0:
            if card['usage'] == 'draw_cards_2':
                self.draw_cards += 2
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'reverse':
                self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'stop':
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}.'
            elif card['usage'] == 'change_color':
                #self.__reverse()
                #self.__prepare(color=color, turn=turn, card=card)
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}.'
            elif card['usage'] == 'normal':
                #self.__prepare(color=color, turn=turn, card=card)
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}. Maybe in the last cards are plus Cards. Then you have to draw'
            else:
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

        elif self.draw_cards != 0:
            #self.__prepare(color=color, turn=turn, card=card)
            return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

        elif top_card['usage'] in ['draw_cards_4','draw_cards_2']:
            if card['usage'] == 'draw_cards_2':
                self.draw_cards += 2
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'reverse' and card['color'][0] in top_card['color']:
                self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'stop' and card['color'][0] in top_card['color']:
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'change_color':
                #self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'normal':
                if card['color'][0] in top_card['color'] or card['number'][0] in top_card['number'] and self.draw_cards == 0:
                    self.__prepare(color=color, turn=turn, card=card)
                    return True, False
                else:
                    return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            else:
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

        elif top_card['usage'] in ['stop']:
            if card['usage'] == 'draw_cards_2' and card['color'][0] in top_card['color']:
                self.draw_cards += 2
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'reverse' and card['color'][0] in top_card['color']:
                self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'stop':
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'change_color':
                #self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'normal':
                if card['color'][0] in top_card['color'] or card['number'][0] in top_card['number'] and self.draw_cards == 0:
                    self.__prepare(color=color, turn=turn, card=card)
                    return True, False
                else:
                    return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            else:
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

        elif top_card['usage'] in ['reverse']:
            if card['usage'] == 'draw_cards_2':
                self.draw_cards += 2
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'reverse':
                self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'stop' and card['color'][0] in top_card['color']:
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'change_color':
                #self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'normal':
                if card['color'][0] in top_card['color'] or card['number'][0] in top_card['number']:
                    self.__prepare(color=color, turn=turn, card=card)
                    return True, False
                else:
                    return False, f'You cant put a {card["name"]} on a {top_card["name"]}. Maybe in the last cards are plus Cards. Then you have to draw'
            else:
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

        elif top_card['usage'] in ['change_color'] and self.draw_cards == 0:
            if card['usage'] == 'draw_cards_2' and card['color'][0] in top_card['color']:
                self.draw_cards += 2
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'reverse' and card['color'][0] in top_card['color']:
                self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'stop' and card['color'][0] in top_card['color']:
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'change_color':
                #self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'normal':
                if card['color'][0] in top_card['color'] or card['number'][0] in top_card['number']:
                    self.__prepare(color=color, turn=turn, card=card)
                    return True, False
                else:
                    return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            elif card['usage'] == 'normal':
                if card['color'][0] in top_card['color'] or card['number'][0] in top_card['number']:
                    self.__prepare(color=color, turn=turn, card=card)
                    return True, False
                else:
                    return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            else:
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

        elif top_card['usage'] in ['normal'] and self.draw_cards == 0:
            if card['usage'] == 'draw_cards_2' and card['color'][0] in top_card['color']:
                self.draw_cards += 2
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'reverse' and card['color'][0] in top_card['color']:
                self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'stop' and card['color'][0] in top_card['color']:
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'change_color':
                #self.__reverse()
                self.__prepare(color=color, turn=turn, card=card)
                return True, False
            elif card['usage'] == 'normal':
                if card['color'][0] in top_card['color'] or card['number'][0] in top_card['number']:
                    self.__prepare(color=color, turn=turn, card=card)
                    return True, False
                else:
                    return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            elif card['usage'] == 'normal':
                if card['color'][0] in top_card['color'] or card['number'][0] in top_card['number']:
                    self.__prepare(color=color, turn=turn, card=card)
                    return True, False
                else:
                    return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
            else:
                return False, f'You cant put a {card["name"]} on a {top_card["name"]}'
        else: 
            return False, f'You cant put a {card["name"]} on a {top_card["name"]}'

                
                
    
    def __prepare(self, turn, card, color):
        x = 1
        if card != False and card != None:
            if card['usage'] == 'stop':
                x += 1
        for _ in range(0,x):
            if self.clockwise:
                player = self.players.pop(0)
                self.players.append(player)
            else:
                if len(self.players) > 2:
                    player = self.players.pop(0)
                    self.players.reverse()
                    self.clockwise = True
                    self.players.append(player)
                else:
                    self.clockwise = True 

        if card != False and card != None:
            self.hands[turn].remove(card)
            if color != False and color != None and card['usage'] in ['draw_cards_4', 'change_color']:
                card['color'] = [color]
            self.cast_off_stack.append(card)
        else:
            pass
        self.gameover = self.is_gameover()

    def __reverse(self):
        if self.clockwise:
            self.clockwise = False
        else:
            self.clockwise = True
        return

    def get_info(self):
        if self.clockwise:
            player = self.players[0]

        else:
            player = self.players[-1]

        top_card = self.cast_off_stack[-1]
        #for key in top_card.keys():
        #    top_card["name"] = key
        if self.draw_cards == 0:
            draw_cards = 1
        else: draw_cards = self.draw_cards
        return player, top_card, draw_cards, self.gameover, self.winner

    def get_hand(self, player):
        cards = []
        hand = self.hands[player]
        for card in hand:
            cards.append(card['name'])
        return '; '.join(cards), hand


    def is_gameover(self):
        for player, hand in self.hands.items():
            if hand == []:
                self.gameover = True
                self.winner = player
                return True
        return False


    def print_card(self, hand, add_card_numbers = True, only_top_card = False):
        hand2 = hand.copy()
        if type(hand) != list:
            card = hand2
            hand2 = [card]

        def change_color(card, color, usage):
            
            card_print = []
            for line_i ,line in enumerate(card):
                if usage not in ['draw_cards_4', 'change_color']:
                    if color == 'red':
                        block_3 = re.sub('🟦','🟥',line)
                    elif color == 'yellow':
                        block_3 = re.sub('🟦','🟨',line)
                    elif color == 'green':
                        block_3 = re.sub('🟦','🟩',line)
                    else:
                        block_3 = line          
                else: block_3 = line 
                if not only_top_card:
                    block_3 = f'{block_3} ░ '
                card_print.append([block_3])
            return card_print



        card_1=['⬛⬛🟦', 
                '⬛⬛🟦',
                '⬛⬛🟦',
                '⬛⬛🟦',
                '⬛⬛🟦']

        card_2=['🟦🟦🟦',
                '⬛⬛🟦',
                '🟦🟦🟦',
                '🟦⬛⬛',
                '🟦🟦🟦']

        card_3=['🟦🟦🟦',
                '⬛⬛🟦',
                '🟦🟦🟦',
                '⬛⬛🟦',
                '🟦🟦🟦']

        card_4=['🟦⬛🟦',
                '🟦⬛🟦',
                '🟦🟦🟦',
                '⬛⬛🟦',
                '⬛⬛🟦']

        card_5=['🟦🟦🟦',
                '🟦⬛⬛',
                '🟦🟦🟦',
                '⬛⬛🟦',
                '🟦🟦🟦']

        card_6=['🟦🟦🟦',
                '🟦⬛⬛',
                '🟦🟦🟦',
                '🟦⬛🟦',
                '🟦🟦🟦']

        card_7=['🟦🟦🟦',
                '⬛⬛🟦',
                '⬛⬛🟦',
                '⬛⬛🟦',
                '⬛⬛🟦']

        card_8=['🟦🟦🟦',
                '🟦⬛🟦',
                '🟦🟦🟦',
                '🟦⬛🟦',
                '🟦🟦🟦']

        card_9=['🟦🟦🟦',
                '🟦⬛🟦',
                '🟦🟦🟦',
                '⬛⬛🟦',
                '🟦🟦🟦']

        card_0=['🟦🟦🟦',
                '🟦⬛🟦',
                '🟦⬛🟦',
                '🟦⬛🟦',
                '🟦🟦🟦']

        card_stop=  ['🟦⬛🟦',
                    '🟦⬛🟦',
                    '⬛🟦⬛',
                    '🟦⬛🟦',
                    '🟦⬛🟦']

        card_color_changer=['🟦🟩🟩',
                            '🟦⬛⬛',
                            '⬛⬛⬛',
                            '⬛⬛🟥',
                            '🟨🟨🟥']

        card_draw_cards_4=['🟥⬛🟩',
                            '🟥⬛🟩',
                            '🟨🟨🟦',
                            '⬛⬛🟦',
                            '⬛⬛🟦']

        card_draw_cards_2=['🟦🟦🟦',
                            '⬛🟪🟦',
                            '🟪🟪🟪',
                            '🟦🟪⬛',
                            '🟦🟦🟦']

        card_reverse=['⬛🟦🟦',
                        '⬛⬛🟦',
                        '⬛⬛⬛',
                        '🟦⬛⬛',
                        '🟦🟦⬛']
        card_rows = []
        print_lines = ''
        card_number = 1
        while True:
            # get max. 6 cards
            if len(hand2) == 0:
                break
            
            cards_6 = []
            for i in range(0,6):
                if len(hand2) > 0:
                    cards_6.append(hand2.pop(0))
                    if only_top_card:
                        break
                else: break

            # first line
            if add_card_numbers:
                print_lines = f'{print_lines}\n'
                for j in range(len(cards_6)):
                    print_lines = f'{print_lines}┌----{card_number}----┐'
                    card_number += 1

            # card lines       
            line_1 = ''
            line_2 = ''
            line_3 = ''
            line_4 = ''
            line_5 = ''
            print_lines = f'{print_lines}\n'
            for index, card in enumerate(cards_6):
                if card['usage'] == 'draw_cards_4':
                    card_to_print = card_draw_cards_4
                elif card['usage'] == 'draw_cards_2':
                    card_to_print = card_draw_cards_2
                elif card['usage'] == 'reverse':
                    card_to_print = card_reverse
                elif card['usage'] == 'change_color':
                    card_to_print = card_color_changer
                elif card['usage'] == 'stop':
                    card_to_print = card_stop
                elif card['usage'] == 'normal':
                    if card['number'][0] == 0:
                        card_to_print = card_0
                    elif card['number'][0] == 1:
                        card_to_print = card_1
                    elif card['number'][0] == 2:
                        card_to_print = card_2                    
                    elif card['number'][0] == 3:
                        card_to_print = card_3
                    elif card['number'][0] == 4:
                        card_to_print = card_4
                    elif card['number'][0] == 5:
                        card_to_print = card_5
                    elif card['number'][0] == 6:
                        card_to_print = card_6        
                    elif card['number'][0] == 7:
                        card_to_print = card_7
                    elif card['number'][0] == 8:
                        card_to_print = card_8
                    elif card['number'][0] == 9:
                        card_to_print = card_9
                card_converted = change_color(card=card_to_print, color=card['color'][0], usage=card['usage'])  
                line_1 = f'{line_1}{"".join(card_converted[0])}'
                line_2 = f'{line_2}{"".join(card_converted[1])}'
                line_3 = f'{line_3}{"".join(card_converted[2])}'     
                line_4 = f'{line_4}{"".join(card_converted[3])}' 
                line_5 = f'{line_5}{"".join(card_converted[4])}'  
            print_lines = f'{print_lines}{line_1}\n{line_2}\n{line_3}\n{line_4}\n{line_5}'
            if not only_top_card:
                print_lines = f'{print_lines}\n{str("░░░░░░░")*len(cards_6)}'
            #print(f'{print_lines}{line_1}\n{line_2}\n{line_3}\n{line_4}\n{line_5}#')
            card_rows.append(print_lines)
            print_lines = ''
            if only_top_card: break

        return card_rows































x = False
if __name__ == "__main__" and x == True:
    game = uno(['paul', 'artur'])
    game.start_game()
    while True:
        player, top_card, draw_cards, gameover, winner = game.get_info()
        cards, hand = game.get_hand(player)
        print(f'----info------\nplayer = {player}\ntop_card = {top_card["name"]}\ngameover = {gameover}\n winner = {winner}\nYOUR HAND:\n{cards}')
        if gameover:
            print('GAME IS OVER')
            break
        else:
            print('Cast a card:\n')
            x = 0
            print(f'x - draw cards')

            for card in hand:
                for name, data in card.items():
                    print(f'{x} - {name}')
                    x += 1
            card_to_cast = input('Number:\n')
            if str(card_to_cast) != "x":
                for key in hand[int(card_to_cast)].keys():
                    card["name"] = key
                print(card_to_cast)
                print(card["name"])
                print(hand[int(card_to_cast)])
                print(hand[int(card_to_cast)]['number'])
                

                #hand[int(card_to_cast)]['needs_color'])
                if bool(hand[int(card_to_cast)]['needs_color']):
                    color = input('New Color:')
                    color = color.lower()
                    if int(card_to_cast) == x:
                        n, info = game.main(card = False)
                    else:
                        n, info = game.main(card = hand[int(card_to_cast)], color = color)
                    if not n:
                        print(info)
                else:
                    if int(card_to_cast) == x:
                        n, info = game.main(card = False)
                    else:
                        n, info = game.main(card = hand[int(card_to_cast)])
                    if not n:
                        print(info)
            else:
                n, info = game.main(card = False)
                if not n:
                    print(info)
        
#



                        

        