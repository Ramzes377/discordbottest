import discord
from discord.ext import commands
from random import randint as r
import os
import re

created_channels = {} # User_Name : Channel

create_channel_id = int(os.environ.get('Create_channel_ID'))

_categories = {discord.ActivityType.playing:   int(os.environ.get('Category_playing')),
               discord.ActivityType.streaming: int(os.environ.get('Category_steaming')),
               4:                              int(os.environ.get('Category_custom')),
               0:                              int(os.environ.get('Category_idle'))}


privileged_role_names = ['Admin']


def _channel_name_helper(member): #describe few activities to correct show
    if member.activity:
        activity_name = member.activity.name
        if len(activity_name) > 6:
            short_name = ''
            for word in re.split(r'\W', activity_name):
                short_name += word[:1] if word else ' '
            return f"|{short_name}| {member.display_name}'s channel"
        return f"|{activity_name}| {member.display_name}'s channel"
    return f"|{member.display_name}'s channel"

class Channels_manager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.leader_role_rights = discord.PermissionOverwrite(kick_members = True,
                                                    mute_members = True,
                                                    deafen_members = True,
                                                    manage_channels = True,
                                                    create_instant_invite = True)

        self.default_role_rights = discord.PermissionOverwrite(connect = True,
                                              speak = True,
                                              use_voice_activation = True,
                                              kick_members = False,
                                              mute_members = False,
                                              deafen_members = False,
                                              manage_channels = False,
                                              create_instant_invite = False)

    @commands.Cog.listener()
    async def on_ready(self):
        for cat in _categories:
            _categories[cat] = self.bot.get_channel(_categories[cat])  # getting categories from their IDs

        self.bot.create_channel = self.bot.get_channel(create_channel_id)
        self.bot.created_roles = {role.name: role for guild in self.bot.guilds for role in guild.roles}
        self.bot.privileged_roles = [self.bot.created_roles[role_name] for role_name in privileged_role_names]
        for channel in self.bot.get_all_channels( ):
            if channel.name[0] == '|':
                await channel.delete( )

        if self.bot.create_channel.members:
            user = self.bot.create_channel.members[0]
            category = _categories.get(user.activity.type if user.activity else 0)
            permissions = {user.guild.default_role: self.default_role_rights, user: self.leader_role_rights}
            channel = await user.guild.create_voice_channel(_channel_name_helper(user), category = category, overwrites = permissions)
            created_channels[user] = channel
            for user in self.bot.create_channel.members:
                await user.move_to(channel)
                
        await self.bot.change_presence(status = discord.Status.idle, activity = discord.Game('бога'))

        print(f'{type(self).__name__} starts')

    async def _sort_users_by_activity(self, user):
        category = _categories.get(user.activity.type if user.activity else 0)
        await  created_channels[user].edit(name = _channel_name_helper(user), category = category)

    async def _create_role(self, user, role_name):
        role = await user.guild.create_role(name = role_name,
                                            permissions = self.bot.created_roles['@everyone'].permissions,
                                            colour = discord.Colour(1).from_rgb(r(0, 255), r(0, 255), r(0, 255)),
                                            hoist = True)
        self.bot.created_roles[role_name] = role
        await user.add_roles(role)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after in created_channels:
            await self._sort_users_by_activity(after)

        if after.activity and after.activity.type == discord.ActivityType.playing:
            role_name = after.activity.name + ' player'
            if all(role_name != role.name for role in after.roles): #user haven't these role
                if not self.bot.created_roles.get(role_name):  #role haven't exist
                    await self._create_role(after, role_name) #create role and give it to user
                else: #role already exist
                    await after.add_roles(self.bot.created_roles[role_name]) #just give

    async def _transfer_channel(self, user):
        channel = created_channels.pop(user)
        new_leader = channel.members[0]  # New leader of these channel
        _permissions = {user: self.default_role_rights, new_leader: self.leader_role_rights}
        created_channels[new_leader] = channel
        await channel.edit(name = _channel_name_helper(new_leader), overwrites = _permissions)

    async def _create_channel(self, user):
        _category = _categories.get(user.activity.type if user.activity else 0)
        _permissions = {user.guild.default_role: self.default_role_rights, user: self.leader_role_rights}
        channel = await user.guild.create_voice_channel(_channel_name_helper(user), category = _category, overwrites = _permissions)
        created_channels[user] = channel
        await user.move_to(channel)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not after.channel or after.channel != self.bot.create_channel:  # Client LEAVE FROM CHANNEL
            if member in created_channels:
                if not created_channels[member].members:  # Client's channel is empty
                    await created_channels.pop(member).delete( )
                else:  # Client's channel isn't empty
                    await self._transfer_channel(member)

        elif after.channel == self.bot.create_channel:  # Creating new channel
            if member not in created_channels:  # if not created already
                await self._create_channel(member)
            else:  # if created then just back client to himself channel
                await member.move_to(created_channels[member])


def setup(bot):
    bot.add_cog(Channels_manager(bot))
