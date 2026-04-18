# Everytime I Come Back To This Project, I Realize How Good I Am At Coding.
# The Bot Also Has The Preview 1280 Command.
import tasks
import logging
import ffmpeg
import random as rand
import datetime
import humanize
import sqlite3
from urlextract import URLExtract
import parse
from catboxpy.catbox import CatboxClient
from dpy_paginator import paginate
from yt_dlp import YoutubeDL
import re
from pathlib import Path
import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import random as rand, string
import aiohttp
import uuid
import subprocess
import time
import datetime
import random
import shutil
import shlex
import tempfile
import yt_dlp

UPLOAD_DIR = "./uploads"
UPLOAD_DIR_ALT = Path(UPLOAD_DIR)

def random_string(length=8): return ''.join(rand.choices(string.ascii_letters + string.digits, k=length))

async def FFcmd(cmd:str):
    process = await asyncio.create_subprocess_shell("ffmpeg " + cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"FFmpeg command failed with error: {stderr.decode()}")
    return stdout.decode()

async def gen_hue_hald(hue: float=0, sat: float=0, val: float=0) -> str:
    # Use .as_posix() to ensure forward slashes
    random_filename = (UPLOAD_DIR_ALT / f"{random_string(10)}_hald.ppm").as_posix()
    
    # Use create_subprocess_exec with a LIST of arguments
    args = [
        "hald:6", 
        "-define", "modulate:colorspace=hsl", 
        "-modulate", f"{val*100+100},{sat*100+100},{hue*200+100}", 
        random_filename
    ]
    
    # Note: Using 'magick' (v7) or 'convert' (v6). Change if necessary.
    process = await asyncio.create_subprocess_exec(
        "magick", *args, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"ImageMagick failed: {stderr.decode()}")
    return random_filename

async def get_dimensions(file:str):
    info = await FFprobe(file, stream="v:0")
    width = int(info['streams'][0]['width'])
    height = int(info['streams'][0]['height'])
    return width, height

async def FFprobe(file:str, stream:str=None):
    cmd = f"ffprobe -v quiet -print_format json -show_format -show_streams {file}"
    if stream:
        cmd += f" -select_streams {stream}"
    process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"FFprobe command failed with error: {stderr.decode()}")
    return json.loads(stdout.decode())

async def get_duration(file:str):
    info = await FFprobe(file, stream="v:0")
    return float(info['streams'][0]['duration'])

async def download_file(attachment: discord.Attachment, filename: str):
    bytes = await attachment.read()
    with open(filename, 'wb') as f:
        f.write(bytes)

VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.mpeg', '.mpg', '.wmv')
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="bytp64!", intents=intents)

def cleanup_files(files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)
def create_video_list(video_files, output_list_file='input_videos.txt'):
      """
      Creates a text file in FFmpeg's concat format.
      """
      with open(output_list_file, 'w') as f:
        for video_file in video_files:
            # Ensure path is formatted correctly, particularly for Windows paths
            formatted_path = os.path.abspath(video_file).replace('\\', '/')
            f.write(f"file '{formatted_path}'\n")

@bot.event
async def on_ready():
    # Option 1: Modern Custom Status (Just text)
    await bot.change_presence(activity=discord.CustomActivity(name=f"Making Preview 1280 Out Of Videos And More In {len(bot.guilds)} servers! | bytp64!help"))
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# Mocking the helper functions from your snippet
def getName(path): return os.path.basename(path)
def chName(path, new): return os.path.join(os.path.dirname(path), new)

OWNER_ID = 1438290075736735775  # Replace with your ID
blocked_users = set() # Store blocked IDs here

