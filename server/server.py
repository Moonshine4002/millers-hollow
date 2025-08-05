import asyncio
import collections
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
import string
import time
from typing import Any, Literal, NamedTuple, Protocol, Self, TypeAlias
from typing import final, runtime_checkable


import aiosqlite
from fastapi import FastAPI, BackgroundTasks, HTTPException, responses, status
from pydantic import BaseModel
import uvicorn

from ai import JsonFormat, input_ai


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
    async def fetchall(cursor: aiosqlite.Cursor) -> list:
        fetch = await cursor.fetchall()
        if fetch is None:
            return []
        return list(fetch)

    @staticmethod
    async def fetchone(cursor: aiosqlite.Cursor) -> tuple:
        fetch = await cursor.fetchone()
        if fetch is None:
            return ()
        return tuple(fetch)

    @staticmethod
    async def init_db() -> None:
        SQLS = """
        CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        controller TEXT NOT NULL,
        kind TEXT DEFALUT '',
        total_games INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        ---
        CREATE TABLE IF NOT EXISTS game (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle INTEGER DEFAULT 1,
        phase TEXT DEFAULT 'night',
        start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end TIMESTAMP);
        ---
        CREATE TABLE IF NOT EXISTS role (
        id TEXT PRIMARY KEY,
        faction TEXT NOT NULL,
        description TEXT DEFAULT '');
        ---
        CREATE TABLE IF NOT EXISTS skill (
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
        INSERT OR IGNORE INTO user (name, controller) VALUES
        ('Moderator', 'system');
        ---
        INSERT OR IGNORE INTO role (id, faction) VALUES
        ('villager', 'human'),
        ('werewolf', 'werewolf'),
        ('seer', 'god'),
        ('witch', 'god'),
        ('hunter', 'god'),
        ('guard', 'god');
        ---
        INSERT OR IGNORE INTO skill (id, link_id, link_type) VALUES
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
    async def insert_user(name: str, controller: str, kind: str = '') -> int:
        SQL = """
        INSERT INTO user (name, controller, kind) VALUES (?, ?, ?);
        """
        async with Database.get_conn() as conn:
            try:
                await conn.execute(SQL, (name, controller, kind))
            except Exception as e:
                return 0
            else:
                cursor = await conn.execute('SELECT last_insert_rowid()')
                fetch = await Database.fetchone(cursor)
                return fetch[0]

    @staticmethod
    async def delete_user(name: str) -> None:
        SQL = """
        DELETE FROM user WHERE name = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (name,))

    @staticmethod
    async def select_user(name: str) -> tuple:
        SQL = """
        SELECT id, controller, kind FROM user WHERE name = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (name,))
            fetch = await Database.fetchone(cursor)
            return fetch if fetch else (0, '', '')

    @staticmethod
    async def update_user(name: str, win: bool) -> None:
        SQL = """
        UPDATE user SET total_games = total_games + 1, wins = wins + ?
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
        self.player_ids: list[int] = []
        self.started = False
        self.player_started: dict[int, bool] = {}
        self.player_finished: dict[int, bool] = {}
        self.player_input: dict[int, dict[str, Any]] = {}
        self.player_output: dict[int, dict[str, Any]] = {}

    async def insert(self) -> int:
        async with Database.get_conn() as conn:
            SQL = """
            INSERT INTO game DEFAULT VALUES;
            """
            await conn.execute(SQL)
            cursor = await conn.execute('SELECT last_insert_rowid()')
            fetch = await Database.fetchone(cursor)
            self.id = fetch[0]
            return self.id

    async def init_db(self) -> None:
        for player_id in self.player_ids:
            self.player_started[player_id] = False
            self.player_finished[player_id] = False

        async with Database.get_conn() as conn:
            SQL = """
            SELECT id FROM user WHERE controller = 'ai';
            """
            cursor = await conn.execute(SQL)
            ais = await Database.fetchall(cursor)
            ai_ids = [
                ai_id for (ai_id,) in ais if ai_id not in self.player_ids
            ]

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
            ai_num = len(roles) - len(self.player_ids)
            if ai_num < 0:
                raise ValueError('Too many user')
            elif ai_num > len(ai_ids):
                raise ValueError('Not enough user')
            ai_ids = random.sample(ai_ids, ai_num)
            for ai_id in ai_ids:
                self.player_ids.append(ai_id)

            SQL = """
            INSERT INTO attribute (game_id, player_id, seat, role_id, faction) VALUES
            (?, ?, ?, ?, (SELECT faction FROM role WHERE id = ?));
            """
            random.shuffle(roles)
            random.shuffle(self.player_ids)
            for seat, (player_id, role_id) in enumerate(
                zip(self.player_ids, roles)
            ):
                await conn.execute(
                    SQL, (self.id, player_id, seat + 1, role_id, role_id)
                )

            SQL = """
            INSERT OR IGNORE INTO player_skill (game_id, player_id, skill_id) VALUES
            (?, 1, 'speak');
            """   # TODO: find Moderator
            await conn.execute(SQL, (self.id,))
            cursor = await conn.execute('SELECT last_insert_rowid()')
            fetch = await Database.fetchone(cursor)
            self.system_speak_id = fetch[0]

            SQL = """
            INSERT INTO player_skill (game_id, player_id, skill_id)
            SELECT a.game_id, a.player_id, rs.skill_id FROM attribute a
            JOIN role_skill rs ON rs.role_id = a.role_id
            WHERE a.game_id = ?
            """
            await conn.execute(SQL, (self.id,))

            SQL = """
            UPDATE player_skill AS ps1 SET link_id =
            ps2.id FROM skill s, player_skill ps2
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
            coros = [
                self.player(player_id, skill_ids)
                for player_id, skill_ids in value.items()
            ]
            await asyncio.gather(*coros)

        await self.verdict()

        await self.update_game()

    async def player(self, p_id: int, skill_ids: list[str]) -> None:
        p_info = await self.select_players(p_id)
        p_name, p_controller, p_kind, p_seat, p_role, p_life = p_info[p_id]

        targets = []
        for id_, (name, *others, seat, role, life) in p_info.items():
            if life:
                targets.append(seat)
        targets.append(0)
        targets.sort()
        self.player_input[p_id] = {'skill': skill_ids, 'target': targets}
        self.player_started[p_id] = True

        while skill_ids:
            self.player_finished[p_id] = False
            if p_controller == 'ai':
                async with Database.get_conn() as conn:
                    log = await self.select_log(p_id)
                p_text = f'You are {p_name}, a {p_role} in seat {p_seat}'
                text = ''
                for id_, (name, *others, seat, role, life) in p_info.items():
                    text += f'id: {id_}, name: {name}, seat: {seat}, role: {role}, life: {life}\n'
                self.player_output[p_id] = await input_ai(
                    p_kind, p_text, text, skill_ids, targets, log
                )
                self.player_finished[p_id] = True
            elif p_controller == 'random':
                self.player_output[p_id] = {
                    'skill': random.choice(skill_ids),
                    'target': random.randrange(0, 10),
                    'speech': '',
                    'reason': '',
                }
                self.player_finished[p_id] = True
            else:
                while not self.player_finished[p_id]:
                    await asyncio.sleep(1)

            output = self.player_output[p_id]
            if await self.player_skill(
                p_id,
                skill_ids,
                output['skill'],
                output['target'],
                output['speech'],
            ):
                break

    async def player_skill(
        self,
        player_id: int,
        skill_ids: list[str],
        skill_id: str,
        target: int = 0,
        comment: str = '',
    ) -> bool:
        skill_ids.remove(skill_id)
        async with Database.get_conn() as conn:
            match skill_id:
                case 'vote':
                    await self.update_skill(player_id, skill_id, target)
                    await self.insert_log(
                        player_id, skill_id, 'private', target, comment
                    )
                case 'speak':
                    await self.insert_log(
                        player_id, skill_id, 'public', 0, comment
                    )
                case 'kill':
                    await self.update_skill(player_id, skill_id, target)
                    await self.insert_log(
                        player_id, skill_id, 'private', target, comment
                    )
                case 'identify':
                    await self.update_skill(player_id, skill_id, target)
                    await self.insert_log(
                        player_id, skill_id, 'private', target, comment
                    )
                case 'heal':
                    await self.update_skill(player_id, skill_id, target)
                    await self.insert_log(
                        player_id, skill_id, 'private', target, comment
                    )
                    return True   # TODO: use link
                case 'poison':
                    await self.update_skill(player_id, skill_id, target)
                    await self.insert_log(
                        player_id, skill_id, 'private', target, comment
                    )
                    return True
                case 'shoot':
                    pass
                case 'shield':
                    await self.update_skill(player_id, skill_id, target)
                    await self.insert_log(
                        player_id, skill_id, 'private', target, comment
                    )
                case _:
                    raise NotImplementedError
        return False

    async def verdict(self) -> None:
        skills = await self.select_skill_cycle()
        while skills:
            player_id, skill_id, target_id = skills.pop()
            match skill_id:
                case 'vote':
                    pass
                case 'speak':
                    pass
                case 'kill':
                    pass
                case 'identify':
                    pass
                case 'heal':
                    pass
                case 'poison':
                    pass
                case 'shoot':
                    pass
                case 'shield':
                    pass
                case _:
                    raise NotImplementedError

        SQL = """
        SELECT faction, COUNT(*) FROM attribute
        WHERE game_id = ?
        GROUP BY faction;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            factions = await Database.fetchall(cursor)

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
        UPDATE game SET
            cycle = CASE WHEN phase = 'night' THEN cycle + 1 ELSE cycle END,
            phase = CASE WHEN phase = 'night' THEN 'day' ELSE 'night' END
        WHERE id = ?
        RETURNING cycle, phase;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            fetch = await Database.fetchone(cursor)
            self.cycle, self.phase = fetch

    async def select_players(self, player_id: int) -> dict:
        SQL = """
        SELECT a.player_id, u.name, u.controller, u.kind, a.seat, a.role_id, a.life FROM attribute a
        JOIN user u ON u.id = a.player_id
        WHERE a.game_id = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            players = await Database.fetchall(cursor)

        # TODO: filter known info
        player_dict: dict[int, list] = {}
        for id_, *others in players:
            player_dict[id_] = others
        for id_, (*others, role, life) in player_dict.items():
            if role != player_dict[player_id][-2]:
                role = 'unknown'
                life = 'unknown'
                player_dict[id_] = [*others, role, life]
        return player_dict

    async def select_skill(self) -> list:
        SQL = """
        SELECT player_id, skill_id FROM player_skill WHERE game_id = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            return await Database.fetchall(cursor)

    async def update_skill(
        self, player_id: int, skill_id: str, target_id: int = 0
    ) -> None:
        SQL = """
        UPDATE player_skill SET target_id = ?, cycle = ?
        WHERE game_id = ? AND player_id = ? AND skill_id = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(
                SQL, (target_id, self.cycle, self.id, player_id, skill_id)
            )

    async def select_skill_cycle(self) -> list:
        SQL = """
        SELECT player_id, skill_id, target_id FROM player_skill
        WHERE game_id = ? AND cycle = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id, self.cycle))
            return await Database.fetchall(cursor)

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

    async def select_log(self, player_id: int) -> str:
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
        LEFT JOIN user up ON up.id = ps.player_id
        LEFT JOIN attribute ap ON ap.game_id = :gid AND ap.player_id = ps.player_id
        LEFT JOIN user ut ON ut.id = l.target_id
        LEFT JOIN attribute at ON at.game_id = :gid AND at.player_id = l.target_id
        WHERE ps.game_id = :gid {SQL_WHERE if player_id != 0 else ''};
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(
                SQL, {'gid': self.id, 'pid': player_id}
            )
            logs = await Database.fetchall(cursor)

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


