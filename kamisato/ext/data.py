"""
A helper bot for Genshin Impact players.
Copyright (C) 2022-Present XuaTheGrate

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import MISSING

# from pprint import pprint as print

if TYPE_CHECKING:
    from typing import Any

    from kamisato import Kamisato
    from kamisato.types import Rarity, ScanData, _ScanData_Artifacts_Artifact

    ArtifactSubstatDataT = dict[str, dict[str, list[float]]]

class Data(commands.Cog):
    data = app_commands.Group(name="data", description="Configure your Genshin Impact data.")

    def __init__(self, bot: Kamisato):
        self.bot = bot

        self._artifact_substat_data: ArtifactSubstatDataT = MISSING

    def convert_artifact_substats_to_rolls(self, artifact: _ScanData_Artifacts_Artifact, *, rarity: Rarity) -> dict[str, list[int]]:
        if not self._artifact_substat_data:
            with open("GenshinData/Kamisato_Formatted/artifact_substats.json") as f:
                self._artifact_substat_data: ArtifactSubstatDataT = json.load(f)

        stats: dict[str, list[float]] = self._artifact_substat_data[str(rarity)]
        rolls: dict[str, list[int]] = {}

        for sub in artifact["substats"]:
            stat: str
            v: float
            stat, v = sub.values()  # type: ignore
            is_percent = stat.endswith("_")
            possible = stats[stat]
            if is_percent:
                possible = [k * 100 for k in possible]

            for n in itertools.product(possible, repeat=int(v // possible[0])):
                print("test", v, n, round(sum(n), is_percent))
                total = round(sum(n), is_percent)
                if total == v:
                    rolls[stat] = [{j: i for i, j in enumerate(possible)}[k] for k in n]
        
        return rolls

    async def save_data(self, data: ScanData) -> tuple[int, int, int]:
        # await asyncio.sleep(5)

        roll_data: dict[str, list[int]]
        roll_data, _ = MISSING  # TODO

        artifacts: list[Any] = []
        
        async with self.bot.db.acquire() as c, c.transaction():
            for artifact in artifacts:
                pass

        return 0, 0, 0

    @data.command(name="import")
    async def _import(self, interaction: discord.Interaction, data: discord.Attachment) -> None:
        """Imports your scanned data from a JSON encoded file."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        read = await data.read()

        try:
            dat: ScanData = json.loads(read)
        except json.JSONDecodeError:
            await interaction.followup.send("An error occured decoding the file. Double check your input and try again.")
            return
        
        try:
            artifacts, weapons, characters = await self.save_data(dat)
        except ValueError as err:
            await interaction.followup.send(f"An error occured saving the data. Double check your input and try again.\nDebug: `{err}`")
            return

        await interaction.followup.send(f"Data updated successfully.\n- Artifacts: {artifacts:,}\n- Weapons: {weapons:,}\n- Characters: {characters:,}")

    @data.command()
    async def purge(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("todo", ephemeral=True)


async def setup(bot: Kamisato) -> None:
    await bot.add_cog(Data(bot), guild=discord.Object(639770490755612672))
