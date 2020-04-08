import discord
from discord.ext import commands
import os
import re
import datetime

created_channels = {} # User_Name : Channel
sessions = {} # Channel : start_time

create_channel_id = int(os.environ.get('Create_channel_ID'))
logger_id = int(os.environ.get('Logger_channel_ID'))

_categories = {discord.ActivityType.playing:   int(os.environ.get('Category_playing')),
               discord.ActivityType.streaming: int(os.environ.get('Category_steaming')),
               4:                              int(os.environ.get('Category_custom')),
               0:                              int(os.environ.get('Category_idle'))}


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

def decorator(function):
    sessions_counter = dict.fromkeys(range(1, 367), 0)
    def wrapper():
        day, is_leap = function()
        if not day:
            for key in sessions_counter:
                sessions_counter[key] = 0
        sessions_counter[day] += 1
        yield f'№{sessions_counter[day]} | {day}/{366 if is_leap else 365}'
    return wrapper

def is_leap_year(year):
    return True if not year % 400 else False if not year % 100 else True if not year % 4 else False

@decorator
def session_id():
    cur_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) # GMT+3
    start_of_year = datetime.datetime(cur_time.year, 1, 1, 0, 0, 0, 0)
    delta = cur_time - start_of_year
    return delta.days + 1, is_leap_year(cur_time.year)
  
  
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
        self.bot.logger_channel = self.bot.get_channel(logger_id)

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

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after in created_channels:
            await self._sort_users_by_activity(after)

    async def _transfer_channel(self, user):
        channel = created_channels.pop(user)
        new_leader = channel.members[0]  # New leader of these channel
        _permissions = {user: self.default_role_rights, new_leader: self.leader_role_rights}
        created_channels[new_leader] = channel
        await channel.edit(name = _channel_name_helper(new_leader), overwrites = _permissions)

    async def _create_channel(self, user):
        category = _categories.get(user.activity.type if user.activity else 0)
        permissions = {user.guild.default_role: self.default_role_rights, user: self.leader_role_rights}
        channel = await user.guild.create_voice_channel(_channel_name_helper(user), category=category, overwrites=permissions)
        created_channels[user] = channel
        await user.move_to(channel)
        sessions[channel] = await self.start_session_message(user, channel)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not after.channel or after.channel != self.bot.create_channel:  # Client LEAVE FROM CHANNEL
            if member in created_channels:
                if not created_channels[member].members:  # Client's channel is empty
                    await self.end_session_message(created_channels[member])
                    await created_channels.pop(member).delete( )
                else:  # Client's channel isn't empty
                    await self._transfer_channel(member)
            elif after.channel:
                sessions[after.channel][2].add(member)

        elif after.channel == self.bot.create_channel:  # Creating new channel
            if member not in created_channels:  # if not created already
                await self._create_channel(member)
            else:  # if created then just back client to himself channel
                await member.move_to(created_channels[member])

    async def start_session_message(self, user, channel):
        time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) # GMT+3
        text_time = "%02d:%02d:%02d - %02d.%02d.%04d" % (time.hour, time.minute, time.second, time.day, time.month,  time.year)
        sess_id = next(session_id())
        await self.bot.logger_channel.send(f"{user.display_name} начал сессию {sess_id} в {text_time}")
        return time, sess_id, set([user])

    async def end_session_message(self, channel):
        start_time, sess_id, members = sessions.pop(channel)
        sess_duration = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) - start_time
        await self.bot.logger_channel.send(f"\nCессия {sess_id} окончена. \nПродолжительность: {str(sess_duration).split('.')[0]}\nУчастники: {', '.join(map(lambda m: m.display_name, members))}")

def setup(bot):
    bot.add_cog(Channels_manager(bot))

