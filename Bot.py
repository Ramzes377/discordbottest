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
    traceback = 'Error in event ' + str(event) + '\n'
    traceback += 'Args: ' + ' '.join(map(str, args)) + '\n'
    traceback += 'Kwargs: ' + ' '.join(map(lambda key, value: str(key) + ' - ' + str(value), kwargs.items()))
    admin = await bot.fetch_user(admin_id)
    await admin.send(traceback)

token = os.environ.get('TOKEN')
bot.run(str(token))
