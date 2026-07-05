#!/usr/bin/env python3
import re

FILE = "/Users/swan/Documents/1024/vibe/时光收音机/docs/design/prototype/src/app/components/tuner-radio.tsx"

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

def replace_if_exists(old, new, desc):
    global content
    if old in content:
        content = content.replace(old, new)
        print(f"  OK: {desc}")
        return True
    else:
        print(f"  SKIP (already done or not found): {desc}")
        return False

print("Applying fixes to tuner-radio.tsx...")
print()

# 1. Add "date" to Program type (if not already there)
replace_if_exists(
    'type: "anchor" | "song" | "jingle" | "news" | "life" | "id" | "poetry";',
    'type: "anchor" | "song" | "jingle" | "news" | "life" | "id" | "poetry" | "date";',
    "Add 'date' to Program type"
)

# 2. Add generateDateJingles and DATE_JINGLES
if 'generateDateJingles' not in content:
    date_jingles_code = '''
function generateDateJingles(): Program[] {
  const programs: Program[] = [];
  for (let y = 1949; y <= 1960; y++) {
    for (let m = 1; m <= 12; m++) {
      programs.push({
        id: `date_${y}_${String(m).padStart(2, "0")}`,
        year: y,
        month: m,
        file: `date_${y}_${String(m).padStart(2, "0")}.wav`,
        type: "date",
        volume: 0.92,
        isLoop: false,
      });
    }
  }
  return programs;
}

const DATE_JINGLES = generateDateJingles();

'''
    content = content.replace(
        '\ninterface PoetryItem {',
        date_jingles_code + 'interface PoetryItem {'
    )
    print("  OK: Add generateDateJingles and DATE_JINGLES")
else:
    print("  SKIP: generateDateJingles already exists")

# 3. Add DATE_JINGLES to FLOATS
replace_if_exists(
    'const FLOATS: Program[] = [...generateMonthlyNewsPrograms(), ...generatePoetryPrograms(), ...OTHER_FLOATS];',
    'const FLOATS: Program[] = [...generateMonthlyNewsPrograms(), ...generatePoetryPrograms(), ...OTHER_FLOATS, ...DATE_JINGLES];',
    "Add DATE_JINGLES to FLOATS"
)

# 4. Add mustPlayDateRef and playNextRetryRef
if 'mustPlayDateRef' not in content:
    content = content.replace(
        'const pendingEnterLockedRef = useRef(false);',
        'const pendingEnterLockedRef = useRef(false);\n  const mustPlayDateRef = useRef(false);\n  const playNextRetryRef = useRef(0);'
    )
    print("  OK: Add mustPlayDateRef and playNextRetryRef")
else:
    print("  SKIP: mustPlayDateRef already exists")

# 5. Replace loadAudioBuffers with three-stage version
old_load = '''  const loadAudioBuffers = useCallback(async () => {
    const ctx = ctxRef.current!;

    for (const track of BGM_TRACKS) {
      try {
        const buf = await loadBuffer(`/audio/${track.file}`);
        bgmBuffersRef.current.set(track.id, buf);
      } catch {
        // 跳过加载失败的bgm
      }
    }
    for (const track of SONG_BGM_TRACKS) {
      try {
        const buf = await loadBuffer(`/audio/${track.file}`);
        bgmBuffersRef.current.set(track.id, buf);
      } catch {
        // 跳过加载失败的bgm
      }
    }
    try {
      const buf = await loadBuffer(`/audio/songs/song_zhiyuanjun.mp3`);
      bgmBuffersRef.current.set("song_zhiyuanjun", buf);
    } catch {}

    const loadOne = async (p: Program, map: Map<string, ProgramSource>) => {
      try {
        const basePath = p.file.startsWith("songs/") ? "/audio/" : "/audio/programs/";
        const buf = await loadBuffer(`${basePath}${p.file}`);
        map.set(p.id, createSource(ctx, buf, p.volume));
      } catch {
        // 文件可能尚未生成（如TTS处理中的新闻），跳过加载
      }
    };

    await Promise.all([
      ...ANCHORS.map(p => loadOne(p, anchorSourcesRef.current)),
      ...FLOATS.map(p => loadOne(p, floatSourcesRef.current)),
    ]);
    isReadyRef.current = true;

    if (pendingEnterLockedRef.current) {
      pendingEnterLockedRef.current = false;
      enterLockedRef.current();
    } else if (isPoweredOnRef.current && !isTuningRef.current && !isLockedRef.current) {
      enterLockedRef.current();
    }
  }, [loadBuffer, createSource]);'''

