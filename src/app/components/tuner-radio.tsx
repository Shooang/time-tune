import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import {
  motion, MotionValue,
  useMotionValue, useMotionValueEvent, useSpring, useTransform, useVelocity, animate,
} from "motion/react";
import { Signal, Wifi, BatteryFull, MoreHorizontal } from "lucide-react";

/* ============================================================
   CONSTANTS
   ============================================================ */
const MIN_TIME = 1949;
const MAX_TIME = 1960.999;
const INITIAL_TIME = 1955;

const PX_PER_YEAR    = 680;
const SVG_START_YEAR = 1947;
const SVG_END_YEAR   = 1962;
const SVG_TOTAL_W    = (SVG_END_YEAR - SVG_START_YEAR + 1) * PX_PER_YEAR;

const DAMPING_RATIO   = 0.8;
const ROTATION_FACTOR = 2.0;
const PTR_W   = 5;
const PTR_PAD = 14;
const EDGE_INSET = 60;
const OVERSHOOT_MAX = 45;
const RUBBER_K = 0.55;
const RUBBER_FOLLOW = 0.2;

const FADE_MIN = 40;
const FADE_MAX = 90;
const FADE_RATIO = 0.18;

const MONTH_FONT_SIZE = 18;

const YEAR_JOLT_DISTANCE = 3;

const MONTH_EPS = 1e-8; // 补偿IEEE 754浮点精度误差（1/12*12会得到0.999...而非1.0）
function yearToMonth(yearFloat: number): number {
  const y = Math.floor(yearFloat);
  return Math.max(1, Math.min(12, Math.floor((yearFloat - y) * 12 + MONTH_EPS) + 1));
}
function yearToMonthIdx(yearFloat: number): number {
  return Math.floor((yearFloat - Math.floor(yearFloat)) * 12 + MONTH_EPS);
}

function rubberBand(dist: number, dim: number): number {
  const c = dim * RUBBER_K;
  const overshootPx = dist * dim;
  const rubbered = (1 - 1 / (overshootPx / c + 1)) * OVERSHOOT_MAX;
  return Math.min(rubbered, OVERSHOOT_MAX);
}

const GAIN_MIN = 0.0010;
const GAIN_MAX = 0.075;
const OMEGA_SLOW = 50;
const OMEGA_FAST = 1300;
const GAIN_GAMMA = 2.3;
const EMA_ALPHA = 0.22;
const EDGE_BAND = 2.0;
const DEAD_ZONE = 0.3;

const GRID_ROWS = "minmax(36px, 4fr) minmax(110px, 30fr) minmax(4px, 3fr) minmax(60px, 14fr) minmax(140px, 49fr)";

/* ============================================================
   DARK THEME (Deep charcoal skeuomorphic radio aesthetic)
   ============================================================ */
const THEME = {
  bg: {
    gradient: "linear-gradient(180deg,#28282c 0%,#1e1e22 50%,#18181c 100%)",
    noiseOpacity: 0.09,
  },
  statusBar: {
    iconColor: "#8a8a94",
    buttonBg: "linear-gradient(#36363c,#28282c)",
    buttonShadow: "inset 0 1px 2px rgba(255,255,255,0.10),0 1px 3px rgba(0,0,0,0.6)",
  },
  speaker: {
    panelBg: "radial-gradient(ellipse 100% 80% at 50% 30%, #36363c 0%, #2c2c32 40%, #222228 100%)",
    panelShadow: "inset 0 4px 14px rgba(0,0,0,0.7), inset 0 -1px 2px rgba(255,255,255,0.05), 0 1px 0 rgba(255,255,255,0.07), inset 0 1px 0 rgba(0,0,0,0.25)",
    darkHoleFill: "#09090c",
    holeShadeFill: "rgba(0,0,0,0.6)",
    highlightRingStroke: "rgba(120,120,130,0.10)",
    bulbCoreFill: "#ffc045",
    holeRadius: 2.1,
    holeSpacing: 13.5,
  },
  display: {
    frameBg: "linear-gradient(180deg,#3e3e46 0%,#2a2a30 40%,#1e1e24 100%)",
    frameShadow: "0 2px 3px rgba(0,0,0,0.7), inset 0 1px 3px rgba(0,0,0,0.6), inset 0 -1px 1px rgba(255,255,255,0.08)",
    glassOffBg: "radial-gradient(130% 90% at 50% 20%, #282830 0%, #1c1c22 45%, #101014 100%)",
    glassOnBg: "radial-gradient(130% 90% at 50% 20%, #8b6914 0%, #6a4c10 40%, #3d2a08 100%)",
    glassOffShadow: "inset 0 0 28px rgba(0,0,0,0.88), inset 0 1px 0 rgba(255,255,255,0.04)",
    glassOnShadow: "inset 0 0 40px rgba(255,160,40,0.7)",
    glassTopHighlight: "linear-gradient(165deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.015) 40%, transparent 60%)",
    offStateWarmReflection: "radial-gradient(65% 55% at 50% 25%, rgba(180,140,60,0.12), transparent 70%)",
    onStateCenterGlow: "radial-gradient(65% 55% at 50% 25%, rgba(255,200,80,0.9), rgba(255,160,40,0.5) 40%, rgba(255,120,20,0.2) 70%, transparent 100%)",
    powerFlashMask: "radial-gradient(70% 60% at 50% 20%, rgba(40,40,50,0.6), rgba(28,28,35,0.3) 40%, transparent 70%)",
    tickStroke: "rgba(180,180,200,0.30)",
    yearTickFill: "#e0e0ec",
    quarterTickFill: "rgba(220,220,235,0.75)",
    monthTickFill: "rgba(200,200,215,0.55)",
    pointerShadowEllipse: "rgba(0,0,0,0.5)",
    yearDiamondFill: "#e0e0ec",
    yearDiamondOpacity: 0.85,
    yearLabelFill: "#e8e8f0",
    monthLabelFill: "rgba(232,232,240,0.85)",
    topHighlightBar: "linear-gradient(158deg,rgba(255,255,255,0.06) 0%,rgba(255,255,255,0.015) 38%,transparent 58%)",
    vignette: {
      off: {
        edge: "rgba(6,6,10,0.95)",
        mid: "rgba(10,10,14,0.72)",
        soft: "rgba(14,14,18,0.32)",
        hint: "rgba(18,18,22,0.13)",
        topEdge: "rgba(6,6,10,0.48)",
        bottomEdge: "rgba(6,6,10,0.55)",
      },
      warming: {
        edge: "rgba(35,25,8,0.92)",
        mid: "rgba(50,35,10,0.60)",
        soft: "rgba(65,45,12,0.25)",
        hint: "rgba(75,50,14,0.10)",
        topEdge: "rgba(30,22,6,0.38)",
        bottomEdge: "rgba(26,18,5,0.42)",
      },
      on: {
        edge: "rgba(25,18,5,0.90)",
        mid: "rgba(40,28,8,0.48)",
        soft: "rgba(50,35,10,0.18)",
        hint: "rgba(60,42,12,0.07)",
        topEdge: "rgba(26,18,5,0.32)",
        bottomEdge: "rgba(22,15,4,0.38)",
      },
    },
  },
  pointer: {
    gradient: "linear-gradient(180deg,#ff6050 0%,#e01810 35%,#b00808 75%,#700505 100%)",
    shadow: "0 0 18px rgba(255,40,20,0.95),0 0 34px rgba(255,60,20,0.45),inset 1px 0 0 rgba(255,180,160,0.5),inset -1px 0 0 rgba(0,0,0,0.5)",
    arrowBorderBottom: "#e81810",
    arrowFilter: "drop-shadow(0 -1px 3px rgba(255,40,20,0.7))",
  },
  knob: {
    socketBg: "radial-gradient(circle at 50% 50%, #121216 0%, #0a0a0e 70%, #060608 100%)",
    socketShadow: `
      inset 0 4px 10px rgba(0,0,0,0.85),
      inset 0 -2px 4px rgba(255,255,255,0.03),
      inset 2px 0 6px rgba(0,0,0,0.4),
      inset -2px 0 6px rgba(0,0,0,0.4),
      0 1px 1px rgba(255,255,255,0.05)
    `,
    socketInset: "9%",
    bezelGradient: "linear-gradient(180deg,#2e2e36 0%,#24242a 40%,#1a1a20 100%)",
    bezelShadow: `
      inset 0 2px 3px rgba(0,0,0,0.7),
      inset 0 -1px 2px rgba(255,255,255,0.05),
      0 1px 2px rgba(0,0,0,0.4)
    `,
    bezelInset: "16%",
    tickColor: "rgba(140,140,155,0.35)",
    tickMajorColor: "rgba(160,160,175,0.50)",
    faceGradient: `
      radial-gradient(circle at 50% 38%,#484850 0%,
      #3e3e46 15%,#34343c 30%,
      #2a2a32 50%,#22222a 72%,
      #1c1c24 90%,#16161c 100%)
    `,
    faceShadow: `
      inset 0 2px 4px rgba(255,255,255,0.06),
      inset 0 -3px 8px rgba(0,0,0,0.5),
      inset 3px 0 5px rgba(0,0,0,0.15),
      inset -3px 0 5px rgba(0,0,0,0.15)
    `,
    faceInset: "20%",
    indicatorColor: "rgba(200,200,215,0.75)",
    indicatorGlow: "0 0 4px rgba(200,200,220,0.4)",
    grainOverlay: `
      radial-gradient(circle at 25% 20%, rgba(255,255,255,0.015) 0%, transparent 4%),
      radial-gradient(circle at 75% 30%, rgba(0,0,0,0.04) 0%, transparent 4%),
      radial-gradient(circle at 30% 70%, rgba(0,0,0,0.03) 0%, transparent 5%),
      radial-gradient(circle at 80% 75%, rgba(255,255,255,0.01) 0%, transparent 4%),
      radial-gradient(circle at 50% 50%, rgba(0,0,0,0.02) 0%, transparent 8%)
    `,
    mainHighlight: "radial-gradient(ellipse 60% 35% at 30% 18%, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.025) 30%, transparent 65%)",
    edgeHighlight: `
      radial-gradient(ellipse 50% 20% at 50% 2%, rgba(255,255,255,0.04) 0%, transparent 70%),
      radial-gradient(ellipse 30% 50% at 2% 50%, rgba(255,255,255,0.02) 0%, transparent 70%),
      radial-gradient(ellipse 30% 50% at 98% 50%, rgba(0,0,0,0.1) 0%, transparent 70%),
      radial-gradient(ellipse 50% 20% at 50% 98%, rgba(0,0,0,0.12) 0%, transparent 70%)
    `,
    edgeRingShadow: `inset 0 0 0 1px rgba(255,255,255,0.04)`,
    introPulseBorder: "3px solid rgba(255,180,60,0.3)",
  },
  event: {
    red: "#d84828",
  },
};

/* ============================================================
   DOT-MATRIX FONT (5×7 LED style for year display in speaker grille)
   ============================================================ */
