import { useCallback, useEffect, useRef, useState } from "react";

const PANELS = ["Task", "Trace", "Eval"] as const;

export function useDeck() {
  const deckRef = useRef<HTMLElement>(null);
  const segRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const [activePanel, setActivePanel] = useState(0);

  const paintPeek = useCallback(() => {
    const deck = deckRef.current;
    if (!deck) return;
    const cc = deck.scrollLeft + deck.clientWidth / 2;
    [...deck.children].forEach((p) => {
      const el = p as HTMLElement;
      const d = Math.min(1, Math.abs(el.offsetLeft + el.offsetWidth / 2 - cc) / deck.clientWidth);
      el.style.opacity = (1 - 0.45 * d).toFixed(3);
      el.style.transform = `scale(${(1 - 0.06 * d).toFixed(3)})`;
    });
  }, []);

  const updateSeg = useCallback(() => {
    const deck = deckRef.current;
    const segmented = segRef.current;
    const segTrack = trackRef.current;
    if (!deck || !segmented || !segTrack) return;
    const cc = deck.scrollLeft + deck.clientWidth / 2;
    const centers = [...deck.children].map((p) => {
      const el = p as HTMLElement;
      return el.offsetLeft + el.offsetWidth / 2;
    });
    if (!centers.length) return;
    let frac = 0;
    if (cc <= centers[0]) frac = 0;
    else if (cc >= centers[centers.length - 1]) frac = centers.length - 1;
    else {
      for (let i = 0; i < centers.length - 1; i++) {
        if (cc >= centers[i] && cc <= centers[i + 1]) {
          frac = i + (cc - centers[i]) / (centers[i + 1] - centers[i]);
          break;
        }
      }
    }
    const segs = [...segTrack.children] as HTMLElement[];
    const segCenters = segs.map((s) => s.offsetLeft + s.offsetWidth / 2);
    const i = Math.floor(frac);
    const f = frac - i;
    const c =
      i + 1 < segCenters.length
        ? segCenters[i] + (segCenters[i + 1] - segCenters[i]) * f
        : segCenters[i];
    segTrack.style.setProperty("--shift", `${segmented.clientWidth / 2 - c}px`);
    const idx = Math.round(frac);
    setActivePanel(idx);
    segs.forEach((b, k) => b.classList.toggle("active", k === idx));
  }, []);

  const setPanel = useCallback(
    (idx: number, scroll = true) => {
      const deck = deckRef.current;
      if (!deck) return;
      const clamped = Math.max(0, Math.min(2, idx));
      setActivePanel(clamped);
      if (scroll) {
        const panel = deck.children[clamped] as HTMLElement | undefined;
        if (panel) {
          const target = panel.offsetLeft - (deck.clientWidth - panel.offsetWidth) / 2;
          deck.scrollTo({ left: target, behavior: "smooth" });
        }
      }
      paintPeek();
      updateSeg();
    },
    [paintPeek, updateSeg],
  );

  useEffect(() => {
    const deck = deckRef.current;
    if (!deck) return;
    const onScroll = () => {
      paintPeek();
      updateSeg();
    };
    deck.addEventListener("scroll", onScroll, { passive: true });
    const onResize = () => {
      paintPeek();
      updateSeg();
    };
    window.addEventListener("resize", onResize);
    paintPeek();
    updateSeg();
    return () => {
      deck.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
    };
  }, [paintPeek, updateSeg]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setPanel(activePanel + 1);
      else if (e.key === "ArrowLeft") setPanel(activePanel - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activePanel, setPanel]);

  return { deckRef, segRef, trackRef, activePanel, setPanel, panels: PANELS };
}
