# Frontend - Agentic Assistant POC

React frontend for the Agentic Assistant POC. Provides a modern chat interface for interacting with the intelligent agent.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will run on `http://localhost:5173` and automatically connect to the backend on `http://localhost:8000`.

**Note:** Make sure the backend is running on port 8000 before starting the frontend.

## Project Structure

```
frontend/
├── src/
│   ├── App.jsx          # Main application component
│   ├── main.jsx         # React entrypoint
│   ├── index.css        # Global styles
│   ├── components/     # Reusable UI components
│   │   └── ui/         # Base UI components (accordion, button, card, input, scroll-area)
│   └── lib/            # Utility functions
│       └── utils.js     # Helper functions (clsx, tailwind-merge)
├── index.html          # HTML template
├── package.json        # Dependencies and scripts
├── vite.config.js      # Vite configuration
└── tailwind.config.js  # TailwindCSS configuration
```

## Features

### Chat Interface
- **Clean UI:** Modern, responsive chat interface built with React and TailwindCSS
- **Message History:** Displays conversation history with user questions and assistant responses
- **Loading States:** Visual feedback during API calls
- **Error Handling:** User-friendly error messages

### Expandable Details
- **SQL Queries:** Expandable section showing generated SQL queries (if SQL route was used)
- **Citations:** Expandable section showing document citations with source, page, and content (if RAG route was used)
- **Tool Trace:** Expandable section showing agent decision-making process (for debugging and transparency)

### Session Management
- **Session Persistence:** Automatically generates and maintains session IDs for conversation continuity
- **Context Awareness:** Follow-up questions maintain context from previous exchanges

## Technology Stack

- **Framework:** React 18
- **Build Tool:** Vite 5
- **Styling:** TailwindCSS 3
- **UI Components:** Radix UI (accordion, scroll-area, slot)
- **Icons:** Lucide React
- **Markdown:** react-markdown (for rendering assistant responses)

## Environment Variables

Create `frontend/.env.local` to override default configuration:

```bash
VITE_API_URL=http://localhost:8000
```

**Default:** `http://localhost:8000` (development)

**Production:** Set `VITE_API_URL` to your backend URL (e.g., `https://your-backend.onrender.com`)

**Important:** Do NOT include the `/api` prefix. The frontend will append `/api/v1/ask` automatically.

## Development

### Start Development Server

```bash
npm run dev
```

The development server runs on `http://localhost:5173` with hot module replacement (HMR).

### Build for Production

```bash
npm run build
```

This creates an optimized production build in `frontend/dist/`.

### Preview Production Build

```bash
npm run preview
```

This serves the production build locally for testing.

## Deployment

### Vercel Deployment (Recommended)

The frontend is optimized for deployment on [Vercel](https://vercel.com) due to:
- Optimized for static sites and React applications
- Automatic HTTPS and CDN
- Zero-configuration deployment

#### Quick Setup

1. **Connect Repository:**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your Git repository

2. **Configure Project:**
   - **Framework Preset:** Vite (auto-detected)
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build` (auto-detected)
   - **Output Directory:** `dist` (auto-detected)

   Alternatively, you can use the root-level `vercel.json` which is configured for frontend-only deployment.

3. **Environment Variables:**
   ```
   VITE_API_URL=https://your-backend.onrender.com
   ```
   
   **Important:** Do NOT include the `/api` prefix. The frontend will append `/api/v1/ask` automatically.

4. **Deploy:**
   - Click "Deploy"
   - Vercel will build and deploy your frontend
   - Frontend will be available at `https://your-project.vercel.app`

### Other Platforms

The frontend can be deployed to any static hosting service:
- **Netlify:** Connect repository, set build command `npm run build`, output directory `dist`
- **GitHub Pages:** Use GitHub Actions to build and deploy
- **AWS S3 + CloudFront:** Upload `dist/` folder to S3 bucket, configure CloudFront

## API Integration

The frontend communicates with the backend via REST API:

**Endpoint:** `POST /api/v1/ask`

**Request:**
```json
{
  "question": "Monthly RAV4 HEV sales in Germany in 2024",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "answer": "The monthly RAV4 HEV sales in Germany in 2024...",
  "sql_query": "SELECT month, SUM(contracts) FROM FACT_SALES...",
  "citations": [
    {
      "source_document": "Contract_Toyota_2023.pdf",
      "page": 4,
      "content": "Relevant snippet..."
    }
  ],
  "tool_trace": [
    "Router selected: SQL_Tool",
    "SQL_Tool executed with query: '...'"
  ],
  "session_id": "generated-or-provided-session-id",
  "rate_limit_info": {
    "remaining_interactions": 19,
    "daily_limit": 20,
    "current_count": 1
  }
}
```

**Error Handling:**
- `422 Unprocessable Entity`: Validation error (empty question, exceeds max length, SQL injection detected)
- `429 Too Many Requests`: Daily interaction limit exceeded
- `500 Internal Server Error`: Unexpected internal error
- `503 Service Unavailable`: External service (OpenAI API) unavailable

## CORS Configuration

The backend must be configured to allow requests from the frontend origin.

**Backend Configuration (Render):**
```
CORS_ORIGINS=https://your-frontend.vercel.app
```

For multiple origins (comma-separated):
```
CORS_ORIGINS=https://frontend1.vercel.app,https://frontend2.vercel.app
```

Local development origins (`localhost:5173`, `localhost:3000`) are included by default, so CORS works automatically during local development.

## Troubleshooting

**Common Issues:**

| Issue | Solution |
|-------|----------|
| `Failed to fetch` | Check that `VITE_API_URL` is set correctly and backend is running |
| CORS errors | Verify `CORS_ORIGINS` in backend includes your frontend URL |
| API requests fail | Check browser console for error messages and verify backend health |
| Build fails | Ensure Node.js 18+ is installed and dependencies are installed |

**Verification Steps:**

```bash
# Check Node.js version
node --version  # Should be 18+

# Check dependencies installed
npm list --depth=0

# Test API connection
curl http://localhost:8000/health  # Should return {"status":"ok"}

# Check environment variables
echo $VITE_API_URL  # Should be set in production
```

## Development Notes

### Component Structure

- **App.jsx:** Main application component with chat interface, message history, and expandable details
- **UI Components:** Reusable components from `components/ui/` (accordion, button, card, input, scroll-area)
- **Utilities:** Helper functions in `lib/utils.js` for className merging and conditional styling

### Styling

- **TailwindCSS:** Utility-first CSS framework for rapid UI development
- **Custom Styles:** Global styles in `index.css`, component-specific styles using Tailwind classes
- **Responsive Design:** Mobile-first approach with responsive breakpoints

### State Management

- **React Hooks:** Uses `useState` for local component state (messages, loading, errors)
- **Session Management:** Session IDs stored in component state, passed to API requests
- **No External State:** No Redux or Context API needed for this POC (simple state requirements)

## Future Enhancements

- **Streaming Responses:** Server-Sent Events (SSE) for real-time answer streaming
- **Markdown Rendering:** Enhanced markdown rendering for code blocks and tables
- **Dark Mode:** Theme switching between light and dark modes
- **Export Conversations:** Download conversation history as JSON or PDF
- **Keyboard Shortcuts:** Shortcuts for common actions (send message, clear history)

## Documentation

- **[Main README](../README.md)** - Project overview and quick start
- **[Backend README](../backend/README.md)** - Backend API documentation

