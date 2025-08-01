import asyncio
from collections import Counter, UserList, UserString
from collections.abc import AsyncGenerator, Callable, Generator, Iterable
import contextlib
from copy import copy, deepcopy
from dataclasses import dataclass
import datetime
from enum import Enum, auto
import functools
import itertools
import pathlib
import random
import re
import string
import time
from typing import Any, Literal, NamedTuple, Protocol, Self, TypeAlias
from typing import final, runtime_checkable


import aiosqlite
from fastapi import FastAPI, responses, status
from pydantic import BaseModel
import uvicorn


print(pathlib.Path.cwd())


class Database:
    @staticmethod
    @contextlib.asynccontextmanager
    async def get_conn() -> AsyncGenerator[aiosqlite.Connection, None]:
        conn = await aiosqlite.connect('data.db')
        try:
            # db.row_factory = aiosqlite.Row
            yield conn
            await conn.commit()
        except Exception as e:
            print(f'Error: {e}')
            await conn.rollback()
            raise
        finally:
            await conn.close()

    @staticmethod
    @contextlib.asynccontextmanager
    async def get_cursor(
        sql: str, para: tuple = ()
    ) -> AsyncGenerator[aiosqlite.Cursor, None]:
        async with aiosqlite.connect('data.db') as conn:
            try:
                async with conn.execute(sql, para) as cursor:
                    yield cursor
                await conn.commit()
            except Exception as e:
                print(f'Error: {e}')
                await conn.rollback()
                raise

    @staticmethod
    async def init_db() -> None:
        SQLS = """
        CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        controller TEXT NOT NULL,
        total_games INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        ---
        CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle INTEGER DEFAULT 1,
        phase TEXT DEFAULT 'night',
        start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end TIMESTAMP);
        ---
        CREATE TABLE IF NOT EXISTS roles (
        id TEXT PRIMARY KEY,
        faction TEXT NOT NULL,
        description TEXT DEFAULT '');
        ---
        CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY,
        link_id TEXT DEFAULT '',
        link_type TEXT DEFAULT '',
        description TEXT DEFAULT '');
        ---
        CREATE TABLE IF NOT EXISTS role_skill (
        role_id TEXT,
        skill_id TEXT,
        PRIMARY KEY (role_id, skill_id));
        ---
        CREATE TABLE IF NOT EXISTS attribute (
        game_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        seat INTEGER NOT NULL,
        role_id TEXT NOT NULL,
        faction TEXT NOT NULL,
        life BOOLEAN DEFAULT TRUE,
        sequence INTEGER DEFAULT 0,
        PRIMARY KEY (game_id, player_id));
        ---
        CREATE TABLE IF NOT EXISTS player_skill (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link_id INTEGER DEFAULT 0,
        game_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        skill_id TEXT NOT NULL,
        quantity REAL DEFAULT 1,
        target_id INTEGER DEFAULT 0,
        cycle INTEGER DEFAULT 0,
        UNIQUE (game_id, player_id, skill_id));
        ---
        CREATE TABLE IF NOT EXISTS log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_skill_id INTEGER NOT NULL,
        target_id INTEGER DEFAULT 0,
        type TEXT NOT NULL,
        comment TEXT DEFAULT '');
        ---
        INSERT OR IGNORE INTO users (name, controller) VALUES
        ('Moderator', 'system');
        ---
        INSERT OR IGNORE INTO roles (id, faction) VALUES
        ('villager', 'human'),
        ('werewolf', 'werewolf'),
        ('seer', 'god'),
        ('witch', 'god'),
        ('hunter', 'god'),
        ('guard', 'god');
        ---
        INSERT OR IGNORE INTO skills (id, link_id, link_type) VALUES
        ('vote', '', ''),
        ('speak', '', ''),
        ('kill', '', ''),
        ('identify', '', ''),
        ('heal', 'poison', 'constraint'),
        ('poison', 'heal', 'constraint'),
        ('shoot', '', ''),
        ('shield', '', '');
        ---
        INSERT OR IGNORE INTO role_skill (role_id, skill_id) VALUES
        ('villager', 'vote'),
        ('villager', 'speak'),
        ('werewolf', 'vote'),
        ('werewolf', 'speak'),
        ('werewolf', 'kill'),
        ('seer', 'vote'),
        ('seer', 'speak'),
        ('seer', 'identify'),
        ('witch', 'vote'),
        ('witch', 'speak'),
        ('witch', 'heal'),
        ('witch', 'poison'),
        ('hunter', 'vote'),
        ('hunter', 'speak'),
        ('hunter', 'shoot'),
        ('guard', 'vote'),
        ('guard', 'speak'),
        ('guard', 'shield');
        """
        for SQL in SQLS.split('---'):
            async with Database.get_conn() as conn:
                await conn.execute(SQL)

    @staticmethod
    async def insert_user(name: str, controller: str, silent=False) -> None:
        SQL = """
        INSERT INTO users (name, controller) VALUES (?, ?);
        """
        try:
            async with Database.get_conn() as conn:
                await conn.execute(SQL, (name, controller))
        except Exception as e:
            if silent:
                pass
            else:
                raise

    @staticmethod
    async def delete_user(name: str) -> None:
        SQL = """
        DELETE FROM users WHERE name = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (name,))

    @staticmethod
    async def select_user(name: str) -> list:
        SQL = """
        SELECT name, controller FROM users WHERE name = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (name,))
            return await cursor.fetchone()

    @staticmethod
    async def update_user(name: str, win: bool) -> None:
        SQL = """
        UPDATE users SET total_games = total_games + 1, wins = wins + ?
        WHERE name = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (int(win), name))


class Game:
    def __init__(self) -> None:
        self.cycle = 1
        self.phase = 'night'
        self.id = 0
        self.system_speak_id = 0

    async def init_db(self) -> None:
        async with Database.get_conn() as conn:
            SQL = """
            INSERT INTO games DEFAULT VALUES;
            """
            await conn.execute(SQL)
            cursor = await conn.execute('SELECT last_insert_rowid()')
            self.id = (await cursor.fetchone())[0]

            SQL = """
            SELECT id FROM users WHERE controller != 'system';
            """
            cursor = await conn.execute(SQL)
            players = await cursor.fetchall()

            roles = [
                'villager',
                'villager',
                'villager',
                'werewolf',
                'werewolf',
                'werewolf',
                'seer',
                'witch',
                'hunter',
            ]
            if len(players) < len(roles):
                raise ValueError('not enough users')

            SQL = """
            INSERT INTO attribute (game_id, player_id, seat, role_id, faction) VALUES
            (?, ?, ?, ?, (SELECT faction FROM roles WHERE id = ?));
            """
            random.shuffle(roles)
            random.shuffle(players)
            for seat, ((player_id,), role_id) in enumerate(
                zip(players, roles)
            ):
                await conn.execute(
                    SQL, (self.id, player_id, seat + 1, role_id, role_id)
                )

            SQL = """
            INSERT OR IGNORE INTO player_skill (game_id, player_id, skill_id) VALUES
            (?, 1, 'speak');
            """
            await conn.execute(SQL, (self.id,))
            cursor = await conn.execute('SELECT last_insert_rowid()')
            self.system_speak_id = (await cursor.fetchone())[0]

            SQL = """
            INSERT INTO player_skill (game_id, player_id, skill_id)
            SELECT a.game_id, a.player_id, rs.skill_id FROM attribute a
            JOIN role_skill rs ON rs.role_id = a.role_id
            WHERE a.game_id = ?
            """
            await conn.execute(SQL, (self.id,))

            SQL = """
            UPDATE player_skill AS ps1 SET link_id =
            ps2.id FROM skills s, player_skill ps2
            WHERE ps1.game_id = ? AND s.id = ps1.skill_id
            AND ps2.game_id = ps1.game_id AND ps2.player_id = ps1.player_id
            AND ps2.skill_id = s.link_id;
            """
            await conn.execute(SQL, (self.id,))

        await self.insert_log(1, 'speak', 'public', 0, 'Game begin.')

    async def loop(self) -> None:
        def setdefault(
            d: dict[int, dict[int, list[str]]],
            seq: int,
            player_id: int,
            skill_id: str,
        ):
            d.setdefault(seq, {})
            d[seq].setdefault(player_id, [])
            d[seq][player_id].append(skill_id)

        skills = await self.select_skill()

        d: dict[int, dict[int, list[str]]] = {}
        skill_seq = {
            'night': {
                'vote': 0,
                'speak': 0,
                'kill': 1,
                'identify': 1,
                'heal': 2,
                'poison': 2,
                'shoot': 0,
                'shield': 1,
            },
            'day': {},
        }

        for player_id, skill_id in skills:
            setdefault(d, skill_seq[self.phase][skill_id], player_id, skill_id)

        sorted(d)
        for seq, value in d.items():
            if seq == 0:
                continue
            await self.player_gather(
                self.player(player_id, skill_ids)
                for player_id, skill_ids in value.items()
            )

        await self.verdict()

        await self.update_game()

    async def player_gather(self, coros) -> None:
        await asyncio.gather(*coros)

    async def player(self, player_id: int, skill_ids: list[str]) -> None:
        async with Database.get_conn() as conn:
            while skill_ids:
                random.shuffle(skill_ids)
                skill_id = skill_ids.pop()
                if await self.player_skill(conn, player_id, skill_id):
                    break

    async def player_skill(
        self, conn: aiosqlite.Connection, player_id: int, skill_id: str
    ) -> bool:
        await asyncio.sleep(0.3)
        targets = [i + 1 for i in range(9)]
        match skill_id:
            case 'vote':
                target = random.choice(targets)
                await self.update_player_skill(player_id, skill_id, target)
                await self.insert_log(player_id, skill_id, 'private', target)
            case 'speak':
                text = 'test'
                await self.insert_log(player_id, skill_id, 'public', 0, text)
            case 'kill':
                target = random.choice(targets)
                await self.update_player_skill(player_id, skill_id, target)
                await self.insert_log(player_id, skill_id, 'private', target)
            case 'identify':
                target = random.choice(targets)
                await self.update_player_skill(player_id, skill_id, target)
                await self.insert_log(player_id, skill_id, 'private', target)
            case 'heal':
                target = random.choice(targets)
                await self.update_player_skill(player_id, skill_id, target)
                await self.insert_log(player_id, skill_id, 'private', target)
            case 'poison':
                target = random.choice(targets)
                await self.update_player_skill(player_id, skill_id, target)
                await self.insert_log(player_id, skill_id, 'private', target)
            case 'shoot':
                pass
            case 'shield':
                target = random.choice(targets)
                await self.update_player_skill(player_id, skill_id, target)
                await self.insert_log(player_id, skill_id, 'private', target)
            case _:
                raise NotImplementedError
        return False

    async def verdict(self) -> None:
        SQL = """
        SELECT faction, COUNT(*) FROM attribute
        WHERE game_id = ?
        GROUP BY faction;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            factions = await cursor.fetchall()

        winner = ''
        for faction, count in factions:
            if faction == 'werewolf' and count == 0:
                winner = 'human'
            if faction != 'werewolf' and count == 0:
                winner = 'werewolf'   # override
        print(factions)
        print(f'winner: {winner if winner else "none"}.')

    async def update_game(self) -> None:
        SQL = """
        UPDATE games SET
            cycle = CASE WHEN phase = 'night' THEN cycle + 1 ELSE cycle END,
            phase = CASE WHEN phase = 'night' THEN 'day' ELSE 'night' END
        WHERE id = ?
        RETURNING cycle, phase;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            self.cycle, self.phase = await cursor.fetchone()

    async def select_skill(self) -> list:
        SQL = """
        SELECT player_id, skill_id FROM player_skill WHERE game_id = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            return await cursor.fetchall()

    async def update_player_skill(
        self, player_id: int, skill_id: str, target_id: int = 0
    ) -> None:
        SQL = """
        UPDATE player_skill SET target_id = ?, cycle = ? WHERE game_id = ? AND player_id = ? AND skill_id = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(
                SQL, (target_id, self.cycle, self.id, player_id, skill_id)
            )

    async def insert_log(
        self,
        player_id: int,
        skill_id: str,
        type_: str,
        target_id: int = 0,
        comment: str = '',
    ) -> None:
        SQL = """
        INSERT INTO log (player_skill_id, type, target_id, comment)
        SELECT id, ?, ?, ? FROM player_skill
        WHERE game_id = ? AND player_id = ? AND skill_id = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(
                SQL, (type_, target_id, comment, self.id, player_id, skill_id)
            )

    async def select_log(self, player_id: int, condition: bool = True) -> str:
        SQL_WHERE = """
        AND (
            up.controller = 'system'
            OR ps.player_id = :pid
            OR l.type = 'public'
            OR l.type = 'team' AND ps.player_id IN (
                SELECT a2.player_id FROM attribute a1
                JOIN attribute a2 ON a2.game_id = :gid AND a1.role_id = a2.role_id
                WHERE a1.game_id = :gid AND a1.player_id = :pid
            )
        )
        """

        SQL = f"""
        SELECT up.name, ap.seat, ps.skill_id, ut.name, at.seat, l.comment
        FROM log l
        JOIN player_skill ps ON ps.id = l.player_skill_id
        LEFT JOIN users up ON up.id = ps.player_id
        LEFT JOIN attribute ap ON ap.game_id = :gid AND ap.player_id = ps.player_id
        LEFT JOIN users ut ON ut.id = l.target_id
        LEFT JOIN attribute at ON at.game_id = :gid AND at.player_id = l.target_id
        WHERE ps.game_id = :gid {SQL_WHERE if condition else ''};
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(
                SQL, {'gid': self.id, 'pid': player_id}
            )
            logs = await cursor.fetchall()

        text = ''
        for (
            player_name,
            player_seat,
            skill_id,
            target_name,
            target_seat,
            comment,
        ) in logs:
            if skill_id == 'speak':
                text += f'{player_name}({player_seat}) said: {comment}\n'
            else:
                text += f'{player_name}({player_seat}) {skill_id} {target_name}({target_seat}).\n'
        return text.strip()


class Games:
    def __init__(self):
        self.games: dict[int, Game] = {}

    async def add_game(self) -> None:
        game = Game()
        await game.init_db()
        self.games[game.id] = game

    async def gather_loop(self):
        coros = [game.loop() for game in self.games.values()]
        await asyncio.gather(*coros)

    async def gather_add_ai(self):
        coros = [
            Database.insert_user(name, 'ai', silent=True)
            for name in random.sample(string.ascii_uppercase, 12)
        ]
        await asyncio.gather(*coros)

    async def gather_log(self):
        coros = [game.select_log(1, False) for game in self.games.values()]
        results = await asyncio.gather(*coros)
        for result in results:
            print(result)


class User(BaseModel):
    name: str
    controller: str


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.init_db()
    games = Games()
    await games.gather_add_ai()
    await games.add_game()
    await games.gather_loop()
    await games.gather_log()
    yield
    print('App is shutting down.')


app = FastAPI(lifespan=lifespan)


@app.post('/register')
async def register(user: User) -> dict:
    try:
        await Database.insert_user(user.name, user.controller)
        return responses.JSONResponse(
            'Registration successful', status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        name, controller = await Database.select_user(user.name)
        if controller == user.controller:
            return responses.JSONResponse(
                'Login successful', status_code=status.HTTP_200_OK
            )
        else:
            raise responses.JSONResponse(
                f'User {user.name} already exists',
                status.HTTP_401_UNAUTHORIZED,
            )


@app.post('/login')
async def login():
    return responses.RedirectResponse(
        url='/register', status_code=status.HTTP_302_FOUND
    )


if __name__ == '__main__':
    uvicorn.run(app)
