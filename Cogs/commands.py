import discord
import asyncio
from discord.ext import commands



class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{type(self).__name__} starts')


    @commands.command()
    async def color_me(self, ctx, red = 0, green = 0, blue = 0):
        """Set user role color. Type:\n!color_me 'red (0-255)' 'green (0-255)' 'blue (0-255)'"""
        if 0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255:
            user = ctx.message.author
            guild = ctx.message.guild
            user_top_role = guild.default_role

            for role in user.roles:
                if role.hoist and role.position > user_top_role.position:
                    user_top_role = role
            if user_top_role == guild.default_role:
                await self.send_removable_message(ctx, "У вас нет отдельно отображаемых ролей!")
                return

            color = discord.Color(1).from_rgb(int(red), int(green), int(blue))
            await role.edit(colour = color)
            await self.send_removable_message(ctx, f"Успешно изменён цвет для роли {user_top_role.name}.")
        else:
            await self.send_removable_message(ctx, "Некорректный ввод цвета. Введите !help color_me", 20)

        await asyncio.sleep(15)
        await ctx.message.delete( )


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

        for role in requested_roles:
            self.bot.db_cursor.execute(f"SELECT * FROM CreatedRoles WHERE role_id = {role.id}")
            if self.bot.db_cursor.fetchone(): #it's created role
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


def setup(bot):
    bot.add_cog(Commands(bot))