"""Narrow copy-only AAC contract. Never resample, trim, stretch, or re-encode."""
import hashlib
import json

AUDIO_KEYS = ('codec_name','profile','sample_rate','channels','channel_layout','time_base','start_pts','duration_ts','extradata_hash')

def validate_streams(meta, duration):
    streams=meta.get('streams',[])
    if len(streams)==1 and streams[0].get('codec_type')=='video':return False
    if len(streams)!=2 or [s.get('codec_type') for s in streams]!=['video','audio']:
        raise ValueError('Supported audio: exactly one video then one AAC-LC mono 48 kHz track; no extra tracks. Keep the original and supply this supported profile.')
    a=streams[1]
    expected={'codec_name':'aac','profile':'LC','codec_tag_string':'mp4a','sample_rate':'48000','channels':1,'channel_layout':'mono','time_base':'1/48000','start_pts':0,'duration_ts':round(duration*48000)}
    if any(a.get(k)!=v for k,v in expected.items()):
        raise ValueError('Unsupported audio profile or offset/duration. Requires AAC-LC mono 48 kHz, zero presentation start, same duration as video. No automatic conversion or audio removal is performed.')
    return True

def capture(e,args,label,limit=524288):
    p,log=e.BOUNDS.begin(args,label)
    try:
        b=p.stdout.read(limit+1)
        if len(b)>limit:raise ValueError('Audio evidence exceeds bounded size')
        p.stdout.close();e.BOUNDS.end(p,log);return b
    except BaseException:
        if not log.closed:e.BOUNDS.abort(p,log)
        raise

def evidence(e,path,label):
    presentation=validate_presentation(path,e.N/30)
    base=['/usr/bin/ffprobe','-v','error','-threads','1']+e.INPUT_FLAGS
    data=json.loads(capture(e,base+['-select_streams','a:0','-show_streams','-show_packets','-show_data_hash','sha256','-show_entries','stream=codec_name,profile,sample_rate,channels,channel_layout,time_base,start_pts,duration_ts,extradata_hash:packet=pts,dts,duration,size,flags,data_hash,side_data_list','-of','json',str(path)],label+'_packets'))
    if len(data.get('streams',[]))!=1 or not data.get('packets'):raise ValueError('Missing audio evidence')
    # Hash raw decoded float32 PCM without normalization or trimming. Includes codec tail padding.
    pcm=capture(e,['/usr/bin/ffmpeg','-v','error','-nostdin','-threads','1']+e.INPUT_FLAGS+['-i',str(path),'-map','0:a:0','-vn','-sn','-dn','-c:a','pcm_f32le','-f','f32le','pipe:1'],label+'_pcm',e.N*6400+8192)
    return {'presentation':presentation,'stream':data['streams'][0],'packets':data['packets'],'pcm_sha256':hashlib.sha256(pcm).hexdigest(),'pcm_bytes':len(pcm)}

def compare(a,b):
    return {'stream_exact':a['stream']==b['stream'],'packet_payload_timing_skip_exact':a['packets']==b['packets'],'decoded_pcm_exact':a['pcm_sha256']==b['pcm_sha256'] and a['pcm_bytes']==b['pcm_bytes']}

def mux(e,source,video,label):
    temporary=video.with_name(video.stem+'-with-audio.mp4')
    args=['/usr/bin/ffmpeg','-v','error','-nostdin','-n','-threads','1','-copyts']+e.INPUT_FLAGS+['-i',str(video)]+e.INPUT_FLAGS+['-i',str(source),'-map','0:v:0','-map','1:a:0','-c','copy','-copytb','1','-avoid_negative_ts','disabled','-video_track_timescale','15360',str(temporary)]
    capture(e,args,label+'_mux',1024)
    temporary.replace(video)


