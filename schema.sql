-- A helper bot for Genshin Impact players.
-- Copyright (C) 2022-Present XuaTheGrate
-- 
-- This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
-- 
-- This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
-- 
-- You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

CREATE TABLE IF NOT EXISTS artifacts (
    uuid SERIAL PRIMARY KEY,
    userid BIGINT NOT NULL,
    set TEXT NOT NULL,
    slot SMALLINT NOT NULL,
    rarity SMALLINT NOT NULL,
    level SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_substats (
    uuid INT REFERENCES artifacts on delete cascade,
    stat TEXT NOT NULL,
    rolls SMALLINT[] NOT NULL
);

CREATE TABLE IF NOT EXISTS user_config (
    userid BIGINT PRIMARY KEY UNIQUE NOT NULL,
    server TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_reminder (
    userid BIGINT UNIQUE REFERENCES user_config ON DELETE CASCADE,
    repeat BOOLEAN NOT NULL DEFAULT FALSE,
    channelid BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_reminder (
    userid BIGINT UNIQUE REFERENCES user_config ON DELETE CASCADE,
    repeat BOOLEAN NOT NULL DEFAULT FALSE,
    channelid BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS custom_reminder (
    uid SERIAL PRIMARY KEY UNIQUE NOT NULL,
    userid BIGINT NOT NULL,
    channelid BIGINT NOT NULL,
    message TEXT NOT NULL DEFAULT '...',
    target TIMESTAMP NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS custom_reminder_target_idx ON custom_reminder (target);