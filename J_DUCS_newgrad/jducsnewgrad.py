import json
import os
import time
from datetime import datetime, timedelta, timezone, time as dt_time
import git
import discord
from discord.ext import tasks, commands
import asyncio
from dotenv import load_dotenv
import gc
import ijson  # new dependency

# Constants
REPO_URL = 'https://github.com/SimplifyJobs/New-Grad-Positions'
LOCAL_REPO_PATH = 'New-Grad-Positions'
JSON_FILE_PATH = os.path.join(LOCAL_REPO_PATH, '.github', 'scripts', 'listings.json')
ROLES_DATA_FILE = 'roles_data.json'
load_dotenv() 
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = "1361931043413823539"

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
running = True

def clone_or_update_repo():
    print("Cloning or updating repository...")
    if os.path.exists(LOCAL_REPO_PATH):
        try:
            repo = git.Repo(LOCAL_REPO_PATH)
            repo.remotes.origin.pull()
            print("Repository updated.")
        except git.exc.InvalidGitRepositoryError:
            os.rmdir(LOCAL_REPO_PATH)
            git.Repo.clone_from(REPO_URL, LOCAL_REPO_PATH, depth=5)
            print("Repository cloned fresh.")
    else:
        git.Repo.clone_from(REPO_URL, LOCAL_REPO_PATH, depth=2)
        print("Repository cloned fresh.")

def iter_json():
    print(f"Reading JSON file from {JSON_FILE_PATH} iteratively...")
    with open(JSON_FILE_PATH, 'r') as file:
        # 'item' tells ijson to iterate over the items of the top-level array
        for role in ijson.items(file, 'item'):
            print(f"Processing role: {role['title']} at {role['company_name']}")
            yield role

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
        print(f"Sending message to channel ID {channel_id}...")
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            print(f"Channel {channel_id} not in cache, attempting to fetch...")
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except Exception as e:
                print(f"Error fetching channel {channel_id}: {e}")
                return

        await channel.send(message)
        print(f"Successfully sent message to channel {channel_id}")
        await asyncio.sleep(2)
        
    except Exception as e:
        print(f"Error sending message to channel {channel_id}: {e}")
        return

async def check_for_new_roles():
    global running
    print("Checking for new roles...")
    
    clone_or_update_repo()
    
    # Load previously processed roles as a set of role IDs
    if os.path.exists(ROLES_DATA_FILE):
        with open(ROLES_DATA_FILE, 'r') as file:
            processed_roles_list = json.load(file)
            processed_roles = set(tuple(item) for item in processed_roles_list)
        print("Previous data loaded.")
    else:
        processed_roles = set()
        print("No previous data found.")

    new_roles = []

    print(f"Reading JSON file from {JSON_FILE_PATH} iteratively...")
    with open(JSON_FILE_PATH, 'r') as file:
        for role in ijson.items(file, 'item'):
            print(f"Processing role: {role['title']} at {role['company_name']}")
            role_id = role['id']
            if role_id in processed_roles:
                continue

            if role.get('is_visible') and role.get('active'):
                print(f"Role {role['title']} is visible and active.")
                date_posted = role.get('date_posted')
                created_at_str = datetime.fromtimestamp(date_posted).isoformat() if date_posted else None
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        print(f"Created at: {created_at}")
                        if datetime.now() - created_at <= timedelta(hours=24):
                            new_roles.append(role)
                            processed_roles.add(role_id)
                            print(f"New role found: {role['title']} at {role['company_name']}")
                    except Exception as e:
                        print(f"Error parsing created_at for role {role['title']}: {e}")

    for role in new_roles:
        message = format_message(role)
        try:
            await send_message(message, CHANNEL_ID)
        except Exception as e:
            print(f"Channel error encountered: {e}")
            running = False
            # DM the server owner for each guild the bot is in
            for guild in bot.guilds:
                if guild.owner:
                    try:
                        await guild.owner.send(
                            f"Error sending message to channel {CHANNEL_ID}: '{e}'. "
                            "The bot has stopped sending new messages."
                        )
                    except Exception as dm_error:
                        print(f"Failed to DM owner for guild {guild.id}: {dm_error}")
            # Stop sending new messages forever
            break
        # Wait for 2 seconds before sending the next message
        await asyncio.sleep(2)

    with open(ROLES_DATA_FILE, 'w') as file:
        json.dump(list(processed_roles), file)
    print("Updated previous data with roles from the last 24 hours.")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    scheduled_role_check.start()
    scheduled_clean_roles_data.start()


# @tasks.loop(time=dt_time(hour=20, minute=0, tzinfo=timezone.utc))
@tasks.loop(time=dt_time(hour=5, minute=14, tzinfo=timezone.utc))
async def scheduled_role_check():
    print("Scheduled task running...")
    if running:
        await check_for_new_roles()
    gc.collect()

@scheduled_role_check.before_loop
async def before_scheduled_role_check():
    await bot.wait_until_ready()


@tasks.loop(seconds=604800)
async def scheduled_clean_roles_data():
    print("Cleaning roles data file...")
    if os.path.exists(ROLES_DATA_FILE):
        try:
            with open(ROLES_DATA_FILE, 'w') as file:
                json.dump([], file)
            print("Roles data file cleaned.")
        except Exception as e:
            print(f"Failed to clean roles data file: {e}")
    else:
        print("Roles data file does not exist; nothing to clean.")

@scheduled_clean_roles_data.before_loop
async def before_clean_roles_data():
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
    print(f"Scheduled cleaning will start in {delay} seconds.")
    await asyncio.sleep(delay)


@scheduled_clean_roles_data.before_loop
async def before_clean_roles_data():
    await bot.wait_until_ready()





print("Starting bot...")
if DISCORD_TOKEN and CHANNEL_ID:
    bot.run(DISCORD_TOKEN)
else:
    if not DISCORD_TOKEN:
        print("Please provide your Discord token.")
    if not CHANNEL_ID:
        print("Please provide your channel IDs.")
