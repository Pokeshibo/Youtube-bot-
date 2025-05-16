import discord
from discord.ext import commands
import pytchat
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import asyncio

intents = discord.Intents.default()
intents.messages = True
intents.dm_messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

monitoring_tasks = {}

async def monitor_chat(url, user_id):
    video_id = get_video_id(url)
    if not video_id:
        await bot.get_user(user_id).send("Invalid YouTube live stream URL")
        return

    try:
        chat = pytchat.create(video_id=video_id)
        await bot.get_user(user_id).send(f"Started monitoring {url}")

        while chat.is_alive():
            for c in chat.get().sync_items():
                if c.message == '-clip':
                    timestamp = datetime.strptime(c.datetime, "%Y-%m-%d %H:%M:%S")
                    await bot.get_user(user_id).send(f"Clip command received at: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error: {str(e)}")
        await bot.get_user(user_id).send("Monitoring stopped due to an error or stream ended")

def get_video_id(url):
    parsed_url = urlparse(url)
    if parsed_url.netloc == 'youtu.be':
        return parsed_url.path[1:]
    elif parsed_url.netloc in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        elif parsed_url.path.startswith('/live/'):
            return parsed_url.path.split('/')[2].split('?')[0]
    return None

@bot.command()
async def start(ctx, url: str):
    user_id = ctx.author.id
    if user_id in monitoring_tasks:
        await ctx.author.send("You are already monitoring a stream")
        return

    async def task():
        await monitor_chat(url, user_id)
        if user_id in monitoring_tasks:
            del monitoring_tasks[user_id]

    monitoring_tasks[user_id] = bot.loop.create_task(task())
    await ctx.author.send(f"Monitoring started for {url}")

@bot.command()
async def stop(ctx):
    user_id = ctx.author.id
    if user_id in monitoring_tasks:
        task = monitoring_tasks.pop(user_id)
        task.cancel()
        await ctx.author.send("Monitoring stopped")
    else:
        await ctx.author.send("You are not monitoring any stream")

bot.run('MTM3MzAxNzA3NDA0NTAzMDUxMw.GlR96-.llbIFdBd8NHlGQZy6SY0LWbQJshdVmjef8WQqs')
