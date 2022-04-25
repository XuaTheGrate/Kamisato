"""
A helper bot for Genshin Impact players.
Copyright (C) 2022-Present XuaTheGrate

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import ast
import asyncio, asyncio.subprocess
import io
import re
import textwrap
import traceback
import sys
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands as ac, ui, utils
from discord.ext import commands
from tabulate import tabulate

from kamisato.util import MergeStream, Paginator, ReactivePaginator

if TYPE_CHECKING:
    from typing import Any, Awaitable, Callable, Generator

    from kamisato import Kamisato


CLOSET_ID = 864774293300838420
MAYA_ID = 455289384187592704


def trim(text: str, *, max: int = utils.MISSING, code_block: bool = False, end: str = "…") -> str:
    new_max: int = max or (1900 if code_block else 1990)

    trimmed = text[:new_max]

    if len(text) >= new_max:
        trimmed += end

    if code_block:
        return f"```\n{trimmed}\n```"
    return trimmed


REMOVE_CODEBLOCK = re.compile(r"```([a-zA-Z\-]+)?([\s\S]+?)```")
def remove_codeblock(text: str) -> tuple[str | None, str]:
    find = REMOVE_CODEBLOCK.match(text)
    if not find:
        return None, text
    lang, txt = find.groups()
    return lang, txt


def full_command_name(command: ac.Command[Any, Any, Any] | ac.Group) -> Generator[str, Any, Any]:
    if command.parent:
        yield from full_command_name(command.parent)
    yield command.name


class EvalModal(ui.Modal):
    def __init__(self, *, title: str, sql: bool = False, prev_code: str | None = None, prev_extras: str | None = None):
        super().__init__(title=title)

        self.code = ui.TextInput(label="Code to evaluate", style=discord.TextStyle.paragraph, required=True, default=prev_code)
        self.add_item(self.code)

        self.interaction: discord.Interaction = utils.MISSING
        self.extras: ui.TextInput = utils.MISSING

        if sql:
            self.extras = ui.TextInput(label="Semicolon-separated SQL args", required=False, default=prev_extras)
            self.add_item(self.extras)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self.stop()


class Developers(commands.Cog, ac.Group):
    def __init__(self, bot: Kamisato) -> None:
        super().__init__(name="dev", description="\u2026")
        self.bot = bot
        self.cog.parent = self

        self._last_eval: str | None = None
        self._eval_globals: dict[str, Any] = {"bot": self.bot}

        self._last_sql: str | None = None
        self._last_sql_args: str | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == MAYA_ID

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type is not discord.InteractionType.application_command:
            return
        
        if not interaction.command:
            name = interaction.data["name"]  # type: ignore
            self.bot.log.warning("Received command '%s' which was not found", name)
            return
        
        command_name = " ".join(full_command_name(interaction.command))  # type: ignore
        command_args = " ".join([f"{k}: {v!r}" for k, v in interaction.namespace.__dict__.items()])

        self.bot.log.info(
            "[%s/#%s/%s]: /%s %s", 
            interaction.user,
            interaction.channel,
            interaction.guild,
            command_name, command_args
        )

    cog = ac.Group(name="cog", description="Cog related commands.")

    @cog.command()
    async def load(self, interaction: discord.Interaction, extension: Optional[str] = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        success: list[str] = []
        fail: list[str] = []

        if not extension:
            for ext in self.bot._all_exts:
                if ext not in self.bot.extensions:
                    try:
                        await self.bot.load_extension(ext)
                    except Exception as e:
                        self.bot.log.exception("Failed to load extension '%s'", ext, exc_info=e)
                        fail.append(f'{ext}: {e}')
                    else:
                        success.append(ext)
        else:
            try:
                await self.bot.load_extension(extension)
            except Exception as e:
                self.bot.log.exception("Failed to load extension '%s'", extension, exc_info=e)
                fail.append(f'{extension}: {e}')
            else:
                success.append(extension)

        embed = discord.Embed(colour=discord.Colour.green() if not fail else discord.Colour.red(), description='\u200b')
        if success:
            embed.add_field(name="\U0001f4e5", value="\n".join(success))
        if fail:
            embed.add_field(name="\U0001f4e4", value="\n".join(fail))
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @load.autocomplete("extension")
    async def _load_autocomplete(self, interaction: discord.Interaction, current: str) -> list[ac.Choice[str]]:
        unloaded = sorted(set(self.bot._all_exts) - set(self.bot.extensions.keys()))
        return [ac.Choice(name=k, value=k) for k in unloaded if current in k]

    @cog.command()
    async def reload(self, interaction: discord.Interaction, extension: str) -> None:
        try:
            await self.bot.reload_extension(extension)
        except Exception as e:
            exc = traceback.format_exception(type(e), e, e.__traceback__)
            exc_text = trim("".join(exc), code_block=True)
            await interaction.response.send_message(f"Error reloading extension {extension}{exc_text}", ephemeral=True)
        else:
            await interaction.response.send_message("Success!", ephemeral=True)

    @reload.autocomplete("extension")
    async def _reload_autocomplete(self, interaction: discord.Interaction, current: str) -> list[ac.Choice[str]]:
        exts = list(self.bot.extensions.keys())
        return [ac.Choice(name=k, value=k) for k in sorted(exts) if current in k]

    @cog.command()
    async def list(self, interaction: discord.Interaction) -> None:
        loaded = self.bot.extensions.keys()
        unloaded = set(self.bot._all_exts) - set(loaded)
        embed = discord.Embed(colour=discord.Colour.og_blurple())
        embed.add_field(name="\U0001f4e5", value="\n".join(loaded))
        if unloaded:
            embed.add_field(name="\U0001f4e4", value="\n".join(unloaded))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ac.command()
    async def sync(self, interaction: discord.Interaction, guild_id: Optional[str] = None):
        guild: discord.Guild | None = None
        if guild_id is not None:
            newid = int(guild_id)
            guild = self.bot.get_guild(newid)

            if guild is None:
                await interaction.response.send_message(f"No guild by that ID found.", ephemeral=True)
                return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            commands = await self.bot.tree.sync(guild=guild)
        except discord.HTTPException as e:
            exc = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            trimmed = trim(exc, code_block=True, max=1850)
            await interaction.followup.send(f"Failed to sync commands.\n{trimmed}")
        else:
            await interaction.followup.send(f"Synced `{len(commands)}` commands successfully.")

    @ac.command()
    async def shutdown(self, interaction: discord.Interaction):
        await interaction.response.send_message("ok", ephemeral=True)
        await self.bot.close()

    @ac.command()
    async def sql(self, interaction: discord.Interaction):
        modal = EvalModal(title="SQL Eval", sql=True, prev_code=self._last_sql, prev_extras=self._last_sql_args)
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        await modal.interaction.response.defer(ephemeral=True, thinking=True)
        self._last_sql = modal.code.value
        self._last_sql_args = modal.extras.value

        args: list[Any]
        if modal.extras.value:
            args = [eval(a.strip(), {"interaction": interaction, "bot": self.bot}, {}) for a in modal.extras.value.split(";")]
        else:
            args = []

        try:
            async with self.bot.db.acquire() as c, c.transaction():
                result = await c.fetch(modal.code.value, *args)  # type: ignore
        except Exception as e:
            await modal.interaction.followup.send(f"```sql\n{e}\n```")
            return
        
        fmt = tabulate(result, headers="keys", missingval="null", tablefmt="grid") or "\u200b"
        if len(fmt) > 1900:
            await modal.interaction.followup.send("Output too long...", file=discord.File(io.BytesIO(fmt.encode("UTF-8"))))
        else:
            await modal.interaction.followup.send(f"```sql\n{fmt}\n```")

    @ac.command()
    async def eval(self, interaction: discord.Interaction):
        modal = EvalModal(title="Python Eval", prev_code=self._last_eval)
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return
        
        await modal.interaction.response.defer(ephemeral=True, thinking=True)
        self._last_eval = modal.code.value
        code = f"async def _ka_eval_func0():\n{textwrap.indent(modal.code.value, '    ')}"  # type: ignore

        # if we don't specify `return` in our eval code, then we can inject it directly
        parse: ast.Module = ast.parse(code)
        astfunc: ast.AsyncFunctionDef = parse.body[0]  # type: ignore
        ret = astfunc.body[-1]
        if not isinstance(ret, ast.Return):
            astfunc.body[-1] = ast.Return(ret.value)  # type: ignore
        
        code = ast.unparse(parse)

        self._eval_globals["interaction"] = interaction

        lcls = {}
        try:
            exec(code, self._eval_globals, lcls)
        except Exception as e:
            fmt = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            await modal.interaction.followup.send(f"```py\n{fmt}\n```")
            return
        
        func: Callable[[], Awaitable[Any]] = lcls.pop("_ka_eval_func0")
        try:
            result = await func()
        except Exception as e:
            fmt = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if len(fmt) > 1900:
                await modal.interaction.followup.send("Error too long...", file=discord.File(io.BytesIO(fmt.encode("UTF-8"))))
                return
            await modal.interaction.followup.send(f"```py\n{fmt}\n```")
            return
        
        self._eval_globals["_"] = result
        await modal.interaction.followup.send(f"```py\n{result}\n```")

    @ac.command()
    async def shell(self, interaction: discord.Interaction):
        modal = EvalModal(title="Shell Eval")
        await interaction.response.send_modal(modal)
        self.bot.log.debug("pee pee poo poo")
        if await modal.wait():
            return
        
        await modal.interaction.response.defer(ephemeral=True, thinking=True)
        proc = await asyncio.create_subprocess_shell(modal.code.value, stdout=-1, stderr=-1)  # type: ignore

        shell = "powershell" if sys.platform == "win32" else "bash"

        pg = Paginator(max_size=1900, prefix="```" + shell, suffix="```")

        async for line in MergeStream(proc):
            pg.appendln(line)
        self.bot.log.debug(f"pages: {len(pg.pages)}")
        
        await modal.interaction.followup.send(content=pg.pages[0], view=ReactivePaginator(pg, allowed_users={interaction.user.id}))

    @ac.command()
    @ac.choices(status=[
        ac.Choice(name="Online", value=discord.Status.online.value),
        ac.Choice(name="Idle", value=discord.Status.idle.value),
        ac.Choice(name="Do Not Disturb", value=discord.Status.do_not_disturb.value),
        ac.Choice(name="Offline", value=discord.Status.offline.value)
    ])
    @ac.choices(type=[
        ac.Choice(name="Playing", value=0),
        ac.Choice(name="Listening", value=2),
        ac.Choice(name="Watching", value=3),
        ac.Choice(name="Competing", value=5)
    ])
    async def presence(
        self, 
        interaction: discord.Interaction, 
        status: Optional[ac.Choice[str]] = None, 
        type: Optional[ac.Choice[int]] = None, 
        text: Optional[str] = None
    ):
        if text is None and type is not None:
            await interaction.response.send_message("`text` must be specified with `type`", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        activity = None
        if type is not None:
            self.bot.activity = activity = discord.Activity(type=discord.ActivityType(type.value), name=text)

        s = None
        if status is not None:
            self.bot.status = s = discord.Status[status.value]

        await self.bot.change_presence(status=s, activity=activity)
        await interaction.followup.send("Done")


async def setup(bot: Kamisato) -> None:
    await bot.add_cog(Developers(bot), guild=discord.Object(CLOSET_ID))