new_load = '''  const loadAudioBuffers = useCallback(async () => {
    const ctx = ctxRef.current!;

    const loadOne = async (p: Program, map: Map<string, ProgramSource>) => {
      try {
        const basePath = p.file.startsWith("songs/") ? "/audio/" : "/audio/programs/";
        const buf = await loadBuffer(`${basePath}${p.file}`);
        map.set(p.id, createSource(ctx, buf, p.volume));
        return true;
      } catch {
        return false;
      }
    };

    const stage1Tracks = [...BGM_TRACKS, ...SONG_BGM_TRACKS];
    for (const track of stage1Tracks) {
      try {
        const buf = await loadBuffer(`/audio/${track.file}`);
        bgmBuffersRef.current.set(track.id, buf);
      } catch {}
    }
    try {
      const buf = await loadBuffer(`/audio/songs/song_zhiyuanjun.mp3`);
      bgmBuffersRef.current.set("song_zhiyuanjun", buf);
    } catch {}

    await Promise.all(ANCHORS.map(p => loadOne(p, anchorSourcesRef.current)));
    isReadyRef.current = true;

    const y = Math.floor(currentYearRef.current);
    const m = yearToMonth(currentYearRef.current);
    const firstProgId = `news_${y}_${String(m).padStart(2, "0")}`;
    const firstProg = FLOATS.find(f => f.id === firstProgId);
    const firstDateId = `date_${y}_${String(m).padStart(2, "0")}`;
    const firstDateProg = FLOATS.find(f => f.id === firstDateId);

    if (firstProg) {
      await loadOne(firstProg, floatSourcesRef.current);
    }
    if (firstDateProg) {
      await loadOne(firstDateProg, floatSourcesRef.current);
    }

    if (isPoweredOnRef.current && !isTuningRef.current && !isLockedRef.current) {
      enterLockedRef.current();
    } else {
      pendingEnterLockedRef.current = true;
    }

    const loadRemaining = async () => {
      const alreadyLoaded = new Set([
        ...(firstProg ? [firstProg.id] : []),
        ...(firstDateProg ? [firstDateProg.id] : []),
      ]);
      const batchSize = 10;
      const remaining = FLOATS.filter(f => !alreadyLoaded.has(f.id));
      for (let i = 0; i < remaining.length; i += batchSize) {
        const batch = remaining.slice(i, i + batchSize);
        await Promise.all(batch.map(p => loadOne(p, floatSourcesRef.current)));
      }
    };
    loadRemaining();
  }, [loadBuffer, createSource]);'''

replace_if_exists(old_load, new_load, "Replace loadAudioBuffers with three-stage loading")

# 6. Replace setPlaybackLevels noise values
old_setpb = '''    if (progType === "news" || progType === "life" || progType === "jingle" || progType === "poetry") {
      noiseVol = 0.00015;
      noiseQ = 10.0;
      noiseFreq = 2800;
    } else {
      noiseVol = 0.002;
      noiseQ = 5.0;
      noiseFreq = 2000;
    }'''
new_setpb = '''    if (progType === "news" || progType === "life" || progType === "jingle" || progType === "poetry" || progType === "date") {
      noiseVol = 0.00006;
      noiseQ = 3.0;
      noiseFreq = 2400;
    } else {
      noiseVol = 0.0003;
      noiseQ = 3.0;
      noiseFreq = 2000;
    }'''
replace_if_exists(old_setpb, new_setpb, "Update setPlaybackLevels noise values and add date")

# 7. Replace playNext function
old_playnext_start = '  const playNext = useCallback(() => {'
old_playnext_end = '  }, [setPlaybackLevels, startSource, stopCurrentFloat, stopSource, startBgm, stopBgm, pickBgmForEvent]);'

