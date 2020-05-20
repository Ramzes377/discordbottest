import discord
from discord.ext import commands
import os
import re
import datetime
from random import randint as r
import aiohttp
import asyncio
import cv2
from sklearn.cluster import KMeans
import numpy as np



create_channel_id = int(os.environ.get('Create_channel_ID'))
logger_id = int(os.environ.get('Logger_channel_ID'))
role_request_id = int(os.environ.get('Role_request'))

_categories = {discord.ActivityType.playing:   int(os.environ.get('Category_playing')),
               discord.ActivityType.streaming: int(os.environ.get('Category_steaming')),
               4:                              int(os.environ.get('Category_custom')),
               0:                              int(os.environ.get('Category_idle'))}

time_formatter = lambda time: "%02d:%02d:%02d - %02d.%02d.%04d" % (time.hour, time.minute, time.second, time.day, time.month,  time.year)

def is_leap_year(year):
    return True if not year % 400 else False if not year % 100 else True if not year % 4 else False

def session_id():
    cur_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) # GMT+3
    start_of_year = datetime.datetime(cur_time.year, 1, 1, 0, 0, 0, 0)
    delta = cur_time - start_of_year
    return delta.days + 1, is_leap_year(cur_time.year)

def DominantColors(img, clusters):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.reshape((img.shape[0] * img.shape[1], 3))
    kmeans = KMeans(n_clusters=clusters)
    kmeans.fit(img)
    colors = kmeans.cluster_centers_
    return colors.astype(int)

