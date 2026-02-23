# Discord MyAnimeList Bot

## Project Overview
A comprehensive Discord bot integration for MyAnimeList (MAL) that allows users to seamlessly browse anime information, manage lists, and engage in interactive anime-related mini-games directly within Discord. Built using `discord.py` and the MAL API v2, it features modern slash command interactions, paginated views, and dynamic UI components.

## Features

### Search & Browse
- **`/search <query>`** - Search MyAnimeList for anime by title with instant results and detailed information
- **`/anime <id>`** - Fetch comprehensive details including synopsis, rating, genres, studios, and related anime
- **`/seasonal <year> <season>`** - Explore anime released in a specific season with pagination
- **`/list <username> [sorting_method] [status]`** - View any user's anime list with optional status filtering

### Interactive Games
- **Guess the Rating** - `/guessgame [difficulty] [limit] [ranking_type]` then `/guess <guess_value>`
  - Guess anime ratings within margin (easy - 0.5; medium - 0.25; hard - 0.1)
  - Customizable anime pool size (1-2500)
  - Customizable ranking type to change what is in the pool

- **Higher or Lower** - `/higherlower [limit] [ranking_type]`
  - Predict if the next anime's rating is higher or lower
  - Interactive button-based gameplay
  - Customizable anime pool size (1-2500)
  - Customizable ranking type to change what is in the pool

### Configuration Options
- **Ranking Types**: popularity (default), airing, movie, favorite
- **Seasons**: winter, spring, summer, fall
- **List Statuses**: watching, completed, on hold, dropped, plan to watch

## Installation

### Prerequisites
- Python 3.8+
- Discord.py 2.3+
- A Discord bot token
- MyAnimeList API client ID

### How to setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd discord-anime-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** in the root directory
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   CLIENT_ID=your_mal_client_id_here
   ```

4. **Get your credentials**
   - Discord Bot Token: Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
   - MyAnimeList Client ID: Register your app at [MyAnimeList API](https://myanimelist.net/apiconfig/references/api/v2)

5. **Run the bot**
   ```bash
   python app.py
   ```

## Usage

Once the bot is running and invited to your server, use slash commands:

### Quick Examples
```
/search Demon Slayer
/anime 5114
/list MyUsername score completed
/seasonal 2024 spring
/guessgame easy 200 airing
/guess 8.5
/higherlower 100 favorite
/help
/help guessgame
```

### Adding the Bot to Your Server

Generate an invite link with these permissions:
- Send Messages
- Manage Messages
- Add Reactions
- Read Message History
- Embed Links

## Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `search` | `/search <query>` | Search for anime by title |
| `anime` | `/anime <anime_id>` | Get detailed anime information |
| `list` | `/list <username> [sorting_method] [status]` | View a user's anime list |
| `seasonal` | `/seasonal <year> <season>` | Browse seasonal anime |
| `guessgame` | `/guessgame [difficulty] [limit] [ranking_type]` | Start guess the rating game |
| `guess` | `/guess <guess_value>` | Submit a guess |
| `higherlower` | `/higherlower [limit] [ranking_type]` | Start higher or lower game |
| `help` | `/help [command]` | View help information |

## Changelog
See [CHANGELOG.md](CHANGELOG.md) for a full history of changes.

## Architecture

### State Management
- **In-memory session storage** - Game sessions stored per user ID
- `user_guess_sessions` - Tracks guess game progress
- `user_higher_lower_sessions` - Tracks higher/lower game progress
- Sessions cleared on game end or bot restart

### API Integration
- MyAnimeList API v2 for all data fetching
- Pagination support for large datasets (up to 2500 anime per game)
- Efficient batch requests with offset pagination

### UI Components
- **SearchView** - Dropdown menu for selecting from search results
- **PaginationView** - Buttons for browsing paginated lists
- **HigherLowerView** - Interactive game buttons (Higher/Lower)

## Dependencies

- `discord.py` - Discord bot framework
- `requests` - HTTP requests for MyAnimeList API
- `python-dotenv` - Environment variable management

## Configuration

Edit the top of `app.py` to adjust:
- `DEBUG_LEVEL` - Set to 1 for debug output, 0 to disable
- `BASE_URL` - MyAnimeList API endpoint (default: v2)

## Error Handling

The bot handles:
- Invalid command arguments with helpful error messages
- API failures gracefully (returns None or error message)
- Missing or invalid user lists
- Expired game sessions
- Button interactions from non-authorized users

## Limitations

- Game sessions reset on bot restart
- Search limited to 10 initial results (more info with dropdown)
- Pagination maxes out at 10 items per page
- MyAnimeList API rate limits apply

## Future Improvements

- **Rate limit handling (implement rate limiting to prevent abuse, retry with backoff, queueing, etc)**. This is important if the bot receives too many requests too quickly.
- Persistent session storage (database integration)
- User statistics and leaderboards
- Advanced anime recommendation features

## Troubleshooting

**Bot won't start**
- Verify `DISCORD_TOKEN` and `CLIENT_ID` in `.env`
- Check Python version (3.8+)
- Ensure all dependencies installed: `pip install -r requirements.txt`

**Commands not working**
- Verify bot has Message Content Intent enabled in Developer Portal (required for some legacy features, though slash commands use Interactions)
- Check bot has send message permissions in the channel
- Ensure you are using slash commands (`/`) and the bot's commands appear in the Discord UI

**API errors**
- Verify MyAnimeList Client ID is valid
- Check rate limits aren't being exceeded
- Confirm anime IDs/usernames exist on MAL


---
**Uses [MyAnimeList](https://myanimelist.net/) API** | Made by Lance S