class Games(collections.UserDict[int, Game]):
    def __init__(self, *args) -> None:
        super().__init__(*args)

    async def add_game(self) -> int:
        game = Game()
        game_id = await game.insert()
        self[game_id] = game
        return game_id

    async def add_ai(self) -> None:
        coros = [
            Database.insert_user(name, 'ai', 'deepseek_chat')
            for name in string.ascii_uppercase
        ]
        await asyncio.gather(*coros)


games = Games()


class User(BaseModel):
    name: str
    controller: str


class Player(BaseModel):
    name: str
    game_id: int


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.init_db()
    await games.add_ai()
    yield


app = FastAPI(lifespan=lifespan)


@app.post('/register')
async def register(user: User) -> responses.JSONResponse:
    id_ = await Database.insert_user(user.name, user.controller)
    if id_:
        return responses.JSONResponse(
            {'id': id_, 'message': 'Sign up successfully'},
            status.HTTP_201_CREATED,
        )
    return await login(user)


@app.post('/login')
async def login(user: User) -> responses.JSONResponse:
    id_, controller, _ = await Database.select_user(user.name)
    if not id_:
        return await register(user)
    if controller != user.controller:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'User exists')
    return responses.JSONResponse(
        {'id': id_, 'message': 'Sign in successfully'}, status.HTTP_200_OK
    )


