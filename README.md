# The Werewolves of Miller's Hollow

This project is a simulation of the social deduction game **The Werewolves of Miller's Hollow**, where AI agents representing villagers, werewolves, seers and more to interact, make decisions, and vote to eliminate each other based on hidden roles and social reasoning.

## Overview

This simulation uses language model agents to emulate human-like reasoning and deception in the werewolf game. Each AI "player" is assigned a role and makes decisions using natural language prompts. The game progresses through alternating day and night cycles until one faction wins at last.

## Features

The game includes:
- 🤖 **Generative AI Agents**: Utilize large language models for human-like reasoning, deception, and dynamic role-playing.
- 🗃️ **Database Integration**: Store game states, player roles, and action history using SQLite databases.
- 🌐 **Client-Server Architecture**: App-based frontend (QT) + backend (FastAPI) for multiplayer interactions.
- 👥 **Human-AI Hybrid Play**: Humans join via apps to collaborate/compete with AI agents in real-time.
- 🔧 **Configurable Rules**: Customize role setup, win conditions and detailed rules through the ini file.

## Deploy

### With source code

First, edit the ini file `config.ini` in the root directory.
```ini
[database]
names = Alice | ...

[server]

[client]
ORIGIN = http://localhost:8000
model = model
models = model | ...

[game]
role_setup = villager | ...

[ai]
api_key = api_key
base_url = base_url
language = language
```

Then, run the server file `server.py` inside `server/`.

Last, run the client file `client.py` inside `client/`.
