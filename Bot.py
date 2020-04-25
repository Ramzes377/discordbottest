from discord.ext import commands
import os
import sqlite3

admin_id = os.environ.get('Admin_ID')

bot = commands.Bot(command_prefix = '!')


name = os.environ.get('db_name')
user = os.environ.get('db_user')
password = os.environ.get('db_password')
host = os.environ.get('db_host')

dsn = f'dbname={name} user={user} password={password} host={host}'


for filename in os.listdir('./Cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'Cogs.{filename[:-3]}')


@bot.event
async def on_ready():
    bot.db = await aiopg.create_pool(dsn)

    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS ChannelsINFO(user_id int, channel_id int)')
    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS SessionsINFO(channel_id int, creator_id int, start_day int, session_id text, message_id int)')
    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS SessionsID(current_day int, past_sessions_counter int, current_sessions_counter int)')
    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS SessionsMembers(channel_id int, member_id int)')
    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS SessionsActivities(channel_id int, associate_role int)')
    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS CreatedRoles(application_id int UNIQUE, role_id int)')
    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS ActivitiesINFO(application_id int,  icon_url text, name text)')
    bot.db_cursor.execute('CREATE TABLE IF NOT EXISTS CreatedEmoji(application_id int UNIQUE, emoji_id int)')

    admin = await bot.fetch_user(admin_id)
    await admin.send("I'am restarting!")
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
