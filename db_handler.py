from datetime import datetime
import discord
from pymongo import MongoClient

class DbHandler:
    def __init__(self, db_conn_string: str) -> None:
        self.__db = MongoClient(db_conn_string).general_walarus
        self.__log = lambda discord_server, collection, data: collection.update_one({"_id": discord_server.id}, {"$set": data}, upsert = True).upserted_id != None
    
    def log_user_stat(self, discord_server: discord.Guild, user: discord.User, target_stat: str, inc = 1) -> bool:
        user_stats = self.__db.user_stats
        stats = ["mentioned", "sent_messages", "vc_time"]
        stats_data = {}
        for stat in stats:
            if stat == target_stat:
                stats_data[stat] = inc
            else:
                stats_data[stat] = 0
        return user_stats.update_one({
                                        "_id": {
                                            "server_id": discord_server.id, 
                                            "user_id": user.id
                                        }
                                    }, 
                                    {
                                        "$set": {
                                            "server_name": discord_server.name, 
                                            "user_name": user.name
                                        },
                                        "$inc": stats_data
                                    }, 
                                    upsert = True).upserted_id != None

    def log_server(self, discord_server: discord.Guild) -> bool:
        connected_servers = self.__db.connected_servers
        server_exists = bool(connected_servers.find_one({"_id": discord_server.id}))
        icon_exists = bool(discord_server.icon)
        description_exists = bool(discord_server.description)
        server_data = {
            "_id": discord_server.id,
            "name": str(discord_server.name),
            "description": str(discord_server.description) if description_exists else "",
            "icon_url": str(discord_server.icon.url) if icon_exists else "",
            "creation_at": discord_server.created_at,
            "last_updated": datetime.now()
        }
        if not server_exists:
            server_data["joined"] = datetime.now()
        return self.__log(discord_server, connected_servers, server_data)
    
    # Remove the given server from all relevant collections, returns the number of documents deleted
    def remove_discord_server(self, discord_server: discord.Guild) -> int:
        connected_servers = self.__db.connected_servers
        user_stats = self.__db.user_stats
        total = connected_servers.delete_many({"_id": discord_server.id}).deleted_count
        total += user_stats.delete_many({"_id.server_id": discord_server.id}).deleted_count
        return total
        
        