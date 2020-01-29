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
        self.role_change_colour.start( )

    @tasks.loop(seconds = 200)
    async def role_change_colour(self):
        if any(user.status == discord.Status.online for user in self.bot.created_roles['Admin'].members):
            try:
                color = await anext(gradient_cycle)
                await self.bot.created_roles['Admin'].edit(colour = color)
            except discord.HTTPException:
                pass

def setup(bot):
    bot.add_cog(Role_colors(bot))