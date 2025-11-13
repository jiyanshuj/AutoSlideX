import React, { useState, useEffect } from 'react';
import { FileText, Download, Edit2, Plus, Trash2, Save, Loader, Sparkles, Zap } from 'lucide-react';

const API_URL = 'https://autoslidex.onrender.com/api';

// Animated 3D Background Component with Mouse Interaction
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
    const connectionDistance = 120;

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

        if (this.x < 0 || this.x > canvas.width) {
          this.vx *= -1;
          this.baseVx *= -1;
        }
        if (this.y < 0 || this.y > canvas.height) {
          this.vy *= -1;
          this.baseVy *= -1;
        }
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

          if (distance < connectionDistance) {
            const opacity = (connectionDistance - distance) / connectionDistance;
            const avgOpacity = (particle.opacity + otherParticle.opacity) / 2;
            ctx.strokeStyle = `rgba(255, 255, 255, ${opacity * avgOpacity * 0.4})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particle.x2d, particle.y2d);
            ctx.lineTo(otherParticle.x2d, otherParticle.y2d);
            ctx.stroke();
          }
        });

        const dxMouse = mouse.x - particle.x;
        const dyMouse = mouse.y - particle.y;
        const distanceToMouse = Math.sqrt(dxMouse * dxMouse + dyMouse * dyMouse);

        if (distanceToMouse < 150) {
          const opacity = (150 - distanceToMouse) / 150;
          ctx.strokeStyle = `rgba(255, 255, 255, ${opacity * 0.6})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(particle.x2d, particle.y2d);
          ctx.lineTo(mouse.x, mouse.y);
          ctx.stroke();
        }
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

