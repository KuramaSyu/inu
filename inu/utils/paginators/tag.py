from code import interact
import traceback
from typing import *
import asyncio
import logging
from enum import Enum
import re

import hikari
from hikari import (
    CommandInteraction, ComponentInteraction, ComponentInteractionCreateEvent, InteractionCreateEvent, 
    NotFoundError, PartialIntegration, PartialInteraction, 
    events, ResponseType, Embed, Event
)
from hikari import ButtonStyle, MessageFlag
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb.context import Context

from utils import TagIsTakenError
from .base import (
    JsonDict,
    CustomID,
    Paginator,
    InteractionListener,
    EventObserver,
    listener,
    StatelessPaginator,
)
import asyncpg

from utils import crumble, TagManager, add_row_when_filled, ListParser
from utils.language import Human
from utils.db import Tag, TagType

from core import Inu, BotResponseError, ComponentContext, get_context, InuContext, Interaction
import hashlib

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)


DEFAULT_PAGE = """
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

TAG_TYPES_EXPLANATION = """
**Media**: Media tags will be recommended in `/play` command.
Use it to store the URL of a playlist or song.\n\n
**List**: List tags will be recommended in the `/random list` command.
Use it, to store large lists you don't want to rewrite every time. Like a list
with LoL champions.\n\n
**Normal**: Well - just to store some data. This is the default