playnext_start_idx = content.find(old_playnext_start)
playnext_end_idx = content.find(old_playnext_end, playnext_start_idx)
if playnext_start_idx != -1 and playnext_end_idx != -1:
    playnext_end_idx += len(old_playnext_end)
    new_playnext = '''  const playNext = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx || !isLockedRef.current) return;

    if (songTimerRef.current) {
      clearTimeout(songTimerRef.current);
      songTimerRef.current = null;
    }

    if (mustPlayDateRef.current) {
      const y = Math.floor(currentYearRef.current);
      const m = yearToMonth(currentYearRef.current);
      const dateId = `date_${y}_${String(m).padStart(2, "0")}`;
      const dateProg = DATE_JINGLES.find(d => d.id === dateId);
      if (dateProg) {
        let datePs = floatSourcesRef.current.get(dateProg.id);
        if (!datePs) {
          if (playNextRetryRef.current < 30) {
            playNextRetryRef.current++;
            setTimeout(() => playNextRef.current(), 100);
            return;
          }
          playNextRetryRef.current = 0;
          mustPlayDateRef.current = false;
        } else {
          playNextRetryRef.current = 0;
          mustPlayDateRef.current = false;
          stopCurrentFloat();
          segmentTypeRef.current = "news";
          currentPlayingRef.current = { prog: dateProg, source: null as unknown as AudioBufferSourceNode };
          currentLoopRef.current = false;
          setPlaybackLevels("date");
          datePs.filter.type = "bandpass";
          datePs.filter.frequency.value = 2800;
          datePs.filter.Q.value = 0.4;
          startBgm({ volume: 0.02, filterFreq: 1800, filterQ: 0.5 });
          const td = ctx.currentTime;
          datePs.gain.gain.cancelScheduledValues(td);
          datePs.gain.gain.setValueAtTime(0, td);
          datePs.gain.gain.linearRampToValueAtTime(dateProg.volume, td + 0.1);
          startSource(datePs, false, () => {
            if (currentPlayingRef.current?.prog.id !== dateProg.id) return;
            currentPlayingRef.current = null;
            setTimeout(() => playNextRef.current(), GAP_BETWEEN_ITEMS_MS);
          });
          if (datePs.source) {
            currentPlayingRef.current = { prog: dateProg, source: datePs.source };
          }
          return;
        }
      } else {
        mustPlayDateRef.current = false;
      }
    }

    const prog = programQueueRef.current.shift() ?? null;
    if (!prog) {
      rebuildAndPlayRef.current();
      return;
    }
    lastPlayedProgIdRef.current = prog.id;

    if (prog.type === "song") {
      const ps = floatSourcesRef.current.get(prog.id);
      if (!ps) {
        if (playNextRetryRef.current < 30) {
          programQueueRef.current.unshift(prog);
          playNextRetryRef.current++;
          setTimeout(() => playNextRef.current(), 100);
          return;
        }
        playNextRetryRef.current = 0;
        playNextRef.current();
        return;
      }
      playNextRetryRef.current = 0;

      stopCurrentFloat();

      segmentTypeRef.current = "music";
      currentPlayingRef.current = { prog, source: null as unknown as AudioBufferSourceNode };
      currentLoopRef.current = true;
      setPlaybackLevels("song");
      stopBgm();

      const t0 = ctx.currentTime;
      ps.gain.gain.cancelScheduledValues(t0);
      ps.gain.gain.setValueAtTime(0, t0);
      ps.gain.gain.linearRampToValueAtTime(prog.volume * 0.85, t0 + 0.3);

      ps.filter.type = "lowpass";
      ps.filter.frequency.value = 4000;
      ps.filter.Q.value = 0.5;

      startSource(ps, true, undefined);
      if (ps.source) {
        currentPlayingRef.current = { prog, source: ps.source };
      }

      const hasMoreInQueue = programQueueRef.current.length > 0;
      songTimerRef.current = window.setTimeout(() => {
        const t1 = ctx.currentTime;
        ps.gain.gain.cancelScheduledValues(t1);
        ps.gain.gain.linearRampToValueAtTime(0, t1 + SONG_FADE_OUT_MS / 1000);
        setTimeout(() => {
          stopSource(ps);
          currentPlayingRef.current = null;
          currentLoopRef.current = false;
          songTimerRef.current = null;
          if (isLockedRef.current) {
            if (hasMoreInQueue) {
              setTimeout(() => playNextRef.current(), GAP_BETWEEN_ITEMS_MS);
            } else {
              rebuildAndPlayRef.current();
            }
          }
        }, SONG_FADE_OUT_MS);
      }, hasMoreInQueue ? Math.min(SONG_SEGMENT_MS, 12000) : SONG_SEGMENT_MS);
      return;
    }

    const ps = floatSourcesRef.current.get(prog.id);
    if (!ps) {
      if (playNextRetryRef.current < 30) {
        programQueueRef.current.unshift(prog);
        playNextRetryRef.current++;
        setTimeout(() => playNextRef.current(), 100);
        return;
      }
      playNextRetryRef.current = 0;
      playNextRef.current();
      return;
    }
    playNextRetryRef.current = 0;

    stopCurrentFloat();

    const isVoice = prog.type === "news" || prog.type === "life" || prog.type === "poetry" || prog.type === "date";
    segmentTypeRef.current = isVoice ? "news" : "filler";
    currentPlayingRef.current = { prog, source: null as unknown as AudioBufferSourceNode };
    currentLoopRef.current = false;
    setPlaybackLevels(prog.type);

    if (isVoice) {
      ps.filter.type = "bandpass";
      ps.filter.frequency.value = 2800;
      ps.filter.Q.value = 0.4;
    } else {
      ps.filter.type = "lowpass";
      ps.filter.frequency.value = 5000;
      ps.filter.Q.value = 0.5;
    }

    const voiceType: "news" | "life" | "poetry" | "date" | null = isVoice
      ? (prog.type === "news" ? "news" : prog.type === "life" ? "life" : prog.type === "poetry" ? "poetry" : "date")
      : null;

    if (isVoice && voiceType) {
      const curYear = Math.floor(currentYearRef.current);
      const curMonth = yearToMonth(currentYearRef.current);
      const isSameVoiceBlock = lastVoiceTypeRef.current === voiceType && currentBgmIdRef.current !== null;

      let bgmConfig: { bgmId?: string; bgmVolume: number; bgmFilterFreq: number; bgmFilterQ: number };
      if (prog.type === "poetry") {
        bgmConfig = { bgmVolume: 0.025, bgmFilterFreq: 1500, bgmFilterQ: 0.6 };
      } else if (prog.type === "date") {
        bgmConfig = { bgmVolume: 0.02, bgmFilterFreq: 1800, bgmFilterQ: 0.5 };
      } else if (isSameVoiceBlock && currentBgmIdRef.current) {
        const cachedId = currentBgmIdRef.current;
        const isZhiyuanjun = cachedId === "song_zhiyuanjun";
        bgmConfig = {
          bgmId: cachedId,
          bgmVolume: isZhiyuanjun ? 0.04 : 0.07,
          bgmFilterFreq: isZhiyuanjun ? 1800 : 2500,
          bgmFilterQ: isZhiyuanjun ? 0.7 : 0.5,
        };
      } else {
        const isNewsItem = prog.type === "news";
        const picked = pickBgmForEvent(
          curYear,
          curMonth,
          isNewsItem && prog.id.startsWith("news_") ? prog.id : undefined
        );
        bgmConfig = picked;
        currentBgmIdRef.current = picked.bgmId;
      }
      lastVoiceTypeRef.current = voiceType;

      if (bgmFilterRef.current) {
        const t = ctx.currentTime;
        bgmFilterRef.current.frequency.cancelScheduledValues(t);
        bgmFilterRef.current.Q.cancelScheduledValues(t);
        bgmFilterRef.current.frequency.linearRampToValueAtTime(bgmConfig.bgmFilterFreq, t + 0.5);
        bgmFilterRef.current.Q.linearRampToValueAtTime(bgmConfig.bgmFilterQ, t + 0.5);
      }
      startBgm(prog.type === "poetry" || prog.type === "date"
        ? { volume: bgmConfig.bgmVolume, filterFreq: bgmConfig.bgmFilterFreq, filterQ: bgmConfig.bgmFilterQ }
        : { bgmId: bgmConfig.bgmId, volume: bgmConfig.bgmVolume, filterFreq: bgmConfig.bgmFilterFreq, filterQ: bgmConfig.bgmFilterQ }
      );
    } else if (prog.type === "song") {
      lastVoiceTypeRef.current = null;
      currentBgmIdRef.current = null;
      stopBgm();
    }

    const t0 = ctx.currentTime;
    ps.gain.gain.cancelScheduledValues(t0);
    ps.gain.gain.setValueAtTime(0, t0);
    ps.gain.gain.linearRampToValueAtTime(prog.volume, t0 + 0.1);

    startSource(ps, false, () => {
      if (currentPlayingRef.current?.prog.id !== prog.id) return;
      currentPlayingRef.current = null;
      setTimeout(() => playNextRef.current(), GAP_BETWEEN_ITEMS_MS);
    });

    if (ps.source) {
      currentPlayingRef.current = { prog, source: ps.source };
    }
  }, [setPlaybackLevels, startSource, stopCurrentFloat, stopSource, startBgm, stopBgm, pickBgmForEvent]);'''
    content = content[:playnext_start_idx] + new_playnext + content[playnext_end_idx:]
    print("  OK: Replace playNext function")
