"""
A helper bot for Genshin Impact players.
Copyright (C) 2022-Present XuaTheGrate

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import asyncio
from typing import overload, TYPE_CHECKING

import discord
from discord import ui, utils

if TYPE_CHECKING:
    from typing import Iterable
    from typing_extensions import Self


U200B = "\u200b"


class ReactivePaginator(ui.View):
    def __init__(self, paginator: Paginator, /, *, allowed_users: set[int] | None = None):
        super().__init__()
        self._paginator = paginator
        self._page_index = 0
        self._message: discord.Message = utils.MISSING
        self._allowed_users = allowed_users
        if len(paginator.pages) == 1:
            self.right.disabled = self._end.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._allowed_users is None:
            return True
        
        return interaction.user.id in self._allowed_users

    def _rotate(self, dir: int):
        self._page_index += dir
        if self._page_index < 0:
            self._page_index = len(self._paginator.pages) - 1
        elif self._page_index >= len(self._paginator.pages):
            self._page_index = 0
    
    async def _update_msg(self, interaction: discord.Interaction):
        self.left.disabled = self._start.disabled = self._page_index == 0
        self.right.disabled = self._end.disabled = self._page_index == len(self._paginator.pages) -1 

        await interaction.response.edit_message(content=self._paginator.pages[self._page_index], view=self)

    @ui.button(emoji="\u23ee\ufe0f", style=discord.ButtonStyle.blurple, disabled=True)
    async def _start(self, interaction: discord.Interaction, button: ui.Button[Self]) -> None:
        self._page_index = 0
        await self._update_msg(interaction)

    @ui.button(emoji="\u2b05\ufe0f", style=discord.ButtonStyle.blurple, disabled=True)
    async def left(self, interaction: discord.Interaction, button: ui.Button[Self]) -> None:
        self._rotate(-1)
        await self._update_msg(interaction)

    @ui.button(emoji="\u27a1\ufe0f", style=discord.ButtonStyle.blurple)
    async def right(self, interaction: discord.Interaction, button: ui.Button[Self]) -> None:
        self._rotate(+1)
        await self._update_msg(interaction)

    @ui.button(emoji="\u23ed\ufe0f", style=discord.ButtonStyle.blurple)
    async def _end(self, interaction: discord.Interaction, button: ui.Button[Self]) -> None:
        self._page_index = len(self._paginator.pages) - 1
        await self._update_msg(interaction)

    @ui.button(emoji="\u23f9\ufe0f", style=discord.ButtonStyle.red)
    async def _stop(self, interaction: discord.Interaction, button: ui.Button[Self]) -> None:
        child: ui.Button[Self]
        for child in self.children:  # type: ignore
            child.disabled = True
        await interaction.response.edit_message(view=self)


class Paginator:
    def __init__(
        self, *,
        max_size: int = 1990,
        prefix: str | None = None,
        suffix: str | None = None
    ):
        self._pages: list[str] = []
        self._current_page: str = ""

        self.prefix = prefix
        self.suffix = suffix
        self.max_size = max_size

    def _into_fix(self, value: str | None = None) -> str:
        return f'{self.prefix or ""}{value or self._current_page or U200B}{self.suffix or ""}'

    @property
    def pages(self) -> tuple[str, ...]:
        if self._current_page:
            return tuple(self._pages + [self._into_fix()])
        return tuple(self._pages)

    def next_page(self):
        self._pages.append(self._into_fix())
        self._current_page = ""

    def append(self, value: str, /) -> None:
        if len(self._into_fix(value)) > self.max_size:
            raise ValueError("string is outside maximum size (including *fixes")
        
        if len(self._into_fix(self._current_page + value)) > self.max_size:
            self.next_page()
        
        self._current_page += value

    def appendln(self, value: str, /) -> None:
        self.append(value + "\n")
    
    @overload
    def appendlines(self, values: Iterable[str], /) -> None: ...

    @overload
    def appendlines(self, value: str, /, *values: str) -> None: ...

    def appendlines(self, value: Iterable[str] | str, /, *values: str):
        if isinstance(value, str):
            self.append(value)
            for item in values:
                self.append(item)
        else:
            for item in value:
                self.append(item)


class MergeStream:
    def __init__(self, process: asyncio.subprocess.Process):
        if process.stdout is None or process.stderr is None:
            raise ValueError("stdout and stderr must not be None (did you forget to pass stdout=PIPE?)")
        
        self.__process = process
        self.__queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.__stdout = asyncio.create_task(self.__stream_task(process.stdout))
        self.__stderr = asyncio.create_task(self.__stream_task(process.stderr))
        asyncio.create_task(self.__stop_task())

    async def __stop_task(self):
        await self.__process.wait()
        self.__queue.put_nowait(None)

    async def __stream_task(self, stream: asyncio.StreamReader):
        async for line in stream:
            await self.__queue.put(line)
    
    def __aiter__(self) -> MergeStream:
        return self
    
    async def __anext__(self) -> str:
        item = await self.__queue.get()
        if item is None:
            self.__stdout.cancel()
            self.__stderr.cancel()

            raise StopAsyncIteration
        return item.decode("UTF-8").strip()