# 1. The Block Command
@bot.tree.command(name="block", description="Block a user (Owner Only)")
async def block(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("You don't have permission.", ephemeral=True)
    
    blocked_users.add(user.id)
    await interaction.response.send_message(f"🚫 {user.mention} is now blocked.", ephemeral=True)

# 2. The Global Check (Prevents blocked users from using ANY command)
@bot.before_invoke
async def stop_blocked_users(ctx):
    if ctx.author.id in blocked_users:
        raise commands.CheckFailure("You are blocked.")

# 3. For Slash Commands specifically
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if interaction.user.id in blocked_users:
        if not interaction.response.is_done():
            await interaction.response.send_message("You are blocked from this bot.", ephemeral=True)


@bot.tree.command(name="download", description="Download a video from YouTube")
@app_commands.describe(url="The YouTube video URL")
async def download(interaction: discord.Interaction, url: str):
    await interaction.response.defer() # Bot is 'thinking' (prevents timeout)

    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(title)s.%(ext)s', # Saves to a downloads folder
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Send file to Discord (8MB limit for free servers)
        file = discord.File(filename)
        await interaction.followup.send(content=f"Downloaded: {info['title']}", file=file)
        
        # Cleanup: Remove the file after sending
        os.remove(filename)
        
    except Exception as e:
        await interaction.followup.send(f"Error on download command: {str(e)}")

@bot.command()
async def ffmpeg(ctx, *, command):
    """
    Execute an FFmpeg command on a Discord video link, uploaded file, or reply.
    Example usage: !ffmpeg -vf negate
    """
    attachment_url = None

    # Check for attachments or replied media
    if ctx.message.reference:
        referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if referenced_message.attachments:
            attachment_url = referenced_message.attachments[0].url
    if not attachment_url and ctx.message.attachments:
        attachment_url = ctx.message.attachments[0].url

    if not attachment_url:
        await ctx.send("Sorry, Please provide a video attachment or link.")
        return

    try:
        # Download the file
        file_name = os.path.join(UPLOAD_DIR, f"input_{ctx.author.id}.mp4")
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment_url) as response:
                if response.status == 200:
                    with open(file_name, "wb") as f:
                        f.write(await response.read())
                else:
                    await ctx.send(":warning: **Failed to download the video.**")
                    return

        sanitized_command = shlex.split(command)

        # Prepare output file
        output_file = os.path.join(UPLOAD_DIR, f"output_{ctx.author.id}.mp4")
        if not any(arg.endswith(".mp4") for arg in sanitized_command):
            sanitized_command.append(output_file)

        # Run FFmpeg command asynchronously
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", file_name,
            *sanitized_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if os.path.exists(output_file):
            await ctx.send(":white_check_mark: **Successful!**", file=discord.File(output_file))
            os.remove(output_file)
        else:
            await ctx.send(f":x: **FFmpeg error**:\n```{stderr.decode()}```")

        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        await ctx.send(f":x: FAIL!!! {str(e)}")

# Slash command to process video with FFmpeg (synchronous)
@bot.tree.command(name="ffmpeg", description="Execute an FFmpeg command on a video")
async def ffmpeg_any(interaction: discord.Interaction, command: str, attachment: discord.Attachment = None, url: str = None):
    """Process a video from attachment or URL using FFmpeg."""
    await interaction.response.defer()

    if not attachment and not url:
        await interaction.followup.send("Slash command error. Please provide a video attachment or URL.")
        return

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_file = temp_file.name.replace(".mp4", "_output.mp4")

    try:
        if attachment:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as response:
                    if response.status == 200:
                        with open(temp_file.name, "wb") as f:
                            f.write(await response.read())
                    else:
                        await interaction.followup.send(":warning: **Failed to download the video.**")
                        return
            input_source = temp_file.name

        elif url:
            input_source = url

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", input_source, *shlex.split(command), output_file,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            await interaction.followup.send(f":x: **FFmpeg error**:\n```{stderr.decode()}```")
            return

        if os.path.exists(output_file):
            await interaction.followup.send(":white_check_mark: **Done!**", file=discord.File(output_file))

    finally:
        os.remove(temp_file.name)
        if os.path.exists(output_file):
            os.remove(output_file)

