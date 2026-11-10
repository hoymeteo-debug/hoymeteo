#!/usr/bin/env python3
"""Compone las pistas lo-fi de @hoymeteo (música propia, sin licencias de terceros).

Cada pista: acordes de piano eléctrico con séptimas, bajo suave, batería con swing,
una melodía pentatónica escasa y el «crujido de vinilo» típico del lo-fi.
Es determinista: la misma semilla da siempre la misma pista.

  python tools/make_music.py            # genera music/lofi_1.m4a … lofi_8.m4a
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "music"

# Acordes en semitonos desde la tónica
CHORDS = {
    "I": [0, 4, 7, 11], "ii": [2, 5, 9, 12], "iii": [4, 7, 11, 14], "IV": [5, 9, 12, 16],
    "V": [7, 11, 14, 17], "vi": [9, 12, 16, 19],
}
PROGRESSIONS = [["I", "vi", "ii", "V"], ["ii", "V", "I", "I"], ["IV", "iii", "ii", "I"], ["I", "IV", "iii", "vi"]]
# (tonalidad, tempo, progresión, semilla)
TRACKS = [(5, 74, 0, 1), (2, 78, 1, 2), (3, 72, 2, 3), (7, 80, 3, 4),
          (9, 76, 0, 5), (0, 82, 2, 6), (10, 70, 1, 7), (4, 77, 3, 8)]
PENTA = [0, 2, 4, 7, 9]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def fold(m, lo, hi):
    while m < lo:
        m += 12
    while m > hi:
        m -= 12
    return m


def env(n, attack, decay):
    t = np.arange(n) / SR
    e = np.minimum(t / attack, 1.0) * np.exp(-t / decay)
    fade = np.minimum(1.0, (n - np.arange(n)) / (0.02 * SR))  # sin clics al final
    return e * fade


def epiano(freq, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
            + 0.12 * np.sin(2 * np.pi * 3 * freq * t) * np.exp(-t / 0.3))
    trem = 1 + 0.08 * np.sin(2 * np.pi * 4.5 * t)
    return vel * tone * trem * env(n, 0.012, 1.4)


def bell(freq, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * 4 * freq * t) * np.exp(-t / 0.15)
    return vel * tone * env(n, 0.005, 0.7)


def bass(freq, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * 2 * freq * t)
    return vel * tone * env(n, 0.01, 0.5)


def kick(rng):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 45 + 75 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.18)


def snare(rng):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = lowpass(rng.standard_normal(n), 5000)
    return (0.6 * noise + 0.4 * np.sin(2 * np.pi * 185 * t)) * env(n, 0.002, 0.07)


def hat(rng):
    n = int(0.06 * SR)
    noise = rng.standard_normal(n)
    noise = noise - lowpass(noise, 6000)  # agudos
    return noise * env(n, 0.001, 0.015)


def lowpass(x, cutoff):
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1 / np.sqrt(1 + (freqs / cutoff) ** 4)  # caída suave de 2.º orden
    return np.fft.irfft(spec, len(x))


def place(buf, sound, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sound))
    buf[i:j] += sound[:j - i]


def track(key, bpm, prog_idx, seed, seconds=16.0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    keys, low, drums, mel = (np.zeros(n) for _ in range(4))
    beat = 60.0 / bpm
    bar = 4 * beat
    prog = PROGRESSIONS[prog_idx]
    swing = 0.58
    t, b = 0.0, 0
    while t < seconds:
        chord = CHORDS[prog[b % 4]]
        root = chord[0]
        # Acordes: rasgueo suave (notas escalonadas) en el 1 y una repetición más suave en el «y» del 2
        for hit, vel in ((0.0, 0.9), (1.5 + (swing - 0.5), 0.45)):
            for k, iv in enumerate(chord):
                m = fold(60 + key + iv, 53, 72)
                place(keys, epiano(midi_hz(m), bar, vel * 0.22), t + hit * beat + k * 0.018)
        # Bajo
        bm = fold(36 + key + root, 33, 45)
        place(low, bass(midi_hz(bm), beat * 1.6, 0.5), t)
        place(low, bass(midi_hz(bm + 7 if rng.random() < 0.5 else bm), beat * 0.9, 0.32), t + 2.5 * beat)
        # Batería: bombo 1 y «y» del 3, caja 2 y 4, charles en corcheas con swing
        place(drums, kick(rng) * 0.55, t)
        place(drums, kick(rng) * 0.4, t + 2.5 * beat)
        place(drums, snare(rng) * 0.18, t + beat)
        place(drums, snare(rng) * 0.18, t + 3 * beat)
        for e in range(8):
            off = (e // 2) * beat + (e % 2) * swing * beat
            place(drums, hat(rng) * (0.05 if e % 2 else 0.07), t + off)
        # Melodía escasa (pentatónica), no en todos los compases
        if b % 4 in (1, 3) or rng.random() < 0.3:
            for s in sorted(rng.choice(8, size=rng.integers(2, 4), replace=False)):
                m = fold(72 + key + PENTA[rng.integers(0, 5)], 70, 86)
                place(mel, bell(midi_hz(m), beat * 1.5, 0.1), t + s * beat / 2)
        t += bar
        b += 1

    mix = 1.0 * keys + 0.9 * low + 0.9 * drums + 0.8 * mel
    # Lo-fi: filtro de paso bajo, ligera oscilación de cinta, siseo y crujidos de vinilo
    mix = lowpass(mix, 3800)
    tt = np.arange(n) / SR
    warp = tt + 0.0012 * np.sin(2 * np.pi * 0.35 * tt)
    mix = np.interp(warp, tt, mix)
    hiss = lowpass(rng.standard_normal(n), 2500) * 0.004
    clicks = np.zeros(n)
    for i in rng.integers(0, n, size=int(seconds * 6)):
        clicks[i] = rng.uniform(0.05, 0.18) * rng.choice([-1, 1])
    clicks = lowpass(clicks, 3000)
    mix = mix + hiss + clicks
    # Entrada y salida suaves, compresión suave y normalización
    fade = np.minimum(1, tt / 0.6) * np.minimum(1, (seconds - tt) / 1.5)
    mix = np.tanh(1.4 * mix / (np.max(np.abs(mix)) + 1e-9)) * fade
    return (mix / np.max(np.abs(mix)) * 0.7).astype(np.float32)


def save_m4a(samples, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    stereo = np.stack([samples, samples], axis=1)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(path)]
    subprocess.run(cmd, input=stereo.tobytes(), check=True)


def main():
    for i, (key, bpm, prog, seed) in enumerate(TRACKS, 1):
        out = OUT / f"lofi_{i}.m4a"
        save_m4a(track(key, bpm, prog, seed), out)
        print(f"{out.name}: tonalidad {key}, {bpm} bpm, progresión {'-'.join(PROGRESSIONS[prog])}")


if __name__ == "__main__":
    sys.exit(main())
