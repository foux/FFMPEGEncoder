import logging
import os
import subprocess
import tempfile
from subprocess import CalledProcessError
import time
import datetime
import shutil
import string

def which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def recurse_directory(directory):
    for current_entry in os.listdir(directory):
        current_entry = os.path.join(directory,current_entry)
        if os.path.isdir(current_entry):
            recurse_directory(current_entry)
        else:
            treat_file(current_entry)

def treat_file(video_file):
    try:
        pipe = subprocess.Popen([which("ffprobe"),'-show_streams','-of','compact',video_file],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = pipe.communicate()[0]
        if out:
            streams = out.rstrip().split('\n')
            command = {
                'commands': [],
                'audio_number': 0,
                'video_number': 0,
                'subtitle_number': 0,
                'total_streams': 0,
                'should_encode' : False
            }
            for current_stream in streams:
                command = analyze_stream(current_stream,command)
                
            if command["should_encode"]:
                my_ffmpeg_command = [which("ffmpeg"),'-i',video_file]
                my_ffmpeg_command.extend(command["commands"])
                my_ffmpeg_command.append("-threads")
                my_ffmpeg_command.append("0")
                tmpfile = os.path.join(tempfile.gettempdir(),os.path.basename(video_file))
                my_ffmpeg_command.append(tmpfile)
                
                logging.warning("Encoding %s with command %s" % (os.path.basename(video_file),string.join(my_ffmpeg_command," ")))
                #return_code = subprocess.call(my_ffmpeg_command)
                ts = time.time()
                pipe2 = subprocess.Popen(my_ffmpeg_command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                error = pipe2.communicate()[1]
                return_code = pipe2.returncode
                te = time.time()
                if return_code == 0:
                    logging.warning("Encoded successfull in %s, moving file : %s" % (str(datetime.timedelta(seconds=te-ts)),os.path.basename(video_file)))
                    shutil.move(tmpfile, video_file)
                    te2 = time.time()
                    logging.warning("Copy complete in %s. Process took %s" % (str(datetime.timedelta(seconds=te2-te)),str(datetime.timedelta(seconds=te2-ts))))
                else:
                    logging.error("Encoding failed...")
                    os.remove(tmpfile)
                
    except CalledProcessError:
        return
    
def analyze_stream(stream,command):
    hashed_stream={}
    parsed_stream = stream.rstrip().split('|')
    for stream_element in parsed_stream:
        element = stream_element.rstrip().split('=')
        if len(element)==2:
            hashed_stream[element[0]] = element[1]
    
    current_audio_stream = command["audio_number"]
    current_video_stream = command["video_number"]
    current_subtitle_stream = command["subtitle_number"]
    
    stream_number = command["total_streams"]
    
    command["commands"].append("-map")
    command["commands"].append("0:%s" % stream_number)
    
    movie_bitrate = 448000
    try:
        movie_bitrate = int(hashed_stream["bit_rate"])
    except ValueError:
        pass   
    if hashed_stream["codec_type"]=="video":
        command["commands"].append("-c:v:%s" % current_video_stream)
        command["commands"].append("copy")
        command["video_number"] = current_video_stream+1
    elif hashed_stream["codec_type"]=="audio":
        if hashed_stream["codec_name"]=="aac":
            if int(hashed_stream["channels"])==2:
                bitrate = min(128000,movie_bitrate)
                command["commands"].append("-c:a:%s" % current_audio_stream)
                command["commands"].append("libmp3lame")
                command["commands"].append("-b:a:%s" % current_audio_stream)
                command["commands"].append("%s" % bitrate)
                command["should_encode"] = True
            else:
                bitrate = min(448000,movie_bitrate)
                command["commands"].append("-c:a:%s" % current_audio_stream)
                command["commands"].append("ac3")
                command["commands"].append("-b:a:%s" % current_audio_stream)
                command["commands"].append("%s" % bitrate)
                command["should_encode"] = True
        else:
            command["commands"].append("-c:a:%s" % current_audio_stream)
            command["commands"].append("copy")
        command["audio_number"] = current_audio_stream+1
    elif hashed_stream["codec_type"]=="subtitle":
        command["commands"].append("-c:s:%s" % current_subtitle_stream)
        command["commands"].append("copy")
        command["subtitle_number"] = current_subtitle_stream + 1
    
    command["total_streams"] = stream_number+1
    
    return command
    
    #codec_type = parsed_stream[5]
    #if codec_type == "codec_type=audio":
    #    logging.warning("Found an audio stream : " + stream)

current_dir = os.getcwd()

if os.path.isdir(current_dir):
    recurse_directory(current_dir)
else:
    treat_file(current_dir)

