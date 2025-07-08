# UI Development Commands

## Frontend
```bash
cd ui/frontend
npm install  # Install dependencies
npm run dev  # Start development server on port 5173
```

## Backend
```bash
cd ui/backend
python3 -m venv venv  # Create virtual environment
source venv/bin/activate  # Activate virtual environment
pip install -r requirements.txt  # Install dependencies
uvicorn main:app --reload --port 8000  # Start backend server
```

## Both Servers
Start both servers in separate terminals for the full application.