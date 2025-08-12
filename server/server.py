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

import ai


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
    async def get_cursor(sql: str, para: tuple = ()) -> AsyncGenerator[aiosqlite.Cursor, None]:
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
    async def fetchall(cursor: aiosqlite.Cursor) -> list[tuple]:
        fetches = await cursor.fetchall()
        if fetches is None:
            return []
        return [tuple(fetch) for fetch in fetches]

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
        date INTEGER DEFAULT 1,
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
        PRIMARY KEY (game_id, player_id));
        ---
        CREATE TABLE IF NOT EXISTS player_skill (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link_id INTEGER DEFAULT 0,
        game_id INTEGER NOT NULL,
        seat INTEGER NOT NULL,
        skill_id TEXT NOT NULL,
        quantity REAL DEFAULT 1,
        UNIQUE (game_id, seat, skill_id));
        ---
        CREATE TABLE IF NOT EXISTS log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ps_id INTEGER NOT NULL,
        cycle INTEGER NOT NULL,
        type TEXT NOT NULL,
        target INTEGER DEFAULT 0,
        speech TEXT DEFAULT '',
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
        INSERT OR IGNORE INTO skill (id, link_id, link_type, description) VALUES
        ('vote', '', '', 'During the day phase, all players vote publicly to eliminate one player from the game.'),
        ('speak', '', '', 'During the day phase, players take turns speaking publicly to discuss suspicions, share information, and debate who to eliminate.'),
        ('kill', '', '', 'At night, the Werewolves secretly select one player to eliminate. If consensus cannot be reached, the option with the highest number of votes will be selected, or a random choice will be made among the candidates with the highest votes.'),
        ('team_chat', '', '', 'At night, the Werewolves privately to decide whom to kill, which role to impersonate, and communicate to formulate strategies. Other roles cannot see these messages. After selecting a target to kill, you cannot discuss with your teammates anymore, so avoid deciding before everyone agrees.'),
        ('identify', '', '', 'At night, the Seer targets one player to secretly learn their faction (werewolf or human).'),
        ('heal', 'poison', 'constraint', 'At night, the Witch knows who was killed by the werewolf and decides whether to use a one-time antidote to heal that player. Cannot self-heal except for the first night. If the Witch choose to heal, then she cannot poison.'),
        ('poison', 'heal', 'constraint', 'At night, the Witch uses a one-time poison potion to secretly eliminate any player. The targeted player will not be able to use any other special skills. If the Witch choose to poison, then she cannot heal. If a player is both guarded by the Guard and healed by the Witch on the same night, the protections nullify each other, and the player still dies.'),
        ('shoot', '', '', 'When the Hunter is eliminated (day or night), he immediately shoot and kill one other player as a final revenge.'),
        ('shield', '', '', 'At night, the Guard chooses a player to protect. Cannot protect the same player consecutively. If a player is both guarded by the Guard and healed by the Witch on the same night, the protections nullify each other, and the player still dies.');
        ---
        INSERT OR IGNORE INTO role_skill (role_id, skill_id) VALUES
        ('villager', 'vote'),
        ('villager', 'speak'),
        ('werewolf', 'vote'),
        ('werewolf', 'speak'),
        ('werewolf', 'kill'),
        ('werewolf', 'team_chat'),
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
        self.date = 1
        self.cycle = 1
        self.phase = 'night'
        self.id = 0
        self.system_seat = 0
        self.users: list[int] = []
        self.started = False
        self.ended = False
        self.player_num = 0
        self.seats: list[int] = []
        self.user_seat: dict[int, int] = {}
        self.skill_info: dict[str, str] = {}
        self.player_started: dict[int, bool] = {}
        self.player_finished: dict[int, bool] = {}
        self.player_input: dict[int, ai.GuiInput] = {}
        self.player_output: dict[int, ai.GuiOutput] = {}

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
        SQL = """
        SELECT id FROM user WHERE controller = 'ai';
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL)
            ais = await Database.fetchall(cursor)
        ai_ids = [ai_id for (ai_id,) in ais if ai_id not in self.users]

        role_setup = [role.strip() for role in ai.config.get('game', 'role_setup').split('|')]
        self.player_num = len(role_setup)

        role_count = dict(collections.Counter(role_setup))
        role_text = ', '.join(f'{value} {key}' for key, value in role_count.items())

        self.seats = list(range(1, self.player_num + 1))
        ai_num = len(role_setup) - len(self.users)
        if ai_num < 0:
            raise ValueError('Too many user')
        elif ai_num > len(ai_ids):
            raise ValueError('Not enough user')
        ai_ids = random.sample(ai_ids, ai_num)
        for ai_id in ai_ids:
            self.users.append(ai_id)

        SQL = """
        INSERT INTO attribute (game_id, player_id, seat, role_id, faction) VALUES
        (?1, ?2, ?3, ?4, (SELECT faction FROM role WHERE id = ?4));
        """
        random.shuffle(role_setup)
        random.shuffle(self.users)
        async with Database.get_conn() as conn:
            for player_id, seat, role_id in zip(self.users, self.seats, role_setup):
                self.user_seat[player_id] = seat
                await conn.execute(SQL, (self.id, player_id, seat, role_id))

        SQL = """
        INSERT OR IGNORE INTO player_skill (game_id, seat, skill_id) VALUES
        (?, 0, 'speak');
        """   # TODO: find Moderator, set system_seat
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (self.id,))

        SQL = """
        INSERT INTO player_skill (game_id, seat, skill_id)
        SELECT a.game_id, a.seat, rs.skill_id FROM attribute a
        JOIN role_skill rs ON rs.role_id = a.role_id
        WHERE a.game_id = ?
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (self.id,))

        SQL = """
        UPDATE player_skill AS ps1 SET link_id =
        ps2.id FROM skill s, player_skill ps2
        WHERE ps1.game_id = ? AND s.id = ps1.skill_id
        AND ps2.game_id = ps1.game_id AND ps2.seat = ps1.seat
        AND ps2.skill_id = s.link_id;
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (self.id,))

        SQL = """
        SELECT id, description FROM skill;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL)
            skill_info = await Database.fetchall(cursor)
        self.skill_info = {skill_id: des for skill_id, des in skill_info}

        await self.system_speak(f'Game begin. Game settings: {role_text}')

    async def loops(self) -> None:
        for seat in self.seats:
            self.player_started[seat] = False
            self.player_finished[seat] = False
        self.started = True

        while not self.ended:
            await self.loop()

    async def loop(self) -> None:
        await self.system_speak(f"It's {self.phase} {self.date}.")
        skill_seq = {
            'night': {
                'vote': 0,
                'speak': 0,
                'kill': 1,
                'team_chat': 1,
                'identify': 1,
                'heal': 2,
                'poison': 2,
                'shoot': 0,
                'shield': 1,
            },
            'day': {
                'vote': 2,
                'speak': 1,
                'kill': 0,
                'team_chat': 0,
                'identify': 0,
                'heal': 0,
                'poison': 0,
                'shoot': 0,
                'shield': 0,
            },
        }
        skill_dict = await self.set_skill_dict(skill_seq)
        skill_dict = await self.set_sheriff_dict(skill_dict)
        death_seats = await self.loop_action(skill_dict)

        if death_seats:
            await self.system_speak(f'Seat {death_seats} was dead.')
        else:
            await self.system_speak(f'No one was dead.')

        if self.ended:
            return
        await self.update_time(phase=False)
        await self.loop_dying(death_seats)
        await self.update_time(cycle=False)

    async def loop_dying(self, death_seats: list[int]) -> None:
        if not death_seats:
            return
        skill_seq = {
            'night': {
                'vote': 0,
                'speak': 1,
                'kill': 0,
                'team_chat': 0,
                'identify': 0,
                'heal': 0,
                'poison': 0,
                'shoot': 1,
                'shield': 0,
            },
            'day': {
                'vote': 0,
                'speak': 1,
                'kill': 0,
                'team_chat': 0,
                'identify': 0,
                'heal': 0,
                'poison': 0,
                'shoot': 1,
                'shield': 0,
            },
        }
        if self.date > 1:
            skill_seq['night']['speak'] = 0

        skill_dict = await self.set_skill_dict(
            skill_seq, force_quantity=None, force_life=False, force_seats=death_seats
        )
        death_seats = await self.loop_action(skill_dict)
        if self.ended:
            return
        await self.update_time(phase=False)
        await self.loop_dying(death_seats)

    async def set_skill_dict(
        self,
        skill_seq: dict[str, dict[str, int]],
        force_quantity: bool | None = True,
        force_life: bool | None = True,
        force_seats: list[int] | None = None,
    ) -> dict[int, dict[int, list[str]]]:
        skill_dict: dict[int, dict[int, list[str]]] = {}
        skills = await self.s_ps_player()
        for seat, skill_id in skills:
            if seat == 0:
                continue
            (quantity,) = await self.s_ps_quantity(seat, skill_id)
            if force_quantity is not None and bool(quantity) != force_quantity:
                continue
            (life,) = await self.s_a_life(seat)
            if force_life is not None and life != force_life:
                continue
            if force_seats is not None and seat not in force_seats:
                continue

            seq = skill_seq[self.phase][skill_id]
            skill_dict.setdefault(seq, {})
            skill_dict[seq].setdefault(seat, [])
            skill_dict[seq][seat].append(skill_id)
        skill_dict.pop(0, [])
        return dict(sorted(skill_dict.items()))

    async def set_sheriff_dict(
        self,
        skill_dict: dict[int, dict[int, list[str]]],
    ):
        sheriff_seq = self.seats
        new_dict: dict[int, dict[int, list[str]]] = {}
        new_seq = 0
        for seq, d in skill_dict.items():
            new_seq += 1
            if not any('speak' in skills for seat, skills in d.items()):
                new_dict[new_seq] = d
                continue
            for seat in sheriff_seq:
                new_seq += 1
                if seat not in d.keys():
                    continue
                new_dict[new_seq] = {seat: d[seat]}
        return new_dict

    async def loop_action(self, skill_dict: dict[int, dict[int, list[str]]]) -> list[int]:
        for seq, value in skill_dict.items():
            coros = [self.player(seat, skill_ids) for seat, skill_ids in value.items()]
            await asyncio.gather(*coros)

        deaths = await self.verdict()
        death_seats = list(deaths.keys())
        return death_seats

    async def player(self, p_seat: int, skill_ids: list[str]) -> None:
        p_info = await self.s_a_player(p_seat)
        p_name, p_controller, p_kind, p_role, p_faction, p_life = p_info[p_seat]
        p_text = f'\tYou are {p_name}, a {p_role} in seat {p_seat}.'
        players_text = '\n'.join(
            f'\tname: {name}, seat: {seat}, role: {role}, faction: {faction}, life: {life}'
            for seat, (name, *others, role, faction, life) in p_info.items()
        )
        targets: list[int] = []
        for seat, (name, *others, role, faction, life) in p_info.items():
            if life:
                targets.append(seat)
        targets.append(0)
        targets.sort()

        while skill_ids:
            skills = {
                skill: ai.GuiInSkill(targets=targets, description=self.skill_info[skill])
                for skill in skill_ids
            }
            await self.pre_action(p_seat, skill_ids, skills)
            log = await self.select_log(p_seat)
            input_ = ai.GuiInput(
                model=p_kind, me=p_text, players=players_text, skills=skills, log=log
            )
            self.player_input[p_seat] = input_
            self.player_started[p_seat] = True
            self.player_finished[p_seat] = False
            if p_controller == 'ai':
                try:
                    self.player_output[p_seat] = await ai.input_ai(input_)
                except Exception as e:
                    print(f'Error: {e}')
                    p_controller = 'random'
                    continue
                self.player_finished[p_seat] = True
                self.player_started[p_seat] = False
            elif p_controller == 'random':
                self.player_output[p_seat] = ai.GuiOutput(
                    skill=random.choice(skill_ids),
                    target=random.choice(targets),
                    speech='',
                    reason='',
                )
                self.player_finished[p_seat] = True
                self.player_started[p_seat] = False
            else:
                while not self.player_finished[p_seat]:
                    await asyncio.sleep(1)

            output = self.player_output[p_seat]

            result = await self.action(
                p_seat, output.skill, output.target, output.speech, output.reason
            )
            if result is None:
                skill_ids.remove(output.skill)
            elif result:
                break

    async def pre_action(
        self, seat: int, skill_ids: list[str], skills: dict[str, ai.GuiInSkill]
    ) -> None:
        if 'heal' in skill_ids:
            # targets = skills['heal'].targets
            deaths = await self.verdict(predict=True)
            kill_seats: list[int] = []
            for key, value in deaths.items():
                if 'kill' in value:
                    kill_seats.append(key)
            if not kill_seats:
                await self.system_speak(f'No one was killed.', seat)
                skills.pop('heal')
            else:
                kill_seat = kill_seats[0]
                await self.system_speak(f'Seat {kill_seat} was killed.', seat)
                if kill_seat == seat and self.date != 1:
                    skills.pop('heal')
                else:
                    skills['heal'].targets = [kill_seat]
        if 'shoot' in skill_ids:
            await self.system_speak(f'Seat {seat} is a hunter!')
        if 'shield' in skill_ids:
            SQL = """
            SELECT l.cycle, l.target FROM log l
            JOIN player_skill ps ON ps.id = l.ps_id
            WHERE ps.game_id = ? AND ps.seat = ? AND ps.skill_id = ? AND l.cycle = ?;
            """
            async with Database.get_conn() as conn:
                cursor = await conn.execute(SQL, (self.id, seat, 'shield', self.cycle - 1))
                shielded = await Database.fetchall(cursor)
            if shielded:
                last_shielded = max(shielded)[1]
                if last_shielded in skills['shield'].targets:
                    skills['shield'].targets.remove(last_shielded)

    async def action(
        self,
        seat: int,
        skill_id: str,
        target_seat: int = 0,
        speech: str = '',
        comment: str = '',
    ) -> bool | None:
        async def seer(target_seat: int) -> None:
            if target_seat == 0:
                return
            (faction,) = await self.s_a_faction(target_seat)
            if faction != 'werewolf':
                faction = 'good'
            await self.system_speak(f'Seat {target_seat} is {faction}.', seat)

        skill_log = functools.partial(
            self.insert_log, seat, skill_id, target=target_seat, speech=speech, comment=comment
        )
        match skill_id:
            case 'vote':
                await skill_log('private')
            case 'speak':
                await skill_log('public')
            case 'kill':
                await skill_log('private')
                return True
            case 'team_chat':
                await skill_log('team')
                return False
            case 'identify':
                await skill_log('private')
                await seer(target_seat)
            case 'heal' | 'poison':
                await skill_log('private')
                if target_seat != 0:
                    await self.u_ps_quantity(seat, skill_id)
                return True   # TODO: use link
            case 'shoot':
                (quantity,) = await self.s_ps_quantity(seat, skill_id)
                if not quantity:
                    return None
                await skill_log('public')
            case 'shield':
                await skill_log('private')
            case _:
                raise NotImplementedError
        return None

    async def verdict(self, predict: bool = False) -> dict[int, list[str]]:
        def vote(skills: list[tuple], skill: str) -> tuple[list[tuple], list[int], str]:
            filtered_skills: list[tuple] = []
            votes: dict[int, list[int]] = {}
            for seat, skill_id, target_seat in skills:
                if skill_id != skill:
                    filtered_skills.append((seat, skill_id, target_seat))
                    continue
                votes.setdefault(target_seat, [])
                votes[target_seat].append(seat)
            for vote in votes:
                votes[vote].sort()
            votes = dict(sorted(votes.items()))
            waivers = votes.pop(0, [])
            waiver_text = ', '.join(map(str, waivers))
            waiver_text = f'{waiver_text} -> abstain' if waiver_text else ''
            vote_list = [f"{', '.join(map(str, v))} -> {k}" for k, v in votes.items()]
            vote_text = '; '.join(vote_list + ([waiver_text] if waiver_text else []))
            max_vote = max(len(v) for v in votes.values()) if votes else 0
            elect = [k for k, v in votes.items() if len(v) == max_vote]
            return filtered_skills, elect, vote_text

        async def poison(target_seat: int):
            SQL = """
            UPDATE player_skill SET quantity = 0
            WHERE game_id = ? AND seat = ?;
            """
            async with Database.get_conn() as conn:
                await conn.execute(SQL, (self.id, target_seat))

        deaths: dict[int, list[str]] = {}
        skills = await self.s_log_cycle()

        werewolves = []
        for seat, skill_id, target_seat in skills:
            if skill_id == 'kill':
                werewolves.append(seat)

        skills, vote_elect, vote_text = vote(skills, 'vote')
        elect_id = vote_elect[0] if vote_elect else 0
        if elect_id:
            deaths.setdefault(elect_id, [])
            deaths[elect_id].append('vote')

        skills, kill_elect, kill_text = vote(skills, 'kill')
        kill_id = kill_elect[0] if kill_elect else 0
        if kill_id:
            deaths.setdefault(kill_id, [])
            deaths[kill_id].append('kill')

        for seat, skill_id, target_seat in skills:
            if target_seat == 0:
                continue
            match skill_id:
                case 'speak' | 'team_chat' | 'identify' | 'vote' | 'kill':
                    pass
                case 'heal':
                    deaths.setdefault(target_seat, [])
                    deaths[target_seat].append('heal')
                case 'poison':
                    deaths.setdefault(target_seat, [])
                    deaths[target_seat].append('poison')
                    await poison(target_seat)
                case 'shoot':
                    deaths.setdefault(target_seat, [])
                    deaths[target_seat].append('shoot')
                case 'shield':
                    deaths.setdefault(target_seat, [])
                    deaths[target_seat].append('shield')
                case _:
                    raise NotImplementedError
        deaths.pop(0, [])

        if predict:
            return deaths

        if elect_id:
            await self.system_speak(f'Vote result: {vote_text}')
        for werewolf in werewolves:
            if kill_id:
                await self.system_speak(
                    f'Seat {kill_id} was killed, vote result: {kill_text}', werewolf
                )
            else:
                await self.system_speak(f'No one was killed, vote result: {kill_text}', werewolf)

        for key, value in deaths.items():
            if 'heal' in value and 'shield' in value:
                value.remove('heal')
                value.remove('shield')
            if 'heal' in value and 'kill' in value:
                value.remove('heal')
                value.remove('kill')
            if 'shield' in value and 'kill' in value:
                value.remove('shield')
                value.remove('kill')
            if 'heal' in value:
                value.remove('heal')
            if 'shield' in value:
                value.remove('shield')
            if not value:
                continue
            await self.u_a_life(key)
        deaths = {key: value for key, value in deaths.items() if value}

        factions = await self.s_a_factions()
        f_dict = {faction: count for faction, count in factions}
        f_keys = f_dict.keys()

        winner = ''
        if 'werewolf' not in f_keys:
            winner = 'human'
        if 'human' not in f_keys or 'god' not in f_keys:
            winner = 'werewolf'   # override
        print(f_dict)
        if winner:
            self.ended = True
            await self.system_speak(f'Winner: {winner}.')

        return deaths

    async def update_time(self, cycle: bool = True, phase: bool = True) -> None:
        if cycle:
            self.cycle += 1
        if phase:
            if self.phase == 'night':
                self.phase = 'day'
                self.date += 1
            elif self.phase == 'day':
                self.phase = 'night'

        SQL = """
        UPDATE game SET cycle = ?, date = ?, phase = ?
        WHERE id = ?
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (self.cycle, self.date, self.phase, self.id))

    async def system_speak(self, speech: str, target: int = 0) -> None:
        if target == 0:
            type_ = 'public'
        else:
            type_ = 'private'
        await self.insert_log(self.system_seat, 'speak', type_, target, speech)

    async def s_a_factions(self) -> list[tuple]:
        SQL = """
        SELECT faction, COUNT(*) FROM attribute
        WHERE game_id = ? AND life = TRUE
        GROUP BY faction;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            return await Database.fetchall(cursor)

    async def s_a_faction(self, seat: int) -> tuple:
        SQL = """
        SELECT faction FROM attribute
        WHERE game_id = ? AND seat = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id, seat))
            return await Database.fetchone(cursor)

    async def s_a_life(self, seat: int) -> tuple:
        SQL = """
        SELECT life FROM attribute
        WHERE game_id = ? AND seat = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id, seat))
            return await Database.fetchone(cursor)

    async def u_a_life(self, seat: int) -> None:
        SQL = """
        UPDATE attribute SET life = FALSE
        WHERE game_id = ? AND seat = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (self.id, seat))

    async def s_a_player(self, p_seat: int) -> dict[int, list]:
        SQL = """
        SELECT a.seat, u.name, u.controller, u.kind, a.role_id, a.faction, a.life
        FROM attribute a
        JOIN user u ON u.id = a.player_id
        WHERE a.game_id = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            players = await Database.fetchall(cursor)

        # TODO: filter known info, role/faction/side
        player_dict: dict[int, list] = {}
        for seat, *others in players:
            player_dict[seat] = others
        for seat, (*others, role, faction, life) in player_dict.items():
            targets = [target for target, in await self.s_l_skill(seat, 'identify')]
            if not (
                seat == p_seat or role == player_dict[p_seat][-2] == 'werewolf' or seat in targets
            ):
                role = 'unknown'
                faction = 'unknown'
            if seat in targets and faction != 'werewolf':
                faction = 'good'
            player_dict[seat] = [*others, role, faction, life]
        return player_dict

    async def s_l_skill(self, seat: int, skill_id: str) -> list[tuple]:
        SQL = """
        SELECT target FROM log WHERE ps_id = (
            SELECT id FROM player_skill
            WHERE game_id = ? AND seat = ? AND skill_id = ?
        );
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id, seat, skill_id))
            return await Database.fetchall(cursor)

    async def s_ps_player(self) -> list[tuple]:
        SQL = """
        SELECT seat, skill_id FROM player_skill WHERE game_id = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id,))
            return await Database.fetchall(cursor)

    async def s_ps_quantity(self, seat: int, skill_id: str) -> tuple:
        SQL = """
        SELECT quantity FROM player_skill
        WHERE game_id = ? AND seat = ? AND skill_id = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id, seat, skill_id))
            return await Database.fetchone(cursor)

    async def u_ps_quantity(self, seat: int, skill_id: str, add: int = -1) -> None:
        SQL = """
        UPDATE player_skill SET quantity = quantity + ?
        WHERE game_id = ? AND seat = ? AND skill_id = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(SQL, (add, self.id, seat, skill_id))

    async def s_log_cycle(self) -> list[tuple]:
        SQL = """
        SELECT ps.seat, ps.skill_id, l.target FROM log l
        JOIN player_skill ps ON ps.id = l.ps_id
        WHERE game_id = ? AND cycle = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id, self.cycle))
            return await Database.fetchall(cursor)

    async def insert_log(
        self,
        seat: int,
        skill_id: str,
        type_: str,
        target: int = 0,
        speech: str = '',
        comment: str = '',
    ) -> None:
        SQL = """
        INSERT INTO log (ps_id, cycle, type, target, speech, comment)
        SELECT ps.id, ?, ?, ?, ?, ? FROM player_skill ps
        WHERE ps.game_id = ? AND ps.seat = ? AND ps.skill_id = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(
                SQL, (self.cycle, type_, target, speech, comment, self.id, seat, skill_id)
            )

    async def select_log(self, seat: int) -> str:
        SQL = f"""
        SELECT up.name, ps.seat, ps.skill_id, ut.name, l.target, l.speech
        FROM log l
        JOIN player_skill ps ON ps.id = l.ps_id
        LEFT JOIN attribute ap ON ap.game_id = :gid AND ap.seat = ps.seat
        LEFT JOIN user up ON up.id = ap.player_id
        LEFT JOIN attribute at ON at.game_id = :gid AND at.seat = l.target
        LEFT JOIN user ut ON ut.id = at.player_id
        WHERE ps.game_id = :gid AND (
            :seat = :sys
            OR ps.seat = :seat
            OR l.type = 'public'
            OR ps.seat = :sys AND l.target = :seat
            OR l.type = 'team' AND ap.role_id = (
                SELECT a.role_id FROM attribute a
                WHERE a.game_id = :gid AND a.seat = :seat
            )
        );
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(
                SQL, {'gid': self.id, 'seat': seat, 'sys': self.system_seat}
            )
            logs = await Database.fetchall(cursor)

        text = ''
        for (
            player_name,
            player_seat,
            skill_id,
            target_name,
            target_seat,
            speech,
        ) in logs:
            if player_seat == 0:
                text += f'[system] {speech}\n'
            elif skill_id in ['speak', 'team_chat']:
                text += f'{player_name}({player_seat}) said: {speech}\n'
            else:
                text += f'{player_name}({player_seat}) {skill_id} {target_name}({target_seat}).\n'
        return text.rstrip()


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
            Database.insert_user(name, 'ai', 'deepseek-chat') for name in string.ascii_uppercase
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
    id_ = await Database.insert_user(user.name, user.controller, 'deepseek-chat')   # TODO
    if id_:
        return responses.JSONResponse(
            {'id': id_, 'message': 'Sign up successfully'}, status.HTTP_201_CREATED
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


def player_start(game_id: int, seat: int) -> None:
    game = games[game_id]
    if not game.player_started[seat]:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Action do not started')


@app.post('/games')
async def create() -> responses.JSONResponse:
    game_id = await games.add_game()
    return responses.JSONResponse(
        {'game_id': game_id, 'message': 'Game created'}, status.HTTP_201_CREATED
    )


@app.post('/games/{game_id}/users/{user_id}')
async def join(game_id: int, user_id: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    if user_id in game.users:
        return responses.JSONResponse('Rejoin game successfully', status.HTTP_200_OK)
    game.users.append(user_id)
    return responses.JSONResponse('Join game successfully', status.HTTP_200_OK)


@app.post('/games/{game_id}/users/{user_id}/start')
async def start_post(
    game_id: int, user_id: int, background_tasks: BackgroundTasks
) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    await game.init_db()
    seat = game.user_seat[user_id]
    background_tasks.add_task(game.loops)
    return responses.JSONResponse(
        {'seat': seat, 'message': 'Start game successfully'}, status.HTTP_200_OK
    )


@app.get('/games/{game_id}/users/{user_id}/start')
async def start_get(game_id: int, user_id: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    seat = game.user_seat[user_id]
    return responses.JSONResponse(seat, status.HTTP_200_OK)


@app.get('/games/{game_id}/seats/{seat}/stats/player')
async def stats_player(game_id: int, seat: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    if not game.started:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, 'NotImplemented')
    players = await game.s_a_player(seat)
    return responses.JSONResponse(
        {'stats': players, 'message': 'Stats received'},
        status.HTTP_200_OK,
    )


@app.get('/games/{game_id}/seats/{seat}/stats/log')
async def stats_log(game_id: int, seat: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    log = await game.select_log(seat)
    return responses.JSONResponse({'stats': log, 'message': 'Stats received'}, status.HTTP_200_OK)


@app.get('/games/{game_id}/seats/{seat}/stats/action')
async def stats_action_get(game_id: int, seat: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    player_start(game_id, seat)

    info = f'Available skills:\n{ai.skill_text(game.player_input[seat])}'
    skills = list(game.player_input[seat].skills.keys())
    return responses.JSONResponse(
        {'stats': info, 'skills': skills, 'message': 'Stats received'}, status.HTTP_200_OK
    )


@app.post('/games/{game_id}/seats/{seat}/stats/action')
async def stats_action_post(
    game_id: int, seat: int, gui_output: ai.GuiOutput
) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    player_start(game_id, seat)
    skills = game.player_input[seat]
    try:
        ai.logic(gui_output, skills)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    game.player_output[seat] = gui_output
    game.player_finished[seat] = True
    game.player_started[seat] = False
    return responses.JSONResponse('Action sent', status.HTTP_201_CREATED)


if __name__ == '__main__':
    uvicorn.run(app)
