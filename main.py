import os
import dotenv
import requests as req
import time
import discord
import json
from discord.ext import tasks, commands
from discord import app_commands

dotenv.load_dotenv()

TOKEN = os.getenv("OLY_TOKEN")
DISCORD_TOKEN = os.getenv("DISC_TOKEN")

BASE_URL = "https://stats.olympus-entertainment.com/api/v3.0/"
headers = {
    "accept": "application/json",
    "X-Fields": "name, gang_name, progress, gang_id",
    "Authorization": f"Token {TOKEN}"
}
config = {}
prev_state = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!',intents=intents)

def get_cartels() -> list:
    response = req.get(BASE_URL + "cartels/", headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data
    elif response.status_code == 401:
        print("Improper Auth")
        return []
    else:
        print("Limit reached")
        return []

@tasks.loop(minutes=1.2)
async def cartel_check():

    for guild_id, guild_config in config.items():
        channel_id = guild_config.get("channel_id")
        gang_id = guild_config.get("gang_id", 0)

        if not channel_id or not gang_id:
            continue

        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        cartels = get_cartels()
        if guild_id not in prev_state:
            prev_state[guild_id] = {}

        for cartel in cartels:
            name = cartel['name']
            gang = cartel['gang_name']
            cartel_gang_id = cartel['gang_id']
            progress = cartel['progress']

            if name in prev_state[guild_id]:
                prev_progress = prev_state[guild_id][name]['progress']
                prev_gang_id = prev_state[guild_id][name]['gang_id']

                if prev_gang_id == gang_id and cartel_gang_id == gang_id and progress < prev_progress:
                    embed = discord.Embed(title="🚨 CARTEL UNDER ATTACK! 🚨", description=f"**{name}** is being contested!", color=discord.Color.red())
                    embed.add_field(name="Progress", value=f"{prev_progress}% → {progress}%", inline=False)
                    embed.add_field(name="Status", value="Defenders needed!", inline=False)
                    await channel.send(content="@everyone", embed=embed)

                elif prev_gang_id == gang_id and cartel_gang_id != gang_id:
                    embed = discord.Embed(title="💀 CARTEL LOST", description=f"**{name}** has been captured by **{gang}**", color=discord.Color.dark_red())
                    await channel.send(content="@everyone", embed=embed)

                elif prev_gang_id != gang_id and cartel_gang_id == gang_id:
                    embed = discord.Embed(title="🎉 CARTEL CAPTURED!", description=f"**{name}** is now being controlled!", color=discord.Color.green())
                    embed.add_field(name="Progress", value=f"{progress}%", inline=False)
                    await channel.send(embed=embed)

            prev_state[guild_id][name] = {'gang_name': gang, 'progress': progress, 'gang_id': cartel_gang_id}

@bot.tree.command(name='caps', description='Shows current cartels')
async def cur_cartels(interaction: discord.Interaction):
    """Shows current cartel status"""
    guild_id = str(interaction.guild_id)
    guild_prev_state = prev_state.get(guild_id, {})
    if not guild_prev_state:
        await interaction.response.send_message("No cartel data available yet. Please wait for the first update.")
        return
    embed = discord.Embed(
        title="🏴 Current Cartel Status",
        color=discord.Color.red()
    )
    for cartel_name, cartel_data in guild_prev_state.items():
        embed.add_field(
            name=f"{cartel_name} ({cartel_data['progress']}%) - {cartel_data['gang_name']}",
            value="",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='id', description='Shows tracked gang ID')
async def cur_id(interaction: discord.Integration):
    guild_config = config.get(str(interaction.guild_id), {"gang_id": 0})
    embed = discord.Embed(title='Gang ID', color=discord.Color.red())
    embed.add_field(name=f"Gang ID: {guild_config['gang_id']}", value="", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='set_id', description='Set the tracked gang ID')
@app_commands.default_permissions(administrator=True)
async def set_id(interaction: discord.Interaction, gang_id: int):
    
    guild_id = str(interaction.guild_id)
    if guild_id not in config:
        config[guild_id] = {"gang_id": 0, "channel_id": None}
    config[guild_id]['gang_id'] = gang_id
    save_config()
    await interaction.response.send_message(f"Tracking new gang ID: {gang_id}")

def get_gang_info(gang_id:int) -> list:
    headers = {
        "accept": "application/json",
        "X-Fields": "bank",
        "Authorization": f"Token {TOKEN}"
    }
    response = req.get(BASE_URL + f"gangs/{gang_id}", headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data
    elif response.status_code == 401:
        print("Improper Auth")
        return []
    else:
        print("Too many requests")
        return []

@bot.event
async def on_ready():
    print(f"{bot.user} logged in!")
    await bot.tree.sync()
    print(f"Connected to {len(bot.guilds)} server")
    if not cartel_check.is_running():
        cartel_check.start()


@bot.tree.command(name='setchannel', description='Set notification/bot channel')
@app_commands.default_permissions(administrator=True)  
async def set_channel(interaction: discord.Interaction):
    """Set the current channel as the notification channel"""
    
    guild_id = str(interaction.guild_id)
    if guild_id not in config:
        config[guild_id] = {'gang_id': 0, 'channel_id': None}
    config[guild_id]['channel_id'] = interaction.channel.id
    save_config()
    await interaction.response.send_message(f"✅ Notification channel set to {interaction.channel.mention}")
    print(f"Channel set to: {interaction.channel.name} (ID: {config[guild_id]['channel_id']})")

def save_config():
    with open("config.json", "w") as f:
        json.dump(config, f)

def load_config():
    global config

    if os.path.exists("config.json"):
        with open("config.json") as f:
            config = json.load(f)
    else:
        save_config()

if __name__ == "__main__":
    load_config()   # Always initializes config before running the bot
    bot.run(DISCORD_TOKEN)


