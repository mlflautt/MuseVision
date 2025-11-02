#!/bin/bash
# World-Building Graph Viewer Launch Script

echo "🌍 World-Building Network Viewer"
echo "================================="
echo

# Export fresh graph data
echo "📊 Exporting graph data..."
cd _export && python3 export_graph.py

# Launch HTTP server
echo "🚀 Starting local server on http://localhost:8000"
echo "📱 Open viewer at: http://localhost:8000/viewer.html"
echo
echo "Press Ctrl+C to stop the server"
echo

# Start server (this will run in foreground)
python3 -m http.server 8000