"""Convert an explicitly selected lesson excerpt; preserve upload/provenance separately.

This is an isolated subprocess. Preparation changes media. Exact edit preservation
is subsequently measured against input.mp4, never against the uploaded original.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import signal
import subprocess
import sys

MAX_UPLOAD = 64 * 1024**2
INPUT = ['-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm,ogg',
         '-probesize', '5000000', '-analyzeduration', '5000000']


def parameters(start, duration):
    start, duration = float(start), float(duration)
    if not math.isfinite(start) or not math.isfinite(duration):
        raise ValueError('Excerpt times must be finite numbers.')
    if start < 0 or start > 600 or not 1 <= duration <= 12 or abs(duration * 10 - round(duration * 10)) > 1e-6:
        raise ValueError('Choose a start from 0 to 600 seconds and a length of 1–12 seconds in 0.1-second steps.')
    return start, duration


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lesson_tracks(metadata, header):
    streams = metadata.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video']
    audios = [s for s in streams if s.get('codec_type') == 'audio']
    extra = [s for s in streams if s.get('codec_type') not in ('video', 'audio')]
    # Xiph Skeleton is structural metadata, not subtitles or teaching content:
    # https://xiph.org/ogg/doc/skeleton.html and https://wiki.xiph.org/Skeleton
    # Accept only its complete, single-segment first BOS identification packet.
    # Arbitrary data tracks and subtitles still refuse before full decoding.
    skeleton = False
    if metadata.get('format', {}).get('format_name') == 'ogg' and len(extra) == 1:
        track = extra[0]
        if len(header) >= 28 and header[:6] == b'OggS\x00\x02' and header[18:22] == b'\x00'*4 and header[26] == 1:
            length = header[27]
            packet = header[28:28+length]
            skeleton = (track.get('index') == 0 and track.get('codec_type') == 'data' and not track.get('codec_name')
                        and len(packet) == length and length in (64, 80) and packet[:8] == b'fishead\x00'
                        and (int.from_bytes(packet[8:10], 'little'), length) in ((3, 64), (4, 80))
                        and packet[10:12] == b'\x00\x00')
    if len(videos) != 1 or len(audios) > 1 or extra and not skeleton:
        raise ValueError('Use one video track and at most one audio track; remove subtitle/data tracks first. Recognized Ogg Skeleton metadata is allowed.')
    return videos[0], audios, skeleton


def prepare(folder):
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (75, 75))
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (72 * 1024**2, 72 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    signal.alarm(100)
    request = json.loads((folder / 'prepare-request.json').read_text())
    start, duration = parameters(request['start_seconds'], request['duration_seconds'])
    upload = folder / 'uploaded-original.bin'
    if not 0 < upload.stat().st_size <= MAX_UPLOAD or digest(upload) != request['upload_sha256']:
        raise ValueError('The uploaded original changed or exceeds 64 MiB.')
    # Restrict container/codec families and protocols before any full decode.
    probe = subprocess.run(['/usr/bin/ffprobe', '-v', 'error', '-threads', '1', *INPUT,
                            '-show_entries', 'format=duration,format_name:stream=index,codec_type,codec_name,width,height,pix_fmt,color_transfer,chroma_location,avg_frame_rate,channels:stream_side_data=rotation', '-of', 'json', str(upload)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=True)
    if len(probe.stdout) > 131072:
        raise ValueError('Source metadata exceeds the limit.')
    metadata = json.loads(probe.stdout)
    with upload.open('rb') as source:
        header = source.read(108)
    video, audios, skeleton = lesson_tracks(metadata, header)
    if video.get('codec_name') not in ('h264', 'hevc', 'vp8', 'vp9', 'av1', 'mpeg4', 'theora'):
        raise ValueError('Supported lesson codecs: H.264, SDR HEVC, VP8, VP9, AV1, MPEG-4 or Theora.')
    if not 16 <= video.get('width', 0) <= 3840 or not 16 <= video.get('height', 0) <= 2160:
        raise ValueError('Lesson dimensions must be between 16 pixels and 3840 × 2160.')
    if video.get('color_transfer') in ('smpte2084', 'arib-std-b67') or '10' in video.get('pix_fmt', '') or '12' in video.get('pix_fmt', ''):
        raise ValueError('HDR and high-bit-depth lessons need a separate color workflow; export an 8-bit SDR copy.')
    source_duration = float(metadata.get('format', {}).get('duration', 0))
    if not math.isfinite(source_duration) or not 1 <= source_duration <= 1800 or start + duration > source_duration + .01:
        raise ValueError('Choose an excerpt entirely inside a lesson of at most 30 minutes.')
    if any(int(a.get('channels', 0)) not in (1, 2) or a.get('codec_name') not in ('aac', 'opus', 'vorbis', 'mp3', 'pcm_s16le', 'pcm_s24le') for a in audios):
        raise ValueError('Supported lesson audio: mono/stereo AAC, Opus, Vorbis, MP3 or PCM.')
    frames = round(duration * 30)
    silent = folder / 'prepared-video.mp4'
    # Honor display rotation; preserve aspect ratio with a visible letterbox.
    filt = ('scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2:'
            'out_color_matrix=bt709:out_range=tv:out_chroma_loc=left:flags=bilinear+accurate_rnd+bitexact,'
            'pad=640:360:(ow-iw)/2:(oh-ih)/2:black,setsar=1,'
            'fps=30:start_time=0,tpad=stop_mode=clone:stop_duration=0.1,format=yuv420p,'
            'setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709')
    base = ['/usr/bin/ffmpeg', '-v', 'error', '-nostdin', '-y', '-threads', '1', '-filter_threads', '1', *INPUT]
    cmd = base + ['-ss', str(start), '-i', str(upload), '-map', '0:v:0', '-vf', filt,
                  '-an', '-sn', '-dn', '-map_metadata', '-1', '-c:v', 'libx264', '-preset', 'veryfast',
                  '-crf', '18', '-bf', '0', '-threads', '1', '-pix_fmt', 'yuv420p', '-color_range', 'tv',
                  '-colorspace', 'bt709', '-color_trc', 'bt709', '-color_primaries', 'bt709',
                  '-chroma_sample_location', 'left', '-video_track_timescale', '15360', '-frames:v', str(frames), str(silent)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60, check=True)
    target = folder / 'input.mp4'
    if audios:
        # One explicit resample/downmix at preparation. Editing subsequently copies
        # this prepared AAC track and verifies its packet/timing/PCM identity.
        audio_cmd = base + ['-ss', str(start), '-i', str(upload), '-i', str(silent), '-map', '1:v:0',
                           '-map', '0:a:0', '-c:v', 'copy', '-af',
                           f'aresample=48000:async=1:first_pts=0,apad,atrim=duration={duration},asetpts=PTS-STARTPTS',
                           '-c:a', 'aac', '-ac', '1', '-ar', '48000', '-b:a', '96k',
                           '-map_metadata', '-1', '-video_track_timescale', '15360', str(target)]
        subprocess.run(audio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=35, check=True)
        silent.unlink()
    else:
        silent.rename(target)
    if target.stat().st_size > 8 * 1024**2:
        raise ValueError('The prepared segment exceeds 8 MiB. Choose a shorter excerpt.')
    prepared_probe = subprocess.run(['/usr/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                    '-show_entries', 'stream=chroma_location', '-of', 'json', str(target)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
    prepared_chroma = json.loads(prepared_probe.stdout)['streams'][0].get('chroma_location')
    if prepared_chroma != 'left':
        raise ValueError('Prepared chroma location did not meet the left-sited edit profile.')
    preview = folder / 'prepared-preview.png'
    subprocess.run(['/usr/bin/ffmpeg', '-v', 'error', '-nostdin', '-threads', '1', '-i', str(target),
                    '-frames:v', '1', '-threads', '1', str(preview)], stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, timeout=10, check=True)
    receipt = {'schema': 'lesson-preparation-v1', 'uploaded_sha256': digest(upload),
               'prepared_sha256': digest(target), 'uploaded_bytes': upload.stat().st_size,
               'preview_sha256': digest(preview),
               'start_seconds': start, 'duration_seconds': duration, 'frames': frames,
               'source': {'video_codec': video['codec_name'], 'width': video['width'], 'height': video['height'],
                          'duration_seconds': source_duration, 'frame_rate': video.get('avg_frame_rate'),
                          'chroma_location': video.get('chroma_location', 'unspecified'),
                          'audio_codec': audios[0]['codec_name'] if audios else None,
                          'audio_channels': audios[0].get('channels') if audios else 0,
                          'omitted_metadata': ['Ogg Skeleton structural metadata'] if skeleton else []},
               'prepared': {'width': 640, 'height': 360, 'fps': 30, 'color': 'limited BT.709 SDR',
                            'chroma_location': prepared_chroma,
                            'audio': 'AAC-LC mono 48 kHz' if audios else 'none'},
               'changes': ['Selected excerpt only', 'Aspect-preserving resize and letterbox to 640 × 360',
                           '30 fps conversion and H.264 encoding', 'SDR conversion; untagged color interpreted by FFmpeg',
                           'Audio resampled/downmixed and AAC encoded once' if audios else 'No audio track'],
               'preservation_reference': 'prepared_sha256; exact edit checks do not compare against uploaded original',
               'notice': 'Preparation changes picture and audio. Keep the uploaded original. No edit is approved by preparation.'}
    (folder / 'preparation.json').write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    folder = Path(sys.argv[1]).resolve()
    try:
        prepare(folder)
    except BaseException as error:
        message = str(error) if isinstance(error, ValueError) else 'Lesson preparation failed or exceeded its bounded runtime. Try a shorter SDR excerpt.'
        (folder / 'prepare-error.json').write_text(json.dumps({'error': message, 'type': type(error).__name__}))
        raise SystemExit(2)
