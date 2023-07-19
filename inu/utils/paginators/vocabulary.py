import asyncio
from typing import *
import random
import time

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed, ResponseType
from hikari.impl import MessageActionRowBuilder

from .base import PaginatorReadyEvent, Paginator, listener

from core import getLogger, InuContext, ConfigProxy, ConfigType, BotResponseError, get_context
from utils import Human, Colors, MyAnimeList, Anime, Tag, crumble

log = getLogger(__name__)



config = ConfigProxy(ConfigType.YAML)
VOCAB_BIAS: float = 1.8  # a bias for chosing a vocable. the higher the value, the highter the prop of a unknown vocable chosen
STORED_TRIES: int = 5

class Vocable:
    __slots__: List[str] = ["tries", "key", "value"]

    def __init__(
            self,
            key: str,
            value: str,
    ):
        self.tries: List[bool] = []
        self.key = key
        self.value = value 

    def add_try(self, guess: bool):
        self.tries.append(guess)
        if len(self.tries) > STORED_TRIES+4:
            self.tries.pop(0)
    
    def get_last_tries(self, x: int = STORED_TRIES) -> List[bool]:
        l = list(reversed(self.tries))
        return l[:x]
    
    def _get_success_rate_of_last_x_tries(self, x: int = STORED_TRIES) -> float:
        if len(self.tries) < x:
            x = max(len(self.tries), 1)
        return (sum(self.get_last_tries(x=x))/x)
    
    @property
    def success_rate(self) -> float:
        """
        retruns success rate of last STORED_TRIES tries.
        """
        return self._get_success_rate_of_last_x_tries()
    
    @property
    def weight(self) -> float:
        return (1 - max(min(self.success_rate, 0.9), 0.1)) ** VOCAB_BIAS
    
    def __str__(self) -> str:
        return f"**{self.key}**: {self.value}"
    
    def __repr__(self) -> str:
        return f"Vocable<{self.key=},{self.value=},{self.tries},{self.success_rate=},{self.weight=}>"
    
    @property
    def result_str(self) -> str:
        return f"**{self.key}**: {self.success_rate}"


class VocabularyPaginator(Paginator):
    def __init__(
        self,
        tag: Tag,
    ):
        self._rates:Dict[str, float] = {}
        self._languages: Optional[Tuple[str, str]] = None
        self._vocabulary: Dict[str, str] = {}
        
        self._embeds = []
        self.tag = tag
    
    async def parse_tag_and_create_embeds(self) -> bool:
        """
        wether or not parsing was successfull
        """
        try:
            self._languages, self._vocabulary = convert_vocabulary(self.tag)
        except BotResponseError as e:
            await self.ctx.respond(**e.context_kwargs)
            return False
        bare_text = ""
        if self._languages:
            bare_text += f"**{self._languages[0]}** - {self._languages[1]}\n\n"
        for key, value in self._vocabulary.items():
            bare_text += f"**{key}** : {value}\n"
        for part in crumble(bare_text):
            self._embeds.append(Embed(title=self.tag.name, description=part))
        return True


    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        components = super().build_default_components(position)
        components.append(
            MessageActionRowBuilder()
            .add_interactive_button(
                ButtonStyle.SECONDARY, 
                "vocabulary_start_training",
                label="learn ⤵️"
            )
        )
        return components


    async def start(self, ctx: InuContext, **kwargs) -> hikari.Message | None:
        """
        entry point for paginator

        Args:
        ----
        ctx : lightbulb.Context
            The context to use to send the initial message
        """
        self.ctx = ctx
        self._position = 0
        continue_ = await self.parse_tag_and_create_embeds()
        if not continue_:
            return None
        super().__init__(page_s=self._embeds, timeout=14*60, disable_paginator_when_one_site=False)
        return await super().start(ctx)


    @listener(hikari.InteractionCreateEvent)
    async def on_interaction(self, event: hikari.InteractionCreateEvent):
        if not self.interaction_pred(event):
            return
        prefix = "vocabulary_"
        if not event.interaction.custom_id.startswith(prefix):
            return
        task = event.interaction.custom_id.replace(prefix, "")
        if task == "start_training":
            ctx = get_context(event)
            pag = TrainingPaginator(page_s=[""])
            await pag.start(ctx, self.tag)




