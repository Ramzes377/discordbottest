import discord
import os
import youtube_dl
from discord.ext import commands
from discord.ext.tasks import loop
from discord.utils import get
import shutil
import numpy as np
from random import randint as r
from aioitertools import cycle
from aioitertools import next as anext
from math import sin, cos, pi


lerp = lambda s, e, a: np.array((1 - a) * s + a * e, dtype = np.int).tolist()


def get_spiral_gradient(r = 115):
    center = 255/2
    colors = []
    den = 25
    dx = pi/den
    dt = r/(den*2)
    t = 0; x = 0
    while x < 4*pi and t < 2*r:
        colors.append(discord.Colour(1).from_rgb(int(center + r * cos(x)), int(center + r * sin(x)), int(t)))
        x += dx; t += dt
    t = 2*r; x = 0
    while x < 4*pi and t > 0:
        colors.append(discord.Colour(1).from_rgb(int(center + r * cos(x)), int(center + r * sin(x)), int(t)))
        x += dx; t -= dt
    return colors

gradient_cycle = cycle(get_spiral_gradient(125))

ydl_opts = {'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3',
                                'preferredquality': '192'}]}

created_channels = {} # User_Name : Channel
players = {}
queues = {}

created_categories = {discord.ActivityType.playing: 531556241663721492,
                      discord.ActivityType.streaming: 669927306562895900,
                      4: 531504241500749835,
                      0: 531504241500749835}

song_queue = []
song_counter = 0
current_playing_pos = 0

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
    for cat in created_categories:
        created_categories[cat] = bot.get_channel(created_categories[cat])  # getting categories from their IDs

    bot.create_channel = bot.get_channel(create_channel_id)
    bot.created_roles = {role.name: role for guild in bot.guilds for member in guild.members for role in member.roles}
    print('Bot have been started!')
    for channel in bot.get_all_channels( ):
        if channel.name[0] == '|':
            await channel.delete( )
    await bot.change_presence(status = discord.Status.idle, activity = discord.Game('бога') )
    change_colour.start( )
    #bot.loop.create_task(change_colour( ))


@bot.event
async def on_member_update(before, after):
    if after.display_name in created_channels:
        category = created_categories.get(after.activity.type if after.activity else 0)
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
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(connect = True, speak = True, use_voice_activation = True),
                member: discord.PermissionOverwrite(kick_members = True, mute_members = True, deafen_members = True, manage_channels = True, create_instant_invite = True)
            }
            channel = await member.guild.create_voice_channel(channel_name, category = category, overwrites = overwrites)
            created_channels[member_name] = channel
            await member.move_to(channel)
        else: #if created then just back client to himself channel
            await member.move_to(created_channels[member_name])

@bot.command(pass_context=True, aliases = ['j'])
async def join(ctx):
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild = ctx.guild)

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()

    await voice.disconnect()

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()
        print(f"The bot has connected to {channel}\n")

    await ctx.send(f"Joined {channel}")

@bot.command(pass_context = True, aliases = ['l'])
async def leave(ctx):
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)

    if voice and voice.is_connected():
        await voice.disconnect()
        print(f"The bot has left {channel}")
        await ctx.send(f"Left {channel}")
    else:
        print("Bot was told to leave voice channel, but was not in one")
        await ctx.send("Don't think I am in a voice channel")

