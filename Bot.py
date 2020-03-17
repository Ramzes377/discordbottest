from discord.ext import commands
import os

admin_id = os.environ.get('Admin_ID')

bot = commands.Bot(command_prefix = '!')


for filename in os.listdir('./Cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'Cogs.{filename[:-3]}')


@bot.event
async def on_ready():
    print('Bot have been started!')
    
@bot.event
async def on_error(event, *args, **kwargs):
    traceback = str(event) + '| '
    traceback += ' '.join(map(str, args))
    await bot.fetch_user(admin_id).send(traceback)

token = os.environ.get('TOKEN')
bot.run(str(token))
