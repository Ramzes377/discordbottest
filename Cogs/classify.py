import discord
from discord.ext import commands
import os
import re
import datetime


create_channel_id = int(os.environ.get('Create_channel_ID'))
logger_id = int(os.environ.get('Logger_channel_ID'))


time_formatter = lambda time: "%02d:%02d:%02d - %02d.%02d.%04d" % (time.hour, time.minute, time.second, time.day, time.month,  time.year)


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

def is_leap_year(year):
    return True if not year % 400 else False if not year % 100 else True if not year % 4 else False

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

        await self.bot.change_presence(status = discord.Status.idle, activity = discord.Game('бога'))
        print(f'{type(self).__name__} starts')

    async def _sort_users_by_activity(self, user):
        category = _categories.get(user.activity.type if user.activity else 0)
        channel = self.get_private_channel(user)
        await channel.edit(name = _channel_name_helper(user), category = category)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        t = tuple(self.bot.db_cursor.execute("SELECT * FROM ChannelsINFO WHERE user_id = ?",
                                             (after.id,)))
        if t:
            await self._sort_users_by_activity(after)

    async def _transfer_channel(self, user):
        channel = self.get_private_channel(user)
        new_leader = channel.members[0]  # New leader of these channel
        self.bot.db_cursor.execute("UPDATE ChannelsINFO SET user_id = ? WHERE channel_id = ?",
                                   (new_leader.id, channel.id))
        self.bot.db.commit()
        _permissions = {user: self.default_role_rights, new_leader: self.leader_role_rights}
        await channel.edit(name = _channel_name_helper(new_leader), overwrites = _permissions)

    async def _create_channel(self, user):
        category = _categories.get(user.activity.type if user.activity else 0)
        permissions = {user.guild.default_role: self.default_role_rights, user: self.leader_role_rights}
        channel = await user.guild.create_voice_channel(_channel_name_helper(user),
                                                        category=category,
                                                        overwrites=permissions)
        self.bot.db_cursor.execute("INSERT INTO ChannelsINFO VALUES (?, ?)",
                                   (user.id, channel.id))
        self.bot.db.commit()
        await user.move_to(channel)
        return channel


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        try:
            member_have_channel = tuple(self.bot.db_cursor.execute(
                "SELECT channel_id FROM ChannelsINFO WHERE user_id = ?",
                (member.id,)))[0]
            channel = self.bot.get_channel(member_have_channel[0]) #his channel
            if not channel:
                self.bot.db_cursor.execute("DELETE FROM ChannelsINFO WHERE user_id = ?", (member.id,))
        except IndexError:
            member_have_channel = False

        if after.channel == self.bot.create_channel:  #user try to create channel
            if member_have_channel: #if channel already exist
                await member.move_to(channel) #just send user to his channel
            else: #channel still don't exist
                ch = await self._create_channel(member) #create channel
                await self.start_session_message(member, ch) #send session message
        else: #user join any non-create channel two cases:  1) He has channel and join to it;
                                                           #2) He hasn't channel and try to join to channel of another user
            if member_have_channel:
                if after.channel != channel: #user join to channel of another user from his channel
                    if not channel.members:  #handle his channel fate; if his channel is empty write end session message and delete channel
                        await self.end_session_message(channel)
                        await channel.delete()
                        self.bot.db_cursor.execute("DELETE FROM ChannelsINFO WHERE user_id = ?", (member.id,))
                    else: #if channel isn't empty just transfer channel
                        await self._transfer_channel(member)
            if after.channel:
                self.bot.db_cursor.execute("INSERT INTO SessionsMembers VALUES (?, ?)",
                                           (after.channel.id, member.id))
        self.bot.db.commit()
        

       async def start_session_message(self, creator, channel):
        day_of_year, is_leap_year = session_id()
        past_sessions_counter, current_sessions_counter = tuple(self.bot.db_cursor.execute(
            "SELECT past_sessions_counter, current_sessions_counter FROM SessionsID WHERE current_day = ?",
            (day_of_year,)))[0]

        sess_id = f'№ {1 + past_sessions_counter + current_sessions_counter} | {day_of_year}/{366 if is_leap_year else 365}'

        dt_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) # GMT+3
        text_time = time_formatter(dt_time)
        embed_obj = discord.Embed(title=f"{creator.display_name} начал сессию {sess_id}",
                                  description=f'\nВремя начала: {text_time}\nСессия активна...',
                                  color = discord.Color.green())
        msg = await self.bot.logger_channel.send(embed = embed_obj)

        self.bot.db_cursor.execute("UPDATE SessionsID SET current_sessions_counter = ? WHERE current_day = ?",
                                   (current_sessions_counter + 1, day_of_year))
        self.bot.db_cursor.execute("INSERT INTO SessionsINFO VALUES (?, ?, ?, ?, ?)",
                                   (channel.id, creator.id, day_of_year, sess_id, msg.id))
        self.bot.db_cursor.execute("INSERT INTO SessionsMembers VALUES (?, ?)",
                                   (channel.id, creator.id))

        self.bot.db.commit()


    async def end_session_message(self, channel):
        creator_id, start_day, session_id, message_id = tuple(self.bot.db_cursor.execute(
            "SELECT creator_id, start_day, session_id, message_id FROM SessionsINFO WHERE channel_id = ?",
            (channel.id,)))[0]

        past_sessions_counter, current_sessions_counter = tuple(self.bot.db_cursor.execute(
            "SELECT past_sessions_counter, current_sessions_counter FROM SessionsID WHERE current_day = ?",
            (start_day,)))[0]

        self.bot.db_cursor.execute("UPDATE SessionsID SET current_sessions_counter = ? WHERE current_day = ?",
                                   (current_sessions_counter - 1, start_day))

        msg = await self.bot.logger_channel.fetch_message(message_id)

        start_time = msg.created_at + datetime.timedelta(0, 0, 0, 0, 0, 3, 0)
        end_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0)  # GMT+3

        sess_duration = end_time - start_time

        if sess_duration.seconds > 120:
            self.bot.db_cursor.execute("UPDATE SessionsID SET past_sessions_counter = ? WHERE current_day = ?",
                                       (past_sessions_counter + 1, start_day))

            users_ids = tuple(self.bot.db_cursor.execute("SELECT member_id FROM SessionsMembers WHERE channel_id = ?",
                                                         (channel.id,)))

            embed_obj = discord.Embed(title=f"Сессия {session_id} окончена!",
                                      color=discord.Color.red())
            embed_obj.add_field(name='Создатель', value=f'<@{creator_id}>')
            embed_obj.add_field(name='Время начала', value=f'{time_formatter(start_time)}')
            embed_obj.add_field(name='Время окончания', value=f'{time_formatter(end_time)}')
            embed_obj.add_field(name='Продолжительность', value=f"{str(sess_duration).split('.')[0]}")
            embed_obj.add_field(name='Участники', value=f"{', '.join(map(lambda id: f'<@{id[0]}>', set(users_ids)))}")

            await msg.edit(embed = embed_obj)
            self.bot.db_cursor.execute("DELETE FROM SessionsMembers WHERE channel_id = ?", (channel.id,))
        else:
            await msg.delete()

        self.bot.db.commit()

    def get_private_channel(self, user):
        t = tuple(self.bot.db_cursor.execute("SELECT channel_id FROM ChannelsINFO WHERE user_id = ?", (user.id,)))
        return self.bot.get_channel(t[0][0])
            
            
def setup(bot):
    bot.add_cog(Channels_manager(bot))

