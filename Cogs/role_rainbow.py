import discord
from discord.ext import commands, tasks
from aioitertools import cycle, next as anext


def get_spiral_gradient(r = 120, step = 5):
    from math import sin, cos, radians
    first = []; second = []
    num_of_spins = 3
    x_degrees = num_of_spins * 360
    dt = (step * 2 * r)/x_degrees
    t1 =  (255 - 2 * r)/2; t2 = 255 - t1
    for x in range(0, x_degrees, step):
        angle = radians(x)
        first.append(discord.Colour(1).from_rgb(int(255 / 2 + r * cos(angle)), int(255 / 2 + r * sin(angle)), int(t1)))
        second.append(discord.Colour(1).from_rgb(int(255 / 2 + r * cos(angle)), int(255 / 2 + r * sin(angle)), int(t2)))
        t1 += dt; t2 -= dt
    return first + second


gradient_cycle = cycle(get_spiral_gradient())


class Role_colors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{type(self).__name__} starts')

    @tasks.loop(seconds = 1)
    async def role_change_colour(self):
        if any(user.status == discord.Status.online for user in self.bot.created_roles['Admin'].members):
            try:
                color = await anext(gradient_cycle)
                await self.bot.created_roles['Admin'].edit(colour = color)
            except discord.HTTPException:
                pass

    @commands.command()
    async def color_me(self, ctx, red = 0, green = 0, blue = 0):
        """Set user role color. Type:\n!color_me 'red (0-255)' 'green (0-255)' 'blue (0-255)'"""
        if 0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255:
            user = ctx.message.author
            user_role = self.bot.created_roles['@everyone']

            for role in user.roles:
                if role.hoist and role.position > user_role.position:
                    user_role = role

            if user_role == self.bot.created_roles['@everyone']:
                await ctx.send("У вас нет отдельно отображаемых ролей!")
                return

            color = discord.Color(1).from_rgb(int(red), int(green), int(blue))
            await role.edit(colour = color)
            message = await ctx.send(f"Успешно изменён цвет для роли {user_role.name}.")
        else:
            message = await ctx.send("Некорректный ввод цвета. Введите !help color_me")

        await asyncio.sleep(15)
        await ctx.message.delete( )
        await message.delete( )

    @commands.command()
    async def start_rainbow(self, ctx):
        '''Admin only'''
        try:
            if self.is_admin(ctx.message.author):
                self.role_change_colour.start( )
            else:
                await self.rights_violation(ctx)
        except RuntimeError:
            await self.send_removable_message(ctx, "Ошибка! Событийный цикл уже запущен!", 10)
        finally:
            await ctx.message.delete( )

    @commands.command()
    async def stop_rainbow(self, ctx):
        '''Admin only'''
        if self.is_admin(ctx.message.author):
            self.role_change_colour.stop( )
            await self.send_removable_message(ctx, "Остановлен событийный цикл.", 10)
        else:
            await self.rights_violation(ctx)

    @commands.command()
    async def clean_channel(self, ctx, messages_count = 200):
        '''Privileged_roles only'''
        if any(role in self.bot.privileged_roles for role in ctx.message.author.roles):
            channel = ctx.message.channel
            async for message in channel.history(limit = messages_count):
                await message.delete()
        else:
            await self.rights_violation(ctx)
            await ctx.message.delete( )

    def is_admin(self, user):
        return self.bot.created_roles['Admin'] in user.roles


    async def send_removable_message(self, ctx, message, delay = 5):
        message = await ctx.send(message)
        await asyncio.sleep(delay)
        await message.delete()


    async def rights_violation(self, ctx):
        await self.send_removable_message(ctx, "У вас нет прав для этого!", 10)

def setup(bot):
    bot.add_cog(Role_colors(bot))
