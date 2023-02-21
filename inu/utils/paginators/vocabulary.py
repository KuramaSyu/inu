import asyncio
from typing import *

import hikari
from hikari import ButtonStyle, ComponentInteraction, Embed, ResponseType
from hikari.impl import MessageActionRowBuilder

from .base import PaginatorReadyEvent, Paginator, listener

from core import getLogger, InuContext, ConfigProxy, ConfigType, BotResponseError, get_context
from utils import Human, Colors, MyAnimeList, Anime, Tag, crumble

log = getLogger(__name__)



config = ConfigProxy(ConfigType.YAML)
VOCAB_BIAS: int = 2  # a bias for chosing a vocable. the higher the value, the highter the prop of a unknown vocable chosen

class VocabularyPaginator(Paginator):
    def __init__(
        self,
        tag: Tag,
    ):
        self._rates:Dict[str, float] = {}
        self._languages: Optional[Tuple[str, str]] = None
        self._vocabulary: Dict[str, str] = {}
        self._languages, self._vocabulary = convert_vocabulary(tag)
        self._embeds = []
        self.tag = tag
        bare_text = ""
        if self._languages:
            bare_text += f"**{self._languages[0]}** ---> {self._languages[1]}\n\n"
        for key, value in self._vocabulary.items():
            bare_text += f"**{key}** : {value}\n"
        for part in crumble(bare_text):
            self._embeds.append(Embed(title=tag.key, description=part))
        # re-init in start - just leave it
        super().__init__(
            page_s=self._embeds, 
            timeout=60*15,
            disable_paginator_when_one_site=False,
        )


    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        components = super().build_default_components(position)
        (
            components[-1] 
            .add_button(ButtonStyle.SUCCESS, "vocabulary_start_training").set_label("learn ⤵️").add_to_container()
        )
        return components


    async def start(self, ctx: InuContext, **kwargs) -> hikari.Message:
        """
        entry point for paginator

        Args:
        ----
        ctx : lightbulb.Context
            The context to use to send the initial message
        """
        self.ctx = ctx
        self._position = 0
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
            pag = VocabularyPaginator(self.tag)
            await pag.start(ctx)




class TrainingPaginator(Paginator):
    _results: List[Dict[str, Any]]  # bare season info
    _tv_show_id: int
    _rates: List[Dict[str, List[bool] | str]] = []

    async def start(self, ctx: InuContext, tag: Tag):
        self.ctx = ctx
        self._position = 0
        lang, vocab = convert_vocabulary(tag)
        self._rates = [{"key": k, "value": v, "tries": []} for k, v in vocab.items()]
        await self._load_details()
        if not self._pages:
            return

        return await super().start(ctx)


    async def _load_details(self) -> None:
        """
        
        """
        ...

    def _get_rate(self, last_x: int):
        rates = []
        for voc in self._rates:
            l = voc["tries"]
            k = voc["key"]
            v = voc["value"]
            right_guesses = 0
            for try_ in l:
                if try_:
                    right_guesses += 1
            rates.append(
                {
                "key": k, 
                "success_rate": right_guesses / last_x, 
                "guess_amount": len(l),
                "value": v,
                }
            )
    
    def _get_vocable(self) -> Dict[str, str]:
        rates = self._get_rate(last_x=4)
        for rate in rates:
            if rate["tries"] < 3:
                ...




    async def _update_position(self, interaction: ComponentInteraction | None = None,):
        """
        replaces embed page first with a more detailed one, before sending the message
        """
        await self._load_details()
        await super()._update_position(interaction)


    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        training_row = (
            MessageActionRowBuilder()
            .add_button(ButtonStyle.SUCCESS, "vocabulary_training_yes").set_emoji("✔").add_to_container()
            .add_button(ButtonStyle.DANGER, "vocabulary_training_no").set_emoji("✖").add_to_container()
        )
        additional_row = (
            MessageActionRowBuilder()
            .add_button(ButtonStyle.SUCCESS, "vocabulary_training_stop").set_label("").add_to_container()
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
    return DefaultParser().parse(tag.value)


class DefaultParser:
    _language_separator_order = ["->", "|"]
    _separator_order = [";", ",", " "]


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
            lang_dict = self.separate(self._language_separator_order, first_line)
            languages = Tuple([lang_dict.keys()[0], lang_dict.values()[0]])
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
            key, value = line.split(separator)
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
