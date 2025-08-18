import contextlib

from fastapi import FastAPI, BackgroundTasks, HTTPException, responses, status
from pydantic import BaseModel
import uvicorn

from ..common.config import config
from ..common import io
from .game import Database, Games

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
    yield


app = FastAPI(lifespan=lifespan)


@app.post('/register')
async def register(user: User) -> responses.JSONResponse:
    id_ = await Database.insert_user(
        user.name, user.controller, config.get('client', 'model')
    )
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
        raise HTTPException(status.HTTP_409_CONFLICT, 'Action has not started')


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
    if game.started:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Game started')
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
        {'stats': players, 'message': 'Stats received'}, status.HTTP_200_OK
    )


@app.get('/games/{game_id}/seats/{seat}/stats/log')
async def stats_log(game_id: int, seat: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    log = await game.select_log(seat)
    return responses.JSONResponse(
        {'stats': log, 'message': 'Stats received'}, status.HTTP_200_OK
    )


@app.get('/games/{game_id}/seats/{seat}/stats/action')
async def stats_action_get(game_id: int, seat: int) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    player_start(game_id, seat)

    return responses.JSONResponse(
        {
            'stats': game.player_input[seat].model_dump_json(),
            'message': 'Stats received',
        },
        status.HTTP_200_OK,
    )


@app.post('/games/{game_id}/seats/{seat}/stats/action')
async def stats_action_post(
    game_id: int, seat: int, gui_output: io.OutputSkill
) -> responses.JSONResponse:
    game_exist(game_id)
    game = games[game_id]
    game_start(game_id)
    player_start(game_id, seat)
    try:
        io.IOValidator(input_=game.player_input[seat], output=gui_output)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    game.player_output[seat] = gui_output
    game.player_finished[seat] = True
    game.player_started[seat] = False
    return responses.JSONResponse('Action sent', status.HTTP_201_CREATED)


def run_server() -> None:
    uvicorn.run(app, host='0.0.0.0')


if __name__ == '__main__':
    run_server()
