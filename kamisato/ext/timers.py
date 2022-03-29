"""
A helper bot for Genshin Impact players.
Copyright (C) 2022-Present XuaTheGrate

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import datetime
import itertools
import zoneinfo
from typing import TYPE_CHECKING

import discord
from asyncpg.exceptions import ForeignKeyViolationError, UniqueViolationError
from discord import app_commands as ac, utils, ui
from discord.ext import commands, tasks

from kamisato.ext.misc import timezones

if TYPE_CHECKING:
    from kamisato import Kamisato


QUERY_DELETE_REMINDER = """
DELETE FROM {0}_reminder
    USING user_config
WHERE {0}_reminder.userid = user_config.userid
    AND NOT repeat
    AND user_config.server = $1;
"""
QUERY_SELECT_REMINDER = """
SELECT {0}_reminder.userid, {0}_reminder.channelid
    FROM {0}_reminder 
LEFT JOIN user_config
    ON user_config.userid = {0}_reminder.userid
WHERE user_config.server = $1;
"""
QUERY_INSERT_REMINDER = """
WITH {0} AS (
    INSERT INTO {0}_reminder 
    (userid, repeat, channelid)
    VALUES ($1, $2, $3)
    RETURNING {0}_reminder.userid
)
SELECT server
    FROM user_config
INNER JOIN {0}
    ON user_config.userid = {0}.userid;
