import json
import os
from datetime import datetime, timedelta, timezone, time as dt_time
import git
import discord
from discord.ext import tasks, commands
import asyncio
from dotenv import load_dotenv
import gc
import ijson
import filepath

# ===============================================================
# Load environment variables from .env file
# ===============================================================
load_dotenv() 
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# ===============================================================
# Constants
# ===============================================================
INTERN_REPO_URL = filepath.INTERN_REPO_URL
INTERN_LOCAL_REPO_PATH = filepath.INTERN_LOCAL_REPO_PATH
INTERN_JSON_FILE_PATH = filepath.INTERN_JSON_FILE_PATH
INTERN_ROLES_DATA_FILE = filepath.INTERN_ROLES_DATA_FILE
INTERN_CHANNEL_ID = filepath.INTERN_CHANNEL_ID

NEWGRAD_REPO_URL = filepath.NEWGRAD_REPO_URL
NEWGRAD_LOCAL_REPO_PATH = filepath.NEWGRAD_LOCAL_REPO_PATH
NEWGRAD_JSON_FILE_PATH = filepath.NEWGRAD_JSON_FILE_PATH
NEWGRAD_ROLES_DATA_FILE = filepath.NEWGRAD_ROLES_DATA_FILE
NEWGRAD_CHANNEL_ID = filepath.NEWGRAD_CHANNEL_ID

# ===============================================================
# Initialize Discord bot
# ===============================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
running = True

# ===============================================================
# Retrieve mew roles from the repository
# ===============================================================
def clone_or_update_repo(local_repo_path, repo_url):
    print("Cloning or updating repository...")
    if os.path.exists(local_repo_path):
        try:
            repo = git.Repo(local_repo_path)
            repo.remotes.origin.pull()
            # print("Repository updated.")
        except git.exc.InvalidGitRepositoryError:
            os.rmdir(local_repo_path)
            git.Repo.clone_from(repo_url, local_repo_path, depth=5)
            # print("Repository cloned fresh.")
    else:
        git.Repo.clone_from(repo_url, local_repo_path, depth=2)
        # print("Repository cloned fresh.")
    


def iter_json(json_file_path):
    print(f"Reading JSON file from {json_file_path} iteratively...")
    with open(json_file_path, 'r') as file:
        # 'item' tells ijson to iterate over the items of the top-level array
        for role in ijson.items(file, 'item'):
            # print(f"Processing role: {role['title']} at {role['company_name']}")
            yield role


async def check_for_new_roles(local_repo_path, repo_url, roles_data_file, json_file_path, channel_id):
    global running
    print("Checking for new roles...")
    
    clone_or_update_repo(local_repo_path, repo_url)
    
    # Load previously processed roles as a set of role IDs
    if os.path.exists(roles_data_file):
        with open(roles_data_file, 'r') as file:
            processed_roles_list = json.load(file)
            processed_roles = set(tuple(item) for item in processed_roles_list)
        # print("Previous data loaded.")
    else:
        processed_roles = set()
        # print("No previous data found.")

    new_roles = []

    # print(f"Reading JSON file from {json_file_path} iteratively...")
    with open(json_file_path, 'r') as file:
        for role in ijson.items(file, 'item'):
            # print(f"Processing role: {role['title']} at {role['company_name']}")
            role_id = role['id']
            if role_id in processed_roles:
                continue

            if role.get('is_visible') and role.get('active'):
                # print(f"Role {role['title']} is visible and active.")
                date_posted = role.get('date_posted')
                created_at_str = datetime.fromtimestamp(date_posted).isoformat() if date_posted else None
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        # print(f"Created at: {created_at}")
                        if datetime.now() - created_at <= timedelta(hours=24):
                            new_roles.append(role)
                            processed_roles.add(role_id)
                            # print(f"New role found: {role['title']} at {role['company_name']}")
                    except Exception as e:
                        print(f"Error parsing created_at for role {role['title']}: {e}")

    for role in new_roles:
        message = format_message(role)
        try:
            await send_message(message, channel_id)
        except Exception as e:
            print(f"Channel error encountered: {e}")
            running = False
            # DM the server owner for each guild the bot is in
            for guild in bot.guilds:
                if guild.owner:
                    try:
                        await guild.owner.send(
                            f"Error sending message to channel {channel_id}: '{e}'. "
                            "The bot has stopped sending new messages."
                        )
                    except Exception as dm_error:
                        print(f"Failed to DM owner for guild {guild.id}: {dm_error}")
            # Stop sending new messages forever
            break
        # Wait for 2 seconds before sending the next message
        await asyncio.sleep(2)

    with open(roles_data_file, 'w') as file:
        json.dump(list(processed_roles), file)
    print("Updated previous data with roles from the last 24 hours.")



# ===============================================================
# Format message for Discord
# ===============================================================
def format_message(role):
    try:
        location_str = ', '.join(role['locations']) if role['locations'] else 'Not specified'
        return f"""
>>> # {role['company_name']} just posted a new role!

### Role:
[{role['title']}]({role['url']})

### Location:
{location_str}

### Sponsorship: `{role['sponsorship']}`
### Posted on: {datetime.now().strftime('%B, %d')}
"""
    except Exception as e:
        return f"Error formatting message: {e}"


