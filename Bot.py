from discord.ext import commands
import os
import aiopg

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

    async with bot.db.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute('CREATE TABLE IF NOT EXISTS ChannelsINFO(user_id bigint, channel_id bigint)')
            await cur.execute('CREATE TABLE IF NOT EXISTS SessionsINFO(channel_id bigint, creator_id bigint, start_day bigint, session_id text, message_id bigint)')
            await cur.execute('CREATE TABLE IF NOT EXISTS SessionsID(current_day bigint, past_sessions_counter bigint, current_sessions_counter bigint)')
            await cur.execute('CREATE TABLE IF NOT EXISTS SessionsMembers(channel_id bigint, member_id bigint)')
            await cur.execute('CREATE TABLE IF NOT EXISTS SessionsActivities(channel_id bigint, associate_role bigint)')
            await cur.execute('CREATE TABLE IF NOT EXISTS CreatedRoles(application_id bigint, role_id bigint)')
            await cur.execute('CREATE TABLE IF NOT EXISTS ActivitiesINFO(application_id bigint,  icon_url text, name text)')
            await cur.execute('CREATE TABLE IF NOT EXISTS CreatedEmoji(application_id bigint, emoji_id bigint)')

    print('Bot have been started!')

token = os.environ.get('TOKEN')
bot.run(str(token))
