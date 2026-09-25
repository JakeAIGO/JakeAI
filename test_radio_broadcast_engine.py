from pathlib import Path
import json
import tempfile

import torch
import torchaudio as ta

from radio.broadcast_engine import assemble_broadcast, PRODUCER_V2


def test_broadcast_engine_preserves_private_voice_separation_and_peak_ceiling():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        sr=PRODUCER_V2.sample_rate

        # Stereo song with a short dead tail.
        t=torch.arange(int(sr*1.2))/sr
        song=(0.2*torch.sin(2*torch.pi*220*t)).unsqueeze(0).repeat(2,1)
        song=torch.cat([song,torch.zeros((2,int(sr*0.4)))],dim=1)
        song_path=root/"song.wav"
        ta.save(str(song_path),song,sr)

        # Mono-like DJ stem duplicated to stereo with edge silence.
        voice=0.15*torch.sin(2*torch.pi*180*t)
        dj=torch.cat([
            torch.zeros(int(sr*0.15)),
            voice,
            torch.zeros(int(sr*0.2)),
        ]).unsqueeze(0).repeat(2,1)
        open_path=root/"open.wav"
        close_path=root/"close.wav"
        ta.save(str(open_path),dj,sr)
        ta.save(str(close_path),dj,sr)

        out=root/"broadcast.wav"
        manifest=root/"manifest.json"
        cues=root/"cues.json"

        data=assemble_broadcast(
            songs=[{"id":"song-1","title":"Test Song","artist":"Test Artist","path":str(song_path)}],
            dj_breaks=[
                {"id":"OPEN","path":str(open_path),"before_track_id":"song-1"},
                {"id":"CLOSE","path":str(close_path),"after_track_id":"song-1","before_track_id":None},
            ],
            out_path=out,
            manifest_path=manifest,
            cue_path=cues,
            profile=PRODUCER_V2,
        )

        assert out.exists()
        assert data["public_release"] is False
        assert data["founder_voice_used_in_songs"] is False
        assert data["founder_voice_role"]=="DJ/narrator only"

        mixed,mix_sr=ta.load(str(out))
        assert mix_sr==sr
        ceiling=10**(PRODUCER_V2.peak_db/20)
        assert float(mixed.abs().max()) <= ceiling + 0.002

        loaded=json.loads(manifest.read_text(encoding="utf-8"))
        assert loaded["engine"]=="KJAI Broadcast Engine v1"
        assert loaded["release_state"]=="PRIVATE_QA_ONLY"
        assert loaded["transition_report"][0]["dead_tail_removed_seconds"] > 0
