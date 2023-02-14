from ast import alias
import traceback
import typing
from typing import *
import asyncio
import logging
import re
import json

import hikari
from hikari import ComponentInteraction, InteractionCreateEvent, NotFoundError, events, ResponseType, Embed
from hikari import ButtonStyle, MessageFlag
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import MemberConverter, GuildConverter, UserConverter
from lightbulb.context import Context

from utils import TagIsTakenError
from .base import (
    Paginator,
    EventListener,
    EventObserver,
    listener,
    StatelessPaginator
)
import asyncpg

from utils import crumble, TagManager
from utils.language import Human
from utils.db import Tag

from core import Inu, BotResponseError, InteractionContext

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)


class TagHandler(StatelessPaginator):
    """An interactive handler for new tags"""
    def __init__(
        self,
        timeout: int = 15*60,
        component_factory: Callable[[int], MessageActionRowBuilder] = None,
        components_factory: Callable[[int], List[MessageActionRowBuilder]] = None,
        disable_pagination: bool = False,
        disable_component: bool = True,
        disable_components: bool = False,
        disable_paginator_when_one_site: bool = False,
        edit_mode: bool = True,

    ):

        self.tag: Tag
        self._pages: List[Embed] = []
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.WARNING)
        self.bot: Inu
        self._edit_mode = edit_mode
        self._tag_link_task: asyncio.Task | None = None

        super().__init__(
            page_s=self._pages,
            timeout=timeout,
            component_factory=component_factory,
            components_factory=components_factory,
            disable_pagination=disable_pagination,
            disable_component=disable_component,
            disable_components=disable_components,
            disable_paginator_when_one_site=False,
        ) 
    
    def set_tag(self, tag: Tag) -> None:
        self.tag = tag

    async def start(self, ctx: Context, tag: Mapping = None):
        """
        Starts the paginator and initializes the tag
        Args:
            ctx: (lightbulb.Context) the Context
            tag: (dict, default=None) the tag which should be
                initialized. Creates new tag, if tag is None
        """
        try:
            self.set_context(ctx)
            if tag:
                tag = await Tag.from_record(tag, db_checks=False)
            if not tag:
                await self.prepare_new_tag(ctx.member or ctx.author)
            else:
                await self.load_tag(tag, ctx.member or ctx.author)
            self._additional_components = self.tag.components or []
            await super().start(ctx=ctx)
        except Exception:
            self.log.error(traceback.format_exc())

    async def _rebuild(self, event: hikari.events):
        await self._rebuild_pages()
        self.set_context(event=event)

    async def post_start(self, **kwargs):
        # self._tag_link_task = asyncio.create_task(self._wait_for_link_button(self.tag))
        await super().post_start(**kwargs)

    async def _rebuild_pages(self, update_value: bool = True):
        """
        updates and sends the pages
        - `self._pages` with the crumbled tag value (`self.tag` is needed)
        - adds info field to the current position page
        - sets `self._additional_components` to the tag components (link buttons)


        Args:
        -----
        update_value : bool
            wether or not to update and crumble the value
        """
        if update_value:
            pages: List[Embed] = []
            # crumble only the current page to spare recauses
            for value in self.tag.value:
                for index, page in enumerate(crumble(value, 2000)):
                    pages.append(
                        Embed(
                            title="",
                            description=page
                        )
                    )
                # skip current page and replace it
            self._pages = pages # [*self._pages[:self._position], *pages, *self._pages[self._position+1:]]
            self._pages[self._position].add_field(
                name="Info",
                value=str(self.tag or "what's the value? Thats actually a good question")
            )
        # updating embed titles
        for page in self._pages:
            page.title = self.tag.name or "Unnamed"
        

        # these can always change
        self._additional_components = self.tag.components

    async def update_page(self, interaction: ComponentInteraction, update_value: bool = False):
        """
        updates and sends the pages
        - `self._pages` with the crumbled tag value (`self.tag` is needed)
        - adds info field to the current position page
        - sets `self._additional_components` to the tag components (link buttons)
        --> sends the new pag with `self.send()`

        
        """
        await self._rebuild_pages(update_value=update_value)
        await self.tag.update()
        await self._update_position()


    @listener(events.InteractionCreateEvent)
    async def on_interaction(self, event: events.InteractionCreateEvent):
        """
        The starting point of all interactions. 
        The interaction custom_id will be checked,
        and the right method will be called, to handle the event
        Args:
        -----
            - event: (InteractionCreateEvent) the invoked event; passed from the listener
        """
        try:
            if not isinstance(event.interaction, ComponentInteraction):
                return
            if (not event.interaction.message.id == self._message.id 
                or not event.interaction.user.id == self.ctx.author.id):
                return
            i = event.interaction
            try:
                if not self.custom_id.custom_id == "tag_options":
                    return
                custom_id = event.interaction.values[0]
            except (IndexError, AssertionError):
                # interaction was no menu interaction
                return
            self.set_context(event=event)
            if custom_id == "set_name":
                await self.set_name(event.interaction)
            elif custom_id == "set_value":
                await self.set_value(event.interaction)
            elif custom_id == "extend_value":
                await self.extend_value(event.interaction)
            elif custom_id == "change_visibility":
                await self.change_visibility(event.interaction)
            elif custom_id == "change_owner":
                await self.change_owner(event.interaction)
            elif custom_id == "finish":
                await self.finish(event.interaction)
            elif custom_id == "remove_tag":
                await self.delete(event.interaction)
            elif custom_id == "add_author_id":
                await self.change_creators(i, set.add)
            elif custom_id == "add_alias":
                await self.change_aliases(i, set.add)
            elif custom_id == "add_guild_id":
                await self.change_guild_ids(i, set.add)
            elif custom_id == "remove_author_id":
                await self.change_creators(i, set.remove)
            elif custom_id == "remove_alias":
                await self.change_aliases(i, set.remove)
            elif custom_id == "remove_guild_id":
                await self.change_guild_ids(i, set.remove)
            elif custom_id == "add_new_page":
                if len(self._pages) >= 20:
                    return await self.ctx.respond(
                        f"A tag can't have more then 20 pages",
                        ephemeral=True,
                    )
                self._pages.insert(self._position+1, Embed(title=self.tag.name))
                default_page = """
This is a new page. 

**To remove it:**
```
- edit the tag
- go to this page (with arrow buttons)
- select "remove this page" in the menu
```

**To edit it:**
```
- edit the tag
- go to this page (with arrow buttons)
- select "set value" in the menu
```
                """
                self.tag.value.insert(self._position+1, default_page)
                self._position += 1
            elif custom_id == "remove_this_page":
                if len(self._pages) <= 1:
                    return await self.ctx.respond(
                        f"A tag can't have less then 1 page"
                    )
                self._pages.remove(self._pages[self._position])
                self.tag.value.remove(self.tag.value[self._position])
                self._position -= 1
            else:
                if custom_id in self.tag.tag_links:
                    # reaction to this in in self._tag_link_task
                    return
                log.warning(f"Unknown custom_id: {custom_id} - in {self.__class__.__name__}")
            if self.tag.name and self.tag.value:
                try:
                    await self.tag.save()
                except Exception:
                    pass
            await self.update_page(update_value=custom_id in ["set_value", "extend_value", "add_new_page"], interaction=i)
            
        except Exception:
            self.log.error(traceback.format_exc())

    async def change_creators(self, interaction: ComponentInteraction, op: Union[set.add, set.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """
        user_str, self.interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "What is the person you want to add?",
            interaction=interaction,
            placeholder="something like @user, user#0000 or the ID of the user"
        )
        self.set_context(event=event)
        try:
            user = await UserConverter(self.ctx).convert(user_str)
        except TypeError:
            return await self.create_message(f"No person like `{user_str}` found.")
        try:
            op(self.tag.owners, user.id)
        except ValueError:
            await self.create_message("ID's are supposed to be numbers")
            return
        except KeyError:
            await self.create_message("This user never actually had the rights")
            return
        
        #await self.bot.rest.create_message(interaction.channel_id, f"`{user_id}` added to authors of this tag")

    async def change_guild_ids(self, interaction: ComponentInteraction, op: Union[set.add, set.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """

        guild_id, self.interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "Enter the guild ID you want to add",
            placeholder_s="something like 1234567890123456789",
            interaction=interaction,
        )
        self.set_context(event=event)
        try:
            op(self.tag.guild_ids, int(guild_id))
        except ValueError:
            await self.create_message("ID's are supposed to be numbers")
            return
        except KeyError:
            await self.create_message("In this guild your tag was never actually available")
            return

    async def change_aliases(self, interaction: ComponentInteraction, op: Union[set.add, set.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """
        # I know this function is redundant, but otherwise it would affect the readability
        alias, self.interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "What should be the name of the new alias?",
            interaction=interaction,
        )
        self.set_context(event=event)
        try:
            op(self.tag.aliases, alias)
        except KeyError:
            await self.create_message("Your tag has no such alias")
            return
        except ValueError:
            await self.create_message("Alias's are supposed to be strings")
            return
        
        


    async def delete(self, interaction: ComponentInteraction):
        await self.tag.delete()
        await self.create_message(
            f"I removed {'local' if self.tag.is_local else 'global'} tag `{self.tag.name}`"
        )
        self.tag.name = None
        self.tag.value = None
        self.tag.is_local_available = False
        self.tag.is_global_available = False
        await self.tag.update()

    async def set_name(self, interaction: ComponentInteraction):
        new_name, self.interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Rename Tag",
            "New name:",
            min_length_s=1,
            max_length_s=256,
            interaction=interaction,
        )
        self.set_context(event=event)
        try:
            self.tag.name = new_name
        except RuntimeError as e:
            #ctx = InteractionContext(event=event, app=self.bot)
            await self.ctx.respond(e.args[0], ephemeral=True)


    async def set_value(self, interaction: ComponentInteraction, append: bool = False):
        if append:
            value, self.interaction, event = await self.bot.shortcuts.ask_with_modal(
                modal_title=self.tag.name or "Tag",
                question_s="Add to value:" if append else "Value:",
                interaction=interaction,
            )
        else:
            value, self.interaction, event = await self.bot.shortcuts.ask_with_modal(
                modal_title=self.tag.name or "Tag",
                question_s="Edit value:",
                interaction=interaction,
                pre_value_s=self.tag.value[self._position] or "",
            )
        self.set_context(event=event)
        if not value:
            return
        values = crumble(value, 2000)
        if append and self.tag.value:
            self.tag.value = [*self.tag.value[:self._position], *crumble(self.tag.value[self._position]+values[0], 2000), *values[1:], *self.tag.value[self._position+1:]]
        else:
            self.tag.value = [*self.tag.value[:self._position], *crumble(values[0], 2000), *values[1:], *self.tag.value[self._position+1:]]

    async def extend_value(self, interaction: ComponentInteraction):
        await self.set_value(interaction, append=True)

    async def change_visibility(self, interaction: ComponentInteraction):
        if self.tag._is_local:
            self.tag._is_local = False
            self.tag.guild_ids.append(0)
        else:
            self.tag._is_local = True
            self.tag.guild_ids.remove(0)
        # await self.update_page()

    async def finish(self, interaction: ComponentInteraction):
        try:
            await self.tag.save()
            await self.update_page()
        except TagIsTakenError:
            await self.create_message(
                f"Your tag name {self.tag.name}` is {'locally' if self.tag._is_local else 'globally'} already taken"
            )
        except Exception:
            tb = traceback.format_exc()
            pages: List[Embed] = []
            for page in crumble(tb):
                embed = Embed()
                embed.title = "Saving the tag failed"
                embed.description = page
                pages.append(embed)
            paginator = Paginator(pages)
            await paginator.start(self.ctx)
            return

        await self.create_message(
            f"Your tag `{self.tag.name}` was successfully added to my storage :)"
        )

    async def change_owner(self, interaction: ComponentInteraction):
        embed = (
            Embed(title="Enter the ID of the new owner or ping him/her/it or enter the complete name with #XXXX")
            .set_footer(text=f"timeout after {self.timeout}s")
        )
        await self.create_message(
            embed=embed
        )
        bot_message = await self.ctx.interaction.fetch_initial_response()
        try:
            event = await self.bot.wait_for(
                events.MessageCreateEvent,
                self.timeout,
                lambda m: m.author_id == interaction.user.id and m.channel_id == interaction.channel_id
            )
            self.set_context(event)
        except asyncio.TimeoutError:
            await interaction.delete_initial_response()
            return

        if event.message.content is None:
            return

        try:
            pass # old user search
        except NotFoundError:
            user = None

        if not user:
            return await self.ctx.respond(
                "I can't find anyone",
                reply=event.message,
            )
        if user and (channel := self.ctx.get_channel()):
            await channel.delete_messages(bot_message, event.message)
        self.tag.owner = user
        # await self.update_page()

    def build_default_components(self, position) -> List[MessageActionRowBuilder]:
        rows = []
        navi = super().build_default_component(position)
        rows.append(navi)
        menu = (
                MessageActionRowBuilder()
                .add_select_menu(self._serialize_custom_id("tag_options"))
                .add_option("set name", "set_name").add_to_menu()
                .add_option("set value", "set_value").add_to_menu()
                .add_option("append to value", "extend_value").add_to_menu()
                .add_option("add an alias", "add_alias").add_to_menu()
                .add_option("add a guild", "add_guild_id").add_to_menu()
                .add_option("add an author", "add_author_id").add_to_menu()
                .add_option("remove an author", "remove_author_id").add_to_menu()
                .add_option("remove alias", "remove_alias").add_to_menu()
                .add_option("remove guild", "remove_guild_id").add_to_menu()
                .add_option("add new page", "add_new_page").add_to_menu()
                .add_option("remove current page", "remove_this_page").add_to_menu()
                .add_option("local / global", "change_visibility").add_to_menu()
                .add_option("delete tag", "remove_tag").add_to_menu()
                .add_to_container()
            )
        
        rows.append(menu)
        if self._additional_components:
            rows.extend(self._additional_components)
        #if self.pagination:
        return rows
        #return [tag_specific, finish]

    async def load_tag(self, tag: Mapping[str, Any] | Tag, author: Union[hikari.Member, hikari.User]):
        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
            - tag: (Mapping[str, Any]) the tag which should be loaded
            - author: (Member, User) the user which stored the tag
        """

        if isinstance(tag, Dict):
            new_tag = await Tag.from_record(record=tag, author=author)
            self.tag = new_tag
        else:
            self.tag = tag

        # self.embed = Embed()
        # self.embed.title = self.tag.name
        # self.embed.description = self.tag.value[0]
        # self.embed.add_field(name="Status", value=self.tag.__str__())
        # self._pages = [
        #     Embed(
        #         title=self.tag.name,
        #         description=value,
        #     ).add_field("Info", str(self.tag))
        #     for value in self.tag.value
        # ]
        await self._rebuild_pages()
        self._default_site = len(self._pages) - 1


    async def prepare_new_tag(self, author):
        """
        creates a new tag in form of `Tag`
        Args:
        -----
            - author: (Member, User) the user which stored the tag
        """
        tag = Tag(self.ctx.member or self.ctx.author)
        tag.name = None
        tag.value = None
        tag.is_stored = False
        if isinstance(author, hikari.Member):
            tag._is_local = True
        else:
            tag._is_local = False
        tag.is_global_available = False
        tag.is_local_available = False
        self.tag = tag

        await self.load_tag(tag, author)

    def _get_custom_id_kwargs(self) -> Dict[str, int | str]:
        return {"tid": self.tag.id}

    @property
    def custom_id_type(self) -> str:
        return "stl-tag-edit"

    
        

    # async def show_record(
    #     self,
    #     tag: Optional[Tag],
    #     name: Optional[str] = None,
    #     force_show_name: bool = False,
    # ) -> None:
    #     """
    #     Sends the given tag(record) into the channel of <ctx>
        
    #     Args:
    #     ----
    #     record : `asyncpg.Record`
    #         the record/dict, which should contain the keys `tag_value` and `tag_key`
    #     ctx : `Context`
    #         the context, under wich the message will be sent (important for the channel)
    #     key : `str`
    #         The key under which the tag was invoked. If key is an alias, the tag key will be
    #         displayed, otherwise it wont
    #     """

    #     media_regex = r"(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|gif|png|mp4|mp3)"

    #     messages = []
    #     for page in tag.value:
    #         for value in crumble(page, 1900):
    #             message = ""
    #             # if tag isn't just a picture and tag was not invoked with original name,
    #             # then append original name at start of message
    #             if (
    #                 not (
    #                     name == tag.name
    #                     or re.match(media_regex, tag.value[self._position].strip())
    #                 )
    #                 or force_show_name
    #             ):
    #                 message += f"**{tag.name}**\n\n"
    #             message += value
    #             messages.append(message)
    #     pag = Paginator(
    #         page_s=messages,
    #         compact=True,
    #         additional_components=tag.components,
    #         disable_component=True,
    #     )
    #     asyncio.create_task(pag.start(self.ctx))
    #     # if tag.tag_links:
    #     #     asyncio.create_task(self._wait_for_link_button(tag))






