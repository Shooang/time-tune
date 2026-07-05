#!/usr/bin/env python3
"""一次性修改tuner-radio.tsx的所有需要修改的地方"""
import re

FILE = "/Users/swan/Documents/1024/vibe/时光收音机/docs/design/prototype/src/app/components/tuner-radio.tsx"

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 替换 getAvailableFullDatesForMonth 到 DATE_SHORTS 的整个块
old_block1 = '''function getAvailableFullDatesForMonth(y: number, m: number): string[] {
  const all = [
    "01","02","03","04","05","06","07","08","09","10",
    "11","12","13","14","15","16","17","18","19","20",
    "21","22","23","24","25","26","27","28","29","30","31"
  ];
  const rng = (seed: number) => {
    let s = seed;
    return () => { s = (s * 16807 + 0) % 2147483647; return s / 2147483647; };
  };
  const r = rng(y * 100 + m);
  const daysInMonth = new Date(y, m, 0).getDate();
  const picked: number[] = [];
  const used = new Set<number>();
  while (picked.length < Math.min(3, daysInMonth)) {
    const d = Math.floor(r() * daysInMonth) + 1;
    if (!used.has(d)) { used.add(d); picked.push(d); }
  }
  return picked.sort((a, b) => a - b).map(d => String(d).padStart(2, "0"));
}

function pickDateIntroFile(y: number, m: number, forceFull: boolean): { file: string; progId: string; isFull: boolean } {
  const useFull = forceFull || Math.random() < 0.7;
  const ym = `${y}_${String(m).padStart(2, "0")}`;
  if (useFull) {
    const days = getAvailableFullDatesForMonth(y, m);
    const day = days[Math.floor(Math.random() * days.length)];
    return { file: `date_${ym}_${day}.wav`, progId: `date_${ym}_${day}`, isFull: true };
  } else {
    return { file: `date_short_${ym}.wav`, progId: `date_short_${ym}`, isFull: false };
  }
}

const DATE_INTRO_PROG: Program = {
  id: "date_intro_marker",
  year: 1949,
  file: "",
  type: "date_intro",
  volume: 0.92,
  isLoop: false,
};

const DATE_SHORTS = generateDateShorts();'''

