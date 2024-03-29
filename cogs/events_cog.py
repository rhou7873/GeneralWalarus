from datetime import datetime, timedelta
import discord
from discord.ext.commands import Cog
from discord.ext import commands
import discord.utils
import database as db
from datetime import timedelta
from typing import cast
from models import Server
from globals import servers, start_mutex
from utilities import printlog

class EventsCog(Cog, name="Events"):
    """ Class containing implementations for Discord bot events """
    
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    #region Events

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """ Event that runs once General Walarus is up and running """
        for guild in self.bot.guilds:
            servers[guild] = Server(guild)
        print(f"General Walarus active in {len(servers)} server(s)")
        start_mutex.release()
        await self.bot.get_cog("Archive").repeat_archive(timedelta(weeks=2)) # type: ignore
        
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """ Event that runs whenever a user sends something in a text channel """
        if message.guild is None:
            return
        db.inc_user_stat(message.guild, cast(discord.User, message.author), "sent_messages")
        for user in message.mentions:
            if user.id != message.author.id:
                db.inc_user_stat(message.guild, cast(discord.User, user), "mentioned")
 
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """ Event that runs whenever General Walarus joins a new server\n 
            Servers information is added to the database """
        printlog(f"General Walarus joined guild '{guild.name}' (id: {guild.id})")
        servers[guild] = Server(guild)
        db.log_server(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """ Event that runs when General Walarus gets removed from a server.\n
            Server information is deleted from database """
        del servers[guild]
        printlog(f"General Walarus has been removed from guild '{guild.name}' (id: {guild.id})")
        printlog(f"{db.remove_discord_server(guild)} documents removed from database")

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """ Event that runs when a server's information gets updated.\n
            Server information gets updated in the database """
        db.log_server(after)
        printlog(f"Server {before.id} was updated")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """ Event that runs when a user joins a guild """
        db.create_user(member.guild, member)
        
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, ex: commands.CommandError):
        """ Event that runs when a user tries a command and it raises an error """
        if type(ex) == commands.CommandNotFound:
            await ctx.send("That ain't a command my brother in Christ")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """ Event that runs when a user changes voice state (join/leaves VC, gets muted/unmuted, 
            gets deafened/undeafened, etc.) """
        guild: discord.Guild = member.guild
        self.db_update_voice(member, guild, before, after)
        
    #endregion
    
    #region Helper Functions
    
    def db_update_voice(self, member: discord.Member, guild: discord.Guild, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """ Analyzes before and after voice state and updates user voice status in database """
        now: datetime = datetime.now()
        if before.channel == None and after.channel != None:
            # user joins a voice channel
            db.update_user_stats(guild, member, last_connected_to_vc=now, connected_to_vc=True)
            vc_members: list = after.channel.members
            non_bot_count: int = 0
            for vc_member in vc_members:
                if not vc_member.bot:
                    non_bot_count += 1
            vc_timer: bool = non_bot_count > 1
            for vc_member in vc_members:
                db.update_user_stats(guild, vc_member, vc_timer=vc_timer)    
        elif before.channel != None and after.channel == None:
            # user leaves a voice channel
            field_name: str = "last_connected_to_vc"
            connected_time: datetime = cast(dict, db.get_user_stat(guild, member.id, field_name))[field_name]
            session_length: int = (now - connected_time).seconds
            vc_members: list = before.channel.members
            vc_timer: bool = cast(dict, db.get_user_stat(guild, member.id, "vc_timer"))["vc_timer"]
            if len(vc_members) == 1: # just one more person left in voice channel
                # stop everyone's vc timer and update time in db
                for vc_member in vc_members:
                    update_time: bool = cast(dict, db.get_user_stat(guild, vc_member.id, "vc_timer"))["vc_timer"]
                    if update_time:
                        db.inc_user_stat(guild, vc_member, "time_in_vc", session_length)
                        db.update_user_stats(guild, vc_member, vc_timer=False)
            if vc_timer: # update time of the person who's leaving
                db.inc_user_stat(guild, member, "time_in_vc", session_length)
            db.update_user_stats(guild, member, connected_to_vc=False, vc_timer=False)
    
    #endregion