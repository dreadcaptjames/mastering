# MasterForge AI — Dynamic Mastering (v0.10.0)

The Python desktop engine now responds to a recording **as it progresses**, rather than using only a static tonal recipe. The four presets and all existing WAV/MP3/M4A exports remain available.

## What actually happens

1. **Whole-song baseline**: reads all of the song for loudness and stereo / five-band tonal analysis. This still determines the broad mastering EQ curve for the song.
2. **Time-local scene analysis**: reads the *entire* song once again as 8 kHz mono monitoring audio in 2-second windows. Calculates window RMS, crest factor, and percentiles relative to the particular song, not an absolute genre threshold.
3. **Scene classes**: `quiet`, `steady`, `dense`, `transient`, or `silence`. These are acoustic descriptions, not claims that the engine identifies lyrical verses or choruses. A dense chorus is likely to register as `dense` but may not if its RMS is similar to the rest of the song.
4. **Smoothed scene-based gain**: quiet sections get a gentle lift, dense sections get slight restraint, transient-heavy sections get less broad gain adjustment. For Signature, changes are bounded to roughly ±0.66 dB per scene; Natural/Balanced/Impact have different strengths. Adjacent gains are joined by a cubic smoothstep in a separate 200 Hz automation control WAV. The control is mixed into the audio through FFmpeg's `amultiply`, so processing varies *within* the rendered song. The temporary automation file is automatically deleted at the end of mastering.
5. **Program-dependent compressor**: Signature uses RMS detection with a gentle 1.25:1 ratio, 55 ms attack, 280 ms release, and 65% parallel blend. Faster transients are less aggressively compressed than sustained material. Other presets retain their original conditional compressor behavior.
6. **Dynamic frequency control**: when the installed FFmpeg supports `adynamicequalizer`, Signature adds a modest 560 Hz dynamic low-mid cut and 6.2 kHz harshness control, both driven by the current audio rather than fixed timestamps. If that filter is unavailable in an older build, the time-varying gain and compressor still operate; this is recorded in the JSON report.
7. **Two-pass loudness normalization and verified export**: measures the *same automated chain* that renders the master. It normalizes toward the selected integrated LUFS target and checks final measured LUFS, true peak, and output duration. Standard WAV output is stereo 24-bit 48 kHz. MP3 and M4A are encoded from the final WAV when requested.

## What the report includes

Use **Save Processing Report** to export JSON. Look for:

- `recipe.dynamic_sections`: number of seconds in each scene class, maximum applied gain deviation, and analysis window size.
- `recipe.dynamic_eq`: whether frequency-responsive dynamic EQ was enabled.
- `recipe.compressor_behavior`: how the compressor was selected.
- `dynamic_analysis.sections[]`: every 2-second analysis window with start/end time, RMS dBFS, crest factor, scene, and automation gain in dB.
- `input` and `output`: measurements from FFmpeg's loudnorm filter. The app's UI also summarizes scene durations after rendering.

## Important limitations

- There is **no trained AI model** and **no source separation**. The detector cannot know the musical role of an instrument or identify the boundaries of real verses/choruses by name. It classifies passages by short-term acoustic measurements.
- The broad EQ and initial stereo adjustments are still based on whole-song measurements; the extra dynamic EQ responds to frequency energy continuously. Stereo widening is safeguarded by whole-track correlation checks, not dynamically automated per-section.
- Scene gain changes are deliberately restrained to prevent audible pumping. The integrated loudness normalization/true-peak stage can still alter dynamics when a very loud target is chosen. "Dynamic" does not mean that a heavily limited source can regain lost transients.
- FFT/tonal analysis uses a downsampled monitoring stream, while mastering uses the full-resolution original input. FFmpeg versions and source codecs can produce small differences. Real-world listening tests are still needed.
- Up to six-hour source recordings remain supported by existing code limits, but very large files may take substantial CPU time for the multiple analysis, two-pass mastering, and verification stages.

## Running the desktop application

Extract the full ZIP and run `RUN-MASTERFORGE-WINDOWS.bat` on Windows, or `RUN-MASTERFORGE-CACHYOS.sh` on CachyOS after installing `python`, `tk`, and `ffmpeg`. No GitHub or Electron is required. The application UI, themes, track scrubber, and desktop setup scripts are preserved.