new_block1 = '''const DATE_FULL_DAYS: Record<string, number[]> = {
  "1949_01": [12,23,30], "1949_02": [1,3,20], "1949_03": [9,24,28], "1949_04": [14,25,27],
  "1949_05": [1,5,12], "1949_06": [6,9,15], "1949_07": [8,28,31], "1949_08": [5,25,28],
  "1949_09": [7,22,26], "1949_10": [2,14,22], "1949_11": [12,20,23], "1949_12": [24,26,30],
  "1950_01": [6,7,31], "1950_02": [5,6,11], "1950_03": [10,18,19], "1950_04": [3,7,23],
  "1950_05": [19,28,31], "1950_06": [9,21,25], "1950_07": [17,25,31], "1950_08": [9,20,22],
  "1950_09": [2,11,12], "1950_10": [8,19,25], "1950_11": [2,19,23], "1950_12": [8,12,24],
  "1951_01": [14,20,27], "1951_02": [7,12,15], "1951_03": [4,15,27], "1951_04": [14,19,22],
  "1951_05": [5,13,27], "1951_06": [9,23,26], "1951_07": [9,19,20], "1951_08": [3,17,20],
  "1951_09": [12,15,24], "1951_10": [6,7,9], "1951_11": [2,16,18], "1951_12": [2,14,26],
  "1952_01": [1,24,29], "1952_02": [7,20,25], "1952_03": [1,7,20], "1952_04": [7,25,26],
  "1952_05": [13,25,30], "1952_06": [5,16,24], "1952_07": [15,20,28], "1952_08": [5,7,12],
  "1952_09": [4,15,27], "1952_10": [6,26,27], "1952_11": [13,14,22], "1952_12": [4,17,27],
  "1953_01": [4,21,24], "1953_02": [3,13,26], "1953_03": [3,4,28], "1953_04": [7,21,25],
  "1953_05": [10,13,20], "1953_06": [1,17,25], "1953_07": [2,17,29], "1953_08": [3,23,26],
  "1953_09": [8,24,25], "1953_10": [4,16,18], "1953_11": [8,24,29], "1953_12": [13,20,30],
  "1954_01": [7,23,28], "1954_02": [11,16,17], "1954_03": [8,12,31], "1954_04": [22,23,30],
  "1954_05": [6,11,25], "1954_06": [5,15,26], "1954_07": [1,4,12], "1954_08": [1,15,16],
  "1954_09": [11,21,26], "1954_10": [2,11,31], "1954_11": [7,26,28], "1954_12": [6,18,22],
  "1955_01": [10,11,30], "1955_02": [7,12,25], "1955_03": [12,13,17], "1955_04": [9,13,29],
  "1955_05": [2,4,18], "1955_06": [2,9,15], "1955_07": [7,18,22], "1955_08": [5,30,31],
  "1955_09": [8,19,23], "1955_10": [13,14,25], "1955_11": [1,12,29], "1955_12": [3,25,27],
  "1956_01": [3,14,22], "1956_02": [10,11,26], "1956_03": [5,17,21], "1956_04": [12,17,25],
  "1956_05": [14,15,31], "1956_06": [13,20,29], "1956_07": [3,7,31], "1956_08": [11,16,23],
  "1956_09": [5,9,10], "1956_10": [2,5,30], "1956_11": [18,27,28], "1956_12": [5,8,21],
  "1957_01": [3,7,27], "1957_02": [3,9,25], "1957_03": [12,17,20], "1957_04": [2,6,25],
  "1957_05": [6,12,23], "1957_06": [16,23,27], "1957_07": [9,28,30], "1957_08": [1,2,15],
  "1957_09": [14,20,24], "1957_10": [6,21,28], "1957_11": [6,14,27], "1957_12": [4,8,21],
  "1958_01": [10,19,22], "1958_02": [11,24,25], "1958_03": [2,3,15], "1958_04": [4,12,27],
  "1958_05": [3,15,19], "1958_06": [10,11,19], "1958_07": [7,18,31], "1958_08": [1,14,28],
  "1958_09": [4,8,25], "1958_10": [3,11,14], "1958_11": [9,23,26], "1958_12": [8,11,14],
  "1959_01": [12,17,21], "1959_02": [4,7,18], "1959_03": [21,23,26], "1959_04": [4,8,27],
  "1959_05": [18,21,28], "1959_06": [2,11,24], "1959_07": [20,26,28], "1959_08": [5,21,29],
  "1959_09": [21,23,27], "1959_10": [8,15,28], "1959_11": [8,13,27], "1959_12": [7,27,31],
  "1960_01": [3,25,28], "1960_02": [4,6,20], "1960_03": [1,3,13], "1960_04": [4,13,24],
  "1960_05": [7,8,25], "1960_06": [2,6,20], "1960_07": [13,27,28], "1960_08": [13,19,30],
  "1960_09": [6,7,26], "1960_10": [3,4,8], "1960_11": [15,21,26], "1960_12": [4,17,29],
};

function getAvailableFullDatesForMonth(y: number, m: number): number[] {
  return DATE_FULL_DAYS[`${y}_${String(m).padStart(2, "0")}`] || [1, 15, 28];
}

function pickDateIntroFile(y: number, m: number, forceFull: boolean): { file: string; progId: string; isFull: boolean } {
  const useFull = forceFull || Math.random() < 0.7;
  const ym = `${y}_${String(m).padStart(2, "0")}`;
  if (useFull) {
    const days = getAvailableFullDatesForMonth(y, m);
    const day = days[Math.floor(Math.random() * days.length)];
    const dd = String(day).padStart(2, "0");
    return { file: `date_${ym}_${dd}.wav`, progId: `date_${ym}_${dd}`, isFull: true };
  } else {
    return { file: `date_short_${ym}.wav`, progId: `date_short_${ym}`, isFull: false };
  }
}

const DATE_INTRO_PROG: Program = {
  id: "date_intro_marker",
  year: 1949,
  file: "",
  type: "date_intro",
  volume: 0.92,
  isLoop: false,
};

const DATE_SHORTS = generateDateShorts();'''

