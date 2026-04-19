📌 Overview

🤖 Askly AI – Intelligent Chatbot Web Application

Askly AI is a modern, full-stack AI chatbot web application that delivers professional, 
well-structured responses without markdown symbols. It features user authentication with OTP, 
persistent chat sessions, light/dark theme, profile management, and an admin dashboard. 
In addition , Askly ai is an end-to-end chatbot platform designed to simulate real-world SaaS architecture. 
It focuses on performance, clean system design, and user experience , rather than just UI.


🔗 Live Demo: https://askly-ai-1.onrender.com 
🔗 Direct admin login Live Link : https://askly-ai-1.onrender.com/admin/login 

admin credential=>
*username : admin 
*password : admin123


This project demonstrates:

✔ Full-stack development
✔ API design & integration (LLM)
✔ Authentication & security practices
✔ Database modeling & persistence
✔ Scalable deployment on cloud infrastructur




✨ Features

🔐 User Authentication
Login / Signup with email OTP verification (1-minute expiry) / Forgot password with email OTP verification (1-minute expiry)

💬 Chat Interface
Clean, modern chat UI with message copy and speak buttons

🧠 AI Responses
Powered by Groq’s Llama 3.3 70B, formatted without markdown symbols

📚 Chat History
All conversations saved and organised into sessions (rename/delete)

🎨 Theme Toggle
Light / dark mode with persistent user preference

👤 Profile Management
Upload / reset profile photo (default fallback)

🛡️ Admin Panel
View total users, user table (username, email, creation date), registration chart

📧 Email Integration
OTP sending via Gmail SMTP

🗄️ PostgreSQL Database
All data stored in Render’s managed PostgreSQL (users, OTPs, sessions, messages)

📱 Responsive Design
Works on desktop, tablet, and mobile





🛠️ Tools & Technologies

💻 Backend → Python 3.12, Flask
🗄️ Database → PostgreSQL (Render), SQLAlchemy ORM
🤖 AI / LLM → Groq Cloud (Llama 3.3 70B)
🔐 Authentication → bcrypt (password hashing), OTP via email
📧 Email → Flask-Mail, Gmail SMTP
🎨 Frontend → HTML5, CSS3, JavaScript, Chart.js
🚀 Deployment → Render (Web Service + PostgreSQL)
📦 Version Control → Git, GitHub





🚀 Quick Start (Local Development)

⚙️ Prerequisites

🧩 Python 3.12+
🔧 Git
🌐 MongoDB Atlas (for OTP storage – optional)
📧 Gmail account (for OTP emails)


🛠️ Setup

```bash
# Clone the repository
git clone https://github.com/askly-ai-2026/askly.ai.git
cd askly.ai

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file (see .env.example)
cp .env.example .env
# Edit .env with your keys

# Run the app
python app.py
```


👨‍💻 Author =>

Developed by " Neel Soni " as a full-stack project to demonstrate "production-level engineering skills" in AI-powered applications.
