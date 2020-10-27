import discord
import asyncio
import re
import datetime
import aiohttp
import os
import numpy as np
from discord.ext import commands
from random import randint
from sklearn.cluster import KMeans
from cv2 import cvtColor, COLOR_BGR2RGB, imdecode
from hashlib import sha3_224
from asyncio_extras import async_contextmanager
from itertools import chain


create_channel_id = int(os.environ.get('Create_channel_ID'))
logger_id = int(os.environ.get('Logger_channel_ID'))
role_request_id = int(os.environ.get('Role_request'))

categories = {discord.ActivityType.playing:   int(os.environ.get('Category_playing')),
               discord.ActivityType.custom:   int(os.environ.get('Category_custom')),
               0:                              int(os.environ.get('Category_idle'))}

time_formatter = lambda time: "%02d:%02d:%02d - %02d.%02d.%04d" % (time.hour, time.minute, time.second, time.day, time.month,  time.year)

_hash = lambda string: int(str(sha3_224(string.encode(encoding='utf8')).hexdigest()), 16) % 10**10

user_is_playing = lambda user: user.activity and user.activity.type == discord.ActivityType.playing

get_category = lambda user: categories[user.activity.type] if user.activity else categories[0]

is_leap_year = lambda year: True if not year % 400 else False if not year % 100 else True if not year % 4 else False

get_pseudo_random_color = lambda: (randint(70, 255), randint(70, 255), randint(70, 255))

flatten = lambda collection: chain(*collection) if collection is not None else []



def DominantColors(img, clusters):
    img = cvtColor(img, COLOR_BGR2RGB)
    img = img.reshape((img.shape[0] * img.shape[1], 3))
    kmeans = KMeans(n_clusters=clusters)
    kmeans.fit(img)
    colors = kmeans.cluster_centers_
    return colors.astype(int)


def session_id():
    cur_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) # GMT+3
    start_of_year = datetime.datetime(cur_time.year, 1, 1, 0, 0, 0, 0)
    delta = cur_time - start_of_year
    return delta.days + 1, is_leap_year(cur_time.year)


def get_activity_name(user): #describe few activities to correct show
    if user.activity:
        activity_title = user.activity.name
        if len(activity_title) > 6:
            short_name = re.compile('[^a-zA-Z0-9 +]').sub('', activity_title)[:6] + '..'
            return f"[{short_name}] {user.display_name}'s channel"
        return f"[{activity_title}] {user.display_name}'s channel"
    return f"{user.display_name}'s channel"


def get_app_id(activity_interval):
    try:
        app_id, is_real = activity_interval.activity.application_id, True
    except AttributeError:
        app_id, is_real = _hash(activity_interval.activity.name), False
    return app_id, is_real


