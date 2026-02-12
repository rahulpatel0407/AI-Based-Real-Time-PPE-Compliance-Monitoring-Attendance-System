#!/bin/bash

# IOCL Refinery Safety System - Quick Start Guide

echo "=========================================="
echo "IOCL Refinery Safety & Attendance System"
echo "=========================================="
echo ""

# Check Python installation
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python detected"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Create database
echo "🗄️  Initializing database..."
python -c "from database import init_db; init_db(); print('✓ Database initialized')"
echo ""

echo "=========================================="
echo "Running Multiple Services"
echo "=========================================="
echo ""

# Start Flask backend in background
echo "🚀 Starting Flask Backend (Port 5000)..."
python backend.py &
BACKEND_PID=$!
sleep 2

# Check if backend started
if ps -p $BACKEND_PID > /dev/null; then
    echo "✓ Backend running (PID: $BACKEND_PID)"
else
    echo "❌ Backend failed to start"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ System is Ready!"
echo "=========================================="
echo ""
echo "📊 Access the Dashboard:"
echo "   → http://localhost:5000"
echo ""
echo "📱 Streamlit App:"
echo "   → streamlit run app1.py"
echo ""
echo "🔧 Backend API Docs:"
echo "   → Check IOCL_DASHBOARD_README.md"
echo ""
echo "⚠️  Press Ctrl+C to stop all services"
echo ""

# Wait for interrupt
trap "kill $BACKEND_PID 2>/dev/null; echo ''; echo '✓ Services stopped'; exit 0" INT
wait $BACKEND_PID
