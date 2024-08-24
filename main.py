from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import time
import asyncio
from typing import Dict, Any

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# In-memory storage for users and results
users: Dict[str, Dict[str, Any]] = {}
leaderboard = []


with open("python_questions.json", "r") as f:
    questions = json.load(f)


MAX_SCORE_PER_QUESTION = 30

class QuestionTimer:
    def __init__(self, username: str, question_id: int):
        self.username = username
        self.question_id = question_id

    async def auto_submit(self):
        await asyncio.sleep(30)  
        if self.username in users and users[self.username]["current_question"] == self.question_id:
            current_code = users[self.username]["current_code"]
            await submit_code(None, None, self.username, self.question_id, current_code, 0)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login")
async def login(request: Request, background_tasks: BackgroundTasks, username: str = Form(...)):
    if username not in users:
        users[username] = {
            "start_time": time.time(),
            "answers": {},
            "current_question": 0,
            "question_start_time": time.time(),
            "current_code": "",
            "total_score": 0
        }
    
    background_tasks.add_task(QuestionTimer(username, 0).auto_submit)
    
    return templates.TemplateResponse("question.html", {
        "request": request,
        "username": username,
        "question": questions[0],
        "question_number": 1,
        "total_questions": len(questions),
        "function_start": questions[0]["function_start"]
    })

@app.post("/submit-code")
async def submit_code(request: Request, background_tasks: BackgroundTasks, username: str = Form(...), question_id: int = Form(...), code: str = Form(...), score: int = Form(...)):
    if username not in users:
        raise HTTPException(status_code=400, detail="User not logged in")
    
    user_data = users[username]
    
    score = min(score, MAX_SCORE_PER_QUESTION)
    user_data["total_score"] += score
    
    user_data["answers"][question_id] = {
        "code": code,
        "score": score
    }
    user_data["current_question"] += 1
    
    if user_data["current_question"] < len(questions):
        next_question = questions[user_data["current_question"]]
        user_data["question_start_time"] = time.time()
        user_data["current_code"] = ""
        
        background_tasks.add_task(QuestionTimer(username, user_data["current_question"]).auto_submit)
        
        return templates.TemplateResponse("question.html", {
            "request": request,
            "username": username,
            "question": next_question,
            "question_number": user_data["current_question"] + 1,
            "total_questions": len(questions),
            "function_start": next_question["function_start"]
        })
    else:
        return await finish_quiz(request, username)
@app.post("/finish-quiz")
async def finish_quiz(request: Request, username: str):
    if username not in users:
        raise HTTPException(status_code=400, detail="User not logged in")
    
    user_data = users[username]
    end_time = time.time()
    duration = end_time - user_data["start_time"]
    total_score = user_data["total_score"]
    
    
    max_possible_score = len(questions) * MAX_SCORE_PER_QUESTION
    
    leaderboard.append({
        "username": username,
        "score": total_score,
        "duration": duration
    })
    leaderboard.sort(key=lambda x: (-x["score"], x["duration"]))
    
    return templates.TemplateResponse("results.html", {
        "request": request, 
        "username": username, 
        "score": total_score, 
        "max_possible_score": max_possible_score,
        "duration": duration,
        "total_questions": len(questions),
        "MAX_SCORE_PER_QUESTION": MAX_SCORE_PER_QUESTION
    })

@app.get("/leaderboard-data", response_class=HTMLResponse)
async def get_leaderboard_data(request: Request):
    return templates.TemplateResponse("leaderboard_partial.html", {"request": request, "leaderboard": leaderboard[:10]})

@app.post("/update-current-code")
async def update_current_code(username: str = Form(...), code: str = Form(...), score: int = Form(...)):
    if username in users:
        users[username]["current_code"] = code
        users[username]["current_score"] = min(score, MAX_SCORE_PER_QUESTION)
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