assert old_block1 in content, "Block1 not found!"
content = content.replace(old_block1, new_block1)
print("1. Block1 (date functions) replaced")

# 2. FLOATS line
content = content.replace("...DATE_JINGLES]", "...DATE_SHORTS]")
print("2. FLOATS line updated")

# 3. lastVoiceTypeRef
content = content.replace(
    'const lastVoiceTypeRef = useRef<"news" | "life" | "poetry" | "date" | null>(null);',
    'const lastVoiceTypeRef = useRef<"news" | "life" | "poetry" | "date_intro" | "date_short" | null>(null);'
)
print("3. lastVoiceTypeRef updated")

# 4. New refs
content = content.replace(
    "const playNextRetryRef = useRef(0);",
    """const playNextRetryRef = useRef(0);
  const dateIntroSourceRef = useRef<{ source: AudioBufferSourceNode; gain: GainNode } | null>(null);
  const openingFanfareRef = useRef<{ source: AudioBufferSourceNode; gain: GainNode } | null>(null);
  const firstBootRef = useRef(true);"""
)
print("4. New refs added")

# 5. setPlaybackLevels
content = content.replace(
    'if (progType === "news" || progType === "life" || progType === "jingle" || progType === "poetry" || progType === "date") {',
    'if (progType === "news" || progType === "life" || progType === "jingle" || progType === "poetry" || progType === "date_intro" || progType === "date_short") {'
)
print("5. setPlaybackLevels updated")

# 6. enterLocked noise
content = content.replace(
    "noiseGainRef.current.gain.linearRampToValueAtTime(0.0002, t + 0.3);",
    "noiseGainRef.current.gain.linearRampToValueAtTime(0.00006, t + 0.3);"
)
print("6. enterLocked noise fixed")

# 7. Stage 2 loading
old_s2 = """    const firstDateId = `date_${y}_${String(m).padStart(2, "0")}`;
    const firstDateProg = FLOATS.find(f => f.id === firstDateId);

    if (firstProg) {
      await loadOne(firstProg, floatSourcesRef.current);
    }
    if (firstDateProg) {
      await loadOne(firstDateProg, floatSourcesRef.current);
    }"""
new_s2 = """    const firstShortId = `date_short_${y}_${String(m).padStart(2, "0")}`;
    const firstShortProg = DATE_SHORTS.find(f => f.id === firstShortId);

    if (firstProg) {
      await loadOne(firstProg, floatSourcesRef.current);
    }
    if (firstShortProg) {
      await loadOne(firstShortProg, floatSourcesRef.current);
    }"""
assert old_s2 in content, "stage2 not found!"
content = content.replace(old_s2, new_s2)
print("7. Stage2 loading updated")

# 8. alreadyLoaded
old_al = """      const alreadyLoaded = new Set([
        ...(firstProg ? [firstProg.id] : []),
        ...(firstDateProg ? [firstDateProg.id] : []),
      ]);"""
new_al = """      const alreadyLoaded = new Set([
        ...(firstProg ? [firstProg.id] : []),
        ...(firstShortProg ? [firstShortProg.id] : []),
      ]);"""
assert old_al in content, "alreadyLoaded not found!"
content = content.replace(old_al, new_al)
print("8. alreadyLoaded updated")

