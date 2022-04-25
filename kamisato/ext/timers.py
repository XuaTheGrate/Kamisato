"""
A helper bot for Genshin Impact players.
Copyright (C) 2022-Present XuaTheGrate

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import asyncio
import datetime
import itertools
import zoneinfo
from typing import TYPE_CHECKING

import asyncpg
import discord
from asyncpg.exceptions import ForeignKeyViolationError, UniqueViolationError, PostgresConnectionError
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

        self._custom_reminder_task: asyncio.Task[None] | None = None
        self._latest_reminder: datetime.datetime | None = None
        self._custom_reminder_active = asyncio.Event()

        self._ensure_reminder_loop()

    async def cog_unload(self) -> None:
        self.daily_timer_america.stop()
        self.daily_timer_asia.stop()
        self.daily_timer_europe.stop()

        if self._custom_reminder_task:
            self._custom_reminder_task.cancel()
            self._custom_reminder_task = None

    async def _purge_daily(self, server: str, weekly: bool = False):
        async with self.bot.db.acquire() as c, c.transaction():
            await c.execute(QUERY_DELETE_REMINDER.format("daily"), server)
            if not weekly:
                return
            await c.execute(QUERY_DELETE_REMINDER.format("weekly"), server)

    async def _temporary_reminder(
        self, *,
        user: discord.Member | discord.User,
        channel: discord.abc.MessageableChannel,
        text: str,
        current: datetime.datetime,
        when: datetime.datetime
    ) -> None:
        await utils.sleep_until(when)
        await channel.send(f"{user.mention}, {utils.format_dt(current, 'R')}: {text}")

    def _ensure_reminder_loop(self):
        if self._custom_reminder_task:
            self._custom_reminder_task.cancel()
        self._custom_reminder_task = self.bot.loop.create_task(self._reminder_loop())

    # --- Timers --- #

    async def _reminder_loop(self):
        await self.bot.wait_until_ready()

        if not self._custom_reminder_active.is_set() and  await self.bot.db.fetchval("SELECT 1 FROM custom_reminder LIMIT 1;"):
            self._custom_reminder_active.set()

        try:
            while not self.bot.is_closed():
                await self._custom_reminder_active.wait()
                q = """
                SELECT uid, userid, channelid, created, target, message
                FROM custom_reminder
                WHERE expires < (CURRENT_DATE + '40 days'::interval)
                ORDER BY expires
                LIMIT 1;
                """
                data: tuple[int, int, int, datetime.datetime, datetime.datetime, str] | None = await self.bot.db.fetchrow(q)  # type: ignore
                if not data:
                    self._custom_reminder_active.clear()
                    continue
                
                unique, user_id, channel_id, created_at, target, message = data
                self._latest_reminder = target
                await utils.sleep_until(target)

                async with self.bot.db.acquire() as c, c.transaction():
                    await c.execute("DELETE FROM custom_reminder WHERE uid=$1;", unique)
                
                try:
                    channel: discord.abc.MessageableChannel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)  # type: ignore
                except discord.HTTPException:
                    continue
            
                guild = channel.guild.id if hasattr(channel, 'guild') else '@me'  # type: ignore

                try:
                    await channel.send(f'<@!{user_id}>, {utils.format_dt(created_at, "R")}: {message}')
                except discord.HTTPException:
                    continue
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, PostgresConnectionError):
            self._ensure_reminder_loop()

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

    @tasks.loop(time=datetime.time(4, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("Etc/GMT+5")))
    async def daily_timer_america(self):
        weekday = datetime.datetime.now(zoneinfo.ZoneInfo("Etc/GMT+5")).weekday()
        if weekday == 0:
            await self._weekly_callback("america")
        else:
            await self._daily_callback("america")

    @tasks.loop(time=datetime.time(4, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-8")))
    async def daily_timer_asia(self):
        weekday = datetime.datetime.now(zoneinfo.ZoneInfo("Etc/GMT-8")).weekday()
        if weekday == 0:
            await self._weekly_callback("asia")
        else:
            await self._daily_callback("asia")

    @tasks.loop(time=datetime.time(4, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-1")))
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
        await interaction.response.defer(ephemeral=True)

        try:
            async with self.bot.db.acquire() as c, c.transaction():
                server: str = await c.fetchval(
                    QUERY_INSERT_REMINDER.format("daily"),
                    interaction.user.id, repeat, interaction.channel_id
                )
        except ForeignKeyViolationError:
            await interaction.followup.send(f"Failed to set up a reminder. Make sure you have a server specified via `/server update <region>`")
            return
        except UniqueViolationError:
            async with self.bot.db.acquire() as c, c.transaction():
                await c.execute("DELETE FROM daily_reminder WHERE userid=$1;", interaction.user.id)

            await interaction.followup.send("The reminder was cancelled.")
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
        await interaction.response.defer(ephemeral=True)

        try:
            async with self.bot.db.acquire() as c, c.transaction():
                server: str = await c.fetchval(
                    QUERY_INSERT_REMINDER.format("weekly"),
                    interaction.user.id, repeat, interaction.channel_id
                )
        except ForeignKeyViolationError:
            await interaction.followup.send("Failed to set up a reminder. Make sure you have a server specified via `/server update <region>`")
            return
        except UniqueViolationError:
            async with self.bot.db.acquire() as c, c.transaction():
                await c.execute("DELETE FROM weekly_reminder WHERE userid=$1;", interaction.user.id)
                
            await interaction.followup.send("The reminder was cancelled.")
            return

        now = datetime.datetime.now(timezones[server])
        time_since_monday = 7 - now.weekday()
        if now.weekday() == 0 and now.hour < 4:  # resets in a few hours
            time_since_monday = 0
        now += datetime.timedelta(days=time_since_monday)

        time_until = datetime.datetime(now.year, now.month, now.day, 4, tzinfo=timezones[server]).astimezone(zoneinfo.ZoneInfo("Etc/UTC"))
        time_format = utils.format_dt(time_until, "R")

        await interaction.followup.send(f"Okay, I will mention you when the {server.title()} server resets {time_format}{' every week' if repeat else ''}.")
    
    @reminder.command()
    @ac.describe(current="The current amount of resin you have.", limit="The maximum amount of resin before pinging. Defaults to 155.")
    async def resin(self, interaction: discord.Interaction, current: ac.Range[int, 0, 160], limit: ac.Range[int, 1, 160] = 155):
        """Set up a reminder to ping you when your resin is close to the limit."""
        if current >= limit:
            await interaction.response.send_message("You're already at the limit!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)

        async with self.bot.db.acquire() as c, c.transaction():
            """    uid SERIAL PRIMARY KEY UNIQUE NOT NULL,
    userid BIGINT NOT NULL,
    channelid BIGINT NOT NULL,
    message TEXT NOT NULL DEFAULT '...',
    target TIMESTAMP NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT NOW AT TIME ZONE 'utc'"""
            query = """
            INSERT INTO custom_reminder
            (userid, channelid, message, target)
            VALUES ($1, $2, $3, $4)
            RETURNING uid;
            """
            # uid = await c.fetchval

    @reminder.command()
    @ac.describe(when="When you want to be reminded.", what="What to remind you of.")
    async def custom(self, interaction: discord.Interaction, when: str, what: str = "\u2026"):
        """Set up a custom reminder to ping you at a certain time."""
        await interaction.response.send_message("todo", ephemeral=True)


async def setup(bot: Kamisato) -> None:
    await bot.add_cog(Timers(bot))
