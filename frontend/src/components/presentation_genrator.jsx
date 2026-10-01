import React, { useEffect, useRef, useState } from 'react';
import PromptInput from './ai-chat-input';
import { FileText, Download, Edit2, Plus, Trash2, Save, Loader, CheckCircle2, ChevronDown } from 'lucide-react';

const API_URL = 'https://autoslidex-wvg0.onrender.com/api';

const VERTEX_SHADER = `attribute vec2 p; void main(){ gl_Position = vec4(p,0.,1.); }`;

const FRAGMENT_SHADER = `
precision highp float;
uniform vec2 u_res;
uniform float u_time;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }
float noise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  f = f*f*(3.-2.*f);
  return mix(mix(hash(i), hash(i+vec2(1,0)), f.x),
             mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y);
}
float fbm(vec2 p){
  float v = 0., a = .5;
  for(int i=0;i<3;i++){ v += a*noise(p); p = p*2.02 + 7.3; a *= .5; }
  return v;
}

vec3 ramp(float t){
  vec3 c0 = vec3(0.016,0.016,0.016);
  vec3 c1 = vec3(0.22,0.155,0.11);
  vec3 c2 = vec3(0.52,0.45,0.39);
  vec3 c3 = vec3(0.80,0.78,0.78);
  vec3 c4 = vec3(0.97,0.96,0.96);
  vec3 c = mix(c0, c1, smoothstep(0.18, 0.42, t));
  c = mix(c, c2, smoothstep(0.48, 0.66, t));
  c = mix(c, c3, smoothstep(0.64, 0.82, t));
  c = mix(c, c4, smoothstep(0.80, 0.97, t));
  return c;
}

void main(){
  vec2 uv = gl_FragCoord.xy / u_res.xy;
  vec2 p = (gl_FragCoord.xy - .5*u_res.xy) / u_res.y;
  float t = u_time * 0.07;

  // Flow direction: lower-left -> upper-right
  vec2 d = normalize(vec2(0.82, 0.57));
  vec2 n = vec2(-d.y, d.x);
  float A = dot(p, d);
  float B = dot(p, n);

  // Slow, smooth warp that also drifts along the flow direction
  float wn = fbm(p * 0.9 + vec2(3.1, 1.7) - d * t * 0.6);
  float w = 0.34 * sin(B * 2.3 + A * 0.9 - t * 1.1)
          + 0.20 * sin(B * 3.9 - A * 1.4 + t * 0.8)
          + 0.55 * (wn - 0.5);

  // Silky ribbons that travel toward the upper-right
  float band  = 0.5 + 0.5 * sin(((A + w) * 1.55 - t) * 3.14159);
  float band2 = 0.5 + 0.5 * sin((A * 0.7 - w * 0.8) * 2.4 - t * 0.7 + 1.3);
  float f = band * 0.55 + band2 * 0.25 + A * 0.35 + 0.12;
  float v = smoothstep(0.10, 1.0, f) * 0.97;

  // Thin dark outline along ribbon edges
  float rim = smoothstep(0.0, 0.04, abs(v - 0.56));
  v = mix(v, v * 0.30, (1. - rim) * 0.85);

  vec3 col = ramp(v);

  // Keep the area behind the title readable
  vec2 tc = vec2((uv.x - 0.5) * 1.3, (uv.y - 0.55) * 2.0);
  col *= 1.0 - 0.30 * exp(-dot(tc, tc) * 3.0);

  col *= smoothstep(0.0, 0.40, uv.y) * 0.9 + 0.1;
  col *= 1.0 - 0.45 * dot(uv - .5, uv - .5) * 2.2;

  // Twinkling stars
  vec2 sg = floor(gl_FragCoord.xy / 3.0);
  float s = step(0.9972, hash(sg));
  col += s * (0.35 + 0.65 * hash(sg + 3.1)) * (0.6 + 0.4 * sin(u_time * 1.4 + hash(sg) * 40.));

  gl_FragColor = vec4(col, 1.0);
}`;