else:
    print("  SKIP: playNext boundaries not found")

# 8. Fix lastVoiceTypeRef type
replace_if_exists(
    'const lastVoiceTypeRef = useRef<"news" | "life" | "poetry" | null>(null);',
    'const lastVoiceTypeRef = useRef<"news" | "life" | "poetry" | "date" | null>(null);',
    "Update lastVoiceTypeRef type to include date"
)

# 9. Fix buildProgramQueue to exclude date type
old_filler = '(f.type === "life" || f.type === "poetry") && isProgramAvailable(f, targetYear, targetMonth)'
new_filler = '(f.type === "life" || f.type === "poetry") && f.type !== "date" && isProgramAvailable(f, targetYear, targetMonth)'
replace_if_exists(old_filler, new_filler, "Exclude date type from filler segments in buildProgramQueue")

# Also exclude date from availableSongs and news filters (date is not song/news, so it's already excluded by type check, but let's make sure)
# Actually date won't match "life"|"poetry"|"song"|"news" filters so it's already excluded. Good.

# 10. Fix enterLocked: mustPlayDate, noise 0.0002, Q=3.0
old_enterlocked_noise = '''    if (noiseGainRef.current) {
      noiseGainRef.current.gain.cancelScheduledValues(t);
      noiseGainRef.current.gain.linearRampToValueAtTime(0.0005, t + 0.3);
    }
    if (noiseFilterRef.current) {
      noiseFilterRef.current.Q.cancelScheduledValues(t);
      noiseFilterRef.current.Q.linearRampToValueAtTime(10.0, t + 0.3);
    }'''