# 9. exitLocked cleanup
old_el = "  const exitLocked = useCallback(() => {\n    if (!isLockedRef.current) return;"
new_el = """  const exitLocked = useCallback(() => {
    if (!isLockedRef.current) return;
    if (dateIntroSourceRef.current) {
      try { dateIntroSourceRef.current.source.stop(); } catch {}
      dateIntroSourceRef.current = null;
    }
    if (openingFanfareRef.current) {
      try { openingFanfareRef.current.source.stop(); } catch {}
      openingFanfareRef.current = null;
    }"""
assert old_el in content, "exitLocked not found!"
content = content.replace(old_el, new_el)
print("9. exitLocked cleanup added")

# 10. isVoice check in playNext
content = content.replace(
    'const isVoice = prog.type === "news" || prog.type === "life" || prog.type === "poetry" || prog.type === "date";',
    'const isVoice = prog.type === "news" || prog.type === "life" || prog.type === "poetry" || prog.type === "date_intro" || prog.type === "date_short";'
)
print("10. isVoice check updated")

# 11. voiceType - replace "date" with "date_intro" in the ternary
content = content.replace(
    ': prog.type === "poetry" ? "poetry" : "date")',
    ': prog.type === "poetry" ? "poetry" : "date_intro")'
)
print("11. voiceType ternary updated")

# 12. date bgm config check
content = content.replace(
    '} else if (prog.type === "date") {',
    '} else if (prog.type === "date_intro" || prog.type === "date_short") {'
)
print("12. date bgm config check updated")

# 13. startBgm call with date
content = content.replace(
    'startBgm(prog.type === "poetry" || prog.type === "date"',
    'startBgm(prog.type === "poetry" || prog.type === "date_intro" || prog.type === "date_short"'
)
print("13. startBgm call updated")

# Now do the big replacements - find the mustPlayDate block
# Find boundaries
must_play_start = content.find("    if (mustPlayDateRef.current) {")
assert must_play_start > 0, "mustPlayDateRef block start not found"

# Find the matching closing brace - find the line with "const prog = programQueueRef.current.shift()"
prog_shift = content.find("    const prog = programQueueRef.current.shift() ?? null;")
assert prog_shift > must_play_start, "prog shift not found after mustPlayDate"

old_date_block = content[must_play_start:prog_shift]

