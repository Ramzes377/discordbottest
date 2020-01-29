import discord
from discord.ext import commands
from random import randint as r
import os

created_channels = {} # User_Name : Channel

create_channel_id = int(os.environ.get('Create_channel_ID'))

_categories = {discord.ActivityType.playing:   int(os.environ.get('Category_playing')),
               discord.ActivityType.streaming: int(os.environ.get('Category_steaming')),
               4:                              int(os.environ.get('Category_custom')),
               0:                              int(os.environ.get('Category_idle'))}


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

class Channel_creator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for cat in _categories:
            _categories[cat] = self.bot.get_channel(_categories[cat])  # getting categories from their IDs

        self.bot.create_channel = self.bot.get_channel(create_channel_id)
        self.bot.created_roles = {role.name: role for guild in self.bot.guilds for member in guild.members for role in
                             member.roles}
        for channel in self.bot.get_all_channels( ):
            if channel.name[0] == '|':
                await channel.delete( )
        await self.bot.change_presence(status = discord.Status.idle, activity = discord.Game('бога'))
        print(f'{type(self).__name__} starts')

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.display_name in created_channels:
            category = _categories.get(after.activity.type if after.activity else 0)
            await created_channels[after.display_name].edit(name = _channel_name_helper(after), category = category)

        if after.activity and after.activity.type == discord.ActivityType.playing:
            role_name = after.activity.name + ' player'
            if all(role_name != role.name for role in after.roles):
                if not self.bot.created_roles.get(role_name):
                    guild = after.guild
                    role = await guild.create_role(name = role_name,
                                                   permissions = self.bot.created_roles['@everyone'].permissions,
                                                   colour = discord.Colour(1).from_rgb(r(0, 255), r(0, 255), r(0, 255)),
                                                   hoist = True)
                    self.bot.created_roles[role_name] = role
                    await after.add_roles(role)
                else:
                    await after.add_roles(self.bot.created_roles[role_name])

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        member_name = member.display_name
        if not after.channel or after.channel != self.bot.create_channel:  # Client LEAVE FROM CHANNEL
            if member_name in created_channels:
                if not created_channels[member_name].members:  # Client's channel is empty
                    await created_channels.pop(member_name).delete( )
                else:  # Client's channel isn't empty
                    channel = created_channels.pop(member_name)
                    new_leader = channel.members[0]  # New leader of these channel
                    _permissions = {member: discord.PermissionOverwrite(connect = True,
                                                                        speak = True,
                                                                        use_voice_activation = True),
                                    new_leader: discord.PermissionOverwrite(kick_members = True,
                                                                            mute_members = True,
                                                                            deafen_members = True,
                                                                            manage_channels = True,
                                                                            create_instant_invite = True)}
                    created_channels[new_leader.display_name] = channel
                    await created_channels[new_leader.display_name].edit(name = _channel_name_helper(new_leader))

        elif after.channel == self.bot.create_channel:  # Creating new channel
            if member_name not in created_channels:  # if not created already
                _category = _categories.get(member.activity.type if member.activity else 0)
                channel_name = _channel_name_helper(member)
                _permissions = {member.guild.default_role: discord.PermissionOverwrite(connect = True,
                                                                                       speak = True,
                                                                                       use_voice_activation = True),
                                member: discord.PermissionOverwrite(kick_members = True,
                                                                    mute_members = True,
                                                                    deafen_members = True,
                                                                    manage_channels = True,
                                                                    create_instant_invite = True)}
                channel = await member.guild.create_voice_channel(channel_name, category = _category,
                                                                  overwrites = _permissions)
                created_channels[member_name] = channel
                await member.move_to(channel)
            else:  # if created then just back client to himself channel
                await member.move_to(created_channels[member_name])


def setup(bot):
    bot.add_cog(Channel_creator(bot))

