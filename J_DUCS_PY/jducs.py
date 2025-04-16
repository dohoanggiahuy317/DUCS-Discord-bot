import os
import re
import asyncio
from datetime import datetime

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}.")

# ========================================================================
# THIS FUNCTION ASKS QUESTIONS TO THE USER IN DM TO SET UP USERNAME AND ROLE
# ========================================================================
@bot.event
async def on_member_join(member):
    try:
        dm_channel = await member.create_dm()

        async def ask_question(question):
            await dm_channel.send(question)
            def check(m):
                return m.author == member and m.channel == dm_channel
            try:
                response = await bot.wait_for("message", check=check, timeout=6000)
                return response.content
            except asyncio.TimeoutError:
                await dm_channel.send("Timed out waiting for a response. Please try rejoin the server again.")
                raise Exception("No response received within time limit.")

        # Ask for the user's name in a loop until a valid (non-empty) answer is provided
        name = ""
        while not name.strip():
            name = await ask_question("Welcome to DUCS! I’m the DUCS Bot, here to help get you all set up on the server 🎉 Let’s start with a quick question — what’s your name?")
            if not name.strip():
                await dm_channel.send("Please enter a valid name.")

        # Ask for the class year in a loop until a valid number is provided
        current_year = datetime.now().year
        class_year = None
        while True:
            class_year_str = await ask_question("What's your class year?")
            try:
                class_year = int(class_year_str.strip())
                break
            except ValueError:
                await dm_channel.send("Please enter a valid class year as a number.")

        # Ask for the Denison email
        email = ""
        while True:
            email = await ask_question("What's your Denison email? (please include '@denison.edu' at the end)")
            if email.strip().lower().endswith('@denison.edu'):
                break
            else:
                await dm_channel.send("Sorry, your email does not meet the required domain. Please try again.")

        # If the member is a graduate, ask if they want to update their company info
        company = ""
        if class_year < current_year:
            while True:
                company_answer = await ask_question("Since you are graduated, do you want to add your company name or school in your server nickname? If yes, please enter the company name, or type 'no' to skip.")
                if not company_answer.strip():
                    await dm_channel.send("Please enter a valid response.")
                    continue
                if company_answer.strip().lower() == 'no':
                    break
                company = company_answer.strip()
                break

        # Build the new nickname based on the answers
        if class_year < current_year:
            nickname = f"{name} - {class_year}" + (f" - {company}" if company else "")
        else:
            nickname = f"{name} - {class_year}"

        # Attempt to set the nickname and assign the "Students/Alumni" role
        try:
            await member.edit(nick=nickname)
            role = discord.utils.get(member.guild.roles, name="Students/Alumni")
            if role:
                await member.add_roles(role)
                await dm_channel.send(f"Success! Your nickname has been changed to: {nickname} and you have been assigned the 'Students/Alumni' role. Contact an admin if you want to change.")
            else:
                await dm_channel.send(f"Nickname updated successfully to: {nickname} but the role 'Students/Alumni' was not found.")
        except Exception as e:
            print("Failed to change nickname or assign role:", e)
            await dm_channel.send("I couldn't change your nickname or assign your role. Please contact an admin.")
    except Exception as error:
        print("Error handling guild member join:", error)

# ========================================================================
# THIS FUNCTION LISTENS TO MESSAGES IN THE CHANNELS "intern-process" AND "new-grad-process"
# AND REACTS TO THEM BASED ON THE CONTENT
# ========================================================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild:
        return

    # Process messages in specific channels
    if message.channel.name in ['intern-process', 'new-grad-process']:
        pattern = r'^!process\s+(.+?)\s+(apply|phone|OA|1st round|2nd round|final|offer|rejected|ghost)(?:\s+\((.+)\))?$'
        match = re.match(pattern, message.content, flags=re.IGNORECASE)
        if match:
            try:
                await message.add_reaction('✅')
            except Exception as e:
                print(e)
            if match.group(2).lower() == 'offer':
                try:
                    await message.channel.send("Congrats 💐!")
                except Exception as e:
                    print(e)
        else:
            try:
                await message.delete()
            except Exception as e:
                print(e)
            try:
                notice = await message.channel.send(
                    f"<@{message.author.id}>, please follow the format: \"!process {{company name}} {{apply|OA|phone|1st round|2nd round|final|offer|rejected|ghost}}\""
                )
                await asyncio.sleep(10)
                await notice.delete()
            except Exception as e:
                print(e)

    # ========================================================================
    # THIS FUNCTION HANDLES THE "!update-title" COMMAND TO UPDATE COMPANY NAME
    # ========================================================================
    if message.content.lower().startswith('!update-title'):
        async def reply_and_delete(content):
            reply = await message.reply(content)
            await asyncio.sleep(5)
            try:
                await reply.delete()
                await message.delete()
            except Exception as e:
                print(e)

        try:
            args = message.content.split(' ')[1:]
            new_company = ' '.join(args).strip()

            member = message.author  # In guild text channels, message.author is a Member
            current_name = member.nick if member.nick else member.name

            # Expected nickname format: "Name - <year>" or "Name - <year> - <company>"
            parts = current_name.split(" - ")
            if len(parts) < 2:
                return await reply_and_delete("Unable to determine your name from your profile.")

            try:
                year = int(parts[1].strip())
            except ValueError:
                return await reply_and_delete("Couldn't determine your graduation year.")

            current_year = datetime.now().year
            if year > current_year:
                return await reply_and_delete("This command is only available to graduates or those graduating this year.")

            updated_nickname = f"{parts[0].strip()} - {year}" + (f" - {new_company}" if new_company else "")
            try:
                await member.edit(nick=updated_nickname)
                await reply_and_delete(f"Your nickname has been updated to: {updated_nickname}")
            except Exception as e:
                print(e)
                return await reply_and_delete("I couldn't update your nickname. Please contact an admin.")
        except Exception as err:
            print("Error updating company name:", err)
            await reply_and_delete("I couldn't update your nickname. Please contact an admin.")

    await bot.process_commands(message)

from dotenv import load_dotenv
load_dotenv() 
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
print("Starting bot...")
if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    if not DISCORD_TOKEN:
        print("Please provide your Discord token.")