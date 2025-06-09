# The Werewolves of Miller's Hollow

This project is a simulation of the social deduction game **The Werewolves of Miller's Hollow**, where AI agents representing villagers, werewolves, seers and more to interact, make decisions, and vote to eliminate each other based on hidden roles and social reasoning.

## Overview

This simulation uses language model agents to emulate human-like reasoning and deception in the werewolf game. Each AI "player" is assigned a role and makes decisions using natural language prompts. The game progresses through alternating day and night cycles until one faction wins at last.

## Features

The game includes:
- 💬 **Natural Language Reasoning**: Each AI agent generates in-character reasoning and dialogue.
- 🐺 **Hidden Roles**: Villagers, werewolves, seers and more following different objectives.
- 🎭 **Deception & Deduction**: Werewolves work together to survive, while villagers attempt to identify them.
- ✅ **Victory Conditions**: The game ends when one faction achieves its winning condition.
- 📉 **Game State Tracking**: Logs keep track of every information: time, dialogues, and game statistics.
- 📜 **Structured Logs**: Improved output formatting for debugging and game analysis.

## Deploy

Add a file called `user_data.py` inside `src/`.
```python
from .header import Char
DEBUG: bool = user_data.DEBUG
api_key: str = user_data.api_key
base_url: str = user_data.base_url
win_condition: Literal[
   'all', 'partial'
] = user_data.win_condition   # type: ignore[assignment]
allow_exposure: bool = user_data.allow_exposure
election_round: int = user_data.election_round
language: str = user_data.language
additional_prompt: str = user_data.additional_prompt
chars: list[Char] = user_data.chars
```
Replace user_data.* with your data.
