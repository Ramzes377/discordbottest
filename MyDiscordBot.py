import discord
from discord.ext import commands
from discord.ext.tasks import loop
from aioitertools import cycle
from aioitertools import next as anext
from random import randint as r

def get_spiral_gradient(r = 120, step = 5):
    from math import sin, cos, radians
    first = []; second = []
    num_of_spins = 2
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

created_channels = {} # User_Name : Channel

_categories = {discord.ActivityType.playing:   531556241663721492,
               discord.ActivityType.streaming: 669927306562895900,
               4:                              531504241500749835,
               0:                              531504241500749835}

create_channel_id = 668969213368729660

bot = commands.Bot(command_prefix = '!')

def _channel_name_helper(member): #describe few activities to correct show
    if member.activity:
        activity_name = member.activity.name
        if activity_name.lower().replace(' ', '') == "pathofexile":
            return f"|PoE| {member.display_name}'s channel"
        elif activity_name.lower().replace(' ', '') == "dota2":
            return f"|Dota| {member.display_name}'s channel"
        elif activity_name.lower().replace(' ', '')[:9] == 'minecraft':
            return f"|Minecraft| {member.display_name}'s channel"
        elif activity_name == 'Custom Status':
            return f"|{member.activity.state}| {member.display_name}'s channel"
        else:
            return f"|{member.activity.name}| {member.display_name}'s channel"
    return f"|{member.display_name}'s channel"


@bot.event
async def on_ready():
    for cat in _categories:
        _categories[cat] = bot.get_channel(_categories[cat])  # getting categories from their IDs

    bot.create_channel = bot.get_channel(create_channel_id)
    bot.created_roles = {role.name: role for guild in bot.guilds for member in guild.members for role in member.roles}
    print('Bot have been started!')
    for channel in bot.get_all_channels( ):
        if channel.name[0] == '|':
            await channel.delete( )
    await bot.change_presence(status = discord.Status.idle, activity = discord.Game('бога') )
    change_colour.start( )


@bot.event
async def on_member_update(before, after):
    if after.display_name in created_channels:
        category = _categories.get(after.activity.type if after.activity else 0)
        await created_channels[after.display_name].edit(name = _channel_name_helper(after), category = category)

    if after.activity and after.activity.type == discord.ActivityType.playing:
        role_name = after.activity.name + ' player'
        if all(role_name != role.name for role in after.roles):
            if not bot.created_roles.get(role_name):
                guild = after.guild
                role = await guild.create_role(name = role_name,
                                               permissions = bot.created_roles['@everyone'].permissions,
                                               colour = discord.Colour(1).from_rgb(r(0, 255), r(0, 255), r(0, 255)),
                                               hoist = True)
                bot.created_roles[role_name] = role
                await after.add_roles(role)
            else:
                await after.add_roles(bot.created_roles[role_name])


@bot.event
async def on_voice_state_update(member, before, after):
    member_name = member.display_name
    if not after.channel or after.channel != bot.create_channel: # Client LEAVE FROM CHANNEL
        if member_name in created_channels:
            if not created_channels[member_name].members: #Client's channel is empty
                await created_channels.pop(member_name).delete( )
            else: # Client's channel isn't empty
                channel = created_channels.pop(member_name)
                new_leader = channel.members[0] #New leader of these channel
                created_channels[new_leader.display_name] = channel
                await created_channels[new_leader.display_name].edit(name = _channel_name_helper(new_leader))

    elif after.channel == bot.create_channel: #Creating new channel
        if member_name not in created_channels: #if not created already
            category = created_categories.get(member.activity.type if member.activity else 0)
            channel_name = _channel_name_helper(member)
            overwrites = {member.guild.default_role: discord.PermissionOverwrite(connect = True,
                                                                                 speak = True,
                                                                                 use_voice_activation = True),
                          member: discord.PermissionOverwrite(kick_members = True,
                                                              mute_members = True,
                                                              deafen_members = True,
                                                              manage_channels = True,
                                                              create_instant_invite = True)}
            channel = await member.guild.create_voice_channel(channel_name, category = category, overwrites = overwrites)
            created_channels[member_name] = channel
            await member.move_to(channel)
        else: #if created then just back client to himself channel
            await member.move_to(created_channels[member_name])


@loop(minutes = 1)
async def change_colour():
    if any(user.status == discord.Status.online for user in bot.created_roles['Admin'].members):
        try:
            color = await anext(gradient_cycle)
            await bot.created_roles['Admin'].edit(colour = color)
        except discord.HTTPException:
            pass

token = os.environ.get('TOKEN')
bot.run(str(token))
