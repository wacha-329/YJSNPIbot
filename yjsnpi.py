# invite url : https://discord.com/api/oauth2/authorize?client_id=798810370088239124&permissions=8&scope=bot

import asyncio
import configparser
from datetime import datetime
import datetime as d_time
import discord
import glob
import math
import os
import paramiko
import psutil
import random
import re
import requests
import subprocess
import threading
import time
import youtube_dl
from mcrcon import MCRcon

from func import  diceroll
import log
import constant as const

log.setLogLv('i')

intents=discord.Intents.all()
client = discord.Client(intents=intents)

music_stop = False #プレイリスト再生時のステータス保持用
start_time = time.time()

isDebug = const.default_debugmode

config = configparser.ConfigParser()
config.read(const.ini_file, 'utf-8')
section_serverstatus = 'ServerStatus'
section_serverconfig = 'ServerConfig'

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'dlfile/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)



class YJDownloadException(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    global music_stop
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception:
            raise YJDownloadException

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options, executable='bin/ffmpeg'), data=data)

    @classmethod
    async def from_playlist(cls, message, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        async with message.channel.typing():
            try:
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            except Exception:
                raise YJDownloadException


        for i,play_data in enumerate(data['entries']):
            filename = play_data['url'] if stream else ytdl.prepare_filename(play_data)
            player = cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options, executable='bin/ffmpeg'), data=play_data)
            message.guild.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
            if i == 0:
                async with message.channel.typing():
                    h,m,s = get_h_m_s(d_time.timedelta(seconds=player.data['duration']))
                    if h == 0:
                        duration = str(m).zfill(2) + ":" + str(s).zfill(2)
                    else:
                        duration = str(h) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)
                    embed=discord.Embed(color=0x22d11f, timestamp=datetime.utcnow())
                    embed.set_author(name="YouTube",url="https://www.youtube.com/", icon_url="https://www.youtube.com/s/desktop/2a49de5e/img/favicon_144.png")
                    embed.set_thumbnail(url=player.data['thumbnails'][0]['url'])
                    embed.add_field(name=f"🎸音楽再生 from PlayList  [{i + 1}/{len(data['entries'])}]", value=f"[{player.title}]({player.data['webpage_url']})  ({duration})", inline=False)
                    embed.add_field(name="ステータス", value="▶再生中", inline=False)
                    embed.add_field(name="操作", value="⏯：一時停止/再生　⏹：停止　⏭：次の曲", inline=False)
                    embed.set_footer(text="YJSNPI bot : play music♪")
                    msg = await message.channel.send(embed=embed)
                    emoji_list_playlist = ['⏯', '⏹', '⏭']
                    for add_emoji in emoji_list_playlist:
                        await msg.add_reaction(add_emoji)

            elif i == len(data['entries']) - 1:
                    h,m,s = get_h_m_s(d_time.timedelta(seconds=player.data['duration']))
                    if h == 0:
                        duration = str(m).zfill(2) + ":" + str(s).zfill(2)
                    else:
                        duration = str(h) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)
                    embed = msg.embeds[0]
                    embed.set_thumbnail(url=player.data['thumbnails'][0]['url'])
                    embed.set_field_at(0,name=f"🎸音楽再生 from PlayList  [{i + 1}/{len(data['entries'])}]", value=f"[{player.title}]({player.data['webpage_url']})  ({duration})", inline=False)
                    embed.set_field_at(1,name="ステータス", value="▶再生中", inline=False)
                    embed.set_field_at(2,name="操作", value="⏯：一時停止/再生　⏹：停止", inline=False)
                    await msg.edit(embed=embed)
                    bot_member = message.guild.get_member(const.bot_author_id)
                    await msg.remove_reaction('⏭', bot_member)

            else:
                h,m,s = get_h_m_s(d_time.timedelta(seconds=player.data['duration']))
                if h == 0:
                    duration = str(m).zfill(2) + ":" + str(s).zfill(2)
                else:
                    duration = str(h) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)
                embed = msg.embeds[0]
                embed.set_thumbnail(url=player.data['thumbnails'][0]['url'])
                embed.set_field_at(0,name=f"🎸音楽再生 from PlayList  [{i + 1}/{len(data['entries'])}]", value=f"[{player.title}]({player.data['webpage_url']})  ({duration})", inline=False)
                embed.set_field_at(1,name="ステータス", value="▶再生中", inline=False)
                await msg.edit(embed=embed)

            while message.guild.voice_client.is_playing() or message.guild.voice_client.is_paused():
                await asyncio.sleep(1)
                pass
            await asyncio.sleep(2)
            if music_stop:
                break
        if music_stop:
            pass
        else:
            embed = msg.embeds[0]
            embed.set_field_at(1,name="ステータス", value="⏹停止", inline=True)
            embed.set_field_at(2,name="再生終了", value="新たに再生する場合は、!playコマンドを実行してください", inline=False)
            await msg.edit(embed=embed)
            await msg.clear_reactions()
            remove_file()




@client.event
async def on_ready():
    log.i('Logged in as')
    log.i(client.user.name)
    log.i(client.user.id)
    await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
    log.i('Bot started.')
    log.i('----------------')


