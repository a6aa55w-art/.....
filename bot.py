import discord
from discord.ext import commands
import asyncio
import yt_dlp

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

queues = {}

def play_next(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and len(queues[guild_id]) > 0:
        next_player = queues[guild_id].pop(0)
        ctx.voice_client.play(next_player, after=lambda e: play_next(ctx) if e is None else print(f'خطأ: {e}'))
        asyncio.run_coroutine_threadsafe(ctx.send(f'🎶 جاري تشغيل الآن: {next_player.title}'), bot.loop)

@bot.command(name='play', help='لتشغيل أغنية')
async def play(ctx, *, query):
    if not ctx.author.voice:
        await ctx.send('يجب أن تكون متصلاً بروم صوتي أولاً!')
        return

    destination = ctx.author.voice.channel
    if ctx.voice_client is None:
        await destination.connect()
    elif ctx.voice_client.channel != destination:
        await ctx.voice_client.move_to(destination)

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            guild_id = ctx.guild.id

            if guild_id not in queues:
                queues[guild_id] = []

            if not ctx.voice_client.is_playing():
                ctx.voice_client.play(player, after=lambda e: play_next(ctx) if e is None else print(f'خطأ: {e}'))
                await ctx.send(f'🎶 جاري تشغيل الآن: {player.title}')
            else:
                queues[guild_id].append(player)
                await ctx.send(f'📥 تمت إضافة الأغنية إلى قائمة الانتظار: {player.title} (الترتيب: {len(queues[guild_id])})')

        except Exception as e:
            await ctx.send(f'حدث خطأ أثناء تحميل المقطع: {e}')

@bot.command(name='stop', help='لإيقاف البوت ومسح القائمة')
async def stop(ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
        await ctx.voice_client.disconnect()
        await ctx.send('🛑 تم إيقاف المشغل ومسح قائمة الانتظار ومغادرة الروم.')
    else:
        await ctx.send('البوت ليس متصلاً بروم صوتي.')

bot.run('ضع_التوكن_هنا')
