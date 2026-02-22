/**
 * NotificationBanner — E5: Request browser notification permission on app start.
 *
 * Shows a non-blocking banner if Notification API is supported and permission
 * is not yet granted or denied. User can grant, dismiss, or permanently
 * dismiss. State is persisted in sessionStorage so it doesn't re-appear
 * mid-session after dismissal.
 *
 * Also plays a subtle audio beep on each new signal using the Web Audio API
 * (no external file needed — generated programmatically).
 */
import { useState, useEffect } from "react";
import { useWebSocket } from "../context/WebSocketContext";

// ── Audio beep generator ───────────────────────────────────────────────────
function playSignalBeep(type = "BUY") {
  try {
    const ctx  = new (window.AudioContext || window.webkitAudioContext)();
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    // BUY → rising two-tone, SELL → falling
    const freqs = type === "BUY" ? [440, 554] : [554, 440];
    osc.frequency.setValueAtTime(freqs[0], ctx.currentTime);
    osc.frequency.setValueAtTime(freqs[1], ctx.currentTime + 0.12);
    gain.gain.setValueAtTime(0.18, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.35);
  } catch {
    // Audio not available — silent fallback
  }
}

export function useSignalAudio() {
  const { lastSignal } = useWebSocket();
  useEffect(() => {
    if (!lastSignal) return;
    playSignalBeep(lastSignal.signal_type || lastSignal.type);
  }, [lastSignal]);
}

// ── Notification permission banner ─────────────────────────────────────────
export default function NotificationBanner() {
  const [visible, setVisible] = useState(false);
  const [granted, setGranted] = useState(false);

  useEffect(() => {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") { setGranted(true); return; }
    if (Notification.permission === "denied")  return;
    // "default" — show banner unless user already dismissed this session
    if (sessionStorage.getItem("notif-dismissed")) return;
    setVisible(true);
  }, []);

  const requestPermission = async () => {
    const result = await Notification.requestPermission();
    setGranted(result === "granted");
    setVisible(false);
    if (result === "granted") {
      new Notification("Pro Terminal — Alerts Active 🔔", {
        body: "You'll receive BUY/SELL signal notifications here.",
        icon: "/favicon.ico",
      });
    }
  };

  const dismiss = () => {
    sessionStorage.setItem("notif-dismissed", "1");
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="notif-banner">
      <span className="notif-icon">🔔</span>
      <span className="notif-text">
        Enable browser notifications to get real-time BUY/SELL signal alerts even
        when this tab is in the background.
      </span>
      <button className="notif-allow" onClick={requestPermission}>
        Allow Notifications
      </button>
      <button className="notif-dismiss" onClick={dismiss} title="Dismiss for this session">
        ✕
      </button>
    </div>
  );
}

export { playSignalBeep };
