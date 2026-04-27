import React, { useState, useEffect } from 'react';
import { FileText, Download, Edit2, Plus, Trash2, Save, Loader, AlertCircle, CheckCircle2 } from 'lucide-react';

const API_URL = 'https://autoslidex-wvg0.onrender.com/api';

// Animated Background
const AnimatedBackground = () => {
  useEffect(() => {
    const canvas = document.getElementById('bg-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const particles = [];
    const particleCount = 60;
    const mouse = { x: canvas.width / 2, y: canvas.height / 2 };

    class Particle {
      constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.z = Math.random() * 800;
        this.baseVx = (Math.random() - 0.5) * 0.3;
        this.baseVy = (Math.random() - 0.5) * 0.3;
        this.vx = this.baseVx;
        this.vy = this.baseVy;
        this.vz = (Math.random() - 0.5) * 1.5;
      }

      update() {
        const dx = mouse.x - this.x;
        const dy = mouse.y - this.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < 200) {
          const force = (200 - distance) / 200;
          this.vx += (dx / distance) * force * 0.1;
          this.vy += (dy / distance) * force * 0.1;
        }

        this.x += this.vx;
        this.y += this.vy;
        this.z += this.vz;

        this.vx *= 0.95;
        this.vy *= 0.95;
        this.vx += (this.baseVx - this.vx) * 0.05;
        this.vy += (this.baseVy - this.vy) * 0.05;

        if (this.x < 0 || this.x > canvas.width) { this.vx *= -1; this.baseVx *= -1; }
        if (this.y < 0 || this.y > canvas.height) { this.vy *= -1; this.baseVy *= -1; }
        if (this.z < 0 || this.z > 800) this.vz *= -1;
      }

      draw() {
        const scale = 800 / (800 + this.z);
        const x2d = (this.x - canvas.width / 2) * scale + canvas.width / 2;
        const y2d = (this.y - canvas.height / 2) * scale + canvas.height / 2;
        const size = 1.5 * scale;
        const opacity = (800 - this.z) / 800;

        ctx.fillStyle = `rgba(255, 255, 255, ${opacity * 0.8})`;
        ctx.beginPath();
        ctx.arc(x2d, y2d, size, 0, Math.PI * 2);
        ctx.fill();

        this.x2d = x2d;
        this.y2d = y2d;
        this.opacity = opacity;
      }
    }

    for (let i = 0; i < particleCount; i++) {
      particles.push(new Particle());
    }

    function animate() {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      particles.forEach((particle, i) => {
        particle.update();
        particle.draw();

        particles.slice(i + 1).forEach(otherParticle => {
          const dx = particle.x - otherParticle.x;
          const dy = particle.y - otherParticle.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 120) {
            const opacity = (120 - distance) / 120;
            const avgOpacity = (particle.opacity + otherParticle.opacity) / 2;
            ctx.strokeStyle = `rgba(255, 255, 255, ${opacity * avgOpacity * 0.4})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particle.x2d, particle.y2d);
            ctx.lineTo(otherParticle.x2d, otherParticle.y2d);
            ctx.stroke();
          }
        });
      });

      requestAnimationFrame(animate);
    }

    animate();

    const handleMouseMove = (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <canvas
      id="bg-canvas"
      className="fixed top-0 left-0 w-full h-full -z-10"
      style={{ background: '#000000' }}
    />
  );
};

export default function PresentationGenerator() {
  const [step, setStep] = useState('input');
  const [topic, setTopic] = useState('');
  const [numSlides, setNumSlides] = useState(5);
  const [additionalContext, setAdditionalContext] = useState('');
  const [presentationId, setPresentationId] = useState('');
  const [slides, setSlides] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
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
          additional_context: additionalContext
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
        alert('Slides updated!');
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
    setPresentationId('');
    setSlides([]);
    setError('');
    setEditingSlide(null);
    setPresentationTitle('');
  };

  return (
    <div className="min-h-screen relative overflow-hidden">
      <AnimatedBackground />

      <div className="container mx-auto px-4 py-6 max-w-6xl relative z-10">
        <div className="text-center mb-8">
          <h1 className="text-5xl font-bold text-white mb-3">AutoSlideX</h1>
          <p className="text-gray-300 text-base font-medium">AI-powered presentations in 2 stages</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-300">
            {error}
          </div>
        )}

        {step === 'input' && (
          <div className="bg-gray-900/80 backdrop-blur-xl rounded-2xl shadow-2xl p-8 border border-gray-700 max-w-5xl mx-auto">
            <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
              <FileText className="w-7 h-7 text-indigo-400" />
              Create Your Presentation
            </h2>

            <div className="space-y-6">
              <div>
                <label className="block text-base font-semibold text-gray-200 mb-2">
                  Topic *
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g., Introduction to Machine Learning"
                  className="w-full min-h-[52px] px-5 py-3 bg-gray-800/80 border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none text-white"
                />
              </div>

              <div>
                <label className="block text-base font-semibold text-gray-200 mb-2">
                  Number of Slides
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="3"
                    max="20"
                    value={numSlides}
                    onChange={(e) => setNumSlides(parseInt(e.target.value))}
                    className="flex-1 h-2 bg-gray-700 rounded-lg accent-indigo-500"
                  />
                  <input
                    type="number"
                    min="3"
                    max="20"
                    value={numSlides}
                    onChange={(e) => {
                      const value = parseInt(e.target.value);
                      if (value >= 3 && value <= 20) setNumSlides(value);
                    }}
                    className="w-20 text-center text-xl font-bold text-indigo-400 bg-gray-800/80 border-2 border-gray-700 rounded-lg px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-base font-semibold text-gray-200 mb-2">
                  Additional Context (Optional)
                </label>
                <textarea
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  placeholder="Add requirements, audience, key points..."
                  rows="3"
                  className="w-full px-5 py-3 bg-gray-800/80 border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none text-white resize-none"
                />
              </div>

              <button
                onClick={generateOutline}
                disabled={loading}
                className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-semibold text-lg disabled:opacity-50"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader className="w-5 h-5 animate-spin" />
                    Generating Outline...
                  </span>
                ) : (
                  'Generate Outline'
                )}
              </button>
            </div>
          </div>
        )}

        {step === 'edit' && (
          <div className="space-y-6">
            <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-indigo-400 mt-0.5" />
              <div>
                <p className="text-indigo-300 font-semibold">Preview Mode - Stage 1</p>
                <p className="text-indigo-200/80 text-sm mt-1">
                  Slide titles shown below. Add/edit/delete slides. Detailed content will be generated when you click "Generate PowerPoint".
                </p>
              </div>
            </div>

            <div className="bg-gray-900/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-gray-700">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-3xl font-bold text-white">{presentationTitle}</h2>
                <button
                  onClick={addSlide}
                  className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-xl"
                >
                  <Plus className="w-4 h-4" />
                  Add Slide
                </button>
              </div>

              <div className="grid gap-4">
                {slides.map((slide, index) => (
                  <div
                    key={index}
                    className="bg-gray-800/60 border-2 border-gray-700 rounded-2xl p-6 hover:border-indigo-400/70"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <span className="flex-shrink-0 flex items-center justify-center w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold rounded-full">
                          {slide.slide_number}
                        </span>
                        <div className="flex-1">
                          {editingSlide === index ? (
                            <input
                              type="text"
                              value={slide.title}
                              onChange={(e) => updateSlideContent(index, 'title', e.target.value)}
                              className="w-full text-xl font-bold bg-gray-800 border-2 border-indigo-500 rounded px-3 py-2 text-white focus:outline-none"
                            />
                          ) : (
                            <h3 className="text-xl font-bold text-white leading-tight">{slide.title}</h3>
                          )}
                          <p className="text-gray-400 italic text-sm mt-2">
                            Content will be generated automatically in Stage 2
                          </p>
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <button
                          onClick={() => setEditingSlide(editingSlide === index ? null : index)}
                          className="p-2 text-blue-400 hover:bg-blue-500/20 rounded-lg transition-all"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteSlide(index)}
                          className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-all"
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
                className="flex-1 bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Save className="w-5 h-5" />
                Save Changes
              </button>
              <button
                onClick={generatePPT}
                disabled={loading}
                className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-semibold text-lg disabled:opacity-50 flex items-center justify-center gap-2"
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
          <div className="bg-gray-900/80 backdrop-blur-xl rounded-2xl shadow-2xl p-12 text-center border border-gray-700 max-w-2xl mx-auto">
            <div className="mb-8">
              <div className="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle2 className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-3xl font-bold text-white mb-2">
                Presentation Ready!
              </h2>
              <p className="text-gray-300 text-lg">
                Your PowerPoint with detailed content and images
              </p>
            </div>

            <div className="space-y-4">
              <button
                onClick={downloadPresentation}
                className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-semibold text-lg flex items-center justify-center gap-2"
              >
                <Download className="w-5 h-5" />
                Download PowerPoint
              </button>
              <button
                onClick={resetApp}
                className="w-full bg-gray-800/80 text-white py-4 rounded-xl font-semibold text-lg border-2 border-gray-700"
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