const DOT_FONT: Record<string, number[][]> = {
  "0": [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,1,1],[1,0,1,0,1],[1,1,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
  "1": [[0,0,1,1,0],[0,1,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,1,1,1,0]],
  "2": [[0,1,1,1,0],[1,0,0,0,1],[0,0,0,0,1],[0,0,0,1,0],[0,0,1,0,0],[0,1,0,0,0],[1,1,1,1,1]],
  "3": [[1,1,1,1,0],[0,0,0,0,1],[0,0,0,0,1],[0,1,1,1,0],[0,0,0,0,1],[0,0,0,0,1],[1,1,1,1,0]],
  "4": [[0,0,0,1,0],[0,0,1,1,0],[0,1,0,1,0],[1,0,0,1,0],[1,1,1,1,1],[0,0,0,1,0],[0,0,0,1,0]],
  "5": [[1,1,1,1,1],[1,0,0,0,0],[1,1,1,1,0],[0,0,0,0,1],[0,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
  "6": [[0,0,1,1,0],[0,1,0,0,0],[1,0,0,0,0],[1,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
  "7": [[1,1,1,1,1],[0,0,0,0,1],[0,0,0,1,0],[0,0,1,0,0],[0,1,0,0,0],[0,1,0,0,0],[0,1,0,0,0]],
  "8": [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,0]],
  "9": [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[0,1,1,1,1],[0,0,0,0,1],[0,0,0,1,0],[0,1,1,0,0]],
};
const DOT_COLS = 5;
const DOT_ROWS = 7;
const NUM_DIGITS = 4;
const TOTAL_DOT_COLS = NUM_DIGITS * DOT_COLS + (NUM_DIGITS - 1);

const BASE_SPEAKER_W = 327;
const BASE_HOLE_SPACING = 13.5;
const BASE_DARK_HOLE_R = 2.1;
const BASE_HIGHLIGHT_R = 2.1;
const BASE_GRID_OFF_X = 0;
const BASE_GRID_OFF_Y = 0.32;

/* ============================================================
   TIMELINE DATA
   ============================================================ */
export interface TimelineEvent {
  id: string; year: number; month: number;
  title: string; description?: string; color?: string;
}
export type TickType = "year" | "quarter" | "month";
export interface ScaleTick {
  x: number; type: TickType; year: number; month: number;
  yearLabel?: string; events: TimelineEvent[];
}

const TIMELINE_EVENTS: TimelineEvent[] = [
  { id: "evt_1949_10_01", year: 1949, month: 10, title: "中华人民共和国成立", color: "#d84828" },
  { id: "evt_1950_06_25", year: 1950, month: 6, title: "朝鲜战争爆发" },
  { id: "evt_1950_10_19", year: 1950, month: 10, title: "志愿军跨过鸭绿江", color: "#d84828" },
  { id: "evt_1951_05_23", year: 1951, month: 5, title: "西藏和平解放" },
  { id: "evt_1951_12_01", year: 1951, month: 12, title: "三反运动开始" },
  { id: "evt_1952_01_01", year: 1952, month: 1, title: "五反运动开始" },
  { id: "evt_1952_07_01", year: 1952, month: 7, title: "成渝铁路通车" },
  { id: "evt_1952_10_14", year: 1952, month: 10, title: "上甘岭战役" },
  { id: "evt_1953_07_27", year: 1953, month: 7, title: "朝鲜停战协定签订", color: "#d84828" },
  { id: "evt_1953_10_01", year: 1953, month: 10, title: "第一个五年计划开始" },
  { id: "evt_1953_12_31", year: 1953, month: 12, title: "和平共处五项原则" },
  { id: "evt_1954_04_26", year: 1954, month: 4, title: "日内瓦会议召开" },
  { id: "evt_1954_09_15", year: 1954, month: 9, title: "第一届全国人大召开", color: "#d84828" },
  { id: "evt_1954_12_25", year: 1954, month: 12, title: "康藏、青藏公路通车" },
  { id: "evt_1955_04_18", year: 1955, month: 4, title: "万隆会议召开" },
  { id: "evt_1955_09_27", year: 1955, month: 9, title: "十大元帅授衔" },
  { id: "evt_1955_10_01", year: 1955, month: 10, title: "新疆维吾尔自治区成立" },
  { id: "evt_1956_07_13", year: 1956, month: 7, title: "长春一汽解放牌汽车下线", color: "#d84828" },
  { id: "evt_1956_09_15", year: 1956, month: 9, title: "中共八大召开" },
  { id: "evt_1957_02_27", year: 1957, month: 2, title: "正确处理人民内部矛盾" },
  { id: "evt_1957_10_15", year: 1957, month: 10, title: "武汉长江大桥通车", color: "#d84828" },
  { id: "evt_1958_05_05", year: 1958, month: 5, title: "八大二次会议召开" },
  { id: "evt_1958_08_17", year: 1958, month: 8, title: "大跃进运动", color: "#d84828" },
  { id: "evt_1958_09_02", year: 1958, month: 9, title: "北京电视台正式开播" },
  { id: "evt_1959_03_10", year: 1959, month: 3, title: "西藏平叛" },
  { id: "evt_1959_04_05", year: 1959, month: 4, title: "容国团获世乒赛冠军", color: "#d84828" },
  { id: "evt_1959_09_13", year: 1959, month: 9, title: "第一届全运会召开" },
  { id: "evt_1959_10_01", year: 1959, month: 10, title: "建国十周年" },
  { id: "evt_1959_11_01", year: 1959, month: 11, title: "第一拖拉机厂建成投产" },
  { id: "evt_1960_02_20", year: 1960, month: 2, title: "大庆石油会战开始" },
  { id: "evt_1960_05_25", year: 1960, month: 5, title: "中国登山队登上珠峰", color: "#d84828" },
  { id: "evt_1960_11_03", year: 1960, month: 11, title: "纠正农村工作中左倾错误" },
];

const BIWEEKLY_X: number[] = (() => {
  const xs: number[] = [];
  for (let x = 7; x < SVG_TOTAL_W; x += 14) xs.push(x);
  return xs;
})();

const SCALE_TICKS: ScaleTick[] = (() => {
  const ticks: ScaleTick[] = [];
  for (let y = SVG_START_YEAR; y <= SVG_END_YEAR; y++) {
    for (let m = 1; m <= 12; m++) {
      const x = (y + (m - 1) / 12 - SVG_START_YEAR) * PX_PER_YEAR;
      const type: TickType =
        m === 1 ? "year" : m === 4 || m === 7 || m === 10 ? "quarter" : "month";
      ticks.push({
        x, type, year: y, month: m,
        yearLabel: m === 1 ? String(y) : undefined,
        events: TIMELINE_EVENTS.filter(e => e.year === y && e.month === m),
      });
    }
  }
  return ticks;
})();

/* ============================================================
   useCellSize
   ============================================================ */
function useCellSize(initial = { w: 320, h: 100 }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect;
      setSize({ w: width, h: height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, size };
}

/* ============================================================
   AUDIO PROGRAM DEFINITIONS
   ============================================================ */
interface Program {
  id: string;
  year: number;
  month?: number;
  startMonth?: number;
  file: string;
  type: "song" | "jingle" | "news" | "life" | "id" | "poetry" | "weather" | "date_intro" | "date_short" | "greeting";
  volume: number;
  isLoop: boolean;
  category?: "epic" | "military" | "construction" | "lyrical";
}

const BGM_TRACKS = [
  { id: "bgm_opening_dfh", file: "bgm/opening_dongfanghong.wav" },
  { id: "bgm_opening_gczg", file: "bgm/opening_gechangzuguoo.wav" },
  { id: "bgm_opening_gczg_brass", file: "bgm/opening_gczg_brass.wav" },
];

const SONG_BGM_TRACKS = [
  { id: "bgm_gczg_inst", file: "songs/bgm_gechangzuguoo_inst.mp3", tags: ["建国", "庆典", "爱国"] },
  { id: "bgm_mygcd_inst", file: "songs/bgm_meiyougongchandang_inst.mp3", tags: ["建党", "建国", "爱国"] },
  { id: "bgm_dashuai_inst", file: "songs/bgm_dashuailianbing_inst.mp3", tags: ["军事", "军队"] },
];

function isProgramAvailable(prog: Program, targetYear: number, targetMonth: number): boolean {
  if (prog.year > targetYear) return false;
  if (prog.year === targetYear && prog.startMonth !== undefined && targetMonth < prog.startMonth) return false;
  return true;
}

function generateMonthlyNewsPrograms(): Program[] {
  const programs: Program[] = [];
  for (let y = 1949; y <= 1960; y++) {
    for (let m = 1; m <= 12; m++) {
      for (let n = 1; n <= 8; n++) {
        programs.push({
          id: `news_${y}_${String(m).padStart(2, "0")}_${String(n).padStart(2, "0")}`,
          year: y,
          month: m,
          file: `news_${y}_${String(m).padStart(2, "0")}_${String(n).padStart(2, "0")}.m4a`,
          type: "news",
          volume: 0.92,
          isLoop: false,
        });
      }
    }
  }
  return programs;
}

function generateDateShorts(): Program[] {
  const programs: Program[] = [];
  for (let y = 1949; y <= 1960; y++) {
    for (let m = 1; m <= 12; m++) {
      programs.push({
        id: `date_short_${y}_${String(m).padStart(2, "0")}`,
        year: y,
        month: m,
        file: `date_short_${y}_${String(m).padStart(2, "0")}.m4a`,
        type: "date_short",
        volume: 0.92,
        isLoop: false,
      });
    }
  }
  return programs;
}

const DATE_FULL_DAYS: Record<string, number[]> = {
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
    return { file: `date_${ym}_${dd}.m4a`, progId: `date_${ym}_${dd}`, isFull: true };
  } else {
    return { file: `date_short_${ym}.m4a`, progId: `date_short_${ym}`, isFull: false };
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

const GREETINGS: Program[] = (() => {
  const periods = ["dawn", "morning", "forenoon", "noon", "afternoon", "evening", "night"];
  const eras: Array<{ key: string; startYear: number; endYear: number }> = [
    { key: "early", startYear: 1949, endYear: 1952 },
    { key: "mid", startYear: 1953, endYear: 1957 },
    { key: "late", startYear: 1958, endYear: 1960 },
  ];
  const list: Program[] = [];
  for (const era of eras) {
    for (const p of periods) {
      for (let i = 1; i <= 4; i++) {
        list.push({
          id: `greet_${era.key}_${p}_${String(i).padStart(2, "0")}`,
          year: era.startYear,
          file: `greet_${era.key}_${p}_${String(i).padStart(2, "0")}.m4a`,
          type: "greeting",
          volume: 0.92,
          isLoop: false,
        });
      }
    }
  }
  return list;
})();

function getCurrentPeriod(): string {
  const hour = new Date().getHours();
  if (hour < 5) return "dawn";
  if (hour < 8) return "morning";
  if (hour < 11) return "forenoon";
  if (hour < 13) return "noon";
  if (hour < 17) return "afternoon";
  if (hour < 21) return "evening";
  return "night";
}

function getEraForYear(year: number): string {
  if (year <= 1952) return "early";
  if (year <= 1957) return "mid";
  return "late";
}

function pickGreetingFile(year: number): string {
  const period = getCurrentPeriod();
  const era = getEraForYear(Math.floor(year));
  const v = 1 + Math.floor(Math.random() * 4);
  return `greet_${era}_${period}_${String(v).padStart(2, "0")}.m4a`;
}

const DATE_SHORTS = generateDateShorts();

interface PoetryItem {
  id: string;
  title: string;
  year: number;
  category: "epic" | "military" | "construction" | "lyrical";
  text: string;
}

const POETRY_LIBRARY: PoetryItem[] = [
  { id: "poem_qinyuanchun_xue", title: "沁园春·雪", year: 1945, category: "epic", text: "北国风光，千里冰封，万里雪飘。望长城内外，惟余莽莽；大河上下，顿失滔滔。山舞银蛇，原驰蜡象，欲与天公试比高。须晴日，看红装素裹，分外妖娆。江山如此多娇，引无数英雄竞折腰。惜秦皇汉武，略输文采；唐宗宋祖，稍逊风骚。一代天骄，成吉思汗，只识弯弓射大雕。俱往矣，数风流人物，还看今朝。" },
  { id: "poem_qilu_changzheng", title: "七律·长征", year: 1937, category: "epic", text: "红军不怕远征难，万水千山只等闲。五岭逶迤腾细浪，乌蒙磅礴走泥丸。金沙水拍云崖暖，大渡桥横铁索寒。更喜岷山千里雪，三军过后尽开颜。" },
  { id: "poem_qinyuanchun_changsha", title: "沁园春·长沙", year: 1925, category: "epic", text: "独立寒秋，湘江北去，橘子洲头。看万山红遍，层林尽染；漫江碧透，百舸争流。鹰击长空，鱼翔浅底，万类霜天竞自由。怅寥廓，问苍茫大地，谁主沉浮？携来百侣曾游，忆往昔峥嵘岁月稠。恰同学少年，风华正茂；书生意气，挥斥方遒。指点江山，激扬文字，粪土当年万户侯。曾记否，到中流击水，浪遏飞舟？" },
  { id: "poem_yiqine_loushanguan", title: "忆秦娥·娄山关", year: 1935, category: "military", text: "西风烈，长空雁叫霜晨月。霜晨月，马蹄声碎，喇叭声咽。雄关漫道真如铁，而今迈步从头越。从头越，苍山如海，残阳如血。" },
  { id: "poem_qilu_nanjing", title: "七律·人民解放军占领南京", year: 1949, category: "epic", text: "钟山风雨起苍黄，百万雄师过大江。虎踞龙盘今胜昔，天翻地覆慨而慷。宜将剩勇追穷寇，不可沽名学霸王。天若有情天亦老，人间正道是沧桑。" },
  { id: "poem_langtaosha_beidaihe", title: "浪淘沙·北戴河", year: 1954, category: "construction", text: "大雨落幽燕，白浪滔天，秦皇岛外打鱼船。一片汪洋都不见，知向谁边？往事越千年，魏武挥鞭，东临碣石有遗篇。萧瑟秋风今又是，换了人间。" },
  { id: "poem_shuidiaoge_youyong", title: "水调歌头·游泳", year: 1956, category: "construction", text: "才饮长沙水，又食武昌鱼。万里长江横渡，极目楚天舒。不管风吹浪打，胜似闲庭信步，今日得宽馀。子在川上曰：逝者如斯夫！风樯动，龟蛇静，起宏图。一桥飞架南北，天堑变通途。更立西江石壁，截断巫山云雨，高峡出平湖。神女应无恙，当惊世界殊。" },
  { id: "poem_dielianhua_dalishuyi", title: "蝶恋花·答李淑一", year: 1957, category: "lyrical", text: "我失骄杨君失柳，杨柳轻飏直上重霄九。问讯吴刚何所有，吴刚捧出桂花酒。寂寞嫦娥舒广袖，万里长空且为忠魂舞。忽报人间曾伏虎，泪飞顿作倾盆雨。" },
  { id: "poem_qilu_songwenshen", title: "七律二首·送瘟神（其一）", year: 1958, category: "construction", text: "绿水青山枉自多，华佗无奈小虫何！千村薜荔人遗矢，万户萧疏鬼唱歌。坐地日行八万里，巡天遥看一千河。牛郎欲问瘟神事，一样悲欢逐逝波。" },
  { id: "poem_qilu_songwenshen2", title: "七律二首·送瘟神（其二）", year: 1958, category: "construction", text: "春风杨柳万千条，六亿神州尽舜尧。红雨随心翻作浪，青山着意化为桥。天连五岭银锄落，地动三河铁臂摇。借问瘟君欲何往，纸船明烛照天烧。" },
  { id: "poem_busuanzi_yongmei", title: "卜算子·咏梅", year: 1960, category: "lyrical", text: "风雨送春归，飞雪迎春到。已是悬崖百丈冰，犹有花枝俏。俏也不争春，只把春来报。待到山花烂漫时，她在丛中笑。" },
  { id: "poem_qilu_daoshaoshan", title: "七律·到韶山", year: 1959, category: "construction", text: "别梦依稀咒逝川，故园三十二年前。红旗卷起农奴戟，黑手高悬霸主鞭。为有牺牲多壮志，敢教日月换新天。喜看稻菽千重浪，遍地英雄下夕烟。" },
];

function generatePoetryPrograms(): Program[] {
  return POETRY_LIBRARY.map(p => ({
    id: p.id,
    year: Math.min(1960, Math.max(1949, p.year)),
    file: `${p.id}.m4a`,
    type: "poetry" as const,
    category: p.category,
    volume: 0.85,
    isLoop: false,
  }));
}

function generateMonthlyLifePrograms(): Program[] {
  const programs: Program[] = [];
  for (let y = 1949; y <= 1960; y++) {
    for (let m = 1; m <= 12; m++) {
      programs.push({
        id: `life_${y}_${String(m).padStart(2, "0")}`,
        year: y,
        month: m,
        file: `life_${y}_${String(m).padStart(2, "0")}.m4a`,
        type: "life",
        volume: 0.72,
        isLoop: false,
      });
    }
  }
  return programs;
}

function generateWeatherPrograms(): Program[] {
  const programs: Program[] = [];
  for (let y = 1949; y <= 1960; y++) {
    for (let m = 1; m <= 12; m++) {
      for (let v = 1; v <= 3; v++) {
        programs.push({
          id: `weather_${y}_${String(m).padStart(2, "0")}_${v}`,
          year: y,
          month: m,
          file: `weather_${y}_${String(m).padStart(2, "0")}_${v}.m4a`,
          type: "weather",
          volume: 0.80,
          isLoop: false,
        });
      }
    }
  }
  return programs;
}

const STATION_IDS: Program[] = [
  { id: "id_001", year: 1950, file: "id_001.m4a", type: "id", volume: 0.92, isLoop: false },
  { id: "id_002", year: 1955, file: "id_002.m4a", type: "id", volume: 0.92, isLoop: false },
  { id: "id_003", year: 1958, file: "id_003.m4a", type: "id", volume: 0.92, isLoop: false },
  { id: "id_004", year: 1960, file: "id_004.m4a", type: "id", volume: 0.92, isLoop: false },
  { id: "id_007", year: 1950, file: "id_007.m4a", type: "id", volume: 0.92, isLoop: false },
  { id: "id_005", year: 1960, file: "id_005.m4a", type: "id", volume: 0.92, isLoop: false },
  { id: "id_006", year: 1960, file: "id_006.m4a", type: "id", volume: 0.92, isLoop: false },
  { id: "id_008", year: 1960, file: "id_008.m4a", type: "id", volume: 0.92, isLoop: false },
];

const JINGLES: Program[] = [
  { id: "jingle_001", year: 1950, file: "jingle_001.m4a", type: "jingle", volume: 0.88, isLoop: false },
  { id: "jingle_004", year: 1955, file: "jingle_004.m4a", type: "jingle", volume: 0.88, isLoop: false },
  { id: "jingle_002", year: 1960, file: "jingle_002.m4a", type: "jingle", volume: 0.88, isLoop: false },
  { id: "jingle_003", year: 1960, file: "jingle_003.m4a", type: "jingle", volume: 0.88, isLoop: false },
];

const KEY_NEWS: Program[] = [
  { id: "news_1949_10_06", year: 1949, month: 10, file: "news_1949_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1950_06_06", year: 1950, month: 6, file: "news_1950_06_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1950_10_06", year: 1950, month: 10, file: "news_1950_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1950_11_06", year: 1950, month: 11, file: "news_1950_11_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1951_05_06", year: 1951, month: 5, file: "news_1951_05_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1951_10_06", year: 1951, month: 10, file: "news_1951_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1952_01_06", year: 1952, month: 1, file: "news_1952_01_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1952_07_06", year: 1952, month: 7, file: "news_1952_07_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1952_10_06", year: 1952, month: 10, file: "news_1952_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1953_07_06", year: 1953, month: 7, file: "news_1953_07_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1953_12_06", year: 1953, month: 12, file: "news_1953_12_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1954_09_06", year: 1954, month: 9, file: "news_1954_09_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1954_12_06", year: 1954, month: 12, file: "news_1954_12_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1955_04_06", year: 1955, month: 4, file: "news_1955_04_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1955_09_06", year: 1955, month: 9, file: "news_1955_09_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1955_10_06", year: 1955, month: 10, file: "news_1955_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1956_01_06", year: 1956, month: 1, file: "news_1956_01_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1956_07_06", year: 1956, month: 7, file: "news_1956_07_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1956_09_06", year: 1956, month: 9, file: "news_1956_09_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1956_12_06", year: 1956, month: 12, file: "news_1956_12_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1957_04_06", year: 1957, month: 4, file: "news_1957_04_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1957_10_06", year: 1957, month: 10, file: "news_1957_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1957_11_06", year: 1957, month: 11, file: "news_1957_11_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1958_05_06", year: 1958, month: 5, file: "news_1958_05_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1958_08_06", year: 1958, month: 8, file: "news_1958_08_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1958_10_06", year: 1958, month: 10, file: "news_1958_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1959_04_06", year: 1959, month: 4, file: "news_1959_04_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1959_09_06", year: 1959, month: 9, file: "news_1959_09_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1959_10_06", year: 1959, month: 10, file: "news_1959_10_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1959_10_07", year: 1959, month: 10, file: "news_1959_10_07.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1960_02_06", year: 1960, month: 2, file: "news_1960_02_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1960_04_06", year: 1960, month: 4, file: "news_1960_04_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1960_05_06", year: 1960, month: 5, file: "news_1960_05_06.m4a", type: "news", volume: 0.92, isLoop: false },
  { id: "news_1960_11_06", year: 1960, month: 11, file: "news_1960_11_06.m4a", type: "news", volume: 0.92, isLoop: false },
];

const SONGS: Program[] = [
  { id: "song_001", year: 1950, startMonth: 10, file: "song_001.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_002", year: 1951, file: "song_002.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_003", year: 1957, file: "song_003.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_004", year: 1960, file: "song_004.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_005", year: 1953, file: "song_005.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_006", year: 1955, file: "song_006.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_007", year: 1960, file: "song_007.m4a", type: "song", volume: 0.55, isLoop: false },
  { id: "song_008", year: 1960, file: "song_008.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_009", year: 1958, file: "song_009.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_010", year: 1956, file: "song_010.m4a", type: "song", volume: 0.60, isLoop: false },
  { id: "song_dongfanghong", year: 1949, file: "songs/song_dongfanghong.mp3", type: "song", volume: 0.55, isLoop: false },
  { id: "song_gczg_1951", year: 1949, month: 10, file: "songs/song_gechangzuguoo_1951.mp3", type: "song", volume: 0.55, isLoop: false },
  { id: "song_sandajilv", year: 1949, file: "songs/song_sandajilv.mp3", type: "song", volume: 0.55, isLoop: false },
  { id: "song_zhiyuanjun", year: 1950, startMonth: 6, file: "songs/song_zhiyuanjun.mp3", type: "song", volume: 0.60, isLoop: false },
  { id: "song_kangmei", year: 1950, startMonth: 10, file: "songs/song_kangmeiyuanchao.mp3", type: "song", volume: 0.55, isLoop: false },
  { id: "song_shehuizhuyi", year: 1957, file: "songs/song_shehuizhuyihao.mp3", type: "song", volume: 0.55, isLoop: false },
  { id: "song_nanniwan", year: 1950, file: "songs/song_nanniwan.mp3", type: "song", volume: 0.50, isLoop: false },
  { id: "song_womenzouzai", year: 1958, file: "songs/song_womenzouzai.mp3", type: "song", volume: 0.55, isLoop: false },
  { id: "song_shisonghongjun", year: 1955, file: "songs/song_shisonghongjun.mp3", type: "song", volume: 0.50, isLoop: false },
];

const OTHER_FLOATS: Program[] = [...SONGS, ...STATION_IDS, ...JINGLES, ...KEY_NEWS];

const FLOATS: Program[] = [...generateMonthlyNewsPrograms(), ...generatePoetryPrograms(), ...generateMonthlyLifePrograms(), ...generateWeatherPrograms(), ...OTHER_FLOATS, ...GREETINGS, ...DATE_SHORTS];

const ALL_PROGRAMS = [...FLOATS];

interface ProgramSource {
  buffer: AudioBuffer;
  source: AudioBufferSourceNode | null;
  gain: GainNode;
  filter: BiquadFilterNode;
  started: boolean;
}

function useRadioAudio() {
  const ctxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const noiseBufRef = useRef<AudioBuffer | null>(null);
  const noiseSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const noiseGainRef = useRef<GainNode | null>(null);
  const noiseFilterRef = useRef<BiquadFilterNode | null>(null);
  const noiseLPRef = useRef<BiquadFilterNode | null>(null);
  const bgmBuffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const bgmSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const bgmGainRef = useRef<GainNode | null>(null);
  const bgmFilterRef = useRef<BiquadFilterNode | null>(null);
  const bgmPlayingRef = useRef(false);
  const floatSourcesRef = useRef<Map<string, ProgramSource>>(new Map());
  const failedLoadsRef = useRef<Set<string>>(new Set());
  const isReadyRef = useRef(false);
  const isPoweredOnRef = useRef(false);
  const lastMoveTimeRef = useRef(0);
  const currentPlayingRef = useRef<{ prog: Program; source: AudioBufferSourceNode } | null>(null);
  const isTuningRef = useRef(false);
  const isLockedRef = useRef(false);
  const lockedYearRef = useRef(0);
  const lockedMonthRef = useRef(0);
  const currentYearRef = useRef(1955);
  const segmentTypeRef = useRef<"news" | "music" | "filler" | null>(null);
  const noiseLockTimerRef = useRef<number | null>(null);
  const currentLoopRef = useRef(false);
  const lastOpenPatternRef = useRef<string>("");
  const lastPlayedProgIdRef = useRef<string>("");
  const currentBgmIdRef = useRef<string | null>(null);
  const lastVoiceTypeRef = useRef<"news" | "life" | "poetry" | "weather" | "date_intro" | "date_short" | null>(null);
  const pendingEnterLockedRef = useRef(false);
  const mustPlayDateRef = useRef(false);
  const playNextRetryRef = useRef(0);
  const dateIntroSourceRef = useRef<{ source: AudioBufferSourceNode; gain: GainNode } | null>(null);
  const openingFanfareRef = useRef<{ source: AudioBufferSourceNode; gain: GainNode } | null>(null);
  const greetSourceRef = useRef<{ source: AudioBufferSourceNode; gain: GainNode } | null>(null);
  const firstBootRef = useRef(true);
  const playGenerationRef = useRef(0);
  const monthSwitchTimerRef = useRef<number | null>(null);

  const loadBuffer = useCallback(async (url: string): Promise<AudioBuffer> => {
    const ctx = ctxRef.current!;
    const resp = await fetch(url);
    const arr = await resp.arrayBuffer();
    return await ctx.decodeAudioData(arr);
  }, []);

  const ensureContext = useCallback(() => {
    if (ctxRef.current) return ctxRef.current;
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AC();
    ctxRef.current = ctx;
    const master = ctx.createGain();
    master.gain.value = 1.0;
    master.connect(ctx.destination);
    masterGainRef.current = master;
    return ctx;
  }, []);

  const createSource = useCallback((ctx: AudioContext, buf: AudioBuffer, vol: number): ProgramSource => {
    const filt = ctx.createBiquadFilter();
    filt.type = "bandpass";
    filt.frequency.value = 2400;
    filt.Q.value = 0.5;
    const gn = ctx.createGain();
    gn.gain.value = 0;
    filt.connect(gn);
    gn.connect(masterGainRef.current!);
    return { buffer: buf, source: null, gain: gn, filter: filt, started: false };
  }, []);

  const startSource = useCallback((ps: ProgramSource, loop: boolean, onEnded?: () => void, offsetSec?: number) => {
    const ctx = ctxRef.current;
    if (!ctx || ps.started) return;
    const src = ctx.createBufferSource();
    src.buffer = ps.buffer;
    src.loop = loop;
    src.connect(ps.filter);
    const off = offsetSec ?? (loop ? Math.random() * ps.buffer.duration * 0.4 : 0);
    src.start(0, off);
    ps.source = src;
    ps.started = true;
    src.onended = () => {
      ps.started = false;
      ps.source = null;
      if (onEnded) onEnded();
    };
  }, []);

  const stopSource = useCallback((ps: ProgramSource) => {
    if (ps.started && ps.source) {
      try { ps.source.stop(); } catch {}
      ps.started = false;
      ps.source = null;
    }
  }, []);

  const stopCurrentFloat = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const myGeneration = ++playGenerationRef.current;
    const isStale = () => playGenerationRef.current !== myGeneration;
    const t = ctx.currentTime;
    const FADE_OUT_TIME = 0.005;
    const STOP_DELAY = 12;

    const cur = currentPlayingRef.current;
    if (cur) {
      const ps = floatSourcesRef.current.get(cur.prog.id);
      if (ps) {
        try {
          ps.gain.gain.cancelScheduledValues(t);
          ps.gain.gain.setValueAtTime(ps.gain.gain.value, t);
          ps.gain.gain.linearRampToValueAtTime(0, t + FADE_OUT_TIME);
        } catch {}
        const psRef = ps;
        setTimeout(() => {
          if (!isStale()) stopSource(psRef);
        }, STOP_DELAY);
      }
    }
    if (songTimerRef.current) {
      clearTimeout(songTimerRef.current);
      songTimerRef.current = null;
    }
    if (dateIntroSourceRef.current) {
      const ds = dateIntroSourceRef.current.source;
      const dg = dateIntroSourceRef.current.gain;
      try {
        dg.gain.cancelScheduledValues(t);
        dg.gain.setValueAtTime(dg.gain.value, t);
        dg.gain.linearRampToValueAtTime(0, t + FADE_OUT_TIME);
      } catch {}
      setTimeout(() => {
        if (!isStale()) { try { ds.stop(); } catch {} }
      }, STOP_DELAY);
      dateIntroSourceRef.current = null;
    }
    if (openingFanfareRef.current) {
      const fs = openingFanfareRef.current.source;
      const fg = openingFanfareRef.current.gain;
      try {
        fg.gain.cancelScheduledValues(t);
        fg.gain.setValueAtTime(fg.gain.value, t);
        fg.gain.linearRampToValueAtTime(0, t + FADE_OUT_TIME);
      } catch {}
      setTimeout(() => {
        if (!isStale()) { try { fs.stop(); } catch {} }
      }, STOP_DELAY);
      openingFanfareRef.current = null;
    }
    if (greetSourceRef.current) {
      const gs = greetSourceRef.current.source;
      const gg = greetSourceRef.current.gain;
      try {
        gg.gain.cancelScheduledValues(t);
        gg.gain.setValueAtTime(gg.gain.value, t);
        gg.gain.linearRampToValueAtTime(0, t + FADE_OUT_TIME);
      } catch {}
      setTimeout(() => {
        if (!isStale()) { try { gs.stop(); } catch {} }
      }, STOP_DELAY);
      greetSourceRef.current = null;
    }
    currentPlayingRef.current = null;
    currentLoopRef.current = false;
  }, [stopSource]);

  const startBgm = useCallback((options?: { bgmId?: string; volume?: number; filterFreq?: number; filterQ?: number }) => {
    const ctx = ctxRef.current;
    if (!ctx || !bgmGainRef.current || !bgmFilterRef.current) return;

    const bgmId = options?.bgmId;
    const volume = options?.volume ?? 0.07;
    const filterFreq = options?.filterFreq ?? 2500;
    const filterQ = options?.filterQ ?? 0.5;

    let buf: AudioBuffer | null = null;
    let currentBgmId: string | null = null;

    if (bgmSourceRef.current && bgmSourceRef.current.buffer) {
      for (const [id, b] of bgmBuffersRef.current) {
        if (b === bgmSourceRef.current.buffer) {
          currentBgmId = id;
          break;
        }
      }
    }

    if (bgmId) {
      buf = bgmBuffersRef.current.get(bgmId) || null;
    }
    if (!buf) {
      const defaultPool = ["bgm_gczg_inst", "bgm_mygcd_inst", "bgm_dashuai_inst"];
      const available = defaultPool.filter(id => bgmBuffersRef.current.has(id));
      if (available.length > 0) {
        buf = bgmBuffersRef.current.get(available[Math.floor(Math.random() * available.length)]) || null;
      }
    }
    if (!buf) {
      const buffers = Array.from(bgmBuffersRef.current.values());
      if (buffers.length === 0) return;
      buf = buffers[Math.floor(Math.random() * buffers.length)] || null;
    }

    const wasPlaying = bgmPlayingRef.current;
    const needSwitch = !bgmSourceRef.current || !wasPlaying || (bgmId && currentBgmId !== bgmId);

    if (needSwitch) {
      if (bgmSourceRef.current) {
        try { bgmSourceRef.current.stop(); } catch {}
        bgmSourceRef.current.disconnect();
      }
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.loop = true;
      src.connect(bgmFilterRef.current);
      src.start();
      bgmSourceRef.current = src;
      bgmPlayingRef.current = true;
    }

    const t = ctx.currentTime;
    bgmGainRef.current.gain.cancelScheduledValues(t);
    if (!wasPlaying || needSwitch) {
      bgmGainRef.current.gain.setValueAtTime(0, t);
    }
    bgmGainRef.current.gain.linearRampToValueAtTime(volume, t + 0.8);

    bgmFilterRef.current.frequency.cancelScheduledValues(t);
    bgmFilterRef.current.frequency.linearRampToValueAtTime(filterFreq, t + 0.5);
    bgmFilterRef.current.Q.cancelScheduledValues(t);
    bgmFilterRef.current.Q.linearRampToValueAtTime(filterQ, t + 0.5);
  }, []);

  const stopBgm = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx || !bgmGainRef.current) return;
    if (!bgmPlayingRef.current) return;

    const t = ctx.currentTime;
    bgmGainRef.current.gain.cancelScheduledValues(t);
    bgmGainRef.current.gain.linearRampToValueAtTime(0, t + 0.5);
    bgmPlayingRef.current = false;

    setTimeout(() => {
      if (bgmSourceRef.current) {
        try { bgmSourceRef.current.stop(); } catch {}
        bgmSourceRef.current.disconnect();
        bgmSourceRef.current = null;
      }
    }, 600);
  }, []);

  const initNoiseGraph = useCallback(() => {
    if (noiseSourceRef.current) return;
    const ctx = ctxRef.current!;

    const bufSize = ctx.sampleRate * 4;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let b0=0,b1=0,b2=0,b3=0,b4=0,b5=0,b6=0;
    for (let i=0;i<bufSize;i++){
      const w=Math.random()*2-1;
      b0=0.99886*b0+w*0.0555179; b1=0.99332*b1+w*0.0750759;
      b2=0.96900*b2+w*0.1538520; b3=0.86650*b3+w*0.3104856;
      b4=0.55000*b4+w*0.5329522; b5=-0.7616*b5-w*0.0168980;
      d[i]=(b0+b1+b2+b3+b4+b5+b6+w*0.5362)*0.11;
      b6=w*0.115926;
    }
    noiseBufRef.current = buf;

    const noiseLP = ctx.createBiquadFilter();
    noiseLP.type = "lowpass"; noiseLP.frequency.value = 6000; noiseLP.Q.value = 0.3;
    noiseLPRef.current = noiseLP;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass"; bp.frequency.value = 2000; bp.Q.value = 2.0;
    noiseFilterRef.current = bp;
    const nGain = ctx.createGain(); nGain.gain.value = 0;
    noiseGainRef.current = nGain;
    noiseLP.connect(bp); bp.connect(nGain); nGain.connect(masterGainRef.current!);
    const nSrc = ctx.createBufferSource();
    nSrc.buffer = noiseBufRef.current; nSrc.loop = true; nSrc.connect(noiseLP); nSrc.start();
    noiseSourceRef.current = nSrc;

    const bgmFilter = ctx.createBiquadFilter();
    bgmFilter.type = "lowpass";
    bgmFilter.frequency.value = 2500;
    bgmFilter.Q.value = 0.5;
    bgmFilterRef.current = bgmFilter;
    const bgmGain = ctx.createGain();
    bgmGain.gain.value = 0;
    bgmGainRef.current = bgmGain;
    bgmFilter.connect(bgmGain);
    bgmGain.connect(masterGainRef.current!);
  }, []);

  const loadAudioBuffers = useCallback(async () => {
    const ctx = ctxRef.current!;

    const loadOne = async (p: Program, map: Map<string, ProgramSource>) => {
      if (failedLoadsRef.current.has(p.id)) return false;
      try {
        const basePath = p.file.startsWith("songs/") ? "/audio/" : "/audio/programs/";
        const buf = await loadBuffer(`${basePath}${p.file}`);
        map.set(p.id, createSource(ctx, buf, p.volume));
        return true;
      } catch {
        failedLoadsRef.current.add(p.id);
        return false;
      }
    };

    const stage1Tracks = [...BGM_TRACKS, ...SONG_BGM_TRACKS];
    await Promise.all(stage1Tracks.map(async (track) => {
      try {
        const buf = await loadBuffer(`/audio/${track.file}`);
        bgmBuffersRef.current.set(track.id, buf);
      } catch {}
    }));

    isReadyRef.current = true;

    const y = Math.floor(currentYearRef.current);
    const m = yearToMonth(currentYearRef.current);
    const firstProgId = `news_${y}_${String(m).padStart(2, "0")}_01`;
    const firstProg = FLOATS.find(f => f.id === firstProgId);
    const firstShortId = `date_short_${y}_${String(m).padStart(2, "0")}`;
    const firstShortProg = DATE_SHORTS.find(f => f.id === firstShortId);

    if (firstProg) {
      await loadOne(firstProg, floatSourcesRef.current);
    }
    if (firstShortProg) {
      await loadOne(firstShortProg, floatSourcesRef.current);
    }

    if (isPoweredOnRef.current && !isTuningRef.current && !isLockedRef.current) {
      enterLockedRef.current();
    } else {
      pendingEnterLockedRef.current = true;
    }

    const loadRemaining = async () => {
      const alreadyLoaded = new Set([
        ...(firstProg ? [firstProg.id] : []),
        ...(firstShortProg ? [firstShortProg.id] : []),
      ]);
      const batchSize = 10;
      const remaining = FLOATS.filter(f => !alreadyLoaded.has(f.id));
      for (let i = 0; i < remaining.length; i += batchSize) {
        const batch = remaining.slice(i, i + batchSize);
        await Promise.all(batch.map(p => loadOne(p, floatSourcesRef.current)));
      }
    };
    loadRemaining();
  }, [loadBuffer, createSource]);

  const SONG_SEGMENT_MS = 100000;
  const GAP_BETWEEN_ITEMS_MS = 600;
  const SONG_FADE_OUT_MS = 1800;
  const LOCK_DELAY_MS = 400;
  const START_DELAY_MS = 0;
  const REBUILD_DELAY_MS = 150;

  const playNextRef = useRef<() => void>(() => {});
  const startProgramRef = useRef<() => void>(() => {});
  const rebuildAndPlayRef = useRef<() => void>(() => {});
  const enterLockedRef = useRef<() => void>(() => {});

  const shuffle = <T,>(arr: T[]): T[] => {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };

  const pickOpenerForYear = useCallback((year: number, _month: number): Program | null => {
    const eligible = STATION_IDS.filter(s => s.year <= year);
    if (eligible.length === 0) return null;
    return eligible[Math.floor(Math.random() * eligible.length)];
  }, []);

  const pickJingleForYear = useCallback((year: number): Program | null => {
    if (Math.random() > 0.25) return null;
    const eligible = JINGLES.filter(j => j.year <= year);
    if (eligible.length === 0) return null;
    return eligible[Math.floor(Math.random() * eligible.length)];
  }, []);

  const pickBgmForEvent = useCallback((year: number, month: number, newsId?: string): { bgmId: string; bgmVolume: number; bgmFilterFreq: number; bgmFilterQ: number } => {
    if (year === 1949 && month === 10 && newsId && newsId.startsWith("news_1949_10_") && newsId.endsWith("_01")) {
      return { bgmId: "bgm_gczg_inst", bgmVolume: 0.07, bgmFilterFreq: 2500, bgmFilterQ: 0.5 };
    }
    if (year === 1949 && month === 10) {
      const pool = ["bgm_gczg_inst", "bgm_mygcd_inst", "bgm_dashuai_inst"];
      return { bgmId: pool[Math.floor(Math.random() * pool.length)], bgmVolume: 0.07, bgmFilterFreq: 2500, bgmFilterQ: 0.5 };
    }
    const pool = ["bgm_gczg_inst", "bgm_mygcd_inst", "bgm_dashuai_inst"];
    return { bgmId: pool[Math.floor(Math.random() * pool.length)], bgmVolume: 0.07, bgmFilterFreq: 2500, bgmFilterQ: 0.5 };
  }, []);

  const pickPoetryBgm = useCallback((category?: string): { bgmId: string; bgmVolume: number; bgmFilterFreq: number; bgmFilterQ: number } => {
    switch (category) {
      case "epic":
        return { bgmId: "bgm_gczg_inst", bgmVolume: 0.04, bgmFilterFreq: 1200, bgmFilterQ: 0.7 };
      case "military":
        return { bgmId: "bgm_dashuai_inst", bgmVolume: 0.04, bgmFilterFreq: 1400, bgmFilterQ: 0.6 };
      case "construction": {
        const pool = ["bgm_gczg_inst", "bgm_mygcd_inst"];
        return { bgmId: pool[Math.floor(Math.random() * pool.length)], bgmVolume: 0.04, bgmFilterFreq: 1200, bgmFilterQ: 0.7 };
      }
      case "lyrical":
        return { bgmId: "bgm_opening_dfh", bgmVolume: 0.03, bgmFilterFreq: 1000, bgmFilterQ: 0.8 };
      default:
        return { bgmId: "bgm_gczg_inst", bgmVolume: 0.04, bgmFilterFreq: 1200, bgmFilterQ: 0.7 };
    }
  }, []);

  const buildProgramQueue = useCallback((year: number, month: number): Program[] => {
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

    const availNews = shuffle(FLOATS.filter(f =>
      f.type === "news" && isProgramAvailable(f, targetYear, targetMonth)
    ));
    const availPoetry = shuffle(FLOATS.filter(f =>
      f.type === "poetry" && isProgramAvailable(f, targetYear, targetMonth)
    ));
    const availSongs = shuffle(FLOATS.filter(f =>
      f.type === "song" && isProgramAvailable(f, targetYear, targetMonth)
    ));
    const availLife = shuffle(FLOATS.filter(f =>
      f.type === "life" && isProgramAvailable(f, targetYear, targetMonth)
    ));
    const availWeather = shuffle(FLOATS.filter(f =>
      f.type === "weather" && isProgramAvailable(f, targetYear, targetMonth)
    ));
    const availIds = shuffle(FLOATS.filter(f =>
      f.type === "id" && isProgramAvailable(f, targetYear, targetMonth)
    ));
    const availJingles = shuffle(FLOATS.filter(f =>
      f.type === "jingle" && isProgramAvailable(f, targetYear, targetMonth)
    ));

    const monthNews = availNews.filter(n => !n.month || n.month === targetMonth);
    const prioritizedNews = monthNews;

    let newsIdx = 0, poetryIdx = 0, songIdx = 0, lifeIdx = 0, weatherIdx = 0;
    let idIdx = 0, jingleIdx = 0;
    let consecutiveVoice = 0;
    let itemsSinceJingle = 0;

    const pickWeighted = (): Program | null => {
      const r = Math.random();
      if (r < 0.45) {
        while (newsIdx < prioritizedNews.length) {
          const p = prioritizedNews[newsIdx++];
          if (!added.has(p.id)) return p;
        }
        while (newsIdx < availNews.length) {
          const p = availNews[newsIdx++];
          if (!added.has(p.id)) return p;
        }
        return null;
      } else if (r < 0.60) {
        while (poetryIdx < availPoetry.length) {
          const p = availPoetry[poetryIdx++];
          if (!added.has(p.id)) return p;
        }
        return null;
      } else if (r < 0.72) {
        while (weatherIdx < availWeather.length) {
          const p = availWeather[weatherIdx++];
          if (!added.has(p.id)) return p;
        }
        return null;
      } else if (r < 0.87) {
        while (songIdx < availSongs.length) {
          const p = availSongs[songIdx++];
          if (!added.has(p.id)) return p;
        }
        return null;
      } else {
        while (lifeIdx < availLife.length) {
          const p = availLife[lifeIdx++];
          if (!added.has(p.id)) return p;
        }
        return null;
      }
    };

    for (let i = 0; i < 25; i++) {
      const lastType = queue.length > 0 ? queue[queue.length - 1].type : null;
      const isLastSong = lastType === "song";

      if (queue.length === 1 && Math.random() < 0.5) {
        while (idIdx < availIds.length) {
          const p = availIds[idIdx++];
          if (!added.has(p.id)) { added.add(p.id); queue.push(p); consecutiveVoice++; itemsSinceJingle = 0; break; }
        }
      }

      if (itemsSinceJingle >= 3 && Math.random() < 0.3) {
        while (jingleIdx < availJingles.length) {
          const p = availJingles[jingleIdx++];
          if (!added.has(p.id)) { added.add(p.id); queue.push(p); consecutiveVoice++; itemsSinceJingle = 0; break; }
        }
      }

      const picked = pickWeighted();
      if (picked) {
        added.add(picked.id);
        queue.push(picked);
        if (picked.type === "song") {
          consecutiveVoice = 0;
        } else {
          consecutiveVoice++;
        }
        itemsSinceJingle++;
      } else {
        while (newsIdx < prioritizedNews.length) {
          const p = prioritizedNews[newsIdx++];
          if (!added.has(p.id)) { added.add(p.id); queue.push(p); consecutiveVoice++; itemsSinceJingle++; break; }
        }
      }
    }

    return queue;
  }, []);

  const programQueueRef = useRef<Program[]>([]);
  const songTimerRef = useRef<number | null>(null);

  const setPlaybackLevels = useCallback((progType: Program["type"]) => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const t = ctx.currentTime;
    let noiseVol: number;
    let noiseQ: number;
    let noiseFreq: number;

    if (progType === "news" || progType === "life" || progType === "poetry" || progType === "weather" || progType === "id" || progType === "jingle" || progType === "date_intro" || progType === "date_short" || progType === "greeting") {
      noiseVol = 0.00006;
      noiseQ = 3.0;
      noiseFreq = 2400;
    } else {
      noiseVol = 0.0003;
      noiseQ = 3.0;
      noiseFreq = 2000;
    }

    if (noiseGainRef.current) {
      noiseGainRef.current.gain.cancelScheduledValues(t);
      noiseGainRef.current.gain.linearRampToValueAtTime(noiseVol, t + 0.3);
    }
    if (noiseFilterRef.current) {
      noiseFilterRef.current.Q.cancelScheduledValues(t);
      noiseFilterRef.current.Q.linearRampToValueAtTime(noiseQ, t + 0.3);
      noiseFilterRef.current.frequency.cancelScheduledValues(t);
      noiseFilterRef.current.frequency.linearRampToValueAtTime(noiseFreq, t + 0.3);
    }
  }, []);

  const duckCurrentProgram = useCallback((duckLevel: number, fadeTime: number) => {
    const ctx = ctxRef.current;
    const cur = currentPlayingRef.current;
    if (!ctx || !cur) return;
    const ps = floatSourcesRef.current.get(cur.prog.id);
    if (ps && ps.started) {
      ps.gain.gain.cancelScheduledValues(ctx.currentTime);
      ps.gain.gain.linearRampToValueAtTime(cur.prog.volume * duckLevel, ctx.currentTime + fadeTime);
    }
  }, []);

  const restoreCurrentProgram = useCallback((fadeTime: number) => {
    const ctx = ctxRef.current;
    const cur = currentPlayingRef.current;
    if (!ctx || !cur) return;
    const ps = floatSourcesRef.current.get(cur.prog.id);
    if (ps && ps.started) {
      const isSong = cur.prog.type === "song";
      const targetVol = isSong ? cur.prog.volume * 0.85 : cur.prog.volume;
      ps.gain.gain.cancelScheduledValues(ctx.currentTime);
      ps.gain.gain.linearRampToValueAtTime(targetVol, ctx.currentTime + fadeTime);
    }
  }, []);

  const playNext = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx || !isLockedRef.current) return;

    if (songTimerRef.current) {
      clearTimeout(songTimerRef.current);
      songTimerRef.current = null;
    }

    const dateIntroItem = programQueueRef.current.length > 0 && programQueueRef.current[0].type === "date_intro"
      ? programQueueRef.current[0] : null;

    if (mustPlayDateRef.current || dateIntroItem) {
      if (dateIntroItem) {
        programQueueRef.current.shift();
      }
      const branchGen = playGenerationRef.current;
      const isBranchStale = () => playGenerationRef.current !== branchGen;
      const y = lockedYearRef.current;
      const m = lockedMonthRef.current;
      const forceFull = firstBootRef.current || mustPlayDateRef.current;
      firstBootRef.current = false;
      const picked = pickDateIntroFile(y, m, forceFull);
      mustPlayDateRef.current = false;
      lastPlayedProgIdRef.current = picked.progId;

      const playDateVoice = (voiceBuffer: AudioBuffer, withFanfare: boolean = true) => {
        stopCurrentFloat();
        segmentTypeRef.current = "news";

        const myGeneration = playGenerationRef.current;
        const isStale = () => playGenerationRef.current !== myGeneration;

        let fanfareBuf: AudioBuffer | null = null;
        if (withFanfare) {
          fanfareBuf = bgmBuffersRef.current.get("bgm_opening_gczg_brass") || bgmBuffersRef.current.get("bgm_opening_gczg");
        }
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

        setPlaybackLevels("greeting");
        startBgm({ volume: 0.025, filterFreq: 1800, filterQ: 0.5 });

        const voiceDelay = fanfareBuf ? 1.2 : 0.1;
        const tv = ctx.currentTime + voiceDelay;

        const playDateMain = (startTime: number) => {
          if (isStale() || !isLockedRef.current) return;
          setPlaybackLevels("date_intro");
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
          dateGain.gain.cancelScheduledValues(startTime);
          dateGain.gain.setValueAtTime(0, startTime);
          dateGain.gain.linearRampToValueAtTime(0.92, startTime + 0.15);
          dateSrc.start(startTime);
          dateIntroSourceRef.current = { source: dateSrc, gain: dateGain };

          dateSrc.onended = () => {
            if (dateIntroSourceRef.current?.source === dateSrc) {
              const t = ctx.currentTime;
              dateGain.gain.cancelScheduledValues(t);
              dateGain.gain.linearRampToValueAtTime(0, t + 0.2);
              setTimeout(() => {
                try { dateSrc.stop(); } catch {}
                if (dateIntroSourceRef.current?.source === dateSrc) {
                  dateIntroSourceRef.current = null;
                }
              }, 250);
            }
            if (isLockedRef.current && !isStale()) {
              setTimeout(() => playNextRef.current(), GAP_BETWEEN_ITEMS_MS);
            }
          };

          if (openingFanfareRef.current) {
            const fadeTime = startTime + voiceBuffer.duration - 1.5;
            if (fadeTime > ctx.currentTime) {
              openingFanfareRef.current.gain.gain.cancelScheduledValues(fadeTime);
              openingFanfareRef.current.gain.gain.linearRampToValueAtTime(0, fadeTime + 1.5);
            }
          }
        };

        const greetFile = pickGreetingFile(y);
        loadBuffer(`/audio/programs/${greetFile}`).then(greetBuf => {
          if (isStale() || !isLockedRef.current) return;
          const greetFilter = ctx.createBiquadFilter();
          greetFilter.type = "bandpass";
          greetFilter.frequency.value = 2800;
          greetFilter.Q.value = 0.4;
          const greetGain = ctx.createGain();
          greetGain.gain.value = 0;
          greetFilter.connect(greetGain);
          greetGain.connect(masterGainRef.current!);
          const greetSrc = ctx.createBufferSource();
          greetSrc.buffer = greetBuf;
          greetSrc.connect(greetFilter);
          greetGain.gain.cancelScheduledValues(tv);
          greetGain.gain.setValueAtTime(0, tv);
          greetGain.gain.linearRampToValueAtTime(0.92, tv + 0.1);
          greetSrc.start(tv);
          greetSourceRef.current = { source: greetSrc, gain: greetGain };
          const greetEndTime = tv + greetBuf.duration + 0.05;
          greetSrc.onended = () => {
            if (greetSourceRef.current?.source === greetSrc) {
              greetSourceRef.current = null;
            }
            const t = ctx.currentTime;
            greetGain.gain.cancelScheduledValues(t);
            greetGain.gain.linearRampToValueAtTime(0, t + 0.08);
            setTimeout(() => {
              try { greetSrc.stop(); } catch {}
            }, 120);
            if (isLockedRef.current && !isStale()) {
              playDateMain(greetEndTime);
            }
          };
        }).catch(() => {
          if (!isStale() && isLockedRef.current) {
            playDateMain(tv);
          }
        });
      };

      if (!picked.isFull) {
        const shortId = `date_short_${y}_${String(m).padStart(2, "0")}`;
        const shortPs = floatSourcesRef.current.get(shortId);
        if (shortPs) {
          playDateVoice(shortPs.buffer, false);
        } else {
          loadBuffer(`/audio/programs/${picked.file}`).then(buf => {
            if (!isBranchStale() && isLockedRef.current) playDateVoice(buf, false);
          }).catch(() => {
            if (!isBranchStale() && isLockedRef.current) setTimeout(() => playNextRef.current(), 100);
          });
        }
      } else {
        loadBuffer(`/audio/programs/${picked.file}`).then(buf => {
          if (!isBranchStale() && isLockedRef.current) playDateVoice(buf);
        }).catch(() => {
          if (isBranchStale() || !isLockedRef.current) return;
          const shortId = `date_short_${y}_${String(m).padStart(2, "0")}`;
          const shortPs = floatSourcesRef.current.get(shortId);
          if (shortPs) {
            playDateVoice(shortPs.buffer, false);
          } else {
            setTimeout(() => {
              if (!isBranchStale() && isLockedRef.current) playNextRef.current();
            }, 100);
          }
        });
      }
      return;
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
        if (failedLoadsRef.current.has(prog.id)) {
          playNextRetryRef.current = 0;
          playNextRef.current();
          return;
        }
        if (playNextRetryRef.current < 30) {
          programQueueRef.current.unshift(prog);
          playNextRetryRef.current++;
          const retryGen = playGenerationRef.current;
          setTimeout(() => {
            if (playGenerationRef.current === retryGen && isLockedRef.current) playNextRef.current();
          }, 100);
          return;
        }
        playNextRetryRef.current = 0;
        playNextRef.current();
        return;
      }
      playNextRetryRef.current = 0;

      stopCurrentFloat();
      const myGeneration = playGenerationRef.current;
      const isStale = () => playGenerationRef.current !== myGeneration;

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
        if (isStale() || !isLockedRef.current) return;
        const t1 = ctx.currentTime;
        ps.gain.gain.cancelScheduledValues(t1);
        ps.gain.gain.linearRampToValueAtTime(0, t1 + SONG_FADE_OUT_MS / 1000);
        setTimeout(() => {
          if (isStale() || !isLockedRef.current) return;
          stopSource(ps);
          if (currentPlayingRef.current?.prog.id === prog.id) {
            currentPlayingRef.current = null;
          }
          currentLoopRef.current = false;
          songTimerRef.current = null;
          if (hasMoreInQueue) {
            setTimeout(() => {
              if (!isStale() && isLockedRef.current) playNextRef.current();
            }, GAP_BETWEEN_ITEMS_MS);
          } else {
            rebuildAndPlayRef.current();
          }
        }, SONG_FADE_OUT_MS);
      }, hasMoreInQueue ? Math.min(SONG_SEGMENT_MS, 12000) : SONG_SEGMENT_MS);
      return;
    }

    const ps = floatSourcesRef.current.get(prog.id);
    if (!ps) {
      if (failedLoadsRef.current.has(prog.id)) {
        playNextRetryRef.current = 0;
        playNextRef.current();
        return;
      }
      if (playNextRetryRef.current < 15) {
        programQueueRef.current.unshift(prog);
        playNextRetryRef.current++;
        const retryGen = playGenerationRef.current;
        setTimeout(() => {
          if (playGenerationRef.current === retryGen && isLockedRef.current) playNextRef.current();
        }, 100);
        return;
      }
      failedLoadsRef.current.add(prog.id);
      playNextRetryRef.current = 0;
      playNextRef.current();
      return;
    }
    playNextRetryRef.current = 0;

    stopCurrentFloat();
    const myGeneration = playGenerationRef.current;
    const isStale = () => playGenerationRef.current !== myGeneration;

    const isVoice = prog.type === "news" || prog.type === "life" || prog.type === "poetry" || prog.type === "weather" || prog.type === "id" || prog.type === "jingle" || prog.type === "date_intro" || prog.type === "date_short" || prog.type === "greeting";
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

    const voiceType: "news" | "life" | "poetry" | "weather" | "date_intro" | "date_short" | null = isVoice
      ? (prog.type === "news" ? "news" : prog.type === "life" ? "life" : prog.type === "poetry" ? "poetry" : prog.type === "weather" ? "weather" : "date_intro")
      : null;

    if (isVoice && voiceType) {
      const curYear = lockedYearRef.current;
      const curMonth = lockedMonthRef.current;
      const isSameVoiceBlock = lastVoiceTypeRef.current === voiceType && currentBgmIdRef.current !== null;

      let bgmConfig: { bgmId?: string; bgmVolume: number; bgmFilterFreq: number; bgmFilterQ: number };
      if (prog.type === "poetry") {
        bgmConfig = pickPoetryBgm(prog.category);
        currentBgmIdRef.current = bgmConfig.bgmId || null;
      } else if (prog.type === "date_intro" || prog.type === "date_short") {
        bgmConfig = { bgmVolume: 0.02, bgmFilterFreq: 1800, bgmFilterQ: 0.5 };
      } else if (isSameVoiceBlock && currentBgmIdRef.current) {
        const cachedId = currentBgmIdRef.current;
        bgmConfig = {
          bgmId: cachedId,
          bgmVolume: 0.07,
          bgmFilterFreq: 2500,
          bgmFilterQ: 0.5,
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
      startBgm(
        { bgmId: bgmConfig.bgmId, volume: bgmConfig.bgmVolume, filterFreq: bgmConfig.bgmFilterFreq, filterQ: bgmConfig.bgmFilterQ }
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
      if (isStale() || currentPlayingRef.current?.prog.id !== prog.id) return;
      currentPlayingRef.current = null;
      setTimeout(() => {
        if (!isStale() && isLockedRef.current) playNextRef.current();
      }, GAP_BETWEEN_ITEMS_MS);
    });

    if (ps.source) {
      currentPlayingRef.current = { prog, source: ps.source };
    }
  }, [setPlaybackLevels, startSource, stopCurrentFloat, stopSource, startBgm, stopBgm, pickBgmForEvent, pickPoetryBgm]);

  const avoidFirstItemRepeat = () => {
    if (programQueueRef.current.length > 0 && programQueueRef.current[0].id === lastPlayedProgIdRef.current) {
      if (programQueueRef.current.length > 1) {
        const swapIdx = 1 + Math.floor(Math.random() * (programQueueRef.current.length - 1));
        [programQueueRef.current[0], programQueueRef.current[swapIdx]] = [programQueueRef.current[swapIdx], programQueueRef.current[0]];
      }
    }
  };

  const startProgram = useCallback(() => {
    if (!isLockedRef.current) return;
    const y = lockedYearRef.current;
    const m = lockedMonthRef.current;
    programQueueRef.current = buildProgramQueue(y, m);
    avoidFirstItemRepeat();
    setTimeout(() => playNextRef.current(), START_DELAY_MS);
  }, [buildProgramQueue]);

  const rebuildAndPlay = useCallback(() => {
    if (!isLockedRef.current) return;
    if (songTimerRef.current) {
      clearTimeout(songTimerRef.current);
      songTimerRef.current = null;
    }
    const y = lockedYearRef.current;
    const m = lockedMonthRef.current;
    programQueueRef.current = buildProgramQueue(y, m);
    avoidFirstItemRepeat();
    setTimeout(() => playNextRef.current(), REBUILD_DELAY_MS);
  }, [buildProgramQueue]);

  const enterLocked = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx || isLockedRef.current) return;
    if (!isReadyRef.current) {
      pendingEnterLockedRef.current = true;
      return;
    }
    isLockedRef.current = true;
    pendingEnterLockedRef.current = false;
    lockedYearRef.current = Math.floor(currentYearRef.current);
    lockedMonthRef.current = yearToMonth(currentYearRef.current);
    const t = ctx.currentTime;
    mustPlayDateRef.current = true;
    if (noiseGainRef.current) {
      noiseGainRef.current.gain.cancelScheduledValues(t);
      noiseGainRef.current.gain.linearRampToValueAtTime(0.00006, t + 0.3);
    }
    if (noiseFilterRef.current) {
      noiseFilterRef.current.Q.cancelScheduledValues(t);
      noiseFilterRef.current.Q.linearRampToValueAtTime(3.0, t + 0.3);
    }
    programQueueRef.current = [];
    segmentTypeRef.current = null;
    startProgramRef.current();
  }, []);

  const exitLocked = useCallback(() => {
    if (!isLockedRef.current) return;
    isLockedRef.current = false;
    if (songTimerRef.current) {
      clearTimeout(songTimerRef.current);
      songTimerRef.current = null;
    }
    if (monthSwitchTimerRef.current) {
      clearTimeout(monthSwitchTimerRef.current);
      monthSwitchTimerRef.current = null;
    }
    stopCurrentFloat();
    stopBgm();
    currentBgmIdRef.current = null;
    lastVoiceTypeRef.current = null;
    programQueueRef.current = [];
    segmentTypeRef.current = null;
  }, [stopCurrentFloat, stopBgm]);

  const powerOn = useCallback(() => {
    const ctx = ensureContext();
    if (ctx.state === "suspended") ctx.resume();
    initNoiseGraph();
    isPoweredOnRef.current = true;
    isLockedRef.current = false;
    lastMoveTimeRef.current = performance.now();
    const now = ctx.currentTime;
    const g = noiseGainRef.current!.gain;
    g.cancelScheduledValues(now);
    g.setValueAtTime(0, now);
    g.linearRampToValueAtTime(0.42, now + 0.05);
    loadAudioBuffers();
  }, [ensureContext, initNoiseGraph, loadAudioBuffers]);

  const setTuning = useCallback((omegaDegPerSec: number, currentTime: number) => {
    const ctx = ctxRef.current;
    if (!ctx || !isPoweredOnRef.current) return;
    const absOmega = Math.abs(omegaDegPerSec);
    const now = ctx.currentTime;
    const wasTuning = isTuningRef.current;
    const isTuning = absOmega > DEAD_ZONE;
    isTuningRef.current = isTuning;
    lastMoveTimeRef.current = performance.now();

    const clampedYear = Math.max(MIN_TIME, Math.min(MAX_TIME, currentTime));
    currentYearRef.current = clampedYear;

    if (isReadyRef.current) {
      if (isTuning && !wasTuning) {
        duckCurrentProgram(0.1, 0.08);
        exitLocked();
      }
      if (!isTuning && wasTuning) {
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
      }
      if (isLockedRef.current && !isTuning) {
        const newYear = Math.floor(clampedYear);
        const newMonth = yearToMonth(clampedYear);
        if (Math.abs(newYear - lockedYearRef.current) >= 1 || Math.abs(newMonth - lockedMonthRef.current) >= 2) {
          exitLocked();
          if (monthSwitchTimerRef.current) clearTimeout(monthSwitchTimerRef.current);
          monthSwitchTimerRef.current = window.setTimeout(() => {
            monthSwitchTimerRef.current = null;
            if (!isTuningRef.current && isPoweredOnRef.current) enterLocked();
          }, 200);
        }
      }
    } else {
      if (!isTuning && wasTuning) {
        pendingEnterLockedRef.current = true;
      }
    }

    const norm = Math.min(1, Math.max(0, (absOmega - 50) / (1200 - 50)));
    const isNewsSeg = segmentTypeRef.current === "news";
    const isMusicSeg = segmentTypeRef.current === "music";
    let targetNoise: number;
    let targetQ: number;
    let targetCenter: number;
    let noiseFadeTime: number;

    if (isTuning) {
      targetNoise = 0.45 + 0.40 * Math.pow(norm, 0.7);
      targetQ = 1.2 - 0.8 * norm;
      targetCenter = 1800 + norm * 2200;
      noiseFadeTime = 0.06;
    } else if (isLockedRef.current) {
      targetNoise = isMusicSeg ? 0.0003 : 0.00006;
      targetQ = 3.0;
      targetCenter = 2000;
      noiseFadeTime = 0.3;
    } else {
      targetNoise = 0.35;
      targetQ = 2.0;
      targetCenter = 2000;
      noiseFadeTime = 0.15;
    }

    noiseGainRef.current!.gain.cancelScheduledValues(now);
    noiseGainRef.current!.gain.linearRampToValueAtTime(targetNoise, now + noiseFadeTime);
    noiseFilterRef.current!.Q.cancelScheduledValues(now);
    noiseFilterRef.current!.Q.linearRampToValueAtTime(targetQ, now + noiseFadeTime);
    noiseFilterRef.current!.frequency.cancelScheduledValues(now);
    noiseFilterRef.current!.frequency.linearRampToValueAtTime(targetCenter, now + noiseFadeTime);
  }, [enterLocked, exitLocked, duckCurrentProgram, restoreCurrentProgram]);

  useEffect(() => {
    playNextRef.current = playNext;
    startProgramRef.current = startProgram;
    rebuildAndPlayRef.current = rebuildAndPlay;
    enterLockedRef.current = enterLocked;
  }, [playNext, startProgram, rebuildAndPlay, enterLocked]);

  useEffect(() => {
    return () => {
      if (noiseLockTimerRef.current) clearTimeout(noiseLockTimerRef.current);
      if (songTimerRef.current) clearTimeout(songTimerRef.current);
      if (monthSwitchTimerRef.current) clearTimeout(monthSwitchTimerRef.current);
      if (bgmSourceRef.current) {
        try { bgmSourceRef.current.stop(); } catch {}
        bgmSourceRef.current.disconnect();
        bgmSourceRef.current = null;
      }
    };
  }, []);

  const resumeAudio = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }
  }, []);

  return { powerOn, setTuning, ensureContext, resumeAudio };
}