async def send_message(message, channel_id):
    try:
        # print(f"Sending message to channel ID {channel_id}...")
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            # print(f"Channel {channel_id} not in cache, attempting to fetch...")
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except Exception as e:
                print(f"Error fetching channel {channel_id}: {e}")
                return

        await channel.send(message)
        # print(f"Successfully sent message to channel {channel_id}")
        await asyncio.sleep(2)
        
    except Exception as e:
        print(f"Error sending message to channel {channel_id}: {e}")
        return



# ===============================================================
# Discord bot events
# ===============================================================
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    scheduled_intern_role_check.start()
    scheduled_clean_intern_roles_data.start()

    scheduled_newgrad_role_check.start()
    scheduled_clean_newgrad_roles_data.start()


# ------------- Intern Roles -------------------
@tasks.loop(time=dt_time(hour=22, minute=10, tzinfo=timezone.utc))
async def scheduled_intern_role_check():
    print("Scheduled intern task running...")
    if running:
        await check_for_new_roles(INTERN_LOCAL_REPO_PATH, INTERN_REPO_URL, INTERN_ROLES_DATA_FILE, INTERN_JSON_FILE_PATH, INTERN_CHANNEL_ID)
    gc.collect()

@scheduled_intern_role_check.before_loop
async def before_scheduled_intern_role_check():
    await bot.wait_until_ready()

@tasks.loop(seconds=604800)
async def scheduled_clean_intern_roles_data():
    print("Cleaning roles data file...")
    if os.path.exists(INTERN_ROLES_DATA_FILE):
        try:
            with open(INTERN_ROLES_DATA_FILE, 'w') as file:
                json.dump([], file)
            # print("Roles data file cleaned.")
        except Exception as e:
            print(f"Failed to clean roles data file: {e}")
    else:
        # print("Roles data file does not exist; nothing to clean.")
        pass

@scheduled_clean_intern_roles_data.before_loop
async def before_clean_Intern_roles_data():
    await bot.wait_until_ready()
    # Calculate delay until next Sunday at 20:01 UTC.
    now = datetime.now(timezone.utc)
    # Sunday is weekday 6 (Monday=0, Sunday=6)
    # Set target time for this week (or next if already passed)
    target = now.replace(hour=20, minute=1, second=0, microsecond=0)
    days_ahead = (6 - now.weekday()) % 7
    if days_ahead == 0 and target < now:
        days_ahead = 7
    target = target + timedelta(days=days_ahead)
    delay = (target - now).total_seconds()
    print(f"Scheduled intern cleaning will start in {delay} seconds.")
    await asyncio.sleep(delay)


# ------------- Intern Roles -------------------
@tasks.loop(time=dt_time(hour=22, minute=11, tzinfo=timezone.utc))
async def scheduled_newgrad_role_check():
    print("Scheduled newgrad task running...")
    if running:
        await check_for_new_roles(NEWGRAD_LOCAL_REPO_PATH, NEWGRAD_REPO_URL, NEWGRAD_ROLES_DATA_FILE, NEWGRAD_JSON_FILE_PATH, NEWGRAD_CHANNEL_ID)
    gc.collect()

@scheduled_newgrad_role_check.before_loop
async def before_scheduled_newgrad_role_check():
    await bot.wait_until_ready()

@tasks.loop(seconds=604800)
async def scheduled_clean_newgrad_roles_data():
    print("Cleaning roles data file...")
    if os.path.exists(NEWGRAD_ROLES_DATA_FILE):
        try:
            with open(NEWGRAD_ROLES_DATA_FILE, 'w') as file:
                json.dump([], file)
            # print("Roles data file cleaned.")
        except Exception as e:
            print(f"Failed to clean roles data file: {e}")
    else:
        # print("Roles data file does not exist; nothing to clean.")
        pass

@scheduled_clean_newgrad_roles_data.before_loop
async def before_clean_newgrad_roles_data():
    await bot.wait_until_ready()
    # Calculate delay until next Sunday at 20:01 UTC.
    now = datetime.now(timezone.utc)
    # Sunday is weekday 6 (Monday=0, Sunday=6)
    # Set target time for this week (or next if already passed)
    target = now.replace(hour=19, minute=1, second=0, microsecond=0)
    days_ahead = (6 - now.weekday()) % 7
    if days_ahead == 0 and target < now:
        days_ahead = 7
    target = target + timedelta(days=days_ahead)
    delay = (target - now).total_seconds()
    print(f"Scheduled newgrad cleaning will start in {delay} seconds.")
    await asyncio.sleep(delay)


# ===============================================================
# Run the bot
# ===============================================================
print("Starting bot...")
if DISCORD_TOKEN and INTERN_CHANNEL_ID:
    bot.run(DISCORD_TOKEN)
else:
    if not DISCORD_TOKEN:
        print("Please provide your Discord token.")
    if not INTERN_CHANNEL_ID:
        print("Please provide your channel IDs.")
