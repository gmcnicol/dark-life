"""Repo-local XTTS inference entrypoint.

This avoids coupling the renderer to the external training workspace's Python
packaging behavior. The workspace only needs to provide model artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import soundfile as sf
import torch
import torchaudio

import TTS.tts.models.xtts as xtts_model_module
import TTS.utils.io as tts_io
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts


_ORIGINAL_LOAD_FSSPEC = tts_io.load_fsspec


def _load_fsspec_compat(path: str, *args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _ORIGINAL_LOAD_FSSPEC(path, *args, **kwargs)


def _load_audio_compat(audiopath: str, sampling_rate: int) -> torch.Tensor:
    audio, source_rate = sf.read(audiopath, dtype="float32", always_2d=True)
    wav = torch.from_numpy(audio.T)
    if wav.size(0) != 1:
        wav = torch.mean(wav, dim=0, keepdim=True)
    if source_rate != sampling_rate:
        wav = torchaudio.functional.resample(wav, source_rate, sampling_rate)
    return torch.clamp(wav, -1.0, 1.0)


tts_io.load_fsspec = _load_fsspec_compat
xtts_model_module.load_fsspec = _load_fsspec_compat
xtts_model_module.load_audio = _load_audio_compat


def _load_model(
    *,
    run_dir: Path,
    checkpoint_path: Path,
    config_path: Path,
    vocab_path: Path,
    speaker_file_path: Path | None,
    device: str,
) -> Xtts:
    config = XttsConfig()
    config.load_json(str(config_path))
    model = Xtts.init_from_config(config)
    checkpoint_kwargs = dict(
        config=config,
        checkpoint_dir=str(run_dir),
        checkpoint_path=str(checkpoint_path),
        vocab_path=str(vocab_path),
        use_deepspeed=False,
    )
    if speaker_file_path is not None:
        checkpoint_kwargs["speaker_file_path"] = str(speaker_file_path)
    model.load_checkpoint(
        **checkpoint_kwargs,
    )
    model.to(torch.device("mps" if device == "mps" else "cpu"))
    model.eval()
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--speaker-wav", required=True)
    parser.add_argument("--language", default="en")
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config", dest="config_path", required=True)
    parser.add_argument("--vocab-path", required=True)
    parser.add_argument("--speaker-file-path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    checkpoint_path = Path(args.checkpoint)
    config_path = Path(args.config_path)
    vocab_path = Path(args.vocab_path)
    speaker_file_path = Path(args.speaker_file_path) if args.speaker_file_path else None
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    model = _load_model(
        run_dir=run_dir,
        checkpoint_path=checkpoint_path,
        config_path=config_path,
        vocab_path=vocab_path,
        speaker_file_path=speaker_file_path,
        device=args.device,
    )
    speaker_wav = str(Path(args.speaker_wav).resolve())

    gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
        audio_path=speaker_wav,
        gpt_cond_len=model.config.gpt_cond_len,
        max_ref_length=model.config.max_ref_len,
        sound_norm_refs=model.config.sound_norm_refs,
    )
    out = model.inference(
        text=args.text,
        language=args.language,
        gpt_cond_latent=gpt_cond_latent,
        speaker_embedding=speaker_embedding,
        temperature=model.config.temperature,
        length_penalty=model.config.length_penalty,
        repetition_penalty=model.config.repetition_penalty,
        top_k=model.config.top_k,
        top_p=model.config.top_p,
    )

    wav = torch.tensor(out["wav"], dtype=torch.float32).cpu().numpy()
    sf.write(str(out_path), wav, 24000)
    print(out_path.resolve())


if __name__ == "__main__":
    main()
