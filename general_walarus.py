import asyncio
from datetime import datetime, timedelta
import random
from typing import cast
import discord
from discord.ext import commands
from discord.sinks import WaveSink
from database.db_handler import DbHandler
from discord.ext import commands
import discord.utils
from dotenv import load_dotenv
from models.election import Election
from models.server import Server
import os
from processes import servers, vc_connections, elections
from pytz import timezone
from utilities import timef

# Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
load_dotenv()
bot: discord.Bot = commands.Bot(command_prefix="$", intents=intents) # type: ignore
db : DbHandler = DbHandler(str(os.getenv("DB_CONN_STRING")))

# Prints in console when bot is ready to be used
@bot.event
async def on_ready() -> None:
    """ Event that runs once General Walarus is up and running (v2) """
    rshuffle: list[str] = ["CEO of the Republic", 
             "Indian of the Republic",
             "The Softest of the Softest Carries", 
             "Chinese of the Republic", 
             "Economist of the Republic", 
             "Pope of the Republic"]
    ushuffle: list[discord.User] = []
    for guild in bot.guilds:
        servers[guild] = Server(guild, rshuffle, ushuffle)
    print(f"General Walarus active in {len(servers)} server(s)")
    await repeat_archive(timedelta(weeks=2))
    
@bot.event
async def on_message(message: discord.Message) -> None:
    """ Event that runs whenever a user sends something in a text channel (v2) """
    if message.guild is None:
        return
    db.log_user_stat(message.guild, cast(discord.User, message.author), "sent_messages")
    for user in message.mentions:
        db.log_user_stat(message.guild, cast(discord.User, user), "mentioned")
    await bot.process_commands(message)

@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    """ Event that runs whenever General Walarus joins a new server\n 
        Servers information is added to the database (v2)
    """
    print(f"General Walarus joined guild '{guild.name}' (id: {guild.id})")
    db.log_server(guild)

@bot.event
async def on_guild_remove(guild: discord.Guild) -> None:
    """ Event that runs when General Walarus gets removed from a server.\n
        Server information is deleted from database (v2)
    """
    print(f"General Walarus has been removed from guild '{guild.name}' (id: {guild.id})")
    print(f"{db.remove_discord_server(guild)} documents removed from database")

@bot.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    """ Event that runs when a server's information gets updated.\n
        Server information gets updated in the database (v2)
    """
    db.log_server(after)
    print(f"Server {before.id} was updated")

@bot.command(name="archivegeneral", aliases=["archive"])
async def test_archive_general(ctx: commands.Context, general_cat_name=None, archive_cat_name="Archive", freq=2) -> None:
    """ Command that manually runs archive function for testing purposes (v2) """
    if ctx.guild is None: 
        raise Exception("ctx.guild is None")
    if ctx.author.id == ctx.guild.owner_id:
        await archive_general(ctx.guild, general_cat_name=general_cat_name, archive_cat_name=archive_cat_name, freq=freq)
    else:
        await ctx.send("Only the owner can use this command")
        
@bot.command(name="bruh")
async def bruh(ctx: commands.Context) -> None:
    """ Stupid command that just has General Walarus send 'bruh' (v2) """
    await ctx.send("bruh")
    
@bot.command(name="echo", aliases=["say"])
async def echo(ctx: commands.Context, *words) -> None:
    """ Command that has General Walarus repeat back command args (v2) """
    message = ""
    for word in words:
        message += word + " "
    await ctx.send(message)
    
@bot.command(name="intodatabase", aliases=["intodb"])
async def log_server_into_database(ctx: commands.Context):
    """ Command to manually log a server into the database (v2) """
    if ctx.guild is None: 
        raise Exception("ctx.guild is None")
    if ctx.author.id == ctx.guild.owner_id:
        created_new = db.log_server(ctx.guild)
        if created_new:
            await ctx.send("Logged this server into the database") 
        else: 
            await ctx.send("Updated this server in database")
    else:
        await ctx.send("Only the owner can use this command")

