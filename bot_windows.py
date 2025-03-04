import discord
import yt_dlp
import asyncio

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

voice_clients = {}
queues = {}
current_song = {}


yt_dl_options = {
    "format": "bestaudio/best",
    "noplaylist": False, 
    "default_search": "ytsearch",
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "skip_download": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }]
}

prefix = "+"

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

def search_youtube(query):
    """Recherche une vidéo sur YouTube et retourne l'URL et le titre"""
    search_options = yt_dl_options.copy()
    search_options["noplaylist"] = True  
    
    if not query.startswith("http"):
        query = f"ytsearch1:{query}"
    
    with yt_dlp.YoutubeDL(search_options) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            
            if 'entries' in info:
             
                video = info['entries'][0]
            else:
                video = info
                
            video_url = f"https://www.youtube.com/watch?v={video['id']}"
            video_title = video.get('title', 'Titre inconnu')
            
            return video_url, video_title
            
        except Exception as e:
            print(f"Erreur de recherche YouTube: {e}")
            return None, f"Erreur: {e}"

def get_audio_url(video_url):
    """Obtient l'URL du flux audio d'une vidéo YouTube"""
    with yt_dlp.YoutubeDL(yt_dl_options) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
            
            if 'entries' in info:
                info = info['entries'][0]
                
            formats = info.get('formats', [info])
            audio_url = None
            

            for f in formats:
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audio_url = f.get('url')
                    if audio_url:
                        break
            

            if not audio_url:
                audio_url = info.get('url')
                
            return audio_url, info.get('title', 'Titre inconnu')
            
        except Exception as e:
            print(f"Erreur d'extraction audio: {e}")
            return None, f"Erreur: {e}"

async def play_next(ctx, voice_client):
    """Joue la prochaine musique de la file d'attente"""
    if not queues.get(ctx.guild.id):
        await asyncio.sleep(150)
        if not queues.get(ctx.guild.id):
            await voice_client.disconnect()
            voice_clients.pop(ctx.guild.id, None)
            queues.pop(ctx.guild.id, None)
            current_song.pop(ctx.guild.id, None)
            return

    next_song = queues[ctx.guild.id].pop(0)
    video_url = next_song.get("url")
    video_title = next_song.get("title")
    
    try:

        audio_url, confirmed_title = get_audio_url(video_url)
        

        final_title = confirmed_title if confirmed_title and confirmed_title != 'Titre inconnu' else video_title
        
        current_song[ctx.guild.id] = {'url': video_url, 'title': final_title}
        
        player = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options)
        voice_client.play(player, after=lambda e: asyncio.create_task(play_next(ctx, voice_client)))
        
        embed = discord.Embed(title="Lecture en cours", description=f"🎵 **{final_title}**", color=discord.Color.blue())
        await ctx.channel.send(embed=embed)
        
    except Exception as e:
        print(f"Erreur de lecture: {e}")
        embed = discord.Embed(title="Erreur", description=f"❌ Impossible de lire cette piste: {e}", color=discord.Color.red())
        await ctx.channel.send(embed=embed)
        

        if queues.get(ctx.guild.id):
            await play_next(ctx, voice_client)

