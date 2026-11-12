# MasterForge Web Studio v1.0 beta — Dynamic Signature

The browser edition now uses `web-mastering.js` for entirely local processing. The source file is decoded by the browser, analyzed across its complete duration, rendered through Web Audio's offline signal graph, loudness-normalized and peak-protected in JavaScript, and exported through the existing WAV/MP3/M4A controls. Neither audio nor section analysis is sent to a mastering server in Browser Local mode.

## Actual signal path

1. **Full-song analysis** — 2-second windows across the entire decoded recording. Relative RMS, crest factor, percentile spread and spectral-band proxies classify quiet, steady, dense and transient-rich sections. This does not identify verses or choruses semantically.
2. **Source-aware EQ** — bounded low-frequency shelf (115 Hz), low-mid cut (560 Hz), presence (4.4 kHz), air shelf (8.5 kHz), plus a 26 Hz high-pass filter. Signature makes gain choices based on aggregate program balance rather than only the intro.
3. **Dynamic EQ** — time-varying, bounded cuts at 560 Hz and 6.2 kHz when a section has increased low-mid or high-frequency energy relative to the whole track.
4. **Section gain automation** — small, smoothly interpolated boosts/reductions, preserving transient-rich sections where possible; quiet/steady/dense classification uses the same basic thresholds as the Python reference engine, not exact DSP parity.
5. **Guarded stereo width** — ~12% extra side-channel energy when the source has safe channel correlation and adequate side signal, never on mono sources.
6. **Conditional compression** — broadband Web Audio dynamics compression when section loudness suggests that additional control is useful; Signature uses a gentle 1.17:1 setting with 45 ms attack and 280 ms release.
7. **Integrated loudness estimation** — EBU-style K-weighting with 400 ms blocks, 75% overlap, -70 LUFS absolute gate and -10 LU relative gate. The chosen integrated loudness is a target, not a guaranteed achieved value. The report includes measured estimated result.
8. **Peak protection** — a bounded time-varying output gain envelope and a 4x cubic-interpolated intersample peak check, followed by a safety trim if needed. Signature applies a conservative -1.3 dB estimated peak ceiling to leave extra margin for reconstruction; the intended compatibility goal is -1.1 dBTP on a calibrated meter. This is not equivalent to a calibrated BS.1770 true-peak limiter.

## Compatibility and privacy

- The current web output is **not bit-identical** to Python/FFmpeg Dynamic Signature. Browser differences in decoding, filter response, compressor attack, limiting, and audio rounding mean that parity must be established by further listening tests.
- Browser support for AudioContext/OfflineAudioContext and codecs varies. Large songs can exhaust memory because decoding and offline rendering allocate PCM buffers. There is **no fixed app duration limit**.
- WAV exports remain 24-bit; MP3 and M4A/AAC retain the browser's existing encoder compatibility requirements. Lossy formats can create additional intersample peaks.
- The app shell is served from GitHub Pages or another HTTPS static host. The song is decoded, analyzed and mastered in the user's own browser. Do not enable an optional remote Studio API if you want strictly local operation.
- No trained neural network is used. Dynamic Signature is source-adaptive digital signal processing.

## Validation performed

- Synthetic 24-second program: quiet, dense and transient-heavy sections classified separately and bounded automation generated.
- A 12-second browser audio render in Chromium: full duration retained, mode Signature, integrated loudness estimate -14 LUFS (for an -14 setting), peak estimate below -1 dBTP, waveform channel count/sample rate retained.
- See `tests/web-mastering.test.cjs` for repeatable Node test of the analysis helpers. Additional real-device tests in iOS Safari and external FFmpeg loudness/true-peak comparison are required before claiming equivalent quality to the desktop engine.