# @bot.command(name="join", aliases=["connect", "startstalking"])
# async def join_vc(ctx: commands.Context):    
#     voice_state: discord.VoiceState = ctx.author.voice
#     voice_client: discord.VoiceClient
#     if voice_state != None:
#         voice_channel: discord.VoiceChannel = voice_state.channel
#         try:
#             voice_client = await voice_channel.connect()
#         except:
#             curr_voice_client: discord.VoiceClient = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
#             voice_client = await curr_voice_client.move_to(voice_channel)
#         vc_connections.update({ctx.guild.id: voice_client})
#         voice_client.start_recording(WaveSink(), once_stop_recording, voice_client.channel, ctx.channel)
#         print(f"started recording for {voice_client.channel.name}")
#     else:
#         await ctx.send("You're not connected to a voice channel")

# @bot.command(name="clip", aliases=["capture", "clipthatshit"])
# async def clip_vc(ctx: commands.Context, *args):
#     voice_client: discord.VoiceClient = vc_connections[ctx.guild.id]
#     if voice_client != None:
#         voice_client.stop_recording()
#         voice_client.start_recording(WaveSink(), once_stop_recording, voice_client.channel, ctx.channel)
#     else:
#         await ctx.send(f"I need to be in a voice channel {ctx.author}")

# @bot.command(name="leave", aliases=["disconnect", "stopstalking"])
# async def leave_vc(ctx: commands.Context):
#     voice_client: discord.VoiceClient = vc_connections[ctx.guild.id]
#     if voice_client != None:
#         del vc_connections[ctx.guild.id]
#         await voice_client.disconnect()
#         voice_client.stop_recording()
#     else:
#         await ctx.send("I'm not in a voice channel")
        
@bot.command(name="nextarchivedate", aliases=["nextarchive"])
async def next_archive_date_command(ctx: commands.Context) -> None:
    """ Command that sends the date of the next general chat archive. Assumes global archive date (v2) """
    if ctx.guild is None: 
        raise Exception("ctx.guild is None")
    await ctx.send("Next archive date: " + str(db.get_next_archive_date()))

@bot.command(name="nextresult", aliases=["nextelectionresult"])
async def next_election_result(ctx: commands.Context):
    """ Command that sends the time of the next election result (v2) """
    if not ctx.guild:
        raise Exception("ctx.guild is None")
    active_election: Election | None = elections.get(ctx.guild)
    if active_election:
        await ctx.send(f"The next role change will be at {active_election.next_time}")
    else:
        await ctx.send("There is no role change currently active")

@bot.command(name="election", aliases=["startelection"])
async def change_roles(ctx: commands.Context, arg="default"):
    """ Command that initiates an automated election (v2) """
    if ctx.guild is None: 
        raise Exception("ctx.guild is None")
    if ctx.author.id != ctx.guild.owner_id:
        await ctx.send("Only the Supreme Leader can use this command")
        return
    election: Election | None = elections.get(ctx.guild)
    if election is not None:
        if str(arg).lower() == "cancel":
            await ctx.send("Stopping current role change...")
            del elections[ctx.guild]
        else:
            await ctx.send("A role change is already active")
        return
    server: Server = cast(Server, servers.get(ctx.guild)) 
    now: datetime = datetime.now(tz=timezone(server.timezone))
    elections[ctx.guild] = Election(server, now, server.rshuffle, server.ushuffle)
    await carry_out_election(ctx, timedelta(minutes=server.rc_int))

@bot.command(name="datetime", aliases=["date", "time"])
async def time(ctx: commands.Context) -> None:
    """ Get the current datetime in the timezone of the given server (v2) """
    if ctx.guild is None:
        raise Exception("ctx.guild is None")
    server: Server = cast(Server, servers.get(ctx.guild))
    now: datetime = datetime.now(tz=timezone(server.timezone))
    await ctx.send(f"It is {now.date()}, {timef(now)}")