"""


class Timers(commands.Cog):
    def __init__(self, bot: Kamisato):
        self.bot = bot
        self.daily_timer_america.start()
        self.daily_timer_asia.start()
        self.daily_timer_europe.start()

    async def cog_unload(self) -> None:
        self.daily_timer_america.stop()
        self.daily_timer_asia.stop()
        self.daily_timer_europe.stop()

    async def _purge_daily(self, server: str, weekly: bool = False):
        async with self.bot.db.acquire() as c, c.transaction():
            await c.execute(QUERY_DELETE_REMINDER.format("daily"), server)
            if not weekly:
                return
            await c.execute(QUERY_DELETE_REMINDER.format("weekly"), server)

    # --- Timers --- #

    async def _daily_callback(self, server: str):
        rows: list[tuple[int, int]] = await self.bot.db.fetch(QUERY_SELECT_REMINDER.format("daily"), server)  # type: ignore

        for channel_id, group in itertools.groupby(rows, key=lambda t: t[1]):
            channel: discord.abc.MessageableChannel | None = self.bot.get_channel(channel_id)  # type: ignore

            if channel is None:
                self.bot.log.error("Failed to send daily reminder as channel id '%s' was not found.", channel_id)

                async with self.bot.db.acquire() as c, c.transaction():
                    await c.execute("DELETE FROM daily_reminder WHERE channelid = $1;", channel_id)

                continue

            mention_format = " ".join(f"<@!{k}>" for k, _ in group)
            await channel.send(f'{mention_format} the {server.title()} server dailies have reset!')
        
        await self._purge_daily(server)

    async def _weekly_callback(self, server: str):
        rows: list[tuple[int, int]] = await self.bot.db.fetch(QUERY_SELECT_REMINDER.format("weekly"), server)  # type: ignore

        for channel_id, group in itertools.groupby(rows, key=lambda t: t[1]):
            channel: discord.abc.MessageableChannel | None = self.bot.get_channel(channel_id)  # type: ignore

            if channel is None:
                self.bot.log.error("Failed to send weekly reminder as channel id '%s' was not found.", channel_id)
                async with self.bot.db.acquire() as c, c.transaction():
                    await c.execute("DELETE FROM weekly_reminder WHERE channelid = $1;", channel_id)

                continue

            mention_format = " ".join(f"<@!{k}>" for k, _ in group)
            await channel.send(f'{mention_format} the {server.title()} server weeklies (and dailies) have reset!')
        
        await self._purge_daily(server)

    @tasks.loop(time=datetime.time(4, tzinfo=zoneinfo.ZoneInfo("Etc/GMT+5")))
    async def daily_timer_america(self):
        weekday = datetime.datetime.now(zoneinfo.ZoneInfo("Etc/GMT+5")).weekday()
        if weekday == 0:
            await self._weekly_callback("america")
        else:
            await self._daily_callback("america")

    @tasks.loop(time=datetime.time(4, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-8")))
    async def daily_timer_asia(self):
        weekday = datetime.datetime.now(zoneinfo.ZoneInfo("Etc/GMT-8")).weekday()
        if weekday == 0:
            await self._weekly_callback("asia")
        else:
            await self._daily_callback("asia")

    @tasks.loop(time=datetime.time(4, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-1")))
    async def daily_timer_europe(self):
        weekday = datetime.datetime.now(zoneinfo.ZoneInfo("Etc/GMT-1")).weekday()
        if weekday == 0:
            await self._weekly_callback("europe")
        else:
            await self._daily_callback("europe")

    # --- Commands --- #

    reminder = ac.Group(name="reminder", description="Commands to help remind you about stuff.", guild_ids=[639770490755612672])

    @reminder.command()
    @ac.describe(repeat="Whether to remind you every day. If `true`, re-run this command to disable the reminder.")
    async def daily(self, interaction: discord.Interaction, repeat: bool = False):
        """Set up a reminder to ping you when the daily server reset occurs."""
        await interaction.response.defer()

        try:
            async with self.bot.db.acquire() as c, c.transaction():
                server: str = await c.fetchval(
                    QUERY_INSERT_REMINDER.format("daily"),
                    interaction.user.id, repeat, interaction.channel_id
                )
        except ForeignKeyViolationError:
            await interaction.followup.send(f"Failed to set up a reminder. Make sure you have a server specified via `/server update <region>`", ephemeral=True)
            return
        except UniqueViolationError:
            async with self.bot.db.acquire() as c, c.transaction():
                await c.execute("DELETE FROM daily_reminder WHERE userid=$1;", interaction.user.id)

            await interaction.followup.send("The reminder was cancelled.", ephemeral=True)
            return

        now = datetime.datetime.now(timezones[server])
        if now.hour > 4:
            now += datetime.timedelta(days=1)

        time_until = datetime.datetime(now.year, now.month, now.day, 4, tzinfo=timezones[server]).astimezone(zoneinfo.ZoneInfo("Etc/UTC"))
        time_format = utils.format_dt(time_until, "R")

        await interaction.followup.send(f"Okay, I will mention you when the {server.title()} server resets {time_format}{' every day' if repeat else ''}.")

    @reminder.command()
    @ac.describe(repeat="Whether to remind you every week. If `true`, re-run this command to disable the reminder.")
    async def weekly(self, interaction: discord.Interaction, repeat: bool = False):
        """Set up a reminder to ping you when the weekly server reset occurs."""
        await interaction.response.defer()

        try:
            async with self.bot.db.acquire() as c, c.transaction():
                server: str = await c.fetchval(
                    QUERY_INSERT_REMINDER.format("weekly"),
                    interaction.user.id, repeat, interaction.channel_id
                )
        except ForeignKeyViolationError:
            await interaction.followup.send("Failed to set up a reminder. Make sure you have a server specified via `/server update <region>`", ephemeral=True)
            return
        except UniqueViolationError:
            async with self.bot.db.acquire() as c, c.transaction():
                await c.execute("DELETE FROM weekly_reminder WHERE userid=$1;", interaction.user.id)
                
            await interaction.followup.send("The reminder was cancelled.", ephemeral=True)
            return

        now = datetime.datetime.now(timezones[server])
        time_since_monday = 7 - now.weekday()
        now += datetime.timedelta(weeks=time_since_monday)

        time_until = datetime.datetime(now.year, now.month, now.day, 4, tzinfo=timezones[server]).astimezone(zoneinfo.ZoneInfo("Etc/UTC"))
        time_format = utils.format_dt(time_until, "R")

        await interaction.followup.send(f"Okay, I will mention you when the {server.title()} server resets {time_format}{' every week' if repeat else ''}.")
    
    @reminder.command()
    @ac.describe(current="The current amount of resin you have.", limit="The maximum amount of resin before pinging. Defaults to 155.")
    async def resin(self, interaction: discord.Interaction, current: ac.Range[int, 0, 160], limit: ac.Range[int, 1, 160] = 155):
        """Set up a reminder to ping you when your resin is close to the limit."""
        await interaction.response.send_message("todo", ephemeral=True)

    @reminder.command()
    @ac.describe(when="When you want to be reminded.")
    @ac.describe(what="What to remind you of.")
    async def custom(self, interaction: discord.Interaction, when: str, what: str = "\u2026"):
        """Set up a custom reminder to ping you at a certain time."""
        await interaction.response.send_message("todo", ephemeral=True)


async def setup(bot: Kamisato) -> None:
    await bot.add_cog(Timers(bot))
