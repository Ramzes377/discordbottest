from discord.ext import commands
import os

bot = commands.Bot(command_prefix = '!')


for filename in os.listdir('./Cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'Cogs.{filename[:-3]}')


@bot.event
async def on_ready():
    print('Bot have been started!')

token = os.environ.get('TOKEN')
bot.run(str(token))