class TrainingPaginator(Paginator):
    vocables: List[Vocable] = []
    _current_vocable: Vocable | None = None

    @property
    def current_vocable(self) -> Vocable:
        if not self._current_vocable:
            raise RuntimeError("Vocable is None")
        return self._current_vocable
    
    @current_vocable.setter
    def current_vocable(self, vocable: Vocable) -> None:
        self._current_vocable = vocable

    async def start(self, ctx: InuContext, tag: Tag):
        self.set_context(ctx)
        self._position = 0
        _, vocab = convert_vocabulary(tag)
        self.vocables = [Vocable(k, v) for k, v in vocab.items()]
        await self._load_details()
        if not self._pages:
            return

        return await super().start(ctx)


    async def _load_details(self) -> None:
        vocable = self._get_vocable()
        self.current_vocable = vocable
        embed = Embed(title=vocable.key)
        embed.description = f"||{vocable.value}||"
        embed.color = Colors.random_blue()
        self._pages[0] = embed
    
    def _get_vocable(self) -> Vocable:
        return random.choices(self.vocables, [v.weight for v in self.vocables])[0]

    @listener(hikari.InteractionCreateEvent)
    async def on_interaction(self, event: hikari.InteractionCreateEvent):
        if not self.interaction_pred(event):
            return
        prefix = "vocabulary_training_"
        if not event.interaction.custom_id.startswith(prefix):
            return
        task = event.interaction.custom_id.replace(prefix, "")
        try:
            if task == "stop":
                self.set_context(event=event)
                await self.delete_presence()
                self.vocables.sort(key=lambda v: v._get_success_rate_of_last_x_tries(x=len(v.tries)))
                results = "\n".join(v.result_str for v in self.vocables)
                await self.ctx.respond(results, ephemeral=True)
                return
            if task == "yes":
                self.set_context(event=event)
                self.current_vocable.add_try(True)
            if task == "no":
                self.set_context(event=event)
                self.current_vocable.add_try(False)
        except BotResponseError as e:
            self.ctx.respond(**e.context_kwargs)
        await self._update_position()



    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self._load_details()
        await super()._update_position(interaction)


    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        training_row = (
            MessageActionRowBuilder()
            .add_interactive_button(
                ButtonStyle.SUCCESS, 
                "vocabulary_training_yes",
                label="✔"
            )
            .add_interactive_button(
                ButtonStyle.DANGER, 
                "vocabulary_training_no",
                label="✖"
            )
        )
        additional_row = (
            MessageActionRowBuilder()
            .add_interactive_button(
                ButtonStyle.SUCCESS, 
                "vocabulary_training_stop",
                label="stop"
            )
        )
        components = [training_row, additional_row]
        return components
    



def convert_vocabulary(tag: Tag) -> Tuple[Optional[Tuple[str, str]], Dict[str, str]]:
    """
    Returns:
    --------
    `Optional[Tuple[str, str]]:`
        the 2 languages used
    `Dict[str, str]:`
        the vocabulary with key in language 1 and value in language 2

    Raises:
    -------
    `core.BotResponseError:`
        A specific Error for the user
    """
    return DefaultParser().parse("\n".join(tag.value))


class DefaultParser:
    _language_separator_order = ["->", "|"]
    _separator_order = [";", "  ", "    ", ",", " "]


    def parse(self, value: str) -> Tuple[Optional[Tuple[str, str]], Dict[str, str]]:
        """
        Returns:
        --------
        `Optional[Tuple[str, str]]:`
            the 2 languages used
        Dict[str, str]:
            the vocabulary with key in language 1 and value in language 2

        Raises:
        -------
        core.BotResponseError:
            A specific Error for the user
        other:
            needs to be converted to BotResponseError
        """
        languages: Optional[Tuple[str, str]] = None
        vocabulary: Dict[str, str] = {}

        lines = value.splitlines()
        first_line = lines[0]
        try:
            lang_dict = self.separate(self._language_separator_order, [first_line])
            languages = tuple([list(lang_dict.keys())[0], list(lang_dict.values())[0]])
            lines.pop(0)
        except ValueError:
            pass

        # manual error handling and creating of info messages contained in BotResponseError
        vocabulary = self.separate(self._separator_order, lines)
        return languages, vocabulary
        
    

    def separate(self, separator_order: List[str], text: List[str]) -> Dict[str, str]:
        """
        Raises:
        -------
        ValueError:
            when a line has more then 2 items
        """
        dictionary: Dict[str, str] = {}
        for line in text:
            separator = " "
            for s in separator_order:
                if s in line:
                    separator = s
                    break
            values = line.split(separator)
            if len(values) != 2:
                raise BotResponseError(
                    f"```\n{line}```\nI tried to split this line with >`{separator}`<. What I was able to split it into the following"
                    f""" {len(values)} parts: {Human.list_(values, wrap_word_with="'", with_a_or_an=False)}. What I expected were exactly 2 parts. """
                    "If you can't split this line with space, you can also use either `,` or `;` to split this line.",
                    ephemeral=True
                    )
            key, value = values
            dictionary[key] = value
        return dictionary


"""
    Define the list of vocables, along with the number of total tries and failed tries for each vocable.

    Calculate the success rate for each vocable by dividing the number of successful attempts by the total attempts. 
    This will give you a score between 0 and 1, with higher scores indicating more familiar vocables.

    Generate a random number between 0 and 1.

    Iterate over the vocables in the list, starting with the first one. For each vocable, 
    calculate the probability of selecting it based on its success rate and the random number generated in step 3. 
    The probability of selecting a vocable with a success rate of s is given by (1-s)^n, where n is a constant 
    that determines the strength of the bias towards unfamiliar vocables.

    Select a vocable at random, weighted by the probabilities calculated in step 4.

    Present the selected vocable to the user.

    import random

vocables = [("apple", 10, 2), ("banana", 5, 1), ("carrot", 3, 3), ("dog", 15, 5), ("elephant", 20, 10)]
n = 2  # constant to determine the strength of the bias

# calculate the success rate for each vocable
success_rates = []
for vocable in vocables:
    total_attempts = vocable[1]
    successful_attempts = total_attempts - vocable[2]
    success_rates.append(successful_attempts / total_attempts)

# calculate the selection probabilities for each vocable
selection_probs = []
for success_rate in success_rates:
    prob = (1 - success_rate)**n
    selection_probs.append(prob)

# select a vocable at random, weighted by the selection probabilities
selected_vocable = random.choices(vocables, weights=selection_probs)[0]

print("Selected vocable: " + selected_vocable[0])

"""
