"""
A helper bot for Genshin Impact players.
Copyright (C) 2022-Present XuaTheGrate

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import datetime
import json
import zoneinfo
from typing import Literal, TYPE_CHECKING

import discord
from discord import app_commands as ac, ui, utils
from discord.ext import commands
from discord.utils import MISSING

if TYPE_CHECKING:
    from typing_extensions import Self

    from kamisato import Kamisato
    from kamisato.types import DailyData


timezones: dict[str, zoneinfo.ZoneInfo] = {
    "america": zoneinfo.ZoneInfo("Etc/GMT+5"),
    "asia": zoneinfo.ZoneInfo("Etc/GMT-8"),
    "europe": zoneinfo.ZoneInfo("Etc/GMT-1")
}

UTC = zoneinfo.ZoneInfo("Etc/UTC")

item_emoji: dict[str, discord.PartialEmoji] = {
    "Freedom": discord.PartialEmoji(name='freedom', id=956865112763924541, animated=False),
    "Prosperity": discord.PartialEmoji(name='prosperity', id=956865128094126080, animated=False),
    "Transience": discord.PartialEmoji(name='transience', id=956865136562421781, animated=False),
    "Ballad": discord.PartialEmoji(name='ballad', id=956865099958734918, animated=False),
    "Gold": discord.PartialEmoji(name='gold', id=956865117574795294, animated=False),
    "Light": discord.PartialEmoji(name='light', id=956865121114812427, animated=False),
    "Resistance": discord.PartialEmoji(name='resistance', id=956865132556869652, animated=False),
    "Diligence": discord.PartialEmoji(name='diligence', id=956865104325001277, animated=False),
    "Elegance": discord.PartialEmoji(name='elegance', id=956865107739152384, animated=False),

    "Decarabian": discord.PartialEmoji(name='decarabian', id=956866862103269376, animated=False),
    "Guyun": discord.PartialEmoji(name='guyun', id=956867348172767232, animated=False),
    "Distant Sea": discord.PartialEmoji(name='distant_sea', id=956867025215578122, animated=False),
    "Boreal Wolf": discord.PartialEmoji(name='boreal_wolf', id=956866795380281344, animated=False),
    "Mist Veiled Elixir": discord.PartialEmoji(name='mist_veiled', id=956867227540414494, animated=False),
    "Narukami": discord.PartialEmoji(name='narukami', id=956867292761841664, animated=False),
    "Dandelion Gladiator": discord.PartialEmoji(name='dand_gladiator', id=956867415503933460, animated=False),
    "Aerosiderite": discord.PartialEmoji(name='aerosiderite', id=956866711930433567, animated=False),
    "Mask": discord.PartialEmoji(name='mask', id=956867093729513492, animated=False),
}

elements: dict[str, discord.PartialEmoji] = {
    "hydro": discord.PartialEmoji(name='hydro', id=956871937303388210, animated=False),
    "pyro": discord.PartialEmoji(name='pyro', id=956871942835679252, animated=False),
    "anemo": discord.PartialEmoji(name='anemo', id=956871949945024542, animated=False),
    "cryo": discord.PartialEmoji(name='cryo', id=956871955275972608, animated=False),
    "dendro": discord.PartialEmoji(name='dendro', id=956871961244475442, animated=False),
    "electro": discord.PartialEmoji(name='electro', id=956871966810325013, animated=False),
    "geo": discord.PartialEmoji(name='geo', id=956871972971765810, animated=False),
}

class Miscellaneous(commands.Cog):
    def __init__(self, bot: Kamisato):
        self.bot = bot
        with open("kamisato/data/daily.json") as f:
            self.daily_data: DailyData = json.load(f)

    server = ac.Group(name="server", description="Genshin Impact server-related commands.", guild_ids=[639770490755612672])

    @server.command(name="update")
    @ac.choices(region=[
        ac.Choice(name="America (GMT-5)", value="america"),
        ac.Choice(name="Asia (GMT+8)", value="asia"),
        ac.Choice(name="Europe (GMT+1)", value="europe")
    ])
    async def _set(self, interaction: discord.Interaction, region: ac.Choice[str]) -> None:
        """Updates your selected server for other server-related commands."""

        async with self.bot.db.acquire() as c, c.transaction():
            q = """
            INSERT INTO user_config (userid, server)
            VALUES ($1, $2)
            ON CONFLICT (userid)
            DO UPDATE
            SET server=$2
            WHERE EXCLUDED.userid=$1;
            """
            await c.execute(q, interaction.user.id, region.value)

        await interaction.response.send_message(f"Updated server to: {region.name}", ephemeral=True)

    @server.command()
    async def today(self, interaction: discord.Interaction) -> None:
        """Shows information about what is available today (domains etc)."""

        server: str = await self.bot.db.fetchval("SELECT server FROM user_config WHERE userid=$1;", interaction.user.id) or "america"
        timezone = timezones[server]
        today = datetime.datetime.now(timezone)

        if today.hour < 4:
            today -= datetime.timedelta(days=1)
            
        reset = datetime.datetime(today.year, today.month, today.day + 1, 4, 0, 0, 0, timezone).astimezone(UTC)

        embed = discord.Embed(title="Available Today", colour=discord.Colour.og_blurple())
        embed.description = f"Resets {utils.format_dt(reset, 'R')}"

        if today.weekday() == 6:
            embed.add_field(name="Talent Books", value="All!", inline=False)
            embed.add_field(name="Weapon Materials", value="All!", inline=False)
        else:
            talents = self.daily_data["domains"]["talent"][today.weekday()]
            for t in talents:
                characters = "\n".join([f"{elements[v]} {k}" for k, v in self.daily_data["talent_books"][t].items()])
                embed.add_field(name=f'{item_emoji[t]} {t}', value=characters, inline=True)
            
            weapons = self.daily_data["domains"]["weapon"][today.weekday()]

            weapon_fmt = [f"{item_emoji[w]} {w}" for w in weapons]

            embed.add_field(name="Weapon Materials", value="\n".join(weapon_fmt), inline=False)

        embed.set_footer(text=f"Server: {server.title()}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: Kamisato):
    await bot.add_cog(Miscellaneous(bot))
