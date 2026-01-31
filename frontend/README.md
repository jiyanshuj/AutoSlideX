# AutoSlideX Frontend

A modern, interactive React-based frontend for AutoSlideX - an intelligent presentation generation and customization platform.

## Overview

AutoSlideX Frontend is a sophisticated web application built with React and Vite that enables users to generate, customize, and download professional PowerPoint presentations. The application features an animated interactive UI with real-time content editing capabilities.

## Tech Stack

- **Framework**: React 19.1
- **Build Tool**: Vite 7.1
- **Styling**: Tailwind CSS 3.4
- **Icons**: Lucide React 0.544
- **Language**: JavaScript (ES Module)
- **Linting**: ESLint 9.36

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── presentation_genrator.jsx    # Main presentation generator component
│   ├── App.jsx                          # Root application component
│   ├── App.css                          # Application styles
│   ├── main.jsx                         # Application entry point
│   ├── index.css                        # Global styles
│   └── assets/                          # Static assets
├── public/                              # Public static files
├── index.html                           # HTML template
├── vite.config.js                       # Vite configuration
├── tailwind.config.js                   # Tailwind CSS configuration
├── postcss.config.js                    # PostCSS configuration
├── eslint.config.js                     # ESLint configuration
├── package.json                         # Project dependencies and scripts
└── README.md                            # This file
```

## Features

- **Presentation Generator**: Create presentations with customizable content
- **Interactive UI**: Animated background with particle effects and mouse interaction
- **Real-time Editing**: Edit presentation content on the fly
- **Download Capability**: Export presentations as PowerPoint files
- **Modern Design**: Clean and responsive UI powered by Tailwind CSS
- **API Integration**: Seamless backend integration via REST API

## Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Available Scripts

### Development
Start the development server with hot module replacement:
```bash
npm run dev
```
The app will be available at `http://localhost:5173` (default Vite port).

### Build
Build the project for production:
```bash
npm run build
```
Output will be generated in the `dist/` directory.

### Preview
Preview the production build locally:
```bash
npm run preview
```

### Lint
Check code quality with ESLint:
```bash
npm run lint
```

## Configuration

### Vite Configuration
- Configured with React plugin for JSX support
- Optimized for development and production builds

### Tailwind CSS
- Integrated via `@tailwindcss/vite` for optimal build performance
- Customizable through `tailwind.config.js`

### API Configuration
- Backend API URL: `https://autoslidex.onrender.com/api`
- Configured in the PresentationGenerator component

## Browser Support

- Modern browsers supporting ES modules
- Requires JavaScript enabled

## Development Notes

- The application uses functional components with React Hooks
- Animated background uses Canvas API for smooth particle effects
- ESLint enforced for code quality (React recommended rules)
- Tailwind CSS for utility-first styling approach

## Dependencies Overview

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^19.1.1 | UI library |
| react-dom | ^19.1.1 | React DOM rendering |
| lucide-react | ^0.544.0 | Icon library |
| @tailwindcss/vite | ^4.1.14 | Tailwind CSS Vite plugin |
| vite | ^7.1.7 | Build tool |

## Contributing

When contributing to the frontend:
1. Follow the ESLint configuration
2. Maintain code quality with `npm run lint`
3. Use Tailwind CSS classes for styling
4. Test changes locally with `npm run dev`

## Future Enhancements

- [ ] Dark mode support
- [ ] Template library
- [ ] Collaborative editing
- [ ] Advanced styling options
- [ ] Export to multiple formats

## License

Part of the AutoSlideX project.
