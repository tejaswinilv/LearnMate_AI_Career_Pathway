# LearnMate - Agentic AI for Personalized Course Pathways

**AICTE 2026 - IBM SkillsBuild University Engagement (Edunet Foundation)**
**Problem Statement No.12 - Agentic AI for Personalized Course Pathways**

## Overview
LearnMate is a conversational AI career-learning coach. Students often struggle to pick the right learning path given the overwhelming number of online courses and lack of personalized guidance. LearnMate solves this by acting as an Agentic AI coach that:

- Understands the student's field of interest (e.g. Web Development, Cybersecurity, Data Science, UI/UX Design)
- Assesses their current skill level and available study time through natural conversation
- Generates a structured, sequenced course roadmap with clear stages, time estimates, and free learning resources
- Tracks progress as the student completes stages, and adapts the roadmap if their goals or availability change

## Tech Stack
- **Model**: IBM Granite (via IBM watsonx.ai)
- **Backend**: Python, Flask
- **Frontend**: HTML/CSS/JS (server-rendered chat interface)
- **Cloud**: IBM Cloud Lite services
- **Built using**: IBM Bob (AI coding assistant)

## Features
- Natural conversation flow: goal → skill assessment → personalized roadmap
- Live sidebar showing Progress (ring + stage list), My Roadmap (formatted, downloadable), and Profile (captured interests, skill level, study time)
- Functional quick-action buttons (Create roadmap / Update progress / Change goal / Ask a question)
- Roadmap resource links use verified domains and safe YouTube search links to avoid broken/hallucinated URLs
- Custom branding (logo, consistent color theme)

## Project Structure

├── app.py # Flask app entry point
├── learnmate_agent.py # Core agent logic / watsonx.ai integration
├── requirements.txt # Python dependencies
├── .env.example # Template for required environment variables
└── .gitignore


## Setup & Run Locally
1. Clone this repository
2. Install dependencies:

pip install -r requirements.txt

3. Copy `.env.example` to `.env` and fill in your own IBM watsonx.ai credentials (leave these blank in this repo — fill them only in your own local `.env`, never commit real values):

WATSONX_API_URL=
WATSONX_MODEL_ID=
WATSONX_PROJECT_ID=
WATSONX_API_KEY=

4. Run the app:

python app.py

5. Open `http://localhost:5000` in your browser

## Technology Requirement
Use of IBM Cloud Lite services / IBM Granite — as mandated by the problem statement.

## Author
Tejaswini LV


## Screenshots

### 1. Conversation Flow — Interest & Skill Assessment
LearnMate greets the student, captures their career interest (web development), and asks structured questions to assess skill level and available study time.

![Conversation flow](<img width="1909" height="1070" alt="agentss1" src="https://github.com/user-attachments/assets/09355aac-9860-42fc-af1f-ddfd97ad1531" />
)

### 2. Personalized Roadmap Generation
Based on the student's intermediate skill level and 7 hours/week availability, LearnMate generates a structured, stage-by-stage roadmap with time estimates and free resources, downloadable via the "Download Roadmap" button.

![Roadmap generation](<img width="1902" height="1075" alt="agentss2" src="https://github.com/user-attachments/assets/4d255922-25a5-49b2-9400-2eb69bccdb04" />
)

### 3. Profile Tab — Captured Student Data
The Profile tab shows the career goal, skill level, study time, and current stage — all captured live from the conversation, no manual form-filling required.

![Profile tab](<img width="1904" height="1070" alt="agentss3" src="https://github.com/user-attachments/assets/7b5ae767-1dbd-42c3-a294-2ffb751718c7" />
)