__Select the type you want__:
"""

class TagCustomID(CustomID):
    def set_tag_id(self, tag_id: int) -> "TagCustomID":
        self._kwargs["tid"] = tag_id
        return self
    
    def serialize_custom_id(self) -> JsonDict:
        if not self._kwargs.get("tid"):
            raise ValueError("Tag ID is not set")
        return super().serialize_custom_id()
    
    @property
    def type(self) -> str:
        return "stl-tag-edit"
    
class TagTypeComponents:
    @classmethod
    def get(cls, tag_type: Type[TagType]) -> Callable[["TagHandler"], MessageActionRowBuilder]:
        return {
            TagType.LIST: cls.list_components
        }.get(tag_type, lambda _: None)
        
    @staticmethod
    def list_components(tag: "TagHandler") -> MessageActionRowBuilder:
        return (
            MessageActionRowBuilder()
            .add_interactive_button(
                ButtonStyle.SECONDARY, 
                tag._serialize_custom_id("tag_options_sort"),
                label="Sort",
                emoji="⬇️"
            )
            .add_interactive_button(
                ButtonStyle.SECONDARY, 
                tag._serialize_custom_id("tag_options_sort_r"),
                label="Sort Reverse",
                emoji="⬆️"
            )
        )



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
        self.log.setLevel(logging.DEBUG)
        self.bot: Inu
        self._edit_mode = edit_mode
        self._tag_link_task: asyncio.Task | None = None
        self._info_visible = False
        self._submessages: List[int] = []

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
    async def rebuild(self, interaction: PartialInteraction | InteractionCreateEvent, reject_user: bool = False, **kwargs) -> None:
        await super().rebuild(interaction, reject_user=reject_user, **kwargs)

    def _interaction_pred(self, interaction: PartialInteraction) -> Tuple[bool, bool]:
        """Checks user in tag.owners and message id of the event interaction
        
        Returns:
        --------
            - bool: wether or not the user is allowed to use this
            - bool: wether or not the message id is the same as the one of the paginator
        """
        i = interaction
        self.log.debug(f"tag test - testing interaction of type {type(interaction)}")
        if not isinstance(i, ComponentInteraction):
            self.log.debug("False interaction pred")
            return False, False
        return (i.user.id in self.tag.owners, i.message.id == self._message.id)

    def interaction_pred(self, interaction: PartialInteraction) -> bool:
        return all(self._interaction_pred(interaction))

    async def check_user(self) -> bool:
        """
        Returns wether or not the user is allowed to use this
        """
        if not (
            self.custom_id.is_same_user(self.ctx.interaction)
            or self.ctx.interaction.user.id in self.tag.owners
        ):
            await self.ctx.respond(self._get_rejection_message(), ephemeral=True)
            return False
        return True
    
    def set_tag(self, tag: Tag) -> None:
        self.tag = tag

    async def start(self, ctx: InuContext, tag: Mapping = None):
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

    async def _rebuild(self, interaction: PartialInteraction | InteractionCreateEvent, **kwargs):
        await self._rebuild_pages()
        if isinstance(interaction, InteractionCreateEvent):
            interaction = interaction.interaction
        self.set_context(interaction=interaction)

    async def post_start(self, **kwargs):
        await super().post_start(**kwargs)

    async def _rebuild_pages(self, update_value: bool = True):
        """
        updates pages
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
            self._pages = pages
        # remove Info field
        self._pages[self._position]._fields = [
            field for field 
            in self._pages[self._position]._fields or [] 
            if not field.name == "Info"
        ]
        if self.tag.info_visible:
            if self.tag:
                value = f"```{self.tag.to_string(self._position, 'dynamic')}\n{self.tag.to_string(self._position, 'static')}```"
            else:
                value = "what's the value? Thats actually a good question"
            self._pages[self._position].add_field(
                name="Info",
                value=value
            )
            if self.tag.to_do:
                self._pages[self._position].add_field(
                    name="Tag is incomplete:",
                    value=self.tag.to_string(self._position, "to_do")
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
        await self._update_position()


    @listener(ComponentInteractionCreateEvent)
    async def on_interaction(self, event: events.InteractionCreateEvent):
        """
        The starting point of all interactions. 
        The interaction custom_id will be checked,
        and the right method will be called, to handle the event
        Args:
        -----
            - event: (InteractionCreateEvent) the invoked event; passed from the listener
        """
        TAG_MENU_PREFIX = "tag_options"
        try:
            if not self.interaction_pred(event.interaction):
                return 
            
            i = cast(ComponentInteraction, event.interaction)
            try:
                if not self.custom_id.custom_id.startswith(TAG_MENU_PREFIX):
                    return
                if i.values:
                    custom_id = i.values[0]
                else:
                    custom_id = self.custom_id.custom_id.removeprefix(f"{TAG_MENU_PREFIX}_")
            except (IndexError, AssertionError):
                # interaction was no menu interaction
                return
                # set_type has other message, not this one
            self.log.debug(f"Custom ID: {custom_id}")
            self.set_context(interaction=i)
            success = True
            if custom_id == "set_name":
                await self.set_name(i)
            elif custom_id == "set_value":
                success = await self.set_value(i)
            elif custom_id == "extend_value":
                success = await self.extend_value(i)
            elif custom_id == "change_visibility":
                await self.change_visibility(i)
            elif custom_id == "change_owner":
                await self.change_owner(i)
            elif custom_id == "finish":
                await self.finish(i)
            elif custom_id == "remove_tag":
                await self.delete(i)
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
            elif custom_id == "ask_type":
                await self.ask_type(get_context(event=event))
                return
            elif custom_id == "info_visible":
                await self.change_info_visibility()
            elif custom_id.startswith("set_type_"):
                value = int(custom_id.replace("set_type_", ""))
                self.tag.tag_type = TagType.from_value(value)
                log.debug(self.tag.tag_type)
            elif custom_id == "sort":
                await self.sort(reverse=False)
            elif custom_id == "sort_r":
                await self.sort(reverse=True)
            elif custom_id == "add_new_page":
                if len(self._pages) >= 20:
                    return await self.ctx.respond(
                        f"A tag can't have more then 20 pages",
                        ephemeral=True,
                    )
                self._pages.insert(self._position+1, Embed(title=self.tag.name))
                self.tag.value.insert(self._position+1, DEFAULT_PAGE)
                self._position += 1
            elif custom_id == "end_editing":
                return await self.start_view()
            elif custom_id == "remove_this_page":
                if len(self._pages) <= 1:
                    return await self.ctx.respond(
                        f"A tag can't have less then 1 page"
                    )
                self._pages.remove(self._pages[self._position])
                self.tag.value.remove(self.tag.value[self._position])
                self._position -= 1
            elif custom_id == "update":
                self.add_onetime_kwargs(content=None)
                await self.update_page(update_value=True, interaction=i)
                return
            elif custom_id == "resend":
                # stopping this and restarting a new one
                try:   
                    await self.update_page(update_value=True, interaction=i)       
                    if self._proxy:      
                        await self._proxy.delete()
                except Exception:
                    log.warning(traceback.format_exc())
                await self.send(content=self.pages[self._position], update=False)
                return
            elif custom_id == "get_tag_link":
                await self.ctx.respond(f"Here is the link to your tag: ```{self.tag.link}```",)
                return
            else:
                if custom_id in self.tag.tag_links:
                    # reaction to this in in self._tag_link_task
                    return
                log.warning(f"Unknown custom_id: {custom_id} - in {self.__class__.__name__}")

            if not success:
                # interaction failed, most likely timeout
                return
            
            if self.tag.name and self.tag.value: 
                self.log.debug(f"Saving tag: {self.tag}; Custom ID: {custom_id}")
                try:
                    await self.tag.save()
                except Exception:
                    log.error(traceback.format_exc())
            await self.update_page(
                update_value=custom_id in ["set_value", "extend_value", "add_new_page", "info_visible", "sort", "sort_r"], 
                interaction=i
            )
            
        except Exception:
            self.log.error(traceback.format_exc())
            
    async def sort(self, reverse: bool = False):
        value = self.tag.value[self._position]
        strategy = ListParser().parse(value)
        parsed = sorted(strategy.processed_list, reverse=reverse, key=lambda x: x.strip())
        self.tag.value[self._position] = strategy.reassemble(parsed)

    async def change_info_visibility(self):
        self.tag.info_visible = not self.tag.info_visible

    async def ask_type(self, ctx: InuContext):
        menu = (
            MessageActionRowBuilder()
            .add_text_menu(self._serialize_custom_id("tag_options"))
            .add_option("Normal", f"set_type_{TagType.NORMAL.value}")
            .add_option("Media (for /play)", f"set_type_{TagType.MEDIA.value}")
            .add_option("List (for /random list)", f"set_type_{TagType.LIST.value}")
            .parent
        )
        await self.ctx.respond(
            TAG_TYPES_EXPLANATION,
            component=menu,
            embed=None,
            update=True,
        )

    async def start_view(self):
        await self.ctx.defer(update=True)
        paginator = TagViewPaginator(self.tag)
        await paginator.start(self.ctx, force_show_name=True)

    async def change_creators(self, interaction: ComponentInteraction, op: Callable[[set, int], None]):
        """
        Args:
        -----
            - op (`builtins.function`) the function (set.add | set.remove), where the result of the question will be passed in
        """
        raise NotImplementedError("User search not implemented vor lightbulb v3")
        ctx = get_context(interaction)
        user_str, new_ctx = await ctx.ask_with_modal(
            "Edit Tag",
            "What is the person you want to add?",
            placeholder_s="something like @user, user#0000 or the ID of the user"
        )
        self.set_context(new_ctx)
        try:
            pass
            #user = await UserConverter(self.ctx).convert(user_str)
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

    async def change_guild_ids(self, interaction: ComponentInteraction, op: Union[set.add, set.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """
        ctx = get_context(interaction)
        guild_id, new_ctx = await ctx.ask_with_modal(
            "Edit Tag",
            "Enter the guild ID you want to add",
            placeholder_s="something like 1234567890123456789",
        )
        self.set_context(new_ctx)
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
        ctx = get_context(interaction)
        alias, new_ctx = await ctx.ask_with_modal(
            "Edit Tag",
            "What should be the name of the new alias?",
        )
        self.set_context(new_ctx)
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
        ctx = get_context(interaction)
        new_name, new_ctx = await ctx.ask_with_modal(
            "Rename Tag",
            "New name:",
            min_length_s=1,
            max_length_s=256,
        )
        self.set_context(new_ctx)
        try:
            self.tag.name = new_name
        except RuntimeError as e:
            #ctx = InteractionContext(event=event, app=self.bot)
            await self.ctx.respond(e.args[0], ephemeral=True)

    async def set_value(self, interaction: ComponentInteraction, append: bool = False) -> bool:
        """
        Sets the value of the tag based on the given interaction.
        Parameters:
            interaction (ComponentInteraction): The interaction object.
            append (bool, optional): Whether to append the value or edit it. Defaults to False.
        Returns:
            bool: True if the value was set successfully, False otherwise.
        """
        ctx = get_context(interaction)
        value_sha256 = hashlib.sha256((self.tag.value[self._position] or "").encode()).hexdigest()
        value = None
        try:
            if append:
                value, new_ctx = await ctx.ask_with_modal(
                    title=self.tag.name or "Tag",
                    question_s="Add to value:" if append else "Value:",
                    timeout=60*20,
                )
            else:
                value, new_ctx = await ctx.ask_with_modal(
                    title=self.tag.name or "Tag",
                    question_s="Edit value:",
                    pre_value_s=self.tag.value[self._position] or "",
                    timeout=60*20,
                )
        except asyncio.TimeoutError:
            return False
        self.set_context(new_ctx)
        if value is None or not value:
            # no new value or value is the same
            return False
        if not append and value_sha256 == hashlib.sha256(value.encode()).hexdigest():
            # when the edited is the same, return
            return False
        
        values = crumble(f"{value}", 2000)
        if append and self.tag.value:
            self.tag.value = [
                *self.tag.value[:self._position],  # tag pages until selected page
                *crumble(self.tag.value[self._position]+f"\n{values[0]}", 2000),  # selected page + value crumbled
                *values[1:],  # rest of values as separate pages
                *self.tag.value[self._position+1:]  # tag pages after selected page
            ]
        else:
            self.tag.value = [
                *self.tag.value[:self._position], 
                *crumble(values[0], 2000), 
                *values[1:], 
                *self.tag.value[self._position+1:]
            ]
        return True

    async def extend_value(self, interaction: ComponentInteraction) -> bool:
        """
        Extends the value of the paginator by appending the interaction value.

        Parameters:
        ------------
        interaction (ComponentInteraction): The interaction object representing the user's interaction.

        Returns:
        ----------
        bool: True if the value was successfully extended, False otherwise.
        """

        return await self.set_value(interaction, append=True)

    async def change_visibility(self, interaction: ComponentInteraction):
        if self.tag._is_local:
            self.tag._is_local = False
            self.tag.guild_ids.append(0)
        else:
            self.tag._is_local = True
            self.tag.guild_ids.remove(0)

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
        raise NotImplementedError("Needs to be reimplemented with modal")
        ctx = get_context(interaction)
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

    def build_default_components(self, position: int | None = None) -> List[MessageActionRowBuilder]:
        rows: List[MessageActionRowBuilder] = []
        navi = super().build_default_component(position)
        if navi:
            rows.append(navi)
        rows = add_row_when_filled(rows, min_empty_slots=2)
        rows[-1].add_interactive_button(
            ButtonStyle.PRIMARY, 
            self._serialize_custom_id("tag_options_update"),
            emoji="🔄",
            label="update",
        )
        rows[-1].add_interactive_button(
            ButtonStyle.PRIMARY,
            self._serialize_custom_id("tag_options_resend"),
            emoji="⤵️",
            label="send down",
        )
        rows = add_row_when_filled(rows, min_empty_slots=3)
        rows[1].add_interactive_button(
            ButtonStyle.SECONDARY,
            self._serialize_custom_id("tag_options_set_value"),
            emoji="📝",
            label="Edit",
        )
        rows[1].add_interactive_button(
            ButtonStyle.SECONDARY,
            self._serialize_custom_id("tag_options_extend_value"), # plus emoji: "➕"
            emoji="➕",
            label="Append",
        )
        rows[1].add_interactive_button(
            ButtonStyle.PRIMARY if self.tag.info_visible else ButtonStyle.SECONDARY,
            self._serialize_custom_id("tag_options_info_visible"), # eye emoji: "👁️"
            label="Info visible" if self.tag.info_visible else "Info hidden",
        )
        rows[1].add_interactive_button(
            ButtonStyle.SECONDARY,
            self._serialize_custom_id("tag_options_end_editing"), # end editing emojis: 
            label="End Editing",
            emoji="✔️"
        )
        tag_type_components = TagTypeComponents.get(self.tag.tag_type)(self)
        if tag_type_components:
            rows.append(tag_type_components)
        menu = (
            MessageActionRowBuilder()
            .add_text_menu(self._serialize_custom_id("tag_options"))
            .add_option("set name", "set_name")
            .add_option("edit value", "set_value")
            .add_option("add to value", "extend_value")
            .add_option("add an alias", "add_alias")
            .add_option("add a guild", "add_guild_id")
            .add_option("add an author", "add_author_id")
            .add_option("remove an author", "remove_author_id")
            .add_option("remove alias", "remove_alias")
            .add_option("remove guild", "remove_guild_id")
            .add_option("add new page", "add_new_page")
            .add_option("remove current page", "remove_this_page")
            .add_option("change tag type", "ask_type")
            .add_option("delete tag", "remove_tag")
            .add_option("Get tag link", "get_tag_link")
            .parent
        )
        rows.append(menu)
        if self._additional_components:
            rows.extend(self._additional_components)
        return rows

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
    
    @staticmethod
    def F_get_serialization_custom_id_dict(
        custom_id: str,
        custom_id_type: str,
        position: int,
        tag_id: int,
        author_id: Optional[int] = None,
        message_id: Optional[int] = None,
        **kwargs
    ) -> Dict:
        """
        Manually serialize custom ID statically.
        
        Returns:
        - str: the serialized json string
        """
        d = {
            "tid": tag_id,
            "cid": custom_id,
            "t": custom_id_type,
            "p": position
        }
        if author_id:
            d["aid"] = author_id
        if message_id:
            d["mid"] = message_id
        d.update(kwargs)
        return d
    

class TagViewPaginator(StatelessPaginator):
    def __init__(self, tag: Tag, **kwargs):
        self.tag = tag
        super().__init__(
            **kwargs,
            timeout=15*60,
            additional_components=tag.components,
            first_message_kwargs={"embeds": []},
        )

    def _get_custom_id_kwargs(self) -> Dict[str, int | str]:
        return {"tid": self.tag.id}

    async def _rebuild(self, interaction: ComponentInteraction | CommandInteraction, force_show_name: bool = False, name: str = ""):
        self.set_context(interaction=interaction)
        if not isinstance(interaction, ComponentInteraction):
            return
        self.__maybe_add_edit_component(interaction)    
        self._build_pages(force_show_name=force_show_name, name=name)

    def __maybe_add_edit_component(self, interaction: ComponentInteraction | CommandInteraction) -> None:
        """
        Adds an edit button to the tag's components if the user is authorized to write.
        This method checks if the user who triggered the interaction is authorized to write to the tag.
        If the user is authorized, it adds an interactive button to the tag's components that allows
        the user to edit the tag. The button is labeled with the tag's name and an edit emoji.
        Args:
            event (InteractionCreateEvent): The event that triggered the interaction.
        Attributes:
            self._additional_components (List[MessageActionRowBuilder]): The updated list of components
                with the added edit button if the user is authorized to write.
        """

        if self.tag.is_authorized_to_write(interaction.user.id):
            log.debug("User is authorized to write")
            # user authorized to write -> add tag edit button
            components: List[MessageActionRowBuilder] = add_row_when_filled(self.tag.components or [])
            components[-1].add_interactive_button( # todo: small json
                ButtonStyle.SECONDARY, 
                TagCustomID(
                    custom_id="tag_options_update",
                    author_id=interaction.user.id
                )
                    .set_tag_id(self.tag.id)
                    .set_position(0)
                    .serialize_custom_id()
                    .as_json(),
                label=f"Edit {self.tag.name} instead",
                emoji="📝"
            )
            self._additional_components = components
        else:
            log.debug("User is not authorized to write")
            
    def _build_pages(self, force_show_name: bool = False, name: str = ""):
        media_regex = r"(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|gif|png|mp4|mp3)"
        messages = []
        add_title = True
        assert self.tag.value is not None
        for page in self.tag.value:
            for value in crumble(page, 2000):
                message = ""
                # if tag isn't just a picture and tag was not invoked with original name,
                # AND it's the first page of the tag
                # then append original name at start of message
                if (
                    (not (
                        name == self.tag.name
                        or re.match(media_regex, "\n".join(self.tag.value).strip())
                    )
                    or force_show_name) and add_title
                ):
                    message += f"**{self.tag.name}**\n\n"
                    add_title = False
                message += value
                messages.append(message)
        self.set_pages(messages)

    async def start(self, ctx: InuContext, force_show_name: bool = False, name: str = ""):
        self._build_pages(force_show_name=force_show_name, name=name)
        self.__maybe_add_edit_component(ctx.interaction)
        await super().start(ctx)

    @property
    def custom_id_type(self) -> str:
        return "stl-tag"  # stateless tag paginator




