import requests
import discord
import os
import random
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from typing import Optional

load_dotenv()

# ===== CONFIGURATION =====

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
BASE_URL = "https://api.myanimelist.net/v2"
DEBUG_LEVEL = 1

# ===== BOT SETUP =====

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ===== STATE MANAGEMENT =====
# Stores active game sessions in memory; cleared on game end or bot restart

# Maps user_id -> {current_anime, anime_pool, score, difficulty}
user_guess_sessions = {}

# Maps user_id -> {current_anime, next_anime, score, anime_pool}
user_higher_lower_sessions = {}

# ===== UTILITY FUNCTIONS =====


def debug(message: str):
    """Print debug output if DEBUG_LEVEL is enabled."""

    if DEBUG_LEVEL == 1:
        print(f"{message}")


def _mal_headers():
    """Return MyAnimeList API headers with client ID."""

    headers = {"X-MAL-Client-ID": CLIENT_ID, "Accept": "application/json"}
    return headers


# ===== API CALLS =====


def search_anime(query, limit=10):
    """Search the MyAnimeList anime endpoint by title.

    Returns the parsed JSON response if the request succeeds (HTTP 200),
    otherwise returns None.
    """

    params = {
        "q": query,
        "limit": limit,
        "offset": 0,
        "fields": "id,title,main_picture,synopsis,start_date,alternative_titles",
    }
    resp = requests.get(f"{BASE_URL}/anime", params=params, headers=_mal_headers())
    return resp.json() if resp.status_code == 200 else None


def get_anime(anime_id):
    """Fetch detailed information for a single anime."""

    params = {
        "fields": (
            "synopsis,pictures,rating,status,genres,related_anime,studios,"
            "num_episodes,mean,rank,start_date,end_date,alternative_titles"
        )
    }

    resp = requests.get(
        f"{BASE_URL}/anime/{anime_id}", params=params, headers=_mal_headers()
    )

    return resp.json() if resp.status_code == 200 else None


def get_user_anime_list(username, status=None, limit=100, offset=0):
    """Get a user's anime list with optional status filter"""

    params = {
        "limit": limit,
        "offset": offset,
        "fields": "list_status,synopsis,pictures,alternative_titles",
    }
    if status:
        params["status"] = status
    resp = requests.get(
        f"{BASE_URL}/users/{username}/animelist", params=params, headers=_mal_headers()
    )
    return resp.json() if resp.status_code == 200 else None


def get_top_anime_by_rank(limit=500, ranking_type="bypopularity", offset=0):
    """Get top anime by ranking"""

    params = {
        "ranking_type": ranking_type,
        "limit": min(limit, 500),
        "offset": offset,
        "fields": "rank,mean,pictures,alternative_titles",
        "sort": "ranking_asc",
    }
    resp = requests.get(
        f"{BASE_URL}/anime/ranking", params=params, headers=_mal_headers()
    )
    return resp.json() if resp.status_code == 200 else None


def get_seasonal_anime(year, season, limit=500, sort="anime_num_list_users", offset=0):
    """Get anime for a specific season"""

    params = {
        "limit": min(limit, 500),
        "offset": offset,
        "fields": "rank,mean,pictures,alternative_titles",
        "sort": sort,
    }
    resp = requests.get(
        f"{BASE_URL}/anime/season/{year}/{season}",
        params=params,
        headers=_mal_headers(),
    )
    return resp.json() if resp.status_code == 200 else None


# ===== FORMATTING/PARSING =====


def parse_search_results(search_data):
    """Clean up messy API search results into simple dictionaries"""

    if not search_data or "data" not in search_data:
        return []

    results = []
    for item in search_data["data"]:
        node = item.get("node", {})
        start_date = node.get("start_date", "Unknown")

        # Extract year from start_date or default to "Unknown"
        year = (
            start_date.split("-")[0]
            if start_date and start_date != "Unknown"
            else "Unknown"
        )

        results.append(
            {
                "id": node.get("id"),
                "title": node.get("title"),
                "alternative_titles": node.get("alternative_titles", {}),
                "picture": node.get("main_picture", {}).get("medium"),
                "synopsis": node.get("synopsis", "No description available"),
                "year": year,
            }
        )
    return results


