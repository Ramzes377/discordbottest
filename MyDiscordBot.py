import discord
import os

created_channels = {} # User_Name : Channel
created_categories = {discord.ActivityType.playing: 531556241663721492,
                      discord.ActivityType.streaming: 669927306562895900,
                      4: 531504241500749835,
                      0: 531504241500749835}

create_channel_id = 668969213368729660

class Bot(discord.Client):

    async def on_ready(self):
        for cat in created_categories:
            created_categories[cat] = self.get_channel(created_categories[cat]) #getting categories from their IDs
        self.create_channel = self.get_channel(create_channel_id)
        print('Bot have been started!')

        for channel in self.get_all_channels():
            if channel.name[0] == '|':
                await channel.delete()

    def _channel_name_helper(self, member): #describe few activities to correct show
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

    async def on_member_update(self, before, after):
        if after.display_name in created_channels:
            category = created_categories.get(after.activity.type if after.activity else 0)
            await created_channels[after.display_name].edit(name = self._channel_name_helper(after), category = category)

    async def on_voice_state_update(self, member, before, after):
        member_name = member.display_name
        if not after.channel or after.channel != self.create_channel:
            # Client LEAVE FROM CHANNEL
            if member_name in created_channels:
                if not created_channels[member_name].members:
                    #Client's channel is empty
                    await created_channels.pop(member_name).delete( )
                else:
                    # Client's channel isn't empty
                    channel = created_channels.pop(member_name)
                    new_leader = channel.members[0] #New leader of these channel
                    created_channels[new_leader.display_name] = channel
                    await created_channels[new_leader.display_name].edit(name = self._channel_name_helper(new_leader))

        elif after.channel == self.create_channel:
            #Creating new channel
            if member_name not in created_channels: #if not created already
                category = created_categories.get(member.activity.type if member.activity else 0)
                channel_name = self._channel_name_helper(member)
                overwrites = {
                    member.guild.default_role: discord.PermissionOverwrite(connect = True, speak = True, use_voice_activation = True),
                    member: discord.PermissionOverwrite(kick_members = True, mute_members = True, deafen_members = True, manage_channels = True)
                }
                channel = await member.guild.create_voice_channel(channel_name, category = category, overwrites = overwrites)
                created_channels[member_name] = channel
                await member.move_to(channel)
            else: #if created then just back client to himself channel
                await member.move_to(created_channels[member_name])

    async def on_message(self, message):  #PROTOTYPE
        channel = message.channel
        if message.author != self.user:
            if message.content.startswith('!'):
                if message.content[1:] == 'time':
                    await channel.send('Hey!')