/* ============================================================
   SPEAKER (SVG grille + dot-matrix year display, responsive)
   ============================================================ */
function Speaker({
  springTime, phase,
}: {
  springTime: MotionValue<number>;
  phase: "intro" | "powering" | "on";
}) {
  const { ref, size } = useCellSize({ w: BASE_SPEAKER_W, h: 200 });
  const [currentYear, setCurrentYear] = useState(() =>
    Math.floor(INITIAL_TIME)
  );

  useMotionValueEvent(springTime, "change", v => {
    const y = Math.max(MIN_TIME, Math.min(MAX_TIME, v));
    const yi = Math.floor(y);
    setCurrentYear(prev => prev !== yi ? yi : prev);
  });

  const innerW = Math.max(1, size.w - 48);
  const innerH = Math.max(1, size.h);
  const BASE_SPEAKER_H = 200;
  const scaleW = innerW / BASE_SPEAKER_W;
  const scaleH = innerH / BASE_SPEAKER_H;
  const scale = Math.min(scaleW, scaleH);
  const spacing = BASE_HOLE_SPACING * scale;
  const darkR = BASE_DARK_HOLE_R * scale;
  const offX = BASE_GRID_OFF_X * scale;
  const offY = BASE_GRID_OFF_Y * scale;
  const hlRingW = (BASE_HIGHLIGHT_R - BASE_DARK_HOLE_R) * scale;

  const gridW = innerW;
  const gridH = innerH;
  const cols = Math.max(1, Math.floor((gridW - offX) / spacing) + 2);
  const rows = Math.max(1, Math.floor((gridH - offY) / spacing) + 2);

  const idealStartCol = (gridW / 2 - offX) / spacing - (TOTAL_DOT_COLS - 1) / 2;
  const idealStartRow = (gridH / 2 - offY) / spacing - (DOT_ROWS - 1) / 2;
  const startCol = Math.max(0, Math.min(cols - TOTAL_DOT_COLS, Math.round(idealStartCol)));
  const startRow = Math.max(0, Math.min(rows - DOT_ROWS, Math.round(idealStartRow)));

  const coreR = darkR;

  const warmProgress = useMotionValue(0);
  const flickerVal = useMotionValue(1);
  const yearFlash = useMotionValue(1);
  const prevYearRef = useRef(currentYear);
  const flashCooldownRef = useRef(0);

  useEffect(() => {
    if (phase === "powering") {
      warmProgress.set(0);
      flickerVal.set(0);
      animate(warmProgress, 1, { duration: 1.8, ease: "easeOut", delay: 0.4 });
      const seed = Math.random();
      const fKeys = [0, 0.08, 0.2, 0.35, 0.55, 0.75, 1];
      const fVals = [
        0,
        0.5 + Math.random() * 0.3,
        0.25 + Math.random() * 0.2,
        0.65 + seed * 0.25,
        0.45 + Math.random() * 0.25,
        0.85 + Math.random() * 0.1,
        1,
      ];
      animate(flickerVal, fVals, { duration: 1.6, ease: "easeOut", times: fKeys, delay: 0.4 });
    } else if (phase === "on") {
      warmProgress.set(1);
      flickerVal.set(1);
    } else {
      warmProgress.set(0);
      flickerVal.set(0);
    }
    prevYearRef.current = currentYear;
  }, [phase, currentYear, warmProgress, flickerVal]);

  useEffect(() => {
    if (currentYear !== prevYearRef.current) {
      const now = performance.now();
      if (now - flashCooldownRef.current > 150) {
        flashCooldownRef.current = now;
        yearFlash.set(0.2);
        animate(yearFlash, 1, { duration: 0.12, ease: "easeOut" });
      }
      prevYearRef.current = currentYear;
    }
  }, [currentYear, yearFlash]);

  const litOpacity = useTransform(
    [warmProgress, flickerVal, yearFlash],
    ([wp, fv, yf]: number[]) => {
      if (phase === "intro") return 0;
      return Math.max(0, Math.min(1, wp * fv * yf));
    }
  );

  const yearStr = String(Math.max(MIN_TIME, Math.min(MAX_TIME, currentYear)));
  const digits = yearStr.padStart(NUM_DIGITS, "9").slice(-NUM_DIGITS).split("");

  const darkHoles: JSX.Element[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cx = offX + c * spacing;
      const cy = offY + r * spacing;
      if (cx < -spacing || cy < -spacing || cx > innerW + spacing || cy > innerH + spacing) continue;
      darkHoles.push(
        <circle key={`ds-${r}-${c}`} cx={cx} cy={cy} r={darkR} fill={THEME.speaker.holeShadeFill} />
      );
      darkHoles.push(
        <circle key={`d-${r}-${c}`} cx={cx} cy={cy} r={darkR * 0.72} fill={THEME.speaker.darkHoleFill} />
      );
    }
  }

  const coreEls: JSX.Element[] = [];
  for (let d = 0; d < NUM_DIGITS; d++) {
    const ch = digits[d];
    const glyph = DOT_FONT[ch] || DOT_FONT["0"];
    const dOff = d * (DOT_COLS + 1);
    for (let r = 0; r < DOT_ROWS; r++) {
      for (let c = 0; c < DOT_COLS; c++) {
        if (!glyph[r][c]) continue;
        const gc = startCol + dOff + c;
        const gr = startRow + r;
        const cx = offX + gc * spacing;
        const cy = offY + gr * spacing;
        coreEls.push(<circle key={`co-${d}-${r}-${c}`} cx={cx} cy={cy} r={coreR} fill={THEME.speaker.bulbCoreFill} />);
      }
    }
  }

  return (
    <div
      ref={ref}
      style={{ padding: "0 24px", overflow: "hidden", position: "relative", height: "100%" }}
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          borderRadius: 18,
          background: THEME.speaker.panelBg,
          boxShadow: THEME.speaker.panelShadow,
          overflow: "hidden",
        }}
      >
        <svg
          viewBox={`0 0 ${innerW} ${innerH}`}
          width="100%"
          height="100%"
          style={{ display: "block", borderRadius: 16 }}
          preserveAspectRatio="none"
        >
          {darkHoles}
          <motion.g style={{ opacity: litOpacity }}>
            {coreEls}
          </motion.g>
        </svg>
      </div>
    </div>
  );
}