def format_anime_embed(anime_data):
    """Format anime data for Discord embed"""

    if not anime_data:
        return None

    anime_id = anime_data.get("id")
    start_date = anime_data.get("start_date", "Unknown")
    end_date = anime_data.get("end_date", "Unknown")

    # Construct aired date range
    if start_date and start_date != "Unknown":
        aired = start_date
        if end_date and end_date != "Unknown":
            aired = f"{start_date} to {end_date}"
    else:
        aired = "Unknown"

    # Format genres
    genres = anime_data.get("genres", [])
    genres_str = ", ".join(g["name"] for g in genres) if genres else "N/A"

    # Format studios
    studios = anime_data.get("studios", [])
    studios_str = ", ".join(s["name"] for s in studios) if studios else "N/A"

    # Format related anime
    MAX_FIELD_LEN = 1024
    FOOTER_TEXT = "…more related anime available on the MyAnimeList page."

    related = anime_data.get("related_anime", [])
    lines = []

    for r in related:
        line = (
            f"[{r['node']['title']}](https://myanimelist.net/anime/{r['node']['id']}) "
            f"({r['relation_type'].replace('_', ' ').title()}, ID: {r['node']['id']})"
        )

        # +1 for newline
        projected_length = sum(len(l) + 1 for l in lines) + len(line)

        # Leave space for footer text if needed
        if projected_length + len(FOOTER_TEXT) > MAX_FIELD_LEN:
            lines.append(FOOTER_TEXT)
            break

        lines.append(line)

    related_str = "\n".join(lines) if lines else "None"

    return {
        "title": anime_data.get("title"),
        "description": anime_data.get("synopsis", "No description available")[:2048],
        "image_url": anime_data.get("main_picture", {}).get("large"),
        "rating": anime_data.get("mean", "N/A"),
        "episodes": anime_data.get("num_episodes", "?"),
        "status": anime_data.get("status", "Unknown").replace("_", " "),
        "aired": aired,
        "url": f"https://myanimelist.net/anime/{anime_id}" if anime_id else "N/A",
        "id": anime_id,
        "genres": genres_str,
        "related_anime": related_str,
        "studios": studios_str,
    }


def get_anime_title_with_alternative(anime_data):
    """Get anime title with English alternative title if available"""

    title = anime_data.get("title", "Unknown")

    # Try to get English alternative title
    alternative_titles = anime_data.get("alternative_titles", {})
    en_title = alternative_titles.get("en")

    if en_title and en_title != title:  # Only show if it exists and is different
        return f"{en_title}\n({title})"

    return title


# ===== DISCORD UI CLASSES =====


class PaginationView(discord.ui.View):
    """Build and return a Discord embed for the current page of paginated anime data."""

    def __init__(
        self, data, title, user_id, profile_url=None, is_ranking=False, timeout=300
    ):
        super().__init__(timeout=timeout)
        self.data = data
        self.title = title
        self.user_id = user_id
        self.profile_url = profile_url
        self.is_ranking = is_ranking
        self.current_page = 0
        self.per_page = 10
        self.total_pages = (len(data) + self.per_page - 1) // self.per_page
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.prev_five_button.disabled = self.current_page == 0
        self.next_five_button.disabled = self.current_page >= self.total_pages - 1
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def get_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]

        embed = discord.Embed(
            title=self.title,
            color=discord.Color.purple(),
        )

        description = ""
        if self.profile_url:
            description += f"[View profile on MAL]({self.profile_url})\n\n"
        description += f"Page {self.current_page + 1}/{self.total_pages}"
        embed.description = description

        for item in page_data:
            node = item.get("node", {})
            title = get_anime_title_with_alternative(node)
            anime_id = node.get("id", "N/A")
            mal_url = (
                f"https://myanimelist.net/anime/{anime_id}"
                if anime_id != "N/A"
                else "N/A"
            )

            if self.is_ranking:
                # For ranking/seasonal data (rank is in the node)
                rank = node.get("rank", "N/A")
                score = node.get("mean", "N/A")
                embed.add_field(
                    name=f"{title}\n(ID: {anime_id})",
                    value=f"[View on MAL]({mal_url})\nRank: {rank} | Score: {score}",
                    inline=False,
                )
            else:
                # For user list data
                list_status = item.get("list_status", {})
                embed.add_field(
                    name=f"{title}\n(ID: {anime_id})",
                    value=f"[View on MAL]({mal_url})\nScore: {list_status.get('score', 0)}/10 | Status: {list_status.get('status')}",
                    inline=False,
                )

        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.blurple)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()

        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏮ -5 Pages", style=discord.ButtonStyle.grey)
    async def prev_five_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return

        if self.current_page > 0:
            self.current_page = max(0, self.current_page - 5)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="+5 Pages ⏭", style=discord.ButtonStyle.grey)
    async def next_five_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return

        if self.current_page < self.total_pages - 1:
            self.current_page = min(self.total_pages - 1, self.current_page + 5)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()

        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()