def validate_presentation(path, duration):
    """Admit only the tested canonical MP4 timing/volume headers, not general edit lists."""
    import struct
    def boxes(data):
        result={};offset=0
        while offset<len(data):
            if offset+8>len(data):raise ValueError('Truncated MP4 presentation box')
            size,kind=struct.unpack('>I4s',data[offset:offset+8])
            if size<8 or offset+size>len(data):raise ValueError('Unsupported MP4 extended/open/truncated box')
            result.setdefault(kind,[]).append(data[offset+8:offset+size]);offset+=size
        return result
    def one(data,key):
        found=data.get(key,[])
        if len(found)!=1:raise ValueError('Missing or duplicate MP4 presentation box '+repr(key))
        return found[0]
    if path.stat().st_size>8*1024**2:raise ValueError('MP4 presentation parser size bound exceeded')
    top=boxes(path.read_bytes());movie=boxes(one(top,b'moov'))
    tracks=[]
    for raw in movie.get(b'trak',[]):
        track=boxes(raw);media=boxes(one(track,b'mdia'))
        if set(track)!={b'tkhd',b'edts',b'mdia'} or set(media)!={b'mdhd',b'hdlr',b'minf'}:
            raise ValueError('Unsupported MP4 track reference/presentation boxes')
        minf=boxes(one(media,b'minf'))
        if set(minf) not in ({b'vmhd',b'dinf',b'stbl'},{b'smhd',b'dinf',b'stbl'}):raise ValueError('Unsupported MP4 media information')
        if one(minf,b'dinf')!=bytes.fromhex('0000001c6472656600000000000000010000000c75726c2000000001'):
            raise ValueError('Unsupported MP4 data reference; self-contained video and audio only')
        table=boxes(one(minf,b'stbl'))
        if set(table)-{b'stsd',b'stts',b'stsc',b'stsz',b'stco',b'sgpd',b'sbgp',b'stss',b'ctts'}:raise ValueError('Unsupported MP4 sample table')
        description=one(table,b'stsd')
        if description[:8]!=bytes.fromhex('0000000000000001'):raise ValueError('Exactly one canonical sample description is required')
        entries=boxes(description[8:])
        if len(entries)!=1 or any(len(v)!=1 for v in entries.values()):raise ValueError('Unsupported sample descriptions')
        sample=next(iter(entries.values()))[0]
        if sample[:8]!=bytes.fromhex('0000000000000001'):raise ValueError('Unsupported sample data-reference index')
        if one(media,b'hdlr')[8:12]==b'soun':tracks.append((track,media))
    if len(tracks)!=1:raise ValueError('Exactly one canonical audio track is required')
    track,media=tracks[0]
    minimum=boxes(one(media,b'minf'))
    if set(top)-{b'ftyp',b'free',b'mdat',b'moov'} or set(movie)!={b'mvhd',b'trak',b'udta'} or len(movie[b'trak'])!=2 or set(track)!={b'tkhd',b'edts',b'mdia'} or set(media)!={b'mdhd',b'hdlr',b'minf'} or set(minimum)!={b'smhd',b'dinf',b'stbl'}:
        raise ValueError('Unsupported additional MP4 presentation/reference boxes')
    # Reject external URLs/URNs and non-default reference layouts, rather than
    # relying only on FFmpeg external-reference disabling flags.
    dinf=bytes.fromhex('0000001c6472656600000000000000010000000c75726c2000000001')
    if one(minimum,b'dinf')!=dinf:raise ValueError('Unsupported MP4 audio data reference; self-contained media only')
    udta=bytes.fromhex('000000596d657461000000000000002168646c7200000000000000006d6469726170706c0000000000000000000000002c696c737400000024a9746f6f0000001c6461746100000001000000004c61766636312e372e313033')
    if one(movie,b'udta')!=udta:raise ValueError('Unsupported MP4 movie metadata; canonical development mux only')
    # Frozen FFmpeg-created version-0 headers include unit movie rate/volume,
    # enabled/in-movie audio flags, unity track volume, identity matrix and
    # no alternate presentation edits. Only profile durations are substituted.
    mvhd=bytearray.fromhex('000000000000000000000000000003e800000bb80001000001000000000000000000000000010000000000000000000000000000000100000000000000000000000000004000000000000000000000000000000000000000000000000000000000000003')
    tkhd=bytearray.fromhex('000000030000000000000000000000020000000000000bb8000000000000000000000001010000000001000000000000000000000000000000010000000000000000000000000000400000000000000000000000')
    mdhd=bytearray.fromhex('0000000000000000000000000000bb800002368055c40000')
    mvhd[16:20]=struct.pack('>I',round(duration*1000));tkhd[20:24]=struct.pack('>I',round(duration*1000));mdhd[16:20]=struct.pack('>I',round(duration*48000)+1024)
    elst=struct.pack('>IIIiHH',0,1,round(duration*1000),1024,1,0)
    checks={'movie_header':one(movie,b'mvhd')==mvhd,'audio_track_header':one(track,b'tkhd')==tkhd,'audio_media_header':one(media,b'mdhd')==mdhd,'audio_edit_list':one(boxes(one(track,b'edts')),b'elst')==elst,'sound_media_header':one(boxes(one(media,b'minf')),b'smhd')==bytes(8)}
    if not all(checks.values()):raise ValueError('Unsupported MP4 audio presentation metadata: '+', '.join(k for k,v in checks.items() if not v)+'. Requires canonical unit-rate, unity-volume, zero-start AAC presentation; no conversion was attempted.')
    return checks