@bot.tree.command(name="ricecake", description="Apply ricecake datamosh effect to a video")
@app_commands.describe(
    video="The video file to process",
    chance="Probability of duplicating a P-frame (default 0.08)",
    dups="Number of times to duplicate the frame (default 5)",
    speed="Adjust speed to maintain original duration (default True)"
)
async def ricecake_cmd(
    interaction: discord.Interaction, 
    video: discord.Attachment, 
    chance: float = 0.08, 
    dups: int = 5, 
    speed: bool = True
):
    if not video.content_type or "video" not in video.content_type:
        return await interaction.response.send_message("Please upload a valid video file.", ephemeral=True)

    await interaction.response.defer() # Bot is thinking...

    input_path = f"in_{video.filename}"
    output_path = f"out_{video.filename}"
    avi_path = f"tmp_{video.id}.avi"
    mosh_path = f"mosh_{video.id}.avi"
    
    # Constants for datamoshing
    spl = b'\x30\x30\x64\x63' # '00dc' delimiter
    iframe = b'\x00\x01\xb0'

    try:
        # 1. Download the file
        await video.save(input_path)

        # 2. Convert to AVI (DivX) to make P-frames predictable
        subprocess.call(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'fatal', '-i', input_path, '-c:v', 'mpeg4', '-vtag', 'xvid', '-q:v', '5', avi_path])

        # 3. Process frames
        with open(avi_path, 'rb') as f:
            frames = f.read().split(spl)
            
            iframes = 0
            pframes = 0
            
            with open(mosh_path, 'wb') as out:
                for frame in frames:
                    if not frame: continue
                    full_frame = frame + spl
                    
                    # Detect Frame Type
                    is_iframe = frame[5:8] == iframe
                    if is_iframe: iframes += 1
                    else: pframes += 1

                    # Apply Mosh
                    if not is_iframe and random.random() < chance:
                        for _ in range(dups):
                            out.write(full_frame)
                    else:
                        out.write(full_frame)

        # 4. Final Render & Speed Adjustment
        speed_factor = 1 + (dups * chance * pframes / (pframes + iframes))
        cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'fatal', '-i', mosh_path]
        
        if speed:
            # Note: atempo has a limit of 0.5 to 2.0. Complex logic needed for extreme speeds.
            cmd += ['-vf', f'setpts=(1/{speed_factor})*PTS', '-af', f'atempo={speed_factor}']
        
        cmd += [output_path]
        subprocess.call(cmd)

        # 5. Upload and Cleanup
        await interaction.followup.send(file=discord.File(output_path))

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")
    
    finally:
        # Cleanup files
        for p in [input_path, output_path, avi_path, mosh_path]:
            if os.path.exists(p): os.remove(p)

@bot.command(name="sox", description="Edits A Video's Audio Using A Sox Command")
async def sox(ctx, sox_command: str):
    """Enter A SoX Command Like oops"""
    # Check if a video was actually attached
    if not ctx.message.attachments:
        return await ctx.send("Please attach a video file!")

    video = ctx.message.attachments[0]
    
    # Create unique names for this specific run
    uid = str(uuid.uuid4())[:8]
    files = {
        "in": f"input_{uid}.mp4",
        "audio": f"audio_{uid}.wav",
        "proc": f"proc_{uid}.wav",
        "out": f"output_{uid}.mp4"
    }

    msg = await ctx.send("Processing... 🛠️")

    try:
        await video.save(files["in"])

        # 1. Extract Audio
        proc1 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", files["in"], "-q:a", "0", "-map", "a", files["audio"]
        )
        await proc1.wait()

        # 2. Run SoX (Split command to avoid shell injection)
        sox_args = ["sox", files["audio"], files["proc"]] + sox_command.split()
        proc2 = await asyncio.create_subprocess_exec(*sox_args)
        await proc2.wait()

        # 3. Merge Audio/Video
        proc3 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", files["in"], "-i", files["proc"], "-c:v", "copy",
            "-map", "0:v:0", "-map", "1:a:0", "-shortest", files["out"]
        )
        await proc3.wait()

        await ctx.send(file=discord.File(files["out"]))
        await msg.delete()

    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

    finally:
        # Clean up all temp files
        for f in files.values():
            if os.path.exists(f):
                os.remove(f)

