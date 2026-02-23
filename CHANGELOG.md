# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-23

### Added
- **Slash Command Support**: Migrated all legacy prefix commands (`!`) to Discord Slash Commands (`/`) using `discord.app_commands`.
- **Parameter Descriptions**: Added user-friendly hints for all command parameters using `@app_commands.describe`.
- **Global Error Handling**: Implemented `@bot.tree.error` to handle app command errors, including cooldowns and general execution failures.
- **Enhanced Search**: Added a dropdown menu (`SearchView`) to search results for selecting and viewing detailed anime information.
- **Improved Pagination**: Refactored `PaginationView` for better navigation through user lists and seasonal anime.
- **Project Overview**: Added a comprehensive project overview and architecture section to `README.md`.

### Changed
- **Command Syntax**: Updated all help text and internal references to use `/` instead of `!`.
- **Interaction Model**: Replaced `commands.Context` with `discord.Interaction` across all commands and UI components.
- **Response Methods**: Updated bot responses to use `interaction.response.send_message`, `interaction.response.defer`, and `interaction.followup.send`.
- **View Logic**: Updated `HigherLowerView` and `PaginationView` to be fully compatible with interaction-based callbacks.

### Removed
- Legacy prefix command system (the bot no longer responds to `!` commands).

## [1.0.0] - 2024-05-15

### Added
- **Search Command**: Ability to search MyAnimeList for anime by title.
- **Anime Command**: Detailed information for specific anime by ID.
- **List Command**: View user anime lists with status filtering.
- **Seasonal Command**: Browse anime by year and season.
- **Guess The Rating Game**: Interactive mini-game to guess anime scores.
- **Higher or Lower Game**: Mini-game to predict relative ratings.
- **Help System**: Built-in help command for all available features.
- **MAL API Integration**: Integration with MyAnimeList API v2.