class SearchView(discord.ui.View):
    """Handle dropdown selection and display detailed anime information for the chosen result."""

    def __init__(self, user, results, timeout=300):
        super().__init__(timeout=timeout)
        self.results = results
        self.user = user

        # Create options for the select menu
        options = []
        for i, anime in enumerate(results):
            title = anime["title"]
            en_title = anime["alternative_titles"].get("en")
            if en_title and en_title != title:
                label = f"{en_title}\n({title})"[:100]
            else:
                label = title[:100]
            options.append(discord.SelectOption(label=label, value=str(i)))

        # Add the select menu
        select = discord.ui.Select(
            placeholder="Select an anime to view details...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.defer()
            return

        index = int(interaction.data["values"][0])
        anime_id = self.results[index]["id"]
        anime_data = get_anime(anime_id)
        embed_data = format_anime_embed(anime_data)

        if not embed_data:
            await interaction.response.send_message("Anime not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=get_anime_title_with_alternative(anime_data),
            description=embed_data["description"],
            color=discord.Color.green(),
        )
        embed.set_image(url=embed_data["image_url"])
        embed.add_field(name="Rating", value=embed_data["rating"], inline=True)
        embed.add_field(name="Episodes", value=embed_data["episodes"], inline=True)
        embed.add_field(name="Status", value=embed_data["status"], inline=True)
        embed.add_field(name="Aired", value=embed_data["aired"], inline=True)
        embed.add_field(name="Genres", value=embed_data["genres"], inline=False)
        embed.add_field(
            name="Related Anime:", value=embed_data["related_anime"], inline=False
        )
        embed.add_field(name="Studios", value=embed_data["studios"], inline=False)
        embed.add_field(name="ID", value=embed_data["id"], inline=False)
        embed.add_field(
            name="MyAnimeList",
            value=f"[View on MAL]({embed_data['url']})",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)


class HigherLowerView(discord.ui.View):
    """Initialize the higher/lower game button view for a specific user session."""

    def __init__(self, user_id, message=None, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.message = message

    @discord.ui.button(label="📈 Higher", style=discord.ButtonStyle.green)
    async def higher_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        await interaction.response.defer()
        await _process_higher_lower_guess("higher", interaction, self.message)
        self.stop()

    @discord.ui.button(label="📉 Lower", style=discord.ButtonStyle.red)
    async def lower_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.defer()
            return
        await interaction.response.defer()
        await _process_higher_lower_guess("lower", interaction, self.message)
        self.stop()


# ===== COMMANDS - SEARCH & BROWSE =====


@app_commands.describe(query="Anime title to search for")
@bot.tree.command(name="search", description="Search MyAnimeList for anime by title")
async def search(interaction: discord.Interaction, query: Optional[str] = None):
    """Search MyAnimeList for anime by title and display selectable search results."""

    if query == None:
        await interaction.response.send_message("Missing search query. Use `/help search` for more info.", ephemeral=True)
        return

    query = str(query).strip()
    results_data = search_anime(query, limit=10)
    results = parse_search_results(results_data)

    if not results:
        await interaction.response.send_message("No anime found.")
        return

    embed = discord.Embed(
        title=f"Search results for '{query}'", color=discord.Color.blue()
    )
    for i, anime in enumerate(results, 1):
        title_display = anime["title"]
        en_title = anime["alternative_titles"].get("en")
        if en_title and en_title != anime["title"]:
            title_display = f"{en_title} ({anime['title']})"

        embed.add_field(
            name=f"{i}. {title_display}\n(ID: {anime['id']})",
            value=f"{anime['synopsis'][:200]}...",
            inline=False,
        )
    embed.set_footer(
        text="Use /anime <ID> to get more details or use the dropdown and select an anime"
    )

    view = SearchView(interaction.user, results)
    await interaction.response.send_message(embed=embed, view=view)  # Include dropdown for detailed view


@app_commands.describe(anime_id="MyAnimeList anime ID")
@bot.tree.command(name="anime", description="Get detailed information for an anime by ID")
async def anime(interaction: discord.Interaction, anime_id: int):
    """Fetch and display detailed information for a single anime by its MyAnimeList ID."""

    if anime_id is None:
        await interaction.response.send_message("Missing anime ID. Use `/help anime` for more info.")
        return

    try:
        anime_id = int(anime_id)
    except ValueError:
        await interaction.response.send_message(
            f'Invalid anime ID "{anime_id}". ID must be a number. Use `/help anime` for more info.'
        )
        return

    anime_data = get_anime(anime_id)
    embed_data = format_anime_embed(anime_data)

    if not embed_data:
        await interaction.response.send_message("Anime not found.")
        return

    embed = discord.Embed(
        title=get_anime_title_with_alternative(anime_data),
        description=embed_data["description"],
        color=discord.Color.green(),
    )
    embed.set_image(url=embed_data["image_url"])
    embed.add_field(name="Rating", value=embed_data["rating"], inline=True)
    embed.add_field(name="Episodes", value=embed_data["episodes"], inline=True)
    embed.add_field(name="Status", value=embed_data["status"], inline=True)
    embed.add_field(name="Aired", value=embed_data["aired"], inline=True)
    embed.add_field(name="Genres", value=embed_data["genres"], inline=False)
    embed.add_field(
        name="Related Anime:", value=embed_data["related_anime"], inline=False
    )
    embed.add_field(name="Studios", value=embed_data["studios"], inline=False)
    embed.add_field(name="ID", value=embed_data["id"], inline=False)
    embed.add_field(
        name="MyAnimeList", value=f"[View on MAL]({embed_data['url']})", inline=False
    )
    await interaction.response.send_message(embed=embed)


@app_commands.describe(year="Year, e.g., 2024", season="Season: winter, spring, summer, fall")
@bot.tree.command(name="seasonal", description="View anime from a specific season")
async def seasonal(interaction: discord.Interaction, year: int, season: str):
    """Retrieve and paginate anime released in a specific year and season."""

    await interaction.response.defer()

    season = season.lower()

    valid_seasons = ["winter", "spring", "summer", "fall"]
    if season not in valid_seasons:
        await interaction.followup.send(
            f"Invalid season \"{season}\". Valid options: {', '.join(valid_seasons)}. Use `/help seasonal` for more info."
        )
        return

    all_anime = []
    offset = 0

    # Fetch all entries using offset pagination (max 500 per request)
    while True:
        response = get_seasonal_anime(year, season, limit=500, offset=offset)

        if not response or "data" not in response:
            break

        all_anime.extend(response["data"])

        # Stop if we got fewer than 500 (means we've reached the end)
        if len(response["data"]) < 500:
            break

        offset += 500

    if not all_anime:
        await interaction.followup.send(f"Could not fetch anime for {season.capitalize()} {year}.")
        return

    title = f"{season.capitalize()} {year} Anime"
    view = PaginationView(all_anime, title, interaction.user.id, is_ranking=True, timeout=300)
    embed = view.get_embed()
    await interaction.followup.send(embed=embed, view=view)


# ===== COMMANDS - LIST  =====


@app_commands.describe(username="MyAnimeList username", sorting_method="Sort: alphabetical or score", status="Filter status: watching, completed, on hold, dropped, plan to watch")
@bot.tree.command(name="list", description="View a user's anime list with pagination")
async def list(interaction: discord.Interaction, username: str, sorting_method: str = "alphabetical", status: Optional[str] = None):
    """Retrieve and paginate a user's MyAnimeList anime list, optionally filtered by status."""

    await interaction.response.defer()

    if sorting_method not in ["alphabetical", "score"]:
        await interaction.followup.send(
            f'Cannot sort by "{sorting_method}". Use `/help list` for more info.'
        )
        return

    valid_statuses = ["watching", "completed", "on hold", "dropped", "plan to watch"]
    if status is not None and status not in valid_statuses:
        await interaction.followup.send(
            f"Invalid status \"{status}\". Valid options: {', '.join(valid_statuses)}. Use `/help list` for more info."
        )
        return

    # Change on hold and plan to watch for the MAL API to recognize status params
    if status == "on hold":
        status = "on_hold"
    if status == "plan to watch":
        status = "plan_to_watch"

    user_id = interaction.user.id
    all_anime = []
    offset = 0

    # Fetch all entries using offset pagination (max 100 per request)
    while True:
        response = get_user_anime_list(
            username, status=status, limit=100, offset=offset
        )

        if not response or "data" not in response:
            break

        all_anime.extend(response["data"])

        # Stop if we got fewer than 100 (means we've reached the end)
        if len(response["data"]) < 100:
            break

        offset += 100

    if not all_anime:
        await interaction.followup.send("Could not fetch your list.")
        return

    if sorting_method == "score":
        all_anime = sorted(
            all_anime, key=lambda anime: anime["list_status"]["score"], reverse=True
        )

    profile_url = f"https://myanimelist.net/profile/{username}"
    title = f"{username}'s Anime List ({status or 'All'})"
    view = PaginationView(all_anime, title, user_id, profile_url, timeout=300)
    embed = view.get_embed()
    await interaction.followup.send(embed=embed, view=view)


# ===== COMMANDS - GAMES =====


@app_commands.describe(difficulty="Difficulty: easy, medium, or hard", limit="Anime pool size (1-2500)", ranking_type="Ranking type: bypopularity (default), airing, movie, favorite")
@bot.tree.command(name="guessgame", description="Start the guess-the-rating game")
async def guessgame(
    interaction: discord.Interaction,
    difficulty: str = "medium",
    limit: int = 500,
    ranking_type: str = "bypopularity",
):
    """Start the guess the rating game with optional pool size and ranking type"""

    await interaction.response.defer()

    user_id = interaction.user.id

    difficulty = difficulty.lower()
    difficulties = ["easy", "medium", "hard"]
    if difficulty not in difficulties:
        await interaction.followup.send(
            f"Invalid difficulty \"{difficulty}\". Valid options: {', '.join(difficulties)}. Use `/help guessgame` for more info."
        )
        return

    if limit < 1 or limit > 2500:
        await interaction.followup.send(
            "Limit must be a number between 1-2500. Use `/help guessgame` for more info."
        )
        return

    ranking_type = ranking_type.lower()
    if ranking_type == "popularity":
        ranking_type = "bypopularity"

    valid_types = ["bypopularity", "airing", "movie", "favorite"]
    if ranking_type not in valid_types:
        await interaction.followup.send(
            f"Invalid ranking type \"{ranking_type}\". Valid options: {', '.join(valid_types)}. Use `/help guessgame` for more info."
        )
        return

    all_anime = []
    offset = 0
    remaining = limit

    # Fetch anime in batches (API max: 500 per request)
    while remaining > 0:
        batch_limit = min(remaining, 500)
        response = get_top_anime_by_rank(
            limit=batch_limit, ranking_type=ranking_type, offset=offset
        )

        if not response or "data" not in response:
            break

        all_anime.extend(response["data"])

        # Stop if we got fewer than requested (means we've reached the end)
        if len(response["data"]) < batch_limit:
            break

        remaining -= batch_limit
        offset += batch_limit

    if not all_anime:
        await interaction.followup.send("Could not start game.")
        return

    # Remove from pool so same anime doesn't appear twice
    current_anime = all_anime.pop(random.randint(0, len(all_anime) - 1)).get("node", {})

    user_guess_sessions[user_id] = {
        "current_anime": current_anime,
        "anime_pool": all_anime,
        "score": 0,
        "difficulty": difficulty,
    }

    embed = discord.Embed(title="Guess The Rating Game", color=discord.Color.gold())
    embed.add_field(
        name="Anime",
        value=get_anime_title_with_alternative(current_anime),
        inline=False,
    )
    if current_anime.get("main_picture"):
        embed.set_image(url=current_anime["main_picture"]["medium"])

    margin = 0.25
    if difficulty == "easy":
        margin = 0.5
    if difficulty == "hard":
        margin = 0.1
    embed.add_field(
        name="Instructions",
        value=f"Guess the rating (0-10) within ±{margin} points!\nUse: /guess <number>",
        inline=False,
    )
    await interaction.followup.send(embed=embed)


@app_commands.describe(guess_value="Your rating guess (0-10)")
@bot.tree.command(name="guess", description="Submit your rating guess")
async def guess(interaction: discord.Interaction, guess_value: float):
    """Guess the anime rating. Usage: /guess 8.5"""

    user_id = interaction.user.id

    if user_id not in user_guess_sessions:
        await interaction.response.send_message("Start a game first with /guessgame")
        return

    if guess_value is None:
        await interaction.response.send_message("Missing rating value. Use `/help guess` for more info.")
        return

    try:
        guess_value = float(guess_value)
    except ValueError:
        await interaction.response.send_message(
            f'Invalid rating "{guess_value}". Rating must be a number between 0-10. Use `/help guess` for more info.'
        )
        return

    if guess_value < 0 or guess_value > 10:
        await interaction.response.send_message(
            "Rating must be between 0 and 10. Use `/help guess` for more info."
        )
        return

    session = user_guess_sessions[user_id]
    current_anime = session["current_anime"]
    actual_rating = current_anime.get("mean", 0)

    if session["difficulty"] == "easy":
        margin = 0.5
    if session["difficulty"] == "medium":
        margin = 0.25
    if session["difficulty"] == "hard":
        margin = 0.1

    anime_pool = session["anime_pool"]

    # Check if guess is within acceptable margin
    if abs(guess_value - actual_rating) <= margin:
        session["score"] += 1
        embed = discord.Embed(title="✓ Correct!", color=discord.Color.green())

        if anime_pool:  # Still have more anime
            embed.add_field(name="Your Guess", value=guess_value, inline=True)
            embed.add_field(name="Actual Rating", value=actual_rating, inline=True)
            embed.add_field(
                name="Difficulty: ", value=session["difficulty"], inline=True
            )
            embed.add_field(name="Current Score", value=session["score"], inline=False)
            next_anime = anime_pool.pop(random.randint(0, len(anime_pool) - 1)).get(
                "node", {}
            )
            session["current_anime"] = next_anime
            embed.add_field(
                name="Next Anime",
                value=get_anime_title_with_alternative(next_anime),
                inline=False,
            )
            if next_anime.get("main_picture"):
                embed.set_image(url=next_anime["main_picture"]["medium"])
        else:  # Pool exhausted, last correct guess
            embed.add_field(name="Final Guess", value=guess_value, inline=True)
            embed.add_field(name="Actual Rating", value=actual_rating, inline=True)
            embed.add_field(
                name="Difficulty: ", value=session["difficulty"], inline=True
            )
            embed.add_field(name="Final Score", value=session["score"], inline=False)
            embed.add_field(
                name="Game Over",
                value="Anime pool exhausted! You did it!",
                inline=False,
            )
            if current_anime.get("main_picture"):
                embed.set_image(url=current_anime["main_picture"]["medium"])
            del user_guess_sessions[user_id]

    else:
        embed = discord.Embed(title="✗ Wrong!", color=discord.Color.red())
        embed.add_field(name="Your Guess", value=guess_value, inline=True)
        embed.add_field(name="Actual Rating", value=actual_rating, inline=True)
        embed.add_field(name="Difficulty: ", value=session["difficulty"], inline=True)
        embed.add_field(name="Final Score", value=session["score"], inline=False)
        if current_anime.get("main_picture"):
            embed.set_image(url=current_anime["main_picture"]["medium"])
        del user_guess_sessions[user_id]

    await interaction.response.send_message(embed=embed)


@app_commands.describe(limit="Anime pool size (2-2500). Default 500", ranking_type="Ranking type: bypopularity (default), airing, movie, favorite")
@bot.tree.command(name="higherlower", description="Play the higher or lower rating game")
async def higherlower(
    interaction: discord.Interaction,
    limit: Optional[int] = None,
    ranking_type: str = "bypopularity",
):
    """Start the higher/lower rating game"""

    await interaction.response.defer()

    user_id = interaction.user.id
    ranking_type = ranking_type.lower()

    # Default limit if not provided
    if not limit:
        limit_value = 500
    else:
        try:
            limit_value = int(limit)
        except ValueError:
            await interaction.followup.send(
                f'Invalid limit "{limit}". Limit must be a number between 2-2500. Use `/help higherlower` for more info.'
            )
            return

    if ranking_type == "popularity":
        ranking_type = "bypopularity"

    valid_types = ["bypopularity", "airing", "movie", "favorite"]
    if ranking_type not in valid_types:
        await interaction.followup.send(
            f"Invalid ranking type \"{ranking_type}\". Valid options: {', '.join(valid_types)}. Use `/help higherlower` for more info."
        )
        return

    if limit_value < 2 or limit_value > 2500:
        await interaction.followup.send(
            f'Invalid limit "{limit}". Limit must be a number between 2-2500. Use `/help higherlower` for more info.'
        )
        return

    # Use limit_value for fetching instead of limit
    limit = limit_value

    all_anime = []
    offset = 0
    remaining = limit

    # Fetch anime in batches (API max: 500 per request)
    while remaining > 0:
        batch_limit = min(remaining, 500)
        response = get_top_anime_by_rank(
            limit=batch_limit, ranking_type=ranking_type, offset=offset
        )

        if not response or "data" not in response:
            break

        all_anime.extend(response["data"])

        # Stop if we got fewer than requested (means we've reached the end)
        if len(response["data"]) < batch_limit:
            break

        remaining -= batch_limit
        offset += batch_limit

    if not all_anime or len(all_anime) < 2:
        await interaction.followup.send("Could not start game.")
        return

    # Remove from pool so same anime doesn't appear twice
    current_anime = all_anime.pop(random.randint(0, len(all_anime) - 1)).get("node", {})
    next_anime = all_anime.pop(random.randint(0, len(all_anime) - 1)).get("node", {})

    user_higher_lower_sessions[user_id] = {
        "current_anime": current_anime,
        "next_anime": next_anime,
        "score": 0,
        "anime_pool": all_anime,
    }

    embed = discord.Embed(title="Higher or Lower Game", color=discord.Color.gold())
    embed.add_field(
        name="Anime",
        value=get_anime_title_with_alternative(current_anime),
        inline=False,
    )
    embed.add_field(name="Rating", value=current_anime.get("mean", "?"), inline=False)
    embed.add_field(
        name="Instructions",
        value="Is the next anime rated higher or lower?\nUse the buttons below!",
        inline=False,
    )

    if current_anime.get("main_picture"):
        embed.set_image(url=current_anime["main_picture"]["medium"])

    await interaction.followup.send(embed=embed)

    embed2 = discord.Embed(title="Next Anime", color=discord.Color.gold())
    embed2.add_field(
        name="Title", value=get_anime_title_with_alternative(next_anime), inline=False
    )
    if next_anime.get("main_picture"):
        embed2.set_image(url=next_anime["main_picture"]["medium"])

    view = HigherLowerView(user_id)
    msg = await interaction.followup.send(embed=embed2, view=view)
    view.message = msg


async def _process_higher_lower_guess(guess, interaction, message):
    """Process higher/lower guess"""

    user_id = interaction.user.id

    if user_id not in user_higher_lower_sessions:
        await interaction.followup.send("Start a game first with /higherlower")
        return

    session = user_higher_lower_sessions[user_id]
    anime_pool = session["anime_pool"]

    current_anime = session["current_anime"]
    current_rating = current_anime.get("mean", 0)
    next_anime = session["next_anime"]
    next_rating = next_anime.get("mean", 0)

    # Determine if guess matches rating comparison
    is_correct = (guess == "higher" and next_rating >= current_rating) or (
        guess == "lower" and next_rating <= current_rating
    )

    if is_correct:
        session["score"] += 1
        session["current_anime"] = next_anime

        embed = discord.Embed(title="✓ Correct!", color=discord.Color.green())

        if anime_pool:  # Still have more anime
            embed.add_field(name="Streak", value=session["score"], inline=False)
            embed.add_field(
                name="Current Anime",
                value=f"{get_anime_title_with_alternative(session['current_anime'])}\nRating: {next_rating}",
                inline=False,
            )
            session["next_anime"] = anime_pool.pop(
                random.randint(0, len(anime_pool) - 1)
            ).get("node", {})

            embed.add_field(
                name="Next Anime",
                value=get_anime_title_with_alternative(session["next_anime"]),
                inline=False,
            )

            if session["next_anime"].get("main_picture"):
                embed.set_image(url=session["next_anime"]["main_picture"]["medium"])

            view = HigherLowerView(user_id)
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg
        else:  # Pool exhausted, last correct guess
            embed.add_field(name="Final Streak", value=session["score"], inline=False)
            embed.add_field(
                name="Final Anime",
                value=f"{get_anime_title_with_alternative(session['current_anime'])}\nRating: {next_rating}",
                inline=False,
            )
            embed.add_field(
                name="Game Over",
                value="Anime pool exhausted! You did it!",
                inline=False,
            )
            if next_anime.get("main_picture"):
                embed.set_image(url=next_anime["main_picture"]["medium"])
            await interaction.followup.send(embed=embed)
            del user_higher_lower_sessions[user_id]
    else:
        embed = discord.Embed(title="✗ Wrong!", color=discord.Color.red())
        embed.add_field(
            name="Previous Anime",
            value=f"{get_anime_title_with_alternative(current_anime)}\nRating: {current_rating}",
            inline=True,
        )
        embed.add_field(
            name="Final Anime",
            value=f"{get_anime_title_with_alternative(next_anime)}\nRating: {next_rating}",
            inline=True,
        )
        embed.add_field(name="Final Streak", value=session["score"], inline=False)

        if session["next_anime"].get("main_picture"):
            embed.set_image(url=session["next_anime"]["main_picture"]["medium"])

        del user_higher_lower_sessions[user_id]
        await interaction.followup.send(embed=embed)


@app_commands.describe(command="Command name to get help for")
@bot.tree.command(name="help", description="Display help information for commands")
async def help(interaction: discord.Interaction, command: Optional[str] = None):
    """Display help information for commands"""

    if command is None:
        embed = discord.Embed(
            title="📖 Bot Command Help",
            description="Use `/help <command>` for detailed info\nExample: `/help search`\n`< >` are required fields\n`[ ]` are optional fields",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🔍 Search & Info",
            value="`/search <name>` - Search for anime\n`/anime <id>` - Get anime details",
            inline=False,
        )

        embed.add_field(
            name="📚 Anime Lists",
            value="`/list <username> [sorting method] [status]` - View a user's list\n`/seasonal <year> <season>` - View seasonal anime in a list",
            inline=False,
        )

        embed.add_field(
            name="🎮 Games",
            value="`/guessgame [difficulty] [limit] [ranking type]` - Guess the rating\n`/guess <number>` - Submit guess for guess the rating game\n`/higherlower [limit] [ranking type]` - Higher or lower game",
            inline=False,
        )

        embed.set_footer(text="Powered by MyAnimeList")
        await interaction.response.send_message(embed=embed)
        return

    command = command.lower()

    help_data = {
        "search": {
            "usage": "/search <anime name>",
            "description": "Search MyAnimeList for anime titles. Returns anime ID and brief overview. Use the dropdown to get more info.",
            "example": "/search Demon Slayer",
        },
        "anime": {
            "usage": "/anime <anime_id>",
            "description": "Get detailed information for an anime by ID.",
            "example": "/anime 5114",
        },
        "list": {
            "usage": "/list <username> [sorting method] [status]",
            "description": "View a user's anime list with pagination. Optional sort by alphabetical (default) or score. Optionally, filter by status.",
            "example": "/list username completed",
            "sort options": "alphabetical (default), score",
            "statuses": "watching, completed, on hold, dropped, plan to watch",
        },
        "seasonal": {
            "usage": "/seasonal <year> <season>",
            "description": "View anime from a specific season with pagination.",
            "example": "/seasonal 2024 spring",
            "seasons": "winter, spring, summer, fall",
        },
        "guessgame": {
            "usage": "/guessgame [difficulty] [limit] [ranking type]",
            "description": "Start the guess-the-rating game. Guess the rating within margin. Optional limit for anime pool size (default: 500, min is 1, max is 2500) and ranking type.",
            "example": "/guessgame or /guessgame 100 airing",
            "ranking types": "popularity (default), airing, movie, favorite",
            "difficulties": "easy (margin: 0.5), medium (default margin: 0.25), hard (margin: 0.1)",
        },
        "guess": {
            "usage": "/guess <number>",
            "description": "Submit your rating guess in the guess game.",
            "example": "/guess 8.5",
        },
        "higherlower": {
            "usage": "/higherlower [limit] [ranking type]",
            "description": "Play the higher or lower rating game using buttons. Optional limit for anime pool size (default: 500, min is 2, max is 2500) and ranking type.",
            "example": "/higherlower or /higherlower 100 favorite",
            "ranking types": "popularity (default), airing, movie, favorite",
        },
    }

    if command not in help_data:
        embed = discord.Embed(
            title="❌ Unknown Command",
            description=f"'{command}' is not a valid command.\nUse `/help` to see all available commands.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)
        return

    data = help_data[command]
    embed = discord.Embed(title=f"📖 Help: /{command}", color=discord.Color.green())

    embed.add_field(name="Usage", value=f"`{data['usage']}`", inline=False)
    embed.add_field(name="Description", value=data["description"], inline=False)

    if "statuses" in data:
        embed.add_field(name="Valid Statuses", value=data["statuses"], inline=False)

    if "ranking types" in data:
        embed.add_field(name="Ranking Types", value=data["ranking types"], inline=False)

    if "seasons" in data:
        embed.add_field(name="Valid Seasons", value=data["seasons"], inline=False)

    if "sort options" in data:
        embed.add_field(name="Sort Options", value=data["sort options"], inline=False)

    if "difficulties" in data:
        embed.add_field(name="Difficulties", value=data["difficulties"], inline=False)

    embed.add_field(name="Example", value=data["example"], inline=False)
    embed.set_footer(text="Powered by MyAnimeList")

    await interaction.response.send_message(embed=embed)


# ===== BOT STARTUP =====


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """Handle errors for app commands"""
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"This command is on cooldown. Please try again in {error.retry_after:.2f}s.",
            ephemeral=True,
        )
    else:
        debug(f"App command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "An error occurred while processing the command.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "An error occurred while processing the command.", ephemeral=True
            )


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} has connected and synced commands!")


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
