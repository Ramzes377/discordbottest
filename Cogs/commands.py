import discord
import asyncio
from discord.ext import commands
from .classify import _hash, get_app_id
import asyncio_extras
import datetime
from time import time



class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{type(self).__name__} starts')
        
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.activity and after.activity.type == discord.ActivityType.playing:
            app_id, _ = get_app_id(after)
            async with self.get_connection() as cur:
                await cur.execute(f"SELECT seconds FROM UserActivityDuration WHERE user_id = {before.id} AND app_id = {app_id}")
                seconds = await cur.fetchone()
                if not seconds:
                    await cur.execute(f"INSERT INTO UserActivityDuration (user_id, app_id, seconds) VALUES ({after.id}, {app_id}, {0})")

        if before.activity and before.activity.type == discord.ActivityType.playing:
            app_id, _ = get_app_id(before)
            sess_duration = int(time() - before.activity.start.timestamp())
            async with self.get_connection() as cur:
                await cur.execute(f"SELECT seconds FROM UserActivityDuration WHERE user_id = {before.id} AND app_id = {app_id}")
                seconds = await cur.fetchone()
                await cur.execute(f"UPDATE UserActivityDuration SET seconds = {seconds[0] + sess_duration} WHERE user_id = {before.id} AND app_id = {app_id}")


    @commands.command()
    async def activity(self, ctx):
        '''Дает пользователю продолжительность активности у соответствующей игре ИГРОВОЙ роли!
           Введите !activity @роль или Введите !activity @роль @роль . . .'''
        member = ctx.message.author
        channel = ctx.message.channel
        requested_games = ctx.message.role_mentions

        if len(requested_games) == 0:
            await self.send_removable_message(ctx, 'Отсутствуют упоминания игровых ролей! Введите !help activity', 20)
            return

        async with self.get_connection() as cur:
            for role in requested_games:
                await cur.execute(f"SELECT application_id FROM CreatedRoles WHERE role_id = {role.id}")
                app_id = await cur.fetchone()  # it's created role
                if app_id:
                    await cur.execute(f"SELECT seconds FROM UserActivityDuration WHERE user_id = {member.id} AND app_id = {app_id[0]}")
                    seconds = await cur.fetchone()  # it's created role
                    total_time = datetime.timedelta(seconds=seconds[0])

                    embed_obj = discord.Embed(title=f"В игре {role.name} вы провели:",
                                              color=role.color)
                    embed_obj.description = str(total_time).split('.')[0]

                    await cur.execute(f'SELECT icon_url FROM ActivitiesINFO WHERE application_id = {app_id[0]}')
                    thumbnail_url = await cur.fetchone()
                    if thumbnail_url:
                        embed_obj.set_thumbnail(url=thumbnail_url[0])

                    bot = channel.guild.get_member(self.bot.user.id)
                    embed_obj.set_footer(text=bot.display_name, icon_url=bot.avatar_url)

                    message = await member.send(embed = embed_obj)
                    await asyncio.sleep(30)
                    await message.delete()


    @commands.command()
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
            return

        with self.get_connection() as cur:
            for role in requested_roles:
                await cur.execute(f"SELECT * FROM CreatedRoles WHERE role_id = {role.id}")
                if await cur.fetchone(): #it's created role
                    if not role in member.roles: #member hasn't these role
                         await member.add_roles(role)
                    else: #member already have these role
                        await self.send_removable_message(ctx, f'У вас уже есть роль {role.mention}!', 15)
                else: #wrong role
                    await self.send_removable_message(ctx, f'{role.mention} не относится к игровым ролям!', 15)

        await asyncio.sleep(10)
        await ctx.message.delete()



    @commands.command()
    async def clean(self, ctx, messages_count = 200):
        '''Privileged_roles only'''
        if self.is_admin(ctx.message.author):
            channel = ctx.message.channel
            async for message in channel.history(limit = messages_count):
                await message.delete()
        else:
            await self.rights_violation(ctx)
            await ctx.message.delete( )


    def is_admin(self, user, guild):
        return user.id == guild.owner_id


    async def send_removable_message(self, ctx, message, delay = 5):
        message = await ctx.send(message)
        await asyncio.sleep(delay)
        await message.delete()


    async def rights_violation(self, ctx):
        await self.send_removable_message(ctx, "У вас нет прав для этого!", 10)
        
        
    @asyncio_extras.async_contextmanager
    async def get_connection(self):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                yield cur



def setup(bot):
    bot.add_cog(Commands(bot))
