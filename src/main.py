import sys

from P4 import P4, P4Exception

p4 = P4()
p4.connect()


def main(stream):
    print(f"The stream is {stream}")
    stream = p4.run_stream("-o", f"{stream}")[0]
    parent = stream["Parent"]
    paths = p4.run_files("--streamviews", f"{parent}/...")
    streamFiles = [path['streamFile'].replace(f"{parent}/", '') for path in paths]
    
    print(streamFiles)
    #Example: 
    '''
    ['DCC/Reaper/Ambient Music/Ambient Music.rpp', 'DCC/Reaper/Ambient Music/Media/Ambient Music_stems_CinematicUnderscore.wav', 'DCC/Reaper/Ambient Music/Media/Ambient Music_stems_HeartThump.wav', 'DCC/Reaper/Ambient Music/Media/Ambient Music_stems_Reason Rack Plugin.wav', 'DCC/Reaper/Ambient Music/Media/peaks/Ambient Music_stems_CinematicUnderscore.wav.reapeaks', 'DCC/Reaper/Ambient Music/Media/peaks/Ambient Music_stems_HeartThump.wav.reapeaks', 'DCC/Reaper/Ambient Music/Media/peaks/Ambient Music_stems_Reason Rack Plugin.wav.reapeaks', 'DCC/Reaper/Ambient Music/Media/peaks/reaper_freeze_Reason Rack Plugin.wav.reapeaks', 'DCC/Reaper/Ambient Music/Media/reaper_freeze_Reason Rack Plugin.wav', 'DCC/Reaper/placeholder.txt', 'DCC/Reaper/SFX/Footsteps/Backups/Footsteps-2025-05-31_131813.rpp-bak', 'DCC/Reaper/SFX/Footsteps/Footsteps.rpp', 'DCC/Reaper/SFX/Footsteps/Media/Gritty_Stone_Step_01.wav', 'DCC/Reaper/SFX/Footsteps/Media/Gritty_Stone_Step_02.wav', 'DCC/Reaper/SFX/Footsteps/Media/peaks/Gritty_Stone_Step_01.wav.reapeaks', 'DCC/Reaper/SFX/Footsteps/Media/peaks/Gritty_Stone_Step_02.wav.reapeaks', 'Imports/Music/CinematicUnderscore.wav', 'Imports/Music/HeartThump.wav', 'Imports/Music/placeholder.txt', 'Imports/Music/SpookyPad.wav', 'p4ignore.txt']
    '''


if __name__ == '__main__':
    # Get argument and make sure it is a valid stream name
    if len(sys.argv) != 2:
        print("Usage: python main.py <stream>")
        sys.exit(1)
    main(sys.argv[1])