@bot.tree.command(name="sox", description="Edit a video's audio using a SoX command")
async def sox(interaction: discord.Interaction, video: discord.Attachment, sox_command: str):
    await interaction.response.defer()  # Avoid timeout

    # File paths
    input_video = "input.mp4"
    extracted_audio = "audio.wav"
    processed_audio = "processed_audio.wav"
    output_video = "output.mp4"

    # Download the video
    await video.save(input_video)

    try:
        # Extract audio from video
        subprocess.run(["ffmpeg", "-i", input_video, "-q:a", "0", "-map", "a", extracted_audio], check=True)

        # Construct the SoX command dynamically
        sox_cmd = f"sox {extracted_audio} {processed_audio} {sox_command}"
        process = subprocess.run(sox_cmd, shell=True, text=True, capture_output=True)

        # Check for warnings but allow the process to continue
        if "clipped" in process.stderr.lower():
            await interaction.followup.send(f"Warning: SoX reported clipping: {process.stderr}")

        # Merge processed audio back to video
        subprocess.run([
            "ffmpeg", "-i", input_video, "-i", processed_audio, "-c:v", "copy",
            "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_video
        ], check=True)

        # Send the processed video
        await interaction.followup.send(file=discord.File(output_video))

    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f":x: **Error processing video**: {e}")

    finally:
        # Clean up
        for f in [input_video, extracted_audio, processed_audio, output_video]:
            if os.path.exists(f):
                os.remove(f)


