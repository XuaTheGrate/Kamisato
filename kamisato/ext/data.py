from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import MISSING

if TYPE_CHECKING:
    from kamisato import Kamisato
    from kamisato.types import Rarity, ScanData

    ArtifactSubstatDataT = dict[str, dict[str, list[float]]]

class Data(commands.Cog):
    data = app_commands.Group(name="data", description="Configure your Genshin Impact data.")

    def __init__(self, bot: Kamisato):
        self.bot = bot

        self._artifact_substat_data: ArtifactSubstatDataT = MISSING

    def convert_artifact_stat_to_rolls(self, key: str, value: float, *, rarity: int = Rarity.gold) -> list[int]:
        if not self._artifact_substat_data:
            with open("GenshinData/Kamisato_Formatted/artifact_substats.json") as f:
                self._artifact_substat_data: ArtifactSubstatDataT = json.load(f)

        stats = self._artifact_substat_data[str(rarity)]
        is_percent = key.endswith("_")
        possible: list[float] = [f * ((is_percent and 100) or 1) for f in stats[key]]
        rounded: list[float] = [round(f, is_percent) for f in possible]

        if value in rounded:  # 1 roll into key
            return [rounded.index(value)]

        # todo: check for multiple rolls
        
        return ...

    async def save_data(self, data: ScanData) -> tuple[int, int, int]:
        # await asyncio.sleep(5)



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


async def setup(bot: Kamisato) -> None:
    await bot.add_cog(Data(bot), guild=discord.Object(639770490755612672))
