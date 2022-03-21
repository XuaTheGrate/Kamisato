from __future__ import annotations

import asyncio
import contextlib
import logging
from asyncio.subprocess import Process as AsyncProcess
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, TypeVar

import asyncpg
import discord
import toml
from discord.ext import commands
from discord.utils import MISSING


BotT = TypeVar("BotT", bound="Kamisato")

if TYPE_CHECKING:
    from typing import AsyncGenerator

    from .types import Config as ConfigT


__all__ = ['Kamisato', 'Context']

def create_logger(name: str, *, stream: bool = False, level: int = logging.DEBUG, size: int = 8 * 1024 * 1024) -> logging.Logger:
    log_fmt = logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s", datefmt="%d/%m/%y-%H:%M:%S")

    log = logging.getLogger(name)
    log.setLevel(level)
    
    hdlr = RotatingFileHandler(f"logs/{name.lower()}.log", maxBytes=size, backupCount=30, encoding="UTF-8")
    hdlr.setFormatter(log_fmt)
    log.handlers = [hdlr]

    if stream:
        strm = logging.StreamHandler()
        strm.setFormatter(log_fmt)
        log.handlers.append(strm)

    return log

log = create_logger("Kamisato", stream=True)
create_logger("discord", level=logging.INFO)


class Context(commands.Context[BotT]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._pool = self.bot.db
        self.__connection: asyncpg.Connection[asyncpg.Record] | None = None

    def __repr__(self) -> str:
        return f"<Context connection: {self.__connection!r}>"

    @contextlib.asynccontextmanager
    async def acquire(self, timeout: float = 60.0) -> AsyncGenerator[asyncpg.Connection[asyncpg.Record], None]:
        if self.__connection is None:
            self.__connection = await self._pool.acquire(timeout=timeout)  # type: ignore

        try:
            yield self.__connection  # type: ignore
        finally:
            await self._pool.release(self.__connection, timeout=timeout)  # type: ignore
            self.__connection = None


class Kamisato(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.all()
        )

        config: ConfigT = toml.load("config.toml")  # type: ignore
        self.config = config

        self._ssh_tunnel = self.config.get("ssh_tunnel", MISSING)
        self._ssh_tunnel_proc: AsyncProcess = MISSING

        self.db: asyncpg.Pool[asyncpg.Record] = MISSING

    async def get_context(self, message: discord.Message, *, cls: type[commands.Context[Kamisato]] = MISSING) -> commands.Context[Kamisato]:
        return await super().get_context(message, cls=cls or Context)

    async def on_ready(self):
        log.info("Ready[user=%r, guild_count=%d, user_count=%d]", self.user, len(self.guilds), len(self.users))

    async def start_ssh_tunnel(self) -> None:
        if self._ssh_tunnel_proc:
            log.warning("SSH tunnel already running, terminating")
            await self.stop_ssh_tunnel()
        
        log.info("Starting SSH tunnel with args %r", self._ssh_tunnel)
        self._ssh_tunnel_proc = proc = await asyncio.create_subprocess_exec("ssh", "-NL", *self._ssh_tunnel)

        await asyncio.sleep(3)
        if proc.returncode is not None:
            raise RuntimeError(f"Starting SSH tunnel failed with code {proc.returncode}")

    async def stop_ssh_tunnel(self) -> None:
        if self._ssh_tunnel_proc:
            log.info("Shutting down SSH tunnel")

            self._ssh_tunnel_proc.terminate()
            await self._ssh_tunnel_proc.wait()
            self._ssh_tunnel_proc = MISSING
    
    async def setup_hook(self) -> None:
        if self._ssh_tunnel:
            await self.start_ssh_tunnel()

        db: asyncpg.Pool[asyncpg.Record] = await asyncpg.create_pool(**self.config["postgresql"])  # type: ignore
        self.db = db

        log.info("Database connected [{user}@{host}:{port}/{database}]".format(**self.config["postgresql"]))

        for ext in self.config["discord"]["extensions"]:
            try:
                await self.load_extension(ext)
            except Exception as err:
                log.error("Error occured while loading extension \"%s\"", ext, exc_info=err)
            else:
                log.info("Loaded \"%s\" successfully", ext)

        await self.sync_all_commands()

    async def close(self) -> None:
        log.info("Close accepted, shutting down.")
        if self.db:
            try:
                await asyncio.wait_for(self.db.close(), timeout=60.0)
            except asyncio.TimeoutError:
                log.warning("Timed out shutting down database.")
                self.db.terminate()
            finally:
                if self._ssh_tunnel:
                    await self.stop_ssh_tunnel()
        
        await super().close()

    async def sync_all_commands(self) -> None:
        if self.user is None:
            raise RuntimeError("sync_all_commands should be called during startup (after login)")

        global_cmds = [c.to_dict() for c in self.tree._global_commands.values()]
        guild_commands = {k: [c.to_dict() for c in v.values()] for k, v in self.tree._guild_commands.items()}

        for (_, guild_id, _), ctxmenu in self.tree._context_menus.items():
            if not guild_id:
                global_cmds.append(ctxmenu.to_dict())
            else:
                guild_commands.setdefault(guild_id, []).append(ctxmenu.to_dict())

        if global_cmds:
            log.info("Syncing %d global commands", len(global_cmds))
            await self.http.bulk_upsert_global_commands(self.user.id, global_cmds)

        for guild_id, payload in guild_commands.items():
            log.info("Syncing %d commands for guild %d", len(payload), guild_id)
            await self.http.bulk_upsert_guild_commands(self.user.id, guild_id, payload)
