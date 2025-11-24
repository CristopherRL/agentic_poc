# Frontend - Agentic Assistant POC

React frontend for the Agentic Assistant POC.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will run on `http://localhost:5173` and automatically proxy API requests to `http://localhost:8000`.

## Project Structure

```
frontend/
├── src/
│   ├── components/   # React components
│   │   ├── Chat.jsx
│   │   └── Message.jsx
│   ├── App.jsx       # Main app component
│   ├── main.jsx      # Entry point
│   └── styles.css    # Global styles
├── index.html
└── package.json
```

## Environment Variables

Create `.env.local` for local development:

```env
VITE_API_URL=http://localhost:8000
```

For production, set `VITE_API_URL` to your backend URL (e.g., `https://your-backend.onrender.com`).

**Note:** The backend is deployed on Render (not Vercel) due to size limitations. The frontend is deployed on Vercel.

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build

## Features

- **Chat Interface:** Simple, clean chat UI for asking questions
- **Message History:** Displays conversation history
- **Expandable Details:** 
  - SQL queries (if SQL route was used)
  - Citations (if RAG route was used)
  - Tool trace (for debugging)

## Deployment

### Vercel Deployment

1. **Connect Repository:**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your Git repository

2. **Configure Project:**
   - **Framework Preset:** Vite (auto-detected)
   - **Root Directory:** `frontend`
   - Build settings are auto-detected

3. **Environment Variables:**
   - Set `VITE_API_URL` to your backend URL (e.g., `https://your-backend.onrender.com`)
   - **Important:** Do NOT include `/api` prefix

4. **Deploy:**
   - Click "Deploy"
   - Frontend will be available at `https://your-project.vercel.app`

**Note:** The backend is deployed separately on Render. Ensure `CORS_ORIGINS` is configured in the backend to allow requests from your Vercel frontend URL.

See main [README.md](../README.md) for complete deployment instructions.