def game_exist(game_id: int) -> None:
    if not games.get(game_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Game do not exists')


def game_start(game_id: int) -> None:
    game = games[game_id]
    if not game.started:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Game do not started')


def player_start(game_id: int, player_id: int) -> None:
    game = games[game_id]
    if not game.player_started[player_id]:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Action do not started')


@app.post('/games')
async def create() -> responses.JSONResponse:
    game_id = await games.add_game()
    return responses.JSONResponse(
        {'game_id': game_id, 'message': 'Game created'},
        status_code=status.HTTP_201_CREATED,
    )


@app.post('/games/{game_id}/players/{player_id}')
async def join(game_id: int, player_id: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    if player_id in game.player_ids:
        return responses.JSONResponse(
            'Rejoin game successfully', status_code=status.HTTP_200_OK
        )
    game.player_ids.append(player_id)
    return responses.JSONResponse(
        'Join game successfully', status_code=status.HTTP_200_OK
    )


@app.post('/games/{game_id}/start')
async def start_post(
    game_id: int, background_tasks: BackgroundTasks
) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    await game.init_db()
    background_tasks.add_task(game.loop)
    game.started = True
    return responses.JSONResponse(
        'Start game successfully', status_code=status.HTTP_200_OK
    )


@app.get('/games/{game_id}/start')
async def start_get(game_id: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    return responses.JSONResponse(game.started, status_code=status.HTTP_200_OK)


@app.get('/games/{game_id}/players/{player_id}/stats/player')
async def stats_player(game_id: int, player_id: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    if not game.started:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, 'NotImplemented')
    players = await game.select_players(player_id)
    return responses.JSONResponse(
        {'stats': players, 'message': 'Stats received'},
        status_code=status.HTTP_200_OK,
    )


@app.get('/games/{game_id}/players/{player_id}/stats/log')
async def stats_log(game_id: int, player_id: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    log = await game.select_log(player_id)
    return responses.JSONResponse(
        {'stats': log, 'message': 'Stats received'},
        status_code=status.HTTP_200_OK,
    )


@app.get('/games/{game_id}/players/{player_id}/stats/action')
async def stats_action_get(
    game_id: int, player_id: int
) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    player_start(game_id, player_id)
    cond = game.player_input[player_id]
    info = (
        f'Available skills: {cond["skill"]}\nValid targets: {cond["target"]}'
    )
    return responses.JSONResponse(
        {'stats': info, 'message': 'Stats received'},
        status_code=status.HTTP_200_OK,
    )


@app.post('/games/{game_id}/players/{player_id}/stats/action')
async def stats_action_post(
    game_id: int, player_id: int, json_format: JsonFormat
) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    player_start(game_id, player_id)
    cond = game.player_input[player_id]
    if (
        json_format.skill not in cond['skill']
        or json_format.target not in cond['target']
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid action')
    game.player_output[player_id] = json_format.model_dump()
    game.player_finished[player_id] = True
    game.player_started[player_id] = False
    return responses.JSONResponse(
        'Action sent',
        status_code=status.HTTP_201_CREATED,
    )


if __name__ == '__main__':
    uvicorn.run(app)