new_enterlocked_noise = '''    mustPlayDateRef.current = true;
    if (noiseGainRef.current) {
      noiseGainRef.current.gain.cancelScheduledValues(t);
      noiseGainRef.current.gain.linearRampToValueAtTime(0.0002, t + 0.3);
    }
    if (noiseFilterRef.current) {
      noiseFilterRef.current.Q.cancelScheduledValues(t);
      noiseFilterRef.current.Q.linearRampToValueAtTime(3.0, t + 0.3);
    }'''
replace_if_exists(old_enterlocked_noise, new_enterlocked_noise, "Fix enterLocked noise and add mustPlayDate")

# 11. Fix powerOn: noise ramp to 0.42
replace_if_exists(
    'g.linearRampToValueAtTime(0.45, now + 0.05);',
    'g.linearRampToValueAtTime(0.42, now + 0.05);',
    "Fix powerOn initial noise to 0.42"
)

# 12. Fix setTuning noise parameters
old_tuning_noise = '''    } else if (isLockedRef.current) {
      targetNoise = isNewsSeg ? 0.00015 : (isMusicSeg ? 0.002 : 0.001);
      targetQ = isNewsSeg ? 10.0 : 5.0;
      targetCenter = 2000;
      noiseFadeTime = 0.3;
    } else {
      targetNoise = 0.02;
      targetQ = 4.0;
      targetCenter = 2000;
      noiseFadeTime = 0.5;
    }'''
new_tuning_noise = '''    } else if (isLockedRef.current) {
      targetNoise = isNewsSeg ? 0.00006 : (isMusicSeg ? 0.0003 : 0.0001);
      targetQ = 3.0;
      targetCenter = 2000;
      noiseFadeTime = 0.3;
    } else {
      targetNoise = 0.35;
      targetQ = 2.0;
      targetCenter = 2000;
      noiseFadeTime = 0.15;
    }'''
replace_if_exists(old_tuning_noise, new_tuning_noise, "Fix setTuning noise parameters")

# 13. Add 20% date chance on tuning stop
old_tuning_stop = '''      if (!isTuning && wasTuning) {
        restoreCurrentProgram(0.3);
        if (noiseLockTimerRef.current) clearTimeout(noiseLockTimerRef.current);
        noiseLockTimerRef.current = window.setTimeout(() => {
          if (!isTuningRef.current && isPoweredOnRef.current) {
            enterLocked();
          }
        }, LOCK_DELAY_MS);
      }'''
new_tuning_stop = '''      if (!isTuning && wasTuning) {
        restoreCurrentProgram(0.3);
        if (Math.random() < 0.2) {
          mustPlayDateRef.current = true;
        }
        if (noiseLockTimerRef.current) clearTimeout(noiseLockTimerRef.current);
        noiseLockTimerRef.current = window.setTimeout(() => {
          if (!isTuningRef.current && isPoweredOnRef.current) {
            enterLocked();
          }
        }, LOCK_DELAY_MS);
      }'''
replace_if_exists(old_tuning_stop, new_tuning_stop, "Add 20% date chance on tuning stop")

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print()
print("All fixes applied!")