@client.event
async def on_ready():
    print(f'{client.user} est prêt à jouer de la musique !')
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{prefix}help"))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.lower()
    args = message.content.split()[1:]

    if content.startswith(prefix + "play"):
        if message.author.voice is None:
            embed = discord.Embed(description="❌ Tu dois être dans un canal vocal !", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)
            return

        voice_channel = message.author.voice.channel
        voice_client = voice_clients.get(message.guild.id)

        if not voice_client:
            try:
                voice_client = await voice_channel.connect()
                voice_clients[message.guild.id] = voice_client
            except Exception as e:
                embed = discord.Embed(description=f"❌ Impossible de rejoindre le canal vocal: {e}", color=discord.Color.blue())
                await message.reply(embed=embed, mention_author=False)
                return

        if not args:
            embed = discord.Embed(description="❌ Tu dois fournir un nom de chanson ou une URL.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)
            return

        song_input = " ".join(args)
        
        # Message de chargement
        embed = discord.Embed(description=f"🔍 Recherche en cours...", color=discord.Color.blue())
        loading_msg = await message.channel.send(embed=embed)
        
        try:
            video_url, video_title = search_youtube(song_input)
            
            if not video_url:
                await loading_msg.delete()
                embed = discord.Embed(description=f"❌ Impossible de trouver la chanson: {video_title}", color=discord.Color.blue())
                await message.reply(embed=embed, mention_author=False)
                return
            await loading_msg.delete()
            
            song = {"url": video_url, "title": video_title}

            if message.guild.id not in queues:
                queues[message.guild.id] = []

            queues[message.guild.id].append(song)

            if not voice_client.is_playing():
                await play_next(message, voice_client)
            else:
                embed = discord.Embed(description=f"✅ **{video_title}** ajoutée à la file d'attente.", color=discord.Color.blue())
                await message.reply(embed=embed, mention_author=False)
                
        except Exception as e:
            await loading_msg.delete()
            embed = discord.Embed(description=f"❌ Erreur lors de la recherche: {e}", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)

    elif content.startswith(prefix + "pause"):
        if message.guild.id in voice_clients and voice_clients[message.guild.id].is_playing():
            voice_clients[message.guild.id].pause()
            embed = discord.Embed(description="⏸ Musique en pause.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)
        else:
            embed = discord.Embed(description="❌ Aucune musique en cours.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)

    elif content.startswith(prefix + "resume"):
        if message.guild.id in voice_clients and voice_clients[message.guild.id].is_paused():
            voice_clients[message.guild.id].resume()
            embed = discord.Embed(description="▶️ Musique reprise.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)
        else:
            embed = discord.Embed(description="❌ La musique n'est pas en pause.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)

    elif content.startswith(prefix + "stop"):
        if message.guild.id in voice_clients:
            voice_clients[message.guild.id].stop()
            await voice_clients[message.guild.id].disconnect()
            voice_clients.pop(message.guild.id, None)
            queues.pop(message.guild.id, None)
            current_song.pop(message.guild.id, None)
            embed = discord.Embed(description="⏹ Arrêt de la musique.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)
        else:
            embed = discord.Embed(description="❌ Le bot n'est pas connecté.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)

    elif content.startswith(prefix + "skip"):
        if message.guild.id in voice_clients and voice_clients[message.guild.id].is_playing():
            voice_clients[message.guild.id].stop()
            embed = discord.Embed(description=f":track_next: Musique passée", color=discord.Color.blue())
            await message.reply(embed=embed)
        else:
            embed = discord.Embed(description="❌ Aucune musique en cours.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)

    elif content.startswith(prefix + "queue"):
        if message.guild.id in queues and queues[message.guild.id]:
            embed = discord.Embed(title="File d'attente", color=discord.Color.blue())
            
            for i, song in enumerate(queues[message.guild.id]):
                embed.add_field(name=f"{i+1}. {song['title']}", value="\u200b", inline=False)
                
            await message.reply(embed=embed, mention_author=False)
        else:
            await message.reply("❌ La file d'attente est vide.", mention_author=False)

    elif content.startswith(prefix + "song"):
        song_info = current_song.get(message.guild.id)
        if song_info:
            embed = discord.Embed(title="Chanson actuelle", description=f"🎵 **{song_info['title']}**", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)
        else:
            embed = discord.Embed(description="❌ Aucune musique en cours.", color=discord.Color.blue())
            await message.reply(embed=embed, mention_author=False)

    elif content.startswith(prefix + "help"):
        embed = discord.Embed(title="📜 Commandes du bot", color=discord.Color.blue())
        embed.add_field(name="🎵 **+play [nom ou URL]**", value="Joue une musique", inline=False)
        embed.add_field(name="⏭ **+skip**", value="Passe à la musique suivante", inline=False)
        embed.add_field(name="⏸ **+pause**", value="Met la musique en pause", inline=False)
        embed.add_field(name="▶️ **+resume**", value="Reprend la musique", inline=False)
        embed.add_field(name="⏹ **+stop**", value="Arrête la musique et quitte", inline=False)
        embed.add_field(name="🎶 **+song**", value="Affiche la musique en cours", inline=False)
        embed.add_field(name="📋 **+queue**", value="Affiche la file d'attente", inline=False)
        await message.reply(embed=embed, mention_author=False)


client.run('tkn')