new_date_block = '''    const dateIntroItem = programQueueRef.current.length > 0 && programQueueRef.current[0].type === "date_intro"
      ? programQueueRef.current[0] : null;

    if (mustPlayDateRef.current || dateIntroItem) {
      if (dateIntroItem) {
        programQueueRef.current.shift();
      }
      const y = Math.floor(currentYearRef.current);
      const m = yearToMonth(currentYearRef.current);
      const forceFull = firstBootRef.current || mustPlayDateRef.current;
      firstBootRef.current = false;
      const picked = pickDateIntroFile(y, m, forceFull);
      mustPlayDateRef.current = false;
      lastPlayedProgIdRef.current = picked.progId;

      const playDateVoice = (voiceBuffer: AudioBuffer) => {
        stopCurrentFloat();
        segmentTypeRef.current = "news";

        if (openingFanfareRef.current) {
          try { openingFanfareRef.current.source.stop(); } catch {}
          openingFanfareRef.current = null;
        }
        if (dateIntroSourceRef.current) {
          try { dateIntroSourceRef.current.source.stop(); } catch {}
          dateIntroSourceRef.current = null;
        }

        const fanfareBuf = bgmBuffersRef.current.get("bgm_opening_gczg") || bgmBuffersRef.current.get("bgm_opening_fanfare");
        if (fanfareBuf) {
          const fanfareGain = ctx.createGain();
          fanfareGain.gain.value = 0;
          fanfareGain.connect(masterGainRef.current!);
          const fanfareFilter = ctx.createBiquadFilter();
          fanfareFilter.type = "lowpass";
          fanfareFilter.frequency.value = 3500;
          fanfareFilter.Q.value = 0.6;
          fanfareFilter.connect(fanfareGain);
          const fanfareSrc = ctx.createBufferSource();
          fanfareSrc.buffer = fanfareBuf;
          fanfareSrc.connect(fanfareFilter);
          const td = ctx.currentTime;
          fanfareGain.gain.setValueAtTime(0, td);
          fanfareGain.gain.linearRampToValueAtTime(0.06, td + 0.3);
          fanfareSrc.start(td);
          openingFanfareRef.current = { source: fanfareSrc, gain: fanfareGain };
          fanfareSrc.onended = () => {
            if (openingFanfareRef.current?.source === fanfareSrc) {
              openingFanfareRef.current = null;
            }
          };
        }

        setPlaybackLevels("date_intro");
        startBgm({ volume: 0.025, filterFreq: 1800, filterQ: 0.5 });

        const dateFilter = ctx.createBiquadFilter();
        dateFilter.type = "bandpass";
        dateFilter.frequency.value = 2800;
        dateFilter.Q.value = 0.4;
        const dateGain = ctx.createGain();
        dateGain.gain.value = 0;
        dateFilter.connect(dateGain);
        dateGain.connect(masterGainRef.current!);
        const dateSrc = ctx.createBufferSource();
        dateSrc.buffer = voiceBuffer;
        dateSrc.connect(dateFilter);
        const voiceDelay = fanfareBuf ? 1.2 : 0.1;
        const tv = ctx.currentTime + voiceDelay;
        dateGain.gain.cancelScheduledValues(tv);
        dateGain.gain.setValueAtTime(0, tv);
        dateGain.gain.linearRampToValueAtTime(0.92, tv + 0.15);
        dateSrc.start(tv);
        dateIntroSourceRef.current = { source: dateSrc, gain: dateGain };

        dateSrc.onended = () => {
          if (dateIntroSourceRef.current?.source === dateSrc) {
            const t = ctx.currentTime;
            dateGain.gain.cancelScheduledValues(t);
            dateGain.gain.linearRampToValueAtTime(0, t + 0.2);
            setTimeout(() => {
              try { dateSrc.stop(); } catch {}
              dateIntroSourceRef.current = null;
            }, 250);
          }
          if (isLockedRef.current) {
            setTimeout(() => playNextRef.current(), GAP_BETWEEN_ITEMS_MS);
          }
        };

        if (openingFanfareRef.current) {
          const fadeTime = tv + voiceBuffer.duration - 1.5;
          if (fadeTime > ctx.currentTime) {
            openingFanfareRef.current.gain.gain.cancelScheduledValues(fadeTime);
            openingFanfareRef.current.gain.gain.linearRampToValueAtTime(0, fadeTime + 1.5);
          }
        }
      };

      if (!picked.isFull) {
        const shortId = `date_short_${y}_${String(m).padStart(2, "0")}`;
        const shortPs = floatSourcesRef.current.get(shortId);
        if (shortPs) {
          playDateVoice(shortPs.buffer);
        } else {
          loadBuffer(`/audio/programs/${picked.file}`).then(buf => playDateVoice(buf)).catch(() => {
            if (isLockedRef.current) setTimeout(() => playNextRef.current(), 100);
          });
        }
      } else {
        loadBuffer(`/audio/programs/${picked.file}`).then(buf => playDateVoice(buf)).catch(() => {
          const shortId = `date_short_${y}_${String(m).padStart(2, "0")}`;
          const shortPs = floatSourcesRef.current.get(shortId);
          if (shortPs) {
            playDateVoice(shortPs.buffer);
          } else {
            if (isLockedRef.current) setTimeout(() => playNextRef.current(), 100);
          }
        });
      }
      return;
    }

'''
content = content[:must_play_start] + new_date_block + content[prog_shift:]
print("14. date_intro playNext block replaced")