@bot.command(pass_context=True, aliases=['p', 'pla'])
async def play(ctx, *url: str):

    def check_queue():
        Queue_infile = os.path.isdir("./Queue")
        if Queue_infile is True:
            DIR = os.path.abspath(os.path.realpath("Queue"))
            length = len(os.listdir(DIR))
            still_q = length - 1
            try:
                first_file = os.listdir(DIR)[0]
            except:
                print("No more queued song(s)\n")
                queues.clear()
                return
            main_location = os.path.dirname(os.path.realpath(__file__))
            song_path = os.path.abspath(os.path.realpath("Queue") + "\\" + first_file)
            if length != 0:
                print("Song done, playing next queued\n")
                print(f"Songs still in queue: {still_q}")
                song_there = os.path.isfile("song.mp3")
                if song_there:
                    os.remove("song.mp3")
                shutil.move(song_path, main_location)
                for file in os.listdir("./"):
                    if file.endswith(".mp3"):
                        os.rename(file, 'song.mp3')

                voice.play(discord.FFmpegPCMAudio("song.mp3"), after=lambda e: check_queue())
                voice.source = discord.PCMVolumeTransformer(voice.source)
                voice.source.volume = 0.5

            else:
                queues.clear()
                return

        else:
            queues.clear()
            print("No songs were queued before the ending of the last song\n")



    song_there = os.path.isfile("song.mp3")
    try:
        if song_there:
            os.remove("song.mp3")
            queues.clear()
            print("Removed old song file")
    except PermissionError:
        print("Trying to delete song file, but it's being played")
        await ctx.send("ERROR: Music playing")
        return


    Queue_infile = os.path.isdir("./Queue")
    try:
        Queue_folder = "./Queue"
        if Queue_infile is True:
            print("Removed old Queue Folder")
            shutil.rmtree(Queue_folder)
    except:
        print("No old Queue folder")

    await ctx.send("Getting everything ready now")

    voice = get(bot.voice_clients, guild=ctx.guild)

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': False,
        'outtmpl': "./song.mp3",
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    song_search = " ".join(url)

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            print("Downloading audio now\n")
            ydl.download([f"ytsearch1:{song_search}"])
    except:
        print("FALLBACK: youtube-dl does not support this URL, using Spotify (This is normal if Spotify URL)")
        c_path = os.path.dirname(os.path.realpath(__file__))
        os.system("spotdl -ff song -f " + '"' + c_path + '"' + " -s " + song_search)

    voice.play(discord.FFmpegPCMAudio("song.mp3"), after=lambda e: check_queue())
    voice.source = discord.PCMVolumeTransformer(voice.source)
    voice.source.volume = 0.07

@bot.command(pass_context=True)
async def pause(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)

    if voice and voice.is_playing():
        print("Music paused")
        voice.pause()
        await ctx.send("Music paused")
    else:
        print("Music not playing failed pause")
        await ctx.send("Music not playing failed pause")

@bot.command(pass_context=True, aliases=['r'])
async def resume(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)

    if voice and voice.is_paused():
        print("Resumed music")
        voice.resume()
        await ctx.send("Resumed music")
    else:
        print("Music is not paused")
        await ctx.send("Music is not paused")

@bot.command(pass_context=True, aliases=['s'])
async def stop(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)

    queues.clear()

    if voice and voice.is_playing():
        print("Music stopped")
        voice.stop()
        await ctx.send("Music stopped")
    else:
        print("No music playing failed to stop")
        await ctx.send("No music playing failed to stop")

@bot.command(pass_context=True, aliases=['q', 'que'])
async def queue(ctx, *url: str):
    Queue_infile = os.path.isdir("./Queue")
    if Queue_infile is False:
        os.mkdir("Queue")
    DIR = os.path.abspath(os.path.realpath("Queue"))
    q_num = len(os.listdir(DIR))
    q_num += 1
    add_queue = True
    while add_queue:
        if q_num in queues:
            q_num += 1
        else:
            add_queue = False
            queues[q_num] = q_num

    queue_path = os.path.abspath(os.path.realpath("Queue") + f"\song{q_num}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'outtmpl': queue_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    song_search = " ".join(url)

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            print("Downloading audio now\n")
            ydl.download([f"ytsearch1:{song_search}"])
    except:
        print("FALLBACK: youtube-dl does not support this URL, using Spotify (This is normal if Spotify URL)")
        q_path = os.path.abspath(os.path.realpath("Queue"))
        system(f"spotdl -ff song{q_num} -f " + '"' + q_path + '"' + " -s " + song_search)


    await ctx.send("Adding song " + str(q_num) + " to the queue")

    print("Song added to queue\n")

@bot.command(pass_context=True, aliases=['n', 'nex'])
async def next(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)

    if voice and voice.is_playing():
        print("Playing Next Song")
        voice.stop()
        await ctx.send("Next Song")
    else:
        print("No music playing")
        await ctx.send("No music playing failed")

@bot.command(pass_context=True, aliases=['v', 'vol'])
async def volume(ctx, volume: int):

    if ctx.voice_client is None:
        return await ctx.send("Not connected to voice channel")

    print(volume/100)

    ctx.voice_client.source.volume = volume / 100
    await ctx.send(f"Changed volume to {volume}%")

@loop(seconds = 2)
async def change_colour():
    try:
        color = await anext(gradient_cycle)
        await bot.created_roles['Admin'].edit(colour = color)
    except discord.HTTPException as e:
        pass
    except:
        pass

token = os.environ.get('TOKEN')
bot.run(str(token))
