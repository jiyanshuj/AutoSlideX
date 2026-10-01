import React, { useRef, useState, useEffect, useCallback } from "react";

// Small local replacement for shadcn's cn()
const cn = (...c) => c.filter(Boolean).join(" ");

const SPRING = "cubic-bezier(0.175, 0.885, 0.32, 1.275)";
const SPRING_TRANSITION = `max-width 0.4s ${SPRING}, height 0.4s ${SPRING}`;
const SMOOTH_TRANSITION = `max-width 0.4s ${SPRING}, height 0.15s ease-out`;

function MorphingText({ text }) {
  const [width, setWidth] = useState("auto");
  const spanRef = useRef(null);

  useEffect(() => {
    if (spanRef.current) setWidth(spanRef.current.offsetWidth);
  }, [text]);

  return (
    <span
      className="relative inline-flex items-center justify-center overflow-hidden"
      style={{ width, transition: `width 0.3s ${SPRING}` }}
    >
      <span ref={spanRef} className="invisible whitespace-nowrap px-1">{text}</span>
      <span key={text} className="pi-fade absolute inset-0 flex items-center justify-center whitespace-nowrap">
        {text}
      </span>
    </span>
  );
}

const ArrowUpIcon = () => (
  <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <path d="M7 12V2M7 2L2.5 6.5M7 2L11.5 6.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const MicIcon = () => (
  <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <rect x="5" y="1" width="4" height="7" rx="2" stroke="currentColor" strokeWidth="1.5" />
    <path d="M2.75 6.5V7a4.25 4.25 0 0 0 8.5 0v-.5M7 11.25V13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);
const StopIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" fill="currentColor" />
  </svg>
);
const SpinnerIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="animate-spin" aria-hidden="true">
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
    <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
);
const MinusIcon = () => (
  <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <path d="M2.5 7H11.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
  </svg>
);
const PlusIcon = () => (
  <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <path d="M7 2.5V11.5M2.5 7H11.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
  </svg>
);
const SlidesIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <rect x="1.5" y="2.5" width="11" height="7.5" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
    <path d="M5 12.5H9M7 10V12.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
);

/**
 * Animated prompt input.
 * Props:
 *  value / onChange        controlled topic text
 *  slides / onSlidesChange controlled slide count
 *  onSubmit(value, {slides})
 *  loading                 shows spinner + disables input
 */
