#!/bin/bash

# Start the Versioned File Manager API Server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
DATA_DIR="$SCRIPT_DIR/data"

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"

# Set environment variables
export VFM_DATA_DIR="$DATA_DIR"

# Start the server
cd "$SRC_DIR"
echo "Starting VFM API Server..."
echo "Data directory: $DATA_DIR"
echo "Server: http://127.0.0.1:8765"
echo ""
python -m uvicorn api.server:app --host 127.0.0.1 --port 8765