export default function App() {
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
      setError('Error connecting to server: ' + err.message);
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
        alert('Slides updated successfully!');
      } else {
        setError('Failed to update slides');
      }
    } catch (err) {
      setError('Error updating slides: ' + err.message);
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
        setError('Failed to generate presentation');
      }
    } catch (err) {
      setError('Error generating PPT: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadPresentation = () => {
    window.open(`${API_URL}/download/${presentationId}`, '_blank');
  };

  const updateSlideContent = (slideIndex, field, value) => {
    const updatedSlides = [...slides];
    if (field === 'content') {
      updatedSlides[slideIndex][field] = value.split('\n').filter(line => line.trim());
    } else {
      updatedSlides[slideIndex][field] = value;
    }
    setSlides(updatedSlides);
  };

  const addSlide = () => {
    const newSlide = {
      slide_number: slides.length + 1,
      title: 'New Slide',
      content: ['Point 1', 'Point 2', 'Point 3'],
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
          <div className="flex items-center justify-center gap-3 mb-3">
            <h1 className="text-5xl font-bold text-white">
              AutoSlideX
            </h1>
          </div>
          <p className="text-gray-300 text-base font-medium">Create professional presentations in minutes with AI</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 backdrop-blur-sm border border-red-500/30 rounded-lg text-red-300">
            {error}
          </div>
        )}

        {step === 'input' && (
          <div className="bg-gray-900/80 backdrop-blur-xl rounded-2xl shadow-2xl p-8 border border-gray-700 max-w-5xl mx-auto">
            <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
              <FileText className="w-7 h-7 text-indigo-400" />
              Tell us about your presentation
            </h2>

            <div className="space-y-6">
              <div className="group">
                <label className="block text-base font-semibold text-gray-200 mb-2">
                  Presentation Topic *
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g., Introduction to Machine Learning"
                  className="w-full min-h-[52px] px-5 py-3 bg-gray-800/80 backdrop-blur-sm border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none transition-all duration-300 text-white text-base placeholder:text-gray-400 placeholder:text-sm hover:bg-gray-800 hover:border-indigo-400/50 leading-relaxed"
                />
              </div>

              <div className="group">
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
                    className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                    style={{
                      background: `linear-gradient(to right, #6366f1 0%, #6366f1 ${((numSlides - 3) / 17) * 100}%, #374151 ${((numSlides - 3) / 17) * 100}%, #374151 100%)`
                    }}
                  />
                  <input
                    type="number"
                    min="3"
                    max="20"
                    value={numSlides}
                    onChange={(e) => {
                      const value = parseInt(e.target.value);
                      if (value >= 3 && value <= 20) {
                        setNumSlides(value);
                      }
                    }}
                    className="w-20 text-center text-xl font-bold text-indigo-400 bg-gray-800/80 border-2 border-gray-700 rounded-lg px-3 py-2 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="group">
                <label className="block text-base font-semibold text-gray-200 mb-2">
                  Additional Context (Optional)
                </label>
                <textarea
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  placeholder="Add any specific requirements, target audience, or key points to include..."
                  rows="3"
                  className="w-full min-h-[100px] px-5 py-3 bg-gray-800/80 backdrop-blur-sm border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none transition-all duration-300 text-white text-base placeholder:text-gray-400 placeholder:text-sm hover:bg-gray-800 hover:border-indigo-400/50 leading-relaxed resize-none"
                />
              </div>

              <button
                onClick={generateOutline}
                disabled={loading}
                className="group relative w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-semibold text-lg transition-all duration-300 disabled:opacity-50 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                <span className="relative flex items-center justify-center gap-2">
                  {loading ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      Generating Outline...
                    </>
                  ) : (
                    <>
                      Generate Presentation
                    </>
                  )}
                </span>
              </button>
            </div>
          </div>
        )}

        {step === 'edit' && (
          <div className="space-y-6">
            <div className="bg-gray-900/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-gray-700">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-3xl font-bold text-white">
                  {presentationTitle}
                </h2>
                <button
                  onClick={addSlide}
                  className="group relative flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-xl transition-all duration-300 overflow-hidden"
                >
                  <div className="absolute inset-0 bg-green-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                  <span className="relative flex items-center gap-2">
                    <Plus className="w-4 h-4" />
                    Add Slide
                  </span>
                </button>
              </div>

              <div className="grid gap-4">
                {slides.map((slide, index) => (
                  <div
                    key={index}
                    className="bg-gray-800/60 backdrop-blur-sm border-2 border-gray-700 rounded-2xl p-6 hover:border-indigo-400/70 transition-all duration-300 hover:bg-gray-800/80 hover:shadow-lg hover:shadow-indigo-500/20"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <span className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold rounded-full shadow-lg">
                          {slide.slide_number}
                        </span>
                        <input
                          type="text"
                          value={slide.title}
                          onChange={(e) => updateSlideContent(index, 'title', e.target.value)}
                          className="text-xl font-bold bg-transparent border-b-2 border-transparent hover:border-indigo-400/50 focus:border-indigo-500 focus:outline-none px-2 py-1 text-white transition-all duration-300 min-w-[200px] leading-relaxed"
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setEditingSlide(editingSlide === index ? null : index)}
                          className="p-2 text-blue-400 hover:bg-blue-500/20 rounded-lg transition-all duration-300"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteSlide(index)}
                          className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-all duration-300"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {editingSlide === index ? (
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-semibold text-gray-200 mb-2">
                            Content (one point per line)
                          </label>
                          <textarea
                            value={slide.content.join('\n')}
                            onChange={(e) => updateSlideContent(index, 'content', e.target.value)}
                            rows="6"
                            className="w-full min-h-[150px] px-4 py-3 bg-gray-800/80 backdrop-blur-sm border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none text-white text-base transition-all duration-300 hover:bg-gray-800 leading-relaxed resize-y"
                          />
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-semibold text-gray-200 mb-2">
                              Layout Type
                            </label>
                            <select
                              value={slide.layout_type}
                              onChange={(e) => updateSlideContent(index, 'layout_type', e.target.value)}
                              className="w-full min-h-[44px] px-4 py-2 bg-gray-800/80 backdrop-blur-sm border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none text-white text-base transition-all duration-300 hover:bg-gray-800 leading-relaxed"
                            >
                              <option value="content" className="bg-gray-800">Content</option>
                              <option value="two_column" className="bg-gray-800">Two Column</option>
                              <option value="image" className="bg-gray-800">Image</option>
                              <option value="title" className="bg-gray-800">Title</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-semibold text-gray-200 mb-2">
                              Image Query
                            </label>
                            <input
                              type="text"
                              value={slide.image_query || ''}
                              onChange={(e) => updateSlideContent(index, 'image_query', e.target.value)}
                              placeholder="e.g., technology, business"
                              className="w-full min-h-[44px] px-4 py-2 bg-gray-800/80 backdrop-blur-sm border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none text-white text-base placeholder:text-gray-400 placeholder:text-sm transition-all duration-300 hover:bg-gray-800 leading-relaxed"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="block text-sm font-semibold text-gray-200 mb-2">
                            Speaker Notes
                          </label>
                          <textarea
                            value={slide.notes || ''}
                            onChange={(e) => updateSlideContent(index, 'notes', e.target.value)}
                            placeholder="Add speaker notes for this slide..."
                            rows="3"
                            className="w-full min-h-[90px] px-4 py-3 bg-gray-800/80 backdrop-blur-sm border-2 border-gray-700 rounded-lg focus:border-indigo-500 focus:outline-none text-white text-base placeholder:text-gray-400 placeholder:text-sm transition-all duration-300 hover:bg-gray-800 leading-relaxed resize-y"
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="ml-11">
                        <ul className="space-y-2">
                          {slide.content.map((point, i) => (
                            <li key={i} className="flex items-start gap-2 text-gray-300">
                              <span className="text-indigo-400 mt-1">•</span>
                              <span>{point}</span>
                            </li>
                          ))}
                        </ul>
                        {slide.layout_type !== 'content' && (
                          <div className="mt-3 text-sm text-gray-400">
                            Layout: <span className="font-semibold text-indigo-400">{slide.layout_type}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-4">
              <button
                onClick={updateSlides}
                disabled={loading}
                className="group relative flex-1 bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg transition-all duration-300 disabled:opacity-50 flex items-center justify-center gap-2 overflow-hidden"
              >
                <div className="absolute inset-0 bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                <span className="relative flex items-center gap-2">
                  <Save className="w-5 h-5" />
                  Save Changes
                </span>
              </button>
              <button
                onClick={generatePPT}
                disabled={loading}
                className="group relative flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-semibold text-lg transition-all duration-300 disabled:opacity-50 flex items-center justify-center gap-2 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                <span className="relative flex items-center gap-2">
                  {loading ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      Generating PPT...
                    </>
                  ) : (
                    <>
                      <FileText className="w-5 h-5" />
                      Generate PowerPoint
                    </>
                  )}
                </span>
              </button>
            </div>
          </div>
        )}

        {step === 'download' && (
          <div className="bg-gray-900/80 backdrop-blur-xl rounded-2xl shadow-2xl p-12 text-center border border-gray-700 max-w-2xl mx-auto">
            <div className="mb-8">
              <div className="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
                <Download className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-3xl font-bold text-white mb-2">
                Presentation Ready!
              </h2>
              <p className="text-gray-300 text-lg">
                Your PowerPoint presentation has been generated successfully
              </p>
            </div>

            <div className="space-y-4">
              <button
                onClick={downloadPresentation}
                className="group relative w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-semibold text-lg transition-all duration-300 flex items-center justify-center gap-2 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                <span className="relative flex items-center gap-2">
                  <Download className="w-5 h-5" />
                  Download PowerPoint
                </span>
              </button>
              <button
                onClick={resetApp}
                className="group relative w-full bg-gray-800/80 backdrop-blur-sm text-white py-4 rounded-xl font-semibold text-lg transition-all duration-300 border-2 border-gray-700 flex items-center justify-center gap-2 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gray-700/80 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                <span className="relative">Create New Presentation</span>
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(-20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}