@bot.tree.command(name="preview1280", description="Make Preview 1280 Out Of A Video")
@app_commands.describe(file="The video to edit", start="Start trim", end="End trim")
async def p1280(interaction: discord.Interaction, file: discord.Attachment, start: float=1.85, end: float=0.85):
    filename = file.filename
    random_filename = os.path.join(UPLOAD_DIR, random_string(10)+"_"+filename)
    output_filename = os.path.join(UPLOAD_DIR, f"p1280_{random_string(10)}.mp4")
    await interaction.response.defer()
    if not filename.endswith(VIDEO_EXTENSIONS):
        await interaction.followup.send("Sorry, Please upload a valid video file.")
        return
    try:
        await download_file(file, random_filename)
        vidlen = await get_duration(random_filename)
        dimensions = await get_dimensions(random_filename)
        start = str(start).replace("vidlen", str(vidlen))
        t = str(end).replace("vidlen", str(vidlen))
        t2 = float(t) / 2
        t3 = float(t) + float(end)
        userHash = str(interaction.user.id)+str(rand.randint(0,9999))
        hue_45 = await gen_hue_hald(0.125)
        hue_180 = await gen_hue_hald(0.5)
        hue_22 = await gen_hue_hald(0.0611)
        hue_120 = await gen_hue_hald(0.3333)
        filename_0 = f"{UPLOAD_DIR}/0_{userHash}.avi"
        filename_1 = f"{UPLOAD_DIR}/1_{userHash}.avi"
        filename_2 = f"{UPLOAD_DIR}/2_{userHash}.avi"
        filename_3 = f"{UPLOAD_DIR}/3_{userHash}.avi"
        filename_4 = f"{UPLOAD_DIR}/4_{userHash}.avi"
        filename_5 = f"{UPLOAD_DIR}/5_{userHash}.avi"
        filename_6 = f"{UPLOAD_DIR}/6_{userHash}.avi"
        filename_7 = f"{UPLOAD_DIR}/7_{userHash}.avi"
        filename_8 = f"{UPLOAD_DIR}/8_{userHash}.avi"
        filename_9 = f"{UPLOAD_DIR}/9_{userHash}.avi"
        filename_10 = f"{UPLOAD_DIR}/10_{userHash}.avi"
        filename_11 = f"{UPLOAD_DIR}/11_{userHash}.avi"
        filename_12 = f"{UPLOAD_DIR}/12_{userHash}.avi"
        concat = f"{UPLOAD_DIR}/concat_{userHash}.txt"
        await FFcmd(f"-y -hide_banner -loglevel fatal -stream_loop -1 -i {random_filename} -vf scale=640:360,setsar=1:1 -ss {start} -t {t3} -c:v libx264 -c:a pcm_s16le {filename_0}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -t {t} -c:v libx264 -c:a pcm_s16le {filename_1}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -vf \"movie={hue_45},[in]haldclut\",format=yuv420p -af \"rubberband=pitch=2^(1/12):window=short:transients=mixed:detector=soft:channels=together:pitchq=consistency\" -t {t} -c:v libx264 -c:a pcm_s16le {filename_2}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -stream_loop -1 -i \"https://file.garden/aTXso15ukD3mnuPI/tv_sim_displacement_map.mov\" -filter_complex \"movie={hue_180}[h];[0][h]haldclut,hflip,crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack,format=yuv420p,format=bgr32[00];[1]crop=iw:ih/1:0:0,scale=640:360,eq=contrast=0.4,format=bgr32,hue=b=-0.033[x];nullsrc=1x1,geq=r=128:g=128:b=128,scale=640:360,format=bgr32[y];[00][x][y]displace=edge=wrap[v]\" -af \"rubberband=pitch=2^(-2/12):window=short:transients=mixed:detector=soft:channels=together:pitchq=consistency\" -map \"[v]\" -map 0:a -pix_fmt yuv420p -t {t} -c:v libx264 -c:a pcm_s16le {filename_3}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_2} -t {t} -c copy {filename_4}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -t {t2} -c:v libx264 -c:a pcm_s16le {filename_5}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -vf \"movie={hue_22},[in]haldclut\",hflip,format=yuv420p -af \"rubberband=pitch=2^(2/12):window=short:transients=mixed:detector=soft:channels=together:pitchq=consistency\" -t {t2} -c:v libx264 -c:a pcm_s16le {filename_6}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -vf \"movie={hue_45},[in]haldclut\",format=yuv420p -af \"rubberband=pitch=2^(1/12):window=short:transients=mixed:detector=soft:channels=together:pitchq=consistency\" -t {t2} -c:v libx264 -c:a pcm_s16le {filename_7}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -vf \"movie={hue_120},[in]haldclut\",hflip,format=yuv420p -af \"rubberband=pitch=2^(3/12):window=short:transients=mixed:detector=soft:channels=together:pitchq=consistency\" -t {t2} -c:v libx264 -c:a pcm_s16le {filename_8}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_0} -vf \"movie={hue_180},[in]haldclut\",format=yuv420p -af \"rubberband=pitch=2^(-2/12):window=short:transients=mixed:detector=soft:channels=together:pitchq=consistency\" -t {t2} -c:v libx264 -c:a pcm_s16le {filename_9}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_5} -vf hflip -c:v libx264 -c:a pcm_s16le {filename_10}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_7} -c copy {filename_11}")
        await FFcmd(f"-y -hide_banner -loglevel fatal -i {filename_8} -c copy {filename_12}")
        await asyncio.sleep(2.5) # Ensure all files are fully written before creating the list, its in avi so it processes quickly but just to be safe
        create_video_list([filename_1, filename_2, filename_3, filename_4, filename_5, filename_6, filename_7, filename_8, filename_9, filename_10, filename_11, filename_12], output_list_file=concat)
        await FFcmd(f"-y -hide_banner -loglevel fatal -f concat -safe 0 -i {concat} -vf scale={dimensions[0]}:{dimensions[1]},setsar=1 {output_filename}")
        await interaction.followup.send(file=discord.File(output_filename, filename=f"p1280.mp4"))
    except Exception as e:
        await interaction.followup.send(content=f":x: **Error**: {e}\n")
    finally:
        cleanup_files([random_filename, output_filename, concat, filename_0, filename_1, filename_2, filename_3, filename_4, filename_5, filename_6, filename_7, filename_8, filename_9, filename_10, filename_11, filename_12, hue_45, hue_180, hue_22, hue_120])

bot.run("YOUR_BOT_TOKEN")