export default function PromptInput({
  value = "",
  onChange,
  slides = 5,
  onSlidesChange,
  alwaysExpanded = false,
  fullWidth = false,
  minSlides = 3,
  maxSlides = 20,
  onSubmit,
  loading = false,
  placeholder = "Enter your presentation topic...",
  bottomContent = null,
  className,
}) {
  const [expanded, setExpanded] = useState(alwaysExpanded);
  const [smooth, setSmooth] = useState(false);
  const [containerHeight, setContainerHeight] = useState(116);
  const [textareaHeight, setTextareaHeight] = useState(68);
  const [isScrolling, setIsScrolling] = useState(false);

  const [isRecording, setIsRecording] = useState(false);
  const [audioData, setAudioData] = useState(new Array(5).fill(0));

  const textareaRef = useRef(null);
  const wrapRef = useRef(null);
  const topFadeRef = useRef(null);
  const bottomFadeRef = useRef(null);
  const valueRef = useRef(value);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const rafRef = useRef(null);
  const recognitionRef = useRef(null);

  const hasValue = value.trim() !== "";
  const speechSupported =
    typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

  useEffect(() => { valueRef.current = value; }, [value]);

  const updateFades = () => {
    const el = textareaRef.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    if (topFadeRef.current) topFadeRef.current.style.opacity = Math.min(scrollTop / 20, 1);
    if (bottomFadeRef.current) {
      const b = scrollHeight - clientHeight - scrollTop;
      bottomFadeRef.current.style.opacity = Math.min(Math.max(b - 16, 0) / 10, 1);
    }
  };

  const setValue = useCallback((v) => { setSmooth(true); onChange?.(v); }, [onChange]);

  const changeSlides = (delta) => (e) => {
    e.stopPropagation();
    const next = Math.min(maxSlides, Math.max(minSlides, slides + delta));
    if (next !== slides) onSlidesChange?.(next);
  };

  // ---------- Voice ----------
  const stopRecording = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    setIsRecording(false);
    setAudioData(new Array(5).fill(0));
  }, []);

  const startRecording = useCallback(async () => {
    if (!speechSupported) return;
    setSmooth(false);
    setExpanded(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      audioCtxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(data);
        const step = Math.floor(data.length / 5);
        const bands = Array.from({ length: 5 }, (_, i) => {
          let s = 0;
          for (let j = 0; j < step; j++) s += data[i * step + j];
          return s / step / 255;
        });
        setAudioData(bands);
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();

      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new SR();
      rec.continuous = true;
      rec.interimResults = true;
      let baseline = valueRef.current;
      rec.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) baseline += (baseline ? " " : "") + t;
          else interim += t;
        }
        setValue((baseline + (interim ? " " + interim : "")).trim());
      };
      rec.onerror = stopRecording;
      rec.onend = stopRecording;
      recognitionRef.current = rec;
      rec.start();
      setIsRecording(true);
    } catch {
      stopRecording(); // mic denied/unavailable
    }
  }, [speechSupported, setValue, stopRecording]);

  useEffect(() => () => stopRecording(), [stopRecording]);

  useEffect(() => {
    if (isRecording && textareaRef.current) textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
  }, [value, isRecording]);

  // ---------- Layout ----------
  useEffect(() => {
    if (hasValue && !expanded) { setSmooth(false); setExpanded(true); }
  }, [hasValue, expanded]);

  useEffect(() => {
    if (expanded && !isRecording && !loading) {
      const t = setTimeout(() => {
        const el = textareaRef.current;
        if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
      }, 50);
      return () => clearTimeout(t);
    }
  }, [expanded, isRecording, loading]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    const current = el.style.height;
    el.style.transition = "none";
    el.style.height = "0px";
    const sh = el.scrollHeight;
    el.style.height = current;
    void el.offsetHeight;
    el.style.transition = "";
    const h = Math.max(68, Math.min(sh, 160));
    el.style.height = `${h}px`;
    setTextareaHeight(h);
    setIsScrolling(sh > 160);
    setTimeout(updateFades, 0);
  }, [value, expanded]);

  useEffect(() => {
    setContainerHeight(Math.max(116, textareaHeight + 48));
    setTimeout(updateFades, 0);
  }, [textareaHeight]);

  const handleBlur = (e) => {
    if (wrapRef.current?.contains(e.relatedTarget)) return;
    if (!alwaysExpanded && !hasValue && !isRecording) { setSmooth(false); setExpanded(false); }
  };

  const submit = () => {
    if (!hasValue || loading) return;
    setSmooth(false);
    onSubmit?.(value, { slides });
  };

  const showSpinner = loading;
  const showArrow = hasValue && !isRecording && !loading;
  const showStop = isRecording && !loading;
  const showMic = !hasValue && !isRecording && !loading;

  const onAction = (e) => {
    e.preventDefault();
    if (loading) return;
    if (isRecording) stopRecording();
    else if (hasValue) submit();
    else startRecording();
  };

  const iconLayer = (visible, rot) =>
    cn(
      "absolute inset-0 flex items-center justify-center transition-all duration-300",
      visible ? "opacity-100 scale-100 rotate-0" : `opacity-0 scale-50 ${rot} pointer-events-none`
    );

  const stepBtn =
    "flex size-6 items-center justify-center rounded-full text-stone-400 transition-all duration-200 hover:bg-white/10 hover:text-stone-50 outline-none disabled:opacity-30 disabled:pointer-events-none";

  return (
    <div
      ref={wrapRef}
      onBlur={handleBlur}
      className={cn("flowstack-prompt relative flex w-full flex-col", !fullWidth && "mx-auto", className)}
      style={{
        maxWidth: fullWidth ? "100%" : expanded ? 480 : 320,
        transition: smooth ? "max-width 0.15s ease-out" : `max-width 0.4s ${SPRING}`,
      }}
    >
      <style>{`
        @keyframes pi-fade { from { opacity: 0; transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }
        .pi-fade { animation: pi-fade 0.3s ease-out; }
        .pi-scroll::-webkit-scrollbar { width: 4px; background: transparent; }
        .pi-scroll::-webkit-scrollbar-thumb { background: transparent; border-radius: 4px; }
        .pi-scroll:hover::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.25); }
      `}</style>

      <div
        onMouseDown={(e) => {
          if (expanded && e.target !== textareaRef.current && !isRecording) {
            e.preventDefault();
            textareaRef.current?.focus();
          }
        }}
        style={{
          borderRadius: 24,
          height: expanded ? containerHeight : 48,
          transition: smooth ? SMOOTH_TRANSITION : SPRING_TRANSITION,
          overflow: expanded ? "visible" : "hidden",
        }}
        className={cn(
          "relative z-10 w-full border border-stone-700 bg-stone-900/80 shadow-sm backdrop-blur-sm",
          "focus-within:border-[#e0a458]/70 focus-within:ring-2 focus-within:ring-[#e0a458]/15 hover:border-stone-600",
          expanded ? "cursor-text" : "cursor-default"
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onScroll={updateFades}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
            if (e.key === "Escape" && !hasValue && !alwaysExpanded) { setSmooth(false); setExpanded(false); }
          }}
          placeholder={placeholder}
          aria-label="Presentation topic"
          disabled={isRecording || loading}
          style={{
            transition: smooth
              ? "height 0.15s ease-out"
              : `opacity 0.3s ease-out, transform 0.3s ease-out, height 0.4s ${SPRING}`,
          }}
          className={cn(
            "pi-scroll absolute inset-x-0 top-0 z-[1] w-full resize-none bg-transparent py-3.5 pl-4 pr-12 text-sm leading-[22px] text-stone-50 outline-none placeholder:font-medium placeholder:text-stone-500",
            expanded ? "opacity-100 scale-100 translate-y-0" : "opacity-0 scale-95 -translate-y-1 pointer-events-none",
            isScrolling ? "overflow-y-auto" : "overflow-y-hidden"
          )}
        />

        <div ref={topFadeRef} className="pointer-events-none absolute left-4 right-12 top-0 z-[2] h-8 bg-gradient-to-b from-stone-900 to-transparent" style={{ opacity: 0 }} />
        <div
          ref={bottomFadeRef}
          className="pointer-events-none absolute left-4 right-12 z-[2] h-8 bg-gradient-to-t from-stone-900 to-transparent"
          style={{ opacity: 0, top: `${textareaHeight - 32}px`, transition: smooth ? "top 0.15s ease-out" : `top 0.4s ${SPRING}` }}
        />

        {/* Collapsed placeholder */}
        <button
          type="button"
          onClick={() => { setSmooth(false); setExpanded(true); }}
          style={{ transition: smooth ? "none" : `all 0.4s ${SPRING}` }}
          className={cn(
            "absolute inset-x-0 top-0 z-[1] cursor-text py-[15px] pl-4 pr-12 text-left text-sm font-medium leading-[17px] text-stone-500 outline-none",
            !expanded ? "opacity-100 scale-100 translate-y-0" : "opacity-0 scale-105 translate-y-1 pointer-events-none"
          )}
          aria-label="Open prompt input"
        >
          {placeholder}
        </button>

        {/* Bottom bar: slide-count stepper */}
        <div
          className={cn(
            "absolute bottom-2 left-3 right-12 z-[10] flex items-center transition-all duration-300",
            expanded && !isRecording ? "opacity-100 translate-y-0 pointer-events-auto" : "opacity-0 translate-y-2 pointer-events-none"
          )}
        >
          <div className="flex items-center gap-1 rounded-full px-1 py-0.5 text-stone-400">
            <button type="button" aria-label="Fewer slides" disabled={slides <= minSlides || loading}
              onMouseDown={(e) => e.preventDefault()} onClick={changeSlides(-1)} className={stepBtn}>
              <MinusIcon />
            </button>
            <span className="flex items-center gap-1.5 text-xs font-semibold text-stone-300 select-none">
              <SlidesIcon />
              <MorphingText text={`${slides} slides`} />
            </span>
            <button type="button" aria-label="More slides" disabled={slides >= maxSlides || loading}
              onMouseDown={(e) => e.preventDefault()} onClick={changeSlides(1)} className={stepBtn}>
              <PlusIcon />
            </button>
          </div>
          {bottomContent}
        </div>

        {/* Voice visualizer */}
        <div
          className={cn(
            "absolute bottom-2 right-12 z-[10] flex h-8 items-center justify-end gap-[3px] transition-all duration-300",
            isRecording ? "w-16 opacity-100 translate-x-0" : "w-0 opacity-0 translate-x-4 pointer-events-none"
          )}
        >
          {audioData.map((v, i) => (
            <div key={i} className="w-1 rounded-full bg-[#e0a458] transition-[height] duration-75 ease-out"
              style={{ height: `${Math.max(4, v * 24)}px` }} />
          ))}
        </div>

        {/* Action button */}
        <button
          type="button"
          onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onClick={onAction}
          disabled={!hasValue && !speechSupported && !isRecording}
          aria-label={showArrow ? "Generate outline" : showStop ? "Stop recording" : showSpinner ? "Generating" : "Use voice input"}
          className={cn(
            "absolute bottom-2 right-2 z-[10] flex h-8 w-8 items-center justify-center rounded-full bg-[#e0a458] text-stone-950 active:scale-95 transition-all duration-300 outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-[#e0a458]",
            !hasValue && !speechSupported && !isRecording && !loading && "opacity-40 pointer-events-none"
          )}
        >
          <span className="relative flex h-full w-full items-center justify-center">
            <span className={iconLayer(showArrow, "rotate-45")}><ArrowUpIcon /></span>
            <span className={iconLayer(showMic, "-rotate-45")}><MicIcon /></span>
            <span className={iconLayer(showStop, "rotate-45")}><StopIcon /></span>
            <span className={iconLayer(showSpinner, "rotate-0")}><SpinnerIcon /></span>
          </span>
        </button>
      </div>
    </div>
  );
}

export { PromptInput };