const AnimatedBackground = () => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext('webgl', { antialias: false, alpha: false });
    if (!gl) return undefined;

    const compileShader = (type, source) => {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('Shader compile error:', gl.getShaderInfoLog(shader));
      }
      return shader;
    };

    const program = gl.createProgram();
    gl.attachShader(program, compileShader(gl.VERTEX_SHADER, VERTEX_SHADER));
    gl.attachShader(program, compileShader(gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return undefined;
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'p');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    const resolution = gl.getUniformLocation(program, 'u_res');
    const time = gl.getUniformLocation(program, 'u_time');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const scale = Math.min(window.devicePixelRatio || 1, 1.5) * 0.75;

    const resize = () => {
      canvas.width = Math.floor(window.innerWidth * scale);
      canvas.height = Math.floor(window.innerHeight * scale);
      gl.viewport(0, 0, canvas.width, canvas.height);
      if (reduceMotion && draw) draw();
    };
    let draw;
    resize();
    window.addEventListener('resize', resize);

    let animationFrame;
    const start = performance.now();
    draw = () => {
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform1f(time, reduceMotion ? 8 : (performance.now() - start) / 1000 + 8);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      if (!reduceMotion && !document.hidden) animationFrame = requestAnimationFrame(draw);
    };
    draw();

    const handleVisibility = () => {
      if (!document.hidden && !reduceMotion) {
        cancelAnimationFrame(animationFrame);
        draw();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', handleVisibility);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="fixed inset-0 z-0 h-full w-full"
      style={{ background: 'radial-gradient(80% 60% at 75% 10%, #cfcbc8 0%, #3a2e26 45%, #050505 100%)' }}
    />
  );
};

const STEPS = [
  { id: 'input',    label: 'Describe',  desc: 'Enter your topic & settings' },
  { id: 'edit',     label: 'Refine',    desc: 'Review & edit slide outline' },
  { id: 'download', label: 'Export',    desc: 'Download your PowerPoint' },
];

function WorkflowStepper({ step }) {
  const current = STEPS.findIndex(s => s.id === step);
  return (
    <div className="workflow-stepper max-w-5xl mx-auto mb-10">
      {STEPS.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <React.Fragment key={s.id}>
            <div className={`workflow-step ${active ? 'active' : ''} ${done ? 'done' : ''}`}>
              <div className="workflow-badge">
                {done
                  ? <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 7.5L5.8 10L11 4" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  : <span>{i + 1}</span>
                }
              </div>
              <div className="workflow-text">
                <span className="workflow-label">{s.label}</span>
                <span className="workflow-desc">{s.desc}</span>
              </div>
            </div>
            {i < STEPS.length - 1 && <div className={`workflow-connector ${done ? 'done' : ''}`} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default function PresentationGenerator() {
  const [step, setStep] = useState('input');
  const [topic, setTopic] = useState('');
  const [numSlides, setNumSlides] = useState(5);
  const [additionalContext, setAdditionalContext] = useState('');
  const [presentationId, setPresentationId] = useState('');
  const [slides, setSlides] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showContext, setShowContext] = useState(false);
  const [editingSlide, setEditingSlide] = useState(null);
  const [presentationTitle, setPresentationTitle] = useState('');

  const generateOutline = async () => {
    if (!topic.trim()) {
      setError('Please enter a topic');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/generate-outline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          num_slides: numSlides,
          additional_context: showContext ? additionalContext : ''
        })
      });

      const data = await response.json();

      if (data.success) {
        setPresentationId(data.presentation_id);
        setSlides(data.data.slides);
        setPresentationTitle(data.data.title);
        setStep('edit');
      } else {
        setError('Failed to generate outline');
      }
    } catch (err) {
      setError('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateSlides = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/update-slides`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          presentation_id: presentationId,
          slides: slides
        })
      });

      const data = await response.json();

      if (data.success) {
        setNotice('Changes saved.');
        setTimeout(() => setNotice(''), 2500);
      } else {
        setError('Failed to update');
      }
    } catch (err) {
      setError('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const generatePPT = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/generate-ppt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          presentation_id: presentationId,
          template: 'modern',
          export_format: 'pptx'
        })
      });

      const data = await response.json();

      if (data.success) {
        setStep('download');
      } else {
        setError('Failed to generate');
      }
    } catch (err) {
      setError('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadPresentation = () => {
    window.open(`${API_URL}/download/${presentationId}`, '_blank');
  };

  const updateSlideContent = (slideIndex, field, value) => {
    const updatedSlides = [...slides];
    updatedSlides[slideIndex][field] = value;
    setSlides(updatedSlides);
  };

  const addSlide = () => {
    const newSlide = {
      slide_number: slides.length + 1,
      title: 'New Slide',
      content: [],
      layout_type: 'content',
      image_query: '',
      notes: ''
    };
    setSlides([...slides, newSlide]);
  };

  const deleteSlide = (index) => {
    const updatedSlides = slides.filter((_, i) => i !== index);
    updatedSlides.forEach((slide, i) => {
      slide.slide_number = i + 1;
    });
    setSlides(updatedSlides);
  };

  const resetApp = () => {
    setStep('input');
    setTopic('');
    setNumSlides(5);
    setAdditionalContext('');
    setShowContext(false);
    setPresentationId('');
    setSlides([]);
    setError('');
    setEditingSlide(null);
    setPresentationTitle('');
  };

  return (
    <div className="flowstack-theme min-h-[100dvh] relative overflow-hidden">
      <AnimatedBackground />
      <div className="grain" aria-hidden="true" />

      <div className="container mx-auto px-4 pt-14 pb-12 max-w-6xl relative z-10">
        <header className="flowstack-header">
          <p className="flowstack-kicker">AI-Powered Presentation Workflow</p>
          <h1 className="flowstack-title">
            Auto<span className="flowstack-accent">SlideX</span>
          </h1>
          <p className="flowstack-subtitle">Turn a rough idea into a polished deck, one clear stage at a time.</p>
        </header>

        <WorkflowStepper step={step} />

        {error && (
          <div className="mb-6 p-4 bg-red-400/10 border border-red-400/25 rounded-lg text-red-200 max-w-5xl mx-auto">
            {error}
          </div>
        )}

        {notice && (
          <div role="status" className="mb-6 p-4 bg-[#e0a458]/10 border border-[#e0a458]/30 rounded-lg text-[#e0a458] max-w-5xl mx-auto">
            {notice}
          </div>
        )}

        {step === 'input' && (
          <div className="input-workspace mx-auto max-w-3xl">
            <div className="input-controls">
              <PromptInput
                value={topic}
                onChange={setTopic}
                slides={numSlides}
                onSlidesChange={setNumSlides}
                loading={loading}
                onSubmit={generateOutline}
                placeholder="e.g., Introduction to machine learning"
                bottomContent={(
                  <label className="context-toggle ml-2 inline-flex items-center gap-2 cursor-pointer select-none group">
                    <input
                      type="checkbox"
                      checked={showContext}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setShowContext(checked);
                        if (!checked) setAdditionalContext('');
                      }}
                      className="peer sr-only"
                    />
                    <span className="flex size-5 items-center justify-center rounded-md border border-stone-600 bg-stone-900 transition-all duration-200 group-hover:border-stone-500 peer-checked:border-[#e0a458] peer-checked:bg-[#e0a458] peer-focus-visible:ring-2 peer-focus-visible:ring-[#e0a458]/40 [&>svg]:opacity-0 peer-checked:[&>svg]:opacity-100">
                      <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                        <path d="M3 7.5L5.8 10L11 4" stroke="#0c0a09" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </span>
                    <span className="text-xs font-semibold text-stone-300">Context</span>
                    <ChevronDown className={`h-3.5 w-3.5 text-stone-500 transition-transform ${showContext ? 'rotate-180' : ''}`} />
                  </label>
                )}
              />
              {showContext && (
                <div className="context-field rise">
                  <textarea
                    value={additionalContext}
                    onChange={(e) => setAdditionalContext(e.target.value)}
                    placeholder="Add requirements, audience, key points..."
                    rows="3"
                    tabIndex={0}
                    className="mt-3 w-full px-4 py-3 bg-stone-900/80 border border-stone-700 rounded-2xl text-sm placeholder:text-stone-500 focus:border-[#e0a458]/70 focus:outline-none focus:ring-2 focus:ring-[#e0a458]/20 transition-all duration-200 text-stone-50 resize-none"
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {step === 'edit' && (
          <div className="space-y-6">
            <div className="bg-stone-900/70 backdrop-blur-xl rounded-3xl shadow-[0_20px_60px_-20px_rgba(224,164,88,0.12)] p-8 border border-stone-800">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-3xl font-semibold tracking-tight text-stone-50">{presentationTitle}</h2>
                <button
                  onClick={addSlide}
                  className="flex items-center gap-2 px-6 py-3 bg-stone-800 text-stone-100 border border-stone-800 hover:bg-stone-700 active:scale-[0.98] transition-all duration-200 rounded-xl"
                >
                  <Plus className="w-4 h-4" />
                  Add Slide
                </button>
              </div>

              <div className="grid gap-4">
                {slides.map((slide, index) => (
                  <div
                    key={index}
                    style={{ animationDelay: `${Math.min(index, 8) * 50}ms` }}
                    className="rise bg-stone-800/60 border border-stone-800 rounded-2xl p-6 hover:border-[#e0a458]/70"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <span className="flex-shrink-0 flex items-center justify-center w-10 h-10 bg-[#e0a458]/10 text-[#e0a458] border border-[#e0a458]/30 tabular-nums font-bold rounded-full">
                          {slide.slide_number}
                        </span>
                        <div className="flex-1">
                          {editingSlide === index ? (
                            <input
                              type="text"
                              value={slide.title}
                              onChange={(e) => updateSlideContent(index, 'title', e.target.value)}
                              className="w-full text-xl font-bold bg-stone-800 border-2 border-[#e0a458] rounded px-3 py-2 text-stone-50 focus:outline-none"
                            />
                          ) : (
                            <h3 className="text-xl font-semibold tracking-tight text-stone-50 leading-tight">{slide.title}</h3>
                          )}
                          <p className="text-stone-400 italic text-sm mt-2">
                            Content will be generated automatically in Stage 2
                          </p>
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <button
                          onClick={() => setEditingSlide(editingSlide === index ? null : index)}
                          className="p-2 text-stone-400 hover:text-stone-100 hover:bg-stone-700/60 rounded-lg transition-all"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteSlide(index)}
                          className="p-2 text-stone-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-4">
              <button
                onClick={updateSlides}
                disabled={loading}
                className="flex-1 bg-stone-800 text-stone-100 border border-stone-800 hover:bg-stone-700 active:scale-[0.98] transition-all duration-200 py-4 rounded-xl font-semibold text-lg disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Save className="w-5 h-5" />
                Save Changes
              </button>
              <button
                onClick={generatePPT}
                disabled={loading}
                className="flex-1 bg-[#e0a458] text-stone-950 hover:bg-[#ebb269] active:scale-[0.98] transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#e0a458] py-4 rounded-xl font-semibold text-lg disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    Creating PowerPoint...
                  </>
                ) : (
                  <>
                    <FileText className="w-5 h-5" />
                    Generate PowerPoint
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {step === 'download' && (
          <div className="bg-stone-900/70 backdrop-blur-xl rounded-2xl shadow-[0_20px_60px_-20px_rgba(224,164,88,0.12)] p-12 text-center border border-stone-800 max-w-2xl mx-auto">
            <div className="mb-8">
              <div className="w-20 h-20 bg-[#e0a458] rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle2 className="w-10 h-10 text-stone-950" />
              </div>
              <h2 className="text-3xl font-semibold tracking-tight text-stone-50 mb-2">
                Presentation Ready!
              </h2>
              <p className="text-stone-300 text-lg">
                Your PowerPoint with detailed content and images
              </p>
            </div>

            <div className="space-y-4">
              <button
                onClick={downloadPresentation}
                className="w-full bg-[#e0a458] text-stone-950 hover:bg-[#ebb269] active:scale-[0.98] transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#e0a458] py-4 rounded-xl font-semibold text-lg flex items-center justify-center gap-2"
              >
                <Download className="w-5 h-5" />
                Download PowerPoint
              </button>
              <button
                onClick={resetApp}
                className="w-full bg-stone-800/80 text-stone-100 hover:bg-stone-800 active:scale-[0.98] transition-all duration-200 py-4 rounded-xl font-semibold text-lg border border-stone-800"
              >
                Create New Presentation
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}