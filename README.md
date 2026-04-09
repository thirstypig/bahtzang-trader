# bahtzang-trader

A full-stack trading application with a Next.js frontend and FastAPI backend.

## Project Structure

```
bahtzang-trader/
├── frontend/   # Next.js 14 (App Router) + Tailwind CSS
├── backend/    # Python FastAPI
└── package.json # Root scripts for running both services
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+

### Installation

```bash
# Install frontend dependencies
npm run install:frontend

# Install backend dependencies
npm run install:backend
```

### Development

```bash
# Run both frontend and backend concurrently
npm run dev

# Run individually
npm run dev:frontend   # http://localhost:3060
npm run dev:backend    # http://localhost:4060
```

## API Documentation

Once the backend is running, visit [http://localhost:4060/docs](http://localhost:4060/docs) for the interactive Swagger UI.
