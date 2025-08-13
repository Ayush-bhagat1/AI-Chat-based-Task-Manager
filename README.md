# 📝 Task Management App

A full-stack task management application with a **Next.js frontend**, **Python backend**, and **PostgreSQL database** setup via Docker Compose.

## 🚀 Quick Start

### 1. Clone the Repository

git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
2. Start PostgreSQL using Docker Compose

docker-compose up -d
This will spin up a PostgreSQL container accessible from your backend.

3. Set Up Backend

cd backend
# (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the backend server
python main.py  # or uvicorn main:app --reload for FastAPI
4. Set Up Frontend

cd ../my-task-app
npm install
npm run dev
The frontend will run on http://localhost:3000

✅ Prerequisites
Docker & Docker Compose

Python 3.8+

Node.js 18+