/* ============================================================
   DISPLAY
   ============================================================ */
function Display({
  springTime, timeVelocity, phase, yearJolt,
}: {
  springTime: MotionValue<number>;
  timeVelocity: MotionValue<number>;
  phase: 'intro' | 'powering' | 'on';
  yearJolt: MotionValue<number>;
}) {
  const { ref: outerRef, size: cellSize } = useCellSize({ w: 320, h: 100 });

  // Warm-up flicker MotionValue: driven by keyframes when phase='powering', 0 at rest
  const warmFlicker = useMotionValue(0);
  const prevPhaseRef = useRef(phase);

  useEffect(() => {
    if (phase === 'powering' && prevPhaseRef.current !== 'powering') {
      // Generate a randomized flicker sequence simulating CRT/tube warm-up.
      // Every power-on produces a different random flicker pattern.
      // Physics-inspired: early high-frequency micro-flickers + occasional bright flashes,
      // then decreasing amplitude as tubes stabilize, with a final settling pop.
      // Total duration 1300ms (compressed 2x for faster boot).
      const DURATION = 1300;
      const N_KEYS = 24;
      // Random seed for this power-on (each boot different)
      const seed = Math.random();
      // Pre-generate random events: 1-2 bright surges and 1-2 power dips
      const events: { at: number; delta: number }[] = [];
      // Initial power-surge flash (always present near start)
      events.push({ at: 0.04 + Math.random() * 0.05, delta: 0.35 + Math.random() * 0.2 });
      // 1-2 random bright surges in the early-mid phase
      const nSurges = 1 + Math.floor(Math.random() * 2);
      for (let k = 0; k < nSurges; k++) {
        events.push({ at: 0.15 + Math.random() * 0.35, delta: 0.15 + Math.random() * 0.2 });
      }
      // 1-2 random power dips (flickering down) in the unstable phase
      const nDips = 1 + Math.floor(Math.random() * 2);
      for (let k = 0; k < nDips; k++) {
        events.push({ at: 0.2 + Math.random() * 0.4, delta: -(0.15 + Math.random() * 0.2) });
      }
      // Small random phase offsets for the two sine components (different every boot)
      const fastPhase = seed * Math.PI * 2;
      const slowPhase = seed * Math.PI * 5.3;
      const fastFreq = 110 + Math.random() * 40;
      const slowFreq = 24 + Math.random() * 12;

      const keys = new Array(N_KEYS + 1).fill(0).map((_, i) => i / N_KEYS);
      const values: number[] = [];
      for (let i = 0; i <= N_KEYS; i++) {
        const t = i / N_KEYS; // 0..1 progress
        // Base brightness ramp: quick initial dim glow → darker unstable phase → final rise
        let base: number;
        if (t < 0.06) {
          base = (t / 0.06) * 0.55;              // 0-156ms: initial surge to dim glow
        } else if (t < 0.32) {
          base = 0.55 + (t - 0.06) / 0.26 * 0.1;  // 156-832ms: dim unstable plateau
        } else if (t < 0.75) {
          base = 0.65 + Math.pow((t - 0.32) / 0.43, 1.1) * 0.25; // 832-1950ms: brightening
        } else {
          base = 0.9 + Math.pow((t - 0.75) / 0.25, 1.4) * 0.1;    // 1950-2600ms: final settle
        }
        base = Math.max(0, Math.min(1, base));
        // Flicker amplitude envelope: strong at start, decays as tubes warm
        const envelope = Math.max(0, Math.pow(1 - t, 0.75)) * 0.5;
        // Mix fast micro-jitter + slow wobble
        const fastJitter = Math.sin(t * fastFreq + fastPhase) * 0.35;
        const slowWobble = Math.sin(t * slowFreq + slowPhase) * 0.65;
        let flicker = (fastJitter * 0.4 + slowWobble * 0.6) * envelope;
        // Apply random events (surges/dips) with smooth falloff
        for (const ev of events) {
          const dist = Math.abs(t - ev.at);
          const width = ev.delta > 0 ? 0.03 : 0.05; // dips wider than surges
          if (dist < width) {
            const falloff = Math.cos((dist / width) * Math.PI / 2);
            flicker += ev.delta * falloff;
          }
        }
        values.push(Math.max(0, Math.min(1.08, base + flicker)));
      }
      // Animate warmFlicker through the randomized sequence
      warmFlicker.set(0);
      animate(warmFlicker, values, {
        duration: DURATION / 1000,
        ease: "linear",
        times: keys,
      });
    }
    if (phase === 'on' && prevPhaseRef.current === 'powering') {
      warmFlicker.set(1);
    }
    prevPhaseRef.current = phase;
  }, [phase, warmFlicker]);

  // Derived opacity for SVG content and pointer during warm-up
  const contentOpacity = useTransform(warmFlicker, v => {
    if (phase === 'intro') return 0.28;
    if (phase === 'on') return 1;
    return 0.28 + (v * 0.72);
  });
  const pointerOpacity = useTransform(warmFlicker, v => {
    if (phase === 'intro') return 0.35;
    if (phase === 'on') return 1;
    return 0.35 + (v * 0.65);
  });
  // Warm glow overlay brightness during warm-up
  const glowOpacity = useTransform(warmFlicker, v => {
    if (phase !== 'powering') return 0;
    // Glow pulses with flicker but always present once started
    return 0.25 + v * 0.55 + Math.max(0, v - 0.7) * 0.5;
  });

  const amberW  = Math.max(cellSize.w - 4, 100);
  const amberH  = Math.max(cellSize.h - 4, 50);
  const ptrTravel = amberW - PTR_PAD * 2 - EDGE_INSET * 2;
  const leftStopPx  = PTR_PAD + EDGE_INSET;
  const rightStopPx = amberW - PTR_PAD - EDGE_INSET;

  const yearFontSz = Math.max(10, Math.min(26, amberH * 0.22));
  const monthFontSz = Math.max(9, Math.min(18, amberH * 0.15));
  const yearLabelY = amberH - Math.max(3, yearFontSz * 0.28);
  const monthLabelY = Math.max(monthFontSz + 8, yearLabelY - yearFontSz - 4);
  const dmdCY = Math.min(amberH * 0.55, monthLabelY - monthFontSz * 0.8);
  const maxTickH = Math.max(12, dmdCY - 10 - 5);
  const tkBiweekly = maxTickH * 0.20;
  const tkMonth    = maxTickH * 0.45;
  const tkQtr      = maxTickH * 0.65;
  const tkYear     = maxTickH;
  const dmdR  = Math.max(1.2, Math.min(3, amberH * 0.022));
  const ptrBottom = Math.min(amberH - 2, yearLabelY + yearFontSz * 0.2);
  const ptrH = Math.max(16, ptrBottom - 5);

  // Responsive fade-mask width (capped)
  const fadeW = Math.max(FADE_MIN, Math.min(FADE_MAX, amberW * FADE_RATIO));

  // Force re-render on every animation frame (motion value changes don't trigger React renders)
  const [, setTick] = useState(0);
  useMotionValueEvent(springTime, "change", () => setTick(t => (t + 1) & 0xffff));

  // Compute ptrSvgX and visXRange directly from latest springTime (always up-to-date, no lag)
  const currentTime = springTime.get();
  const clampedTime = Math.max(MIN_TIME, Math.min(MAX_TIME, currentTime));
  const ptrSvgX = (clampedTime - SVG_START_YEAR) * PX_PER_YEAR;
  const prog = (clampedTime - MIN_TIME) / (MAX_TIME - MIN_TIME);
  const ptrScreenX = leftStopPx + prog * ptrTravel;
  // Large buffer (80px each side ≈ 2.6 months) ensures months are pre-rendered before entering view
  const VIS_BUFFER = 80;
  const visXRange: [number, number] = [
    ptrSvgX - ptrScreenX - VIS_BUFFER,
    ptrSvgX + (amberW - ptrScreenX) + VIS_BUFFER,
  ];

  const pxPerYear = ptrTravel / (MAX_TIME - MIN_TIME);

  const toPx = (v: number): number => {
    if (v < MIN_TIME) return leftStopPx - rubberBand(MIN_TIME - v, pxPerYear);
    if (v > MAX_TIME) return rightStopPx + rubberBand(v - MAX_TIME, pxPerYear);
    return leftStopPx + ((v - MIN_TIME) / (MAX_TIME - MIN_TIME)) * ptrTravel;
  };

  const basePointerCenterX = useTransform(springTime, toPx);
  const pointerCenterX = useTransform(
    [basePointerCenterX, yearJolt],
    ([bx, jx]: number[]) => bx + jx
  );
  const pointerLeft = useTransform(pointerCenterX, cx => cx - PTR_W / 2);

  const scaleX = useTransform(springTime, v => {
    if (v < MIN_TIME) {
      const fD = rubberBand(MIN_TIME - v, pxPerYear);
      const gD = fD * RUBBER_FOLLOW;
      const tickXMin = (MIN_TIME - SVG_START_YEAR) * PX_PER_YEAR;
      return (leftStopPx - tickXMin) + gD;
    }
    if (v > MAX_TIME) {
      const fD = rubberBand(v - MAX_TIME, pxPerYear);
      const gD = fD * RUBBER_FOLLOW;
      const tickXMax = (MAX_TIME - SVG_START_YEAR) * PX_PER_YEAR;
      return (rightStopPx - tickXMax) - gD;
    }
    const tickX = (v - SVG_START_YEAR) * PX_PER_YEAR;
    const pCenter = toPx(v);
    return pCenter - tickX;
  });
  const pointerRot = useTransform(
    timeVelocity, v => Math.max(-3, Math.min(3, v * ROTATION_FACTOR))
  );

  return (
    <div ref={outerRef} style={{ padding: "0 24px" }}>
      <div style={{
        width: "100%", height: cellSize.h,
        padding: 2, borderRadius: 10, overflow: "hidden",
        boxSizing: "border-box",
        background: THEME.display.frameBg,
        boxShadow: THEME.display.frameShadow,
      }}>
        <div style={{
          position: "relative", width: "100%", height: "100%",
          borderRadius: 8, overflow: "hidden",
          background:
            phase === 'intro'
              ? THEME.display.glassOffBg
              : THEME.display.glassOnBg,
          transition: "background 1200ms ease",
          boxShadow:
            phase === 'intro'
              ? THEME.display.glassOffShadow
              : THEME.display.glassOnShadow,
        }}>
          {/* Subtle glass reflection on off state */}
          {phase === 'intro' && (
            <div style={{
              pointerEvents: "none", position: "absolute", inset: 0,
              background: THEME.display.glassTopHighlight,
            }} />
          )}
          {(phase === 'on') && (
            <motion.div
              style={{
                pointerEvents: "none", position: "absolute", inset: 0,
                background: THEME.display.offStateWarmReflection,
              }}
              animate={{ opacity: [0.45, 0.9, 0.45] }}
              transition={{ duration: 3.8, repeat: Infinity, ease: "easeInOut" }}
            />
          )}
          {/* Power-on warm-up: glow brightness follows the flicker sequence */}
          {phase === 'powering' && (
            <motion.div
              style={{
                pointerEvents: "none", position: "absolute", inset: 0,
                background: THEME.display.onStateCenterGlow,
                opacity: glowOpacity,
              }}
            />
          )}
          {/* Power-on white flash: quick initial flash, then strobe 2-3 times before fading out */}
          {phase === 'powering' && (
            <motion.div
              key="whiteflash"
              style={{
                pointerEvents: "none", position: "absolute", inset: 0,
                background: THEME.display.powerFlashMask,
              }}
              initial={{ opacity: 0 }}
              animate={{ opacity: [
                0, 1, 0,        // 0→80ms: flash on, 80→160ms: off
                0.75, 0,         // 160→240ms: second flash, off
                0.4, 0.1, 0.5, 0 // 240-450ms: weak flicker, gone
              ] }}
              transition={{
                duration: 0.55,
                times: [0, 0.08, 0.16, 0.24, 0.32, 0.4, 0.5, 1],
                ease: "easeOut",
              }}
            />
          )}

          <motion.svg
            style={{
              position: "absolute", top: 0, left: 0,
              width: SVG_TOTAL_W, height: "100%",
              x: scaleX,
              opacity: contentOpacity,
            }}
          >
            {BIWEEKLY_X.map(x => (
              <line
                key={`bw${x}`}
                x1={x} x2={x} y1={5} y2={5 + tkBiweekly}
                stroke={THEME.display.tickStroke} strokeWidth={0.9}
              />
            ))}

            {SCALE_TICKS.map(t => {
              const h = t.type === "year" ? tkYear
                : t.type === "quarter" ? tkQtr : tkMonth;
              const stroke =
                t.type === "year"    ? THEME.display.yearTickFill
                : t.type === "quarter" ? THEME.display.quarterTickFill
                : THEME.display.monthTickFill;
              const sw = t.type === "year" ? 2.2 : t.type === "quarter" ? 1.5 : 1.1;

              return (
                <g key={`${t.year}-${t.month}`}>
                  <line x1={t.x} x2={t.x} y1={5} y2={5 + h} stroke={stroke} strokeWidth={sw} />

                  {t.type === "year" && (
                    <polygon
                      points={[
                        `${t.x},${dmdCY - dmdR * 1.5}`,
                        `${t.x + dmdR},${dmdCY}`,
                        `${t.x},${dmdCY + dmdR * 1.5}`,
                        `${t.x - dmdR},${dmdCY}`,
                      ].join(" ")}
                      fill={THEME.display.yearDiamondFill} opacity={THEME.display.yearDiamondOpacity}
                    />
                  )}

                  {t.yearLabel && (
                    <text
                      x={t.x} y={yearLabelY} textAnchor="middle" fill={THEME.display.yearLabelFill}
                      style={{
                        fontSize: yearFontSz,
                        fontFamily: "Georgia,'Times New Roman',serif",
                        fontWeight: 700, letterSpacing: -0.5,
                      }}
                    >
                      {t.yearLabel}
                    </text>
                  )}

                  {/* ── Month labels: pointer in interval [label_n, label_{n+1}) highlights label_n at 24px ── */}
                  {t.month !== 1 && (() => {
                    if (t.x < visXRange[0] || t.x > visXRange[1]) return null;
                    // Floor-based month index: interval [tick_m, tick_{m+1}) belongs to month m's label
                    // monthIdx=0 → Jan/year boundary (no highlight), 1→label"2"(Feb), ..., 11→label"12"(Dec)
                    const monthIdx = yearToMonthIdx(clampedTime);
                    // Year boundary zone (0=Dec→Jan, or near next year's Jan at 12) → no month highlight
                    if (monthIdx === 0) {
                      return (
                        <text
                          x={t.x} y={monthLabelY} textAnchor="middle"
                          fill={THEME.display.monthLabelFill}
                          style={{
                            fontSize: monthFontSz,
                            fontFamily: "Georgia,'Times New Roman',serif",
                            fontWeight: 700,
                            letterSpacing: -0.3,
                          }}
                        >{t.month}</text>
                      );
                    }
                    // monthIdx 1-11 corresponds to label month (monthIdx+1): "2"-"12"
                    // The label position for that month is at (Math.floor(clampedTime) + (monthIdx)/12) → tick for month (monthIdx+1)
                    const highlightLabelMonth = monthIdx + 1;
                    const highlightX = (Math.floor(clampedTime) + monthIdx / 12 - SVG_START_YEAR) * PX_PER_YEAR;
                    const monthW = PX_PER_YEAR / 12;
                    const distToHighlight = Math.abs(t.x - highlightX);
                    const isHighlighted = t.month === highlightLabelMonth && distToHighlight < monthW * 0.4;
                    // Smooth crossfade near the tick boundary to avoid jarring jump
                    let sizeProx = 0;
                    if (isHighlighted) {
                      sizeProx = 1;
                    } else if (t.month === highlightLabelMonth && distToHighlight < monthW * 0.55) {
                      sizeProx = Math.max(0, 1 - (distToHighlight - monthW * 0.4) / (monthW * 0.15));
                    }
                    const fontSize = monthFontSz + sizeProx * Math.max(4, monthFontSz * 0.33);
                    return (
                      <text
                        x={t.x} y={monthLabelY} textAnchor="middle"
                        fill={THEME.display.monthLabelFill}
                        style={{
                          fontSize,
                          fontFamily: "Georgia,'Times New Roman',serif",
                          fontWeight: 700,
                          letterSpacing: -0.3,
                        }}
                      >{t.month}</text>
                    );
                  })()}
                </g>
              );
            })}
          </motion.svg>

          {/* ── Red pointer ── */}
          <motion.div
            style={{
              pointerEvents: "none", position: "absolute",
              left: 0, x: pointerLeft, top: 5,
              width: PTR_W, height: ptrH,
              transformOrigin: "bottom center", rotate: pointerRot,
              opacity: pointerOpacity,
            }}
          >
            <div style={{
              position: "absolute", left: 4, top: 4,
              width: 5, height: "100%",
              background: THEME.display.pointerShadowEllipse, borderRadius: 3, filter: "blur(3px)",
            }} />
            <div style={{
              position: "absolute", inset: 0,
              background: THEME.pointer.gradient,
              borderRadius: "3px 3px 2px 2px",
              boxShadow: THEME.pointer.shadow,
            }} />
            <div style={{
              position: "absolute", top: -6, left: "50%", transform: "translateX(-50%)",
              width: 0, height: 0,
              borderLeft: "4px solid transparent",
              borderRight: "4px solid transparent",
              borderBottom: `7px solid ${THEME.pointer.arrowBorderBottom}`,
              filter: THEME.pointer.arrowFilter,
            }} />
          </motion.div>

          {/* ── Multi-layer edge fade masks (optical vignetting simulation) ──
              Design rationale:
              - Color matches display state (grey when off, warm amber when on)
              - 5+ gradient stops with nonlinear curve simulating cos⁴θ optical falloff
              - 3 stacked layers: hard inner frame shadow → medium vignette → soft outer fade
              - Top/bottom subtle vignette added for depth (curved glass effect)          */}
          {(() => {
            const isOff = phase === 'intro';
            const isWarming = phase === 'powering';
            const vignette = isOff ? THEME.display.vignette.off : isWarming ? THEME.display.vignette.warming : THEME.display.vignette.on;
            const edge = vignette.edge;
            const mid = vignette.mid;
            const soft = vignette.soft;
            const hint = vignette.hint;
            const topEdge = (vignette as typeof THEME.display.vignette.off).topEdge ?? THEME.display.vignette.on.topEdge;
            const bottomEdge = (vignette as typeof THEME.display.vignette.off).bottomEdge ?? THEME.display.vignette.on.bottomEdge;

            const fw1 = fadeW * 0.35;
            const fw2 = fadeW * 0.7;
            const fw3 = fadeW;

            const leftGrad = `linear-gradient(90deg,
              ${edge} 0%,
              ${mid}  ${(fw1/fw3*100).toFixed(1)}%,
              ${soft} ${(fw2/fw3*100).toFixed(1)}%,
              ${hint} ${((fw2+fw1)/fw3*50+30).toFixed(1)}%,
              transparent 100%)`;
            const rightGrad = `linear-gradient(270deg,
              ${edge} 0%,
              ${mid}  ${(fw1/fw3*100).toFixed(1)}%,
              ${soft} ${(fw2/fw3*100).toFixed(1)}%,
              ${hint} ${((fw2+fw1)/fw3*50+30).toFixed(1)}%,
              transparent 100%)`;

            return (
              <>
                <div style={{
                  pointerEvents: "none", position: "absolute", top: 0, bottom: 0, left: 0,
                  width: fw3, background: leftGrad,
                }} />
                <div style={{
                  pointerEvents: "none", position: "absolute", top: 0, bottom: 0, right: 0,
                  width: fw3, background: rightGrad,
                }} />
                <div style={{
                  pointerEvents: "none", position: "absolute", left: 0, right: 0, top: 0,
                  height: Math.round(amberH * 0.18),
                  background: `linear-gradient(180deg, ${topEdge} 0%, transparent 100%)`,
                }} />
                <div style={{
                  pointerEvents: "none", position: "absolute", left: 0, right: 0, bottom: 0,
                  height: Math.round(amberH * 0.22),
                  background: `linear-gradient(0deg, ${bottomEdge} 0%, transparent 100%)`,
                }} />
              </>
            );
          })()}
          <div style={{
            pointerEvents: "none", position: "absolute", inset: 0, borderRadius: 8,
            background: THEME.display.topHighlightBar,
          }} />
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   KNOB
   ============================================================ */
function Knob({
  timeMV, onKnobStart, onKnobMove, onKnobEnd, introRunning, introAngle, phase,
}: {
  timeMV: MotionValue<number>;
  onKnobStart: () => void;
  onKnobMove: (omega: number, currentTime: number) => void;
  onKnobEnd: (omega: number, currentTime: number) => void;
  introRunning: boolean;
  introAngle: MotionValue<number>;
  phase: "intro" | "powering" | "on";
}) {
  const { ref: outerRef, size: cellSize } = useCellSize({ w: 360, h: 360 });
  const knobRef = useRef<HTMLDivElement>(null);

  const knobMarginRatio = 0.10;
  const availableSize = Math.min(cellSize.w, cellSize.h);
  const knobSize = Math.floor(availableSize * (1 - 2 * knobMarginRatio));
  const knobRadius = knobSize / 2;
  const socketInset = Math.round(knobSize * 0.05);
  const bezelInset = Math.round(knobSize * 0.07);
  const faceInset = Math.round(knobSize * 0.12);

  const dragRef = useRef<{
    active: boolean;
    centerX: number;
    centerY: number;
    lastAngle: number;
    lastVisRotation: number;
    lastTime: number;
    omegaSmooth: number;
    currentTime: number;
    pointerX: number;
    pointerY: number;
  } | null>(null);
  const visRotationRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const visRotation = useMotionValue(0);
  const [pressed, setPressed] = useState(false);

  const computeMovementFactor = useCallback((currentTime: number, goingLeft: boolean): number => {
    if (currentTime < MIN_TIME) {
      const overshoot = MIN_TIME - currentTime;
      if (goingLeft) {
        return 1 / (1 + overshoot * 8);
      }
      return 1.0;
    }
    if (currentTime > MAX_TIME) {
      const overshoot = currentTime - MAX_TIME;
      if (!goingLeft) {
        return 1 / (1 + overshoot * 8);
      }
      return 1.0;
    }
    const distToLeft = currentTime - MIN_TIME;
    const distToRight = MAX_TIME - currentTime;
    if (goingLeft && distToLeft < EDGE_BAND) {
      return 0.35 + 0.65 * (distToLeft / EDGE_BAND);
    }
    if (!goingLeft && distToRight < EDGE_BAND) {
      return 0.35 + 0.65 * (distToRight / EDGE_BAND);
    }
    return 1.0;
  }, []);

  const computeGain = useCallback((omegaDegPerSec: number, currentTime: number, goingLeft: boolean): number => {
    const absOmega = Math.abs(omegaDegPerSec);
    if (absOmega < DEAD_ZONE) return 0;

    const clampedOmega = Math.max(OMEGA_SLOW, Math.min(OMEGA_FAST, absOmega));
    const normalized = (clampedOmega - OMEGA_SLOW) / (OMEGA_FAST - OMEGA_SLOW);
    let gain = GAIN_MIN + (GAIN_MAX - GAIN_MIN) * Math.pow(normalized, GAIN_GAMMA);

    const factor = computeMovementFactor(currentTime, goingLeft);
    gain *= factor;

    return gain;
  }, [computeMovementFactor]);

  useEffect(() => {
    const initialTime = INITIAL_TIME;
    timeMV.set(initialTime);
    if (dragRef.current) {
      dragRef.current.currentTime = initialTime;
    }
  }, [timeMV]);

  const scheduleUpdate = useCallback(() => {
    if (rafRef.current != null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const drag = dragRef.current;
      if (!drag || !drag.active) return;

      const now = performance.now();
      const ddx = drag.pointerX - drag.centerX;
      const ddy = drag.pointerY - drag.centerY;
      const currentAngle = Math.atan2(ddy, ddx) * (180 / Math.PI);

      let deltaAngle = currentAngle - drag.lastAngle;
      if (deltaAngle > 180) deltaAngle -= 360;
      if (deltaAngle < -180) deltaAngle += 360;

      const dt = Math.max(1, now - drag.lastTime);
      const omega = (deltaAngle / dt) * 1000;
      drag.omegaSmooth = EMA_ALPHA * omega + (1 - EMA_ALPHA) * drag.omegaSmooth;

      onKnobMove(drag.omegaSmooth, drag.currentTime);

      const goingLeft = deltaAngle < 0;
      const gain = computeGain(drag.omegaSmooth, drag.currentTime, goingLeft);

      let newTime = drag.currentTime;
      let newVisRot = drag.lastVisRotation;

      if (gain > 0) {
        const deltaTime = deltaAngle * gain;
        const rawNewTime = drag.currentTime + deltaTime;
        const maxOvershoot = 3.0;
        newTime = Math.max(MIN_TIME - maxOvershoot, Math.min(MAX_TIME + maxOvershoot, rawNewTime));

        const visFactor = computeMovementFactor(newTime, goingLeft);
        const visDelta = deltaAngle * visFactor;
        newVisRot = drag.lastVisRotation + visDelta;
      }

      drag.lastAngle = currentAngle;
      drag.lastVisRotation = newVisRot;
      drag.lastTime = now;
      drag.currentTime = newTime;
      visRotationRef.current = newVisRot;

      if (gain > 0) {
        visRotation.set(newVisRot);
        timeMV.set(newTime);
      }

      if (drag.active) scheduleUpdate();
    });
  }, [computeGain, computeMovementFactor, timeMV, onKnobMove]);

  const handlePointerDown = useCallback((clientX: number, clientY: number) => {
    if (!knobRef.current) return;
    onKnobStart();
    const rect = knobRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const angle = Math.atan2(clientY - centerY, clientX - centerX) * (180 / Math.PI);
    const currentTime = timeMV.get();

    dragRef.current = {
      active: true,
      centerX,
      centerY,
      lastAngle: angle,
      lastVisRotation: visRotationRef.current,
      lastTime: performance.now(),
      omegaSmooth: 0,
      currentTime,
      pointerX: clientX,
      pointerY: clientY,
    };
    setPressed(true);
    scheduleUpdate();
  }, [scheduleUpdate, timeMV, onKnobStart]);

  const handlePointerMove = useCallback((clientX: number, clientY: number) => {
    if (!dragRef.current?.active) return;
    dragRef.current.pointerX = clientX;
    dragRef.current.pointerY = clientY;
    scheduleUpdate();
  }, [scheduleUpdate]);

  const handlePointerUp = useCallback(() => {
    let finalTime = timeMV.get();
    if (dragRef.current) {
      dragRef.current.active = false;
      const t = dragRef.current.currentTime;
      if (t < MIN_TIME) {
        timeMV.set(MIN_TIME);
        dragRef.current.currentTime = MIN_TIME;
        finalTime = MIN_TIME;
      } else if (t > MAX_TIME) {
        timeMV.set(MAX_TIME);
        dragRef.current.currentTime = MAX_TIME;
        finalTime = MAX_TIME;
      } else {
        finalTime = t;
      }
    }
    setPressed(false);
    onKnobEnd(0, finalTime);
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, [timeMV, onKnobEnd]);

  useEffect(() => {
    const mm = (e: MouseEvent) => handlePointerMove(e.clientX, e.clientY);
    const mu = () => handlePointerUp();
    const tm = (e: TouchEvent) => {
      if (e.touches.length > 0) handlePointerMove(e.touches[0].clientX, e.touches[0].clientY);
    };
    const tu = () => handlePointerUp();
    window.addEventListener("mousemove", mm);
    window.addEventListener("mouseup", mu);
    window.addEventListener("touchmove", tm, { passive: true });
    window.addEventListener("touchend", tu);
    window.addEventListener("touchcancel", tu);
    return () => {
      window.removeEventListener("mousemove", mm);
      window.removeEventListener("mouseup", mu);
      window.removeEventListener("touchmove", tm);
      window.removeEventListener("touchend", tu);
      window.removeEventListener("touchcancel", tu);
    };
  }, [handlePointerMove, handlePointerUp]);

  const tickMarks = Array.from({ length: 30 }, (_, i) => {
    const angle = (i * 12 - 90) * (Math.PI / 180);
    return { angle, i };
  });

  const knobRotate = useTransform(
    [visRotation, introAngle],
    ([vr, ia]: number[]) => vr + ia
  );

  const isOn = phase === "on";

  return (
    <div ref={outerRef} style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    }}>
      <div
        ref={knobRef}
        style={{
          position: "relative",
          width: knobSize,
          height: knobSize,
          cursor: introRunning ? "pointer" : "grab",
          userSelect: "none",
          touchAction: "none",
        }}
        onMouseDown={e => {
          e.preventDefault();
          handlePointerDown(e.clientX, e.clientY);
        }}
        onTouchStart={e => {
          if (e.touches.length > 0) handlePointerDown(e.touches[0].clientX, e.touches[0].clientY);
        }}
      >
        {/* Socket (deep recessed groove) - fixed, does not move on press */}
        <div style={{
          position: "absolute",
          inset: socketInset,
          borderRadius: "50%",
          background: THEME.knob.socketBg,
          boxShadow: THEME.knob.socketShadow,
        }} />

        {/* Pressable knob inner: bezel + rotating face + highlights */}
        <div style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          transform: pressed ? "scale(0.975) translateY(2px)" : "scale(1)",
          transition: "transform 100ms ease",
        }}>
          {/* Bezel ring (fixed, non-rotating metal ring) */}
          <div style={{
            position: "absolute",
            inset: bezelInset,
            borderRadius: "50%",
            background: THEME.knob.bezelGradient,
            boxShadow: THEME.knob.bezelShadow,
          }} />

          {/* Rotating knob face */}
          <motion.div
            style={{
              position: "absolute",
              inset: faceInset,
              borderRadius: "50%",
              rotate: knobRotate,
              overflow: "hidden",
            }}
          >
            <div style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              background: THEME.knob.faceGradient,
              boxShadow: THEME.knob.faceShadow,
            }} />

            <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }} viewBox="0 0 100 100">
              {tickMarks.map(({ angle, i }) => {
                const outerR = 48;
                const innerR = 41;
                const x1 = 50 + Math.cos(angle) * outerR;
                const y1 = 50 + Math.sin(angle) * outerR;
                const x2 = 50 + Math.cos(angle) * innerR;
                const y2 = 50 + Math.sin(angle) * innerR;
                return (
                  <line
                    key={`tk-${i}`}
                    x1={x1} y1={y1} x2={x2} y2={y2}
                    stroke={THEME.knob.tickColor}
                    strokeWidth="0.6"
                    strokeLinecap="round"
                  />
                );
              })}
            </svg>

            {/* Fixed spherical dent (replaces indicator line) */}
            <div style={{
              position: "absolute",
              top: "14%",
              left: "50%",
              transform: "translateX(-50%)",
              width: "19%",
              aspectRatio: "1",
              borderRadius: "50%",
              pointerEvents: "none",
              background: "radial-gradient(ellipse at 50% 62%, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.32) 28%, rgba(0,0,0,0.14) 52%, rgba(0,0,0,0.04) 68%, transparent 80%)",
              boxShadow: "inset 0 2px 5px rgba(0,0,0,0.55), inset 0 -1px 2px rgba(255,255,255,0.04), 0 1px 1px rgba(0,0,0,0.3)",
            }}>
              <div style={{
                position: "absolute",
                top: "8%",
                left: "18%",
                right: "18%",
                height: "30%",
                borderRadius: "50%",
                background: "radial-gradient(ellipse at 50% 50%, rgba(255,255,255,0.06) 0%, transparent 70%)",
                pointerEvents: "none",
              }} />
            </div>
          </motion.div>

          {/* Fine surface grain (fixed, does not rotate) */}
          <div style={{
            pointerEvents: "none",
            position: "absolute",
            inset: faceInset,
            borderRadius: "50%",
            backgroundImage: THEME.knob.grainOverlay,
          }} />

          {/* Top highlight (fixed, simulates light source) */}
          <div style={{
            pointerEvents: "none",
            position: "absolute",
            inset: faceInset,
            borderRadius: "50%",
            background: THEME.knob.mainHighlight,
          }} />

          {/* Edge highlights/shadows (fixed) */}
          <div style={{
            pointerEvents: "none",
            position: "absolute",
            inset: faceInset,
            borderRadius: "50%",
            background: THEME.knob.edgeHighlight,
          }} />

          {/* Fine edge ring */}
          <div style={{
            pointerEvents: "none",
            position: "absolute",
            inset: faceInset,
            borderRadius: "50%",
            boxShadow: THEME.knob.edgeRingShadow,
          }} />

          {/* Intro pulse glow */}
          {introRunning && (
            <motion.div
              style={{
                pointerEvents: "none",
                position: "absolute", inset: -8,
                borderRadius: "50%",
                border: THEME.knob.introPulseBorder,
              }}
              animate={{ opacity: [0.2, 0.7, 0.2], scale: [1, 1.06, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   TUNER RADIO — Main component
   ============================================================ */
export interface TunerRadioHandle {
  start: () => void;
  resume: () => void;
}

export const TunerRadio = forwardRef<TunerRadioHandle>(function TunerRadio(_, ref) {
  const timeMV     = useMotionValue(INITIAL_TIME);
  const springTime = useSpring(timeMV, { stiffness: 180, damping: 30, mass: 1.0 });
  const timeVelocity = useVelocity(springTime);
  const { powerOn, setTuning, ensureContext, resumeAudio } = useRadioAudio();

  // App phases: 'intro' (swaying silently) → 'powering' (warm-up noise+screen flicker) → 'on'
  const [phase, setPhase] = useState<'intro' | 'powering' | 'on'>('intro');

  // Year-crossing jolt: briefly offset pointer by ±3px when crossing year boundary
  const yearJolt = useMotionValue(0);
  const lastYearRef = useRef(INITIAL_TIME);
  const joltRafRef = useRef<number | null>(null);
  useMotionValueEvent(springTime, "change", v => {
    const year = Math.round(v);
    if (year !== lastYearRef.current) {
      const dir = year > lastYearRef.current ? 1 : -1;
      lastYearRef.current = year;
      if (joltRafRef.current) cancelAnimationFrame(joltRafRef.current);
      // Sharp jolt forward, then spring back
      yearJolt.set(dir * YEAR_JOLT_DISTANCE);
      animate(yearJolt, 0, { type: "spring", stiffness: 500, damping: 28, mass: 0.6 });
    }
  });

  // First-run intro: dial sways ±30° at double speed to attract attention, display stays still
  const introAngle = useMotionValue(0);
  const introRunning = phase === 'intro';

  useEffect(() => {
    if (!introRunning) return;
    let start: number | null = null;
    let rafId: number;
    const SWAY_AMP = 30;         // ±30° — eye-catching motion to draw user attention
    const SWAY_PERIOD = 2600;    // 2.6s per cycle (double the speed of previous 5.2s)
    // Display stays still during intro — only the dial sways
    const loop = (t: number) => {
      if (start == null) start = t;
      const elapsed = t - start;
      const phase = (elapsed % SWAY_PERIOD) / SWAY_PERIOD;
      // Use a slightly non-sinusoidal curve for more organic motion (ease-in-out)
      const s = Math.sin(phase * Math.PI * 2);
      const angle = s * SWAY_AMP;
      introAngle.set(angle);
      rafId = requestAnimationFrame(loop);
    };
    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, [introRunning, introAngle]);

  const endIntro = useCallback(() => {
    if (phase !== 'intro') return;
    setPhase('powering');
    introAngle.set(0, true);
    const midTime = INITIAL_TIME;
    timeMV.set(midTime);
    powerOn();
    setTimeout(() => setPhase('on'), 1300);
  }, [phase, introAngle, timeMV, powerOn]);

  const resumePlayback = useCallback(() => {
    resumeAudio();
    if (phase === 'on' && !isDraggingRef.current) {
      setTuning(0, springTime.get());
    }
  }, [phase, resumeAudio, setTuning, springTime]);

  useImperativeHandle(ref, () => ({
    start: () => endIntro(),
    resume: () => resumePlayback(),
  }), [endIntro, resumePlayback]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && phase === 'on') {
        setTimeout(() => {
          resumeAudio();
          if (!isDraggingRef.current) {
            setTuning(0, springTime.get());
          }
        }, 200);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [phase, resumeAudio, setTuning, springTime]);

  const isDraggingRef = useRef(false);

  const handleKnobStart = useCallback(() => {
    isDraggingRef.current = true;
    ensureContext();
    endIntro();
  }, [endIntro, ensureContext]);

  const handleKnobMove = useCallback((omega: number, currentTime: number) => {
    setTuning(omega, currentTime);
  }, [setTuning]);

  const handleKnobEnd = useCallback((_omega: number, finalTime: number) => {
    isDraggingRef.current = false;
    setTuning(0, finalTime);
  }, [setTuning]);

  useMotionValueEvent(springTime, "change", (v) => {
    if (!isDraggingRef.current && (phase === 'on' || phase === 'powering')) {
      setTuning(0, v);
    }
  });

  return (
    <div style={{
      width: "100%",
      height: "100dvh",
      margin: "0 auto",
      display: "grid",
      gridTemplateRows: GRID_ROWS,
      position: "relative",
      background: THEME.bg.gradient,
      overflow: "hidden",
      paddingTop: "env(safe-area-inset-top, 0px)",
      paddingBottom: "env(safe-area-inset-bottom, 0px)",
      boxSizing: "border-box",
    }}>
      <div style={{
        pointerEvents: "none", position: "absolute", inset: 0,
        opacity: THEME.bg.noiseOpacity,
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)'/%3E%3C/svg%3E\")",
      }} />

      {/* Row 1: Status bar */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 24px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: THEME.statusBar.iconColor }}>
          <Signal size={15} strokeWidth={2.5} />
          <Wifi size={15} strokeWidth={2.5} />
          <BatteryFull size={18} strokeWidth={2} />
        </div>
        <div style={{
          display: "flex", alignItems: "center", gap: 4,
          padding: "4px 10px", borderRadius: 9999,
          background: THEME.statusBar.buttonBg,
          boxShadow: THEME.statusBar.buttonShadow,
        }}>
          <MoreHorizontal size={15} style={{ color: THEME.statusBar.iconColor }} />
        </div>
      </div>

      {/* Row 2: Speaker */}
      <Speaker springTime={springTime} phase={phase} />

      {/* Row 3: Gap */}
      <div />

      {/* Row 4: Display */}
      <Display springTime={springTime} timeVelocity={timeVelocity} phase={phase} yearJolt={yearJolt} />

      {/* Row 5: Knob */}
      <Knob
        timeMV={timeMV}
        onKnobStart={handleKnobStart}
        onKnobMove={handleKnobMove}
        onKnobEnd={handleKnobEnd}
        introRunning={introRunning}
        introAngle={introAngle}
        phase={phase}
      />
    </div>
  );
});
