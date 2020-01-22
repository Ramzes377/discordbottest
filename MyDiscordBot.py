import discord
import os


created_channels = {} # User_Name : Channel
channel_position = 2

class Bot(discord.Client):
    async def on_ready(self):
        print('Bot have been started!')
        for channel in self.get_all_channels():
            if channel.name[0] == '|':
                await channel.delete()

    def _channel_name_helper(self, member):
        if member.activity:
            activity_name = member.activity.name
            if activity_name.lower().replace(' ', '') == "pathofexile":
                return f"|PoE| {member.display_name}'s channel"
            elif activity_name.lower().replace(' ', '') == "dota2":
                return f"|Dota| {member.display_name}'s channel"
            elif activity_name.lower().replace(' ', '')[:9] == 'minecraft':
                return f"|Minecraft| {member.display_name}'s channel"
            else:
                return f"|{member.activity.name}| {member.display_name}'s channel"
        return f"|{member.display_name}'s channel"

    async def on_member_update(self, before, after):
        if after.display_name in created_channels:
            await created_channels[after.display_name].edit(name = self._channel_name_helper(after))

    async def on_voice_state_update(self, member, before, after):
        member_name = member.display_name

        if not after.channel or after.channel.name != 'Create channel':
            # PLAYER LEAVE FROM CHANNEL
            if member_name in created_channels:
                if not created_channels[member_name].members:
                    await created_channels.pop(member_name).delete( )
                    channel_position -= 1
                else:
                    channel = created_channels.pop(member_name)
                    new_leader = channel.members[-1]
                    created_channels[new_leader.display_name] = channel
                    await created_channels[new_leader.display_name].edit(name = self._channel_name_helper(new_leader))

        elif after.channel.name == 'Create channel':
            if member_name not in created_channels:
                category = self.get_channel(after.channel.category_id)
                channel_name = self._channel_name_helper(member)
                channel = await member.guild.create_voice_channel(channel_name, category = category, position = channel_position)
                created_channels[member_name] = channel
                await member.move_to(channel)
                channel_position += 1
            else:
                await member.move_to(created_channels[member_name])

bot = Bot()
token = os.environ.get('TOKEN')
bot.run(str(token))
