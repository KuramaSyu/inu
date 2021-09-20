import random
from fractions import Fraction
import os
import traceback

import hikari
from hikari import embeds
import lightbulb
from lightbulb.context import Context
from lightbulb import plugins
from lightbulb import errors
from lightbulb import events


from utils.logger import build_logger

log = build_logger(__name__)

class inu_random(lightbulb.Plugin):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(name="Random")

    @plugins.listener(events.CommandErrorEvent)
    async def on_error(self, event):
        """The event triggered when an error is raised while invoking a command.
        Parameters
        ------------
        ctx: commands.Context
            The context used for command invocation.
        error: commands.CommandError
            The Exception raised.
        """
        ctx: lightbulb.Context = event.context
        error = event.exception

        if not ctx:
            # creating fake context which has the method respond
            ctx = FakeContext(event.message)
        # This prevents any commands with local handlers being handled here in on_command_error.


        # All other Errors not returned come here. And we can just print the default TraceBack. 
        log.info(
            msg = f"{''.join(traceback.format_exception(type(error), error, error.__traceback__))}"
        )
        #traceback.print_exception(type(error), error, error.__traceback__)#, file=sys.stderr
        

        def check(event):
            if event.user_id != self.bot.user.id and reaction.message_id == message.id:
                return True
            return False
        try:
            title = random.choice(
                ['ERROR', '3RR0R', 'Th3r3 w4s s0m3th1ing wr0ng', '3RR0R 404']
            )
            error_embed = hikari.Embed()
            error_embed.title = title
            error_embed.description = f'{error}'
            message = await ctx.respond(embed = error_embed)
            for reaction in ['🍭', '❔']:
                await message.add_reaction(reaction)
            try:
                event = await self.bot.wait_for(
                    hikari.events.reaction_events.ReactionAddEvent,
                    timeout=int(60*10),
                    predicate=check,
                )
                if str(event.emoji_name) == '🍭':
                    # setting invoker
                    error_embed.set_author(
                        name=f'Invoked by: {ctx.author.nick if ctx.author.nick else ctx.author.name}',
                        icon_url=ctx.author.avatar_url,
                    )
                    # formating traceback to a list ## with .join to a str
                    traceback_list = traceback.format_tb(error.__traceback__)
                    # set error field
                    error_embed.add_field(
                        name=f'{str(error.__class__)[8:-2]}',
                        value=f'Error:\n{error}',
                        )
                    for index, tb in enumerate(traceback_list):
                        # print as codeblock to have \n as newline
                        error_embed.add_field(
                            name=f'Traceback - layer {index + 1}',
                            value=f'```python\n{tb}```',
                            inline=False
                        )

                    if hasattr(error, 'original'):
                        error_embed.add_field(
                            name=f'Original Error - {type(error.original)}',
                            value=f'{error.original}',
                        )
                    await message.edit(embed=error_embed, delete_after=int(20*60))
                    await message.clear_reactions()
                elif str(reaction.emoji) == '❔':
                    help_cog = self.client.get_cog("Help")
                    try:
                        await help_cog.search(ctx, ctx.invoked_with)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            await ctx.send(f'Fehler mit einer Länge von über 2000 Zeichen!')

    """Below is an example of a Local Error Handler for our command do_repeat"""
    @lightbulb.command(aliases=['random', 'randomize'])
    async def fact_randomizer(self, ctx, *, facts):
        '''
        Sends a randomized list
        Parameters:
        facts: Your input list of things - things must be seperated with comma ","
        '''
        fact_list = facts.split(",")
        random.shuffle(fact_list)
        random.shuffle(fact_list)
        shortestFact = int(2000)
        longestFact = int(0)
        interrupt = int(0)

        for element in fact_list:
            length = int(len(element))
            if length > longestFact:
                longestFact = int(length)

        for element in fact_list:
            length1 = int(len(element))
            if int(length1) < int(shortestFact):
                shortestFact = int(length1)

        async def len_compensation(self, fact_list=fact_list, longestFact=longestFact, shortestFact=shortestFact):
            i = 0
            for fact in fact_list:
                if int(len(fact)) < int(longestFact):
                    #print(f'{int(len(fact)) % 4), = modulo zu {fact_list[i]}')
                    if int(len(fact)) % 6 == 0:
                        fact_list[i] = f'-{fact_list[i]}'##############

                    elif int(len(fact)) % 6 == 1:
                        fact_list[i] = f'{fact_list[i]}-'
                    elif int(len(fact)) % 6 == 2:
                        fact_list[i] = f'-{fact_list[i]}'
                    elif int(len(fact)) % 6 == 3:
                        fact_list[i] = f'{fact_list[i]}-'
                    elif int(len(fact)) % 6 == 4:
                        fact_list[i] = f'~{fact_list[i]}'
                    elif int(len(fact)) % 6 == 5:
                        fact_list[i] = f'{fact_list[i]}~'
                i += 1
            return fact_list

        while True:
            shortestFact = int(2000)
            for element in fact_list:
                length1 = int(len(element))
                if length1 <= int(shortestFact):
                    shortestFact = int(length1)
            if shortestFact == longestFact:
                break
            
            fact_list= await len_compensation(self)
            interrupt += 1
            if interrupt == 500:
                break
        #how many columns
        x = float(2)
        gr1 = float(1.5)
        gr2 = float(2.8)
        gr3 = float(3.7)
        gr4 = float(4.7)
        gr5 = float(5.7)
        if 60 / float(longestFact) <= gr1:
            i = 0
            count = 1
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')
            for var in range(0,int(len(fact_list ) + count),count):
                try:
                    fact1 = f'||{fact_list[int(i)]}||'
                except:
                    fact1 = ""
                if fact1 == "":
                    break
                try:
                    await ctx.respond(f'| {fact1:<20}')
                except:
                    break
                i += count
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')
        elif 60 / float(longestFact) <= gr2:
            i = 0
            count = 2
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')

            for var in range(0,int(len(fact_list ) + count),count):
                try:
                    fact1 = f'||{fact_list[int(i)]}||'
                except:
                    fact1 = ""
                try:
                    fact2 = f'||{fact_list[int(i+1)]}||'
                except:
                    fact2 = ""
                if fact1 == "":
                    break
                try:
                    await ctx.respond(f'| {fact1:<20}          {fact2:<20}')
                except:
                    break
                i += count
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')
        elif 60 / float(longestFact) <= gr3:
            i = 0
            count = 3
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')

            for var in range(0,int(len(fact_list ) + count),count):
                try:
                    fact1 = f'||{fact_list[int(i)]}||'
                except:
                    fact1 = ""
                try:
                    fact2 = f'||{fact_list[int(i+1)]}||'
                except:
                    fact2 = ""
                try:
                    fact3 = f'||{fact_list[int(i+2)]}||'
                except:
                    fact3 = ""
                #try:
                    #fact4 = f'||{fact_list[int(i+3)]}||'
                #except:
                    #fact4 = ""
                if fact1 == "":
                    break
                try:
                    await ctx.respond(f'| {fact1:<20}          {fact2:<20}          {fact3:<20}')
                except:
                    break
                i += count
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')
        elif 60 / float(longestFact) <= gr4: 
            i = 0
            count = 4
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')

            for var in range(0,int(len(fact_list ) + count),count):
                try:
                    fact1 = f'||{fact_list[int(i)]}||'
                except:
                    fact1 = ""
                try:
                    fact2 = f'||{fact_list[int(i+1)]}||'
                except:
                    fact2 = ""
                try:
                    fact3 = f'||{fact_list[int(i+2)]}||'
                except:
                    fact3 = ""
                try:
                    fact4 = f'||{fact_list[int(i+3)]}||'
                except:
                    fact4 = ""
                if fact1 == "":
                    break
                try:
                    await ctx.respond(f'| {fact1:<20}       {fact2:<20}       {fact3:<20}       {fact4:<20} ')
                except:
                    break
                i += count
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')
        elif 60 / longestFact > gr4:
            i = 0
            count = 5
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')

            for var in range(0,int(len(fact_list ) + count),count):
                try:
                    fact1 = f'||{fact_list[int(i)]}||'
                except:
                    fact1 = ""
                try:
                    fact2 = f'||{fact_list[int(i+1)]}||'
                except:
                    fact2 = ""
                try:
                    fact3 = f'||{fact_list[int(i+2)]}||'
                except:
                    fact3 = ""
                try:
                    fact4 = f'||{fact_list[int(i+3)]}||'
                except:
                    fact4 = ""
                try:
                    fact5 = f'||{fact_list[int(i+4)]}||'
                except:
                    fact5 = ""
                if fact1 == "":
                    break
                try:
                    await ctx.respond(f'| {fact1:<20}    {fact2:<20}    {fact3:<20}    {fact4:<20}    {fact5:<20}')
                except:
                    break
                i += count
            await ctx.respond(f'————————————————{len(fact_list)}—————————————————')

    @lightbulb.command(aliases=['cube'])
    @lightbulb.cooldowns.cooldown(1, 2.5, lightbulb.UserBucket)
    async def dice(self, ctx, eyes: int = 6) -> None:
        '''
        Roll a dice!
        Parameters:
        [Optional] eyes: how many eyes the cube should have (1-9)
        '''

        if 1 > eyes > 6:
            await ctx.respond('I have dices with 1 to 6 sites. \
                I don\'t know, what kind of magic dices you have')
            return

        # creates discord formated dices 1 - eyes
        eye_ids = [
            f'{os.getcwd()}/inu/data/bot/dices/dice{n}.png' for n in range(1, eyes+1)
        ]
        all_eyes = [eye_ids[eye_num-1] for eye_num in range(1, eyes+1)]
        await ctx.respond(
            attachment=hikari.files.File(random.choice(all_eyes))
            )
        return

    @lightbulb.cooldown(1, 2.5, lightbulb.UserBucket)
    @lightbulb.command()
    async def coin(self, ctx) -> None:
        '''
        Flips a Coin - two sides + can stand
        Parameter:
        /
        '''

        probability = [True for _ in range(0, 100)]
        probability.append(False)
        if random.choice(probability):
            coin = random.choice(["head", "tail"])
            await ctx.respond(
                file=hikari.files.File(
                    f'{os.getcwd()}/other/pictures/coins/{coin}.png'
                    ),
                content=coin
                )
            return
        await ctx.respond('Your coin stands! probability 1:100')
        return

    @lightbulb.cooldowns.cooldown(1, 4, lightbulb.GuildBucket)
    @lightbulb.command(aliases=['prob'])
    async def probability(self, ctx, probability: float = 0.25, probability2: int = None) -> None:
        '''
        Rolles a dice with own probability
        Parameters:
        [Optional] probability = your probability - default: 0.25'''

        def is_float_allowed(num):
            '''checks if number is to long'''
            s_num = str(num)
            if len(s_num) > 7:
                return False
            return True

        # test if any number is too big -> avoid memoryError
        num1 = is_float_allowed(probability)
        num2 = is_float_allowed(probability2)
        if not (num1 and num2):
            await ctx.respond(
                f'Your {"numbers are" if probability2 else "number is"} to big.'
            )
            return
        # creating fraction
        if probability2:
            fraction = Fraction(f'{int(round(probability))}/{probability2}')
        else:
            fraction = Fraction(str(probability))
        d = fraction.denominator
        n = fraction.numerator
        prob_plus = [True for _ in range(n)]
        prob_minus = [False for _ in range(d - n)]
        probabilities = prob_plus + prob_minus
        symbol = random.choice([
            ('🟢', '🔴'), ('🔵', '🟠'), ('✅', '❌'),
            ('🎄', '🎃'), ('🔑', '🔒'), ('🏁', '🏳')
            ])

        # creating dc embed
        embed = hikari.embeds.Embed()
        embed.title = f'probability: {str(n)} in {str(d)}'
        embed.description = f'{symbol[0]} x {n}\n{symbol[1]} x {d - n}'
        embed.add_field(
            name='You got:', 
            value=f'{symbol[0] if random.choice(probabilities) else symbol[1]}'
        )
        embed.set_thumbnail(url=ctx.author.avatar_url)
        embed.color = hikari.colors.Color(0x2A48A8)
        await ctx.respond(embed=embed)
        return


class FakeContext():
    def __init__(
        self,
        message,
    ) -> None:
        self.message = message

    async def respond(self, *args, **kwargs):
        return await self.message.respond(*args, **kwargs)



def load(bot):
    bot.add_plugin(inu_random(bot))