@client.event
async def on_message(message):
    global isDebug
    global music_stop
    if message.author.bot or message.guild.id != const.guild_id:
        return

    if message.channel.id != const.bot_channel_id:
        if message.content[0:1] == '!':
            embed = discord.Embed(title="コマンドエラー", description=f"ここではコマンドを使用することはできません。\n<#{const.bot_channel_id}>で使用してください。", color=0xff0000, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
        return

    log.i('--- command received ---')
    log.i(f'command = {message.content} / user = {message.author.name} / id = {message.author.id}')
    log.i('------------------------')

    if message.content.startswith("!test"):
        return

    elif message.content.startswith("!dbg.on"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="Debugモード", description="❌デバッグモードを変更する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
        else:
            isDebug = True
            embed = discord.Embed(title="Debugモード", description="⭕デバッグモードONに変更しました。", color=0xff0000, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!dbg.off"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="Debugモード", description="❌デバッグモードを変更する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
        else:
            isDebug = False
            embed = discord.Embed(title="Debugモード", description="⭕デバッグモードをOFFに変更しました。", color=0xff0000, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!dbg.is"):
        if isDebug:
            embed = discord.Embed(title="Debugモード", description="現在のデバッグモードはONです", color=0xff0000, timestamp=datetime.utcnow())
        else:
            embed = discord.Embed(title="Debugモード", description="現在のデバッグモードはOFFです", color=0xff0000, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!n.join.on"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="通知モード変更", description="❌通知モードを変更する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
        else:
            config.set(section_serverconfig, 'default_join_notification', 'true')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            embed = discord.Embed(title="通知モード変更", description="⭕通知モード(参加時)をONに変更しました。", color=0xff0000, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!n.join.off"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="通知モード変更", description="❌通知モードを変更する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
        else:
            config.set(section_serverconfig, 'default_join_notification', 'false')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            embed = discord.Embed(title="通知モード変更", description="⭕通知モード(参加時)をOFFに変更しました。", color=0xff0000, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!n.leave.on"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="通知モード変更", description="❌通知モードを変更する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
        else:
            config.set(section_serverconfig, 'default_leave_notification', 'true')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            embed = discord.Embed(title="通知モード変更", description="⭕通知モード(退出時)をONに変更しました。", color=0xff0000, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!n.leave.off"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="通知モード変更", description="❌通知モードを変更する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
        else:
            config.set(section_serverconfig, 'default_leave_notification', 'false')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            embed = discord.Embed(title="通知モード変更", description="⭕通知モード(退出時)をOFFに変更しました。", color=0xff0000, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!n.conf"):
        embed = discord.Embed(title="VC入退出設定", description="現在の設定は以下の通りです", color=0xff0000, timestamp=datetime.utcnow())
        if config.get(section_serverconfig, 'default_join_notification') == 'true':
            embed.add_field(name="入室時", value="現在は ON です", inline=True)
        else:
            embed.add_field(name="入室時", value="現在は OFF です", inline=True)
        if config.get(section_serverconfig, 'default_leave_notification') == 'true':
            embed.add_field(name="退出時", value="現在は ON です", inline=True)
        else:
            embed.add_field(name="退出時", value="現在は OFF です", inline=True)
        await message.channel.send(embed=embed)

    elif message.content.startswith("!dice"):
        say = message.content
        # [!dice ]部分を消し、AdBのdで区切ってリスト化する
        order = say.strip('!dice ')
        cnt, mx = list(map(int, order.split('d'))) # さいころの個数と面数

        embed = discord.Embed(title="🎲ダイスロール結果", description=str(mx) + "面のサイコロを " + str(cnt) + "個投げた！", color=0xa57373, timestamp=datetime.utcnow())
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
        dice = diceroll(cnt, mx)
        embed.add_field(name="合計", value=str(dice[cnt]), inline=False)
        del dice[cnt]
        embed.add_field(name="内訳", value=str(dice), inline=False)
        embed.set_footer(text="YJSNPI bot : dice roll")
        await message.channel.send(embed=embed)

    elif message.content.startswith("!run"):
        embed = discord.Embed(title="🕹サーバー起動", description="起動したいサーバーを以下から選び、\n対応するリアクションをクリックしてください", color=0xec7627, timestamp=datetime.utcnow())
        embed.add_field(name="1️⃣", value="ARK: HGC Server を起動する", inline=True)
        embed.add_field(name="2️⃣", value="Minecraft: Knee-high Boots Server を起動する", inline=True)
        embed.add_field(name="3️⃣", value="Minecraft: Werewolf Server を起動する", inline=True)
        embed.add_field(name="4️⃣", value="Minecraft: Vanilla Server を起動する", inline=True)
        embed.add_field(name="5️⃣", value="Valheim: HGC Server を起動する", inline=True)
        embed.add_field(name="❌", value="キャンセル", inline=True)
        embed.set_footer(text="YJSNPI bot : run server")
        msg = await message.channel.send(embed=embed)

        emoji_list = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '❌']
        for add_emoji in emoji_list:
            await msg.add_reaction(add_emoji)

        def check(reaction, user):
            return user == message.author and str(reaction.emoji) in emoji_list

        #リアクションが付けられるまで待機
        reaction, user = await client.wait_for('reaction_add', check=check)

        #付けられたリアクション毎に実装
        if str(reaction.emoji) == (emoji_list[0]):
            if config.get(section_serverstatus, 'ark_1') == '0':
                embed_1 = discord.Embed(title="🕹サーバー起動", description="ARK: HGC Server を起動しました。\n以下のリンクから起動状況を確認してください。", color=0xec7627, timestamp=datetime.utcnow())
                embed_1.add_field(name="1️⃣", value="ARK: HGC Server を起動する", inline=True)
                embed_1.add_field(name="確認", value="[リンク1](http://bit.ly/2JqCR8F) | [リンク2](http://arkservers.net/server/159.28.185.54:27015)", inline=True)
                config.set(section_serverstatus, 'ark_1', '1')
                with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                    config.write(conffile)
                await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
                log.i('ARK: HGC started. User:' + message.author.name)

                if isDebug:
                    embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー起動しません", inline=False)
                else:
                    ark_island_start_thread = threading.Thread(target=ark_start, args=('TheIsland', ))
                    ark_island_start_thread.start()
            else:
                embed_1 = discord.Embed(title="🕹サーバー起動", description="ARK: HGC Server は既に起動済みです。", color=0xec7627, timestamp=datetime.utcnow())

        elif str(reaction.emoji) == (emoji_list[1]):
            if config.get(section_serverstatus, 'mine_1') == '0':
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Minecraft: Knee-high Boots Server を起動しました。", color=0xec7627, timestamp=datetime.utcnow())
                embed_1.add_field(name="2️⃣", value="Minecraft: Knee-high Boots Server を起動する", inline=True)
                config.set(section_serverstatus, 'mine_1', '1')
                with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                    config.write(conffile)
                await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
                log.i('Minecraft: Knee-high started. User:' + message.author.name)

                if isDebug:
                    embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー起動しません", inline=False)
                else:
                    subprocess.Popen(['start', const.run_mine_knee_bat], shell=True, cwd=const.run_mine_knee_path)
            else:
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Minecraft: Knee-high Boots Server は既に起動済みです。", color=0xec7627, timestamp=datetime.utcnow())

        elif str(reaction.emoji) == (emoji_list[2]):
            if config.get(section_serverstatus, 'mine_2') == '0':
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Minecraft: Werewolf Server を起動しました。", color=0xec7627, timestamp=datetime.utcnow())
                embed_1.add_field(name="3️⃣", value="Minecraft: Werewolf Server を起動する", inline=True)
                config.set(section_serverstatus, 'mine_2', '1')
                with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                    config.write(conffile)
                await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
                log.i('Minecraft: Werewolf started. User:' + message.author.name)

                if isDebug:
                    embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー起動しません", inline=False)
                else:
                    subprocess.Popen(['start', const.run_mine_wolf_bat], shell=True, cwd=const.run_mine_wolf_path)
            else:
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Minecraft: Werewolf Server は既に起動済みです。", color=0xec7627, timestamp=datetime.utcnow())

        elif str(reaction.emoji) == (emoji_list[3]):
            if config.get(section_serverstatus, 'mine_3') == '0':
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Minecraft: Vanilla Server を起動しました。", color=0xec7627, timestamp=datetime.utcnow())
                embed_1.add_field(name="4️⃣", value="Minecraft: Vanilla Server を起動する", inline=True)
                config.set(section_serverstatus, 'mine_3', '1')
                with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                    config.write(conffile)
                await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
                log.i('Minecraft: Vanilla started. User:' + message.author.name)

                if isDebug:
                    embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー起動しません", inline=False)
                else:
                    subprocess.Popen(['start', const.run_mine_vanilla_bat], shell=True, cwd=const.run_mine_vanilla_path)
            else:
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Minecraft: Vanilla Server は既に起動済みです。", color=0xec7627, timestamp=datetime.utcnow())

        elif str(reaction.emoji) == (emoji_list[4]):
            if config.get(section_serverstatus, 'val_1') == '0':
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Valheim: HGC Server を起動します。", color=0xec7627, timestamp=datetime.utcnow())
                embed_1.add_field(name="4️⃣", value="Valheim: HGC Server を起動する", inline=True)
                config.set(section_serverstatus, 'val_1', '1')
                with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                    config.write(conffile)
                await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
                log.i('Valheim: HGC started. User:' + message.author.name)

                if isDebug:
                    embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー起動しません", inline=False)
                else:
                    val_start_thread = threading.Thread(target=valheim_start)
                    val_start_thread.start()
                    embed_1.add_field(name="起動完了", value="サーバー起動が完了しました。", inline=False)
            else:
                embed_1 = discord.Embed(title="🕹サーバー起動", description="Valheim: HGC Server は既に起動済みです。", color=0xec7627, timestamp=datetime.utcnow())

        elif str(reaction.emoji) == (emoji_list[5]):
            embed_1 = discord.Embed(title="🕹サーバー起動", description="キャンセルしました。", color=0xec7627, timestamp=datetime.utcnow())

        else:
            embed_1 = discord.Embed(title="エラー発生", description="想定外のエラーが発生しました。\nはじめから操作をやり直してください。", color=0xec7627, timestamp=datetime.utcnow())

        embed_1.set_footer(text="YJSNPI bot : run server")
        await msg.clear_reactions()
        await msg.edit(embed=embed_1)

    elif message.content.startswith("!stop"):
        active_cnt,status_no = await getServerStatus()
        emoji_stop = []

        if active_cnt == 0:
            embed = discord.Embed(title="🛑サーバー停止", description="現在起動しているサーバーはありません。", color=0x6e4695, timestamp=datetime.utcnow())
        elif active_cnt == 1:
            emoji_stop.append('⭕')
            emoji_stop.append('❌')
            embed = discord.Embed(title="🛑サーバー停止", description="現在起動しているサーバーを停止しますか？\n停止する場合は⭕を、キャンセルする場合は❌を押してください。", color=0x6e4695, timestamp=datetime.utcnow())
            if status_no & 0b00000001 != 0:
                embed.add_field(name="起動中のサーバー", value="ARK: HGC Server", inline=True)
            if status_no & 0b00000010 != 0:
                embed.add_field(name="起動中のサーバー", value="Minecraft: Knee-high Boots Server", inline=True)
            if status_no & 0b00000100 != 0:
                embed.add_field(name="起動中のサーバー", value="Minecraft: Werewolf Server", inline=True)
            if status_no & 0b00001000 != 0:
                embed.add_field(name="起動中のサーバー", value="Minecraft: Vanilla Server", inline=True)
            if status_no & 0b00010000 != 0:
                embed.add_field(name="起動中のサーバー", value="Valheim: HGC Server", inline=True)
        else:
            embed = discord.Embed(title="🛑サーバー停止", description="停止したいサーバーを以下から選択してください。", color=0x6e4695, timestamp=datetime.utcnow())
            if status_no & 0b00000001 != 0:
                embed.add_field(name="1️⃣", value="ARK: HGC Server", inline=True)
                emoji_stop.append('1️⃣')
            if status_no & 0b00000010 != 0:
                embed.add_field(name="2️⃣", value="Minecraft: Knee-high Boots Server", inline=True)
                emoji_stop.append('2️⃣')
            if status_no & 0b00000100 != 0:
                embed.add_field(name="3️⃣", value="Minecraft: Werewolf Server", inline=True)
                emoji_stop.append('3️⃣')
            if status_no & 0b00001000 != 0:
                embed.add_field(name="4️⃣", value="Minecraft: Vanilla Server", inline=True)
                emoji_stop.append('4️⃣')
            if status_no & 0b00010000 != 0:
                embed.add_field(name="5️⃣", value="Valheim: HGC Server", inline=True)
                emoji_stop.append('5️⃣')
            embed.add_field(name="❌", value="キャンセル", inline=True)
            emoji_stop.append('❌')
            if active_cnt == 3:
                embed.add_field(name="\u200B", value="\u200B", inline=True)
                embed.add_field(name="\u200B", value="\u200B", inline=True)
            elif active_cnt == 4:
                embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.set_footer(text="YJSNPI bot : stop server")
        msg = await message.channel.send(embed=embed)

        for add_emoji in emoji_stop:
            await msg.add_reaction(add_emoji)

        def check_stop(reaction, user):
            return user == message.author and str(reaction.emoji) in emoji_stop

        reaction, user = await client.wait_for('reaction_add', check=check_stop)

        if str(reaction.emoji) == ('1️⃣') and str(reaction.emoji) in emoji_stop:
            embed_1 = discord.Embed(title="🛑サーバー停止", description="ARK: HGC Server を停止しました。", color=0x6e4695, timestamp=datetime.utcnow())
            embed_1.add_field(name="1️⃣", value="ARK: HGC Server", inline=True)
            config.set(section_serverstatus, 'ark_1', '0')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
            log.i('ARK: HGC stopped. User:' + message.author.name)

            if isDebug:
                embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー停止しません", inline=False)
            else:
                ark_island_stop_thread = threading.Thread(target=ark_stop, args=('TheIsland', ))
                ark_island_stop_thread.start()

        elif str(reaction.emoji) == ('2️⃣') and str(reaction.emoji) in emoji_stop:
            embed_1 = discord.Embed(title="🛑サーバー停止", description="Minecraft: Knee-high Boots Server を停止しました。", color=0x6e4695, timestamp=datetime.utcnow())
            embed_1.add_field(name="2️⃣", value="Minecraft: Knee-high Boots Server", inline=True)
            config.set(section_serverstatus, 'mine_1', '0')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
            log.i('Minecraft: Knee-high stopped. User:' + message.author.name)

            if isDebug:
                embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー停止しません", inline=False)
            else:
                with MCRcon(const.mine_rcon_host.knee.value, const.mine_rcon_pass.knee.value, port=const.mine_rcon_port.knee.value) as mcr:
                    res = mcr.command('save-all')
                    log.i(res)
                    res = mcr.command('stop')
                    log.i(res)

        elif str(reaction.emoji) == ('3️⃣') and str(reaction.emoji) in emoji_stop:
            embed_1 = discord.Embed(title="🛑サーバー停止", description="Minecraft: Werewolf Server を停止しました。", color=0x6e4695, timestamp=datetime.utcnow())
            embed_1.add_field(name="3️⃣", value="Minecraft: Werewolf Server", inline=True)
            config.set(section_serverstatus, 'mine_2', '0')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
            log.i('Minecraft: Werewolf stopped. User:' + message.author.name)

            if isDebug:
                embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー停止しません", inline=False)
            else:
                with MCRcon(const.mine_rcon_host.wolf.value, const.mine_rcon_pass.wolf.value, port=const.mine_rcon_port.wolf.value) as mcr:
                    res = mcr.command('save-all')
                    log.i(res)
                    res = mcr.command('stop')
                    log.i(res)

        elif str(reaction.emoji) == ('4️⃣') and str(reaction.emoji) in emoji_stop:
            embed_1 = discord.Embed(title="🛑サーバー停止", description="Minecraft: Vanilla Server を停止しました。", color=0x6e4695, timestamp=datetime.utcnow())
            embed_1.add_field(name="4️⃣", value="Minecraft: Vanilla Server", inline=True)
            config.set(section_serverstatus, 'mine_3', '0')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
            log.i('Minecraft: Vanilla stopped. User:' + message.author.name)

            if isDebug:
                embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー停止しません", inline=False)
            else:
                with MCRcon(const.mine_rcon_host.vanilla.value, const.mine_rcon_pass.vanilla.value, port=const.mine_rcon_port.vanilla.value) as mcr:
                    res = mcr.command('save-all')
                    log.i(res)
                    res = mcr.command('stop')
                    log.i(res)

        elif str(reaction.emoji) == ('5️⃣') and str(reaction.emoji) in emoji_stop:
            embed_1 = discord.Embed(title="🛑サーバー停止", description="Valheim: HGC Server を停止しました。", color=0x6e4695, timestamp=datetime.utcnow())
            embed_1.add_field(name="5️⃣", value="Valheim: HGC Server", inline=True)
            config.set(section_serverstatus, 'val_1', '0')
            with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                config.write(conffile)
            await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
            log.i('Valheim: HGC stopped. User:' + message.author.name)

            if isDebug:
                embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー停止しません", inline=False)
            else:
                val_stop_thread = threading.Thread(target=valheim_stop)
                val_stop_thread.start()

        elif str(reaction.emoji) == ('⭕') and str(reaction.emoji) in emoji_stop:
            server_name,ini_name,exec_path = await getStopServerConstant(status_no)
            if server_name is not None:
                embed_1 = discord.Embed(title="🛑サーバー停止", description=server_name + "を停止しました。", color=0x6e4695, timestamp=datetime.utcnow())
                embed_1.add_field(name="⭕", value=server_name, inline=True)
                config.set(section_serverstatus, ini_name, '0')
                with open(const.ini_file, "w", encoding="UTF-8") as conffile:
                    config.write(conffile)
                await client.change_presence(activity=discord.Game(name=await getStatusMsg()))
                log.i(server_name + ' stopped. User:' + message.author.name)

                if isDebug:
                    embed_1.add_field(name="デバッグモード中", value="デバッグモードのためサーバー停止しません", inline=False)
                else:
                    if ini_name == 'val_1':
                        val_stop_thread = threading.Thread(target=valheim_stop)
                        val_stop_thread.start()
                    elif ini_name == 'ark_1':
                        ark_island_stop_thread = threading.Thread(target=ark_stop, args=('TheIsland', ))
                        ark_island_stop_thread.start()
                    elif ini_name == 'mine_1':
                        with MCRcon(const.mine_rcon_host.knee.value, const.mine_rcon_pass.knee.value, port=const.mine_rcon_port.knee.value) as mcr:
                            res = mcr.command('save-all')
                            log.i(res)
                            res = mcr.command('stop')
                            log.i(res)
                    elif ini_name == 'mine_2':
                        with MCRcon(const.mine_rcon_host.wolf.value, const.mine_rcon_pass.wolf.value, port=const.mine_rcon_port.wolf.value) as mcr:
                            res = mcr.command('save-all')
                            log.i(res)
                            res = mcr.command('stop')
                            log.i(res)
                    elif ini_name == 'mine_3':
                        with MCRcon(const.mine_rcon_host.vanilla.value, const.mine_rcon_pass.vanilla.value, port=const.mine_rcon_port.vanilla.value) as mcr:
                            res = mcr.command('save-all')
                            log.i(res)
                            res = mcr.command('stop')
                            log.i(res)

                    #else:
                    #    subprocess.Popen(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', exec_path)))
            else:
                embed_1 = discord.Embed(title="エラー発生", description="想定外のエラーが発生しました。\nはじめから操作をやり直してください。", color=0x6e4695, timestamp=datetime.utcnow())

        elif str(reaction.emoji) == ('❌') and str(reaction.emoji) in emoji_stop:
            embed_1 = discord.Embed(title="🛑サーバー停止", description="キャンセルしました。", color=0x6e4695, timestamp=datetime.utcnow())

        else:
            embed_1 = discord.Embed(title="エラー発生", description="想定外のエラーが発生しました。\nはじめから操作をやり直してください。", color=0x6e4695, timestamp=datetime.utcnow())

        embed_1.set_footer(text="YJSNPI bot : stop server")
        await msg.clear_reactions()
        await msg.edit(embed=embed_1)

    elif message.content.startswith("!server"):
        embed = discord.Embed(title="💻サーバー情報", description="各サーバーの情報について", color=0x2dd0d2, timestamp=datetime.utcnow())
        embed.add_field(name="ARK:\nHGC Server", value="Server Name:\n`HGC Server`\nPassword : `yjsnpi`", inline=True)
        embed.add_field(name="Minecraft:\nKnee-high Boots Server", value="Server Address:\n`wacha.work:25565`\nVersion : `1.8.9`", inline=True)
        embed.add_field(name="Minecraft:\nWerewolf Server", value="Server Address:\n`wacha.work:25566`\nVersion: `1.12.2`", inline=True)
        embed.add_field(name="Minecraft:\nVanilla Server", value="Server Address:\n`wacha.work:25567`\nVersion: `1.16.5`", inline=True)
        embed.add_field(name="Valheim:\nHGC Server", value="Server Address:\n`wacha.work:2457`\nPassword : `yjsnpi`", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.set_footer(text="YJSNPI bot : server info")
        msg = await message.channel.send(embed=embed)

    elif message.content.startswith("!n.new"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="🔔入退室通知設定変更", description="❌新規メッセージを作成する権限がありません", color=0x2f9282, timestamp=datetime.utcnow())
            embed.set_footer(text="YJSNPI bot : notification settings")
            await message.channel.send(embed=embed)
            return
        else:
            isDebug = True
            embed = discord.Embed(title="🔔入退室通知設定変更", description="入退出通知の設定を変更する", color=0x2f9282, timestamp=datetime.utcnow())
            embed.add_field(name="🔔", value='通知ON', inline=True)
            embed.add_field(name="🔕", value='通知OFF', inline=True)
            embed.set_footer(text="YJSNPI bot : notification settings")
        emoji_list_notification = ['🔔', '🔕']
        channel = client.get_channel(const.bot_channel_id)
        pin_msg = await channel.pins()
        for pin_msg_elem in pin_msg:
            if pin_msg_elem.author.id == const.bot_author_id:
                await pin_msg_elem.unpin()
                await pin_msg_elem.delete()
        msg = await message.channel.send(embed=embed)
        for add_emoji in emoji_list_notification:
            await msg.add_reaction(add_emoji)
        await msg.pin()
        await channel.edit(topic='🔔入退室通知設定変更: ' + msg.jump_url)
        async for message_history in channel.history(limit=1):
            if message_history.system_content.endswith('pinned a message to this channel.'):
                await message_history.delete()
        config.set(section_serverconfig, 'role_grant_message_id', str(msg.id))
        with open(const.ini_file, "w", encoding="UTF-8") as conffile:
            config.write(conffile)

    elif message.content.startswith("!join"):
        if message.author.voice is None:
            embed=discord.Embed(title="🎸VC接続", description="ボイスチャンネルに参加してからコマンドを実行してください。", color=0x22d11f, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        voice_client = message.guild.voice_client
        if voice_client is not None:
            await voice_client.move_to(message.author.voice.channel)
        await message.author.voice.channel.connect()
        embed=discord.Embed(title="🎸VC接続", description="ボイスチャンネルに接続しました。", color=0x22d11f, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content == "!leave":
        if message.guild.voice_client is None:
            embed=discord.Embed(title="🎸VC切断", description="現在、このbotはVCに接続していません。", color=0x22d11f, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        # 切断する
        await message.guild.voice_client.disconnect()
        embed=discord.Embed(title="🎸VC切断", description="ボイスチャンネルから切断しました。", color=0x22d11f, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)

    elif message.content.startswith("!play "):
        if message.author.voice is None:
            embed=discord.Embed(title="🎸音楽再生", description="ボイスチャンネルに参加してからコマンドを実行してください。", color=0x22d11f, timestamp=datetime.utcnow())
            embed.set_footer(text="YJSNPI bot : play music♪")
            await message.channel.send(embed=embed)
            return
        voice_client = message.guild.voice_client

        if voice_client is None:
            await message.author.voice.channel.connect()
        elif voice_client.channel.id !=  message.author.voice.channel.id:
            await voice_client.move_to(message.author.voice.channel)

        # 再生中の場合は再生しない
        if message.guild.voice_client.is_playing() or message.guild.voice_client.is_paused():
            embed=discord.Embed(title="🎸音楽再生", description="現在、再生中です。\n再生中の音楽を停止してから実行してください。", color=0x22d11f, timestamp=datetime.utcnow())
            embed.set_footer(text="YJSNPI bot : play music♪")
            await message.channel.send(embed=embed)
            return

        url = message.content.strip('!play ')
        check_url = requests.get(url).url
        if re.search('playlist', check_url):
            music_stop = False
            await YTDLSource.from_playlist(message, url, loop=client.loop)
        else:
            async with message.channel.typing():
                try:
                    player = await YTDLSource.from_url(url, loop=client.loop)
                except YJDownloadException as e:
                    embed=discord.Embed(title="🎸音楽再生", description=f"❌エラー発生 \nURLを確認してください", color=0x22d11f, timestamp=datetime.utcnow())
                    log.i(e)
                    await message.channel.send(embed=embed)
                    return
                message.guild.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
                h,m,s = get_h_m_s(d_time.timedelta(seconds=player.data['duration']))
                if h == 0:
                    duration = str(m).zfill(2) + ":" + str(s).zfill(2)
                else:
                    duration = str(h) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)
                embed=discord.Embed(color=0x22d11f, timestamp=datetime.utcnow())
                embed.set_author(name="YouTube",url="https://www.youtube.com/", icon_url="https://www.youtube.com/s/desktop/2a49de5e/img/favicon_144.png")
                embed.set_thumbnail(url=player.data['thumbnails'][0]['url'])
                embed.add_field(name="🎸音楽再生", value=f"[{player.title}]({player.data['webpage_url']})  ({duration})", inline=False)
                embed.add_field(name="ステータス", value="▶再生中", inline=False)
                embed.add_field(name="操作", value="⏯：一時停止/再生　⏹：停止", inline=False)
                embed.set_footer(text="YJSNPI bot : play music♪")
                msg = await message.channel.send(embed=embed)
                emoji_list_test = ['⏯', '⏹']
                for add_emoji in emoji_list_test:
                    await msg.add_reaction(add_emoji)

        while message.guild.voice_client.is_playing() or message.guild.voice_client.is_paused():
            await asyncio.sleep(1)
            pass

        if music_stop:
            return
        else:
            embed = msg.embeds[0]
            embed.set_field_at(1,name="ステータス", value="⏹停止", inline=True)
            embed.set_field_at(2,name="再生終了", value="新たに再生する場合は、!playコマンドを実行してください", inline=False)
            await msg.edit(embed=embed)
            await msg.clear_reactions()
            remove_file()

    elif message.content == "!m.stop":
        if message.guild.voice_client is None:
            embed=discord.Embed(title="🎸音楽停止", description="VCに接続していません。", color=0x22d11f, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return

        if not message.guild.voice_client.is_playing():
            embed=discord.Embed(title="🎸音楽停止", description="現在、音楽は再生していません。", color=0x22d11f, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return

        message.guild.voice_client.stop()

        embed=discord.Embed(title="🎸音楽停止", description="音楽を停止しました。", color=0x22d11f, timestamp=datetime.utcnow())
        await message.channel.send(embed=embed)
        remove_file()

    elif message.content.startswith("!team "):
        if message.author.voice is None:
            embed=discord.Embed(title="👬チーム分け", description="ボイスチャンネルに参加してからコマンドを実行してください。", color=0x2e6b5f, timestamp=datetime.utcnow())
            embed.set_footer(text="YJSNPI bot : team building")
            await message.channel.send(embed=embed)
            return
        if len(message.author.voice.channel.members) <= 1:
            embed=discord.Embed(title="👬チーム分け", description="2人以上メンバーがいる状態で実行してください。", color=0x2e6b5f, timestamp=datetime.utcnow())
            embed.set_footer(text="YJSNPI bot : team building")
            await message.channel.send(embed=embed)
            return
        team_num = message.content.strip('!team ')
        if not team_num.isdecimal():
            embed=discord.Embed(title="👬チーム分け", description="チーム数は数字(2-10の範囲)を指定してください。", color=0x2e6b5f, timestamp=datetime.utcnow())
            embed.set_footer(text="YJSNPI bot : team building")
            await message.channel.send(embed=embed)
            return
        team_num = int(team_num)
        if team_num <= 1 or team_num > 10:
            embed=discord.Embed(title="👬チーム分け", description="チーム数は2-10の範囲で指定してください。", color=0x2e6b5f, timestamp=datetime.utcnow())
            embed.set_footer(text="YJSNPI bot : team building")
            await message.channel.send(embed=embed)
            return

        members = message.author.voice.channel.members
        embed=discord.Embed(title="👬チーム分け", description=f"{message.author.voice.channel.name}チャンネルに参加しているメンバーを{team_num}チームに分けます。", color=0x2e6b5f, timestamp=datetime.utcnow())
        embed.set_footer(text="YJSNPI bot : team building")
        embed.add_field(name="\u200B", value="メンバー読込中...", inline=True)
        msg = await message.channel.send(embed=embed)
        for i, check_bot in enumerate(members):
            if check_bot.bot:
                del members[i]

        emoji_a = 0x0001F1E6
        emoji_list = []
        embed_memcheck=discord.Embed(title="👬チーム分け", description=f"{message.author.voice.channel.name}チャンネルに参加しているメンバーを{team_num}チームに分けます。", color=0x2e6b5f, timestamp=datetime.utcnow())
        embed_memcheck.set_footer(text="YJSNPI bot : team building")
        for i,member in enumerate(members):
            embed_memcheck.add_field(name=f"{chr(emoji_a + i)}", value=f"{member.mention}", inline=True)
            emoji_list.append(chr(emoji_a + i))
            if i == len(members) - 1:
                emoji_list.append('🆗')
        if len(members) % 3 == 1:
            embed_memcheck.add_field(name="\u200B", value="\u200B", inline=True)
            embed_memcheck.add_field(name="\u200B", value="\u200B", inline=True)
        elif len(members) % 3 == 2:
            embed_memcheck.add_field(name="\u200B", value="\u200B", inline=True)
        embed_memcheck.add_field(name="メンバーチェック", value="上記メンバーでチーム分けから除外するメンバーが居る場合は、対応したリアクションをクリックし、確定したら🆗をクリックしてください。", inline=False)
        if len(members) % team_num != 0:
            embed_memcheck.add_field(name="注意", value="※現在のメンバーでは、チームを均等に分けられません※\n※このままチーム分けを実行することも可能です※", inline=False)
        await msg.edit(embed=embed_memcheck)
        for add_emoji in emoji_list:
            await msg.add_reaction(add_emoji)

        def member_check(reaction, user):
            return user == message.author and str(reaction.emoji) in emoji_list

        while True:
            reaction, user = await client.wait_for('reaction_add', check=member_check)
            if reaction.emoji == '🆗':
                await msg.clear_reactions()
                break
            index = emoji_list.index(reaction.emoji)
            del members[index]
            del emoji_list[index]
            embed_memcheck.clear_fields()
            for i,member in enumerate(members):
                embed_memcheck.add_field(name=f"{emoji_list[i]}", value=f"{member.mention}", inline=True)
            if len(members) % 3 == 1:
                embed_memcheck.add_field(name="\u200B", value="\u200B", inline=True)
                embed_memcheck.add_field(name="\u200B", value="\u200B", inline=True)
            elif len(members) % 3 == 2:
                embed_memcheck.add_field(name="\u200B", value="\u200B", inline=True)
            embed_memcheck.add_field(name="メンバーチェック", value="上記メンバーでチーム分けから除外するメンバーが居る場合は、対応したリアクションをクリックし、確定したら🆗をクリックしてください。", inline=True)
            if len(members) % team_num != 0:
                embed_memcheck.add_field(name="注意", value="※現在のメンバーでは、チームを均等に分けられません※\n※このままチーム分けを実行することも可能です※", inline=False)
            await msg.edit(embed=embed_memcheck)
            await msg.clear_reaction(reaction.emoji)

        random.shuffle(members)

        embed_team_members=discord.Embed(title="👬チーム分け", description="チーム分け完了！", color=0x2e6b5f, timestamp=datetime.utcnow())
        embed_team_members.set_footer(text="YJSNPI bot : team building")
        for team_name in range(team_num):
            team_members = members[team_name:len(members):team_num]
            m = None
            for i,team_member in enumerate(team_members):
                if i == 0:
                    m = str(team_member.mention) + '\n'
                else:
                    m += str(team_member.mention) + '\n'
            embed_team_members.add_field(name=f"チーム{team_name + 1}", value=m, inline=True)
        if team_num % 3 == 1:
            embed_team_members.add_field(name="\u200B", value="\u200B", inline=True)
            embed_team_members.add_field(name="\u200B", value="\u200B", inline=True)
        elif team_num % 3 == 2:
            embed_team_members.add_field(name="\u200B", value="\u200B", inline=True)
        await msg.edit(embed=embed_team_members)

    elif message.content.startswith("!poll"):
        msg_replaced = message.content.replace('　', ' ')
        msg_arg = msg_replaced.split(' ')
        if len(msg_arg) <= 3:
            embed = discord.Embed(title="💭アンケート", description="コマンドを確認してください。引数が足りません。\n \
                                    例:`!poll 質問内容 選択肢1 選択肢2 [任意]投稿したいチャンネルID`", color=0xff0000, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        del msg_arg[0]
        send_ch_id = None
        if (len(msg_arg[-1]) == 18) and (discord.utils.get(message.guild.text_channels, id=int(msg_arg[-1])) is not None):
            send_ch_id = int(msg_arg.pop(-1))
        else:
            send_ch_id = int(const.general_channel_id)
        embed_title = "💭アンケート\n「" + msg_arg.pop(0) + "」"
        emoji_a = 0x0001F1E6
        emoji_list = []
        embed_description = ''
        for i,item in enumerate(msg_arg):
            embed_description += chr(emoji_a + i) +  " " + item + "\n"
            emoji_list.append(chr(emoji_a + i))
            if i == len(msg_arg) - 1:
                emoji_list.append('✅')
                emoji_list.append('❎')
        embed_description += "\n`投票結果を確認する場合は✅を、終了する場合は❎をクリックしてください。\n❎リアクションを削除することで、投票再開できます。`"
        embed = discord.Embed(title=embed_title, description=embed_description, color=0x3da9a1, timestamp=datetime.utcnow())
        embed.set_footer(text='YJSNPI bot : poll')
        send_channel = client.get_channel(send_ch_id)
        msg = await send_channel.send(embed=embed)
        for add_emoji in emoji_list:
            await msg.add_reaction(add_emoji)
        await send_channel.edit(topic='⚡アンケート実施中！: ' + msg.jump_url)

    elif message.content == "!help":
        embed = discord.Embed(title="❔ヘルプ", description="利用できるコマンド/機能は以下です", color=0xb863cf, timestamp=datetime.utcnow())
        embed.add_field(name="🕹`!run`", value="Minecraft/ARKのサーバーを起動", inline=True)
        embed.add_field(name="🛑`!stop`", value="Minecraft/ARKのサーバーを停止", inline=True)
        embed.add_field(name="💻!`server`", value="Minecraft/ARKのサーバー情報を表示", inline=True)
        embed.add_field(name="🎲`!dice`", value="ダイスロール(ex. !dice 4d6)", inline=True)
        embed.add_field(name="👬`!team チーム数`", value="VC接続メンバーをチーム分けします", inline=True)
        embed.add_field(name="❔`!help`", value="ヘルプを表示", inline=True)
        embed.add_field(name="📊`!info`", value="このbotを起動しているサーバーの情報", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="💭`!poll *質問内容 *選択肢1 *選択肢2 +選択肢3... +投稿したいチャンネルID`", value="** *は必須引数、+は任意引数 **\nこのコマンドを実行することで、アンケートを取ることができます。\n最後の引数にチャンネルIDを指定することで、任意のチャンネルに投稿することができます。", inline=False)
        embed.add_field(name="🎸`!play [URL/keyword]`", value="YouTubeの音楽を再生\n動画か公開プレイリストのURL、または、タイトルを入力することで再生されます。\nbotをVCから退出させる場合は、`!leave`コマンドを実行してください。", inline=False)
        embed.add_field(name="🔊`VC入室通知`", value="ボイスチャンネルに誰かが入室した際の通知を受け取ることができます。\nこのチャンネルトピックにあるURLから設定変更できます。", inline=False)
        embed.set_footer(text="YJSNPI bot : help")
        await message.channel.send(embed=embed)

    elif message.content == "!help.a":
        embed = discord.Embed(title="❔ヘルプ(all)", description="利用できるコマンド/機能は以下です", color=0xb863cf, timestamp=datetime.utcnow())
        embed.add_field(name="🕹`!run`", value="Minecraft/ARKのサーバーを起動", inline=True)
        embed.add_field(name="🛑`!stop`", value="Minecraft/ARKのサーバーを停止", inline=True)
        embed.add_field(name="💻!`server`", value="Minecraft/ARKのサーバー情報を表示", inline=True)
        embed.add_field(name="🎲`!dice`", value="ダイスロール(ex. !dice 4d6)", inline=True)
        embed.add_field(name="👬`!team [チーム数]`", value="VC接続メンバーをチーム分けします", inline=True)
        embed.add_field(name="❔`!help`", value="ヘルプを表示", inline=True)
        embed.add_field(name="📊`!info`", value="このbotを起動しているサーバーの情報", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="🎸`!play [URL/keyword]`", value="YouTubeの音楽を再生\n動画か公開プレイリストのURL、または、タイトルを入力することで再生されます。", inline=False)
        embed.add_field(name="🔊`VC入室通知`", value="ボイスチャンネルに誰かが入室した際の通知を受け取ることができます。\nこのチャンネルトピックにあるURLから設定変更できます。", inline=False)
        embed.add_field(name="`!dbg.on`", value="**[制限有]**デバッグモードをONに変更", inline=True)
        embed.add_field(name="`!dbg.off`", value="**[制限有]**デバッグモードをOFFに変更", inline=True)
        embed.add_field(name="`!dbg.is`", value="現在のデバッグモードを取得", inline=True)
        embed.add_field(name="`!n.join.on`", value="**[制限有]**参加時の通知をONに変更", inline=True)
        embed.add_field(name="`!n.join.off`", value="**[制限有]**参加時の通知をOFFに変更", inline=True)
        embed.add_field(name="`!n.leave.on`", value="**[制限有]**退出時の通知をONに変更", inline=True)
        embed.add_field(name="`!n.leave.off`", value="**[制限有]**退出時の通知をOFFに変更", inline=True)
        embed.add_field(name="`!n.conf`", value="現在のVC入退出通知設定を取得", inline=True)
        embed.add_field(name="`!n.new`", value="**[制限有]**入退出通知設定の新規メッセージを作成", inline=True)
        embed.add_field(name="`!c.clear`", value="**[制限有]**YTDLキャッシュをすべて削除", inline=True)
        embed.add_field(name="`!restart`", value="**[制限有]**Botを再起動", inline=True)
        embed.add_field(name="`!cmd [commands]`", value="**[制限有]**コマンド実行", inline=True)
        embed.set_footer(text="YJSNPI bot : help all")
        await message.channel.send(embed=embed)

    elif message.content.startswith("!info"):
        async with message.channel.typing():
            mem = psutil.virtual_memory()
            dsk = psutil.disk_usage('/')
            embed = discord.Embed(title="📊情報", description="このbotを起動しているサーバーの情報です", color=0x709d43, timestamp=datetime.utcnow())
            embed.add_field(name="CPU使用率", value=f"{psutil.cpu_percent(interval=1)}%", inline=True)
            embed.add_field(name="メモリ使用率", value=f"{mem.percent}%\n{convert_size(mem.used)}/{convert_size(mem.total)}", inline=True)
            embed.add_field(name="ディスク使用率", value=f"{dsk.percent}%\n{convert_size(dsk.used)}/{convert_size(dsk.total)}", inline=True)
            embed.add_field(name="YTDL Cache", value=f"{convert_size(get_dir_size('dlfile'))}", inline=True)
            embed.add_field(name="起動時間", value=f"{get_uptime()}", inline=True)
            embed.add_field(name="GitHub", value="[GitHub](https://github.com/wacha-329/YJSNPIbot)", inline=True)
            embed.set_footer(text="YJSNPI bot : server info")
        await message.channel.send(embed=embed)

    elif message.content.startswith("!c.clear"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="📃YTDLキャッシュ削除", description="❌削除する権限がありません", color=0x56154b, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        else:
            remove_file_all()
            embed = discord.Embed(title="📃YTDLキャッシュ削除", description="⭕削除完了", color=0x56154b, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)

    elif message.content.startswith("!restart"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="Bot再起動", description="❌再起動する権限がありません", color=0x37e6c3, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        else:
            subprocess.Popen(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', const.bot_restart_exe_name)))
            embed = discord.Embed(title="Bot再起動", description="数秒後に再起動されます。\n!infoコマンドで確認してください。", color=0x56154b, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)

    elif message.content.startswith("!cmd "):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="コマンド実行(Windows)", description="❌実行する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        else:
            cmd = message.content[5:]
            result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
            embed = discord.Embed(title="コマンド実行(Windows)", color=0x56154b, timestamp=datetime.utcnow())
            embed.add_field(name=cmd, value=f"```{result.stdout}```", inline=False)
            await message.channel.send(embed=embed)

    elif message.content.startswith("!sh "):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="コマンド実行(Linux)", description="❌実行する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        else:
            cmd = message.content[4:]
            with paramiko.SSHClient() as ssh:
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(hostname=const.ssh_ip, port=22, username=const.ssh_username, password=const.ssh_password)

                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)

                stdout_data = stdout.read()
                stderr_data = stderr.read()

                list_stdout_data = stdout_data.decode() + ' '
                list_stderr_data = stderr_data.decode() + ' '
                code = stdout.channel.recv_exit_status()

                ssh.close()

            embed = discord.Embed(title="コマンド実行(Linux)", color=0x56154b, timestamp=datetime.utcnow())
            embed.add_field(name=cmd, value=f"stdout:```{list_stdout_data}``` \nstderr:```{list_stderr_data}```\ncode:```{str(code)}```", inline=False)
            await message.channel.send(embed=embed)

    elif message.content.startswith("!get-log"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="ログ取得", description="❌実行する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        else:
            list_of_files = glob.glob('log/*')
            latest_log_file = max(list_of_files, key=os.path.getctime)
            await message.author.send(content='最新のlogを送信します',file=discord.File(latest_log_file))
            embed = discord.Embed(title="Log取得", description='DMにファイルを送信しました。', color=0x068f4a, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)

    elif message.content.startswith("!get-status"):
        check_role = discord.utils.get(message.author.roles, id=const.debug_role_id)
        if check_role is None:
            embed = discord.Embed(title="status取得", description="❌実行する権限がありません", color=0xff0000, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return
        else:
            await message.author.send(content='status.iniを送信します',file=discord.File("status.ini"))
            embed = discord.Embed(title="status取得", description='DMにファイルを送信しました。', color=0x068f4a, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)

    else:
        if message.content[0:1] == '!':
            embed=discord.Embed(title="エラー発生", description="コマンドを確認してください。", color=0xff0000, timestamp=datetime.utcnow())
            await message.channel.send(embed=embed)
            return



@client.event
async def on_voice_state_update(member, before, after):
    if member.id == const.bot_author_id or member.guild.id != const.guild_id:
        return
    if before.channel != after.channel:
        time = datetime.utcnow() + d_time.timedelta(hours=9)
        channel_id = client.get_channel(const.notification_channel_id)
        if before.channel is None and config.get(section_serverconfig, 'default_join_notification') == 'true':
            msg = f'{time:%m/%d-%H:%M} に {member.name} が {after.channel.name} に参加しました。'
            embed = discord.Embed(title="🔔VC入室通知", description=msg, color=0x38cc24, timestamp=datetime.utcnow())
            await channel_id.send(embed=embed)
        if after.channel is None and config.get(section_serverconfig, 'default_leave_notification') == 'true':
            msg = f'{time:%m/%d-%H:%M} に {member.name} が {before.channel.name} から退出しました。'
            embed = discord.Embed(title="🔔VC退出通知", description=msg, color=0x3f85cf, timestamp=datetime.utcnow())
            await channel_id.send(embed=embed)



@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == const.bot_author_id or payload.guild_id != const.guild_id:
        return

    global music_stop
    channel = client.get_channel(payload.channel_id)
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    member_bot = guild.get_member(const.bot_author_id)

    msg = await channel.fetch_message(payload.message_id)
    if payload.emoji.name == '🔔' or payload.emoji.name == '🔕':
        if msg.embeds and str(msg.embeds[0].footer.text) == 'YJSNPI bot : notification settings':
            pined_msg_id = int(config.get(section_serverconfig, 'role_grant_message_id'))
            if payload.message_id == pined_msg_id:
                role = guild.get_role(const.notification_role_id)
                if role is not None:
                    if payload.emoji.name == '🔔':
                        await member.add_roles(role)
                        await msg.remove_reaction(payload.emoji, member)
                    if payload.emoji.name == '🔕':
                        await member.remove_roles(role)
                        await msg.remove_reaction(payload.emoji, member)
    elif payload.emoji.name == '⏹' or payload.emoji.name == '⏯' or payload.emoji.name == '⏭':
        if msg.embeds and str(msg.embeds[0].footer.text) == 'YJSNPI bot : play music♪':
            if guild.voice_client is not None:
                if member.voice is not None and member.voice.channel.id == member_bot.voice.channel.id:
                    if payload.emoji.name == '⏹':
                        music_stop = True
                        guild.voice_client.stop()
                        embed = msg.embeds[0]
                        embed.set_field_at(1,name="ステータス", value="⏹停止", inline=True)
                        embed.set_field_at(2,name="再生終了", value="新たに再生する場合は、!playコマンドを実行してください", inline=False)
                        await msg.edit(embed=embed)
                        remove_file()

                    elif payload.emoji.name == '⏯':
                        if guild.voice_client.is_playing():
                            guild.voice_client.pause()
                            embed = msg.embeds[0]
                            embed.set_field_at(1,name="ステータス", value="⏸一時停止中", inline=False)
                            await msg.edit(embed=embed)
                        elif guild.voice_client.is_paused():
                            guild.voice_client.resume()
                            embed = msg.embeds[0]
                            embed.set_field_at(1,name="ステータス", value="▶再生中", inline=False)
                            await msg.edit(embed=embed)

                    elif payload.emoji.name == '⏭':
                        guild.voice_client.stop()
                else:
                        embed = msg.embeds[0]
                        embed.add_field(name="🚫操作不可", value="botと同じVoiceChannelに参加しているメンバーのみが操作することができます。", inline=False)
                        await msg.edit(embed=embed)
                        await msg.remove_reaction(payload.emoji, member)
                        await asyncio.sleep(10)
                        embed.remove_field(3)
                        await msg.edit(embed=embed)
                        return

                if music_stop:
                    await msg.clear_reactions()
                else:
                    await msg.remove_reaction(payload.emoji, member)

    elif payload.emoji.name == '✅' or payload.emoji.name == '❎':
        if msg.embeds and str(msg.embeds[0].footer.text) == 'YJSNPI bot : poll':
            choices = msg.embeds[0].description.split("\n")
            del choices[-2:]
            if payload.emoji.name == '✅':
                embed = discord.Embed(title="💭アンケート途中結果", description=f"現在投票中のアンケートは[こちら]({msg.jump_url})", color=0x78a93d, timestamp=datetime.utcnow())
                await msg.remove_reaction(payload.emoji, member)
            elif payload.emoji.name == '❎':
                embed = discord.Embed(title="💭アンケート最終結果", description=f"投票終了したアンケートは[こちら]({msg.jump_url})", color=0x78a93d, timestamp=datetime.utcnow())
            embed.add_field(name="結果", value="集計中...", inline=True)
            embed.set_footer(text="YJSNPI bot : poll result")
            result_msg = await msg.channel.send(embed=embed)
            embed.remove_field(0)
            for i,reaction in enumerate(msg.reactions):
                if (not hex(ord(reaction.emoji)) == "0x2705") and (not hex(ord(reaction.emoji)) == "0x274e"):
                    tmp_user = ''
                    tmp_cnt = 0
                    async for user in reaction.users():
                        if not user.bot:
                            tmp_user += user.mention + " "
                            tmp_cnt += 1
                    if tmp_cnt == 0:
                        tmp_user += "なし"
                    embed.add_field(name=f"{choices[i]}", value=f"投票数 : {tmp_cnt}\n投票者 : {tmp_user}", inline=False)
            await result_msg.edit(embed=embed)

            if payload.emoji.name == '❎':
                poll_description = msg.embeds[0].description.split("\n")
                del poll_description[-1]
                poll_description[-1] = "`このアンケートは投票終了しました。\n終了させた方が❎リアクションを削除することで、投票再開できます。`"
                description = '\n'.join(poll_description)
                poll_embed = discord.Embed(title=msg.embeds[0].title, description=description, color=0x3da9a1, timestamp=msg.embeds[0].timestamp)
                poll_embed.set_footer(text="YJSNPI bot : poll [ended]")
                await msg.edit(embed=poll_embed)
                await channel.edit(topic='')
        else:
            await msg.remove_reaction(payload.emoji, member)

    elif msg.embeds and str(msg.embeds[0].footer.text) == 'YJSNPI bot : poll [ended]':
        await msg.remove_reaction(payload.emoji, member)


@client.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == const.bot_author_id or payload.guild_id != const.guild_id:
        return

    channel = client.get_channel(payload.channel_id)
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    member_bot = guild.get_member(const.bot_author_id)

    msg = await channel.fetch_message(payload.message_id)
    if payload.emoji.name == '❎':
        if msg.embeds and str(msg.embeds[0].footer.text) == 'YJSNPI bot : poll [ended]':
            poll_description = msg.embeds[0].description.split("\n")
            del poll_description[-1]
            poll_description[-1] = "`投票結果を確認する場合は✅を、終了する場合は❎をクリックしてください。\n❎リアクションを削除することで、投票再開できます。`"
            description = '\n'.join(poll_description)
            poll_embed = discord.Embed(title=msg.embeds[0].title, description=description, color=0x3da9a1, timestamp=msg.embeds[0].timestamp)
            poll_embed.set_footer(text="YJSNPI bot : poll")
            await msg.edit(embed=poll_embed)
            await channel.edit(topic='⚡アンケート実施中！: ' + msg.jump_url)



async def getStatusMsg():
    msg = 'Say !help'
    tmp = ''
    if config.get(section_serverstatus, 'ark_1') == '1':
        tmp += '🔴ARK:HGC | '
    if config.get(section_serverstatus, 'mine_1') == '1':
        tmp += '🔴Knee-high Boots | '
    if config.get(section_serverstatus, 'mine_2') == '1':
        tmp += '🔴Werewolf | '
    if config.get(section_serverstatus, 'mine_3') == '1':
        tmp += '🔴Vanilla | '
    if config.get(section_serverstatus, 'val_1') == '1':
        tmp += '🔴Valheim | '
    m = tmp + msg
    return m

async def getServerStatus():
    mask = 0
    cnt = 0
    if config.get(section_serverstatus, 'ark_1') == '1':
        mask |= 0b00000001
        cnt += 1
    if config.get(section_serverstatus, 'mine_1') == '1':
        mask |= 0b00000010
        cnt += 1
    if config.get(section_serverstatus, 'mine_2') == '1':
        mask |= 0b00000100
        cnt += 1
    if config.get(section_serverstatus, 'mine_3') == '1':
        mask |= 0b00001000
        cnt += 1
    if config.get(section_serverstatus, 'val_1') == '1':
        mask |= 0b00010000
        cnt += 1
    return cnt,mask

async def getStopServerConstant(mask):
    if mask & 0b00000001 != 0:
        s_n = 'ARK: HGC Server'
        i_n = 'ark_1'
        e_p = const.stop_ark_path
    elif mask & 0b00000010 != 0:
        s_n = 'Minecraft: Knee-high Boots Server'
        i_n = 'mine_1'
        e_p = None
    elif mask & 0b00000100 != 0:
        s_n = 'Minecraft: Werewolf Server'
        i_n = 'mine_2'
        e_p = None
    elif mask & 0b00001000 != 0:
        s_n = 'Minecraft: Vanilla Server'
        i_n = 'mine_3'
        e_p = None
    elif mask & 0b00010000 != 0:
        s_n = 'Valheim: HGC Server'
        i_n = 'val_1'
        e_p = None
    else:
        s_n = None
        i_n = None
        e_p = None
    return s_n,i_n,e_p

def remove_file():
    now = d_time.date.today()
    for file in os.listdir('dlfile'):
        mtime = d_time.date.fromtimestamp(int(os.path.getatime('dlfile/' + file)))
        if (now - mtime).days >= 30:
            os.remove('dlfile/' + file)

def remove_file_all():
    for file in os.listdir('dlfile'):
        os.remove('dlfile/' + file)

def get_dir_size(path='.'):
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    return total

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

def get_uptime():
    global start_time
    current_time = time.time()
    difference = int(round(current_time - start_time))
    text = str(d_time.timedelta(seconds=difference))
    return text

def get_h_m_s(td):
    m, s = divmod(td.seconds, 60)
    h, m = divmod(m, 60)
    return h, m, s

def valheim_start():
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=const.ssh_ip, port=22, username=const.ssh_username, password=const.ssh_password)

        stdin, stdout, stderr = ssh.exec_command('~/sh/start_valheim_server.sh', timeout=10)

        stdout_data = stdout.read()
        stderr_data = stderr.read()

        list_stdout_data = stdout_data.decode().split('\n')
        list_stderr_data = stderr_data.decode().split('\n')

        code = stdout.channel.recv_exit_status()

        for o in list_stdout_data:
            log.i('[std] ' + o.rstrip('\n'))
        for e in list_stderr_data:
            log.i('[err] ' + e.rstrip('\n'))
        log.i('[code] ' + str(code))

        ssh.close()

def valheim_stop():
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=const.ssh_ip, port=22, username=const.ssh_username, password=const.ssh_password)

        stdin, stdout, stderr = ssh.exec_command('~/sh/stop_valheim_server.sh', timeout=60)

        stdout_data = stdout.read()
        stderr_data = stderr.read()

        list_stdout_data = stdout_data.decode().split('\n')
        list_stderr_data = stderr_data.decode().split('\n')

        code = stdout.channel.recv_exit_status()

        for o in list_stdout_data:
            log.i('[std] ' + o.rstrip('\n'))
        for e in list_stderr_data:
            log.i('[err] ' + e.rstrip('\n'))
        log.i('[code] ' + str(code))

        ssh.close()

def ark_start(mapname):
    log.i('ark_start called. mapname = ' + mapname)
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=const.ssh_ip, port=22, username=const.ssh_username, password=const.ssh_password)

        if mapname == "TheIsland":
            exec_sh = 'ark_start_island.sh'
        elif mapname == "CrystalIsles":
            exec_sh = 'ark_start_crystal.sh'

        stdin, stdout, stderr = ssh.exec_command(f'~/sh/{exec_sh}', timeout=10)

        stdout_data = stdout.read()
        stderr_data = stderr.read()

        list_stdout_data = stdout_data.decode().split('\n')
        list_stderr_data = stderr_data.decode().split('\n')

        code = stdout.channel.recv_exit_status()

        for o in list_stdout_data:
            log.i('[std] ' + o.rstrip('\n'))
        for e in list_stderr_data:
            log.i('[err] ' + e.rstrip('\n'))
        log.i('[code] ' + str(code))

        ssh.close()

def ark_stop(mapname):
    log.i('ark_stop called. mapname = ' + mapname)
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=const.ssh_ip, port=22, username=const.ssh_username, password=const.ssh_password)

        if mapname == "TheIsland":
            exec_sh = 'ark_stop_island.sh'
        elif mapname == "CrystalIsles":
            exec_sh = 'ark_stop_crystal.sh'

        stdin, stdout, stderr = ssh.exec_command(f'~/sh/{exec_sh}', timeout=10)

        stdout_data = stdout.read()
        stderr_data = stderr.read()

        list_stdout_data = stdout_data.decode().split('\n')
        list_stderr_data = stderr_data.decode().split('\n')

        code = stdout.channel.recv_exit_status()

        for o in list_stdout_data:
            log.i('[std] ' + o.rstrip('\n'))
        for e in list_stderr_data:
            log.i('[err] ' + e.rstrip('\n'))
        log.i('[code] ' + str(code))

        ssh.close()


client.run(const.token)