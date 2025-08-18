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


from ..common.config import config
from ..common import io
from .ai import input_ai


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
        audience TEXT NOT NULL,
        type TEXT NOT NULL,
        speech TEXT DEFAULT '',
        seat INTEGER DEFAULT 0,
        word TEXT DEFAULT '',
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
    names = [name.strip() for name in config.get('database', 'names').split('|')]
    models = [model.strip() for model in config.get('client', 'models').split('|')]

    @classmethod
    async def add_ai(cls) -> int:
        name = random.choice(cls.names)
        model = random.choice(cls.models)
        return await Database.insert_user(name, 'ai', model)

    def __init__(self) -> None:
        self.id = 0
        self.users: list[int] = []
        self.player_num = 0
        self.system_seat = 0
        self.seats: list[int] = []
        self.user_seat: dict[int, int] = {}
        self.skill_info: dict[str, str] = {}

        self.started = False
        self.ended = False
        self.cycle = 1
        self.date = 1
        self.phase = 'night'

        self.player_started: dict[int, bool] = {}
        self.player_finished: dict[int, bool] = {}
        self.player_input: dict[int, io.InputSkill] = {}
        self.player_output: dict[int, io.OutputSkill] = {}

        self.vote_elect: list[int] = []

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
        SELECT id, kind FROM user WHERE controller = 'ai';
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL)
            ais = await Database.fetchall(cursor)
        ai_ids = [
            id_ for (id_, kind) in ais if id_ not in self.users and kind in self.models
        ]

        role_setup = [
            role.strip() for role in config.get('game', 'role_setup').split('|')
        ]
        self.player_num = len(role_setup)

        role_count = dict(collections.Counter(role_setup))
        role_text = ', '.join(f'{value} {key}' for key, value in role_count.items())

        self.seats = list(range(1, self.player_num + 1))
        ai_num = len(role_setup) - len(self.users)
        if ai_num < 0:
            raise ValueError('Too many user')
        while ai_num > len(ai_ids):
            id_ = await self.add_ai()
            if not id_:
                continue
            ai_ids.append(id_)

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
            'vote': 0,
            'speak': 0,
            'kill': 1,
            'team_chat': 1,
            'identify': 1,
            'heal': 2,
            'poison': 2,
            'shoot': 0,
            'shield': 1,
        }
        night_actions = await self.set_skill_dict(skill_seq)

        if self.date != 1:
            death_seats = await self.loop_action(night_actions)
            if self.ended:
                return
            await self.update_time(phase=False)
            await self.loop_dying(death_seats)
            await self.update_time(cycle=False)
        else:
            await self.update_time()

        await self.system_speak(f"It's {self.phase} {self.date}.")

        skill_seq = {
            'vote': 2,
            'speak': 1,
            'kill': 0,
            'team_chat': 0,
            'identify': 0,
            'heal': 0,
            'poison': 0,
            'shoot': 0,
            'shield': 0,
        }
        force_seats = await self.loop_sheriff()

        if self.date == 2:
            death_seats = await self.loop_action(night_actions)
            if self.ended:
                return
            await self.update_time(phase=False)
            await self.loop_dying(death_seats)

        day_actions = await self.set_skill_dict(
            skill_seq, force_seats=force_seats, force_skills=['speak']
        )

        death_seats = await self.loop_action(day_actions)
        if len(self.vote_elect) > 1:
            await self.update_time(phase=False)
            day_actions = await self.set_skill_dict(
                skill_seq, force_seats=force_seats, force_skills=['speak']
            )
            death_seats = await self.loop_action(day_actions)
        if self.ended:
            return
        await self.update_time(phase=False)
        await self.loop_dying(death_seats)
        await self.update_time(cycle=False)

    async def loop_dying(self, death_seats: list[int]) -> None:
        if not death_seats:
            return
        skill_seq = {
            'vote': 0,
            'speak': 1,
            'kill': 0,
            'team_chat': 0,
            'identify': 0,
            'heal': 0,
            'poison': 0,
            'shoot': 1,
            'shield': 0,
        }
        if self.date > 1 and self.phase == 'night':
            skill_seq['speak'] = 0

        dying_actions = await self.set_skill_dict(
            skill_seq, force_quantity=None, force_life=False, force_seats=death_seats
        )
        death_seats = await self.loop_action(dying_actions, silent=True)
        if self.ended:
            return
        await self.update_time(phase=False)
        await self.loop_dying(death_seats)

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

    async def set_skill_dict(
        self,
        skill_seq: dict[str, int],
        force_life: bool | None = True,
        force_quantity: bool | None = True,
        force_seats: list[int] | None = None,
        force_skills: list[str] = [],
    ) -> dict[int, dict[int, list[str]]]:
        skill_dict: dict[int, dict[int, list[str]]] = {}
        player_skills = await self.s_ps_player()
        for seat, skill_id in player_skills:
            if seat == self.system_seat:
                continue
            if not (seq := skill_seq[skill_id]):
                continue
            (life,) = await self.s_a_life(seat)
            if force_life is not None and life != force_life:
                continue
            (quantity,) = await self.s_ps_quantity(seat, skill_id)
            if force_quantity is not None and bool(quantity) != force_quantity:
                continue
            if force_seats is not None and seat not in force_seats:
                continue
            skill_dict.setdefault(seq, {})
            skill_dict[seq].setdefault(seat, [])
            skill_dict[seq][seat].append(skill_id)
        skill_dict = dict(sorted(skill_dict.items()))

        if not force_skills:
            return skill_dict
        if force_seats is None:
            raise ValueError('Wrong parameter')
        seq_dict = {}
        seq = 1
        for k, v in skill_dict.items():
            if not all(
                all(skill in force_skills for skill in skills) for skills in v.values()
            ):
                seq_dict[seq] = v
                seq += 1
                continue
            for seat in force_seats:
                if not (skills := v.get(seat)):
                    continue
                seq_dict[seq] = {seat: skills}
                seq += 1

        return seq_dict

    async def loop_sheriff(self) -> list[int]:
        return self.seats   # TODO: sheriff

    async def loop_action(
        self, skill_dict: dict[int, dict[int, list[str]]], silent=False
    ) -> list[int]:
        for seq, value in skill_dict.items():
            coros = [self.player(seat, skill_ids) for seat, skill_ids in value.items()]
            await asyncio.gather(*coros)

        deaths = await self.verdict()
        death_seats = list(deaths.keys())
        death_seats.sort()
        if not silent:
            if death_seats:
                await self.system_speak(f'Seat {death_seats} was dead.')
            elif self.vote_elect:
                await self.system_speak(f"It's a tie.")
            else:
                await self.system_speak(f'No one was dead.')
        return death_seats

    async def player(self, p_seat: int, skill_ids: list[str]) -> None:
        p_info = await self.s_a_player(p_seat)
        p_name, p_controller, p_kind, p_role, p_faction, p_life = p_info[p_seat]
        p_text = f'\tYou are {p_name}, a {p_role} in seat {p_seat}.'
        players_text = '\n'.join(
            f'\tname: {name}, seat: {seat}, role: {role}, faction: {faction}, life: {life}'
            for seat, (name, *others, role, faction, life) in p_info.items()
        )
        options: list[int] = []
        for seat, (name, *others, role, faction, life) in p_info.items():
            if life:
                options.append(seat)
        options.append(0)
        options.sort()

        deaths = await self.verdict(predict=True)
        if 'speak' in skill_ids and self.vote_elect:
            if p_seat not in self.vote_elect:
                skill_ids.remove('speak')
        if 'heal' in skill_ids:
            kill_seats = [key for key, value in deaths.items() if 'kill' in value]
            if not kill_seats:
                await self.system_speak(f'No one was killed.', p_seat)
                skill_ids.remove('heal')
            await self.system_speak(f'Seat {kill_seats} was killed.', p_seat)
            if p_seat in kill_seats and self.date != 1:
                kill_seats.remove(p_seat)
                if not kill_seats:
                    skill_ids.remove('heal')
        if 'shoot' in skill_ids:
            await self.system_speak(f'Seat {p_seat} is a hunter!')

        while skill_ids:
            skills: list[io.SkillType] = []
            for skill in skill_ids:
                match skill:
                    case 'vote':
                        if self.vote_elect:
                            options = [0] + self.vote_elect
                    case 'heal':
                        options = [
                            key for key, value in deaths.items() if 'kill' in value
                        ]
                    case 'shield':
                        SQL = """
                        SELECT l.cycle, l.seat FROM log l
                        JOIN player_skill ps ON ps.id = l.ps_id
                        WHERE ps.game_id = ? AND ps.seat = ? AND ps.skill_id = ? AND l.cycle = ?;
                        """
                        async with Database.get_conn() as conn:
                            cursor = await conn.execute(
                                SQL, (self.id, p_seat, 'shield', self.cycle - 1)
                            )
                            shielded = await Database.fetchall(cursor)
                        if shielded:
                            last_shielded = max(shielded)[1]
                            options = [
                                option for option in options if option != last_shielded
                            ]
                match skill:
                    case 'speak' | 'team_chat':
                        skills.append(
                            io.InputDialogue(
                                type='dialogue',
                                name=skill,
                                description=self.skill_info[skill],
                            )
                        )
                    case 'vote' | 'kill' | 'identify' | 'heal' | 'poison' | 'shoot' | 'shield':
                        skills.append(
                            io.InputSeat(
                                type='seat',
                                name=skill,
                                description=self.skill_info[skill],
                                options=options,
                            )
                        )
                    case _:
                        skills.append(
                            io.InputWord(
                                type='word',
                                name=skill,
                                description=self.skill_info[skill],
                                options=[],
                            )
                        )

            log = await self.select_log(p_seat)
            input_ = io.get_input(
                model=p_kind, player=p_text, players=players_text, log=log, skills=skills
            )
            self.player_input[p_seat] = input_
            self.player_started[p_seat] = True
            self.player_finished[p_seat] = False
            if p_controller == 'ai':
                try:
                    self.player_output[p_seat] = await input_ai(input_)
                except Exception as e:
                    print(f'Error: {e}')
                    p_controller = 'random'
                    continue
                self.player_finished[p_seat] = True
                self.player_started[p_seat] = False
            elif p_controller == 'random':
                skills_map = {s.name: s for s in input_.skills}
                skill = random.choice(skill_ids)
                input_skill = skills_map[skill]
                action: io.ActionType   # TODO: type
                if isinstance(input_skill, io.InputDialogue):
                    action = io.OutputDialogue(
                        type='dialogue', reason='', name=skill, dialogue=''
                    )
                elif isinstance(input_skill, io.InputSeat):
                    seat = random.choice(input_skill.options)
                    action = io.OutputSeat(type='seat', reason='', name=skill, seat=seat)
                elif isinstance(input_skill, io.InputWord):
                    word = random.choice(input_skill.options)
                    action = io.OutputWord(type='word', reason='', name=skill, word=word)
                else:
                    raise RuntimeError('Wrong IO type')
                self.player_output[p_seat] = io.OutputSkill(root=action)
                self.player_finished[p_seat] = True
                self.player_started[p_seat] = False
            else:
                while not self.player_finished[p_seat]:
                    await asyncio.sleep(1)

            output = self.player_output[p_seat]

            result = await self.action(p_seat, output)
            if result is None:
                skill_ids.remove(output.root.name)
            elif result:
                break

    async def action(self, p_seat: int, output: io.OutputSkill) -> bool | None:
        output_skill = output.root
        skill_id = output_skill.name
        insert_log = functools.partial(
            self.insert_log, p_seat, skill_id, comment=output_skill.reason
        )
        if isinstance(output_skill, io.OutputDialogue):
            dialogue = output_skill.dialogue
            insert_log = functools.partial(insert_log, type_='dialogue', speech=dialogue)
            match skill_id:
                case 'speak':
                    await insert_log('public')
                case 'team_chat':
                    await insert_log('team')
                    return False
                case _:
                    raise NotImplementedError
        elif isinstance(output_skill, io.OutputSeat):
            seat = output_skill.seat
            insert_log = functools.partial(insert_log, type_='seat', seat=seat)
            match skill_id:
                case 'vote':
                    await insert_log('private')
                case 'kill':
                    await insert_log('private')
                    return True
                case 'identify':
                    await insert_log('private')
                    if seat == 0:
                        return None
                    (faction,) = await self.s_a_faction(seat)
                    if faction != 'werewolf':
                        faction = 'good'
                    await self.system_speak(f'Seat {seat} is {faction}.', p_seat)
                case 'heal' | 'poison':
                    await insert_log('private')
                    if seat != 0:
                        await self.u_ps_quantity(p_seat, skill_id)
                    return True   # TODO: use link
                case 'shoot':
                    (quantity,) = await self.s_ps_quantity(p_seat, skill_id)
                    if not quantity:
                        return None
                    await insert_log('public')
                case 'shield':
                    await insert_log('private')
                case _:
                    raise NotImplementedError
        elif isinstance(output_skill, io.OutputWord):
            word = output_skill.word
            insert_log = functools.partial(insert_log, type_='word', word=word)
            match skill_id:
                case _:
                    raise NotImplementedError
        else:
            raise RuntimeError('Wrong IO type')

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
        if len(vote_elect) == 1:
            elect_id = vote_elect[0]
            deaths.setdefault(elect_id, [])
            deaths[elect_id].append('vote')

        skills, kill_elect, kill_text = vote(skills, 'kill')
        kill_id = random.choice(kill_elect) if kill_elect else 0
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

        if len(vote_elect) > 1:
            self.vote_elect = vote_elect
        else:
            self.vote_elect = []

        if vote_text:
            await self.system_speak(f'Vote result: {vote_text}')
        for werewolf in werewolves:
            if kill_id:
                await self.system_speak(
                    f'Your team choose seat {kill_id}, vote result: {kill_text}',
                    werewolf,
                )
            else:
                await self.system_speak(
                    f'Your team choose no one, vote result: {kill_text}', werewolf
                )

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

    def vote(
        self, skills: list[tuple], skill: str
    ) -> tuple[list[tuple], list[int], str]:
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

    async def system_speak(self, speech: str, seat: int = 0) -> None:
        if seat == 0:
            audience = 'public'
        else:
            audience = 'private'
        await self.insert_log(
            self.system_seat, 'speak', audience, 'dialogue', speech, seat
        )

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
            if not self.ended and not (
                seat == p_seat
                or role == player_dict[p_seat][-2] == 'werewolf'
                or seat in targets
            ):
                role = 'unknown'
                faction = 'unknown'
            if seat in targets and faction != 'werewolf':
                faction = 'good'
            player_dict[seat] = [*others, role, faction, life]
        return player_dict

    async def s_l_skill(self, seat: int, skill_id: str) -> list[tuple]:
        SQL = """
        SELECT seat FROM log WHERE ps_id = (
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
        SELECT ps.seat, ps.skill_id, l.seat FROM log l
        JOIN player_skill ps ON ps.id = l.ps_id
        WHERE game_id = ? AND cycle = ?;
        """
        async with Database.get_conn() as conn:
            cursor = await conn.execute(SQL, (self.id, self.cycle))
            return await Database.fetchall(cursor)

    async def insert_log(
        self,
        p_seat: int,
        skill_id: str,
        audience: str,
        type_: str,
        speech: str = '',
        seat: int = 0,
        word: str = '',
        comment: str = '',
    ) -> None:
        SQL = """
        INSERT INTO log (ps_id, cycle, audience, type, speech, seat, word, comment)
        SELECT ps.id, ?, ?, ?, ?, ?, ?, ? FROM player_skill ps
        WHERE ps.game_id = ? AND ps.seat = ? AND ps.skill_id = ?;
        """
        async with Database.get_conn() as conn:
            await conn.execute(
                SQL,
                (
                    self.cycle,
                    audience,
                    type_,
                    speech,
                    seat,
                    word,
                    comment,
                    self.id,
                    p_seat,
                    skill_id,
                ),
            )

    async def select_log(self, seat: int) -> str:
        SQL = f"""
        SELECT l.audience, up.name, ps.seat, ps.skill_id, l.type, l.speech, ut.name, l.seat, l.word
        FROM log l
        JOIN player_skill ps ON ps.id = l.ps_id
        LEFT JOIN attribute ap ON ap.game_id = :gid AND ap.seat = ps.seat
        LEFT JOIN user up ON up.id = ap.player_id
        LEFT JOIN attribute at ON at.game_id = :gid AND at.seat = l.seat
        LEFT JOIN user ut ON ut.id = at.player_id
        WHERE ps.game_id = :gid AND (
            :seat = :sys
            OR ps.seat = :seat
            OR l.audience = 'public'
            OR ps.seat = :sys AND l.seat = :seat
            OR l.audience = 'team' AND ap.role_id = (
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
            audience,
            player_name,
            player_seat,
            skill_id,
            type_,
            speech,
            seat,
            seat_name,
            word,
        ) in logs:
            match type_:
                case 'dialogue':
                    if player_seat == 0:
                        text += f'[{audience}] Moderator: {speech}\n'
                        continue
                    text += f'[{audience}] {player_name}({player_seat}) said: {speech}\n'
                case 'seat':
                    text += f'[{audience}] {player_name}({player_seat}) {skill_id} {seat_name}({seat}).\n'
                case 'word':
                    text += f'[{audience}] {player_name}({player_seat}) choose {word}.\n'
        return text.rstrip()


class Games(collections.UserDict[int, Game]):
    def __init__(self, *args) -> None:
        super().__init__(*args)

    async def add_game(self) -> int:
        game = Game()
        game_id = await game.insert()
        self[game_id] = game
        return game_id