class Channels_manager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._is_five_mins_pass = True
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
        await asyncio.sleep(3)
        for cat in categories:
            categories[cat] = self.bot.get_channel(categories[cat])  # getting categories from their IDs

        self.bot.create_channel = self.bot.get_channel(create_channel_id)
        self.bot.logger_channel = self.bot.get_channel(logger_id)

        await self._sort_roles()
        await self._manage_created_channels()
        await self._delete_removed_emoji()

        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=" за каналами"))
        print(f'{type(self).__name__} starts')


    async def _sort_roles(self):
        guild = self.bot.create_channel.guild
        roles = guild.roles
        sorted_roles = sorted(roles, key=lambda role: len(role.members), reverse=True)

        async with self.get_connection() as cur:
            for role in sorted_roles:
                if role.hoist:
                    await cur.execute(f"SELECT * FROM CreatedRoles WHERE role_id = {role.id}")
                    if await cur.fetchone():
                        await role.edit(position=len(role.members) if len(role.members) > 0 else 1)

    async def _manage_created_channels(self):
        async with self.get_connection() as cur:
            active_channels = await cur.execute("SELECT channel_id FROM ChannelsINFO")
        active_channels = flatten(active_channels)
        if active_channels:
            for channel_id in active_channels:
                channel = self.bot.get_channel(channel_id)
                channel_exist = channel is not None
                if channel_exist:
                    channel_empty = not channel.members
                    if channel_empty:
                        await self._end_session_message(channel)
                        await channel.delete()
                    else:
                        await cur.execute(f"SELECT user_id FROM ChannelsINFO WHERE channel_id = {channel_id}")
                        user_id = await cur.fetchone()
                        user = self.bot.get_user(*user_id)
                        leader_leave = not user in channel.members
                        if leader_leave:
                            await self._transfer_channel(user)
                else:
                    await cur.execute(f"DELETE FROM ChannelsINFO WHERE channel_id = {channel_id}")

    async def _delete_removed_emoji(self):
        channel = self.bot.get_channel(role_request_id)
        story = await channel.history(limit=None).flatten()
        if len(story) > 0:
            self.msg = story[0]
            guild = self.msg.guild
            for reaction in self.msg.reactions:
                if not reaction.emoji in guild.emojis:
                    await self.msg.remove_reaction(reaction.emoji, guild.get_member(self.bot.user.id))
                    async with self.get_connection() as cur:
                        await cur.execute(f"DELETE FROM CreatedEmoji WHERE emoji_id = {reaction.emoji.id}")
        else:
            self.msg = await channel.send("Нажмите на иконку игры, чтобы получить соответствующую игровую роль!")


    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        await self._show_activity(after)


    async def _show_activity(self, user):
        channel = await self.get_user_channel(user.id)
        if user_is_playing(user):
            if channel is not None:
                await self._sort_channels_by_activity(user)
                await self._logging_activities(user)
            await self._link_gamerole_with_user(user)

    async def _sort_channels_by_activity(self, user):
        channel = await self.get_user_channel(user.id)
        channel_name = get_activity_name(user)
        category = get_category(user)
        try:
            await asyncio.wait_for(channel.edit(name=channel_name, category=category), timeout=5.0)
        except asyncio.TimeoutError:
            await channel.edit(category=category)
            print('Trying to rename channel but Discord restrictions :(')

    async def _link_gamerole_with_user(self, after):
        app_id, is_real = get_app_id(after)
        role_name = after.activity.name
        guild = after.guild
        async with self.get_connection() as cur:
            await cur.execute(f"SELECT role_id FROM CreatedRoles WHERE application_id = {app_id}")
            created_role = await cur.fetchone()
            if created_role:  # role already exist
                role = guild.get_role(created_role[0])  # get role
                if not role in after.roles:  # check user have these role
                    await after.add_roles(role)
            else:
                color = await self._create_activity_emoji(guild, app_id) if is_real else get_pseudo_random_color()
                if color:
                    role = await guild.create_role(name=role_name, permissions=guild.default_role.permissions,
                                                   colour=discord.Colour(1).from_rgb(*color), hoist=True, mentionable=True)
                    await cur.execute(f"INSERT INTO CreatedRoles (application_id, role_id) VALUES ({app_id}, {role.id})")
                    await after.add_roles(role)

    async def _create_activity_emoji(self, guild, app_id):
        async with self.get_connection() as cur:
            await cur.execute(f'SELECT * FROM CreatedEmoji WHERE application_id = {app_id}')
            if await cur.fetchone():
                return
            await cur.execute(f'SELECT name, icon_url FROM ActivitiesINFO WHERE application_id = {app_id}')
            name, thumbnail_url = await cur.fetchone()
            name = re.compile('[^a-zA-Z0-9]').sub('', name)[:32]
            thumbnail_url = thumbnail_url[:-10]
            async with aiohttp.ClientSession() as session:
                async with session.get(thumbnail_url) as response:
                    content = await response.read()

            if not content:
                return get_pseudo_random_color()

            emoji = await guild.create_custom_emoji(name=name, image=content)
            await cur.execute(f"INSERT INTO CreatedEmoji (application_id, emoji_id) VALUES ({app_id}, {emoji.id})")
            await self._edit_role_giver_message(emoji.id)
            img_np = imdecode(np.frombuffer(content, dtype='uint8'), 1)
            return DominantColors(img_np, 3)[0]

    async def _edit_role_giver_message(self, emoji_id):
        emoji = self.bot.get_emoji(emoji_id)
        try:
            await self.msg.add_reaction(emoji)
        except discord.errors.Forbidden:
            channel = self.msg.channel
            self.msg = await channel.send("Нажмите на иконку игры, чтобы получить соответствующую игровую роль!")
            await self.msg.add_reaction(emoji)

    async def _logging_activities(self, user):
        app_id, is_real = get_app_id(user)

        async with self.get_connection() as cur:
            await cur.execute(f"SELECT channel_id FROM SessionsMembers WHERE member_id = {user.id}") #recognize that's these user member of session
            user_sessions = await cur.fetchall() #all of his sessions
            user_sessions = flatten(user_sessions)
            finded_channel = None
            for channel_id in user_sessions: #user member of atleast one session
                channel = self.bot.get_channel(channel_id)
                if channel is not None and user in channel.members:
                    finded_channel = channel
                    break

            if finded_channel is not None:
                await cur.execute(f"SELECT role_id FROM CreatedRoles WHERE application_id = {app_id}")
                associate_role = await cur.fetchone()
                await cur.execute(f"INSERT INTO SessionsActivities (channel_id, associate_role) VALUES ({finded_channel.id}, {associate_role[0]})")
                if is_real:
                    await self._update_message_icon(app_id, finded_channel.id)

    async def _update_message_icon(self, app_id, channel_id):
        async with self.get_connection() as cur:
            await cur.execute(f"SELECT message_id FROM SessionsINFO WHERE channel_id = {channel_id}")
            message_id = await cur.fetchone()
            await cur.execute(f'SELECT icon_url FROM ActivitiesINFO WHERE application_id = {app_id}')
            thumbnail_url = await cur.fetchone()
        if thumbnail_url:
            msg = await self.bot.logger_channel.fetch_message(*message_id)
            msg_embed = msg.embeds[0]
            msg_embed.set_thumbnail(url=thumbnail_url[0])
            await msg.edit(embed=msg_embed)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        await self._manage_channels(member, after)


    async def _manage_channels(self, member, after):
        channel = await self.get_user_channel(member.id) #try to get user's channel
        user_join_create_channel = after.channel == self.bot.create_channel
        user_join_own_channel = after.channel == channel
        if user_join_create_channel:
            await self._user_try_create_channel(member, channel)
        elif not user_join_own_channel:
            await self._user_join_to_foreign(member, channel, after.channel)


    async def _user_try_create_channel(self, user, user_channel):
        user_have_channel = user_channel is not None
        if user_have_channel:  # if channel already exist
            await user.move_to(user_channel)  # just send user to his channel
        else:  # channel yet don't exist
            channel = await self._create_channel(user)  # create channel
            await self._start_session_message(user, channel)  # send session message

    async def _create_channel(self, user):
        channel_name = get_activity_name(user)
        category = get_category(user)
        permissions = {user.guild.default_role: self.default_role_rights, user: self.leader_role_rights}
        channel = await user.guild.create_voice_channel(channel_name, category=category, overwrites=permissions)

        async with self.get_connection() as cur:
            await cur.execute(f"INSERT INTO ChannelsINFO (user_id, channel_id) VALUES ({user.id}, {channel.id})")
            await cur.execute(f"INSERT INTO SessionsMembers (channel_id, member_id) VALUES ({channel.id}, {user.id})")
        await user.move_to(channel)
        return channel

    async def _start_session_message(self, creator, channel):
        day_of_year, is_leap_year = session_id()
        async with self.get_connection() as cur:
            await cur.execute(f"SELECT past_sessions_counter, current_sessions_counter FROM SessionsID WHERE current_day = {day_of_year}")
            past_sessions_counter, current_sessions_counter = await cur.fetchone()

            sess_id = f'№ {1 + past_sessions_counter + current_sessions_counter} | {day_of_year}/{366 if is_leap_year else 365}'

            dt_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) # GMT+3
            text_time = time_formatter(dt_time)
            embed_obj = discord.Embed(title=f"{creator.display_name} начал сессию {sess_id}",
                                      color = discord.Color.green())
            embed_obj.add_field(name='├ Сессия активна . . .', value='├ ВАЖНО: [[#1]](https://youtu.be/gvTsB7GWpTc), [[#2]](https://youtu.be/Ii8850-G8S0)')

            embed_obj.add_field(name = '├ Время начала', value = '└ ' + f'{text_time}', inline=False)
            creator = channel.guild.get_member(creator.id)
            embed_obj.set_footer(text= creator.display_name + " - Создатель сессии", icon_url=creator.avatar_url)

            msg = await self.bot.logger_channel.send(embed = embed_obj)

            await cur.execute(f"UPDATE SessionsID SET current_sessions_counter = {current_sessions_counter + 1} WHERE current_day = {day_of_year}")
            await cur.execute(f"INSERT INTO SessionsINFO (channel_id, creator_id, start_day, session_id, message_id) VALUES (%s, %s, %s, %s, %s)",
                                    parameters = (channel.id, creator.id, day_of_year, sess_id, msg.id))
            if user_is_playing(creator):
                app_id, is_real = get_app_id(creator)
                if is_real:
                    await self._update_message_icon(app_id, channel.id)


    async def _user_join_to_foreign(self, user, user_channel, foreign_channel):
        # User havn't channel and try to join to channel of another user
        user_have_channel = user_channel is not None
        user_leave_guild = foreign_channel is None

        if user_have_channel:
            await self._leader_leave_own_channel(user, user_channel)

        if not user_leave_guild: #user not just leave from server
            async with self.get_connection() as cur:
                await cur.execute(f"INSERT INTO SessionsMembers (channel_id, member_id) VALUES ({foreign_channel.id}, {user.id})")

    async def _leader_leave_own_channel(self, leader, leader_channel):
        user_channel_empty = not leader_channel.members
        if user_channel_empty:  # write end session message and delete channel
            await self._end_session_message(leader_channel)
            await leader_channel.delete()
        else:  # if channel isn't empty just transfer channel
            await self._transfer_channel(leader, leader_channel)

    async def _end_session_message(self, channel):
        async with self.get_connection() as cur:
            await cur.execute(f"SELECT * FROM SessionsINFO WHERE channel_id = {channel.id}")
            session_info = await cur.fetchone()

            _, creator_id, start_day, session_id, message_id = session_info
            await cur.execute(f"SELECT past_sessions_counter, current_sessions_counter FROM SessionsID WHERE current_day = {start_day}")
            past_sessions_counter, current_sessions_counter = await cur.fetchone()
            await cur.execute(f"UPDATE SessionsID SET current_sessions_counter = {current_sessions_counter - 1} WHERE current_day = {start_day}")
        try:
            msg = await self.bot.logger_channel.fetch_message(message_id)
        except discord.errors.NotFound:
            return
        start_time = msg.created_at + datetime.timedelta(0, 0, 0, 0, 0, 3, 0)
        end_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0)  # GMT+3
        sess_duration = end_time - start_time

        if sess_duration.seconds > 300:
            async with self.get_connection() as cur:
                await cur.execute(f"UPDATE SessionsID SET past_sessions_counter = {past_sessions_counter + 1} WHERE current_day = {start_day}")

                await cur.execute(f"SELECT member_id FROM SessionsMembers WHERE channel_id = {channel.id}")
                session_members = await cur.fetchall()
                users_ids = set(flatten(session_members))

                await cur.execute(f"SELECT associate_role FROM SessionsActivities WHERE channel_id = {channel.id}")
                associated_roles = await cur.fetchall()
                roles_ids = set(flatten(associated_roles))

            embed_obj = discord.Embed(title=f"Сессия {session_id} окончена!", color=discord.Color.red())
            embed_obj.description = '├ ВАЖНО: [[#1]](https://youtu.be/gvTsB7GWpTc), [[#2]](https://youtu.be/Ii8850-G8S0)'
            embed_obj.add_field(name='├ Время начала', value=f'├ {time_formatter(start_time)}', inline=True)
            embed_obj.add_field(name='Время окончания', value=f'{time_formatter(end_time)}')
            embed_obj.add_field(name='├ Продолжительность', value=f"├ {str(sess_duration).split('.')[0]}", inline=False)
            embed_obj.add_field(name='├ Участники', value='└ ' + ', '.join((f'<@{id}>' for id in users_ids)), inline=False)

            thumbnail_url = msg.embeds[0].thumbnail.url
            if thumbnail_url:
                embed_obj.set_thumbnail(url=thumbnail_url)

            embed_obj.set_footer(text=msg.embeds[0].footer.text, icon_url=msg.embeds[0].footer.icon_url)


            await msg.edit(embed=embed_obj)
            await self._add_activities_emoji(msg, roles_ids)
        else:
            await msg.delete()

        async with self.get_connection() as cur:
            await cur.execute(f"DELETE FROM ChannelsINFO WHERE channel_id = {channel.id}")
            await cur.execute(f"DELETE FROM SessionsMembers WHERE channel_id = {channel.id}")
            await cur.execute(f"DELETE FROM SessionsActivities WHERE channel_id = {channel.id}")
            await cur.execute(f"DELETE FROM SessionsINFO WHERE channel_id = {channel.id}")


    async def _add_activities_emoji(self, msg, roles_ids):
        async with self.get_connection() as cur:
            for role_id in roles_ids:
                await cur.execute(f"SELECT application_id FROM CreatedRoles WHERE role_id = {role_id}")
                app_id, = await cur.fetchone()
                await cur.execute(f"SELECT emoji_id FROM CreatedEmoji WHERE application_id = {app_id}")
                emoji_id, = await cur.fetchone()
                if emoji_id:
                    emoji = self.bot.get_emoji(emoji_id)
                    await msg.add_reaction(emoji)


    async def _transfer_channel(self, user, channel):
        new_leader = channel.members[0]  # New leader of these channel
        async with self.get_connection() as cur:
            await cur.execute(f"UPDATE ChannelsINFO SET user_id = {new_leader.id} WHERE channel_id = {channel.id}")

        channel_name = get_activity_name(new_leader)
        permissions = {user: self.default_role_rights, new_leader: self.leader_role_rights}
        try:
            await asyncio.wait_for(channel.edit(name=channel_name, overwrites=permissions), timeout=5.0)
        except asyncio.TimeoutError:
            print('Trying to rename channel in transfer but Discord restrictions :(')
            await channel.edit(overwrites=permissions)


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self._add_associated_role(payload)


    async def _add_associated_role(self, payload):
        user_is_bot = payload.user_id == self.bot.user.id
        if not user_is_bot:
            emoji = payload.emoji
            async with self.get_connection() as cur:
                await cur.execute(f"SELECT application_id FROM CreatedEmoji WHERE emoji_id = {emoji.id}")
                application_id = await cur.fetchone()
                if application_id:
                    await cur.execute(f"SELECT role_id FROM CreatedRoles WHERE application_id = {application_id[0]}")
                    associated_role = await cur.fetchone()
                if associated_role:
                    guild = self.bot.get_guild(payload.guild_id)
                    member = guild.get_member(payload.user_id)
                    role = guild.get_role(associated_role[0])
                    await member.add_roles(role)


    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self._remove_associated_role(payload)


    async def _remove_associated_role(self, payload):
        user_is_bot = payload.user_id == self.bot.user.id
        if not user_is_bot:
            emoji = payload.emoji
            async with self.get_connection() as cur:
                await cur.execute(f"SELECT application_id FROM CreatedEmoji WHERE emoji_id = {emoji.id}")
                application_id = await cur.fetchone()
                if application_id:
                    await cur.execute(f"SELECT role_id FROM CreatedRoles WHERE application_id = {application_id[0]}")
                    associated_role = await cur.fetchone()
                if associated_role:
                    guild = self.bot.get_guild(payload.guild_id)
                    member = guild.get_member(payload.user_id)
                    role = guild.get_role(associated_role[0])
                    await member.remove_roles(role)



    @async_contextmanager
    async def get_connection(self):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                yield cur

    async def get_user_channel(self, user_id):
        async with self.get_connection() as cur:
            await cur.execute(f"SELECT channel_id FROM ChannelsINFO WHERE user_id = {user_id}")
            channel_id = await cur.fetchone()
        if channel_id:
            return self.bot.get_channel(*channel_id)

def setup(bot):
    bot.add_cog(Channels_manager(bot))