# Now find and replace buildProgramQueue
bpq_start = content.find("  const buildProgramQueue = useCallback((year: number, month: number): Program[] => {")
assert bpq_start > 0, "buildProgramQueue not found"

# Find the end: look for "  }, []);" followed by other ref declarations
# Find it by searching for the programQueueRef line
bpq_end_marker = "\n  const programQueueRef = useRef<Program[]>([]);"
bpq_end = content.find(bpq_end_marker, bpq_start)
assert bpq_end > 0, "buildProgramQueue end not found"

# Find the closing "  }, []);" before bpq_end
# Look backwards from bpq_end for the closing pattern
bpq_close = content.rfind("  }, []);", bpq_start, bpq_end)
assert bpq_close > 0, "buildProgramQueue close not found"
bpq_close_end = bpq_close + len("  }, []);")

old_bpq = content[bpq_start:bpq_close_end]

new_bpq = '''  const buildProgramQueue = useCallback((year: number, month: number): Program[] => {
    const targetYear = Math.floor(year);
    const targetMonth = Math.max(1, Math.min(12, month));
    const queue: Program[] = [];
    const added = new Set<string>();

    const tryAdd = (p: Program | null | undefined) => {
      if (p && !added.has(p.id) && isProgramAvailable(p, targetYear, targetMonth)) {
        added.add(p.id);
        queue.push(p);
        return true;
      }
      return false;
    };

    queue.push(DATE_INTRO_PROG);
    added.add(DATE_INTRO_PROG.id);

    const fillerSegments = shuffle(FLOATS.filter(f =>
      (f.type === "life" || f.type === "poetry") && isProgramAvailable(f, targetYear, targetMonth)
    ));

    const availableSongs = shuffle(FLOATS.filter(f =>
      f.type === "song" && isProgramAvailable(f, targetYear, targetMonth)
    ));

    const exactMonthNews = shuffle(FLOATS.filter(f =>
      f.type === "news" && f.year === targetYear && f.month === targetMonth && isProgramAvailable(f, targetYear, targetMonth)
    ));
    for (const n of exactMonthNews) tryAdd(n);

    const sameYearAllNewsShuffled = shuffle(FLOATS.filter(f =>
      f.type === "news" && f.year === targetYear && isProgramAvailable(f, targetYear, targetMonth)
    ));

    const allOtherNews = sameYearAllNewsShuffled.filter(n => n.month !== targetMonth);
    let songIdx = 0;

    const pickInterludeSong = (): Program | null => {
      if (songIdx < availableSongs.length - 1) {
        return availableSongs[songIdx++];
      }
      return null;
    };

    const pickEndingSong = (): Program | null => {
      if (availableSongs.length > 0) {
        for (let i = songIdx; i < availableSongs.length; i++) {
          if (!added.has(availableSongs[i].id)) return availableSongs[i];
        }
        if (!added.has(availableSongs[availableSongs.length - 1].id)) {
          return availableSongs[availableSongs.length - 1];
        }
      }
      return null;
    };

    let fillerIdx = 0;

    for (let i = 0; i < allOtherNews.length; i++) {
      tryAdd(allOtherNews[i]);
      if (i % 3 === 2 && fillerIdx < fillerSegments.length) {
        tryAdd(fillerSegments[fillerIdx++]);
      }
      if (i % 5 === 4) {
        const interludeSong = pickInterludeSong();
        if (interludeSong) tryAdd(interludeSong);
      }
    }

    while (fillerIdx < fillerSegments.length && queue.length < 25) {
      tryAdd(fillerSegments[fillerIdx++]);
    }

    const lastItem = queue[queue.length - 1];
    if (!lastItem || lastItem.type !== "song") {
      const endingSong = pickEndingSong();
      if (endingSong) tryAdd(endingSong);
    }

    return queue;
  }, []);'''

content = content[:bpq_start] + new_bpq + content[bpq_close_end:]
print("15. buildProgramQueue replaced")

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ All modifications written to file!")