def _activity_name(member): #describe few activities to correct show
    if member.activity:
        activity_name = member.activity.name
        if len(activity_name) > 6:
            short_name = ''
            for word in re.split(r'\W', activity_name):
                short_name += word[:1] if word else ' '
            return f"[{short_name}]"
        return f"[{activity_name}]"
    return ""


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
        await asyncio.sleep(3)
        for cat in _categories:
            _categories[cat] = self.bot.get_channel(_categories[cat])  # getting categories from their IDs

        self.bot.create_channel = self.bot.get_channel(create_channel_id)
        self.bot.logger_channel = self.bot.get_channel(logger_id)
        
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                active_channels = await cur.execute("SELECT channel_id FROM ChannelsINFO")
                if active_channels:
                    for chnls in active_channels:
                        channel_id = chnls[0]
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            if not channel.members:
                                await self.end_session_message(channel)
                                await channel.delete()
                                await cur.execute(f"DELETE FROM ChannelsINFO WHERE channel_id = {channel_id}")
                            else:
                                await cur.execute(f"SELECT user_id FROM ChannelsINFO WHERE channel_id = {channel_id}")
                                user_id = await cur.fetchone()[0]
                                user = self.bot.get_user(user_id)
                                if not user in channel.members:
                                    await self._transfer_channel(user)
                        else:
                            await cur.execute(f"DELETE FROM ChannelsINFO WHERE channel_id = {channel_id}")

        channel = self.bot.get_channel(role_request_id)
        story = await channel.history(limit=100).flatten()
        if len(story) > 0:
            self.msg = story[-1]
            guild = self.msg.guild
            for reaction in self.msg.reactions:
                if not reaction.emoji in guild.emojis:
                    await self.msg.remove_reaction(reaction.emoji, guild.get_member(self.bot.user.id))
                    async with self.bot.db.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(f"DELETE FROM CreatedEmoji WHERE emoji_id = {reaction.emoji.id}")
        else:
            self.msg = await channel.send("Нажмите на иконку игры, чтобы получить соответствующую игровую роль!")

        #await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="help to create your own channel"))
        print(f'{type(self).__name__} starts')

    async def _edit_role_giver_message(self, emoji_id):
        emoji = self.bot.get_emoji(emoji_id)
        try:
            await self.msg.add_reaction(emoji)
        except discord.errors.Forbidden:
            channel = self.msg.channel
            self.msg = await channel.send("Нажмите на иконку игры, чтобы получить соответствующую игровую роль!")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id != self.bot.user.id:
            emoji = payload.emoji
            async with self.bot.db.acquire() as conn:
                async with conn.cursor() as cur:
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
        if payload.user_id != self.bot.user.id:
            emoji = payload.emoji
            async with self.bot.db.acquire() as conn:
                async with conn.cursor() as cur:
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

    async def update_message_icon(self, app_id, channel_id):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT message_id FROM SessionsINFO WHERE channel_id = {channel_id}")
                temp = await cur.fetchone()
                if temp:
                    message_id = temp[0]
                else:
                    return
                await cur.execute(f'SELECT icon_url FROM ActivitiesINFO WHERE application_id = {app_id}')
                thumbnail_url = await cur.fetchone()
                if thumbnail_url:
                    msg = await self.bot.logger_channel.fetch_message(message_id)
                    msg_embed = msg.embeds[0]
                    msg_embed.set_thumbnail(url = thumbnail_url[0])
                    await msg.edit(embed=msg_embed)

    async def _sort_channels_by_activity(self, user):
        category = _categories.get(user.activity.type if user.activity else 0)
        channel = await self.get_private_channel(user)
        channel_name = _activity_name(user) + f" {user.display_name}'s channel"
        await channel.edit(name = channel_name, category = category)

    async def logging_activities(self, after):
        # Session activities logging
        try:
            app_id, is_real = after.activity.application_id, True
        except:
            app_id, is_real = abs(hash(after.activity.name)), False

        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT * FROM SessionsMembers WHERE member_id = {after.id}")
                #recognize that's these user member of session
                is_user_session_member = await cur.fetchall() #all of his sessions
                if is_user_session_member: #user member of atleast one session
                    for channel_id, _ in is_user_session_member:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            if after in channel.members:
                                break
                        else:
                            await cur.execute(f"DELETE FROM SessionsMembers WHERE channel_id = {channel_id}")
                    if channel:
                        channel_id = channel.id
                        await cur.execute(f"SELECT role_id FROM CreatedRoles WHERE application_id = {app_id}")
                        associate_role = await cur.fetchone()
                        await cur.execute(f"INSERT INTO SessionsActivities (channel_id, associate_role) VALUES ({channel_id}, {associate_role[0]})")
                        if is_real:
                            await self.update_message_icon(app_id, channel_id)

    async def _create_activity_emoji(self, guild, app_id):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f'SELECT name, icon_url FROM ActivitiesINFO WHERE application_id = {app_id}')
                name, thumbnail_url = await cur.fetchone()
                name = re.compile('[^a-zA-Z ]').sub('', name).replace(" ", "")
                thumbnail_url = thumbnail_url[:-10]
                async with aiohttp.ClientSession() as session:
                    async with session.get(thumbnail_url) as resp:
                        content = await resp.read()
                emoji = await guild.create_custom_emoji(name=name, image=content)

                await cur.execute(f"INSERT INTO CreatedEmoji (application_id, emoji_id) VALUES ({app_id}, {emoji.id})")
                await self._edit_role_giver_message(emoji.id)
                img_np = cv2.imdecode(np.frombuffer(content, dtype='uint8'), 1)
                return DominantColors(img_np, 2)[0]

    async def link_roles(self, after):
        try:
            app_id, is_real = after.activity.application_id, True
        except:
            app_id, is_real = abs(hash(after.activity.name)), False
        role_name = after.activity.name
        guild = after.guild
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT * FROM CreatedRoles WHERE application_id = {app_id}")
                created_role = await cur.fetchone()
                if created_role:  # role already exist
                    role = guild.get_role(created_role[1])  # get role
                    if not role in after.roles:  # check user have these role
                        await after.add_roles(role)
                else:
                    if is_real:
                        color = await self._create_activity_emoji(guild, app_id)
                    else:
                        color = r(70, 255), r(70, 255), r(70, 255)
                    role = await guild.create_role(name=role_name,
                                                   permissions=guild.default_role.permissions,
                                                   colour=discord.Colour(1).from_rgb(int(color[0]), int(color[1]), int(color[2])),
                                                   hoist=True,
                                                   mentionable = True)
                    await cur.execute(f"INSERT INTO CreatedRoles (application_id, role_id) VALUES ({app_id}, {role.id})")
                    await after.add_roles(role)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT * FROM ChannelsINFO WHERE user_id = {after.id}")
                if await cur.fetchone():
                    await self._sort_channels_by_activity(after)

                if after.activity and after.activity.type == discord.ActivityType.playing:
                    await self.link_roles(after)
                    await self.logging_activities(after)

    async def _transfer_channel(self, user):
        channel = await self.get_private_channel(user)
        new_leader = channel.members[0]  # New leader of these channel
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"UPDATE ChannelsINFO SET user_id = {new_leader.id} WHERE channel_id = {channel.id}")

        _permissions = {user: self.default_role_rights, new_leader: self.leader_role_rights}
        channel_name = _activity_name(new_leader) + f" {new_leader.display_name}'s channel"
        await channel.edit(name = channel_name, overwrites = _permissions)

    async def _create_channel(self, user):
        category = _categories.get(user.activity.type if user.activity else 0)
        permissions = {user.guild.default_role: self.default_role_rights, user: self.leader_role_rights}
        channel_name = _activity_name(user) + f" {user.display_name}'s channel"
        channel = await user.guild.create_voice_channel(channel_name,
                                                        category=category,
                                                        overwrites=permissions)
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"INSERT INTO ChannelsINFO (user_id, channel_id) VALUES ({user.id}, {channel.id})")
        await user.move_to(channel)
        return channel

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT channel_id FROM ChannelsINFO WHERE user_id = {member.id}")
                member_have_channel = await cur.fetchone()
                if member_have_channel:
                    channel = self.bot.get_channel(*member_have_channel) #his channel
                    if not channel:
                        await cur.execute(f"DELETE FROM ChannelsINFO WHERE user_id = {member.id}")

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
                                await cur.execute(f"DELETE FROM ChannelsINFO WHERE user_id = {member.id}")
                                await cur.execute(f"DELETE FROM SessionsMembers WHERE channel_id = {channel.id}")
                                await channel.delete()
                            else: #if channel isn't empty just transfer channel
                                await self._transfer_channel(member)
                    if after.channel:
                        await cur.execute(f"INSERT INTO SessionsMembers (channel_id, member_id) VALUES ({after.channel.id}, {member.id})")

    async def start_session_message(self, creator, channel, **kw):
        day_of_year, is_leap_year = session_id()
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT past_sessions_counter, current_sessions_counter FROM SessionsID WHERE current_day = {day_of_year}")
                past_sessions_counter, current_sessions_counter = await cur.fetchone()

                sess_id = f'№ {1 + past_sessions_counter + current_sessions_counter} | {day_of_year}/{366 if is_leap_year else 365}'

                dt_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0) # GMT+3
                text_time = time_formatter(dt_time)
                embed_obj = discord.Embed(title=f"{creator.display_name} начал сессию {sess_id}",
                                          color = discord.Color.green())
                embed_obj.add_field(name = 'Время начала', value = f'{text_time}')
                embed_obj.description = 'Сессия активна...'
                msg = await self.bot.logger_channel.send(embed = embed_obj)

                await cur.execute(f"UPDATE SessionsID SET current_sessions_counter = {current_sessions_counter + 1} WHERE current_day = {day_of_year}")
                await cur.execute(f"INSERT INTO SessionsINFO (channel_id, creator_id, start_day, session_id, message_id) VALUES (%s, %s, %s, %s, %s)",
                                        parameters = (channel.id, creator.id, day_of_year, sess_id, msg.id))
                await cur.execute(f"INSERT INTO SessionsMembers (channel_id, member_id) VALUES ({channel.id}, {creator.id})")

    async def end_session_message(self, channel):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT creator_id, start_day, session_id, message_id FROM SessionsINFO WHERE channel_id = {channel.id}")
                temp = await cur.fetchone()
                if temp:
                    creator_id, start_day, session_id, message_id = temp
                else:
                    return

                await cur.execute(
                    f"SELECT past_sessions_counter, current_sessions_counter FROM SessionsID WHERE current_day = {start_day}")
                past_sessions_counter, current_sessions_counter = await cur.fetchone()

                await cur.execute(f"UPDATE SessionsID SET current_sessions_counter = {current_sessions_counter - 1} WHERE current_day = {start_day}")

                msg = await self.bot.logger_channel.fetch_message(message_id)

                start_time = msg.created_at + datetime.timedelta(0, 0, 0, 0, 0, 3, 0)
                end_time = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, 3, 0)  # GMT+3

                sess_duration = end_time - start_time

                if sess_duration.seconds > 120:
                    await cur.execute(f"UPDATE SessionsID SET past_sessions_counter = {past_sessions_counter + 1} WHERE current_day = {start_day}")
                    await cur.execute(f"SELECT member_id FROM SessionsMembers WHERE channel_id = {channel.id}")
                    temp = await cur.fetchall()
                    users_ids = set(temp) if temp else []
                    await cur.execute(f"SELECT associate_role FROM SessionsActivities WHERE channel_id = {channel.id}")
                    temp = await cur.fetchall()
                    roles_ids = set(temp) if temp else []

                    embed_obj = discord.Embed(title=f"Сессия {session_id} окончена!", color=discord.Color.red())
                    embed_obj.add_field(name='Время начала', value=f'{time_formatter(start_time)}')
                    embed_obj.add_field(name='Время окончания', value=f'{time_formatter(end_time)}')
                    embed_obj.add_field(name='Продолжительность', value=f"{str(sess_duration).split('.')[0]}", inline=False)
                    embed_obj.add_field(name='Участники', value=', '.join(map(lambda id: f'<@{id[0]}>', users_ids)), inline=False)

                    thumbnail_url = msg.embeds[0].thumbnail.url
                    if thumbnail_url:
                        embed_obj.set_thumbnail(url = thumbnail_url)

                    creator = channel.guild.get_member(creator_id)
                    embed_obj.set_footer(text=creator.display_name + " - Создатель сессии", icon_url=creator.avatar_url)

                    await msg.edit(embed = embed_obj)

                    for role_id in roles_ids:
                        await cur.execute(f"SELECT application_id FROM CreatedRoles WHERE role_id = {role_id[0]}")
                        app_id = await cur.fetchone()
                        await cur.execute(f"SELECT emoji_id FROM CreatedEmoji WHERE application_id = {app_id[0]}")
                        emoji_id = await cur.fetchone()
                        if emoji_id:
                            emoji = self.bot.get_emoji(emoji_id[0])
                            await msg.add_reaction(emoji)
                else:
                    await msg.delete()
                                        
                await cur.execute(f"DELETE FROM SessionsMembers WHERE channel_id = {channel.id}")
                await cur.execute(f"DELETE FROM SessionsActivities WHERE channel_id = {channel.id}")
                await cur.execute(f"DELETE FROM SessionsINFO WHERE channel_id = {channel.id}")                        

    async def get_private_channel(self, user):
        async with self.bot.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT channel_id FROM ChannelsINFO WHERE user_id = {user.id}")
                channel_id = await cur.fetchone()
                return self.bot.get_channel(channel_id[0])


def setup(bot):
    bot.add_cog(Channels_manager(bot))
