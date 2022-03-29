-- A helper bot for Genshin Impact players.
-- Copyright (C) 2022-Present XuaTheGrate
-- 
-- This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
-- 
-- This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
-- 
-- You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

create table if not exists artifacts (
    uuid SERIAL PRIMARY KEY,
    userid BIGINT NOT NULL,
    set TEXT NOT NULL,
    slot SMALLINT NOT NULL,
    rarity SMALLINT NOT NULL,
    level SMALLINT NOT NULL
);

create table if not exists artifact_substats (
    uuid INT REFERENCES artifacts on delete cascade,
    stat TEXT NOT NULL,
    rolls SMALLINT[] NOT NULL
);

create table if not exists user_config (
    userid BIGINT PRIMARY KEY UNIQUE NOT NULL,
    server TEXT NOT NULL
);

create table if not exists daily_reminder (
    userid BIGINT UNIQUE REFERENCES user_config ON DELETE CASCADE,
    repeat BOOLEAN NOT NULL DEFAULT FALSE,
    channelid BIGINT NOT NULL
);

create table if not exists weekly_reminder (
    userid BIGINT UNIQUE REFERENCES user_config ON DELETE CASCADE,
    repeat BOOLEAN NOT NULL DEFAULT FALSE,
    channelid BIGINT NOT NULL
);

create table if not exists resin_reminder (
    userid BIGINT UNIQUE REFERENCES user_config ON DELETE CASCADE,
    rlimit INT NOT NULL,
    alert TIMESTAMP WITH TIME ZONE,
    channelid BIGINT NOT NULL
);
