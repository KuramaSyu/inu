from ast import alias
import traceback
import typing
from typing import (
    Union,
    Optional,
    List,
    Callable,
    Mapping,
    Any
)
import asyncio
import logging

import hikari
from hikari import ComponentInteraction, InteractionCreateEvent, NotFoundError, events, ResponseType, Embed
from hikari.messages import ButtonStyle
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb import MemberConverter, GuildConverter, UserConverter
from lightbulb.context import Context

from utils import TagIsTakenError
from .base import (
    Paginator,
    EventListener,
    EventObserver,
    listener,
)
import asyncpg

from utils import crumble, TagManager
from utils.language import Human
from utils.db import Tag

from core import Inu

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)




class TagHandler(Paginator):
    """An interactive handler for new tags"""
    def __init__(
        self,
        timeout: int = 15*60,
        component_factory: Callable[[int], ActionRowBuilder] = None,
        components_factory: Callable[[int], List[ActionRowBuilder]] = None,
        disable_pagination: bool = False,
        disable_component: bool = True,
        disable_components: bool = False,
        disable_paginator_when_one_site: bool = False,

    ):

        self.tag: Tag
        self._pages: List[Embed] = []
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.bot: Inu

        super().__init__(
            page_s=self._pages,
            timeout=timeout,
            component_factory=component_factory,
            components_factory=components_factory,
            disable_pagination=disable_pagination,
            disable_component=disable_component,
            disable_components=disable_components,
            disable_paginator_when_one_site=disable_paginator_when_one_site,
        )

    async def start(self, ctx: Context, tag: Mapping = None):
        """
        Starts the paginator and initializes the tag
        Args:
            ctx: (lightbulb.Context) the Context
            tag: (dict, default=None) the tag which should be
                initialized. Creates new tag, if tag is None
        """
        try:
            self.ctx = ctx
            self.bot = ctx.bot
            if not tag:
                await self.prepare_new_tag(ctx.member or ctx.author)
            else:
                await self.load_tag(tag, ctx.member or ctx.author)
                
            await super().start(ctx)
        except Exception:
            self.log.error(traceback.format_exc())

    async def update_page(self, update_value: bool = False):
        """Updates the embed, if the interaction wasn't for pagination"""
        if update_value:
            pages = []
            for index, page in enumerate(crumble(str(self.tag.value), 2000)):
                pages.append(Embed(
                    title="",
                    description=page
                ))
            self._pages = pages
            self._pages[0].add_field(name="Info", value="not set")
        # updating embed titles
        for page in self._pages:
            page.title = self.tag.name or "Name - not set"
        await self.tag.update()

        self._pages[0].edit_field(0, "Info", str(self.tag))
        await self._message.edit(
            embed=self._pages[0],
            components=self.components
        )


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
                custom_id = event.interaction.values[0]
            except IndexError:
                # interaction was no menu interaction
                return

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
            else:
                log.warning(f"Unknown custom_id: {custom_id} - in {self.__class__.__name__}")
            if self.tag.name and self.tag.value:
                try:
                    await self.tag.save()
                except Exception:
                    pass
            await self.update_page(update_value=custom_id in ["set_value", "extend_value"])
            
        except Exception:
            self.log.error(traceback.format_exc())

    async def change_creators(self, interaction: ComponentInteraction, op: Union[set.add, set.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """
        user_str, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "What is the person you want to add?",
            interaction=interaction,
            placeholder="something like @user, user#0000 or the ID of the user"
        )
        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        try:
            user = await UserConverter(self.ctx).convert(user_str)
        except TypeError:
            return await self.ctx.respond(f"No person like `{user_str}` found.")
        try:
            op(self.tag.owners, user.id)
        except ValueError:
            await self.bot.rest.create_message(interaction.channel_id, "ID's are supposed to be numbers")
            return
        except KeyError:
            await self.bot.rest.create_message(interaction.channel_id, "This user never actually had the rights")
            return
        
        #await self.bot.rest.create_message(interaction.channel_id, f"`{user_id}` added to authors of this tag")

    async def change_guild_ids(self, interaction: ComponentInteraction, op: Union[set.add, set.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """

        log.debug("ask")
        guild_id, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "Enter the guild ID you want to add",
            placeholder_s="something like 1234567890123456789",
            interaction=interaction,
        )

        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        try:
            op(self.tag.guild_ids, int(guild_id))
        except ValueError:
            await self.bot.rest.create_message(interaction.channel_id, "ID's are supposed to be numbers")
            return
        except KeyError:
            await self.bot.rest.create_message(interaction.channel_id, "In this guild your tag was never actually available")
            return
        #await interaction.create_initial_response(f"You can use this tag now in `{guild_id}`")

    async def change_aliases(self, interaction: ComponentInteraction, op: Union[set.add, set.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """
        # I know this function is redundant, but otherwise it would affect the readability
        alias, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "What should be the name of the new alias?",
            interaction=interaction,
        )
        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        try:
            op(self.tag.aliases, alias)
        except KeyError:
            await self.bot.rest.create_message(interaction.channel_id, "Your tag has no such alias")
            return
        except ValueError:
            await self.bot.rest.create_message(interaction.channel_id, "Alias's are supposed to be strings")
            return
        #await interaction.create_initial_response(f"`{alias}` is now an alternative name of this tag")
        
        


    async def delete(self, interaction: ComponentInteraction):
        await self.tag.delete()
        await interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE,
            f"I removed {'local' if self.tag.is_local else 'global'} tag `{self.tag.name}`"
        )
        self.tag.name = None
        self.tag.value = None
        self.tag.is_local_available = False
        self.tag.is_global_available = False
        await self.tag.update()

    async def set_name(self, interaction: ComponentInteraction):
        new_name, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Rename Tag",
            "New name:",
            min_length_s=1,
            max_length_s=256,
            interaction=interaction,
        )
        self.tag.name = new_name
        await interaction.create_initial_response(
            ResponseType.DEFERRED_MESSAGE_UPDATE
        )


    async def set_value(self, interaction: ComponentInteraction, append: bool = False):
        if append:
            value, interaction, event = await self.bot.shortcuts.ask_with_modal(
                modal_title=self.tag.name or "Tag",
                question_s="Add to value:" if append else "Value:",
                interaction=interaction,
            )
        else:
            value, interaction, event = await self.bot.shortcuts.ask_with_modal(
                modal_title=self.tag.name or "Tag",
                question_s="Edit value:",
                interaction=interaction,
                pre_value_s=self.tag.value[:4000] or "",
            )
        if not value:
            return
        await interaction.create_initial_response(
            ResponseType.DEFERRED_MESSAGE_UPDATE
        )
        if append and self.tag.value:
            self.tag.value += value
        else:
            self.tag.value = value

    async def extend_value(self, interaction: ComponentInteraction):
        await self.set_value(interaction, append=True)

    async def change_visibility(self, interaction: ComponentInteraction):
        if self.tag._is_local:
            self.tag._is_local = False
            self.tag.guild_ids.append(0)
        else:
            self.tag._is_local = True
            self.tag.guild_ids.remove(0)
        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        # await self.update_page()

    async def finish(self, interaction: ComponentInteraction):
        try:
            await self.tag.save()
            await self.update_page()
        except TagIsTakenError:
            await interaction.create_initial_response(
                ResponseType.MESSAGE_CREATE,
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
            await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_CREATE)
            paginator = Paginator(pages)
            await paginator.start(self.ctx)
            return

        await interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE,
            f"Your tag `{self.tag.name}` was successfully added to my storage :)"
        )

    async def change_owner(self, interaction: ComponentInteraction):
        embed = (
            Embed(title="Enter the ID of the new owner or ping him/her/it or enter the complete name with #XXXX")
            .set_footer(text=f"timeout after {self.timeout}s")
        )
        await interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE,
            embed=embed
        )
        bot_message = await interaction.fetch_initial_response()
        try:
            event = await self.bot.wait_for(
                events.MessageCreateEvent,
                self.timeout,
                lambda m: m.author_id == interaction.user.id and m.channel_id == interaction.channel_id
            )
        except asyncio.TimeoutError:
            await interaction.delete_initial_response()
            return

        if event.message.content is None:
            return

        try:
            user = await user_converter(WrappedArg(event.message.content, self.ctx))
        except NotFoundError:
            user = None

        if not user:
            return await event.message.respond(
                "I can't find anyone",
                reply=event.message,
            )
        if user and (channel := self.ctx.get_channel()):
            await channel.delete_messages(bot_message, event.message)
        self.tag.owner = user
        # await self.update_page()

    def build_default_components(self, position) -> List[ActionRowBuilder]:
        navi = super().build_default_component(position)
        disable_remove_when = lambda self: self.tag.name is None or self.tag.value is None
        disable_save_when = lambda self: self.tag.name is None or self.tag.value is None
        intelligent_button_style = lambda value: ButtonStyle.PRIMARY if not (value) else ButtonStyle.SECONDARY
        tag_specific = (
            ActionRowBuilder()
            .add_button(intelligent_button_style(self.tag.name), "set_name")
            .set_label("set name")
            .add_to_container()
            .add_button(intelligent_button_style(self.tag.value), "set_value")
            .set_label("set value")
            .add_to_container()
            .add_button(ButtonStyle.SECONDARY, "extend_value")
            .set_label("append to value")
            .add_to_container()
            .add_button(ButtonStyle.SECONDARY, "change_visibility")
            .set_label("local/global")
            .add_to_container()
        )
        add_options = (
            ActionRowBuilder()
            .add_button(ButtonStyle.SECONDARY, "add_alias")
            .set_label("add an alias").add_to_container()
            # .add_button(ButtonStyle.DANGER, "change_owner")
            # .set_label("change tag owner")
            .add_button(ButtonStyle.SECONDARY, "add_guild_id")
            .set_is_disabled(not self.tag.is_local)
            .set_label("add a guild").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "add_author_id")
            .set_label("add an author").add_to_container()
        )
        danger_tags = (
            ActionRowBuilder()
            .add_button(ButtonStyle.DANGER, "remove_tag")
            .set_label("delete tag")
            .set_is_disabled(not self.tag.is_stored).add_to_container()
            # .add_button(ButtonStyle.DANGER, "change_owner")
            # .set_label("change tag owner")
            .add_button(ButtonStyle.DANGER, "remove_author_id")
            .set_label("remove author").add_to_container()
            .add_button(ButtonStyle.DANGER, "remove_alias")
            .set_label("remove alias").add_to_container()
            .add_button(ButtonStyle.DANGER, "remove_guild_id")
            .set_label("remove server")
            .set_is_disabled(not self.tag.is_local).add_to_container()
        )
        finish = (
            ActionRowBuilder()
            .add_button(intelligent_button_style(self.tag.is_stored), "finish")
            .set_label("save")
            .set_is_disabled(disable_save_when(self))
            .add_to_container()
        )
        menu = (
            ActionRowBuilder()
            .add_select_menu("tag_options")
            .add_option("set name", "set_name").add_to_menu()
            .add_option("set value", "set_value").add_to_menu()
            .add_option("append to value", "extend_value").add_to_menu()
            .add_option("add an alias", "add_alias").add_to_menu()
            .add_option("add a guild", "add_guild_id").add_to_menu()
            .add_option("add an author", "add_author_id").add_to_menu()
            .add_option("remove an author", "remove_author_id").add_to_menu()
            .add_option("remove alias", "remove_alias").add_to_menu()
            .add_option("remove guild", "remove_guild_id").add_to_menu()
            .add_option("local / global", "change_visibility").add_to_menu()
            .add_option("delete tag", "remove_tag").add_to_menu()
            .add_to_container()
        )
        #if self.pagination:
        return [navi, menu] #type: ignore
        #return [tag_specific, finish]

    async def load_tag(self, tag: Mapping[str, Any], author: Union[hikari.Member, hikari.User]):
        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
            - tag: (Mapping[str, Any]) the tag which should be loaded
            - author: (Member, User) the user which stored the tag
        """
        # guild_id = author.guild_id if isinstance(author, hikari.Member) else 0
        # local_taken, global_taken = await TagManager.is_taken(key=tag["tag_key"], guild_id = guild_id or 0)
        # new_tag: Tag = Tag(author)
        # new_tag.name = tag["tag_key"]
        # new_tag.value = tag["tag_value"]
        # new_tag.is_stored = True
        # new_tag.id = tag["tag_id"]
        # new_tag.guild_ids = tag["guild_ids"]
        # new_tag.aliases = tag["aliases"]
        # new_tag.owners = tag["author_ids"]
        # if (
        #     isinstance(author, hikari.Member)
        #     and not 0 in tag["guild_ids"]
        #     and author.guild_id in tag["guild_ids"]
        # ):
        #     new_tag._is_local = True
        # else:
        #     new_tag._is_local = False
        # new_tag.is_global_available = not global_taken
        # new_tag.is_local_available = not local_taken
        new_tag = await Tag.from_record(record=tag, author=author)
        self.tag = new_tag

        self.embed = Embed()
        self.embed.title = self.tag.name
        self.embed.description = self.tag.value
        self.embed.add_field(name="Status", value=self.tag.__str__())
        self._pages = [self.embed]
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

        self.embed = Embed()
        self.embed.title = self.tag.name or "Name - not set"
        self.embed.description = self.tag.value or "Value - not set"
        self.embed.add_field(name="Status", value=self.tag.__str__())
        self._pages = [self.embed]