@bot.command(name="test")
async def test(ctx: commands.Context) -> None:
    """ Command reserved for testing purposes (v2) """
    if ctx.guild is None:
        raise Exception("ctx.guild is None")
    # if ctx.author.id != ctx.guild.owner_id:
    await ctx.send("Boi what you tryna test 🫱")

async def archive_general(guild: discord.Guild, general_cat_name=None, archive_cat_name="Archive", freq=2) -> None:
    """ Houses the actual logic of archiving general chat (v2) """
    try:
        general_category = discord.utils.get(guild.categories, name=general_cat_name)
        archive_category = discord.utils.get(guild.categories, name="Archive")
        chat_to_archive = discord.utils.get(guild.text_channels, name="general")
        await cast(discord.TextChannel, chat_to_archive).move(beginning=True, category=archive_category, sync_permissions=True)
        await cast(discord.TextChannel, chat_to_archive).edit(name=db.get_archived_name())
        new_channel = await guild.create_text_channel("general", category=general_category)
        await new_channel.send("good morning @everyone")   
    except Exception as ex:
        raise Exception(str(ex))

async def carry_out_election(ctx: commands.Context, freq: timedelta):
    """ Handles repeatedly sending out election result until finished (v2) """
    if ctx.guild is None:
        raise Exception("ctx.guild is None")
    server: Server = cast(Server, servers.get(ctx.guild))
    roles: list[str] = server.rshuffle
    members: list[discord.User] = server.ushuffle
    roles_used = []
    election: Election = Election(server)
    elections[ctx.guild] = election
    await ctx.send(f"An election has begun @everyone. The first result will be announced at {timef(election.next_time)}")
    while len(members) > 0 and elections.get(ctx.guild) is not None:
        await asyncio.sleep(freq.total_seconds())
        member_num = random.randint(0, len(members) - 1)
        role_num = random.randint(0, len(roles_used) - 1) if len(roles) == 0 else random.randint(0, len(roles) - 1)
        chosen_one = members[member_num]
        chosen_role = roles_used[role_num] if len(roles) == 0 else roles[role_num]
        await ctx.send(f"Role change announcement @everyone: {chosen_one.name}'s new role will be {chosen_role}")
        next = datetime.now() + freq
        next_role_change = datetime.strptime(f"{next.hour}:{next.minute}","%H:%M").strftime("%I:%M %p")
        roles.remove(chosen_role)
        roles_used.append(chosen_role)
        members.remove(chosen_one)
    await ctx.send("Roles have all been reassigned")
    active_role_change = False
    next_role_change = None

async def repeat_archive(freq: timedelta) -> None:
    """ Handles repeatedly archiving general chat """
    await sleep_until_archive()
    while True:
        db.update_next_archive_date(freq)
        for guild in bot.guilds:
            now = datetime.now()
            try:
                await archive_general(guild=guild)
                discord.utils.get(guild.channels, name=db.get_archived_name())
                print(str(now) + f": general archived in '{guild.name}' (id: {guild.id})")
            except Exception as ex:
                print(str(now) + f": there was an error archiving general in '{guild.name}' (id: {guild.id}): {str(ex)}")
        await sleep_until_archive()

async def sleep_until_archive() -> None:
    """ Handles waiting for the next archive date """
    now = datetime.now()
    then = db.get_next_archive_date()
    wait_time = (then - now).total_seconds()
    await asyncio.sleep(wait_time)

async def once_stop_recording(sink: WaveSink, vc: discord.VoiceChannel, tc: discord.TextChannel) -> None:
    print(f"{len(vc_connections)} connections:\n{str(vc_connections)}")
    if len(vc_connections) == 0:
        print("went here")
        return
    recorded_users = [
        f"<@{user_id}>"
        for user_id, audio in sink.audio_data.items()
    ]
    now = datetime.now()
    timestamp = f"{str(now.date())}_{now.hour}-{now.minute}-{now.second}"
    files = [discord.File(audio.file, f"vcclip_{timestamp}.{sink.encoding}") for user_id, audio in sink.audio_data.items()]  # List down the files.
    await tc.send(f"Clipped all audio from the \"{vc.name}\" voice chat:", files=files) 