import discord
import asyncio
import datetime
from discord.ext import commands
from time import time
from .classify import get_app_id, user_is_playing
from asyncio_extras import async_contextmanager


class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{type(self).__name__} starts')

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        await self.game_statistics(before, after)


    @commands.command(aliases = ['a', 'act'])
    async def activity(self, ctx):
        '''Дает пользователю время в игре у соответствующей игре роли!
           Введите !activity @роль или Введите !activity @роль @роль . . .
           Если вам необходимо отображение количества проведённого времени в игре,
           то для этого необходимо чтобы было включено отображение игровой активности в настройках Discord!'''
        member = ctx.message.author
        channel = ctx.message.channel
        requested_games = ctx.message.role_mentions

        if len(requested_games) == 0:
            await self.send_removable_message(ctx, 'Отсутствуют упоминания игровых ролей! Введите !help activity', 20)
            await ctx.message.delete()
            return

        sended_messages = []
        async with self.get_connection() as cur:
            for role in requested_games:
                await cur.execute(f"SELECT application_id FROM CreatedRoles WHERE role_id = {role.id}")
                app_id = await cur.fetchone()  # it's created role
                if app_id:
                    await cur.execute(f"SELECT seconds FROM UserActivityDuration WHERE user_id = {member.id} AND app_id = {app_id[0]}")
                    seconds = await cur.fetchone()  # it's created role
                    if seconds:
                        total_time = datetime.timedelta(seconds=seconds[0])
                    else:
                        total_time = 0

                    embed_obj = discord.Embed(title=f"Обработан ваш запрос по игре {role.name}", color=role.color)
                    if total_time:
                        embed_obj.add_field(name='В игре вы провели', value=f"{str(total_time).split('.')[0]}", inline=False)
                    else:
                        embed_obj.add_field(name='Вы не играли в эту игру или Discord не смог это обнаружить',
                                            value='Если вам нужна эта функция,'
                                                  'то зайдите в Настройки пользователя/Игровая активность/Отображать '
                                                  'в статусе игру в которую сейчас играете',
                                            inline=False)
                    embed_obj.description = 'Это сообщение автоматически удалится через минуту'

                    await cur.execute(f'SELECT icon_url FROM ActivitiesINFO WHERE application_id = {app_id[0]}')
                    thumbnail_url = await cur.fetchone()
                    if thumbnail_url:
                        embed_obj.set_thumbnail(url=thumbnail_url[0])

                    bot = channel.guild.get_member(self.bot.user.id)
                    embed_obj.set_footer(text='Великий бот - ' + bot.display_name, icon_url=bot.avatar_url)

                    message = await member.send(embed=embed_obj)
                    sended_messages.append(message)

        await asyncio.sleep(60)
        for message in sended_messages:
            await message.delete()
        await ctx.message.delete()

    @commands.command(aliases = ['gr'])
    async def give_role(self, ctx):
        '''Дает пользователю ИГРОВУЮ роль!
        Введите
        !give_role @роль чтобы получить роль!
        или
        !give_role @роль, @роль, ...
        чтобы получить сразу несколько ролей!'''
        member = ctx.message.author
        requested_roles = ctx.message.role_mentions

        if len(requested_roles) == 0:
            await self.send_removable_message(ctx, 'Отсутствуют упоминания ролей! Введите !help give_role.', 20)
            await ctx.message.delete()
            return

        sended_messages = []
        async with self.get_connection() as cur:
            for role in requested_roles:
                await cur.execute(f"SELECT * FROM CreatedRoles WHERE role_id = {role.id}")
                if await cur.fetchone(): #it's created role
                    if not role in member.roles: #member hasn't these role
                         await member.add_roles(role)
                         message = await ctx.send(f'Успешно добавлена роль {role.mention}!')
                    else: #member already have these role
                        message = await ctx.send(f'У вас уже есть роль {role.mention}!')
                else: #wrong role
                    message = await ctx.send(f'{role.mention} не относится к игровым ролям!')

                sended_messages.append(message)

        await asyncio.sleep(20)
        for message in sended_messages:
            await message.delete()
        await ctx.message.delete()

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, messages_count = 0):
        '''Удаляет последние message_count сообщений
           Example: !clear 10
           Только для ролей с правом удаления сообщений.'''
        channel = ctx.message.channel
        async for message in channel.history(limit = messages_count + 1):
            await message.delete()


    @async_contextmanager
    async def get_connection(self):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                yield cur


    async def send_removable_message(self, ctx, message, delay = 5):
        message = await ctx.send(message)
        await asyncio.sleep(delay)
        await message.delete()

    async def game_statistics(self, before, after):
        if user_is_playing(after):
            app_id, _ = get_app_id(after)
            async with self.get_connection() as cur:
                await cur.execute(f"SELECT seconds FROM UserActivityDuration WHERE user_id = {before.id} AND app_id = {app_id}")
                seconds = await cur.fetchone()
                if not seconds:
                    await cur.execute(f"INSERT INTO UserActivityDuration (user_id, app_id, seconds) VALUES ({after.id}, {app_id}, {0})")

        if user_is_playing(before):
            app_id, _ = get_app_id(before)
            sess_duration = int(time() - before.activity.start.timestamp())
            async with self.get_connection() as cur:
                await cur.execute(f"SELECT seconds FROM UserActivityDuration WHERE user_id = {before.id} AND app_id = {app_id}")
                seconds = await cur.fetchone()
                await cur.execute(f"UPDATE UserActivityDuration SET seconds = {seconds[0] + sess_duration} WHERE user_id = {before.id} AND app_id = {app_id}")


def setup(bot):
    bot.add_cog(Commands(bot))
