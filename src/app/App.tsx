import { useEffect, useRef, useState } from "react";
import { TunerRadio, type TunerRadioHandle } from "./components/tuner-radio";

const STARTED_KEY = "timetune_started";

export default function App() {
  const radioRef = useRef<TunerRadioHandle>(null);
  const [started, setStarted] = useState(() => {
    try {
      return sessionStorage.getItem(STARTED_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (started) {
      try {
        sessionStorage.setItem(STARTED_KEY, "1");
      } catch {}
      setTimeout(() => radioRef.current?.start(), 0);
    }
  }, [started]);

  useEffect(() => {
    const handlePageShow = (e: PageTransitionEvent) => {
      if (e.persisted && started) {
        setTimeout(() => radioRef.current?.resume(), 100);
      }
    };
    window.addEventListener("pageshow", handlePageShow);
    return () => window.removeEventListener("pageshow", handlePageShow);
  }, [started]);

  const handleStart = () => {
    setStarted(true);
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100dvh",
        background: "#120e08",
        position: "relative",
        overflow: "hidden",
        overscrollBehavior: "none",
        WebkitOverflowScrolling: "auto",
        touchAction: "none",
      }}
    >
      <TunerRadio ref={radioRef} />

      {!started && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "radial-gradient(ellipse at 50% 40%, #1e1810 0%, #120e08 60%, #0a0805 100%)",
            padding: "40px 24px",
            touchAction: "none",
            overscrollBehavior: "none",
          }}
          onClick={handleStart}
        >
          <div
            style={{
              fontSize: "clamp(48px, 14vw, 80px)",
              marginBottom: "16px",
              filter: "drop-shadow(0 2px 8px rgba(255,180,60,0.3))",
            }}
          >
            📻
          </div>
          <div
            style={{
              fontSize: "clamp(24px, 6vw, 36px)",
              fontWeight: 700,
              color: "#e8d5b5",
              textAlign: "center",
              marginBottom: "8px",
              letterSpacing: "0.1em",
              textShadow: "0 1px 4px rgba(0,0,0,0.8)",
            }}
          >
            时光调频
          </div>
          <div
            style={{
              fontSize: "clamp(14px, 3.5vw, 18px)",
              color: "#9a8a6a",
              textAlign: "center",
              marginBottom: "48px",
              lineHeight: 1.6,
              maxWidth: "320px",
            }}
          >
            转动旋钮，穿越回1949-1960年代
            <br />
            收听属于那个年代的广播
          </div>
          <button
            type="button"
            onClick={handleStart}
            style={{
              width: "min(80vw, 320px)",
              height: "64px",
              border: "none",
              borderRadius: "32px",
              fontSize: "clamp(18px, 5vw, 24px)",
              fontWeight: 600,
              color: "#1a1208",
              background: "linear-gradient(180deg, #e8c76b 0%, #c9a23e 50%, #a8832a 100%)",
              boxShadow:
                "0 4px 16px rgba(200,160,50,0.35), inset 0 1px 0 rgba(255,255,255,0.3), inset 0 -1px 0 rgba(0,0,0,0.2)",
              cursor: "pointer",
              letterSpacing: "0.08em",
              WebkitTapHighlightColor: "transparent",
              touchAction: "manipulation",
            }}
          >
            点击开始收听
          </button>
          <div
            style={{
              fontSize: "12px",
              color: "#5a4f3a",
              marginTop: "20px",
              textAlign: "center",
            }}
          >
            请打开声音 · 建议佩戴耳机
          </div>
        </div>
      )}
    </div>
  );
}
